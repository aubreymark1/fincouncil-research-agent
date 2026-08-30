"""Compact single-call LLM analysis for the anonymous workbench."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.agents.llm import _build_prompt, _evidence_text
from app.model import ModelProvider, ModelProviderError
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ReportBlock,
    ResearchRequest,
    SourceDocument,
)


DEFAULT_MAX_TOTAL_EVIDENCE = 24
DEFAULT_PER_METRIC = 2
DEFAULT_PER_RISK = 2
DEFAULT_NEWS_LIMIT = 4
DEFAULT_MINIMAL_MAX_EVIDENCE = 24
_PROMPT_VERSION_RE = re.compile(r"^\s*version:\s*(\S+)", re.MULTILINE)


class CompactReportDraft(BaseModel):
    """One-call LLM output: readable paragraphs, with claims kept optional."""

    narrative: list[ReportBlock] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


def _terms_score(item: Evidence, terms: list[str]) -> int:
    text = _evidence_text(item)
    return sum(1 for term in terms if term and term.casefold() in text)


def _ranked(items: list[Evidence], terms: list[str]) -> list[Evidence]:
    return sorted(
        items,
        key=lambda item: (
            -_terms_score(item, terms),
            -item.confidence,
            -item.published_at.toordinal(),
            item.evidence_id,
        ),
    )


def select_compact_evidence(
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    max_total: int = DEFAULT_MAX_TOTAL_EVIDENCE,
    per_metric: int = DEFAULT_PER_METRIC,
    per_risk: int = DEFAULT_PER_RISK,
    news_limit: int = DEFAULT_NEWS_LIMIT,
) -> list[Evidence]:
    """Select a small, deterministic, verified evidence set for one LLM call."""

    if min(max_total, per_metric, per_risk, news_limit) < 1:
        raise ValueError("compact evidence limits must be positive")

    scoped = [
        item
        for item in evidence
        if item.review_status == "verified" and item.industry_id == config.industry_id
    ]
    selected: list[Evidence] = []
    selected_ids: set[str] = set()

    def add_ranked(items: list[Evidence], limit: int, terms: list[str]) -> None:
        added = 0
        for item in _ranked(items, terms):
            if len(selected) >= max_total or added >= limit:
                break
            if item.evidence_id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(item.evidence_id)
            added += 1

    for metric in config.required_metrics:
        candidates = [
            item
            for item in scoped
            if item.evidence_type in metric.evidence_types
            and _terms_score(item, metric.keywords) > 0
        ]
        add_ranked(candidates, per_metric, metric.keywords)

    for rule in config.risk_rules:
        candidates = [
            item
            for item in scoped
            if item.evidence_type in rule.required_evidence_types
            and _terms_score(item, [*rule.trigger_terms, *rule.exclude_terms]) > 0
        ]
        trigger_items = [
            item for item in candidates if _terms_score(item, rule.trigger_terms) > 0
        ]
        exclude_items = [
            item for item in candidates if _terms_score(item, rule.exclude_terms) > 0
        ]
        if trigger_items and exclude_items and per_risk >= 2:
            add_ranked(trigger_items, per_risk - 1, rule.trigger_terms)
            add_ranked(exclude_items, 1, rule.exclude_terms)
        else:
            add_ranked(candidates, per_risk, [*rule.trigger_terms, *rule.exclude_terms])

    news_items = [
        item
        for item in scoped
        if item.evidence_type in {"news", "policy", "company_release"}
        and _terms_score(item, config.retrieval_keywords) > 0
    ]
    add_ranked(news_items, news_limit, config.retrieval_keywords)

    remaining = [item for item in scoped if item.evidence_id not in selected_ids]
    add_ranked(remaining, max_total - len(selected), config.retrieval_keywords)
    return selected


def select_minimal_evidence(
    evidence: list[Evidence],
    *,
    max_total: int = DEFAULT_MINIMAL_MAX_EVIDENCE,
) -> list[Evidence]:
    """Bound an experiment prompt without applying industry verification.

    E1/E2 intentionally receive raw pending evidence, including material that
    the full system would later remove through time-lock or industry policy.
    This selector only keeps the prompt small and deterministic.
    """

    if max_total < 1:
        raise ValueError("minimal evidence limit must be positive")
    return sorted(
        evidence,
        key=lambda item: (
            -item.confidence,
            -item.published_at.toordinal(),
            item.evidence_id,
        ),
    )[:max_total]


def compact_evidence_payload(evidence: list[Evidence]) -> list[dict[str, Any]]:
    """Return only the short provenance fields needed by the synthesis prompt."""

    return [
        {
            "evidence_id": item.evidence_id,
            "fact_text": item.fact_text,
            "quote": item.quote,
            "published_at": item.published_at.isoformat(),
            "page": item.page,
            "section": item.section,
            "locator": item.locator,
            "company_name": item.company_name,
            "industry_id": item.industry_id,
            "evidence_type": item.evidence_type,
            "confidence": item.confidence,
        }
        for item in evidence
    ]


def _compact_config_payload(config: IndustryConfig) -> dict[str, Any]:
    return {
        "industry_id": config.industry_id,
        "display_name": config.display_name,
        "report_sections": config.report_sections,
        "event_taxonomy": config.event_taxonomy,
        "required_metrics": [
            {
                "metric_id": metric.metric_id,
                "display_name": metric.display_name,
                "keywords": metric.keywords,
                "evidence_types": metric.evidence_types,
                "required": metric.required,
            }
            for metric in config.required_metrics
        ],
        "risk_rules": [
            {
                "risk_id": rule.risk_id,
                "display_name": rule.display_name,
                "trigger_description": rule.trigger_description,
                "trigger_terms": rule.trigger_terms,
                "exclude_terms": rule.exclude_terms,
                "metric_ids": rule.metric_ids,
                "required_evidence_types": rule.required_evidence_types,
                "severity": rule.severity,
            }
            for rule in config.risk_rules
        ],
    }


def _document_payload(documents: list[SourceDocument]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": document.doc_id,
            "title": document.title,
            "publisher": document.publisher,
            "published_at": document.published_at.isoformat()
            if isinstance(document.published_at, date)
            else None,
        }
        for document in documents
    ]


def _matching_rule(claim: Claim, config: IndustryConfig) -> Any | None:
    for rule in config.risk_rules:
        if (
            set(claim.industry_metric_ids) == set(rule.metric_ids)
            and claim.risk_severity == rule.severity
        ):
            return rule
    return None


def _validate_compact_claims(
    claims: list[Claim],
    evidence: list[Evidence],
    config: IndustryConfig,
) -> None:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    known_metrics = {metric.metric_id for metric in config.required_metrics}

    for claim in claims:
        if claim.status not in {"pass", "review"}:
            raise ModelProviderError(
                f"E301 module=agents.compact: claim {claim.claim_id} has "
                f"status={claim.status!r}; expected pass or review"
            )
        unknown_evidence = [
            evidence_id
            for evidence_id in claim.evidence_ids
            if evidence_id not in evidence_by_id
        ]
        if unknown_evidence:
            raise ModelProviderError(
                f"E301 module=agents.compact: claim {claim.claim_id} "
                f"referenced unknown evidence IDs: {unknown_evidence}"
            )
        unknown_metrics = sorted(set(claim.industry_metric_ids) - known_metrics)
        if unknown_metrics:
            raise ModelProviderError(
                f"E301 module=agents.compact: claim {claim.claim_id} "
                f"referenced unknown industry_metric_ids={unknown_metrics}"
            )

        if claim.claim_type in {"fact", "change", "analysis"} and claim.risk_severity is not None:
            raise ModelProviderError(
                f"E301 module=agents.compact: claim {claim.claim_id} "
                "set risk_severity on a non-risk claim"
            )

        if claim.claim_type != "risk":
            continue
        if claim.status != "review":
            raise ModelProviderError(
                f"E301 module=agents.compact: risk claim {claim.claim_id} "
                "must have status=review"
            )
        rule = _matching_rule(claim, config)
        if rule is None:
            raise ModelProviderError(
                f"E301 module=agents.compact: risk claim {claim.claim_id} "
                "does not match an IndustryConfig RiskRule"
            )
        cited_text = "\n".join(
            _evidence_text(evidence_by_id[evidence_id])
            for evidence_id in claim.evidence_ids
        )
        if any(
            evidence_by_id[evidence_id].evidence_type not in rule.required_evidence_types
            for evidence_id in claim.evidence_ids
        ):
            raise ModelProviderError(
                f"E301 module=agents.compact: risk claim {claim.claim_id} "
                "uses an evidence type outside its RiskRule"
            )
        trigger_hit = any(term.casefold() in cited_text for term in rule.trigger_terms)
        exclude_hit = any(term.casefold() in cited_text for term in rule.exclude_terms)
        if not trigger_hit or exclude_hit:
            raise ModelProviderError(
                f"E301 module=agents.compact: risk claim {claim.claim_id} "
                "does not satisfy trigger/exclude semantics"
            )


def _validate_narrative(
    narrative: list[ReportBlock],
    evidence: list[Evidence],
) -> list[ReportBlock]:
    """Keep valid citations without discarding an otherwise useful paragraph."""

    known_evidence_ids = {item.evidence_id for item in evidence}
    sanitized: list[ReportBlock] = []
    for block in narrative:
        valid_ids = [
            evidence_id
            for evidence_id in block.evidence_ids
            if evidence_id in known_evidence_ids
        ]
        if block.evidence_ids and not valid_ids:
            continue
        sanitized.append(block.model_copy(update={"evidence_ids": valid_ids}))
    if narrative and not sanitized:
        raise ModelProviderError(
            "E301 module=agents.compact: narrative did not reference any "
            "evidence sent to the model"
        )
    return sanitized


def _join_claim_texts(claims: list[Claim]) -> str:
    texts: list[str] = []
    for claim in claims:
        text = claim.text.strip()
        if text and text[-1] not in "。！？；":
            text += "。"
        if text:
            texts.append(text)
    return "".join(texts)


def _claim_evidence_ids(claims: list[Claim]) -> list[str]:
    return list(
        dict.fromkeys(
            evidence_id
            for claim in claims
            for evidence_id in claim.evidence_ids
        )
    )


def _build_narrative_from_claims(claims: list[Claim]) -> list[ReportBlock]:
    """Turn LLM-written claim sentences into readable report paragraphs."""

    body_claims = [
        claim
        for claim in claims
        if claim.claim_type in {"fact", "change", "analysis"}
        and claim.status == "pass"
    ]
    risk_claims = [
        claim
        for claim in claims
        if claim.claim_type in {"risk", "unresolved"}
        and claim.status == "pass"
    ]
    blocks: list[ReportBlock] = []

    core_claims = [claim for claim in body_claims if claim.claim_type == "analysis"]
    core_claims = core_claims or body_claims[:3]
    if core_claims:
        blocks.append(
            ReportBlock(
                section="核心判断",
                text=_join_claim_texts(core_claims),
                evidence_ids=_claim_evidence_ids(core_claims),
            )
        )
    if body_claims:
        blocks.append(
            ReportBlock(
                section="基本面分析",
                text=_join_claim_texts(body_claims),
                evidence_ids=_claim_evidence_ids(body_claims),
            )
        )
    if risk_claims:
        blocks.append(
            ReportBlock(
                section="风险与局限",
                text=_join_claim_texts(risk_claims),
                evidence_ids=_claim_evidence_ids(risk_claims),
            )
        )
    return blocks


def get_compact_prompt_version() -> str:
    from app.agents.llm import load_prompt

    prompt = load_prompt("synthesis")
    match = _PROMPT_VERSION_RE.search(prompt)
    return match.group(1) if match else "unknown"


def get_minimal_prompt_version() -> str:
    from app.agents.llm import load_prompt

    prompt = load_prompt("minimal_synthesis")
    match = _PROMPT_VERSION_RE.search(prompt)
    return match.group(1) if match else "unknown"


def run_compact_analysis(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument],
) -> list[Claim]:
    """Generate all workbench claims with one bounded LLM request."""

    return run_compact_report(
        provider,
        request,
        evidence,
        config,
        documents=documents,
    ).claims


def run_compact_report(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument],
) -> CompactReportDraft:
    """Generate readable report paragraphs and structured claims in one call."""

    selected = select_compact_evidence(evidence, config)
    context = {
        "request": request.model_dump(mode="json"),
        "evidence": compact_evidence_payload(selected),
        "config": _compact_config_payload(config),
        "documents": _document_payload(documents),
    }
    prompt = _build_prompt("synthesis", context=context)
    result = provider.generate_json(prompt, response_model=CompactReportDraft)
    if not isinstance(result, CompactReportDraft):
        raise TypeError("E301 module=agents.compact: expected CompactReportDraft response")
    result = result.model_copy(
        update={"narrative": _validate_narrative(result.narrative, selected)}
    )
    _validate_compact_claims(result.claims, selected, config)
    if not result.narrative:
        result = result.model_copy(
            update={"narrative": _build_narrative_from_claims(result.claims)}
        )
    return result


def run_minimal_narrative(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    *,
    config: IndustryConfig | None,
    documents: list[SourceDocument],
) -> list[ReportBlock]:
    """Generate a small, comparable narrative for E1/E2/E3 experiments."""

    selected = select_minimal_evidence(evidence)
    context = {
        "request": request.model_dump(mode="json"),
        "evidence": compact_evidence_payload(selected),
        "config": _compact_config_payload(config) if config is not None else None,
        "documents": _document_payload(documents),
    }
    prompt = _build_prompt("minimal_synthesis", context=context)
    result = provider.generate_json(prompt, response_model=CompactReportDraft)
    if not isinstance(result, CompactReportDraft):
        raise TypeError("E301 module=agents.compact: expected CompactReportDraft response")

    narrative = _validate_narrative(result.narrative, selected)
    if not narrative:
        raise ModelProviderError(
            "E301 module=agents.compact: minimal LLM output contained no narrative"
        )
    return narrative
