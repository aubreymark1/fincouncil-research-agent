"""Fast unit tests for run_pipeline using injected lightweight fakes.

The production pipeline defaults to real ingestion/industry modules; these
tests inject in-memory loaders so a full orchestration pass (time lock,
extraction dispatch, evidence location, verification policy, analysis,
Critic, report rendering, three-file output) stays sub-second.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.industry.loader import load_industry_config
from app.model import JsonFileCache, ModelConfig, ModelProvider, ModelProviderError
from app.orchestrator import run_pipeline
from app.schemas import ResearchReport, ResearchRequest, SourceDocument, TextChunk

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CUTOFF = date(2026, 8, 20)


def make_request(tmp_path: Path) -> ResearchRequest:
    output_dir = tmp_path / "outputs" / "reports" / "RUN-UNIT"
    return ResearchRequest(
        run_id="RUN-UNIT",
        company_name="示例食品公司",
        industry_id="food_beverage",
        cutoff_date=CUTOFF,
        source_manifest_path="data/manifests/food_case.csv",
        output_dir=str(output_dir),
    )


def make_document(doc_id: str, *, review_status: str) -> SourceDocument:
    return SourceDocument.model_validate(
        {
            "doc_id": doc_id,
            "title": f"文档 {doc_id}",
            "source_type": "annual_report",
            "publisher": "示例出版方",
            "local_path": "fixtures/synthetic/food_beverage/annual_report_2025.pdf",
            "published_at": "2026-04-17",
            "retrieved_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
            "company_name": "示例食品公司",
            "industry_id": "food_beverage",
            "trust_level": 5,
            "review_status": review_status,
            "content_hash": f"sha256:{doc_id}",
        }
    )


def fake_manifest_loader(path: str) -> list[SourceDocument]:
    del path
    return [
        make_document("DOC-UNIT-001", review_status="formal"),
        make_document("DOC-UNIT-002", review_status="background"),
    ]


def fake_text_extractor(document: SourceDocument) -> list[TextChunk]:
    suffix = "P1" if document.review_status == "formal" else "BG"
    text = (
        "报告期内公司营业收入同比增长 10%，毛利率保持稳定。"
        if document.review_status == "formal"
        else "背景资料：行业观察仅供参考。"
    )
    return [
        TextChunk(
            chunk_id=f"CHUNK-UNIT-{suffix}",
            doc_id=document.doc_id,
            text=text,
            page=1,
            section="管理层讨论与分析",
            paragraph_index=0,
            char_start=0,
            char_end=len(text),
        )
    ]


def test_run_research_writes_report_md_and_metadata_from_real_chain(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert: outputs exist and round-trip
    report_path = Path(request.output_dir) / "report.json"
    markdown_path = Path(request.output_dir) / "report.md"
    metadata_path = (
        tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json"
    )
    assert report_path.exists()
    assert markdown_path.exists() and markdown_path.stat().st_size > 0
    assert metadata_path.exists()

    saved_report = ResearchReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    assert saved_report == state.report

    saved_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert saved_metadata["status"] == "success"
    assert saved_metadata["model_provider"] == "rule-engine"
    assert saved_metadata["model_name"] == "a008-rules"
    assert saved_metadata["errors"] == []
    assert saved_metadata["module_versions"]["orchestrator"] == "v1-a008"
    assert saved_metadata["module_versions"]["cache"] == "none"


def test_pass_claim_cites_verified_financial_evidence_only(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert: at least one pass fact claim backed by verified financial evidence
    pass_claims = [claim for claim in state.report.claims if claim.status == "pass"]
    assert pass_claims, "expected at least one pass claim from formal-source evidence"

    index_ids = {item.evidence_id for item in state.report.evidence_index}
    cited = {
        evidence_id
        for claim in pass_claims
        for evidence_id in claim.evidence_ids
    }
    assert cited & index_ids, "pass claims must cite indexed evidence"

    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    indexed_items = [evidence_by_id[evidence_id] for evidence_id in cited & index_ids]
    assert all(item.review_status == "verified" for item in indexed_items)
    assert all(item.published_at <= CUTOFF for item in indexed_items)

    # The background-source document must never reach the evidence index.
    assert all(item.doc_id != "DOC-UNIT-002" for item in state.report.evidence_index)


def test_verification_policy_audit_issue_is_recorded(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert
    audit = [
        issue
        for issue in state.validation_issues
        if issue.check_name == "evidence_policy"
    ]
    assert len(audit) == 1


def test_unmatched_required_metric_reports_E202_without_duplicating(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert
    checklist_missing = [
        issue
        for issue in state.validation_issues
        if issue.issue_type == "missing_metric"
        and "sales_expense_rate" in issue.message
    ]
    critic_missing = [
        issue
        for issue in state.validation_issues
        if issue.issue_type == "required_metric_missing"
        and "sales_expense_rate" in issue.message
    ]
    assert checklist_missing, (
        "sales_expense_rate has no matching corpus text and must surface E202"
    )
    assert not critic_missing, "Critic E202 copies of checklist findings are dropped"


def test_empty_manifest_yields_unresolved_claims_without_evidence(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    def empty_manifest_loader(path: str) -> list[SourceDocument]:
        del path
        return []

    # Act
    state = run_pipeline(
        request,
        manifest_loader=empty_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert: no documents -> no evidence or body claims; nodes stay honest
    assert not state.evidence
    assert not state.report.claims
    assert all(claim.claim_type == "unresolved" for claim in state.report.unresolved_items)
    assert state.report.unresolved_items


def test_failed_llm_metadata_records_json_cache_version(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    def transport(_prompt: str, _config: ModelConfig) -> dict:
        raise ModelProviderError("E300 module=model.transport: test failure")

    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=transport,
        cache=JsonFileCache(tmp_path / "model-cache.json"),
    )

    # Act / Assert
    with pytest.raises(ModelProviderError, match="E300"):
        run_pipeline(
            request,
            manifest_loader=fake_manifest_loader,
            text_extractor=fake_text_extractor,
            industry_loader=load_industry_config,
            model_provider=provider,
        )

    metadata_path = tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["module_versions"]["cache"] == "v1-json"


@pytest.mark.parametrize("mode", ["E1", "E2", "E3"])
def test_experiment_modes_require_model_provider(tmp_path, mode):
    request = make_request(tmp_path)

    with pytest.raises(ModelProviderError, match="requires a model provider"):
        run_pipeline(request, mode=mode)


def test_e1_runs_generic_agent_without_config(tmp_path):
    request = make_request(tmp_path)
    captured: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        captured.append(prompt)
        return {
            "claims": [
                {
                    "claim_id": "CL-GENERIC-001",
                    "text": "资料显示公司经营稳健。",
                    "claim_type": "analysis",
                    "risk_severity": None,
                    "evidence_ids": ["EV-RAW-UNIT-P1"],
                    "calculation": None,
                    "confidence": 0.5,
                    "industry_metric_ids": [],
                    "status": "pass",
                }
            ]
        }

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        model_provider=provider,
        mode="E1",
    )

    assert state.metadata.mode == "E1"
    assert state.config is None
    assert state.evidence
    assert all(item.review_status == "pending" for item in state.evidence)
    assert state.report.claims
    # Pending evidence must never produce a formal pass claim.
    assert state.report.claims[0].status == "review"
    assert "通用投研分析 Agent" in captured[0]


def test_e1_minimal_strategy_writes_narrative_without_claim_fields(tmp_path):
    request = make_request(tmp_path)

    def transport(prompt: str, _config: ModelConfig) -> dict:
        assert "受控实验综合提示词" in prompt
        return {
            "narrative": [
                {
                    "section": "核心判断",
                    "text": "资料显示公司经营保持稳定。",
                    "evidence_ids": ["EV-RAW-UNIT-P1"],
                }
            ]
        }

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        model_provider=provider,
        mode="E1",
        llm_strategy="minimal",
    )

    assert state.report.narrative[0].section == "核心判断"
    assert state.report.narrative[0].text == "资料显示公司经营保持稳定。"
    assert state.claims == []
    assert state.metadata.prompt_versions == {"minimal_synthesis": "1"}


def test_e1_generic_agent_batches_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr("app.agents.llm.MAX_PROMPT_EVIDENCE_CHARS", 500)
    request = make_request(tmp_path)
    captured: list[str] = []

    def transport(_prompt: str, _config: ModelConfig) -> dict:
        captured.append(_prompt)
        return {"claims": []}

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        model_provider=provider,
        mode="E1",
    )

    assert len(captured) >= 2


def test_e2_loads_config_without_time_lock(tmp_path):
    request = make_request(tmp_path)

    def transport(_prompt: str, _config: ModelConfig) -> dict:
        return {"claims": []}

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        model_provider=provider,
        mode="E2",
    )

    assert state.metadata.mode == "E2"
    assert state.config is not None
    assert state.config.industry_id == "food_beverage"
    assert state.report is not None


def test_e3_runs_full_chain_with_model_provider(tmp_path):
    request = make_request(tmp_path)

    def transport(prompt: str, _config: ModelConfig) -> dict:
        if "行业 Critic 提示词" in prompt:
            return {"issues": []}
        return {"claims": []}

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        model_provider=provider,
        mode="E3",
    )

    assert state.metadata.mode == "E3"
    assert state.config is not None
    assert state.report is not None
    assert any(item.review_status == "verified" for item in state.evidence)


def test_e3_time_lock_ablation_keeps_post_cutoff_evidence(tmp_path):
    request = make_request(tmp_path).model_copy(update={"run_id": "RUN-ABLATION-TIME"})
    future = make_document("DOC-UNIT-FUTURE", review_status="formal").model_copy(
        update={
            "published_at": date(2026, 8, 25),
            "retrieved_at": datetime(2026, 8, 26, tzinfo=timezone.utc),
        }
    )

    def manifest_loader(_path: str):
        return [future]

    def transport(_prompt: str, _config: ModelConfig) -> dict:
        return {"narrative": [{"section": "核心判断", "text": "资料待确认。", "evidence_ids": []}]}

    state = run_pipeline(
        request,
        manifest_loader=manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        model_provider=ModelProvider(ModelConfig(max_retries=0), transport=transport),
        mode="E3",
        llm_strategy="minimal",
        time_lock_enabled=False,
        critic_enabled=False,
    )

    assert any(document.doc_id == future.doc_id for document in state.documents)
    assert any(
        item.published_at > CUTOFF and item.review_status == "verified"
        for item in state.evidence
    )


def test_e3_critic_ablation_controls_narrative_critic(tmp_path):
    request = make_request(tmp_path)

    def transport(_prompt: str, _config: ModelConfig) -> dict:
        return {
            "narrative": [
                {
                    "section": "核心判断",
                    "text": "公司收入增长 25%。",
                    "evidence_ids": [],
                }
            ]
        }

    def run(critic_enabled: bool, run_id: str):
        return run_pipeline(
            request.model_copy(update={"run_id": run_id}),
            manifest_loader=fake_manifest_loader,
            text_extractor=fake_text_extractor,
            industry_loader=load_industry_config,
            model_provider=ModelProvider(ModelConfig(max_retries=0), transport=transport),
            mode="E3",
            llm_strategy="minimal",
            critic_enabled=critic_enabled,
        )

    with_critic = run(True, "RUN-ABLATION-CRITIC-ON")
    without_critic = run(False, "RUN-ABLATION-CRITIC-OFF")

    assert any(
        issue.issue_type == "narrative_missing_evidence"
        for issue in with_critic.validation_issues
    )
    assert not any(
        issue.issue_type == "narrative_missing_evidence"
        for issue in without_critic.validation_issues
    )


def test_unknown_mode_is_rejected(tmp_path):
    request = make_request(tmp_path)

    with pytest.raises(ValueError, match="unknown mode"):
        run_pipeline(request, mode="E4")


def test_progress_callback_reports_real_rule_engine_stages(tmp_path):
    # Arrange
    request = make_request(tmp_path)
    stages: list[str] = []

    # Act
    run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
        progress_callback=stages.append,
    )

    # Assert
    assert stages[0] == "准备研究请求"
    assert "校验资料清单" in stages
    assert "执行时间过滤" in stages
    assert "解析原始资料" in stages
    assert "定位证据" in stages
    assert "生成分析结论" in stages
    assert "执行 Critic 审查" in stages
    assert "写入报告产物" in stages
    assert stages[-1] == "研究完成"
