"""LangGraph-based agentic claim verification pipeline."""

import json
import logging
from typing import TypedDict, Annotated, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from config.settings import get_llm_temperature, settings
from src.agent.prompts import AGENT_SYSTEM_PROMPT, INVALID_CLAIM_RESPONSE
from src.agent.tools import ALL_TOOLS
from src.core.verification import synthesize_response, verify_claim as _verify_claim_core

logger = logging.getLogger(__name__)

# Tools that return evidence we accumulate for verify_and_synthesize
EVIDENCE_TOOL_NAMES = frozenset({
    "scrape_news", "scrape_finance", "scrape_government", "scrape_science", "fetch_weather", "search_static_kb", "search_historical",
})

# When we already have this many evidence items, skip any further scrape_* / search_historical calls
MIN_EVIDENCE_TO_SKIP_MORE_SEARCH = 2


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def _add_messages(
    existing: Sequence[BaseMessage],
    new: Sequence[BaseMessage],
) -> Sequence[BaseMessage]:
    return list(existing) + list(new)


def _extend_evidence(existing: list, new: list) -> list:
    """Reducer: append new evidence items to existing."""
    if not new:
        return existing
    return list(existing) + list(new)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], _add_messages]
    claim: str
    reasoning_trace: list[str]
    step_count: int
    collected_evidence: Annotated[list, _extend_evidence]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=get_llm_temperature(),
        max_tokens=getattr(settings, "max_agent_response_tokens", 2048) or 2048,
    )


def agent_node(state: AgentState) -> dict:
    """The main agent reasoning node — calls the LLM with tools."""
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    system_prompt = AGENT_SYSTEM_PROMPT.format(max_steps=settings.max_agent_steps)

    # Build messages: system + conversation history
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    response = llm_with_tools.invoke(messages)

    # Track step count
    step_count = state.get("step_count", 0) + 1
    reasoning_trace = list(state.get("reasoning_trace", []))

    # Log the agent's reasoning (DEBUG only; log truncated for readability — full content is in state)
    if response.content:
        reasoning_trace.append(f"Step {step_count}: {response.content[:200]}")
        logger.debug("Agent step %d (first 200 chars): %s", step_count, response.content[:200])

    return {
        "messages": [response],
        "step_count": step_count,
        "reasoning_trace": reasoning_trace,
    }


def should_continue(state: AgentState) -> str:
    """Decide whether to continue tool execution or finish."""
    messages = state["messages"]
    last_message = messages[-1]
    step_count = state.get("step_count", 0)

    # If we've hit the max steps, stop
    if step_count >= settings.max_agent_steps:
        logger.debug("Agent hit max steps (%d), stopping.", settings.max_agent_steps)
        return "end"

    # If the last message has tool calls, continue to tool execution
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, the agent is done
    return "end"


def after_tools_route(state: AgentState) -> str:
    """After running tools: skip the final agent turn if we already have a verification result (avoids hang on long summary)."""
    messages = state["messages"]
    for msg in reversed(messages):
        if hasattr(msg, "name") and msg.name == "verify_and_synthesize":
            logger.debug("Skipping final agent turn; verification result already present.")
            return "end"
    return "agent"


# ---------------------------------------------------------------------------
# Tools node: run tools, accumulate evidence, inject into verify_and_synthesize
# ---------------------------------------------------------------------------

def _evidence_from_result(tool_name: str, result: object) -> list[dict]:
    """Extract evidence list from a tool result for accumulation."""
    if tool_name in ("scrape_news", "scrape_finance", "scrape_government", "scrape_science", "fetch_weather", "search_historical"):
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return [{"content": e.get("content", ""), "source_url": e.get("source_url", ""), "source_title": e.get("source_title", "")} for e in result]
    if tool_name == "search_static_kb" and isinstance(result, dict) and "results" in result:
        return [
            {"content": r.get("content", ""), "source_url": r.get("source_url", ""), "source_title": r.get("source_title", "")}
            for r in result["results"]
        ]
    return []


def tools_node(state: AgentState) -> dict:
    """
    Execute tool calls, accumulate evidence from search/scrape tools, and when
    the agent calls verify_and_synthesize use the accumulated evidence so we
    never pass an empty list when we have evidence.
    """
    messages = list(state["messages"])
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    if not tool_calls:
        return {"messages": [], "collected_evidence": []}

    tools_by_name = {t.name: t for t in ALL_TOOLS}
    collected_so_far = list(state.get("collected_evidence") or [])
    new_evidence_this_round: list[dict] = []
    tool_messages: list[ToolMessage] = []

    for tc in tool_calls:
        if isinstance(tc, dict):
            name = tc.get("name")
            tid = tc.get("id")
            args = dict(tc.get("args") or {})
        else:
            name = getattr(tc, "name", None)
            tid = getattr(tc, "id", None)
            args = dict(getattr(tc, "args", None) or {})
        if not name:
            continue
        # Inject accumulated evidence so the LLM doesn't have to pass it
        if name == "verify_and_synthesize" and collected_so_far:
            args["evidence"] = collected_so_far
        # Skip duplicate scrape/search when we already have enough evidence (avoids extra web search)
        if name in ("scrape_news", "scrape_finance", "scrape_government", "scrape_science", "search_historical"):
            if len(collected_so_far) >= MIN_EVIDENCE_TO_SKIP_MORE_SEARCH:
                n = len(collected_so_far)
                tool_messages.append(ToolMessage(
                    content=(
                        f"You already have sufficient evidence ({n} items) from a previous search. "
                        "Do not search again. Proceed to verify_and_synthesize with the evidence you have."
                    ),
                    tool_call_id=tid or "",
                    name=name,
                ))
                continue
        tool = tools_by_name.get(name)
        if not tool:
            tool_messages.append(ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tid or "", name=name))
            continue
        try:
            result = tool.invoke(args)
        except Exception as e:
            tool_messages.append(ToolMessage(content=str(e), tool_call_id=tid or "", name=name, status="error"))
            continue
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        tool_messages.append(ToolMessage(content=content, tool_call_id=tid or "", name=name))
        evidence = _evidence_from_result(name, result)
        # Only use static KB results as evidence when above threshold; otherwise agent must search online
        if name == "search_static_kb" and isinstance(result, dict) and not result.get("above_threshold"):
            evidence = []
        if evidence:
            collected_so_far.extend(evidence)
            new_evidence_this_round.extend(evidence)

    return {"messages": tool_messages, "collected_evidence": new_evidence_this_round}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_agent_graph() -> StateGraph:
    """Build the LangGraph agent workflow."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Add conditional edges
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    # After tools: go to agent for a summary, or end if we already have verify_and_synthesize result
    graph.add_conditional_edges("tools", after_tools_route, {"agent": "agent", "end": END})

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(claim: str) -> dict:
    """
    Run the agentic claim verification pipeline.

    Args:
        claim: The claim to verify.

    Returns:
        {
            "claim": str,
            "verdict": str,
            "reasoning": str,
            "citations": list,
            "reasoning_trace": list[str],
            "formatted_response": str,
        }
    """
    logger.debug("Running agent for claim: %s", claim)

    # Build and invoke the graph
    app = build_agent_graph()

    initial_state = {
        "messages": [
            HumanMessage(
                content=(
                    f"Please verify the following claim. Use your tools to gather evidence, "
                    f"cross-check sources, and produce a verdict.\n\n"
                    f"CLAIM: {claim}"
                )
            ),
        ],
        "claim": claim,
        "reasoning_trace": [],
        "step_count": 0,
        "collected_evidence": [],
    }

    final_state = app.invoke(initial_state)

    # Extract the final response
    messages = final_state["messages"]
    reasoning_trace = final_state.get("reasoning_trace", [])

    # Get the last non-tool message content as the response
    final_content = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            final_content = msg.content
            break
        # Also check if it has tool_calls but also content
        if hasattr(msg, "content") and msg.content:
            final_content = msg.content
            break

    # Try to extract structured verdict from tool results
    verification_result = _extract_verification_result(messages)

    # If agent hit max steps without calling verify_and_synthesize, run verification on collected evidence if any
    if verification_result is None:
        collected = list(final_state.get("collected_evidence") or [])
        if collected:
            logger.debug("Max steps hit with %d evidence items; running verification on collected evidence.", len(collected))
            verification_result = _verify_claim_core(claim, collected)
        else:
            # No evidence; return a clear response for the extension (valid JSON with user-facing message)
            verification_result = {
                "verdict": "Incomplete",
                "reasoning": "Verification did not complete within the step limit. Try a shorter claim or try again.",
                "citations": [],
            }

    if verification_result:
        formatted = synthesize_response(claim, verification_result, reasoning_trace)
    else:
        formatted = final_content or INVALID_CLAIM_RESPONSE

    verdict = verification_result.get("verdict", "Unknown")
    reasoning = verification_result.get("reasoning", final_content)
    citations = verification_result.get("citations", [])
    return {
        "claim": claim,
        "verdict": verdict,
        "reason": reasoning,
        "reasoning": reasoning,
        "citations": citations,
        "reasoning_trace": reasoning_trace,
        "formatted_response": formatted,
    }


def _extract_verification_result(messages: list) -> dict | None:
    """
    Walk through messages looking for the verify_and_synthesize tool result.
    """
    for msg in reversed(messages):
        if hasattr(msg, "name") and msg.name == "verify_and_synthesize":
            # This is a ToolMessage with the result
            content = msg.content
            if isinstance(content, str):
                import json
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass
            elif isinstance(content, dict):
                return content
    return None
