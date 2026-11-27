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

const PIPELINE_STEPS = [
  {
    code: "01",
    title: "资料解析与文本切分",
    desc: "读取公开财报与行业公告，建立可定位文档块索引",
  },
  {
    code: "02",
    title: "T+0 时间锁过滤",
    desc: "剔除截止日期后发布的资料，杜绝未来信息泄露",
  },
  {
    code: "03",
    title: "行业指标与风控规则",
    desc: "加载行业必查财务口径与风险触发规则",
  },
  {
    code: "04",
    title: "证据链精准定位",
    desc: "结论绑定原文摘录、文档 ID 及精确页码",
  },
  {
    code: "05",
    title: "投研简报结构化生成",
    desc: "基于核验事实组织核心观点与正文章节",
  },
  {
    code: "06",
    title: "Critic 独立复核",
    desc: "自动检出数据冲突、无依据数字与待确认事项",
  },
];

function sectorTag(caseId: string): string {
  if (caseId === "food_main") return "食品饮料";
  if (caseId === "bank_main") return "银行业";
  return "行业研究";
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
    return (
      <div className="panel loading-panel">
        <span className="loading-spinner" aria-hidden="true" />
        <span>正在加载已核验研究资料库…</span>
      </div>
    );
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
    <div className="research-desk-grid">
      <section className="panel new-research">
        <div className="desk-header">
          <h1>新建投研简报</h1>
          <p className="muted">
            选择已验证资料包并设定研究截止日期，系统将在时间锁与证据链约束下生成可溯源投研报告。
          </p>
        </div>

        <form onSubmit={submit} className="research-form">
          <div className="field">
            <div className="field-head">
              <span className="field-label">研究对象与资料包</span>
              <span className="field-hint">
                共 {cases.length} 个已核验样本
              </span>
            </div>

            <div className="case-card-grid" role="radiogroup" aria-label="研究资料包">
              {cases.map((caseInfo) => {
                const selected = caseInfo.case_id === selectedCase.case_id;
                return (
                  <button
                    key={caseInfo.case_id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    disabled={disabled}
                    className={`case-select-card ${selected ? "selected" : ""}`}
                    onClick={() => setCaseId(caseInfo.case_id)}
                  >
                    <div className="case-card-top">
                      <span className="sector-pill">
                        {sectorTag(caseInfo.case_id)}
                      </span>
                      <span className={`radio-check ${selected ? "checked" : ""}`}>
                        {selected ? "✓" : ""}
                      </span>
                    </div>
                    <div className="case-card-title">{caseInfo.display_name}</div>
                    <p className="case-card-desc">{caseInfo.description}</p>
                    <div className="case-card-foot mono">
                      <span>{caseInfo.case_id}</span>
                      <span>截止 {caseInfo.default_cutoff}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-split-row">
            <label className="field">
              <span className="field-label">研究截止日期（时间锁）</span>
              <input
                type="date"
                value={cutoffDate}
                onChange={(event) => setCutoffDate(event.target.value)}
                disabled={disabled}
              />
              <small className="muted">
                晚于该日期发布的资料将被自动排除，日期不明资料降级为待确认项。
              </small>
            </label>

            <div className="field">
              <span className="field-label">分析与撰写引擎</span>
              <label
                className={`toggle-card ${
                  llmAvailable && llmEnabled ? "active" : ""
                } ${!llmAvailable ? "unavailable" : ""}`}
              >
                <div className="toggle-label">
                  <span className="toggle-title">
                    AI 增强模式
                    <span
                      className={`engine-pill ${
                        llmAvailable && llmEnabled ? "on" : "off"
                      }`}
                    >
                      {llmAvailable && llmEnabled ? "LLM + 规则" : "规则引擎"}
                    </span>
                  </span>
                  <small className="muted">
                    {llmAvailable
                      ? "大模型结合证据链撰写正文并由 Critic 复核，异常时可回退。"
                      : "未配置模型密钥，当前自动使用确定性 rule-engine 执行。"}
                  </small>
                </div>
                <input
                  type="checkbox"
                  checked={llmAvailable && llmEnabled}
                  onChange={(event) => setLlmEnabled(event.target.checked)}
                  disabled={disabled || !llmAvailable}
                />
              </label>
            </div>
          </div>

          {activeRun &&
            (activeRun.status === "queued" || activeRun.status === "running") && (
              <div className="notice">
                当前已有任务 <code className="mono">{activeRun.run_id}</code>{" "}
                正在执行，单并发保护已启用，请稍候。
              </div>
            )}

          <div className="form-actions">
            <button className="start-button" type="submit" disabled={disabled}>
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
                <polygon points="6 4 20 12 6 20 6 4" />
              </svg>
              <span>{disabled ? "分析流水线运行中…" : "启动投研分析"}</span>
            </button>

            <span className="action-meta">
              支持在线证据溯源 · Markdown / JSON 一键导出
            </span>
          </div>
        </form>
      </section>

      <aside className="panel methodology-panel">
        <div className="methodology-head">
          <h2>投研质控流水线</h2>
          <p className="muted">先证据、后结论、再复核的标准化研究流程</p>
        </div>

        <ol className="methodology-steps">
          {PIPELINE_STEPS.map((step) => (
            <li key={step.code} className="methodology-step">
              <span className="step-code mono">{step.code}</span>
              <div className="step-content">
                <div className="step-title">{step.title}</div>
                <div className="step-desc">{step.desc}</div>
              </div>
            </li>
          ))}
        </ol>

        <div className="methodology-footer">
          <div className="gov-stat">
            <span className="gov-label">原文溯源率</span>
            <strong className="mono">100%</strong>
          </div>
          <div className="gov-stat">
            <span className="gov-label">时间锁隔离</span>
            <strong>T+0 严控</strong>
          </div>
        </div>
      </aside>
    </div>
  );
}
