import { useMemo } from "react";
import type { Claim, Evidence, ResearchReport, ValidationIssue } from "../types";
import { getReadableSections, presentValidationIssue } from "../reportUtils";
import type { ReadableSection } from "../reportUtils";
import { CitationPopover } from "./CitationPopover";

interface ReportViewProps {
  report: ResearchReport;
  onSelectEvidence: (evidence: Evidence) => void;
}

function sourceSummary(evidence: Evidence | undefined): string {
  if (!evidence) return "缺失来源";
  const page = evidence.page ? `第 ${evidence.page} 页` : "页码未提供";
  return `${evidence.doc_id} · ${page}`;
}

function SourceChips({
  ids,
  evidenceMap,
  onSelectEvidence,
}: {
  ids: string[];
  evidenceMap: Map<string, Evidence>;
  onSelectEvidence: (evidence: Evidence) => void;
}) {
  const sources = ids
    .map((id) => evidenceMap.get(id))
    .filter((item): item is Evidence => Boolean(item));

  return (
    <div className="source-row">
      <span className="source-label">证据</span>
      {sources.length === 0 ? (
        <span className="muted">未绑定可核验来源</span>
      ) : (
        sources.slice(0, 6).map((evidence) => (
          <button
            key={evidence.evidence_id}
            type="button"
            className="source-chip"
            onClick={() => onSelectEvidence(evidence)}
            title="点击查看原文证据"
            aria-label={`查看 ${evidence.evidence_id} 原文证据`}
          >
            <span aria-hidden="true">↗</span> {sourceSummary(evidence)}
          </button>
        ))
      )}
      {sources.length > 6 && <span className="muted">+{sources.length - 6} 条</span>}
    </div>
  );
}

function NarrativeBlock({
  section,
  index,
  evidenceMap,
  onSelectEvidence,
}: {
  section: ReadableSection;
  index: number;
  evidenceMap: Map<string, Evidence>;
  onSelectEvidence: (evidence: Evidence) => void;
}) {
  return (
    <article className="narrative-block">
      <div className="narrative-index">0{index + 1}</div>
      <div className="narrative-content">
        <div className="narrative-kicker">研究段落</div>
        <h3>{section.section}</h3>
        <p className="narrative-prose">
          {section.segments.map((segment) => {
            const evidence = segment.evidence_ids
              .map((id) => evidenceMap.get(id))
              .filter((item): item is Evidence => Boolean(item));
            return (
              <span key={segment.segment_id} className={`narrative-segment ${segment.status}`}>
                {segment.text}
                {segment.status === "pass" && evidence.length > 0 && (
                  <CitationPopover evidence={evidence} onOpenEvidence={onSelectEvidence} />
                )}
              </span>
            );
          })}
        </p>
      </div>
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
  const statusLabel = claim.status === "pass" ? "已通过" : claim.status === "review" ? "待确认" : claim.status;

  return (
    <article className="claim-card">
      <div className="claim-head">
        <span className={`claim-status ${claim.status}`}>{statusLabel}</span>
        <code className="claim-id">{claim.claim_id}</code>
        {claim.risk_severity && (
          <span className={`risk-severity ${claim.risk_severity}`}>
            风险 · {claim.risk_severity}
          </span>
        )}
      </div>
      <p className="claim-text">{claim.text}</p>
      {claim.industry_metric_ids.length > 0 && (
        <div className="claim-meta">
          指标：{claim.industry_metric_ids.join("、")} · 置信度 {claim.confidence.toFixed(2)}
        </div>
      )}
      <SourceChips
        ids={claim.evidence_ids}
        evidenceMap={evidenceMap}
        onSelectEvidence={onSelectEvidence}
      />
    </article>
  );
}

function IssueCard({
  issue,
  onSelectEvidence,
  evidenceMap,
}: {
  issue: ValidationIssue;
  onSelectEvidence: (evidence: Evidence) => void;
  evidenceMap: Map<string, Evidence>;
}) {
  const presented = presentValidationIssue(issue);
  const linkedEvidence = issue.evidence_id ? evidenceMap.get(issue.evidence_id) : undefined;

  return (
    <li className={`issue-item ${issue.severity} ${presented.tone}`}>
      <div className="issue-main">
        <div className="issue-topline">
          <span className="issue-severity">{presented.category}</span>
          <strong>{presented.title}</strong>
        </div>
        <span className="issue-detail">{presented.detail}</span>
        {presented.action && <span className="issue-action">下一步：{presented.action}</span>}
        {linkedEvidence && (
          <button type="button" className="issue-evidence" onClick={() => onSelectEvidence(linkedEvidence)}>
            查看关联证据 ↗
          </button>
        )}
        <details className="issue-technical">
          <summary>技术详情</summary>
          <span>{presented.technical_detail}</span>
        </details>
      </div>
    </li>
  );
}

export function ReportView({ report, onSelectEvidence }: ReportViewProps) {
  const evidenceMap = useMemo(
    () => new Map(report.evidence_index.map((item) => [item.evidence_id, item])),
    [report.evidence_index],
  );
  const readableSections = getReadableSections(report);
  const formalClaims = report.claims.filter((claim) => claim.status === "pass");
  const formalRisks = report.risks.filter((claim) => claim.status === "pass");
  const reviewItems = [
    ...report.claims.filter((claim) => claim.status === "review"),
    ...report.risks.filter((claim) => claim.status === "review"),
  ];
  const issueCount = report.validation_issues.filter((issue) => issue.status === "open").length;

  return (
    <div className="report-view">
      <header className="panel report-header">
        <div className="report-kicker">研究工作台 / 已完成运行</div>
        <div className="panel-header">
          <div>
            <h1>投研简报：{report.company_name}</h1>
            <p className="report-deck">一份可回溯、可复核的研究初稿</p>
          </div>
          <span className="run-id-pill">{report.run_id}</span>
        </div>
        <div className="report-meta">
          <span>行业 · {report.industry_id}</span>
          <span>研究截止 · {report.cutoff_date}</span>
          <span>生成于 · {new Date(report.generated_at).toLocaleString("zh-CN", { hour12: false })}</span>
          <span>版本 · {report.report_version}</span>
        </div>
        <div className="download-row">
          <a className="download-button primary-download" href={`/api/runs/${encodeURIComponent(report.run_id)}/download/report.md`} download>
            下载研究稿 <span aria-hidden="true">↓</span>
          </a>
          <a className="download-button" href={`/api/runs/${encodeURIComponent(report.run_id)}/download/report.json`} download>
            JSON 数据
          </a>
        </div>
      </header>

      <section className="report-stats" aria-label="运行统计">
        <div className="stat-card stat-featured">
          <span className="stat-label">投研正文</span>
          <strong>{readableSections.length}</strong>
          <span>段可阅读内容</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">证据索引</span>
          <strong>{report.evidence_index.length}</strong>
          <span>条已定位来源</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">校验问题</span>
          <strong>{issueCount}</strong>
          <span>{issueCount > 0 ? "条需要复核" : "全部通过"}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">研究口径</span>
          <strong>{report.cutoff_date.slice(0, 4)}</strong>
          <span>时间锁已启用</span>
        </div>
      </section>

      {readableSections.length > 0 && (
        <section className="panel narrative-panel">
          <div className="section-heading">
            <div>
              <div className="section-kicker">主要阅读</div>
              <h2>投研正文</h2>
            </div>
            <span className="section-note">点击段落下方来源，回到原文证据</span>
          </div>
          <div className="narrative-list">
            {readableSections.map((section, index) => (
              <NarrativeBlock
                key={`${section.section}-${index}`}
                section={section}
                index={index}
                evidenceMap={evidenceMap}
                onSelectEvidence={onSelectEvidence}
              />
            ))}
          </div>
        </section>
      )}

      <section className="panel summary-panel">
        <div className="section-heading">
          <div>
            <div className="section-kicker">运行摘要</div>
            <h2>这次运行留下了什么</h2>
          </div>
        </div>
        <ul className="summary-list">
          <li><strong>{readableSections.length} 段</strong>投研正文已生成，结构化正式结论 {formalClaims.length} 条。</li>
          <li><strong>{formalRisks.length} 条</strong>正式风险，另有 {reviewItems.length} 条结论等待人工确认。</li>
          <li>证据索引包含 <strong>{report.evidence_index.length} 条</strong>已定位来源，时间锁截止于 {report.cutoff_date}。</li>
        </ul>
      </section>

      <section className="panel evidence-index-panel">
        <div className="section-heading">
          <div>
            <div className="section-kicker">Evidence</div>
            <h2>证据索引</h2>
          </div>
          <span className="section-note">{report.evidence_index.length} 条来源 · 全部可展开</span>
        </div>
        {report.evidence_index.length === 0 ? (
          <p className="muted">暂无可展示的已验证证据。</p>
        ) : (
          <div className="evidence-index-list">
            {report.evidence_index.map((evidence) => (
              <button key={evidence.evidence_id} type="button" className="evidence-index-item" onClick={() => onSelectEvidence(evidence)}>
                <span className="evidence-index-icon">↗</span>
                <span className="evidence-index-copy">
                  <strong>{sourceSummary(evidence)}</strong>
                  <span>{evidence.fact_text}</span>
                </span>
                <span className={`review-badge ${evidence.review_status}`}>{evidence.review_status === "verified" ? "已验证" : evidence.review_status}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      {formalClaims.length > 0 && <section className="panel claim-panel">
        <div className="section-heading">
          <div>
          <div className="section-kicker">结构化结果</div>
            <h2>正式结论</h2>
          </div>
          <span className="section-note">供研究员二次整理</span>
        </div>
        {formalClaims.length === 0 ? <p className="muted">当前运行没有可单独列出的正式 Claim；正文仍可作为研究初稿阅读。</p> : (
          <div className="claim-list">{formalClaims.map((claim) => <ClaimCard key={claim.claim_id} claim={claim} evidenceMap={evidenceMap} onSelectEvidence={onSelectEvidence} />)}</div>
        )}
      </section>}

      {formalRisks.length > 0 && <section className="panel claim-panel">
        <div className="section-heading"><div><div className="section-kicker">风险</div><h2>正式风险</h2></div></div>
        {formalRisks.length === 0 ? <p className="muted">当前运行没有单独标记为正式风险的 Claim。</p> : (
          <div className="claim-list">{formalRisks.map((claim) => <ClaimCard key={claim.claim_id} claim={claim} evidenceMap={evidenceMap} onSelectEvidence={onSelectEvidence} />)}</div>
        )}
      </section>}

      {reviewItems.length > 0 && <section className="panel review-panel">
        <div className="section-heading"><div><div className="section-kicker">人工确认</div><h2>待确认项</h2></div><span className="section-note">最终研究材料前需要人工判断</span></div>
        {reviewItems.length === 0 ? <p className="muted">暂无待确认的结构化结论。</p> : (
          <div className="claim-list">{reviewItems.map((claim) => <ClaimCard key={claim.claim_id} claim={claim} evidenceMap={evidenceMap} onSelectEvidence={onSelectEvidence} />)}</div>
        )}
      </section>}

      <section className="panel issue-panel">
        <div className="section-heading"><div><div className="section-kicker">质量检查</div><h2>研究质量检查</h2></div><span className="section-note">先处理问题，再纳入正式材料</span></div>
        {report.validation_issues.length === 0 ? <p className="muted">无校验问题。</p> : (
          <ul className="issue-list">{report.validation_issues.map((issue) => <IssueCard key={issue.issue_id} issue={issue} evidenceMap={evidenceMap} onSelectEvidence={onSelectEvidence} />)}</ul>
        )}
      </section>
    </div>
  );
}
