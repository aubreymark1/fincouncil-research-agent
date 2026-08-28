# LLM 轻量投研简报 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留时间锁和证据链，用少量相关证据驱动一次 LLM 综合分析，并在 LLM 失败时自动回退到 rule-engine。

**Architecture:** 工作台在真实 ingestion/industry 链路完成时间锁、证据定位和确定性规则后，由 compact strategy 选择最多 60 条证据，调用一次综合 LLM 输出自然语言 Claim，再由程序组合为带证据引用的 `narrative` 段落。确定性 Critic 和报告渲染继续校验来源；LLM 调用失败时 runner 重跑确定性链路。

**Tech Stack:** Python 3.11+/3.13, Pydantic, pytest, FastAPI backend, React/TypeScript/Vite, 现有 OpenAI-compatible transport。

**Spec:** `docs/superpowers/specs/2026-08-28-llm-mvp-simplification-design.md`

## Global Constraints

- 不修改已有公共字段；`ResearchReport.narrative` 仅作为有默认空列表的向后兼容扩展。
- 只使用通过时间锁和证据策略的 verified Evidence 作为 LLM 输入。
- 不联网、不修改原始资料、不编造数字、来源和实验结果。
- 工作台只支持 `food_main` 和 `bank_main`。
- 保留已有 full/E1/E2/E3 兼容路径；compact 只用于匿名工作台。
- 不修改发布、部署之外的 OJ 服务；API Key 不得写入日志或提交仓库。

---

### Task 1: 先固定模型输出兼容行为

**Files:**
- Modify: `app/model/provider.py`
- Test: `tests/core/test_model_provider.py`

**Interfaces:**
- `ModelProvider.generate_json(prompt, response_model=...)` 继续支持现有 dict 输出，并在 response model 只有一个列表字段时把裸列表兼容成该字段的对象。

**Steps:**

- [ ] 写一个传输函数直接返回 ClaimList 的裸数组，并断言 `generate_json(..., response_model=ClaimList)` 当前失败。
- [ ] 运行该单测，确认失败原因是裸数组不能作为对象校验。
- [ ] 增加最小兼容转换，不改变已有 dict、错误代码和缓存行为。
- [ ] 运行该单测和 `tests/core/test_model_provider.py`。
- [ ] 检查 diff 只包含 provider 与对应测试。

### Task 2: 增加轻量证据选择器

**Files:**
- Create: `app/agents/compact.py`
- Test: `tests/core/test_compact_analysis.py`

**Interfaces:**
- `select_compact_evidence(evidence, config, *, max_total=60, per_metric=3, per_risk=3, news_limit=6) -> list[Evidence]`
- `compact_evidence_payload(evidence) -> list[dict[str, Any]]`

**Steps:**

- [ ] 写测试证明选择器过滤非 verified/非本行业证据、按指标去重并遵守总量上限。
- [ ] 写测试证明风险规则的 trigger 和 exclude 相关证据不会被只保留一侧的逻辑丢掉。
- [ ] 运行测试，确认新选择器尚不存在而失败。
- [ ] 实现确定性关键词、类型、confidence、发布日期和 ID 排序。
- [ ] 实现最小 payload 转换，禁止把完整 SourceDocument 或大块原始文本带入 prompt。
- [ ] 运行 `pytest tests/core/test_compact_analysis.py -q`。

### Task 3: 实现一次综合 LLM 分析

**Files:**
- Create: `app/agents/compact.py` (analysis entry point if kept together)
- Create: `prompts/synthesis.md`
- Modify: `app/agents/aggregation.py`
- Modify: `app/orchestrator/graph.py`
- Modify: `app/main.py`
- Test: `tests/core/test_compact_analysis.py`
- Test: `tests/core/test_orchestrator.py`

**Interfaces:**
- `run_analysis(..., provider=..., llm_strategy="full" | "compact") -> list[Claim]`
- `run_pipeline(..., llm_strategy="full" | "compact") -> ResearchState`
- `run_research(..., llm_strategy="full" | "compact") -> ResearchReport`

**Steps:**

- [ ] 写测试：compact strategy 对 provider 只调用一次，结果能进入现有 report renderer。
- [ ] 写测试：裸数组 Claim 输出能进入 compact 分析，未知 evidence ID 被拒绝。
- [ ] 写测试：full strategy 仍保留已有节点调用和 E3 行为。
- [ ] 运行测试，确认 compact strategy 尚不存在而失败。
- [ ] 编写 synthesis prompt，明确只返回 `{"claims": [...]}`、只使用输入证据、无法判断输出 unresolved。
- [ ] 实现 compact prompt 上下文和 Claim 校验，复用现有 schemas/确定性 Critic。
- [ ] 让 graph 只在 full strategy 执行 LLM Critic，compact 只执行确定性 Critic。
- [ ] 运行相关 core/integration 单测。

### Task 4: 增加工作台 LLM 失败回退

**Files:**
- Modify: `backend/runner.py`
- Test: `tests/api/test_workbench_api.py`

**Interfaces:**
- 工作台 `ResearchRunner` 使用 compact strategy；LLM 失败后用相同 run ID 调用 rule-engine。

**Steps:**

- [ ] 写测试：模拟 ModelProviderError，断言 runner 最终成功并记录回退进度。
- [ ] 写测试：LLM 和 rule-engine 都失败时才持久化 failed。
- [ ] 运行测试确认当前 runner 没有回退行为。
- [ ] 实现只捕获 LLM 结构化/传输错误的回退，不吞掉 rule-engine 错误。
- [ ] 运行 `pytest tests/api/test_workbench_api.py -q`。

### Task 5: 接通容器模型参数

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `DEPLOYMENT.md`

**Interfaces:**
- 容器收到 `FINCOUNCIL_MODEL_TEMPERATURE`、`FINCOUNCIL_MODEL_MAX_RETRIES`、`FINCOUNCIL_MODEL_TIMEOUT_SECONDS`。

**Steps:**

- [ ] 添加默认值和示例说明，不写真实密钥。
- [ ] 运行 `docker compose config --quiet`。
- [ ] 检查配置 diff 不涉及现有 secrets/permissions 或其他服务。

### Task 6: 全量验证、线上部署和交付验收

**Files:**
- No source changes expected unless a verification failure identifies a scoped defect.

**Steps:**

- [ ] 运行 `python -m pytest -q`。
- [ ] 运行 `npm ci` 和 `npm run build` in `frontend/`。
- [ ] 本地用 mock transport 验证 compact 单调用和回退。
- [ ] 以明确文件执行 `git add`，检查 `git diff --cached`。
- [ ] 提交并推送 `feature/llm-mvp-simplification`，创建 PR 到 `main`。
- [ ] PR CI 通过后再同步到 `/opt/fincouncil`，重建后端并确认模型参数进入容器。
- [ ] 线上运行一条 `food_main` LLM 任务，确认报告、证据来源和下载链接。
- [ ] 验证 LLM 失败回退后，工作台仍可生成 rule-engine 报告。

### Task 7: 正文段落与来源气泡

**Files:**
- Modify: `app/schemas/report.py`
- Modify: `app/schemas/__init__.py`
- Modify: `app/agents/compact.py`
- Modify: `app/agents/report.py`
- Modify: `app/orchestrator/graph.py`
- Modify: `prompts/synthesis.md`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/ReportView.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/core/test_compact_analysis.py`
- Test: `tests/core/test_report.py`

**Steps:**

- [ ] 让一次 synthesis 返回适合直接阅读的自然语言 `claims`，程序将其组合为 `narrative`，每个正文段落继承 Evidence ID。
- [ ] 将正文段落写入 ResearchReport，并把段落引用纳入 evidence_index。
- [ ] 前端先展示正文段落，段落旁显示可点击的来源气泡；Claims 作为正式结论和审核详情保留。
- [ ] 运行全量 Python 测试和前端 production build。
