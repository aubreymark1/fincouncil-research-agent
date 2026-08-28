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
from typing import Any, Literal

from app.agents import (
    get_prompt_versions,
    render_markdown,
    render_report,
    run_critic,
    run_critic_llm,
)
from app.agents.compact import get_compact_prompt_version
from app.agents.aggregation import run_analysis
from app.agents.generic import build_raw_evidence, run_generic_analysis
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
from .modes import EXPERIMENT_MODES, normalize_mode
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
    mode: str,
) -> None:
    """Persist a failed RunMetadata audit record before re-raising."""

    _, _, metadata_path = _resolve_output_paths(request)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    if model_provider is None:
        model_provider_name = "rule-engine" if mode == "rule-engine" else "not-configured"
        model_name = "a008-rules" if mode == "rule-engine" else "none"
        prompt_versions: dict[str, str] = {}
        agents_version = "v1-aggregation" if mode == "rule-engine" else "v1-generic"
        model_version = "v1-provider"
        cache_version = "none"
    else:
        model_provider_name = model_provider.config.provider_name
        model_name = model_provider.config.model_name
        if mode in {"E1", "E2"}:
            prompt_versions = {"generic": "v1"}
            agents_version = "v1-generic"
        else:
            prompt_versions = get_prompt_versions()
            agents_version = "v1-llm"
        model_version = "v1-transport"
        cache_version = model_provider.cache_version

    metadata = RunMetadata(
        run_id=request.run_id,
        mode=mode,
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
            "cache": cache_version,
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
    mode: str = "rule-engine",
    llm_strategy: Literal["full", "compact"] = "full",
    progress_callback: Callable[[str], None] | None = None,
) -> ResearchState:
    """Run the research pipeline over real B/C modules and persist outputs.

    ``mode`` selects the frozen E1/E2/E3 experiment behaviour or the default
    ``rule-engine`` chain. E1/E2/E3 require a ``ModelProvider`` so the CLI can
    never silently substitute deterministic rules for an experiment run.
    ``progress_callback`` is optional and emits real stage labels without
    altering any pipeline behaviour.
    """

    def _emit(stage: str) -> None:
        if progress_callback is not None:
            progress_callback(stage)

    started_at = datetime.now(timezone.utc)
    mode = normalize_mode(mode)
    if mode in EXPERIMENT_MODES and model_provider is None:
        exc = ModelProviderError(
            f"E300 module=orchestrator: mode {mode} requires a model provider; "
            "refusing to fake an experiment with the rule-engine"
        )
        _write_failed_metadata(request, started_at, exc, None, mode)
        raise exc

    _emit("准备研究请求")

    state = ResearchState(request=request, mode=mode)
    resolve_manifest = manifest_loader or load_manifest
    resolve_industry = industry_loader or load_industry_config

    state.documents = resolve_manifest(request.source_manifest_path)
    manifest_issues = validate_manifest(state.documents)
    state.validation_issues.extend(manifest_issues)
    state.documents = _manifest_blocked_documents(state.documents, manifest_issues)
    _emit("校验资料清单")

    extract_text = text_extractor or _extract_document_text

    if mode in {"E1", "E2"}:
        # E1/E2 intentionally skip the formal time-lock and evidence chain.
        # E1 is a generic agent with no industry configuration; E2 adds the
        # loaded industry configuration as context only.
        # Red-team and rejected material is never fed to the generic agent.
        state.documents = [
            document
            for document in state.documents
            if document.review_status not in {"red_team", "rejected"}
        ]
        for document in state.documents:
            state.chunks.extend(extract_text(document))
        state.chunks = chunk_text(state.chunks, CHUNK_MAX_CHARS)
        _emit("解析原始资料")

        if mode == "E2":
            state.config = resolve_industry(request.industry_id)

        state.evidence, raw_issues = build_raw_evidence(
            state.chunks,
            state.documents,
        )
        state.validation_issues.extend(raw_issues)
        _emit("定位证据")

        try:
            state.claims = run_generic_analysis(
                model_provider,
                request,
                state.evidence,
                config=state.config,
            )
        except ModelProviderError as exc:
            _write_failed_metadata(request, started_at, exc, model_provider, mode)
            raise
        _emit("生成分析结论")

        generated_at = datetime.now(timezone.utc)
        state.report = render_report(
            request,
            state.claims,
            state.evidence,
            state.validation_issues,
        )
    else:
        # rule-engine and E3 share the full formal chain. rule-engine may run
        # without a model provider; E3 is the full-system experiment mode and
        # therefore requires one (enforced above).
        state.documents, time_lock_issues = apply_time_lock(
            state.documents,
            request.cutoff_date,
        )
        state.validation_issues.extend(time_lock_issues)
        _emit("执行时间过滤")

        for document in state.documents:
            state.chunks.extend(extract_text(document))
        state.chunks = chunk_text(state.chunks, CHUNK_MAX_CHARS)
        _emit("解析原始资料")

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
        _emit("定位证据")

        try:
            state.claims = run_analysis(
                request,
                state.evidence,
                state.config,
                documents=state.documents,
                provider=model_provider,
                llm_strategy=llm_strategy,
            )
            _emit("生成分析结论")

            industry_issues = [
                *check_required_metrics(state.evidence, state.config, documents=state.documents),
                *apply_metric_rules(state.evidence, state.config, documents=state.documents),
            ]
            state.validation_issues.extend(industry_issues)

            critic_issues = run_critic(request, state.claims, state.evidence, state.config)
            if model_provider is not None and llm_strategy == "full":
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
            state.validation_issues.extend(
                _drop_duplicated_metric_issues(critic_issues, industry_issues)
            )
            _emit("执行 Critic 审查")
        except ModelProviderError as exc:
            _write_failed_metadata(request, started_at, exc, model_provider, mode)
            raise

        generated_at = datetime.now(timezone.utc)
        state.report = render_report(
            request,
            state.claims,
            state.evidence,
            state.validation_issues,
        )

    input_hashes = _compute_input_hashes(request)

    if model_provider is None:
        model_provider_name = "rule-engine"
        model_name = "a008-rules"
        prompt_versions: dict[str, str] = {}
        agents_version = "v1-aggregation"
        model_version = "v1-provider"
        cache_version = "none"
    else:
        model_provider_name = model_provider.config.provider_name
        model_name = model_provider.config.model_name
        if mode in {"E1", "E2"}:
            prompt_versions = {"generic": "v1"}
            agents_version = "v1-generic"
        elif llm_strategy == "compact":
            prompt_versions = {"synthesis": get_compact_prompt_version()}
            agents_version = "v1-llm-compact"
        else:
            prompt_versions = get_prompt_versions()
            agents_version = "v1-llm"
        model_version = "v1-transport"
        cache_version = model_provider.cache_version

    state.metadata = RunMetadata(
        run_id=request.run_id,
        mode=mode,
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
            "cache": cache_version,
        },
        errors=[],
    )
    _write_outputs(request=request, report=state.report, metadata=state.metadata)
    _emit("写入报告产物")
    _emit("研究完成")
    return state
