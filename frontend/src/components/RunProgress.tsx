import type { RunStatus } from "../types";

const STAGES = [
  "准备研究请求",
  "校验资料清单",
  "执行时间过滤",
  "解析原始资料",
  "定位证据",
  "生成分析结论",
  "执行 Critic 审查",
  "写入报告产物",
  "研究完成",
];

interface RunProgressProps {
  run: RunStatus;
}

export function RunProgress({ run }: RunProgressProps) {
  const progress = new Set(run.progress);
  const currentStage = run.stage ?? "";

  const completedCount = STAGES.reduce((acc, stage, index) => {
    const done =
      progress.has(stage) ||
      (run.status === "success" && index === STAGES.length - 1);
    return acc + (done ? 1 : 0);
  }, 0);

  const percent = Math.round((completedCount / STAGES.length) * 100);

  return (
    <section className="panel run-progress" aria-live="polite">
      <div className="panel-header">
        <div>
          <h2>研究流水线执行进度</h2>
          <div className="progress-meta-bar">
            <span>
              任务 <code className="mono">{run.run_id}</code>
            </span>
            <span>·</span>
            <span>
              资料包 <code className="mono">{run.case_id}</code>
            </span>
            <span>·</span>
            <span>
              rule-engine{run.llm_enabled ? " + LLM 增强" : ""}
            </span>
          </div>
        </div>

        <div className="progress-header-right">
          <span className="progress-pct mono">{percent}%</span>
          <span className={`status-badge ${run.status}`}>
            {run.status === "queued" && "排队中"}
            {run.status === "running" && "分析中"}
            {run.status === "success" && "已完成"}
            {run.status === "failed" && "失败"}
          </span>
        </div>
      </div>

      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>

      <ol className="progress-grid">
        {STAGES.map((stage, index) => {
          const done =
            progress.has(stage) ||
            (run.status === "success" && index === STAGES.length - 1);
          const active = run.status === "running" && currentStage === stage;
          return (
            <li
              key={stage}
              className={`progress-step ${done ? "done" : ""} ${
                active ? "active" : ""
              }`}
            >
              <span className="step-marker mono">
                {done ? "✓" : String(index + 1).padStart(2, "0")}
              </span>
              <span className="step-label">{stage}</span>
            </li>
          );
        })}
      </ol>

      {run.error && <div className="error-box">运行失败：{run.error}</div>}
    </section>
  );
}
