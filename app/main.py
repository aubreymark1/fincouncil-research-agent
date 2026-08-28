"""Application-level research entry point."""

from __future__ import annotations

from app.model import ModelProvider
from app.orchestrator import run_pipeline
from app.schemas import ResearchReport, ResearchRequest


def run_research(
    request: ResearchRequest,
    *,
    model_provider: ModelProvider | None = None,
    mode: str = "rule-engine",
) -> ResearchReport:
    """Run the research pipeline and return a validated report.

    By default the deterministic rule-engine chain runs. Injecting a
    ``ModelProvider`` enables the LLM-powered agent nodes. ``mode`` selects the
    frozen E1/E2/E3 experiment behaviour or keeps the default rule-engine.
    """

    state = run_pipeline(request, model_provider=model_provider, mode=mode)
    if state.report is None:  # pragma: no cover - defensive invariant check
        raise RuntimeError("E500 module=main: orchestrator returned no report")
    return state.report
