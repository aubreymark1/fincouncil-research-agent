import type { CaseInfo, RunStatus } from "../types";

interface SidebarProps {
  cases: CaseInfo[];
  history: RunStatus[];
  activeRunId: string | null;
  onNew: () => void;
  onSelectRun: (runId: string) => void;
}

function statusLabel(status: RunStatus["status"]): string {
  switch (status) {
    case "queued":
      return "排队中";
    case "running":
      return "分析中";
    case "success":
      return "已完成";
    case "failed":
      return "失败";
  }
}

function caseDisplayName(caseId: string, cases: CaseInfo[]): string {
  const matched = cases.find((item) => item.case_id === caseId);
  if (matched) return matched.display_name;
  if (caseId === "food_main") return "食品饮料行业样本";
  if (caseId === "bank_main") return "中国工商银行样本";
  return caseId;
}

function formatRunTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${min}`;
}

export function Sidebar({
  cases,
  history,
  activeRunId,
  onNew,
  onSelectRun,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="13" width="3.5" height="7" rx="1" fill="currentColor" opacity="0.6" />
            <rect x="10.25" y="9" width="3.5" height="11" rx="1" fill="currentColor" opacity="0.85" />
            <rect x="17.5" y="4" width="3.5" height="16" rx="1" fill="currentColor" />
          </svg>
        </div>
        <div className="brand-copy">
          <div className="brand-name">
            FinCouncil <span className="brand-cn">智研</span>
          </div>
          <div className="brand-sub">AI 投研工作台</div>
        </div>
      </div>

      <button className="primary-action" onClick={onNew} type="button">
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 5v14M5 12h14" />
        </svg>
        <span>新建研究任务</span>
      </button>

      <section className="sidebar-section">
        <div className="sidebar-section-head">
          <h2>历史研究记录</h2>
          <span className="sidebar-count mono">{history.length}</span>
        </div>

        {history.length === 0 ? (
          <div className="empty-history">
            <p className="muted">暂无研究记录</p>
          </div>
        ) : (
          <ul className="history-list">
            {history.map((run) => {
              const isActive = activeRunId === run.run_id;
              return (
                <li key={run.run_id}>
                  <button
                    type="button"
                    className={`history-item ${isActive ? "active" : ""}`}
                    onClick={() => onSelectRun(run.run_id)}
                  >
                    <div className="history-item-top">
                      <span className={`status-dot ${run.status}`} />
                      <span className="history-title">
                        {caseDisplayName(run.case_id, cases)}
                      </span>
                      <span className="engine-mini-tag mono">
                        {run.llm_enabled ? "LLM" : "RULE"}
                      </span>
                    </div>
                    <div className="history-meta">
                      <span className="mono">{run.run_id.slice(-8)}</span>
                      <span>·</span>
                      <span>{statusLabel(run.status)}</span>
                      {run.created_at && (
                        <>
                          <span>·</span>
                          <span className="mono">
                            {formatRunTime(run.created_at)}
                          </span>
                        </>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="sidebar-section sidebar-bottom">
        <div className="sidebar-section-head">
          <h2>已核验资料包</h2>
          <span className="sidebar-verified">Verified</span>
        </div>

        <ul className="case-list">
          {cases.map((caseInfo) => (
            <li key={caseInfo.case_id} className="coverage-mini-card">
              <div className="coverage-mini-head">
                <strong>{caseInfo.display_name}</strong>
                <code className="mono">{caseInfo.case_id}</code>
              </div>
              <span className="muted">{caseInfo.description}</span>
            </li>
          ))}
        </ul>

        <p className="compliance-footnote">
          仅基于已验证公开资料包运行，严守时间锁约束，不执行实时爬虫，不构成投资建议。
        </p>
      </section>
    </aside>
  );
}
