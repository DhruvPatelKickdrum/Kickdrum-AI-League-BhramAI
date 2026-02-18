"""Main entry point — programmatic API for claim verification."""

from config.logging_config import setup_logging
from config.settings import settings
from src.agent.agent import run_agent
from src.agent.prompts import INVALID_CLAIM_RESPONSE
from src.utils.validators import validate_claim


def verify_claim(claim: str) -> dict:
    """
    Verify a factual claim using the agentic RAG pipeline.

    Args:
        claim: The claim text to verify.

    Returns:
        {
            "claim": str,
            "verdict": str,
            "reasoning": str,
            "citations": list[dict],
            "reasoning_trace": list[str],
            "formatted_response": str,
        }
    """
    setup_logging(settings.log_level)

    try:
        claim = validate_claim(claim)
    except ValueError as e:
        return {
            "claim": claim,
            "verdict": "Invalid",
            "reasoning": str(e),
            "citations": [],
            "reasoning_trace": [],
            "formatted_response": INVALID_CLAIM_RESPONSE,
        }

    return run_agent(claim)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python main.py '<claim>'")
        sys.exit(1)

    claim_text = " ".join(sys.argv[1:])
    result = verify_claim(claim_text)
    print("\n" + result["formatted_response"])
