"""Tests for the B-006 source packages.

These tests read the actual manifests and PDFs shipped under data/ and
fixtures/synthetic, so they catch regressions in layout (text overflowing the
page) and in source classification (synthetic data must never be formal).
"""

from __future__ import annotations

import gc
from pathlib import Path

from pypdf import PdfReader

import yaml

from app.ingestion import (
    chunk_text,
    extract_pdf,
    load_manifest,
    locate_evidence,
    validate_manifest,
)

ROOT = Path(__file__).parents[2]
DATA_MANIFESTS = [ROOT / "data" / "manifests" / "food_case.csv",
                  ROOT / "data" / "manifests" / "bank_case.csv"]
SYNTHETIC_MANIFEST = ROOT / "fixtures" / "synthetic" / "synthetic_manifest.csv"

# A4 page width is 595.28pt; right margin is 10mm (~28.35pt).
RIGHT_MARGIN_PT = 28.35


def _all_package_pdfs() -> list[Path]:
    """合成 PDF（fixtures/synthetic + data/raw 红蓝材料）。

    真实财报（文件名以股票代码数字开头）由爬虫下载、排版真实，页脚页码等
    元素 x 坐标天然靠右，不应套用"正文越界"检查。
    """
    pdfs = sorted((ROOT / "fixtures" / "synthetic").rglob("*.pdf"))
    for p in (ROOT / "data" / "raw").rglob("*.pdf"):
        if not p.name[0].isdigit():
            pdfs.append(p)
    return sorted(pdfs)


def test_package_pdfs_do_not_overflow_page() -> None:
    pdfs = _all_package_pdfs()
    assert pdfs, "expected at least one PDF in the source packages"

    for path in pdfs:
        reader = PdfReader(str(path))
        for page in reader.pages:
            width = float(page.mediabox.width)
            coords: list[tuple[float, str]] = []
            page.extract_text(
                visitor_text=lambda t, cm, tm, fd, fs: coords.append(
                    (float(tm[4]), t.strip())
                )
            )
            for x, text in coords:
                if not text:
                    continue
                assert x < width - RIGHT_MARGIN_PT, (
                    f"{path.relative_to(ROOT)} 文本起始 x={x:.1f} 越过右边距 "
                    f"(页宽 {width:.1f}, 右边界 {width - RIGHT_MARGIN_PT:.1f})"
                )


def test_data_manifests_load_and_validate_cleanly() -> None:
    for manifest in DATA_MANIFESTS:
        documents = load_manifest(str(manifest))
        assert documents, f"{manifest} 不应为空"
        issues = validate_manifest(documents)
        assert issues == [], f"{manifest} 存在校验问题: {issues}"


def _core_documents(manifest: Path) -> list:
    return [
        d for d in load_manifest(str(manifest))
        if d.review_status in ("formal", "background")
    ]


def test_data_manifests_contain_real_formal_sources() -> None:
    # data/manifests 的目标是容纳 B 人工核验后的真实 formal/background 来源，
    # 因此这里验收真实资料包的数量与可核验性，而非"无 formal 即通过"。
    food = _core_documents(DATA_MANIFESTS[0])
    bank = _core_documents(DATA_MANIFESTS[1])

    assert 8 <= len(food) <= 12, f"食品应有 8-12 份核心资料，当前 {len(food)} 份"
    assert 4 <= len(bank) <= 6, f"银行应有 4-6 份核心资料，当前 {len(bank)} 份"

    for doc in food + bank:
        assert doc.source_url and doc.source_url.startswith("http"), (
            f"{doc.doc_id} 缺可核验 source_url"
        )
        assert doc.published_at is not None, f"{doc.doc_id} 缺公开日期"
        assert doc.trust_level >= 3, f"{doc.doc_id} trust_level 过低({doc.trust_level})"
        local = Path(doc.local_path)
        if not local.is_absolute():
            local = ROOT / local
        assert local.is_file(), f"{doc.doc_id} 本地原始文件不存在: {doc.local_path}"


def test_synthetic_manifest_is_all_red_team() -> None:
    documents = load_manifest(str(SYNTHETIC_MANIFEST))
    assert documents
    for document in documents:
        assert document.review_status == "red_team", (
            f"{document.doc_id} 的 review_status 应为 red_team，"
            f"实际为 {document.review_status}"
        )
    issues = validate_manifest(documents)
    assert issues == [], f"synthetic manifest 存在校验问题: {issues}"


def _industry_keywords(industry_id: str) -> list[str]:
    # 取 C 配置前 2 个必选指标的全部关键词（含用词变体，如"净息差/净利息收益率"），
    # 既足以验证"能定位到证据"，又不会让 CI 过慢。
    config = "food_beverage" if industry_id == "food_beverage" else "banking"
    path = ROOT / "configs" / f"{config}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    keywords: list[str] = []
    for metric in data.get("required_metrics", [])[:2]:
        keywords.extend(metric.get("keywords", []))
    return keywords


def test_formal_sources_extract_and_locate() -> None:
    # A 要求：每个 formal PDF 都必须能 extract_pdf 且用行业关键词定位到证据，
    # 否则资料包不可声称"端到端可用"。
    for manifest in DATA_MANIFESTS:
        documents = load_manifest(str(manifest))
        for document in documents:
            if document.review_status not in ("formal", "background"):
                continue
            chunks = extract_pdf(document)
            chunks = chunk_text(chunks, max_chars=400)
            keywords = _industry_keywords(document.industry_id)
            evidence = locate_evidence(
                chunks, keywords, documents=[document], evidence_type="financial"
            )
            assert evidence, (
                f"{document.doc_id} extract_pdf 后无法用行业关键词定位到任何证据"
            )
            gc.collect()
