import { useState } from "react";
import type { Evidence } from "../types";

interface CitationPopoverProps {
  evidence: Evidence[];
  onOpenEvidence: (evidence: Evidence) => void;
}

function evidenceLabel(item: Evidence): string {
  return `${item.doc_id}${item.page ? ` · 第 ${item.page} 页` : ""}`;
}

export function CitationPopover({ evidence, onOpenEvidence }: CitationPopoverProps) {
  const [open, setOpen] = useState(false);
  if (evidence.length === 0) return null;

  const primary = evidence[0];

  return (
    <span className="citation-wrap" onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="citation-trigger"
        aria-label={`查看 ${evidence.length} 条句子来源`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        onFocus={() => setOpen(true)}
      >
        [{evidence.length > 1 ? `+${evidence.length}` : "1"}]
      </button>
      {open && (
        <span className="citation-popover" role="dialog" aria-label="句子来源">
          <span className="citation-popover-title">来源</span>
          <span className="citation-popover-source">{evidenceLabel(primary)}</span>
          <span className="citation-popover-quote">“{primary.quote}”</span>
          <span className="citation-popover-meta">
            发布于 {primary.published_at} · {primary.review_status === "verified" ? "已验证" : "待复核"}
          </span>
          <button type="button" className="citation-open" onClick={() => onOpenEvidence(primary)}>
            查看原文详情
          </button>
          {evidence.length > 1 && <span className="citation-more">还有 {evidence.length - 1} 条关联来源</span>}
        </span>
      )}
    </span>
  );
}
