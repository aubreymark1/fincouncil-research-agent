"""Evidence-bound industry risk analysis node.

This is the A-side adapter. The shared rule engine lives in
``app.industry.risk_rules`` so A and C consume the same trigger terms,
exclusion terms, and metric coverage matrix.
"""

from __future__ import annotations

from app.industry import apply_risk_rules
from app.schemas import Claim, Evidence, IndustryConfig


def analyze_risks(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Create reviewable risk or unresolved Claims using the shared C engine."""

    return apply_risk_rules(evidence, config)
