"""Application-level research entry point."""

from __future__ import annotations

from app.orchestrator import run_pipeline
from app.schemas import ResearchReport, ResearchRequest


def run_research(request: ResearchRequest) -> ResearchReport:
    """Run the minimum research pipeline and return a validated report."""

    state = run_pipeline(request)
    if state.report is None:  # pragma: no cover - defensive invariant check
        raise RuntimeError("E500 module=main: orchestrator returned no report")
    return state.report
