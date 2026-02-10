"""Input validation utilities."""


def validate_claim(claim: str) -> str:
    """Validate and clean a claim string. Raise ValueError if invalid."""
    if not claim or not isinstance(claim, str):
        raise ValueError("Claim must be a non-empty string.")

    claim = claim.strip()

    if len(claim) < 5:
        raise ValueError("Claim is too short to verify (minimum 5 characters).")

    if len(claim) > 2000:
        raise ValueError("Claim is too long (maximum 2000 characters).")

    return claim
