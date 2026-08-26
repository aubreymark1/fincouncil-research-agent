"""Tests for B-003 HTML text extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion import HtmlExtractionError, extract_html
from app.schemas import SourceDocument


ROOT = Path(__file__).parents[2]
SAMPLE_HTML = ROOT / "fixtures" / "sources" / "sample_article.html"


def _document(local_path: str) -> SourceDocument:
    return SourceDocument(
        doc_id="DOC-HTML-001",
        title="示例文章",
        source_type="news",
        publisher="示例媒体",
        source_url=None,
        local_path=local_path,
        published_at="2026-04-20",
        event_date=None,
        retrieved_at="2026-08-26T12:00:00+08:00",
        company_name=None,
        industry_id="food_beverage",
        trust_level=3,
        content_hash="sha256:html-fixture",
        review_status="background",
    )


def _text(chunks) -> str:
    return "\n".join(c.text for c in chunks)


def test_extract_html_removes_non_content() -> None:
    chunks = extract_html(_document(str(SAMPLE_HTML)))

    text = _text(chunks)
    assert "console.log" not in text, "script 内容应被移除"
    assert "font-family" not in text, "style 内容应被移除"
    assert "首页" not in text, "nav 导航应被移除"
    assert "版权声明" not in text, "footer 应被移除"
    assert "相关阅读" not in text, "aside 应被移除"


def test_extract_html_preserves_headings_and_body() -> None:
    chunks = extract_html(_document(str(SAMPLE_HTML)))

    text = _text(chunks)
    assert "食品饮料行业消费升级趋势明显" in text, "h1 标题应保留"
    assert "健康化产品需求增长" in text, "h2 标题应保留"
    assert "消费者对低糖、低脂食品的偏好持续上升" in text, "正文应保留"


def test_extract_html_headings_become_sections() -> None:
    chunks = extract_html(_document(str(SAMPLE_HTML)))

    # 找到正文第一段，其 section 应为 h2 标题
    body = [c for c in chunks if "消费者对低糖" in c.text]
    assert body
    assert body[0].section == "健康化产品需求增长"


def test_extract_html_preserves_paragraph_order() -> None:
    chunks = extract_html(_document(str(SAMPLE_HTML)))

    indexes = [c.paragraph_index for c in chunks]
    assert indexes == sorted(indexes), "paragraph_index 应递增"
    assert indexes[0] == 0


def test_extract_html_does_not_guess_event_date() -> None:
    chunks = extract_html(_document(str(SAMPLE_HTML)))

    # 提取只返回文本，不产生日期字段；发布日期作为普通文本保留但不解析
    text = _text(chunks)
    assert "2026 年 4 月 20 日" in text
    for chunk in chunks:
        assert chunk.page is None, "HTML 无页码"


def test_missing_html_raises_e100() -> None:
    with pytest.raises(HtmlExtractionError) as exc_info:
        extract_html(_document("data/raw/food_beverage/does_not_exist.html"))

    assert exc_info.value.code == "E100"


def test_html_without_body_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty.html"
    empty.write_text(
        "<html><head><title>empty</title></head>"
        "<body><script>var x=1;</script></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(HtmlExtractionError) as exc_info:
        extract_html(_document(str(empty)))

    assert exc_info.value.code == "E100"
    assert "no extractable body text" in exc_info.value.message
