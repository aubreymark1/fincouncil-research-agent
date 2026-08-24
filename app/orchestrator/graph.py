"""Minimum orchestration graph with fixture-backed B/C stubs.

The loader and extractor callables are injectable so B and C can be connected
after their PRs are merged without creating duplicate implementations here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchReport,
    ResearchRequest,
    RunMetadata,
    SourceDocument,
    TextChunk,
)
from app.validators import apply_time_lock

from .state import ResearchState


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_FIXTURES = PROJECT_ROOT / "fixtures" / "shared"

ManifestLoader = Callable[[str], list[SourceDocument]]
TextExtractor = Callable[[SourceDocument], list[TextChunk]]
IndustryLoader = Callable[[str], IndustryConfig]


def _read_fixture(name: str) -> dict[str, Any]:
    path = SHARED_FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


def _stub_load_manifest(path: str) -> list[SourceDocument]:
    """Load the shared source fixture until B-001 supplies a real loader."""

    del path
    return [SourceDocument.model_validate(_read_fixture("source_document.json"))]


def _stub_extract_pdf(document: SourceDocument) -> list[TextChunk]:
    """Return one location-preserving fixture chunk without parsing a PDF."""

    return [
        TextChunk(
            chunk_id=f"CHUNK-{document.doc_id.removeprefix('DOC-')}-STUB",
            doc_id=document.doc_id,
            text="A-003 fixture extraction stub.",
            page=1,
            section="fixture",
            paragraph_index=0,
            char_start=0,
            char_end=31,
        )
    ]


def _stub_load_industry_config(industry_id: str) -> IndustryConfig:
    """Load the shared food configuration until C-001 supplies a loader."""

    if industry_id != "food_beverage":
        raise ValueError(f"E200 module=orchestrator: no fixture config for industry_id={industry_id}")
    return IndustryConfig.model_validate(_read_fixture("food_config.json"))


def _load_fixture_evidence() -> list[Evidence]:
    return [Evidence.model_validate(_read_fixture("evidence.json"))]


def _build_test_claim(state: ResearchState) -> list[Claim]:
    """Build one deterministic Claim from the shared evidence fixture."""

    if not state.evidence or state.config is None:
        return [
            Claim(
                claim_id="CL-DEMO-UNRESOLVED",
                text="测试证据或行业配置尚不可用。",
                claim_type="unresolved",
                evidence_ids=[],
                calculation=None,
                confidence=0.0,
                industry_metric_ids=[],
                status="review",
            )
        ]

    evidence = state.evidence[0]
    metric_id = state.config.required_metrics[0].metric_id
    return [
        Claim(
            claim_id="CL-DEMO-001",
            text=evidence.fact_text,
            claim_type="fact",
            evidence_ids=[evidence.evidence_id],
            calculation=None,
            confidence=evidence.confidence,
            industry_metric_ids=[metric_id],
            status="pass",
        )
    ]


def _resolve_output_paths(request: ResearchRequest) -> tuple[Path, Path]:
    output_dir = Path(request.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir = output_dir.resolve()

    outputs_root = next(
        (parent for parent in (output_dir, *output_dir.parents) if parent.name.lower() == "outputs"),
        None,
    )
    if outputs_root is None:
        raise ValueError("E500 module=orchestrator: output_dir is not below an outputs directory")

    metadata_path = outputs_root / "logs" / request.run_id / "run_metadata.json"
    return output_dir / "report.json", metadata_path


def _write_outputs(
    *,
    request: ResearchRequest,
    report: ResearchReport,
    metadata: RunMetadata,
) -> tuple[Path, Path]:
    report_path, metadata_path = _resolve_output_paths(request)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path, metadata_path


def run_pipeline(
    request: ResearchRequest,
    *,
    manifest_loader: ManifestLoader | None = None,
    text_extractor: TextExtractor | None = None,
    industry_loader: IndustryLoader | None = None,
) -> ResearchState:
    """Run the minimum fixture-backed pipeline and persist its outputs."""

    started_at = datetime.now(timezone.utc)
    state = ResearchState(request=request)
    load_manifest = manifest_loader or _stub_load_manifest
    extract_text = text_extractor or _stub_extract_pdf
    load_industry = industry_loader or _stub_load_industry_config

    state.documents = load_manifest(request.source_manifest_path)
    state.documents, time_lock_issues = apply_time_lock(
        state.documents,
        request.cutoff_date,
    )
    state.validation_issues.extend(time_lock_issues)

    for document in state.documents:
        state.chunks.extend(extract_text(document))

    state.config = load_industry(request.industry_id)
    state.evidence = [
        evidence
        for evidence in _load_fixture_evidence()
        if evidence.published_at <= request.cutoff_date
    ]
    state.claims = _build_test_claim(state)

    generated_at = datetime.now(timezone.utc)
    state.report = ResearchReport(
        run_id=request.run_id,
        company_name=request.company_name,
        industry_id=request.industry_id,
        cutoff_date=request.cutoff_date,
        summary=["A-003 fixture-backed minimum report."],
        claims=state.claims,
        risks=[],
        unresolved_items=[claim for claim in state.claims if claim.claim_type == "unresolved"],
        evidence_index=state.evidence,
        validation_issues=state.validation_issues,
        generated_at=generated_at,
        report_version="v1-a003",
    )

    request_hash = hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    state.metadata = RunMetadata(
        run_id=request.run_id,
        started_at=started_at,
        finished_at=generated_at,
        status="success",
        model_provider="fixture",
        model_name="a003-stub",
        prompt_versions={},
        input_hashes={"request": f"sha256:{request_hash}"},
        module_versions={"orchestrator": "v1-a003", "validators": "v1-a002"},
        errors=[],
    )
    _write_outputs(request=request, report=state.report, metadata=state.metadata)
    return state
