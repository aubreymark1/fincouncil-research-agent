"""Application-level research entry point."""

from __future__ import annotations

from collections.abc import Callable

from app.model import ModelProvider
from app.orchestrator import run_pipeline
from app.schemas import ResearchReport, ResearchRequest

ProgressCallback = Callable[[str], None]


def run_research(
    request: ResearchRequest,
    *,
    model_provider: ModelProvider | None = None,
    mode: str = "rule-engine",
    progress_callback: ProgressCallback | None = None,
) -> ResearchReport:
    """Run the research pipeline and return a validated report.

    By default the deterministic rule-engine chain runs. Injecting a
    ``ModelProvider`` enables the LLM-powered agent nodes. ``mode`` selects the
    frozen E1/E2/E3 experiment behaviour or keeps the default rule-engine.
    ``progress_callback`` is optional and receives human-readable stage labels
    at real pipeline boundaries; it never changes pipeline behaviour.
    """

    state = run_pipeline(
        request,
        model_provider=model_provider,
        mode=mode,
        progress_callback=progress_callback,
    )
    if state.report is None:  # pragma: no cover - defensive invariant check
        raise RuntimeError("E500 module=main: orchestrator returned no report")
    return state.report
