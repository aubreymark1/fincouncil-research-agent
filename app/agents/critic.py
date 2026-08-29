"""Critic that validates claims, evidence, and industry coverage before reporting.

The Critic is intentionally defensive: it assumes upstream modules may still
produce structural issues, and it returns ``ValidationIssue`` objects instead
of raising so every problem remains visible to the report and the evaluator.
"""

from __future__ import annotations

import hashlib
import re

from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ReportBlock,
    ResearchRequest,
    ValidationIssue,
)


_NUMBER_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|亿元|万元|元|倍|个百分点|亿|万)"
)
_PLAN_KEYWORDS = (
    "计划",
    "预计",
    "目标",
    "将",
    "拟",
    "有望",
    "承诺",
    "规划",
)
_UP_TERMS = ("增长", "上升", "增加", "提高", "上涨", "加速")
_DOWN_TERMS = ("下降", "下滑", "减少", "降低", "下跌", "回落")
_MISSING_ACTION_SEVERITY = {
    "warn": "warning",
    "review": "error",
    "reject": "critical",
}


def _issue_key(check_name: str, key: str) -> str:
    """Build a stable, schema-valid issue ID for a given check and target."""

    digest = hashlib.sha256(f"{check_name}:{key}".encode("utf-8")).hexdigest()[:10].upper()
    safe_check = re.sub(r"[^A-Za-z0-9]+", "-", check_name).strip("-").upper()
    return f"ISSUE-CRITIC-{safe_check}-{digest}"


def _make_issue(
    *,
    check_name: str,
    severity: str,
    issue_type: str,
    message: str,
    claim_id: str | None = None,
    evidence_id: str | None = None,
    target_key: str | None = None,
    human_confirmation_required: bool = False,
    rerun_required: bool = True,
) -> ValidationIssue:
    """Create one open ValidationIssue using a deterministic ID.

    ``target_key`` makes the ID unique when neither ``claim_id`` nor
    ``evidence_id`` fully identifies the problem (e.g. metric-level checks,
    or the same claim referencing several unknown evidence IDs).
    """

    key = target_key or claim_id or evidence_id or issue_type
    return ValidationIssue(
        issue_id=_issue_key(check_name, key),
        check_name=check_name,
        severity=severity,
        issue_type=issue_type,
        message=message,
        claim_id=claim_id,
        evidence_id=evidence_id,
        report_section=None,
        rerun_required=rerun_required,
        human_confirmation_required=human_confirmation_required,
        status="open",
    )


def _normalize_number(token: str) -> str:
    return re.sub(r"\s+", "", token)


def _extract_numbers(text: str) -> list[str]:
    return [_normalize_number(token) for token in _NUMBER_PATTERN.findall(text)]


def _direction(text: str) -> str | None:
    lowered = text.casefold()
    has_up = any(term in lowered for term in _UP_TERMS)
    has_down = any(term in lowered for term in _DOWN_TERMS)
    if has_up and has_down:
        return "mixed"
    if has_up:
        return "up"
    if has_down:
        return "down"
    return None


def _check_cutoff(
    request: ResearchRequest,
    evidence: list[Evidence],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for item in evidence:
        if item.published_at > request.cutoff_date:
            issues.append(
                _make_issue(
                    check_name="cutoff_violation",
                    severity="critical",
                    issue_type="cutoff_violation",
                    message=(
                        f"E103 {item.evidence_id} published_at "
                        f"{item.published_at.isoformat()} is after cutoff "
                        f"{request.cutoff_date.isoformat()}."
                    ),
                    evidence_id=item.evidence_id,
                    rerun_required=True,
                )
            )
    return issues


def _check_claim_support(claims: list[Claim]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for claim in claims:
        if claim.claim_type != "unresolved" and not claim.evidence_ids:
            issues.append(
                _make_issue(
                    check_name="missing_evidence",
                    severity="error",
                    issue_type="missing_evidence",
                    message=(
                        f"E400 {claim.claim_id} has no evidence_ids but is not "
                        "an unresolved claim."
                    ),
                    claim_id=claim.claim_id,
                    rerun_required=True,
                )
            )
    return issues


def _check_unknown_evidence(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for claim in claims:
        for evidence_id in claim.evidence_ids:
            if evidence_id not in evidence_by_id:
                issues.append(
                    _make_issue(
                        check_name="unknown_evidence_id",
                        severity="error",
                        issue_type="unknown_evidence_id",
                        message=(
                            f"E402 {claim.claim_id} references unknown evidence "
                            f"{evidence_id}."
                        ),
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        target_key=f"{claim.claim_id}:{evidence_id}",
                        rerun_required=True,
                    )
                )
    return issues


def _check_non_verified_evidence(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> list[ValidationIssue]:
    """Block pending/rejected evidence from supporting substantive claims.

    The public contract says pending and rejected Evidence must not support
    key report conclusions. A Claim that is not unresolved and is ready for
    reporting (pass or review) must only reference verified Evidence.
    """

    issues: list[ValidationIssue] = []
    for claim in claims:
        if claim.claim_type == "unresolved":
            continue
        if claim.status not in {"pass", "review"}:
            continue
        for evidence_id in claim.evidence_ids:
            item = evidence_by_id.get(evidence_id)
            if item is None or item.review_status == "verified":
                continue
            issues.append(
                _make_issue(
                    check_name="evidence_status",
                    severity="critical",
                    issue_type="non_verified_evidence",
                    message=(
                        f"{claim.claim_id} references {evidence_id} with "
                        f"review_status={item.review_status}; pending or "
                        "rejected Evidence must not support substantive claims."
                    ),
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                    target_key=f"{claim.claim_id}:{evidence_id}",
                    rerun_required=True,
                )
            )
    return issues


def _check_unsourced_numbers(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for claim in claims:
        if claim.claim_type == "unresolved" or claim.calculation is not None:
            continue
        if not claim.evidence_ids:
            # The missing-evidence check already reports the structural problem.
            continue
        numbers = _extract_numbers(claim.text)
        if not numbers:
            continue

        supporting_text = "\n".join(
            f"{evidence_by_id[evidence_id].fact_text}\n"
            f"{evidence_by_id[evidence_id].quote}"
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_by_id
        )
        normalized_support = _normalize_number(supporting_text)
        unsupported = [
            number for number in numbers if number not in normalized_support
        ]
        if unsupported:
            issues.append(
                _make_issue(
                    check_name="unsourced_number",
                    severity="error",
                    issue_type="unsourced_number",
                    message=(
                        f"{claim.claim_id} contains precise number(s) "
                        f"{', '.join(unsupported)} that do not appear in any "
                        "referenced evidence and have no calculation."
                    ),
                    claim_id=claim.claim_id,
                    rerun_required=True,
                )
            )
    return issues


def _check_locators(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    referenced_ids: set[str] = set()
    for claim in claims:
        referenced_ids.update(
            evidence_id
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_by_id
        )

    for evidence_id in sorted(referenced_ids):
        item = evidence_by_id[evidence_id]
        if not item.locator.strip():
            issues.append(
                _make_issue(
                    check_name="missing_locator",
                    severity="error",
                    issue_type="missing_locator",
                    message=(
                        f"E402 {evidence_id} is referenced by a claim but has "
                        "no non-empty locator."
                    ),
                    evidence_id=evidence_id,
                    rerun_required=True,
                )
            )
        if item.page is None:
            issues.append(
                _make_issue(
                    check_name="missing_page",
                    severity="warning",
                    issue_type="missing_page",
                    message=(
                        f"{evidence_id} has no page number; if the source has "
                        "no physical pagination, the locator must make this clear."
                    ),
                    evidence_id=evidence_id,
                    rerun_required=False,
                )
            )
    return issues


def _check_management_plan_as_fact(claims: list[Claim]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for claim in claims:
        if claim.claim_type != "fact":
            continue
        lowered = claim.text.casefold()
        if any(keyword in lowered for keyword in _PLAN_KEYWORDS):
            issues.append(
                _make_issue(
                    check_name="management_plan_as_fact",
                    severity="warning",
                    issue_type="management_plan_as_fact",
                    message=(
                        f"{claim.claim_id} presents a management plan or target "
                        "as a fact; it should be typed as change/analysis or "
                        "reviewed manually."
                    ),
                    claim_id=claim.claim_id,
                    human_confirmation_required=True,
                    rerun_required=False,
                )
            )
    return issues


def _has_valid_evidence(
    claim: Claim,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    """Return whether a Claim can count as metric coverage.

    Unresolved, draft, rejected, evidence-less Claims, and Claims that only
    reference pending/rejected Evidence do not cover a required metric.
    """

    if claim.claim_type == "unresolved" or claim.status in {"draft", "reject"}:
        return False
    if not claim.evidence_ids:
        return False
    return any(
        evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].review_status == "verified"
        for evidence_id in claim.evidence_ids
    )


def _check_required_metrics(
    claims: list[Claim],
    config: IndustryConfig,
    evidence_by_id: dict[str, Evidence],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    covered_metric_ids = {
        metric_id
        for claim in claims
        if _has_valid_evidence(claim, evidence_by_id)
        for metric_id in claim.industry_metric_ids
    }
    for metric in config.required_metrics:
        if not metric.required:
            continue
        if metric.metric_id in covered_metric_ids:
            continue
        issues.append(
            _make_issue(
                check_name="required_metric_missing",
                severity=_MISSING_ACTION_SEVERITY[metric.missing_action],
                issue_type="required_metric_missing",
                message=(
                    f"E202 required metric {metric.metric_id} "
                    f"({metric.display_name}) has no Claim."
                ),
                target_key=metric.metric_id,
                rerun_required=True,
            )
        )
    return issues


def _check_conflicting_evidence(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Conflict inside a single claim that cites multiple evidence items.
    for claim in claims:
        referenced = [
            evidence_by_id[evidence_id]
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_by_id
        ]
        if len(referenced) < 2:
            continue
        directions = {
            _direction(f"{item.fact_text}\n{item.quote}") for item in referenced
        }
        if "up" in directions and "down" in directions:
            issues.append(
                _make_issue(
                    check_name="conflicting_evidence",
                    severity="warning",
                    issue_type="conflicting_evidence",
                    message=(
                        f"{claim.claim_id} cites evidence with both upward and "
                        "downward directions."
                    ),
                    claim_id=claim.claim_id,
                    human_confirmation_required=True,
                    rerun_required=False,
                )
            )

    # Conflict across claims that address the same industry metric.
    claims_by_metric: dict[str, list[Claim]] = {}
    for claim in claims:
        if claim.claim_type == "unresolved":
            continue
        for metric_id in claim.industry_metric_ids:
            claims_by_metric.setdefault(metric_id, []).append(claim)

    for metric_id, metric_claims in claims_by_metric.items():
        directions = set()
        for claim in metric_claims:
            evidence_text = "\n".join(
                f"{evidence_by_id[evidence_id].fact_text}\n"
                f"{evidence_by_id[evidence_id].quote}"
                for evidence_id in claim.evidence_ids
                if evidence_id in evidence_by_id
            )
            if claim.evidence_ids:
                direction = _direction(evidence_text)
                if direction:
                    directions.add(direction)
            else:
                direction = _direction(claim.text)
                if direction:
                    directions.add(direction)
        if "up" in directions and "down" in directions:
            claim_ids = "、".join(claim.claim_id for claim in metric_claims)
            issues.append(
                _make_issue(
                    check_name="conflicting_evidence",
                    severity="warning",
                    issue_type="conflicting_evidence",
                    message=(
                        f"metric {metric_id} has claims with conflicting "
                        f"directions: {claim_ids}."
                    ),
                    target_key=f"metric:{metric_id}",
                    human_confirmation_required=True,
                    rerun_required=False,
                )
            )
    return issues


def _check_unparsed_model_output(claims: list[Claim]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for claim in claims:
        if claim.status == "draft":
            issues.append(
                _make_issue(
                    check_name="model_output_unparsed",
                    severity="error",
                    issue_type="model_output_unparsed",
                    message=(
                        f"{claim.claim_id} is still in draft status; the model "
                        "output has not been classified for reporting."
                    ),
                    claim_id=claim.claim_id,
                    rerun_required=True,
                )
            )
    return issues


def run_critic(
    request: ResearchRequest,
    claims: list[Claim],
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[ValidationIssue]:
    """Validate claims and evidence before they enter the report.

    The function is additive: every check returns its own ``ValidationIssue``
    and no check mutates the input claims or evidence.
    """

    evidence_by_id = {item.evidence_id: item for item in evidence}
    issues: list[ValidationIssue] = []
    issues.extend(_check_cutoff(request, evidence))
    issues.extend(_check_claim_support(claims))
    issues.extend(_check_unknown_evidence(claims, evidence_by_id))
    issues.extend(_check_non_verified_evidence(claims, evidence_by_id))
    issues.extend(_check_unsourced_numbers(claims, evidence_by_id))
    issues.extend(_check_locators(claims, evidence_by_id))
    issues.extend(_check_management_plan_as_fact(claims))
    issues.extend(_check_required_metrics(claims, config, evidence_by_id))
    issues.extend(_check_conflicting_evidence(claims, evidence_by_id))
    issues.extend(_check_unparsed_model_output(claims))
    return issues


def run_narrative_critic(
    request: ResearchRequest,
    narrative: list[ReportBlock],
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[ValidationIssue]:
    """Check narrative-only output without requiring a full Claim schema."""

    evidence_by_id = {item.evidence_id: item for item in evidence}
    issues: list[ValidationIssue] = []
    for block in narrative:
        if not block.evidence_ids:
            if _extract_numbers(block.text):
                issues.append(
                    _make_issue(
                        check_name="narrative_critic",
                        severity="error",
                        issue_type="narrative_missing_evidence",
                        message=(
                            f"Narrative section {block.section} contains precise "
                            "numbers but has no evidence_ids."
                        ),
                        target_key=block.section,
                        rerun_required=True,
                    )
                )
            continue

        supporting_text: list[str] = []
        for evidence_id in block.evidence_ids:
            item = evidence_by_id.get(evidence_id)
            if item is None:
                issues.append(
                    _make_issue(
                        check_name="narrative_critic",
                        severity="error",
                        issue_type="narrative_unknown_evidence_id",
                        message=(
                            f"Narrative section {block.section} references unknown "
                            f"evidence {evidence_id}."
                        ),
                        evidence_id=evidence_id,
                        target_key=f"{block.section}:{evidence_id}",
                        rerun_required=True,
                    )
                )
                continue

            supporting_text.extend([item.fact_text, item.quote])
            if item.review_status != "verified":
                issues.append(
                    _make_issue(
                        check_name="narrative_critic",
                        severity="critical",
                        issue_type="narrative_non_verified_evidence",
                        message=(
                            f"Narrative section {block.section} references {evidence_id} "
                            f"with review_status={item.review_status}."
                        ),
                        evidence_id=evidence_id,
                        target_key=f"{block.section}:{evidence_id}:status",
                        rerun_required=True,
                    )
                )
            if item.published_at > request.cutoff_date:
                issues.append(
                    _make_issue(
                        check_name="narrative_critic",
                        severity="critical",
                        issue_type="narrative_cutoff_violation",
                        message=(
                            f"Narrative section {block.section} cites {evidence_id} "
                            f"published after cutoff {request.cutoff_date.isoformat()}."
                        ),
                        evidence_id=evidence_id,
                        target_key=f"{block.section}:{evidence_id}:cutoff",
                        rerun_required=True,
                    )
                )

        if supporting_text:
            normalized_support = _normalize_number("\n".join(supporting_text))
            unsupported = [
                number
                for number in _extract_numbers(block.text)
                if number not in normalized_support
            ]
            if unsupported:
                issues.append(
                    _make_issue(
                        check_name="narrative_critic",
                        severity="error",
                        issue_type="narrative_unsourced_number",
                        message=(
                            f"Narrative section {block.section} contains number(s) "
                            f"{', '.join(unsupported)} not found in cited evidence."
                        ),
                        target_key=f"{block.section}:numbers",
                        rerun_required=True,
                    )
                )

        if "风险" in block.section:
            lowered_text = block.text.casefold()
            for rule in config.risk_rules:
                trigger_hit = any(term.casefold() in lowered_text for term in rule.trigger_terms)
                exclude_hit = any(term.casefold() in lowered_text for term in rule.exclude_terms)
                if trigger_hit and exclude_hit:
                    issues.append(
                        _make_issue(
                            check_name="narrative_critic",
                            severity="warning",
                            issue_type="narrative_conflicting_risk",
                            message=(
                                f"Narrative section {block.section} contains both "
                                f"trigger and exclude signals for risk {rule.risk_id}."
                            ),
                            target_key=f"{block.section}:{rule.risk_id}",
                            human_confirmation_required=True,
                            rerun_required=False,
                        )
                    )
    return issues
