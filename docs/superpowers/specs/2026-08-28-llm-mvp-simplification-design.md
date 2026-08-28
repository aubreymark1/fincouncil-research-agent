# LLM 轻量投研简报 MVP 设计

## 目标

在 2026-08-30 20:00 报告截止前，交付一条稳定的线上链路：固定行业资料包经过时间锁和证据筛选后，由 LLM 完成一次综合分析并生成可读的投研结论；页面继续支持结论旁的证据来源气泡。LLM 失败时必须自动回退到确定性的 rule-engine 报告，不能把整个工作台变成失败页。

## 范围与不变量

- 保留 `ResearchRequest`、`Evidence`、`Claim` 和旧 `ResearchReport` 字段；为实现最终可读报告，向后兼容地增加 `ResearchReport.narrative` 正文段落列表。
- 保留 manifest 校验、时间锁、行业配置、证据状态、确定性指标规则和确定性 Critic。
- LLM 只能使用程序筛选后传入的 verified Evidence，不联网、不编造数字、不生成来源之外的事实。
- 只支持当前已经验证的 `food_main` 和 `bank_main` 资料包。
- 本次不接实时网页搜索，不实现多轮搜索、不重做 E1/E2/E3 实验链路。

## 方案

### 1. 轻量证据选择

在 `app/agents/` 增加一个小型选择器，对已经通过时间锁和证据策略的证据做确定性压缩：

- 每个 required/optional 指标按关键词和允许的 evidence type 匹配，默认最多保留 3 条；
- 每个风险规则分别保留触发信号和排除信号的相关证据，默认最多保留 3 条；
- 新闻/政策通道保留最多 6 条相关证据；
- 去重后全局最多 60 条；
- 排序优先使用行业/指标关键词命中、证据 confidence、较新的发布日期和稳定的 evidence ID；
- 没有被选择的证据仍保留在 `state.evidence`，只是不送入 LLM。

选择器输出只包含 LLM 所需的简短字段：`evidence_id`、`fact_text`、`quote`、`published_at`、`page`、`section`、`locator`、`company_name`、`industry_id`、`evidence_type` 和 `confidence`。

### 2. 单次综合分析

新增综合提示词和入口函数。单次调用覆盖基本面、行业事件、风险和未决项，要求 LLM 输出适合直接阅读的完整 Claim 句子；程序再将这些句子组合为面向用户的连贯正文，同时保留现有 `Claim` 列表作为下游核验接口：

```json
{
  "claims": [
    {
      "claim_id": "CL-...",
      "text": "...",
      "claim_type": "analysis",
      "risk_severity": null,
      "evidence_ids": ["EV-..."],
      "calculation": null,
      "confidence": 0.8,
      "industry_metric_ids": ["..."],
      "status": "pass"
    }
  ]
}
```

综合分析入口负责：

- 严格解析 `claims`，并在模型未提供正文时组合 `narrative` 段落；
- 兼容模型偶尔返回裸数组的情况，并转换为 `{"claims": [...]}`；
- 拒绝不存在的 evidence ID、未知指标、无证据的非 unresolved 结论和不合法风险结论；
- 对风险状态、风险等级、指标归属和触发/排除信号做最小必要校验；
- 让后续确定性 Critic 和 `render_report` 继续执行。

工作台默认使用 `llm_strategy="compact"`：一次综合分析后只执行确定性 Critic，不再额外调用 LLM Critic。保留 `llm_strategy="full"` 作为已有实验/兼容路径，避免改变 E3 测试含义。

### 3. 失败回退

`backend/runner.py` 的工作台执行流程在 compact LLM 调用发生 `ModelProviderError` 或结构化输出错误时：

1. 记录进度“LLM 增强失败，切换规则引擎”；
2. 用同一个 run ID、同一资料包和 cutoff 重新运行 `model_provider=None` 的 rule-engine；
3. 回退成功则运行状态为 success，报告可下载，LLM 失败只体现在进度记录；
4. 只有 rule-engine 也失败时才把运行标记为 failed。

这样 LLM 是展示亮点和增强层，时间锁、证据链和确定性规则仍然是可靠性底座。

## 线上配置

容器必须显式传递 `FINCOUNCIL_MODEL_TEMPERATURE`、`FINCOUNCIL_MODEL_MAX_RETRIES` 和 `FINCOUNCIL_MODEL_TIMEOUT_SECONDS`。演示环境使用 temperature 0、max retries 1、timeout 120 秒，避免 `.env` 已设置但容器未收到的问题。

## 验收标准

- 单元测试覆盖：裸数组兼容、未知 evidence ID 拒绝、选择器上限/去重、风险证据同时保留触发和排除信号、LLM 失败后 rule-engine 回退。
- 现有全量 Python 测试全部通过。
- 前端 production build 通过。
- 本地或线上至少完成一条 `food_main` LLM 成功报告；报告正文有自然语言结论，结论点击来源气泡能打开原始证据。
- 人为模拟 LLM 失败时，工作台能得到 rule-engine 报告。
- 线上不输出 API Key，不影响 OJ 和其他服务。
