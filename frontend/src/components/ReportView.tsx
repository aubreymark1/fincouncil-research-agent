import { useMemo } from "react";
import type { Claim, Evidence, ReportBlock, ResearchReport } from "../types";

interface ReportViewProps {
  report: ResearchReport;
  onSelectEvidence: (evidence: Evidence) => void;
}

function sourceSummary(evidence: Evidence | undefined): string {
  if (!evidence) return "缺失来源";
  const page = evidence.page ? ` · 第 ${evidence.page} 页` : "";
  return `${evidence.evidence_id} · ${evidence.doc_id}${page}`;
}

function NarrativeBlock({
  block,
  evidenceMap,
  onSelectEvidence,
}: {
  block: ReportBlock;
  evidenceMap: Map<string, Evidence>;
  onSelectEvidence: (evidence: Evidence) => void;
}) {
  const sources = block.evidence_ids
    .map((id) => evidenceMap.get(id))
    .filter((item): item is Evidence => Boolean(item));

  return (
    <article className="narrative-block">
      <h3>{block.section}</h3>
      <p>{block.text}</p>
      <div className="source-row">
        <span className="source-label">来源</span>
        {sources.length === 0 ? (
          <span className="muted">未绑定来源</span>
        ) : (
          sources.slice(0, 5).map((evidence) => (
            <button
              key={evidence.evidence_id}
              type="button"
              className="source-chip"
              onClick={() => onSelectEvidence(evidence)}
              title="点击查看证据详情"
            >
              {sourceSummary(evidence)}
            </button>
          ))
        )}
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
  const sources = claim.evidence_ids
    .map((id) => evidenceMap.get(id))
    .filter((item): item is Evidence => Boolean(item));

  return (
    <article className="claim-card">
      <div className="claim-head">
        <span className={`claim-status ${claim.status}`}>{claim.status}</span>
        <code className="claim-id">{claim.claim_id}</code>
        {claim.risk_severity && (
          <span className={`risk-severity ${claim.risk_severity}`}>
            {claim.risk_severity}
          </span>
        )}
      </div>
      <p className="claim-text">{claim.text}</p>
      {claim.industry_metric_ids.length > 0 && (
        <div className="claim-meta">
          指标：{claim.industry_metric_ids.join("、")} · 置信度 {claim.confidence.toFixed(2)}
        </div>
      )}
      <div className="source-row">
        <span className="source-label">来源</span>
        {sources.length === 0 ? (
          <span className="muted">无证据引用</span>
        ) : (
          sources.slice(0, 5).map((evidence) => (
            <button
              key={evidence.evidence_id}
              type="button"
              className="source-chip"
              onClick={() => onSelectEvidence(evidence)}
              title="点击查看证据详情"
            >
              {sourceSummary(evidence)}
            </button>
          ))
        )}
        {sources.length > 5 && (
          <span className="muted">+{sources.length - 5}</span>
        )}
      </div>
    </article>
  );
}

export function ReportView({ report, onSelectEvidence }: ReportViewProps) {
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

  return (
    <div className="report-view">
      <div className="panel report-header">
        <div className="panel-header">
          <h1>投研简报：{report.company_name}</h1>
          <span className="muted">{report.run_id}</span>
        </div>
        <div className="report-meta">
          <span>行业：{report.industry_id}</span>
          <span>截止日期：{report.cutoff_date}</span>
          <span>生成时间：{report.generated_at}</span>
          <span>版本：{report.report_version}</span>
        </div>
        <div className="download-row">
          <a
            className="download-button"
            href={`/api/runs/${encodeURIComponent(report.run_id)}/download/report.json`}
            download
          >
            下载 report.json
          </a>
          <a
            className="download-button"
            href={`/api/runs/${encodeURIComponent(report.run_id)}/download/report.md`}
            download
          >
            下载 report.md
          </a>
        </div>
      </div>

      {narrative.length > 0 && (
        <section className="panel narrative-panel">
          <h2>投研正文</h2>
          <div className="narrative-list">
            {narrative.map((block, index) => (
              <NarrativeBlock
                key={`${block.section}-${index}`}
                block={block}
                evidenceMap={evidenceMap}
                onSelectEvidence={onSelectEvidence}
              />
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <h2>摘要</h2>
        <ul className="summary-list">
          {report.summary.map((line, index) => (
            <li key={`${line}-${index}`}>{line}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>正式结论</h2>
        {formalClaims.length === 0 ? (
          <p className="muted">无。</p>
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

      <section className="panel">
        <h2>正式风险</h2>
        {formalRisks.length === 0 ? (
          <p className="muted">无。</p>
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

      <section className="panel">
        <h2>待确认项</h2>
        {reviewItems.length === 0 ? (
          <p className="muted">无。</p>
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
        <h2>未决项</h2>
        {report.unresolved_items.length === 0 ? (
          <p className="muted">无。</p>
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

      <section className="panel">
        <h2>校验问题</h2>
        {report.validation_issues.length === 0 ? (
          <p className="muted">无。</p>
        ) : (
          <ul className="issue-list">
            {report.validation_issues.map((issue) => (
              <li key={issue.issue_id} className={`issue-item ${issue.severity}`}>
                <span className="issue-severity">{issue.severity}</span>
                <span>{issue.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
