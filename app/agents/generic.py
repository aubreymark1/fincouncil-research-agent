"""Generic LLM agent used by E1/E2 experiment modes.

E1 is a generic agent with no industry configuration. E2 is the same generic
agent with the loaded ``IndustryConfig`` passed as context. Both modes are
experimental: they intentionally do not run the formal time-lock / evidence /
Critic chain, so their raw evidence remains ``pending`` and is never presented
as verified by the report renderer.

Generic-agent output is batched like the industry LLM nodes. Because the raw
evidence is never verified, any claim the model marks ``pass`` is demoted to
``review`` before it can enter a report: pending evidence must not generate
formal pass conclusions.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.llm import (
    ClaimList,
    _merge_claims,
    _repair_batch_claims,
    _split_evidence_batches,
)
from app.model import ModelProvider, ModelProviderError
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchRequest,
    SourceDocument,
    TextChunk,
    ValidationIssue,
)

GENERIC_PROMPT = """你是一名通用投研分析 Agent。请基于输入资料生成结构化 Claim 列表。

要求：
- claim_type 只能是 fact、change、analysis、risk、unresolved；
- 非 unresolved 的 claim 必须引用输入中存在的 evidence_id；
- risk 类型的 claim 必须填写 risk_severity，且只能引用支持该风险的证据；
- 不编造输入中不存在的数字、日期或事实；
- 无法确认的内容输出为 unresolved；
- 输出必须是 JSON 对象，包含 claims 数组。
"""


def build_raw_evidence(
    chunks: list[TextChunk],
    documents: list[SourceDocument],
) -> tuple[list[Evidence], list[ValidationIssue]]:
    """Build honest pending Evidence from raw chunks for E1/E2.

    The returned evidence is intentionally ``pending``: E1/E2 do not run the
    formal evidence-verification policy, so the report renderer will not place
    these items in the verified evidence index. Chunks whose source document
    has no publication date are skipped with an explicit ValidationIssue.
    """

    documents_by_id = {document.doc_id: document for document in documents}
    evidence: list[Evidence] = []
    issues: list[ValidationIssue] = []

    for chunk in chunks:
        document = documents_by_id.get(chunk.doc_id)
        if document is None or document.published_at is None:
            issues.append(
                ValidationIssue(
                    issue_id=f"ISSUE-GENERIC-{chunk.chunk_id}",
                    check_name="generic_evidence_builder",
                    severity="warning",
                    issue_type="generic_evidence_skipped",
                    message=(
                        f"E102 {chunk.chunk_id} was skipped for the generic "
                        "agent because its source document lacks published_at."
                    ),
                    claim_id=None,
                    evidence_id=None,
                    report_section="source_filter",
                    rerun_required=False,
                    human_confirmation_required=True,
                    status="open",
                )
            )
            continue

        evidence.append(
            Evidence(
                evidence_id=f"EV-RAW-{chunk.chunk_id.removeprefix('CHUNK-')}",
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                fact_text=chunk.text,
                quote=chunk.text,
                published_at=document.published_at,
                page=chunk.page,
                section=chunk.section,
                locator=(
                    f"{document.doc_id}:{chunk.chunk_id}:"
                    f"p{chunk.page if chunk.page is not None else 'unknown'}"
                ),
                company_name=document.company_name,
                industry_id=document.industry_id,
                evidence_type="other",
                confidence=0.5,
                review_status="pending",
            )
        )

    return evidence, issues


def _validate_generic_claims(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> None:
    """Reject structurally unsafe generic-agent output."""

    for claim in claims:
        if claim.status not in {"pass", "review"}:
            raise ModelProviderError(
                f"E301 module=agents.generic: claim {claim.claim_id} has "
                f"status={claim.status!r}; expected pass or review"
            )
        missing = [
            evidence_id
            for evidence_id in claim.evidence_ids
            if evidence_id not in evidence_by_id
        ]
        if missing:
            raise ModelProviderError(
                f"E301 module=agents.generic: claim {claim.claim_id} referenced "
                f"unknown evidence IDs: {missing}"
            )


def _demote_pending_evidence_claims(
    claims: list[Claim],
    evidence_by_id: dict[str, Evidence],
) -> list[Claim]:
    """Demote pass Claims that rely on pending/unverified evidence to review.

    E1/E2 intentionally do not run the verification policy, so every raw
    evidence item is pending. A formal ``pass`` conclusion must never be
    generated from pending evidence.
    """

    demoted: list[Claim] = []
    for claim in claims:
        if claim.status == "pass" and any(
            evidence_by_id.get(evidence_id) is None
            or evidence_by_id[evidence_id].review_status != "verified"
            for evidence_id in claim.evidence_ids
        ):
            claim = claim.model_copy(update={"status": "review"})
        demoted.append(claim)
    return demoted


def run_generic_analysis(
    provider: ModelProvider,
    request: ResearchRequest,
    evidence: list[Evidence],
    *,
    config: IndustryConfig | None = None,
) -> list[Claim]:
    """Run the generic LLM agent over raw pending evidence with batching.

    E1 passes ``config=None``; E2 passes the loaded industry configuration so
    the prompt can include industry-specific context while still using the same
    generic analysis instruction. Evidence is split into prompt-sized batches
    and duplicate claims are merged conservatively.
    """

    evidence_by_id = {item.evidence_id: item for item in evidence}
    batches = _split_evidence_batches(evidence)
    raw_claims: list[Claim] = []

    for batch_index, batch in enumerate(batches, start=1):
        context: dict[str, Any] = {
            "request": request.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in batch],
            "config": config.model_dump(mode="json") if config is not None else None,
            "batch_index": batch_index,
            "total_batches": len(batches),
        }
        prompt = (
            f"{GENERIC_PROMPT}\n\n## 输入数据\n```json\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}\n```\n"
        )

        result = provider.generate_json(prompt, response_model=ClaimList)
        if not isinstance(result, ClaimList):
            raise TypeError("E301 module=agents.generic: expected ClaimList response")

        batch_evidence_by_id = {item.evidence_id: item for item in batch}
        raw_claims.extend(
            _repair_batch_claims(
                provider,
                "generic",
                prompt,
                result,
                batch_evidence_by_id,
            )
        )

    claims = _merge_claims(raw_claims)
    _validate_generic_claims(claims, evidence_by_id)
    return _demote_pending_evidence_claims(claims, evidence_by_id)
