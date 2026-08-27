"""Real-B/C orchestration graph: manifest -> time lock -> extraction ->
evidence location -> verification policy -> analysis -> Critic -> report.

The loader and extractor callables remain injectable so unit tests can use
lightweight fakes while production runs use the real ingestion and industry
modules by default.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents import (
    get_prompt_versions,
    render_markdown,
    render_report,
    run_critic,
    run_critic_llm,
)
from app.agents.aggregation import run_analysis
from app.industry.checklist import check_required_metrics
from app.industry.loader import load_industry_config
from app.industry.metric_rules import apply_metric_rules
from app.ingestion.chunker import chunk_text
from app.ingestion.evidence_locator import locate_evidence
from app.ingestion.html_extractor import extract_html
from app.ingestion.manifest import load_manifest, validate_manifest
from app.ingestion.pdf_extractor import extract_pdf
from app.model import ModelProvider, ModelProviderError
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchReport,
    ResearchRequest,
    RunMetadata,
    SourceDocument,
    TextChunk,
    ValidationIssue,
)
from app.validators import apply_time_lock

from .evidence_policy import apply_evidence_policy
from .state import ResearchState


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHUNK_MAX_CHARS = 400
MANIFEST_BLOCKING_SEVERITIES = frozenset({"error", "critical"})
_REQUIRED_METRIC_RE = re.compile(r"required metric (\S+)")

ManifestLoader = Callable[[str], list[SourceDocument]]
TextExtractor = Callable[[SourceDocument], list[TextChunk]]
IndustryLoader = Callable[[str], IndustryConfig]


def _extract_document_text(document: SourceDocument) -> list[TextChunk]:
    """Dispatch real extraction on the source file suffix."""

    suffix = Path(document.local_path).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(document)
    if suffix in {".html", ".htm"}:
        return extract_html(document)
    raise ValueError(
        f"E100 module=orchestrator: unsupported source format "
        f"{suffix!r} for {document.doc_id}"
    )


def _merge_evidence(pools: list[list[Evidence]]) -> list[Evidence]:
    """Merge located-evidence pools keeping the first item per evidence_id."""

    merged: dict[str, Evidence] = {}
    for pool in pools:
        for item in pool:
            merged.setdefault(item.evidence_id, item)
    return list(merged.values())


def _locate_config_evidence(
    *,
    chunks: list[TextChunk],
    config: IndustryConfig,
    documents: list[SourceDocument],
) -> list[Evidence]:
    """Locate evidence through metric keywords, risk triggers, and leftovers."""

    pools: list[list[Evidence]] = []

    metric_keywords: set[str] = set()
    for metric in config.required_metrics:
        metric_keywords.update(metric.keywords)
        for evidence_type in metric.evidence_types:
            pools.append(
                locate_evidence(
                    chunks,
                    metric.keywords,
                    documents=documents,
                    evidence_type=evidence_type,
                )
            )

    for rule in config.risk_rules:
        for evidence_type in rule.required_evidence_types:
            pools.append(
                locate_evidence(
                    chunks,
                    rule.trigger_terms,
                    documents=documents,
                    evidence_type=evidence_type,
                )
            )

    leftover = [
        keyword
        for keyword in config.retrieval_keywords
        if keyword not in metric_keywords
    ]
    if leftover:
        pools.append(
            locate_evidence(chunks, leftover, documents=documents, evidence_type="other")
        )

    return _merge_evidence(pools)


def _drop_duplicated_metric_issues(
    critic_issues: list[ValidationIssue],
    industry_issues: list[ValidationIssue],
) -> list[ValidationIssue]:
    """Remove Critic E202 entries already reported by the C002 checklist.

    Both modules emit an E202-family issue per uncovered required metric.
    The checklist version is authoritative (it owns ``check_name`` semantics
    and human-confirmation flags), so matching Critic copies are dropped.
    Matching relies on the stable ``required metric {metric_id}`` message
    anchor shared by both emitters; if either message ever changes, this
    degrades to duplicate lines rather than lost information.
    """

    def metric_of(issue: ValidationIssue) -> str | None:
        match = _REQUIRED_METRIC_RE.search(issue.message)
        return match.group(1) if match else None

    already_reported = {
        metric
        for issue in industry_issues
        if (metric := metric_of(issue)) is not None
    }
    return [
        issue
        for issue in critic_issues
        if not (
            issue.issue_type == "required_metric_missing"
            and metric_of(issue) in already_reported
        )
    ]


def _resolve_output_paths(request: ResearchRequest) -> tuple[Path, Path, Path]:
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

    report_path = output_dir / "report.json"
    metadata_path = outputs_root / "logs" / request.run_id / "run_metadata.json"
    return report_path, report_path.with_suffix(".md"), metadata_path


def _write_outputs(
    *,
    request: ResearchRequest,
    report: ResearchReport,
    metadata: RunMetadata,
) -> tuple[Path, Path, Path]:
    report_path, markdown_path, metadata_path = _resolve_output_paths(request)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path, markdown_path, metadata_path


_MANIFEST_CODE_RE = re.compile(r"^E\d+ (\S+) ")


def _manifest_blocked_documents(
    documents: list[SourceDocument],
    manifest_issues: list[ValidationIssue],
) -> list[SourceDocument]:
    """Drop documents flagged by error/critical manifest validation issues.

    ADAPT-001: validation issues are never dropped; warning/info stay
    informational while error/critical keep their document out of the time
    lock and everything downstream. Issue messages open with a stable
    ``E1xx {doc_id} `` anchor emitted by ingestion.
    """

    blocked_ids = {
        match.group(1)
        for issue in manifest_issues
        if issue.severity in MANIFEST_BLOCKING_SEVERITIES
        and (match := _MANIFEST_CODE_RE.match(issue.message))
    }
    known_ids = {document.doc_id for document in documents}
    return [
        document
        for document in documents
        if document.doc_id not in blocked_ids & known_ids
    ]


def _compute_input_hashes(request: ResearchRequest) -> dict[str, str]:
    """Return stable request and manifest hashes for RunMetadata."""

    request_hash = hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    manifest_path = Path(request.source_manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "request": f"sha256:{request_hash}",
        "manifest": f"sha256:{manifest_hash}",
    }


def _write_failed_metadata(
    request: ResearchRequest,
    started_at: datetime,
    error: Exception,
    model_provider: ModelProvider | None,
) -> None:
    """Persist a failed RunMetadata audit record before re-raising."""

    _, _, metadata_path = _resolve_output_paths(request)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    if model_provider is None:
        model_provider_name = "rule-engine"
        model_name = "a008-rules"
        prompt_versions: dict[str, str] = {}
        agents_version = "v1-aggregation"
        model_version = "v1-provider"
    else:
        model_provider_name = model_provider.config.provider_name
        model_name = model_provider.config.model_name
        prompt_versions = get_prompt_versions()
        agents_version = "v1-llm"
        model_version = "v1-transport"

    metadata = RunMetadata(
        run_id=request.run_id,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        status="failed",
        model_provider=model_provider_name,
        model_name=model_name,
        prompt_versions=prompt_versions,
        input_hashes=_compute_input_hashes(request),
        module_versions={
            "orchestrator": "v1-a008",
            "validators": "v1-a002",
            "ingestion": "v1-b-merged",
            "industry": "v1-c-merged",
            "agents": agents_version,
            "model": model_version,
        },
        errors=[str(error)],
    )
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_pipeline(
    request: ResearchRequest,
    *,
    manifest_loader: ManifestLoader | None = None,
    text_extractor: TextExtractor | None = None,
    industry_loader: IndustryLoader | None = None,
    model_provider: ModelProvider | None = None,
) -> ResearchState:
    """Run the research pipeline over real B/C modules and persist outputs."""

    started_at = datetime.now(timezone.utc)
    state = ResearchState(request=request)
    resolve_manifest = manifest_loader or load_manifest
    resolve_industry = industry_loader or load_industry_config

    state.documents = resolve_manifest(request.source_manifest_path)
    manifest_issues = validate_manifest(state.documents)
    state.validation_issues.extend(manifest_issues)
    state.documents = _manifest_blocked_documents(state.documents, manifest_issues)

    state.documents, time_lock_issues = apply_time_lock(
        state.documents,
        request.cutoff_date,
    )
    state.validation_issues.extend(time_lock_issues)

    extract_text = text_extractor or _extract_document_text
    for document in state.documents:
        state.chunks.extend(extract_text(document))
    state.chunks = chunk_text(state.chunks, CHUNK_MAX_CHARS)

    state.config = resolve_industry(request.industry_id)

    located = _locate_config_evidence(
        chunks=state.chunks,
        config=state.config,
        documents=state.documents,
    )
    state.evidence, policy_issues = apply_evidence_policy(
        located,
        state.documents,
        request=request,
    )
    state.validation_issues.extend(policy_issues)

    try:
        state.claims = run_analysis(
            request,
            state.evidence,
            state.config,
            documents=state.documents,
            provider=model_provider,
        )

        industry_issues = [
            *check_required_metrics(state.evidence, state.config, documents=state.documents),
            *apply_metric_rules(state.evidence, state.config, documents=state.documents),
        ]
        state.validation_issues.extend(industry_issues)

        critic_issues = run_critic(request, state.claims, state.evidence, state.config)
        if model_provider is not None:
            critic_issues = [
                *critic_issues,
                *run_critic_llm(
                    model_provider,
                    request,
                    state.claims,
                    state.evidence,
                    state.config,
                ),
            ]
        state.validation_issues.extend(_drop_duplicated_metric_issues(critic_issues, industry_issues))
    except ModelProviderError as exc:
        _write_failed_metadata(request, started_at, exc, model_provider)
        raise

    generated_at = datetime.now(timezone.utc)
    state.report = render_report(request, state.claims, state.evidence, state.validation_issues)

    input_hashes = _compute_input_hashes(request)

    if model_provider is None:
        model_provider_name = "rule-engine"
        model_name = "a008-rules"
        prompt_versions: dict[str, str] = {}
        agents_version = "v1-aggregation"
        model_version = "v1-provider"
    else:
        model_provider_name = model_provider.config.provider_name
        model_name = model_provider.config.model_name
        prompt_versions = get_prompt_versions()
        agents_version = "v1-llm"
        model_version = "v1-transport"

    state.metadata = RunMetadata(
        run_id=request.run_id,
        started_at=started_at,
        finished_at=generated_at,
        status="success",
        model_provider=model_provider_name,
        model_name=model_name,
        prompt_versions=prompt_versions,
        input_hashes=input_hashes,
        module_versions={
            "orchestrator": "v1-a008",
            "validators": "v1-a002",
            "ingestion": "v1-b-merged",
            "industry": "v1-c-merged",
            "agents": agents_version,
            "model": model_version,
        },
        errors=[],
    )
    _write_outputs(request=request, report=state.report, metadata=state.metadata)
    return state
