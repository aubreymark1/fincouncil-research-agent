"""LLM-powered agent nodes.

These functions consume the public prompts under ``prompts/`` and use
``ModelProvider`` for structured JSON output. They are optional: the default
orchestrator remains rule-engine unless a caller injects a ``ModelProvider``.

The LLM path is intentionally defensive:
- each node filters evidence by evidence_type and node-specific relevance;
- evidence is split into budget-sized batches so real RUN-DEMO pools are fully
  covered instead of failing or silently truncating;
- the request/company context is included so target-company applicability can
  be judged;
- node-specific Claim constraints, config-aware metric/risk semantics,
  trigger/exclude signals (including full-pool exclude evidence), and
  evidence-ID isolation are validated after model output;
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
    NarrativeBlock,
    NarrativeDraft,
    ResearchRequest,
    SourceDocument,
    ValidationIssue,
)


PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"
_PROMPT_VERSION_RE = re.compile(r"^\s*version:\s*(\S+)", re.MULTILINE)
_NEWS_POLICY_TYPES = frozenset({"news", "policy", "company_release"})
_ANALYSIS_STATUSES = frozenset({"pass", "review"})
MAX_PROMPT_EVIDENCE_CHARS = 120_000


class ClaimList(BaseModel):
    """Structured LLM output for analysis nodes."""

    claims: list[Claim]


class ValidationIssueList(BaseModel):
    """Structured LLM output for the industry Critic node."""

    issues: list[ValidationIssue]


def _validate_narrative_evidence(
    blocks: list[NarrativeBlock],
    evidence: list[Evidence],
) -> list[NarrativeBlock]:
    """Ensure every reportable sentence points at verified input Evidence."""

    allowed = {
        item.evidence_id
        for item in evidence
        if item.review_status == "verified"
    }
    for block in blocks:
        for segment in block.segments:
            unknown = set(segment.evidence_ids) - allowed
            if unknown:
                raise ModelProviderError(
                    "E301 module=agents.llm: unknown evidence IDs in narrative "
                    f"({', '.join(sorted(unknown))})"
                )
    return blocks


def synthesize_narrative(
    provider: ModelProvider,
    request: ResearchRequest,
    claims: list[Claim],
    evidence: list[Evidence],
) -> list[NarrativeBlock]:
    """Ask the LLM to organize claims into sentence-level cited prose."""

    context = {
        "request": request.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "evidence": _evidence_payload(evidence),
    }
    result = provider.generate_json(
        _build_prompt("synthesis", context=context),
        response_model=NarrativeDraft,
        cache_key=f"narrative:{request.run_id}",
    )
    if not isinstance(result, NarrativeDraft):
        raise TypeError("E301 module=agents.llm: expected NarrativeDraft response")
    return _validate_narrative_evidence(result.blocks, evidence)


def load_prompt(name: str) -> str:
    """Read one Markdown prompt file."""

    return (PROMPTS_ROOT / f"{name}.md").read_text(encoding="utf-8")


def get_prompt_versions() -> dict[str, str]:
    """Return prompt versions parsed from the Markdown headers."""

    versions: dict[str, str] = {}
    for name in ("fundamental", "news_policy", "risk", "critic_industry", "synthesis"):
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


def _evidence_text(item: Evidence) -> str:
    return f"{item.fact_text}\n{item.quote}".casefold()


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


def _relevance_filter(
    prompt_name: str,
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Evidence]:
    """Drop evidence unlikely to matter for one node before batching."""

    if prompt_name == "fundamental":
        keywords = [
            keyword.casefold()
            for metric in config.required_metrics
            for keyword in metric.keywords
        ]
        return [
            item
            for item in evidence
            if any(keyword in _evidence_text(item) for keyword in keywords)
        ]

    if prompt_name == "risk":
        terms: list[str] = []
        for rule in config.risk_rules:
            terms.extend(rule.trigger_terms)
            terms.extend(rule.exclude_terms)
            for metric in config.required_metrics:
                if metric.metric_id in rule.metric_ids:
                    terms.extend(metric.keywords)
        normalized_terms = {term.casefold() for term in terms if term}
        return [
            item
            for item in evidence
            if any(term in _evidence_text(item) for term in normalized_terms)
        ]

    return evidence


def _budget_evidence(
    evidence: list[Evidence],
    max_chars: int | None = None,
) -> tuple[list[Evidence], list[str]]:
    """Return evidence that fits the budget and IDs omitted by the budget."""

    limit = MAX_PROMPT_EVIDENCE_CHARS if max_chars is None else max_chars
    selected: list[Evidence] = []
    total_chars = 0
    for item in evidence:
        serialized = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)
        item_chars = len(serialized)
        if total_chars + item_chars > limit:
            if not selected:
                raise ModelProviderError(
                    "E301 module=agents.llm: a single evidence item exceeds the "
                    "LLM prompt evidence budget"
                )
            break
        selected.append(item)
        total_chars += item_chars
    omitted_ids = [item.evidence_id for item in evidence[len(selected):]]
    return selected, omitted_ids


def _split_evidence_batches(
    evidence: list[Evidence],
    max_chars: int | None = None,
) -> list[list[Evidence]]:
    """Split evidence into prompt-sized batches without dropping any ID."""

    limit = MAX_PROMPT_EVIDENCE_CHARS if max_chars is None else max_chars
    batches: list[list[Evidence]] = []
    current: list[Evidence] = []
    total_chars = 0
    for item in evidence:
        serialized = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)
        item_chars = len(serialized)
        if item_chars > limit:
            raise ModelProviderError(
                "E301 module=agents.llm: a single evidence item exceeds the "
                "LLM prompt evidence budget"
            )
        if current and total_chars + item_chars > limit:
            batches.append(current)
            current = []
            total_chars = 0
        current.append(item)
        total_chars += item_chars
    if current or not batches:
        batches.append(current)
    return batches


def _evidence_matches_rule_terms(item: Evidence, rule: Any) -> bool:
    """Return True when evidence is relevant to one RiskRule."""

    text = _evidence_text(item)
    terms: list[str] = []
    terms.extend(rule.trigger_terms)
    terms.extend(rule.exclude_terms)
    return any(term.casefold() in text for term in terms if term)


def _known_metric_ids(config: IndustryConfig) -> set[str]:
    return {metric.metric_id for metric in config.required_metrics}


def _matching_risk_rule(
    claim: Claim,
    config: IndustryConfig,
) -> Any | None:
    """Return the single RiskRule a risk Claim claims to represent."""

    for rule in config.risk_rules:
        if (
            set(claim.industry_metric_ids) == set(rule.metric_ids)
            and claim.risk_severity == rule.severity
        ):
            return rule
    return None


def _validate_claim_node_output(
    prompt_name: str,
    claims: list[Claim],
    config: IndustryConfig,
    evidence_by_id: dict[str, Evidence],
    full_evidence_by_id: dict[str, Evidence] | None = None,
) -> None:
    """Enforce node-specific and config-aware Claim constraints."""

    known_metric_ids = _known_metric_ids(config)
    for claim in claims:
        if claim.status not in _ANALYSIS_STATUSES:
            raise ModelProviderError(
                f"E301 module=agents.llm: {prompt_name} node returned "
                f"status={claim.status!r}; expected pass or review"
            )

        unknown_metrics = sorted(set(claim.industry_metric_ids) - known_metric_ids)
        if unknown_metrics:
            raise ModelProviderError(
                f"E301 module=agents.llm: {prompt_name} node returned unknown "
                f"industry_metric_ids={unknown_metrics}"
            )

        missing_evidence = [
            evidence_id
            for evidence_id in claim.evidence_ids
            if evidence_id not in evidence_by_id
        ]
        if missing_evidence:
            raise ModelProviderError(
                f"E301 module=agents.llm: {prompt_name} node referenced evidence "
                f"IDs that were not sent to this node: {missing_evidence}"
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
            if claim.claim_type == "risk":
                rule = _matching_risk_rule(claim, config)
                if rule is None:
                    raise ModelProviderError(
                        "E301 module=agents.llm: risk node returned a risk claim "
                        "that does not match any RiskRule metric_ids/severity"
                    )
                for evidence_type in rule.required_evidence_types:
                    if not any(
                        evidence_by_id.get(evidence_id) is not None
                        and evidence_by_id[evidence_id].evidence_type == evidence_type
                        for evidence_id in claim.evidence_ids
                    ):
                        raise ModelProviderError(
                            f"E301 module=agents.llm: risk claim for "
                            f"{rule.risk_id} is missing required evidence type "
                            f"{evidence_type}"
                        )

                referenced_text = "\n".join(
                    _evidence_text(evidence_by_id[evidence_id])
                    for evidence_id in claim.evidence_ids
                    if evidence_id in evidence_by_id
                )
                trigger_hit = any(
                    term.casefold() in referenced_text for term in rule.trigger_terms
                )
                exclude_hit = any(
                    term.casefold() in referenced_text for term in rule.exclude_terms
                )
                if not trigger_hit or exclude_hit:
                    raise ModelProviderError(
                        f"E301 module=agents.llm: risk claim for {rule.risk_id} "
                        "does not satisfy trigger/exclude semantics"
                    )

                if full_evidence_by_id is not None:
                    full_rule_evidence = [
                        item
                        for item in full_evidence_by_id.values()
                        if _evidence_matches_rule_terms(item, rule)
                    ]
                    full_text = "\n".join(_evidence_text(item) for item in full_rule_evidence)
                    full_exclude_hit = any(
                        term.casefold() in full_text for term in rule.exclude_terms
                    )
                    full_trigger_hit = any(
                        term.casefold() in full_text for term in rule.trigger_terms
                    )
                    if full_exclude_hit or not full_trigger_hit:
                        raise ModelProviderError(
                            f"E301 module=agents.llm: risk claim for {rule.risk_id} "
                            "is inconsistent with the full rule-relevant evidence "
                            "pool (exclude signal present or no trigger signal)"
                        )


def _validate_batch_evidence_isolation(
    prompt_name: str,
    claims: list[Claim],
    batch_evidence_by_id: dict[str, Evidence],
) -> None:
    """Ensure a model never references evidence outside its current batch."""

    for claim in claims:
        missing = [
            evidence_id
            for evidence_id in claim.evidence_ids
            if evidence_id not in batch_evidence_by_id
        ]
        if missing:
            raise ModelProviderError(
                f"E301 module=agents.llm: {prompt_name} node referenced evidence "
                f"IDs that were not in the current batch: {missing}"
            )


def _merge_claims(claims: list[Claim]) -> list[Claim]:
    """Merge duplicate claim_ids using conservative reporting semantics.

    - evidence_ids and industry_metric_ids are unioned;
    - review status wins over pass;
    - text conflicts force review;
    - confidence takes the minimum (most conservative).
    """

    merged: dict[str, Claim] = {}
    for claim in claims:
        existing = merged.get(claim.claim_id)
        if existing is None:
            merged[claim.claim_id] = claim
            continue
        combined_evidence = list(
            dict.fromkeys([*existing.evidence_ids, *claim.evidence_ids])
        )
        combined_metrics = list(
            dict.fromkeys([*existing.industry_metric_ids, *claim.industry_metric_ids])
        )
        text_conflict = existing.text != claim.text
        semantic_conflict = (
            existing.claim_type != claim.claim_type
            or existing.risk_severity != claim.risk_severity
            or existing.calculation != claim.calculation
        )
        merged_status = (
            "review"
            if (
                text_conflict
                or semantic_conflict
                or existing.status == "review"
                or claim.status == "review"
            )
            else existing.status
        )
        merged[claim.claim_id] = existing.model_copy(
            update={
                "evidence_ids": combined_evidence,
                "industry_metric_ids": combined_metrics,
                "status": merged_status,
                "confidence": min(existing.confidence, claim.confidence),
            }
        )
    return list(merged.values())


def _run_claim_node_single(
    provider: ModelProvider,
    prompt_name: str,
    *,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    full_evidence_by_id: dict[str, Evidence] | None,
    batch_index: int,
    total_batches: int,
    documents: list[SourceDocument] | None = None,
) -> list[Claim]:
    context: dict[str, Any] = {
        "request": request.model_dump(mode="json"),
        "evidence": _evidence_payload(evidence),
        "evidence_truncated": False,
        "omitted_evidence_ids": [],
        "batch_index": batch_index,
        "total_batches": total_batches,
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
    batch_evidence_by_id = {item.evidence_id: item for item in evidence}
    _validate_batch_evidence_isolation(
        prompt_name,
        result.claims,
        batch_evidence_by_id,
    )
    return result.claims


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
    filtered = _relevance_filter(prompt_name, filtered, config)
    full_evidence_by_id = {item.evidence_id: item for item in filtered}
    batches = _split_evidence_batches(filtered)

    raw_claims: list[Claim] = []
    for batch_index, batch in enumerate(batches, start=1):
        raw_claims.extend(
            _run_claim_node_single(
                provider,
                prompt_name,
                request=request,
                evidence=batch,
                config=config,
                full_evidence_by_id=full_evidence_by_id,
                batch_index=batch_index,
                total_batches=len(batches),
                documents=documents,
            )
        )

    claims = _merge_claims(raw_claims)
    _validate_claim_node_output(
        prompt_name,
        claims,
        config,
        full_evidence_by_id,
        full_evidence_by_id,
    )
    return claims


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

    The LLM Critic is supplementary: it may receive a budgeted evidence subset
    with omitted IDs recorded in the prompt. The deterministic Critic always
    runs on the full evidence pool, so hard validation is not weakened.
    """

    selected, omitted_ids = _budget_evidence(evidence)
    context = {
        "request": request.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "evidence": _evidence_payload(selected),
        "evidence_truncated": bool(omitted_ids),
        "omitted_evidence_ids": omitted_ids,
        "config": config.model_dump(mode="json"),
    }
    result = provider.generate_json(
        _build_prompt("critic_industry", context=context),
        response_model=ValidationIssueList,
    )
    if not isinstance(result, ValidationIssueList):
        raise TypeError("E301 module=agents.llm: expected ValidationIssueList response")
    return result.issues
