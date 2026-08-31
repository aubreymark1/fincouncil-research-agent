import type { CaseInfo, RunStatus } from "../types";
import type { Theme } from "../theme";

interface SidebarProps {
  cases: CaseInfo[];
  history: RunStatus[];
  activeRunId: string | null;
  onNew: () => void;
  onSelectRun: (runId: string) => void;
  theme: Theme;
  onToggleTheme: () => void;
}

function statusLabel(status: RunStatus["status"]): string {
  switch (status) {
    case "queued":
      return "排队中";
    case "running":
      return "运行中";
    case "success":
      return "已完成";
    case "failed":
      return "失败";
  }
}

export function Sidebar({
  cases,
  history,
  activeRunId,
  onNew,
  onSelectRun,
  theme,
  onToggleTheme,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">FC</div>
        <div>
          <div className="brand-name">FinCouncil</div>
          <div className="brand-sub">匿名体验版投研工作台</div>
        </div>
        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "切换到白天模式" : "切换到黑夜模式"}
          aria-pressed={theme === "light"}
          title={theme === "dark" ? "切换到白天模式" : "切换到黑夜模式"}
        >
          <span aria-hidden="true">{theme === "dark" ? "☼" : "☾"}</span>
          <span>{theme === "dark" ? "白天" : "黑夜"}</span>
        </button>
      </div>

      <button className="primary-action" onClick={onNew} type="button">
        + 新建研究
      </button>

      <section className="sidebar-section">
        <h2>历史运行记录</h2>
        {history.length === 0 ? (
          <p className="muted">暂无运行记录</p>
        ) : (
          <ul className="history-list">
            {history.map((run) => (
              <li key={run.run_id}>
                <button
                  type="button"
                  className={`history-item ${
                    activeRunId === run.run_id ? "active" : ""
                  }`}
                  onClick={() => onSelectRun(run.run_id)}
                >
                  <span className="history-title">
                    {run.source_mode === "authoritative_online"
                      ? run.subject ?? run.case_id
                      : run.case_id === "food_main"
                      ? "食品饮料行业样本"
                      : run.case_id === "bank_main"
                      ? "中国工商银行样本"
                      : run.case_id}
                  </span>
                  <span className="history-meta">
                    {run.run_id} · {statusLabel(run.status)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sidebar-section">
        <h2>案例说明</h2>
        <div className="case-note">
          <p>
            当前匿名体验版仅支持已验证资料包：
            <code>food_main</code>、<code>bank_main</code>。
          </p>
          <p className="muted">
            未知公司不会被伪装成已抓取资料；系统不会执行大规模实时爬虫。
          </p>
        </div>
        <ul className="case-list">
          {cases.map((caseInfo) => (
            <li key={caseInfo.case_id}>
              <strong>{caseInfo.display_name}</strong>
              <span className="muted">{caseInfo.description}</span>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
