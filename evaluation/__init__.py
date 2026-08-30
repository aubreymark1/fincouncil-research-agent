"""Deterministic evaluation utilities for research reports."""

from .metrics import evaluate_report
from .narrative_metrics import evaluate_narrative

__all__ = ["evaluate_narrative", "evaluate_report"]
