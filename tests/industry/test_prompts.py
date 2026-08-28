"""Tests for C-006 industry prompt files.

The prompts are content requirements consumed by A's agents, not code, but
they must exist and carry the mandatory safety constraints from
``docs/roles/C.md`` so a future loader cannot silently ship a stripped prompt.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
PROMPT_DIR = ROOT / "prompts"

_PROMPT_FILES = {
    "fundamental.md",
    "news_policy.md",
    "risk.md",
    "critic_industry.md",
}

# Every prompt must require these behaviours regardless of node.
_MANDATORY_TERMS = (
    "只使用给定",
    "不得生成任何 URL",
    "不得预测目标价",
)

# Claim-producing prompts must additionally enforce evidence binding and the
# unresolved fallback; the Critic prompt emits ValidationIssue, not Claim.
_CLAIM_PROMPTS = {"fundamental.md", "news_policy.md", "risk.md"}
_CLAIM_TERMS = ("unresolved", "evidence_id")


def _read(prompt: str) -> str:
    return (PROMPT_DIR / prompt).read_text(encoding="utf-8")


def test_all_prompt_files_exist() -> None:
    missing = sorted(_PROMPT_FILES - {p.name for p in PROMPT_DIR.glob("*.md")})
    assert missing == [], f"missing prompt files: {missing}"


def test_every_prompt_carries_mandatory_terms() -> None:
    for prompt in _PROMPT_FILES:
        text = _read(prompt)
        for term in _MANDATORY_TERMS:
            assert term in text, f"{prompt} is missing mandatory term: {term!r}"


def test_claim_prompts_carry_claim_terms() -> None:
    for prompt in _CLAIM_PROMPTS:
        text = _read(prompt)
        for term in _CLAIM_TERMS:
            assert term in text, f"{prompt} is missing claim term: {term!r}"


def test_fundamental_prompt_covers_inventory_calibers() -> None:
    text = _read("fundamental.md")

    assert "inventory" in text
    assert "inventory_volume" in text
    assert "channel" in text
    assert "net_interest_margin" in text
    assert "capital_adequacy" in text


def test_news_policy_prompt_blocks_industry_news_overreach() -> None:
    text = _read("news_policy.md")

    assert "change" in text
    assert "食品安全" in text
    assert "房地产" in text
    assert "real_estate_exposure" in text


def test_risk_prompt_copies_rule_metadata() -> None:
    text = _read("risk.md")

    assert "severity" in text
    assert "industry_metric_ids" in text
    assert "RiskRule" in text
    assert "trigger_terms" in text
    assert "exclude_terms" in text


def test_critic_prompt_outputs_validation_issues_only() -> None:
    text = _read("critic_industry.md")

    assert "ValidationIssue" in text
    assert "E401" in text
    assert "E202" in text
    assert "management_plan_as_fact" in text
