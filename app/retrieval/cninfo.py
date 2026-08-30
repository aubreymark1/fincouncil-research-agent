"""Small adapter for the public CNINFO announcement search endpoint."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Mapping

from app.schemas import SearchHit, SearchQuery


CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_HOSTS = {"www.cninfo.com.cn", "static.cninfo.com.cn"}


def _parse_date(value: Any) -> date:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).date()
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"CNINFO announcement has invalid date: {value!r}") from exc


def _source_type(title: str, announcement_type: str) -> str:
    text = f"{title} {announcement_type}"
    if "年度报告" in text or "年报" in text:
        return "annual_report"
    if "半年度" in text or "半年报" in text:
        return "interim_report"
    if "政策" in text or "监管" in text:
        return "regulation"
    return "announcement"


def _strip_markup(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def _source_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://static.cninfo.com.cn/{value.lstrip('/')}"


def parse_cninfo_results(payload: Mapping[str, Any]) -> list[SearchHit]:
    rows = payload.get("announcements", [])
    if not isinstance(rows, list):
        return []
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        title = _strip_markup(row.get("announcementTitle") or row.get("title"))
        adjunct = str(row.get("adjunctUrl") or row.get("source_url") or "").strip()
        if not title or not adjunct:
            continue
        url = _source_url(adjunct)
        if url in seen:
            continue
        seen.add(url)
        hits.append(
            SearchHit(
                title=title,
                source_url=url,
                publisher="巨潮资讯",
                published_at=_parse_date(row.get("announcementTime") or row.get("published_at")),
                source_type=_source_type(title, str(row.get("announcementType") or "")),
            )
        )
    return hits


class CninfoConnector:
    """Search CNINFO and return normalized authoritative document hits."""

    def __init__(self, *, search_url: str = CNINFO_SEARCH_URL, timeout_seconds: float = 20.0) -> None:
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds

    def search_filings(self, query: SearchQuery) -> list[SearchHit]:
        start = query.start_date.isoformat() if query.start_date else "2000-01-01"
        params = {
            "pageNum": "1",
            "pageSize": "30",
            "tabName": "fulltext",
            "column": "sse",
            "stock": "",
            # CNINFO full-text search behaves like an AND query. Keep the
            # discovery key to the company identity; the research question is
            # applied later when the LLM inspects Evidence.
            "searchkey": (query.ticker or query.subject).strip(),
            "category": "",
            "seDate": f"{start}~{query.end_date.isoformat()}",
            "isHLtitle": "true",
        }
        body = urllib.parse.urlencode(params).encode("utf-8")
        request = urllib.request.Request(
            self.search_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "User-Agent": "FinCouncil/0.2"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"CNINFO search failed: {type(exc).__name__}") from exc
        if not isinstance(payload, Mapping):
            raise RuntimeError("CNINFO search returned a non-object response")
        return [hit for hit in parse_cninfo_results(payload) if hit.published_at <= query.end_date]
