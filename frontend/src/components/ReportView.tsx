import { useMemo, useState } from "react";
import type { Claim, Evidence, ReportBlock, ResearchReport } from "../types";

interface ReportViewProps {
  report: ResearchReport;
  onSelectEvidence: (evidence: Evidence) => void;
}

type ReportTab =
  | "all"
  | "narrative"
  | "claims"
  | "risks"
  | "review"
  | "validation";

function industryLabel(industryId: string): string {
  if (industryId.includes("food")) return "食品饮料";
  if (industryId.includes("bank")) return "银行业";
  return industryId;
}

function statusText(status: Claim["status"]): string {
  switch (status) {
    case "pass":
      return "已通过";
    case "review":
      return "待复核";
    case "draft":
      return "草稿";
    case "reject":
      return "已驳回";
  }
}

function claimTypeText(claimType: Claim["claim_type"]): string {
  switch (claimType) {
    case "fact":
      return "事实依据";
    case "change":
      return "边际变化";
    case "analysis":
      return "逻辑分析";
    case "risk":
      return "风险因子";
    case "unresolved":
      return "未决事项";
  }
}

function severityText(severity: Claim["risk_severity"]): string {
  switch (severity) {
    case "high":
      return "高风险";
    case "medium":
      return "中风险";
    case "low":
      return "低风险";
    default:
      return "";
  }
}

function issueSeverityText(
  severity: "info" | "warning" | "error" | "critical"
): string {
  switch (severity) {
    case "critical":
      return "严重";
    case "error":
      return "错误";
    case "warning":
      return "警示";
    case "info":
      return "提示";
  }
}

function formatDateTime(value: string): string {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  const yyyy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  const hh = String(dt.getHours()).padStart(2, "0");
  const min = String(dt.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

function sourceSummary(evidence: Evidence | undefined): string {
  if (!evidence) return "缺失来源";
  const page = evidence.page ? ` · P.${evidence.page}` : "";
  return `${evidence.evidence_id} · ${evidence.doc_id}${page}`;
}

function SourceChipList({
  sources,
  emptyLabel,
  onSelectEvidence,
}: {
  sources: Evidence[];
  emptyLabel: string;
  onSelectEvidence: (evidence: Evidence) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? sources : sources.slice(0, 5);
  const hiddenCount = sources.length - visible.length;

  return (
    <div className="source-row">
      <span className="source-label">证据溯源</span>
      {sources.length === 0 ? (
        <span className="muted source-empty">{emptyLabel}</span>
      ) : (
        <>
          {visible.map((evidence) => (
            <button
              key={evidence.evidence_id}
              type="button"
              className={`source-chip ${evidence.review_status}`}
              onClick={() => onSelectEvidence(evidence)}
              title="点击查看原文引用与页码定位"
            >
              <span className="source-chip-dot" aria-hidden="true" />
              <span>{sourceSummary(evidence)}</span>
            </button>
          ))}
          {hiddenCount > 0 && (
            <button
              type="button"
              className="source-more-btn"
              onClick={() => setExpanded(true)}
            >
              +{hiddenCount} 条来源
            </button>
          )}
          {expanded && sources.length > 5 && (
            <button
              type="button"
              className="source-more-btn"
              onClick={() => setExpanded(false)}
            >
              收起
            </button>
          )}
        </>
      )}
    </div>
  );
}

function NarrativeBlock({
  block,
  index,
  evidenceMap,
  onSelectEvidence,
}: {
  block: ReportBlock;
  index: number;
  evidenceMap: Map<string, Evidence>;
  onSelectEvidence: (evidence: Evidence) => void;
}) {
  const sources = block.evidence_ids
    .map((id) => evidenceMap.get(id))
    .filter((item): item is Evidence => Boolean(item));

  return (
    <article className="narrative-block">
      <div className="narrative-head">
        <span className="narrative-index mono">
          {String(index + 1).padStart(2, "0")}
        </span>
        <h3>{block.section}</h3>
      </div>
      <p className="narrative-body">{block.text}</p>
      <SourceChipList
        sources={sources}
        emptyLabel="本节未绑定来源"
        onSelectEvidence={onSelectEvidence}
      />
    </article>
  );
}

function ClaimCard({
  claim,
  evidenceMap,
  onSelectEvidence,
}: {
  claim: Claim;
  evidenceMap: Map<string, Evidence>;
  onSelectEvidence: (evidence: Evidence) => void;
}) {
  const sources = claim.evidence_ids
    .map((id) => evidenceMap.get(id))
    .filter((item): item is Evidence => Boolean(item));

  const confidencePct = Math.max(
    0,
    Math.min(100, Math.round(claim.confidence * 100))
  );

  return (
    <article
      className={`claim-card ${
        claim.risk_severity ? `risk-${claim.risk_severity}` : ""
      }`}
    >
      <div className="claim-head">
        <div className="claim-head-left">
          <span className={`claim-status ${claim.status}`}>
            {statusText(claim.status)}
          </span>
          <span className="claim-type-tag">{claimTypeText(claim.claim_type)}</span>
          {claim.risk_severity && (
            <span className={`risk-severity ${claim.risk_severity}`}>
              {severityText(claim.risk_severity)}
            </span>
          )}
          <code className="claim-id mono">{claim.claim_id}</code>
        </div>

        <div className="confidence-meter" title={`置信度 ${claim.confidence.toFixed(2)}`}>
          <span className="confidence-label">置信度</span>
          <div className="confidence-bar">
            <div
              className="confidence-fill"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="confidence-val mono">{confidencePct}%</span>
        </div>
      </div>

      <p className="claim-text">{claim.text}</p>

      {claim.calculation && (
        <div className="calculation-box">
          <span className="calc-tag">口径 / 推算</span>
          <code className="mono">{claim.calculation}</code>
        </div>
      )}

      {claim.industry_metric_ids.length > 0 && (
        <div className="metric-tags">
          {claim.industry_metric_ids.map((metricId) => (
            <span key={metricId} className="metric-tag mono">
              #{metricId}
            </span>
          ))}
        </div>
      )}

      <SourceChipList
        sources={sources}
        emptyLabel="无直接证据引用"
        onSelectEvidence={onSelectEvidence}
      />
    </article>
  );
}

export function ReportView({ report, onSelectEvidence }: ReportViewProps) {
  const [activeTab, setActiveTab] = useState<ReportTab>("all");

  const evidenceMap = useMemo(
    () => new Map(report.evidence_index.map((item) => [item.evidence_id, item])),
    [report.evidence_index]
  );

  const formalClaims = report.claims.filter((claim) => claim.status === "pass");
  const formalRisks = report.risks.filter((claim) => claim.status === "pass");
  const reviewItems = [
    ...report.claims.filter((claim) => claim.status === "review"),
    ...report.risks.filter((claim) => claim.status === "review"),
  ];
  const narrative = report.narrative ?? [];

  const verifiedEvidenceCount = report.evidence_index.filter(
    (ev) => ev.review_status === "verified"
  ).length;
  const pendingTotal = reviewItems.length + report.unresolved_items.length;

  const showSection = (tab: ReportTab) =>
    activeTab === "all" || activeTab === tab;

  return (
    <div className="report-view">
      {/* Clean FinTech Report Header */}
      <header className="panel report-masthead">
        <div className="masthead-top">
          <div className="masthead-classification">
            <span className="industry-badge">
              {industryLabel(report.industry_id)}
            </span>
            <span className="timelock-badge mono">
              截止日期 {report.cutoff_date}
            </span>
            <span className="version-badge mono">v{report.report_version}</span>
          </div>

          <div className="download-row">
            <a
              className="download-button primary"
              href={`/api/runs/${encodeURIComponent(report.run_id)}/download/report.md`}
              download
            >
              导出 Markdown
            </a>
            <a
              className="download-button"
              href={`/api/runs/${encodeURIComponent(report.run_id)}/download/report.json`}
              download
            >
              导出 JSON
            </a>
          </div>
        </div>

        <h1 className="masthead-title">{report.company_name}</h1>

        <div className="report-meta-inline">
          <span>
            任务编号 <code className="mono">{report.run_id}</code>
          </span>
          <span>·</span>
          <span>
            行业模板 <code className="mono">{report.industry_id}</code>
          </span>
          <span>·</span>
          <span>
            生成时间 <span className="mono">{formatDateTime(report.generated_at)}</span>
          </span>
        </div>

        {/* Clean 4-Metric Dashboard Strip */}
        <div className="kpi-strip">
          <div className="kpi-card">
            <span className="kpi-label">正式核验结论</span>
            <div className="kpi-value-row">
              <strong className="kpi-value mono">{formalClaims.length}</strong>
              <span className="kpi-unit">条</span>
            </div>
            <span className="kpi-sub">已通过证据链校验</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">关键风险提示</span>
            <div className="kpi-value-row">
              <strong className="kpi-value mono amber">
                {formalRisks.length}
              </strong>
              <span className="kpi-unit">项</span>
            </div>
            <span className="kpi-sub">行业风控规则识别</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">底层溯源证据</span>
            <div className="kpi-value-row">
              <strong className="kpi-value mono teal">
                {report.evidence_index.length}
              </strong>
              <span className="kpi-unit">条</span>
            </div>
            <span className="kpi-sub">
              {verifiedEvidenceCount} 条已核验原文
            </span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">待复核 / 校验提示</span>
            <div className="kpi-value-row">
              <strong className="kpi-value mono">
                {pendingTotal} / {report.validation_issues.length}
              </strong>
            </div>
            <span className="kpi-sub">Critic 复核台账</span>
          </div>
        </div>
      </header>

      {/* Clean Underline Navigation Tabs */}
      <nav className="report-tabs" aria-label="研报章节导航">
        <button
          type="button"
          className={`report-tab ${activeTab === "all" ? "active" : ""}`}
          onClick={() => setActiveTab("all")}
        >
          完整研报
        </button>
        <button
          type="button"
          className={`report-tab ${activeTab === "narrative" ? "active" : ""}`}
          onClick={() => setActiveTab("narrative")}
        >
          摘要与正文
        </button>
        <button
          type="button"
          className={`report-tab ${activeTab === "claims" ? "active" : ""}`}
          onClick={() => setActiveTab("claims")}
        >
          正式结论 <span className="tab-count mono">{formalClaims.length}</span>
        </button>
        <button
          type="button"
          className={`report-tab ${activeTab === "risks" ? "active" : ""}`}
          onClick={() => setActiveTab("risks")}
        >
          风险提示 <span className="tab-count mono">{formalRisks.length}</span>
        </button>
        <button
          type="button"
          className={`report-tab ${activeTab === "review" ? "active" : ""}`}
          onClick={() => setActiveTab("review")}
        >
          待确认与未决 <span className="tab-count mono">{pendingTotal}</span>
        </button>
        <button
          type="button"
          className={`report-tab ${activeTab === "validation" ? "active" : ""}`}
          onClick={() => setActiveTab("validation")}
        >
          Critic 校验{" "}
          <span className="tab-count mono">
            {report.validation_issues.length}
          </span>
        </button>
      </nav>

      {/* Executive Summary */}
      {showSection("narrative") && (
        <section className="panel summary-panel">
          <div className="section-head">
            <h2>核心观点与投资要点</h2>
            <span className="section-sub">Executive Summary</span>
          </div>
          {report.summary.length === 0 ? (
            <p className="muted">暂无核心摘要。</p>
          ) : (
            <ul className="summary-list">
              {report.summary.map((line, index) => (
                <li key={`${line}-${index}`}>
                  <span className="summary-bullet mono">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Narrative Report Body */}
      {showSection("narrative") && narrative.length > 0 && (
        <section className="panel narrative-panel">
          <div className="section-head">
            <h2>投研正文</h2>
            <span className="muted">点击任意来源标签即可核验原文与页码</span>
          </div>
          <div className="narrative-list">
            {narrative.map((block, index) => (
              <NarrativeBlock
                key={`${block.section}-${index}`}
                block={block}
                index={index}
                evidenceMap={evidenceMap}
                onSelectEvidence={onSelectEvidence}
              />
            ))}
          </div>
        </section>
      )}

      {/* Formal Claims */}
      {showSection("claims") && (
        <section className="panel">
          <div className="section-head">
            <h2>正式结论台账</h2>
            <span className="section-count mono">{formalClaims.length} 条</span>
          </div>
          {formalClaims.length === 0 ? (
            <p className="muted">暂无正式结论。</p>
          ) : (
            <div className="claim-list">
              {formalClaims.map((claim) => (
                <ClaimCard
                  key={claim.claim_id}
                  claim={claim}
                  evidenceMap={evidenceMap}
                  onSelectEvidence={onSelectEvidence}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Formal Risks */}
      {showSection("risks") && (
        <section className="panel">
          <div className="section-head">
            <h2>正式风险提示</h2>
            <span className="section-count mono">{formalRisks.length} 项</span>
          </div>
          {formalRisks.length === 0 ? (
            <p className="muted">未检出正式风险项。</p>
          ) : (
            <div className="claim-list">
              {formalRisks.map((claim) => (
                <ClaimCard
                  key={claim.claim_id}
                  claim={claim}
                  evidenceMap={evidenceMap}
                  onSelectEvidence={onSelectEvidence}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Review & Unresolved Items */}
      {showSection("review") && (
        <div className="dual-ledger-grid">
          <section className="panel">
            <div className="section-head">
              <h2>待确认项</h2>
              <span className="section-count mono">{reviewItems.length} 项</span>
            </div>
            {reviewItems.length === 0 ? (
              <p className="muted">无待人工确认条目。</p>
            ) : (
              <div className="claim-list">
                {reviewItems.map((claim) => (
                  <ClaimCard
                    key={claim.claim_id}
                    claim={claim}
                    evidenceMap={evidenceMap}
                    onSelectEvidence={onSelectEvidence}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-head">
              <h2>未决跟踪事项</h2>
              <span className="section-count mono">
                {report.unresolved_items.length} 项
              </span>
            </div>
            {report.unresolved_items.length === 0 ? (
              <p className="muted">无未决跟踪事项。</p>
            ) : (
              <div className="claim-list">
                {report.unresolved_items.map((claim) => (
                  <ClaimCard
                    key={claim.claim_id}
                    claim={claim}
                    evidenceMap={evidenceMap}
                    onSelectEvidence={onSelectEvidence}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Critic Validation Issues */}
      {showSection("validation") && (
        <section className="panel">
          <div className="section-head">
            <h2>Critic 独立复核与校验台账</h2>
            <span className="section-count mono">
              {report.validation_issues.length} 条
            </span>
          </div>
          {report.validation_issues.length === 0 ? (
            <div className="audit-pass-box">
              全部规则校验与证据一致性复核通过，未发现冲突或无依据数字。
            </div>
          ) : (
            <ul className="issue-list">
              {report.validation_issues.map((issue) => (
                <li
                  key={issue.issue_id}
                  className={`issue-item ${issue.severity}`}
                >
                  <div className="issue-meta-col">
                    <span className={`issue-severity ${issue.severity}`}>
                      {issueSeverityText(issue.severity)}
                    </span>
                    <code className="issue-check mono">{issue.check_name}</code>
                  </div>
                  <div className="issue-body-col">
                    <p className="issue-message">{issue.message}</p>
                    <div className="issue-tags">
                      <span className="issue-tag mono">{issue.issue_type}</span>
                      {issue.report_section && (
                        <span className="issue-tag">
                          章节：{issue.report_section}
                        </span>
                      )}
                      {issue.human_confirmation_required && (
                        <span className="issue-tag warn">需人工复核确认</span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <footer className="report-disclaimer">
        <strong>免责声明：</strong>
        本投研简报由 FinCouncil 智研系统基于已验证公开资料在截止日期（
        {report.cutoff_date}
        ）时间锁约束下自动组织，所有结论均绑定原文证据链。本内容仅供研究与演示参考，不构成任何证券买卖或投资建议。
      </footer>
    </div>
  );
}
