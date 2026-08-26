"""Tests for the B-006 source packages.

These tests read the actual manifests and PDFs shipped under data/ and
fixtures/synthetic, so they catch regressions in layout (text overflowing the
page) and in source classification (synthetic data must never be formal).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.ingestion import load_manifest, validate_manifest

ROOT = Path(__file__).parents[2]
DATA_MANIFESTS = [ROOT / "data" / "manifests" / "food_case.csv",
                  ROOT / "data" / "manifests" / "bank_case.csv"]
SYNTHETIC_MANIFEST = ROOT / "fixtures" / "synthetic" / "synthetic_manifest.csv"

# A4 page width is 595.28pt; right margin is 10mm (~28.35pt).
RIGHT_MARGIN_PT = 28.35


def _all_package_pdfs() -> list[Path]:
    return sorted(
        (ROOT / "data" / "raw").rglob("*.pdf")
    ) + sorted((ROOT / "fixtures" / "synthetic").rglob("*.pdf"))


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


def test_data_manifests_contain_no_formal_sources() -> None:
    # Synthetic sources must never be classified as formal/background; real
    # formal sources are filled in manually by B after human verification.
    for manifest in DATA_MANIFESTS:
        documents = load_manifest(str(manifest))
        formal = [d.doc_id for d in documents if d.review_status in ("formal", "background")]
        assert not formal, f"{manifest} 不应包含 formal/background 合成资料: {formal}"


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
