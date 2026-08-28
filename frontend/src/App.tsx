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

export default function App() {
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [history, setHistory] = useState<RunStatus[]>([]);
  const [activeRun, setActiveRun] = useState<RunStatus | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

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

  return (
    <div className="app-shell">
      <Sidebar
        cases={cases}
        history={history}
        activeRunId={activeRun?.run_id ?? null}
        onNew={handleNew}
        onSelectRun={handleSelectRun}
      />

      <main className="main-content">
        {error && (
          <div className="error-banner" role="alert">
            {error}
            <button type="button" onClick={() => setError(null)}>
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
            <h2>研究失败</h2>
            <p>{activeRun.error ?? "未知错误"}</p>
            <p className="muted">
              请检查资料包与运行环境；LLM 失败时可切换回 rule-engine 重试。
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

      <EvidenceDrawer
        evidence={selectedEvidence}
        onClose={() => setSelectedEvidence(null)}
      />
    </div>
  );
}
