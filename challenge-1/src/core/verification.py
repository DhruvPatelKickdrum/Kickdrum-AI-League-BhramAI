"""Claim verification and synthesis logic."""

import json
import logging

from openai import OpenAI

from config.settings import get_llm_temperature, settings

logger = logging.getLogger(__name__)

VERDICT_NOT_ENOUGH = "Not Enough Evidence"

VERIFICATION_SYSTEM_PROMPT = """\
You are a fact-checking assistant. Your job is to compare a user's claim against \
the provided evidence and produce a verdict.

Rules:
1. You MUST only use information from the provided evidence. Never fabricate sources.
2. If the evidence supports the claim, verdict is "Supported".
3. If the evidence contradicts the claim, verdict is "Contradicted".
4. If there is not enough evidence to determine truth, verdict is "Not Enough Evidence".
5. If sources conflict with each other, verdict is "Conflicting Evidence".
6. Always cite the specific sources that support your verdict.
7. Provide clear, transparent reasoning for your verdict.

Respond in this JSON format:
{
  "verdict": "Supported|Contradicted|Not Enough Evidence|Conflicting Evidence",
  "reasoning": "Step-by-step explanation of how you reached this verdict.",
  "citations": [
    {"source_url": "...", "source_title": "...", "relevant_snippet": "..."}
  ]
}
"""


def verify_claim(
    claim: str,
    evidence: list[dict],
) -> dict:
    """
    Verify a claim against gathered evidence.

    Args:
        claim: The user's claim to verify.
        evidence: List of evidence dicts, each with 'content', 'source_url', 'source_title'.

    Returns:
        {"verdict": ..., "reasoning": ..., "citations": [...]}
    """
    if not evidence:
        return {
            "verdict": VERDICT_NOT_ENOUGH,
            "reasoning": "No evidence was found to verify or refute this claim.",
            "citations": [],
        }

    # Format evidence for the prompt
    evidence_text = ""
    for i, e in enumerate(evidence, 1):
        source = e.get("source_url", "Unknown source")
        title = e.get("source_title", "Untitled")
        content = e.get("content", "")
        evidence_text += f"\n[Source {i}] {title} ({source}):\n{content}\n"

    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"CLAIM: {claim}\n\nEVIDENCE:{evidence_text}",
            },
        ],
        temperature=get_llm_temperature(),
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    logger.info("Verification response: %s", raw[:200])

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse verification response: %s", raw)
        return {
            "verdict": VERDICT_NOT_ENOUGH,
            "reasoning": "Failed to process verification results.",
            "citations": [],
        }

    return {
        "verdict": result.get("verdict", VERDICT_NOT_ENOUGH),
        "reasoning": result.get("reasoning", ""),
        "citations": result.get("citations", []),
    }


SYNTHESIS_SYSTEM_PROMPT = """\
You are a claim verification assistant. Synthesize the verification results into a \
clear, user-friendly response.

Format your response as:
1. **Verdict:** [Supported/Contradicted/Not Enough Evidence/Conflicting Evidence]
2. **Reasoning:** [Clear explanation]
3. **Sources:**
   - [Source title](source_url): relevant snippet

Keep the response concise but thorough. Always include source citations.
"""


def synthesize_response(
    claim: str,
    verification_result: dict,
    reasoning_trace: list[str] | None = None,
) -> str:
    """
    Produce a final human-readable response.

    Args:
        claim: The original claim.
        verification_result: Output from verify_claim().
        reasoning_trace: Optional list of agent reasoning steps.

    Returns:
        A formatted string response.
    """
    verdict = verification_result.get("verdict", VERDICT_NOT_ENOUGH)
    reasoning = verification_result.get("reasoning", "")
    citations = verification_result.get("citations", [])

    # Build response
    lines = [
        f"**Claim:** {claim}",
        "",
        f"**Verdict:** {verdict}",
        "",
        f"**Reasoning:** {reasoning}",
        "",
    ]

    if citations:
        lines.append("**Sources:**")
        for cite in citations:
            title = cite.get("source_title", "Source")
            url = cite.get("source_url", "")
            snippet = cite.get("relevant_snippet", "")
            if url:
                lines.append(f"- [{title}]({url}): {snippet}")
            else:
                lines.append(f"- {title}: {snippet}")

    if reasoning_trace:
        lines.append("")
        lines.append("**Agent Reasoning Trace:**")
        for i, step in enumerate(reasoning_trace, 1):
            lines.append(f"  {i}. {step}")

    return "\n".join(lines)
