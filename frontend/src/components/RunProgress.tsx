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

  return (
    <div className="panel run-progress">
      <div className="panel-header">
        <h2>研究进度</h2>
        <span className={`status-badge ${run.status}`}>
          {run.status === "queued" && "排队中"}
          {run.status === "running" && "运行中"}
          {run.status === "success" && "已完成"}
          {run.status === "failed" && "失败"}
        </span>
      </div>
      <p className="muted">
        {run.run_id} · {run.case_id} · rule-engine
        {run.llm_enabled ? " + LLM 增强" : ""}
      </p>
      <ol className="progress-steps">
        {STAGES.map((stage, index) => {
          const done = progress.has(stage) || (run.status === "success" && index === STAGES.length - 1);
          const active = run.status === "running" && currentStage === stage;
          return (
            <li
              key={stage}
              className={`progress-step ${done ? "done" : ""} ${active ? "active" : ""}`}
            >
              <span className="step-marker">{done ? "✓" : index + 1}</span>
              <span className="step-label">{stage}</span>
            </li>
          );
        })}
      </ol>
      {run.error && <div className="error-box">运行失败：{run.error}</div>}
    </div>
  );
}
