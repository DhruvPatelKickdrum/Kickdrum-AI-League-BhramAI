#!/usr/bin/env python3
"""Quick end-to-end test of the claim verification pipeline."""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_config import setup_logging
from config.settings import settings


TEST_CLAIMS = [
    # Static (should use KB)
    "The EU AI Act bans social scoring systems.",
    # Dynamic - news
    "India recently hosted the G20 summit.",
    # Dynamic - weather
    "It is raining in Mumbai right now.",
    # Invalid / opinion
    "Python is the best programming language.",
]


def main() -> None:
    setup_logging("INFO")

    from main import verify_claim

    for claim in TEST_CLAIMS:
        print(f"\n{'='*60}")
        print(f"CLAIM: {claim}")
        print(f"{'='*60}")

        result = verify_claim(claim)

        print(f"\nVERDICT: {result['verdict']}")
        print(f"\n{result['formatted_response']}")

        if result.get("reasoning_trace"):
            print("\nAgent Trace:")
            for i, step in enumerate(result["reasoning_trace"], 1):
                print(f"  {i}. {step}")

        print(f"\n{'─'*60}")


if __name__ == "__main__":
    main()
