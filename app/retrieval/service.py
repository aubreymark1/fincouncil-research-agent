"""Download normalized search hits and build a pipeline-compatible manifest."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import RetrievedDocument, SearchHit, SearchQuery

from .cninfo import CNINFO_STATIC_HOSTS, CninfoConnector
from .security import validate_public_url


Downloader = Callable[[SearchHit, Path], Path]


def _default_downloader(hit: SearchHit, destination: Path) -> Path:
    validate_public_url(str(hit.source_url), allowed_hosts=CNINFO_STATIC_HOSTS)
    request = urllib.request.Request(str(hit.source_url), headers={"User-Agent": "FinCouncil/0.2"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(30 * 1024 * 1024 + 1)
    if len(data) > 30 * 1024 * 1024:
        raise ValueError("retrieved document exceeds 30 MB")
    destination.write_bytes(data)
    return destination


class RetrievalService:
    def __init__(self, outputs_dir: Path, *, connector: Any | None = None, downloader: Downloader | None = None) -> None:
        self.outputs_dir = Path(outputs_dir)
        self.connector = connector or CninfoConnector()
        self.downloader = downloader or _default_downloader

    def prepare_manifest(self, run_id: str, query: SearchQuery) -> tuple[Path, list[RetrievedDocument]]:
        hits = self.connector.search_filings(query)
        run_dir = self.outputs_dir / "retrieval" / run_id
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        documents: list[RetrievedDocument] = []
        records: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        for index, hit in enumerate(hits[:30], start=1):
            safe_name = f"DOC-ONLINE-{index:03d}.pdf"
            path = self.downloader(hit, raw_dir / safe_name)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            downloaded_at = datetime.now(timezone.utc)
            document = RetrievedDocument(
                **hit.model_dump(),
                downloaded_at=downloaded_at,
                sha256=digest,
                local_path=str(path),
                review_status="verified",
            )
            documents.append(document)
            records.append({
                "doc_id": f"DOC-ONLINE-{index:03d}",
                "title": hit.title,
                "source_type": hit.source_type,
                "publisher": hit.publisher,
                "source_url": str(hit.source_url),
                "local_path": str(path),
                "published_at": hit.published_at.isoformat(),
                "event_date": hit.published_at.isoformat(),
                "retrieved_at": downloaded_at.isoformat(),
                "company_name": query.subject,
                "trust_level": 5,
                "review_status": "formal",
            })
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest_path, documents
