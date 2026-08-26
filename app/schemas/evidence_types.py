"""Shared evidence type vocabulary for the public schemas.

CONTRACT-CHANGE-003 requires MetricRule, RiskRule and Evidence to use the
same evidence type vocabulary so validation cannot be bypassed by direct
construction.
"""

from __future__ import annotations

from typing import Literal

EVIDENCE_TYPE_VALUES = (
    "financial",
    "operating",
    "policy",
    "news",
    "company_release",
    "market_data",
    "other",
)

EvidenceType = Literal[
    "financial",
    "operating",
    "policy",
    "news",
    "company_release",
    "market_data",
    "other",
]

ALLOWED_EVIDENCE_TYPES = frozenset(EVIDENCE_TYPE_VALUES)
