import { useCallback, useEffect, useState } from "react";
import {
  createRun,
  fetchCases,
  fetchHealth,
  fetchReport,
  fetchRun,
  fetchRuns,
} from "./api";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { NewResearch } from "./components/NewResearch";
import { ReportView } from "./components/ReportView";
import { RunProgress } from "./components/RunProgress";
import { Sidebar } from "./components/Sidebar";
import type {
  CaseInfo,
  Evidence,
  HealthResponse,
  ResearchReport,
  RunStatus,
} from "./types";

type ThemeMode = "light" | "dark";

function getInitialTheme(): ThemeMode {
  try {
    const saved = window.localStorage.getItem("fincouncil_ui_theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Ignore storage access errors.
  }
  return "light";
}

export default function App() {
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [history, setHistory] = useState<RunStatus[]>([]);
  const [activeRun, setActiveRun] = useState<RunStatus | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem("fincouncil_ui_theme", theme);
    } catch {
      // Ignore storage write errors.
    }
  }, [theme]);

  const refreshHistory = useCallback(async () => {
    try {
      const runs = await fetchRuns();
      setHistory(runs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法读取历史记录");
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const [caseList, healthData, runs] = await Promise.all([
          fetchCases(),
          fetchHealth(),
          fetchRuns(),
        ]);
        setCases(caseList);
        setHealth(healthData);
        setHistory(runs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "无法连接后端服务");
      }
    };
    void load();
  }, []);

  const handleStart = async (payload: {
    case_id: string;
    cutoff_date: string;
    llm_enabled: boolean;
  }) => {
    setError(null);
    setReport(null);
    setSelectedEvidence(null);
    setStarting(true);
    try {
      const run = await createRun(payload);
      setActiveRun(run);
      if (run.status === "success") {
        const loaded = await fetchReport(run.run_id);
        setReport(loaded);
      }
      await refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动研究失败");
    } finally {
      setStarting(false);
    }
  };

  const handleSelectRun = async (runId: string) => {
    setError(null);
    setSelectedEvidence(null);
    try {
      const run = await fetchRun(runId);
      setActiveRun(run);
      if (run.status === "success") {
        const loaded = await fetchReport(runId);
        setReport(loaded);
      } else {
        setReport(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取运行记录失败");
    }
  };

  const handleNew = () => {
    setActiveRun(null);
    setReport(null);
    setSelectedEvidence(null);
    setError(null);
  };

  useEffect(() => {
    if (!activeRun) return;
    if (activeRun.status === "success" || activeRun.status === "failed") return;

    const timer = window.setInterval(async () => {
      try {
        const updated = await fetchRun(activeRun.run_id);
        setActiveRun(updated);
        if (updated.status === "success") {
          const loaded = await fetchReport(updated.run_id);
          setReport(loaded);
          await refreshHistory();
        } else if (updated.status === "failed") {
          await refreshHistory();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "轮询运行状态失败");
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [activeRun, refreshHistory]);

  const busy =
    starting ||
    (activeRun !== null &&
      (activeRun.status === "queued" || activeRun.status === "running"));

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  return (
    <div className="app-shell">
      <Sidebar
        cases={cases}
        history={history}
        activeRunId={activeRun?.run_id ?? null}
        onNew={handleNew}
        onSelectRun={handleSelectRun}
      />

      <div className="workspace-column">
        <header className="topbar">
          <div className="topbar-left">
            <span className="topbar-section">投研工作台</span>
            <span className="topbar-sep">/</span>
            <span className="topbar-crumb">
              {report
                ? report.company_name
                : activeRun
                ? `执行监控 · ${activeRun.run_id}`
                : "新建研究任务"}
            </span>
          </div>

          <div className="topbar-right">
            <div className="status-pill" title="T+0 时间锁防未来函数校验">
              <span className="status-pill-dot teal" />
              <span>时间锁已启用</span>
            </div>

            <div
              className="status-pill"
              title={
                health
                  ? `服务版本 v${health.version}`
                  : "正在连接本地研究引擎"
              }
            >
              <span
                className={`status-pill-dot ${
                  health ? (health.llm_available ? "green" : "blue") : "amber"
                }`}
              />
              <span>
                {health
                  ? health.llm_available
                    ? "LLM 增强在线"
                    : "确定性规则引擎"
                  : "连接服务中…"}
              </span>
            </div>

            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              title={theme === "light" ? "切换深色模式" : "切换浅色模式"}
            >
              {theme === "light" ? (
                <>
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                  </svg>
                  <span>深色</span>
                </>
              ) : (
                <>
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="4" />
                    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
                  </svg>
                  <span>浅色</span>
                </>
              )}
            </button>
          </div>
        </header>

        <main className="main-content">
          {error && (
            <div className="error-banner" role="alert">
              <div className="error-banner-body">
                <span className="error-dot" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                className="icon-button subtle"
                onClick={() => setError(null)}
                aria-label="关闭提示"
              >
                ✕
              </button>
            </div>
          )}

          {activeRun &&
            (activeRun.status === "queued" || activeRun.status === "running") && (
              <RunProgress run={activeRun} />
            )}

          {activeRun && activeRun.status === "failed" && (
            <div className="panel error-panel">
              <div className="panel-header">
                <h2>研究任务执行失败</h2>
                <span className="status-badge failed">已中止</span>
              </div>
              <p className="error-detail-text">{activeRun.error ?? "未知错误"}</p>
              <p className="muted">
                请检查资料包完整性与模型环境；若 LLM 暂不可用，可切换回确定性
                rule-engine 重试。
              </p>
            </div>
          )}

          {report ? (
            <ReportView
              report={report}
              onSelectEvidence={setSelectedEvidence}
            />
          ) : (
            <NewResearch
              cases={cases}
              llmAvailable={health?.llm_available ?? false}
              disabled={busy}
              activeRun={activeRun}
              onStart={handleStart}
            />
          )}
        </main>
      </div>

      <EvidenceDrawer
        evidence={selectedEvidence}
        onClose={() => setSelectedEvidence(null)}
      />
    </div>
  );
}
