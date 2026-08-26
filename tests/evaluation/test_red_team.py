"""Deterministic tests for the D-004 red-team runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas import ResearchRequest, ValidationIssue
from evaluation.red_team import SCENARIO_TYPES, run_red_team


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "evaluation"
RED_TEAM_FIXTURES = FIXTURES / "red_team"


def make_request(**updates: object) -> ResearchRequest:
    payload = json.loads(
        (ROOT / "fixtures" / "shared" / "research_request.json").read_text(encoding="utf-8")
    )
    payload.update(updates)
    return ResearchRequest.model_validate(payload)


def _run(request: ResearchRequest | None = None, fixture_dir: Path = RED_TEAM_FIXTURES) -> list[ValidationIssue]:
    return run_red_team(request or make_request(), str(fixture_dir))


def _of_type(issues: list[ValidationIssue], issue_type: str) -> list[ValidationIssue]:
    return [issue for issue in issues if issue.issue_type == issue_type]


def test_all_six_scenario_issue_types_are_present() -> None:
    issues = _run()

    produced = {issue.issue_type for issue in issues}
    assert {
        "published_after_cutoff",
        "missing_published_at",
        "unsourced_number",
        "irrelevant_evidence",
        "conflicting_evidence",
        "missing_evidence",
    } <= produced


def test_post_cutoff_document_is_rejected_as_critical() -> None:
    cutoff = _of_type(_run(), "published_after_cutoff")

    assert len(cutoff) == 1
    assert cutoff[0].severity == "critical"
    assert "E103" in cutoff[0].message
    assert cutoff[0].evidence_id is None


def test_undated_document_is_held_for_manual_confirmation() -> None:
    undated = _of_type(_run(), "missing_published_at")

    assert len(undated) == 1
    assert undated[0].severity == "warning"
    assert undated[0].human_confirmation_required is True
    assert "E102" in undated[0].message


def test_wrong_number_produces_unsourced_number_issue() -> None:
    unsourced = _of_type(_run(), "unsourced_number")

    assert len(unsourced) == 1
    assert unsourced[0].severity == "error"
    assert unsourced[0].claim_id == "CL-RT-WRONG-NUM"
    assert "25%" in unsourced[0].message


def test_irrelevant_evidence_is_flagged() -> None:
    irrelevant = _of_type(_run(), "irrelevant_evidence")

    assert len(irrelevant) == 1
    assert irrelevant[0].severity == "error"
    assert irrelevant[0].evidence_id == "EV-RT-IRRELEVANT"


def test_conflicting_sources_require_manual_confirmation() -> None:
    conflicts = _of_type(_run(), "conflicting_evidence")

    assert len(conflicts) >= 1
    assert all(issue.human_confirmation_required is True for issue in conflicts)


def test_unsupported_claim_is_reported_as_missing_evidence() -> None:
    missing = _of_type(_run(), "missing_evidence")

    assert len(missing) == 1
    assert missing[0].severity == "error"
    assert missing[0].claim_id == "CL-RT-NO-EVIDENCE"
    assert "E400" in missing[0].message


def test_scenario_manifest_can_select_a_subset(tmp_path: Path) -> None:
    manifest = tmp_path / "scenarios.json"
    manifest.write_text(
        json.dumps({"scenarios": ["post_cutoff"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    issues = _run(fixture_dir=tmp_path)

    produced = {issue.issue_type for issue in issues}
    assert produced == {"published_after_cutoff"}


def test_missing_manifest_defaults_to_all_scenarios(tmp_path: Path) -> None:
    issues = _run(fixture_dir=tmp_path)

    produced = {issue.issue_type for issue in issues}
    assert "published_after_cutoff" in produced
    assert "missing_evidence" in produced


def test_unknown_scenario_name_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "scenarios.json"
    manifest.write_text(
        json.dumps({"scenarios": ["not_a_scenario"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown red-team scenario"):
        _run(fixture_dir=tmp_path)


def test_every_scenario_type_has_a_builder() -> None:
    issues = _run()
    assert all(issue.issue_id.startswith(("ISSUE-TIME-", "ISSUE-CRITIC-", "ISSUE-REDTEAM-")) for issue in issues)
    assert len(SCENARIO_TYPES) == 6
