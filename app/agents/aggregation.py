"""Aggregate the three analysis nodes into one entry point.

docs/CONTRACTS.md Section 十一 defines ``run_analysis`` as the single A-module
function that turns a verified evidence pool into Claims. It composes the
fundamental, news/policy, and risk nodes without adding any logic of its own.

When a ``ModelProvider`` is injected, the same entry point uses the LLM-powered
agent nodes; otherwise it keeps the deterministic rule-engine behaviour.
"""

from __future__ import annotations

from app.agents.fundamental import analyze_fundamentals
from app.agents.llm import (
    analyze_fundamentals_llm,
    analyze_news_policy_llm,
    analyze_risks_llm,
)
from app.agents.news_policy import analyze_news_policy
from app.agents.risk import analyze_risks
from app.model import ModelProvider
from app.schemas import Claim, Evidence, IndustryConfig, ResearchRequest, SourceDocument


def run_analysis(
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument],
    provider: ModelProvider | None = None,
) -> list[Claim]:
    """Run the fundamental, news/policy, and risk nodes over one evidence pool.

    The ``request`` parameter is accepted for contract alignment and future
    node expansion; current nodes derive their scope from ``config`` and the
    upstream-verified evidence pool. Cutoff enforcement remains an upstream
    responsibility: callers must pass time-lock-checked evidence.
    """

    del request
    if provider is not None:
        claims: list[Claim] = []
        claims.extend(analyze_fundamentals_llm(provider, evidence, config, documents=documents))
        claims.extend(analyze_news_policy_llm(provider, evidence, config))
        claims.extend(analyze_risks_llm(provider, evidence, config))
        return claims

    claims = []
    claims.extend(analyze_fundamentals(evidence, config, documents=documents))
    claims.extend(analyze_news_policy(evidence, config))
    claims.extend(analyze_risks(evidence, config))
    return claims
