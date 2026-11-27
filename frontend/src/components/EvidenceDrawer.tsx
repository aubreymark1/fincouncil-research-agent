import { useEffect } from "react";
import type { Evidence } from "../types";

interface EvidenceDrawerProps {
  evidence: Evidence | null;
  onClose: () => void;
}

function reviewStatusLabel(status: Evidence["review_status"]): string {
  switch (status) {
    case "verified":
      return "已核验原文";
    case "pending":
      return "待人工复核";
    case "rejected":
      return "已驳回";
  }
}

export function EvidenceDrawer({ evidence, onClose }: EvidenceDrawerProps) {
  useEffect(() => {
    if (!evidence) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [evidence, onClose]);

  if (!evidence) return null;

  const confidencePct = Math.max(
    0,
    Math.min(100, Math.round(evidence.confidence * 100))
  );

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="evidence-drawer"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="证据溯源详情"
      >
        <div className="drawer-header">
          <div>
            <h2>证据链溯源核验</h2>
            <span className="drawer-subtitle mono">{evidence.evidence_id}</span>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="关闭抽屉"
          >
            ✕
          </button>
        </div>

        <div className="drawer-status-strip">
          <span className={`review-badge ${evidence.review_status}`}>
            {reviewStatusLabel(evidence.review_status)}
          </span>
          <span className="drawer-conf-pill mono">
            匹配置信度 {confidencePct}%
          </span>
        </div>

        <div className="drawer-quote-card">
          <div className="drawer-quote-head">
            <span>原文摘录</span>
            <span className="mono">
              {evidence.doc_id}
              {evidence.page !== null ? ` · 第 ${evidence.page} 页` : ""}
            </span>
          </div>
          <blockquote className="drawer-quote">{evidence.quote}</blockquote>
          {evidence.section && (
            <div className="drawer-quote-foot">章节定位：{evidence.section}</div>
          )}
        </div>

        {evidence.fact_text && evidence.fact_text !== evidence.quote && (
          <div className="drawer-fact-card">
            <span className="drawer-sub-label">抽取事实陈述</span>
            <p>{evidence.fact_text}</p>
          </div>
        )}

        <dl className="evidence-detail">
          <div className="detail-row">
            <dt>发布日期</dt>
            <dd className="mono">{evidence.published_at}</dd>
          </div>
          <div className="detail-row">
            <dt>文档 ID</dt>
            <dd>
              <code className="mono">{evidence.doc_id}</code>
            </dd>
          </div>
          <div className="detail-row">
            <dt>文本块 ID</dt>
            <dd>
              <code className="mono">{evidence.chunk_id}</code>
            </dd>
          </div>
          <div className="detail-row">
            <dt>精准定位</dt>
            <dd className="mono">{evidence.locator}</dd>
          </div>
          <div className="detail-row">
            <dt>页码</dt>
            <dd className="mono">{evidence.page ?? "未提供"}</dd>
          </div>
          <div className="detail-row">
            <dt>证据类型</dt>
            <dd>{evidence.evidence_type}</dd>
          </div>
          {evidence.company_name && (
            <div className="detail-row">
              <dt>关联标的</dt>
              <dd>{evidence.company_name}</dd>
            </div>
          )}
          {evidence.industry_id && (
            <div className="detail-row">
              <dt>行业分类</dt>
              <dd className="mono">{evidence.industry_id}</dd>
            </div>
          )}
        </dl>
      </aside>
    </div>
  );
}
