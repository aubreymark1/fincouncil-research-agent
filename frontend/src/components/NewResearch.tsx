import { useEffect, useMemo, useState } from "react";
import type { CaseInfo, RunStatus } from "../types";

interface NewResearchProps {
  cases: CaseInfo[];
  modelAvailable: boolean;
  disabled: boolean;
  activeRun: RunStatus | null;
  onStart: (payload: {
    case_id: string;
    cutoff_date: string;
  }) => void;
}

export function NewResearch({
  cases,
  modelAvailable,
  disabled,
  activeRun,
  onStart,
}: NewResearchProps) {
  const [caseId, setCaseId] = useState("food_main");
  const [cutoffDate, setCutoffDate] = useState("2026-08-20");

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

        <div className={`model-status ${modelAvailable ? "ready" : "unavailable"}`} role="status">
          <span className="model-status-mark" aria-hidden="true">{modelAvailable ? "✓" : "!"}</span>
          <span>
            <strong>本次研究固定使用 LLM</strong>
            <small className="muted">
              {modelAvailable
                ? "DeepSeek 负责分析与写作，时间锁、证据验证和质量检查由规则程序执行。"
                : "研究模型暂不可用，模型恢复后才能开始研究。"}
            </small>
          </span>
        </div>

        {activeRun && (activeRun.status === "queued" || activeRun.status === "running") && (
          <div className="notice">
            当前已有任务 {activeRun.run_id} 正在运行，单并发保护已启用。
          </div>
        )}

        <button className="start-button" type="submit" disabled={disabled || !modelAvailable}>
          {disabled ? "研究运行中…" : modelAvailable ? "启动研究" : "模型暂不可用"}
        </button>
      </form>
    </div>
  );
}
