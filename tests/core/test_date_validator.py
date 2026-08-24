"""Tests for the A-002 cutoff-date validator."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.schemas import SourceDocument
from app.validators import apply_time_lock


ROOT = Path(__file__).parents[2]
SOURCE_FIXTURE = ROOT / "fixtures" / "shared" / "source_document.json"


def make_document(
    *, published_at: str | None, event_date: str | None = "2026-08-20"
) -> SourceDocument:
    payload = json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    payload["published_at"] = published_at
    payload["event_date"] = event_date
    return SourceDocument.model_validate(payload)


def test_published_before_cutoff_is_allowed() -> None:
    document = make_document(published_at="2026-08-19", event_date="2026-08-19")

    allowed, issues = apply_time_lock([document], date(2026, 8, 20))

    assert allowed == [document]
    assert issues == []


def test_published_on_cutoff_is_allowed() -> None:
    document = make_document(published_at="2026-08-20", event_date="2026-08-20")

    allowed, issues = apply_time_lock([document], date(2026, 8, 20))

    assert allowed == [document]
    assert issues == []


def test_published_after_cutoff_is_rejected_with_e103_issue() -> None:
    document = make_document(published_at="2026-08-21", event_date="2026-08-21")

    allowed, issues = apply_time_lock([document], date(2026, 8, 20))

    assert allowed == []
    assert len(issues) == 1
    assert issues[0].issue_type == "published_after_cutoff"
    assert issues[0].severity == "critical"
    assert issues[0].status == "open"
    assert "E103" in issues[0].message


def test_missing_published_at_is_held_for_manual_verification() -> None:
    document = make_document(published_at=None, event_date="2026-08-20")

    allowed, issues = apply_time_lock([document], date(2026, 8, 20))

    assert allowed == []
    assert len(issues) == 1
    assert issues[0].issue_type == "missing_published_at"
    assert issues[0].human_confirmation_required is True
    assert issues[0].status == "open"
    assert "E102" in issues[0].message


def test_future_event_date_is_allowed_when_published_by_cutoff() -> None:
    document = make_document(published_at="2026-08-19", event_date="2026-08-21")

    allowed, issues = apply_time_lock([document], date(2026, 8, 20))

    assert allowed == [document]
    assert len(issues) == 1
    assert issues[0].issue_type == "event_after_cutoff"
    assert issues[0].severity == "info"
    assert issues[0].status == "accepted_risk"
    assert "event_date" in issues[0].message
