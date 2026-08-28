import { useEffect, useMemo, useState } from "react";
import type { CaseInfo, RunStatus } from "../types";

interface NewResearchProps {
  cases: CaseInfo[];
  llmAvailable: boolean;
  disabled: boolean;
  activeRun: RunStatus | null;
  onStart: (payload: {
    case_id: string;
    cutoff_date: string;
    llm_enabled: boolean;
  }) => void;
}

export function NewResearch({
  cases,
  llmAvailable,
  disabled,
  activeRun,
  onStart,
}: NewResearchProps) {
  const [caseId, setCaseId] = useState("food_main");
  const [cutoffDate, setCutoffDate] = useState("2026-08-20");
  const [llmEnabled, setLlmEnabled] = useState(true);

  const selectedCase = useMemo(
    () => cases.find((item) => item.case_id === caseId) ?? cases[0],
    [cases, caseId]
  );

  useEffect(() => {
    if (selectedCase) {
      setCutoffDate(selectedCase.default_cutoff);
    }
  }, [selectedCase?.case_id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!selectedCase) {
    return <div className="panel">正在加载案例…</div>;
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    onStart({
      case_id: caseId,
      cutoff_date: cutoffDate,
      llm_enabled: llmAvailable && llmEnabled,
    });
  };

  return (
    <div className="panel new-research">
      <div className="panel-header">
        <h1>新建研究</h1>
        <p className="muted">选择已验证资料包和截止日期，启动一次完整研究。</p>
      </div>

      <form onSubmit={submit} className="research-form">
        <label className="field">
          <span>研究对象 / 资料包</span>
          <select
            value={caseId}
            onChange={(event) => setCaseId(event.target.value)}
            disabled={disabled}
          >
            {cases.map((caseInfo) => (
              <option key={caseInfo.case_id} value={caseInfo.case_id}>
                {caseInfo.display_name}（{caseInfo.case_id}）
              </option>
            ))}
          </select>
          <small className="muted">{selectedCase.description}</small>
        </label>

        <label className="field">
          <span>研究截止日期</span>
          <input
            type="date"
            value={cutoffDate}
            onChange={(event) => setCutoffDate(event.target.value)}
            disabled={disabled}
          />
          <small className="muted">
            截止日期之后发布的资料不会进入正文。
          </small>
        </label>

        <label className="field toggle-field">
          <span className="toggle-label">
            <span>AI 增强模式</span>
            <small className="muted">
              {llmAvailable
                ? "DeepSeek 演示环境已配置；失败时可切换回 rule-engine。"
                : "未配置：当前仅可使用确定性 rule-engine。"}
            </small>
          </span>
          <input
            type="checkbox"
            checked={llmAvailable && llmEnabled}
            onChange={(event) => setLlmEnabled(event.target.checked)}
            disabled={disabled || !llmAvailable}
          />
        </label>

        {activeRun && (activeRun.status === "queued" || activeRun.status === "running") && (
          <div className="notice">
            当前已有任务 {activeRun.run_id} 正在运行，单并发保护已启用。
          </div>
        )}

        <button className="start-button" type="submit" disabled={disabled}>
          {disabled ? "研究运行中…" : "启动研究"}
        </button>
      </form>
    </div>
  );
}
