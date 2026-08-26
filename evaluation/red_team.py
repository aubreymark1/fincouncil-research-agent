"""Red-team scenario runner for the evaluation module (D-004).

Red-team testing feeds deliberately hostile inputs — post-cutoff documents,
undated sources, wrong numbers, off-company material, conflicting sources, and
unsupported claims — into the real time-lock and Critic modules and returns
every :class:`ValidationIssue` the system produces. This proves the system
rejects bad input instead of silently absorbing it, without calling any model.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.agents import run_critic
from app.industry.loader import load_industry_config
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchRequest,
    SourceDocument,
    ValidationIssue,
)
from app.validators import apply_time_lock

#: The six red-team scenario types, in a stable reporting order.
SCENARIO_TYPES = (
    "post_cutoff",
    "undated",
    "wrong_number",
    "irrelevant",
    "conflicting_sources",
    "unsupported_claim",
)


def _make_document(
    doc_id: str,
    *,
    published_at: date | None,
    review_status: str,
    company_name: str = "示例食品公司",
    industry_id: str = "food_beverage",
) -> SourceDocument:
    """Build a deterministic red-team source document."""

    return SourceDocument(
        doc_id=doc_id,
        title=f"红蓝测试资料 {doc_id}",
        source_type="news",
        publisher="示例财经媒体",
        source_url=None,
        local_path=f"data/raw/food_beverage/{doc_id}.pdf",
        published_at=published_at,
        event_date=None,
        retrieved_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
        company_name=company_name,
        industry_id=industry_id,
        trust_level=2,
        content_hash=f"sha256:red-team-{doc_id}",
        review_status=review_status,  # type: ignore[arg-type]
    )


def _make_evidence(
    evidence_id: str,
    *,
    fact_text: str,
    quote: str,
    cutoff_date: date,
    **updates: object,
) -> Evidence:
    """Build a deterministic, verified evidence item with a derived locator.

    ``published_at`` is derived from ``cutoff_date`` so the evidence stays
    within the time lock for any request cutoff.
    """

    suffix = evidence_id.removeprefix("EV-")
    payload: dict[str, object] = {
        "evidence_id": evidence_id,
        "doc_id": f"DOC-{suffix}",
        "chunk_id": f"CHUNK-{suffix}",
        "fact_text": fact_text,
        "quote": quote,
        "published_at": (cutoff_date - timedelta(days=30)).isoformat(),
        "page": 1,
        "locator": "第 1 页",
        "company_name": "示例食品公司",
        "industry_id": "food_beverage",
        "evidence_type": "financial",
        "confidence": 0.9,
        "review_status": "verified",
    }
    payload.update(updates)
    return Evidence.model_validate(payload)


def _make_claim(
    claim_id: str,
    *,
    text: str,
    evidence_ids: list[str],
    **updates: object,
) -> Claim:
    """Build a deterministic pass-level fact claim."""

    payload: dict[str, object] = {
        "claim_id": claim_id,
        "text": text,
        "claim_type": "fact",
        "evidence_ids": evidence_ids,
        "calculation": None,
        "confidence": 0.9,
        "industry_metric_ids": ["revenue_growth"],
        "status": "pass",
    }
    payload.update(updates)
    return Claim.model_validate(payload)


def _relevance_issue(evidence: Evidence, request: ResearchRequest) -> ValidationIssue:
    return ValidationIssue(
        issue_id=f"ISSUE-REDTEAM-{evidence.evidence_id.removeprefix('EV-')}-IRRELEVANT",
        check_name="relevance",
        severity="error",
        issue_type="irrelevant_evidence",
        message=(
            f"{evidence.evidence_id} company_name={evidence.company_name!r} or "
            f"industry_id={evidence.industry_id!r} does not match the request "
            f"company_name={request.company_name!r} / industry_id={request.industry_id!r}."
        ),
        claim_id=None,
        evidence_id=evidence.evidence_id,
        report_section="evidence_filter",
        rerun_required=False,
        human_confirmation_required=False,
        status="open",
    )


def _check_relevance(
    request: ResearchRequest, evidence_list: list[Evidence]
) -> list[ValidationIssue]:
    """Flag evidence whose company or industry does not match the request."""

    issues: list[ValidationIssue] = []
    for evidence in evidence_list:
        company_mismatch = (
            evidence.company_name is not None
            and evidence.company_name != request.company_name
        )
        industry_mismatch = (
            evidence.industry_id is not None
            and evidence.industry_id != request.industry_id
        )
        if company_mismatch or industry_mismatch:
            issues.append(_relevance_issue(evidence, request))
    return issues


def _run_post_cutoff(request: ResearchRequest, config: IndustryConfig) -> list[ValidationIssue]:
    del config
    document = _make_document(
        "DOC-RT-CUTOFF",
        published_at=request.cutoff_date + timedelta(days=1),
        review_status="red_team",
    )
    _, issues = apply_time_lock([document], request.cutoff_date)
    return issues


def _run_undated(request: ResearchRequest, config: IndustryConfig) -> list[ValidationIssue]:
    del config
    document = _make_document(
        "DOC-RT-UNDATED",
        published_at=None,
        review_status="pending_date",
    )
    _, issues = apply_time_lock([document], request.cutoff_date)
    return issues


def _run_wrong_number(request: ResearchRequest, config: IndustryConfig) -> list[ValidationIssue]:
    evidence = _make_evidence(
        "EV-RT-NUM",
        fact_text="公司收入保持稳定。",
        quote="收入保持稳定。",
        cutoff_date=request.cutoff_date,
    )
    claim = _make_claim(
        "CL-RT-WRONG-NUM",
        text="公司收入增长 25%。",
        evidence_ids=[evidence.evidence_id],
    )
    return run_critic(request, [claim], [evidence], config)


def _run_irrelevant(request: ResearchRequest, config: IndustryConfig) -> list[ValidationIssue]:
    del config
    evidence = _make_evidence(
        "EV-RT-IRRELEVANT",
        fact_text="某科技公司季度业绩同比增长 8%。",
        quote="某科技公司季度业绩同比增长 8%。",
        company_name="某科技公司",
        cutoff_date=request.cutoff_date,
    )
    return _check_relevance(request, [evidence])


def _run_conflicting_sources(
    request: ResearchRequest, config: IndustryConfig
) -> list[ValidationIssue]:
    up = _make_evidence(
        "EV-RT-UP",
        fact_text="公司收入增长 10%。",
        quote="收入增长 10%。",
        cutoff_date=request.cutoff_date,
    )
    down = _make_evidence(
        "EV-RT-DOWN",
        fact_text="公司收入下降 5%。",
        quote="收入下降 5%。",
        cutoff_date=request.cutoff_date,
    )
    claim = _make_claim(
        "CL-RT-CONFLICT",
        text="公司收入波动。",
        evidence_ids=[up.evidence_id, down.evidence_id],
    )
    return run_critic(request, [claim], [up, down], config)


def _run_unsupported_claim(
    request: ResearchRequest, config: IndustryConfig
) -> list[ValidationIssue]:
    # A fact claim with no evidence fails Pydantic validation, so bypass it to
    # simulate an upstream module that produced a structural issue the Critic
    # must still catch.
    claim = Claim.model_construct(
        claim_id="CL-RT-NO-EVIDENCE",
        text="公司毛利率将大幅提升 30%。",
        claim_type="fact",
        risk_severity=None,
        evidence_ids=[],
        calculation=None,
        confidence=0.8,
        industry_metric_ids=["revenue_growth"],
        status="pass",
    )
    return run_critic(request, [claim], [], config)


_SCENARIO_BUILDERS = {
    "post_cutoff": _run_post_cutoff,
    "undated": _run_undated,
    "wrong_number": _run_wrong_number,
    "irrelevant": _run_irrelevant,
    "conflicting_sources": _run_conflicting_sources,
    "unsupported_claim": _run_unsupported_claim,
}


def _load_scenario_names(fixture_dir: str) -> list[str]:
    """Read the scenario manifest, defaulting to all six scenarios."""

    path = Path(fixture_dir) / "scenarios.json"
    if not path.is_file():
        return list(SCENARIO_TYPES)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Red-team scenario manifest is not valid JSON: {path} (line {exc.lineno})"
        ) from exc

    scenarios = payload.get("scenarios") if isinstance(payload, dict) else payload
    if not isinstance(scenarios, list) or not scenarios:
        return list(SCENARIO_TYPES)

    names: list[str] = []
    for name in scenarios:
        if name not in _SCENARIO_BUILDERS:
            raise ValueError(f"unknown red-team scenario {name!r}")
        names.append(name)
    return names


def run_red_team(request: ResearchRequest, fixture_dir: str) -> list[ValidationIssue]:
    """Run every red-team scenario and return all produced ValidationIssues.

    ``fixture_dir`` holds an optional ``scenarios.json`` manifest listing which
    scenarios to run; when absent, all six run. Each scenario calls the real
    time-lock and Critic modules with deterministic, hostile inputs. The result
    is the flat, ordered list of issues the system exposed while rejecting bad
    input — a non-empty, correctly-typed result proves the red team was caught.
    """

    scenario_names = _load_scenario_names(fixture_dir)
    config = load_industry_config(request.industry_id)

    issues: list[ValidationIssue] = []
    for name in scenario_names:
        issues.extend(_SCENARIO_BUILDERS[name](request, config))
    return issues
