#!/usr/bin/env python3
"""CLI entry point for the claim verification pipeline."""

import argparse
import sys

from config.logging_config import setup_logging
from config.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real-Time News Claim Verification Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python cli.py "The EU AI Act bans social scoring systems."
  python cli.py "What is the current temperature in Mumbai?"
  python cli.py --verbose "Who won the 2024 US election?"
        """,
    )
    parser.add_argument(
        "claim",
        type=str,
        help="The claim to verify",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Show the agent reasoning trace",
    )

    args = parser.parse_args()

    log_level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(log_level)

    from main import verify_claim

    print(f"\n{'='*60}")
    print(f"  Claim: {args.claim}")
    print(f"{'='*60}\n")

    result = verify_claim(args.claim)

    print(result["formatted_response"])

    if args.trace and result.get("reasoning_trace"):
        print(f"\n{'─'*60}")
        print("Agent Reasoning Trace:")
        for i, step in enumerate(result["reasoning_trace"], 1):
            print(f"  {i}. {step}")
        print(f"{'─'*60}")

    print()


if __name__ == "__main__":
    main()
