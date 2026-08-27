"""LLM-powered agent nodes.

These functions consume the public prompts under ``prompts/`` and use
``ModelProvider`` for structured JSON output. They are optional: the default
orchestrator remains rule-engine unless a caller injects a ``ModelProvider``.

The LLM path is intentionally defensive:
- each node filters evidence by the same evidence_type rules as the
  deterministic nodes;
- the request/company context is included so target-company applicability can
  be judged;
- node-specific Claim constraints are validated after model output;
- the provider's default cache key includes the full prompt text, so prompt
  edits invalidate cached responses.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agents._helpers import scoped_verified_evidence
from app.model import ModelProvider, ModelProviderError
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchRequest,
    SourceDocument,
    ValidationIssue,
)


PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"
_PROMPT_VERSION_RE = re.compile(r"^\s*version:\s*(\S+)", re.MULTILINE)
_NEWS_POLICY_TYPES = frozenset({"news", "policy", "company_release"})
_ANALYSIS_STATUSES = frozenset({"pass", "review"})


class ClaimList(BaseModel):
    """Structured LLM output for analysis nodes."""

    claims: list[Claim]


class ValidationIssueList(BaseModel):
    """Structured LLM output for the industry Critic node."""

    issues: list[ValidationIssue]


def load_prompt(name: str) -> str:
    """Read one Markdown prompt file."""

    return (PROMPTS_ROOT / f"{name}.md").read_text(encoding="utf-8")


def get_prompt_versions() -> dict[str, str]:
    """Return prompt versions parsed from the Markdown headers."""

    versions: dict[str, str] = {}
    for name in ("fundamental", "news_policy", "risk", "critic_industry"):
        text = load_prompt(name)
        match = _PROMPT_VERSION_RE.search(text)
        versions[name] = match.group(1) if match else "unknown"
    return versions


def _build_prompt(prompt_name: str, *, context: dict[str, Any]) -> str:
    """Append JSON context to the Markdown prompt."""

    prompt = load_prompt(prompt_name)
    serialized = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    return f"{prompt}\n\n## 输入数据\n```json\n{serialized}\n```\n"


def _evidence_payload(evidence: list[Evidence]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in evidence]


def _filter_evidence_types(
    evidence: list[Evidence],
    config: IndustryConfig,
    allowed_types: set[str] | frozenset[str],
) -> list[Evidence]:
    """Keep verified, industry-scoped evidence of allowed types only."""

    return [
        item
        for item in scoped_verified_evidence(evidence, config)
        if item.evidence_type in allowed_types
    ]


def _validate_claim_node_output(prompt_name: str, claims: list[Claim]) -> None:
    """Enforce node-specific Claim constraints after model output."""

    for claim in claims:
        if claim.status not in _ANALYSIS_STATUSES:
            raise ModelProviderError(
                f"E301 module=agents.llm: {prompt_name} node returned "
                f"status={claim.status!r}; expected pass or review"
            )

        if prompt_name == "fundamental":
            if claim.claim_type not in {"fact", "change", "analysis", "unresolved"}:
                raise ModelProviderError(
                    f"E301 module=agents.llm: fundamental node returned "
                    f"claim_type={claim.claim_type!r}; risk is not allowed"
                )
            if claim.risk_severity is not None:
                raise ModelProviderError(
                    "E301 module=agents.llm: fundamental node returned "
                    "risk_severity on a non-risk claim"
                )

        if prompt_name == "news_policy":
            if claim.claim_type not in {"change", "unresolved"}:
                raise ModelProviderError(
                    f"E301 module=agents.llm: news_policy node returned "
                    f"claim_type={claim.claim_type!r}; expected change/unresolved"
                )
            if claim.risk_severity is not None:
                raise ModelProviderError(
                    "E301 module=agents.llm: news_policy node returned "
                    "risk_severity on a non-risk claim"
                )

        if prompt_name == "risk":
            if claim.claim_type not in {"risk", "unresolved"}:
                raise ModelProviderError(
                    f"E301 module=agents.llm: risk node returned "
                    f"claim_type={claim.claim_type!r}; expected risk/unresolved"
                )
            if claim.status != "review":
                raise ModelProviderError(
                    f"E301 module=agents.llm: risk node returned "
                    f"status={claim.status!r}; risk conclusions require review"
                )
            if claim.claim_type == "risk" and claim.risk_severity is None:
                raise ModelProviderError(
                    "E301 module=agents.llm: risk node returned a risk claim "
                    "without risk_severity"
                )


def _run_claim_node(
    provider: ModelProvider,
    prompt_name: str,
    *,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    allowed_types: set[str] | frozenset[str],
    documents: list[SourceDocument] | None = None,
) -> list[Claim]:
    filtered = _filter_evidence_types(evidence, config, allowed_types)
    context: dict[str, Any] = {
        "request": request.model_dump(mode="json"),
        "evidence": _evidence_payload(filtered),
        "config": config.model_dump(mode="json"),
    }
    if documents is not None:
        context["documents"] = [document.model_dump(mode="json") for document in documents]

    result = provider.generate_json(
        _build_prompt(prompt_name, context=context),
        response_model=ClaimList,
    )
    if not isinstance(result, ClaimList):
        raise TypeError("E301 module=agents.llm: expected ClaimList response")
    _validate_claim_node_output(prompt_name, result.claims)
    return result.claims


def analyze_fundamentals_llm(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument] | None = None,
) -> list[Claim]:
    """Run the fundamental node through the LLM provider."""

    allowed_types = {
        evidence_type
        for metric in config.required_metrics
        for evidence_type in metric.evidence_types
    }
    return _run_claim_node(
        provider,
        "fundamental",
        request=request,
        evidence=evidence,
        config=config,
        allowed_types=allowed_types,
        documents=documents,
    )


def analyze_news_policy_llm(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Run the news/policy node through the LLM provider."""

    return _run_claim_node(
        provider,
        "news_policy",
        request=request,
        evidence=evidence,
        config=config,
        allowed_types=_NEWS_POLICY_TYPES,
    )


def analyze_risks_llm(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Run the risk node through the LLM provider."""

    allowed_types = {
        evidence_type
        for rule in config.risk_rules
        for evidence_type in rule.required_evidence_types
    }
    return _run_claim_node(
        provider,
        "risk",
        request=request,
        evidence=evidence,
        config=config,
        allowed_types=allowed_types,
    )


def run_critic_llm(
    provider: ModelProvider,
    request: ResearchRequest,
    claims: list[Claim],
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[ValidationIssue]:
    """Run the industry Critic node through the LLM provider.

    Unlike analysis nodes, the Critic receives all evidence (including pending
    and rejected items) so it can report evidence-status problems.
    """

    context = {
        "request": request.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "evidence": _evidence_payload(evidence),
        "config": config.model_dump(mode="json"),
    }
    result = provider.generate_json(
        _build_prompt("critic_industry", context=context),
        response_model=ValidationIssueList,
    )
    if not isinstance(result, ValidationIssueList):
        raise TypeError("E301 module=agents.llm: expected ValidationIssueList response")
    return result.issues
