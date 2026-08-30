import { useEffect } from "react";
import type { Evidence } from "../types";

interface EvidenceDrawerProps {
  evidence: Evidence | null;
  onClose: () => void;
}

export function EvidenceDrawer({ evidence, onClose }: EvidenceDrawerProps) {
  useEffect(() => {
    if (!evidence) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [evidence, onClose]);

  if (!evidence) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="evidence-drawer"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="证据详情"
      >
        <div className="drawer-header">
          <h2>证据详情</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭证据详情">
            ✕
          </button>
        </div>

        <dl className="evidence-detail">
          <dt>Evidence ID</dt>
          <dd>
            <code>{evidence.evidence_id}</code>
          </dd>
          <dt>文档 ID</dt>
          <dd>
            <code>{evidence.doc_id}</code>
          </dd>
          <dt>原文引用</dt>
          <dd className="quote">{evidence.quote}</dd>
          <dt>定位</dt>
          <dd>{evidence.locator}</dd>
          <dt>发布日期</dt>
          <dd>{evidence.published_at}</dd>
          <dt>页码</dt>
          <dd>{evidence.page ?? "未提供"}</dd>
          <dt>章节</dt>
          <dd>{evidence.section ?? "未提供"}</dd>
        <dt>审核状态</dt>
        <dd>
          <span className={`review-badge ${evidence.review_status}`}>
              {evidence.review_status === "verified" ? "已验证" : evidence.review_status === "pending" ? "待确认" : "已拒绝"}
          </span>
        </dd>
          <dt>证据类型</dt>
          <dd>{evidence.evidence_type}</dd>
          <dt>置信度</dt>
          <dd>{evidence.confidence.toFixed(2)}</dd>
        </dl>
      </aside>
    </div>
  );
}
