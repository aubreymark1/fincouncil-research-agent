"""LLM-powered agent nodes.

These functions consume the public prompts under ``prompts/`` and use
``ModelProvider`` for structured JSON output. They are optional: the default
orchestrator remains rule-engine unless a caller injects a ``ModelProvider``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agents._helpers import scoped_verified_evidence
from app.model import ModelProvider
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


def _cache_key(prompt_name: str, context: dict[str, Any]) -> str:
    return f"{prompt_name}:{json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)}"


def _evidence_payload(evidence: list[Evidence]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in evidence]


def _run_claim_node(
    provider: ModelProvider,
    prompt_name: str,
    *,
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument] | None = None,
) -> list[Claim]:
    verified = scoped_verified_evidence(evidence, config)
    context: dict[str, Any] = {
        "evidence": _evidence_payload(verified),
        "config": config.model_dump(mode="json"),
    }
    if documents is not None:
        context["documents"] = [document.model_dump(mode="json") for document in documents]

    result = provider.generate_json(
        _build_prompt(prompt_name, context=context),
        response_model=ClaimList,
        cache_key=_cache_key(prompt_name, context),
    )
    if not isinstance(result, ClaimList):
        raise TypeError("E301 module=agents.llm: expected ClaimList response")
    return result.claims


def analyze_fundamentals_llm(
    provider: ModelProvider,
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument] | None = None,
) -> list[Claim]:
    """Run the fundamental node through the LLM provider."""

    return _run_claim_node(
        provider,
        "fundamental",
        evidence=evidence,
        config=config,
        documents=documents,
    )


def analyze_news_policy_llm(
    provider: ModelProvider,
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Run the news/policy node through the LLM provider."""

    return _run_claim_node(provider, "news_policy", evidence=evidence, config=config)


def analyze_risks_llm(
    provider: ModelProvider,
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Run the risk node through the LLM provider."""

    return _run_claim_node(provider, "risk", evidence=evidence, config=config)


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
        cache_key=_cache_key("critic_industry", context),
    )
    if not isinstance(result, ValidationIssueList):
        raise TypeError("E301 module=agents.llm: expected ValidationIssueList response")
    return result.issues
