# FinCouncil Open Research Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 FinCouncil 升级为强制使用 LLM、可调用可信在线检索工具、展示真实运行活动并生成句子级证据引用的开放研究工作台。

**Architecture:** 保留现有时间锁、Evidence、行业规则和 Critic 管线，在其前面增加受控资料检索与 Manifest 构建层，在模型层增加标准工具调用循环，在输出层增加句子级引用，在运行层增加持久化事件和 SSE。预置双案例继续作为回归基准，在线研究作为独立实验模式上线。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、SQLite、React 18、TypeScript、Vite、SSE、OpenAI-compatible Chat Completions tool calls。

**Spec:** `docs/superpowers/specs/2026-08-30-open-research-workbench-design.md`

## Global Constraints

- 所有生产改动遵循 TDD：先写失败测试，确认失败原因，再实现。
- LLM 对每次研究都是必需依赖；模型不可用时返回 503，不允许纯规则降级。
- 时间锁、来源验证、Evidence 状态和 Critic 仍由确定性程序执行。
- 在线访问仅允许 HTTPS 白名单域名，并阻断私网、回环和云元数据地址。
- 工具事件只保存公开操作摘要，不保存 API Key、完整提示词、隐藏思维链和原始模型内部消息。
- 报告正文中的非 unresolved 句子必须绑定至少一个 Evidence ID。
- 页面采用低圆角、少卡片、连续文档流；卡片半径 4-6px，弹层不超过 8px。
- `food_main`、`bank_main` 必须继续通过现有回归测试。

---

## File Structure

### Schema and model runtime

- Create `app/schemas/run_event.py`: 运行事件模型。
- Create `app/schemas/retrieval.py`: 检索查询、命中和下载文档模型。
- Modify `app/schemas/report.py`: 句子级 `NarrativeSegment` 和 `NarrativeBlock`。
- Create `app/model/tool_types.py`: 工具定义、工具调用和模型回合结果。
- Modify `app/model/transport.py`: 支持 `messages`、`tools` 和 `tool_calls`。
- Modify `app/model/provider.py`: 保留 `generate_json`，新增受限工具调用循环。

### Retrieval and orchestration

- Create `app/retrieval/security.py`: URL 白名单、DNS/IP、重定向、MIME 和大小校验。
- Create `app/retrieval/cninfo.py`: 巨潮资讯公告搜索和下载适配器。
- Create `app/retrieval/service.py`: 强制检索、LLM 补充检索和 Manifest 构建。
- Create `app/retrieval/tool_registry.py`: 白名单工具注册和参数验证。
- Modify `app/orchestrator/graph.py`: 运行事件、在线 Manifest、句子级正文和 Critic 串联。
- Modify `backend/cases.py`: 保留预置案例，新增在线 ResearchRequest 构建入口。

### Persistence and API

- Modify `backend/db.py`: `run_events` 表和事件读写接口。
- Modify `backend/main.py`: 新建研究契约、模型门禁、事件列表和 SSE 接口。
- Modify `backend/runner.py`: 强制 ModelProvider、检索服务和事件发布。

### Frontend

- Create `frontend/src/components/CitationPopover.tsx`: 句子级来源弹层。
- Create `frontend/src/components/RunActivity.tsx`: 工具活动时间线。
- Create `frontend/src/components/QualityChecks.tsx`: 用户语言质量检查。
- Modify `frontend/src/components/NewResearch.tsx`: 开放研究表单，删除 LLM 开关。
- Modify `frontend/src/components/ReportView.tsx`: 连续正文、句子引用、隐藏空模块。
- Modify `frontend/src/components/RunProgress.tsx`: 由阶段列表迁移到事件时间线。
- Modify `frontend/src/api.ts`: 事件列表和 SSE 连接。
- Modify `frontend/src/types.ts`: 与后端新契约同步。
- Modify `frontend/src/styles.css`: 低圆角、少卡片、引用和时间线样式。

---

### Task 1: 消除本地仓库与生产服务器漂移

**Files:**
- Modify: `frontend/src/components/NewResearch.tsx`
- Review: `/opt/fincouncil/frontend/src/components/NewResearch.tsx`
- Review: `/opt/fincouncil/backend/*.py`

**Interfaces:**
- Consumes: 当前 Git 工作区和生产目录 `/opt/fincouncil`。
- Produces: 一个可重复部署且包含所有线上变更的本地工作区。

- [ ] **Step 1: 记录本地与生产状态**

Run:

```powershell
git status --short
git diff --stat
ssh quant-system-ubuntu "find /opt/fincouncil/frontend/src /opt/fincouncil/backend -type f -printf '%p %TY-%Tm-%Td %TH:%TM:%TS\n' | sort"
```

Expected: 明确列出本地未提交文件和生产文件时间，不修改任何文件。

- [ ] **Step 2: 对影响本计划的文件逐一比较**

Run:

```powershell
scp quant-system-ubuntu:/opt/fincouncil/frontend/src/components/NewResearch.tsx $env:TEMP/fincouncil-NewResearch.remote.tsx
git diff --no-index frontend/src/components/NewResearch.tsx $env:TEMP/fincouncil-NewResearch.remote.tsx
```

Expected: 识别生产中 `llmEnabled` 默认值等未进入本地仓库的差异。

- [ ] **Step 3: 将仍需保留的生产差异用 apply_patch 合入本地**

保留功能差异，不复制 `.env`、数据库、输出报告和 API Key。执行后运行：

```powershell
npm --prefix frontend run build
python -m pytest tests/api tests/core -q
```

Expected: 前端构建通过，API/core 测试无失败。

- [ ] **Step 4: Commit**

```bash
git add frontend/src backend
git commit -m "chore: reconcile workbench production drift"
```

---

### Task 2: 建立句子级证据报告契约

**Files:**
- Modify: `app/schemas/report.py`
- Modify: `app/schemas/request.py`
- Modify: `app/schemas/__init__.py`
- Modify: `tests/core/test_schemas.py`
- Modify: `tests/core/test_report.py`

**Interfaces:**
- Produces: `NarrativeSegment`, `NarrativeBlock` 和 `ResearchReport.narrative`。
- Consumed by: Task 3、Task 4、Task 12。

- [ ] **Step 1: 写失败的 Schema 测试**

```python
def test_narrative_segment_requires_evidence_for_fact():
    from pydantic import ValidationError
    from app.schemas import NarrativeSegment

    with pytest.raises(ValidationError):
        NarrativeSegment(
            segment_id="SEG-001",
            text="营业收入同比增长。",
            evidence_ids=[],
            claim_type="fact",
            status="pass",
        )


def test_unresolved_segment_may_have_no_evidence():
    from app.schemas import NarrativeSegment

    segment = NarrativeSegment(
        segment_id="SEG-002",
        text="毛利率变化仍待确认。",
        evidence_ids=[],
        claim_type="unresolved",
        status="review",
    )
    assert segment.status == "review"
```

- [ ] **Step 2: 验证测试按预期失败**

Run: `python -m pytest tests/core/test_schemas.py -k narrative_segment -v`

Expected: FAIL，原因是 `NarrativeSegment` 尚不存在。

- [ ] **Step 3: 实现新模型**

在 `app/schemas/report.py` 增加：

```python
class NarrativeSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_id: str = Field(pattern=r"^SEG-[A-Za-z0-9][A-Za-z0-9._-]*$")
    text: str = Field(min_length=1)
    evidence_ids: list[str]
    claim_type: Literal["fact", "change", "analysis", "risk", "unresolved"]
    status: Literal["pass", "review"]

    @model_validator(mode="after")
    def validate_support(self) -> "NarrativeSegment":
        if self.claim_type != "unresolved" and not self.evidence_ids:
            raise ValueError("reportable narrative segments require evidence_ids")
        if self.claim_type == "unresolved" and self.status != "review":
            raise ValueError("unresolved narrative segments must be review")
        return self


class NarrativeBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str = Field(min_length=1)
    segments: list[NarrativeSegment] = Field(min_length=1)


class NarrativeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocks: list[NarrativeBlock] = Field(min_length=1)
```

向 `ResearchReport` 增加 `narrative: list[NarrativeBlock] = Field(default_factory=list)`。
向 `ResearchRequest` 增加 `research_question: str = Field(default="根据已验证资料生成研究初稿", min_length=1)`，使旧案例保持兼容。

- [ ] **Step 4: 运行 Schema 和报告测试**

Run: `python -m pytest tests/core/test_schemas.py tests/core/test_report.py -q`

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/schemas tests/core/test_schemas.py tests/core/test_report.py
git commit -m "feat: add sentence-level evidence report schema"
```

---

### Task 3: 让 LLM 输出受验证的句子级正文

**Files:**
- Modify: `app/agents/llm.py`
- Modify: `app/agents/report.py`
- Modify: `prompts/synthesis.md`
- Modify: `tests/core/test_llm_agents.py`
- Modify: `tests/core/test_report.py`

**Interfaces:**
- Consumes: `NarrativeSegment`, `NarrativeBlock`。
- Produces: `synthesize_narrative(provider, request, claims, evidence) -> list[NarrativeBlock]`。

- [ ] **Step 1: 写失败测试，锁定 Evidence 绑定**

```python
def test_synthesis_rejects_unknown_evidence_id(fake_provider, request, evidence):
    fake_provider.response = {
        "blocks": [{
            "section": "核心判断",
            "segments": [{
                "segment_id": "SEG-001",
                "text": "收入增长。",
                "evidence_ids": ["EV-NOT-FOUND"],
                "claim_type": "fact",
                "status": "pass",
            }],
        }],
    }
    with pytest.raises(ModelProviderError, match="unknown evidence"):
        synthesize_narrative(fake_provider, request, [], evidence)
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/core/test_llm_agents.py -k synthesis -v`

Expected: FAIL，函数尚不存在。

- [ ] **Step 3: 实现结构化合成**

实现要点：

```python
def synthesize_narrative(provider, request, claims, evidence):
    result = provider.generate_json(
        build_synthesis_prompt(request, claims, evidence),
        response_model=NarrativeDraft,
        cache_key=f"narrative:{request.run_id}",
    )
    allowed = {item.evidence_id for item in evidence if item.review_status == "verified"}
    for block in result.blocks:
        for segment in block.segments:
            unknown = set(segment.evidence_ids) - allowed
            if unknown:
                raise ModelProviderError("E301 module=synthesis: unknown evidence IDs")
    return result.blocks
```

提示词必须要求一句一段 `segment`，不得输出未提供的 Evidence ID。

- [ ] **Step 4: 将正文加入报告渲染和 Markdown**

`render_report` 接收 `narrative` 参数；`render_markdown` 在每个句子末尾输出 Evidence 编号。

- [ ] **Step 5: 运行 LLM、报告和集成测试**

Run:

```bash
python -m pytest tests/core/test_llm_agents.py tests/core/test_report.py tests/integration/test_pipeline_integration.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add app/agents prompts/synthesis.md tests
git commit -m "feat: synthesize evidence-bound narrative segments"
```

---

### Task 4: 实现 ChatGPT 式句子引用

**Files:**
- Create: `frontend/src/components/CitationPopover.tsx`
- Modify: `frontend/src/components/ReportView.tsx`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/reportRendering.test.ts`

**Interfaces:**
- Consumes: `NarrativeBlock.segments[]` 和 `Evidence[]`。
- Produces: `CitationPopover`、句末引用按钮和可访问的来源浮层。

- [ ] **Step 1: 写失败的渲染契约测试**

测试样例必须断言：两个句子分别显示各自的 Evidence，不能共享整个段落来源。

```typescript
assert.deepEqual(
  citationIdsForSegment(report.narrative[0].segments[0]),
  ["EV-001"],
);
assert.deepEqual(
  citationIdsForSegment(report.narrative[0].segments[1]),
  ["EV-002", "EV-003"],
);
```

- [ ] **Step 2: 运行并确认失败**

Run: `npm --prefix frontend run test:frontend`

Expected: FAIL，`citationIdsForSegment` 或新结构尚不存在。

- [ ] **Step 3: 实现引用组件**

组件行为：

```tsx
<span className="narrative-segment">
  {segment.text}
  <CitationPopover
    evidence={segment.evidence_ids.map((id) => evidenceMap.get(id)).filter(isEvidence)}
    onOpenEvidence={onSelectEvidence}
  />
</span>
```

引用按钮显示 `[1]` 或 `来源 +2`；支持 click、Enter、Space、Escape 和焦点返回。

- [ ] **Step 4: 将正文改成连续文档流**

删除段落编号和段落底部来源行。来源必须紧跟对应句子。

- [ ] **Step 5: 运行前端测试和构建**

Run:

```bash
npm --prefix frontend run test:frontend
npm --prefix frontend run build
```

Expected: PASS，无 TypeScript 错误。

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: add inline sentence citations"
```

---

### Task 5: 清理空模块和研究质量检查文案

**Files:**
- Create: `frontend/src/components/QualityChecks.tsx`
- Modify: `frontend/src/reportUtils.ts`
- Modify: `frontend/src/components/ReportView.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/reportUtils.test.ts`

**Interfaces:**
- Produces: `presentValidationIssue(issue) -> {category, title, summary, action, tone}`。

- [ ] **Step 1: 写失败的文案映射测试**

```typescript
assert.deepEqual(presentValidationIssue(afterCutoffIssue), {
  category: "已自动处理",
  title: "资料晚于研究截止日",
  summary: "1 份资料已由时间锁自动排除，未进入正文。",
  action: null,
  tone: "success",
});
```

- [ ] **Step 2: 运行并确认失败**

Run: `npm --prefix frontend run test:frontend`

Expected: FAIL，旧实现仍返回“需要处理”。

- [ ] **Step 3: 实现分组和技术详情折叠**

分组固定为：`已自动处理`、`需要人工确认`、`尚未覆盖`。错误码和原始英文放入 `<details>`。

- [ ] **Step 4: 隐藏无数据模块并降低圆角**

当 `formalClaims.length === 0`、`formalRisks.length === 0` 或 `reviewItems.length === 0` 时不渲染对应 section。将主面板半径改为 4px，按钮和输入框 6px，来源浮层 8px；移除英文眉题、渐变头部和多余阴影。

- [ ] **Step 5: 视觉和键盘验证**

使用桌面 1440px 和手机 390px 检查；Tab 顺序依次到正文引用、质量检查技术详情和下载按钮。

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "refactor: simplify report reading and quality checks"
```

---

### Task 6: 后端强制启用 LLM

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/runner.py`
- Modify: `backend/db.py`
- Modify: `frontend/src/components/NewResearch.tsx`
- Modify: `frontend/src/components/RunProgress.tsx`
- Modify: `frontend/src/types.ts`
- Modify: `tests/api/test_workbench_api.py`

**Interfaces:**
- `CreateRunRequest` 不再包含 `llm_enabled`。
- `ResearchRunner.start` 不再接收 `llm_enabled`，始终创建 `ModelProvider`。

- [ ] **Step 1: 写失败 API 测试**

```python
def test_run_is_rejected_when_model_is_unavailable(app_env):
    client, *_ = app_env
    response = client.post("/api/runs", json={
        "case_id": "food_main",
        "cutoff_date": "2026-08-20",
    })
    assert response.status_code == 503
    assert response.json()["detail"] == "研究模型暂不可用，请稍后重试。"


def test_llm_enabled_is_not_accepted(app_env):
    client, *_ = app_env
    response = client.post("/api/runs", json={
        "case_id": "food_main",
        "cutoff_date": "2026-08-20",
        "llm_enabled": False,
    })
    assert response.status_code == 422
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/api/test_workbench_api.py -k "model_is_unavailable or llm_enabled" -v`

Expected: FAIL，当前 API 默认允许关闭 LLM。

- [ ] **Step 3: 修改后端契约和 Runner**

`CreateRunRequest` 使用 `ConfigDict(extra="forbid")`；创建任务前执行 `settings.llm_available()`；Runner 无条件创建 provider。删除数据库 `llm_enabled` 的业务依赖，旧列保留一版以兼容现有数据库。

- [ ] **Step 4: 删除前端开关**

表单不再发送 `llm_enabled`。健康检查不可用时禁用开始按钮并显示明确原因。

- [ ] **Step 5: 运行测试和构建**

```bash
python -m pytest tests/api tests/core -q
npm --prefix frontend run build
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend frontend tests/api
git commit -m "feat: require LLM for every research run"
```

---

### Task 7: 持久化结构化运行事件

**Files:**
- Create: `app/schemas/run_event.py`
- Modify: `app/schemas/__init__.py`
- Modify: `backend/db.py`
- Modify: `tests/api/test_workbench_api.py`
- Create: `tests/core/test_run_events.py`

**Interfaces:**
- Produces: `RunStore.append_event`、`RunStore.list_events`、`RunEvent`。

- [ ] **Step 1: 写失败的顺序和脱敏测试**

```python
def test_run_events_are_ordered_and_redacted(store):
    first = store.append_event("RUN-WB-ONE", kind="tool_start", title="检索公告", summary="开始", public_details={"query": "600519"})
    second = store.append_event("RUN-WB-ONE", kind="tool_result", title="检索完成", summary="找到 4 份", public_details={"count": 4})
    events = store.list_events("RUN-WB-ONE", after_sequence=0)
    assert [event["sequence"] for event in events] == [first["sequence"], second["sequence"]]
    assert "api_key" not in json.dumps(events)
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/core/test_run_events.py -v`

Expected: FAIL，事件接口尚不存在。

- [ ] **Step 3: 创建 `run_events` 表和方法**

表字段：`event_id`、`run_id`、`sequence`、`occurred_at`、`kind`、`tool_name`、`title`、`summary`、`status`、`duration_ms`、`source_ids_json`、`public_details_json`。添加唯一索引 `(run_id, sequence)`。

- [ ] **Step 4: 对 public_details 使用允许键集合**

允许键固定为：`query`、`count`、`document_count`、`evidence_count`、`excluded_count`、`provider`、`model`、`reason`。其他键拒绝写入。

- [ ] **Step 5: 运行测试并提交**

```bash
python -m pytest tests/core/test_run_events.py tests/api/test_workbench_api.py -q
git add app/schemas/run_event.py backend/db.py tests
git commit -m "feat: persist public research run events"
```

---

### Task 8: 增加事件 API、SSE 和真实管线埋点

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/runner.py`
- Modify: `app/orchestrator/graph.py`
- Modify: `tests/api/test_workbench_api.py`
- Modify: `tests/core/test_orchestrator.py`

**Interfaces:**
- Produces: `GET /api/runs/{run_id}/events`、`GET /api/runs/{run_id}/events/stream`。

- [ ] **Step 1: 写失败的事件 API 测试**

```python
def test_events_endpoint_supports_resume(app_env):
    client, store, *_ = app_env
    store.append_event("RUN-WB-ONE", kind="stage", title="准备研究", summary="开始", public_details={})
    store.append_event("RUN-WB-ONE", kind="stage", title="定位证据", summary="完成", public_details={"evidence_count": 12})
    response = client.get("/api/runs/RUN-WB-ONE/events?after_sequence=1")
    assert response.status_code == 200
    assert [item["sequence"] for item in response.json()] == [2]
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/api/test_workbench_api.py -k events_endpoint -v`

- [ ] **Step 3: 实现列表接口和 SSE**

SSE 使用 `StreamingResponse`，每条消息包含 `id: sequence`、`event: run_event` 和 JSON `data`。客户端传 `Last-Event-ID` 或 `after_sequence` 续传。

- [ ] **Step 4: 在真实模块边界发布事件**

至少发布：资料检索、Manifest 校验、时间锁、文档解析、Evidence 定位、LLM 调用、Critic、报告写入。工具开始和结束使用相同 `tool_name`，结束事件写入 `duration_ms`。

- [ ] **Step 5: 测试并提交**

```bash
python -m pytest tests/api/test_workbench_api.py tests/core/test_orchestrator.py -q
git add backend app/orchestrator tests
git commit -m "feat: stream real research activity events"
```

---

### Task 9: 前端展示 Codex 式运行活动

**Files:**
- Create: `frontend/src/components/RunActivity.tsx`
- Modify: `frontend/src/components/RunProgress.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/runEvents.test.ts`

**Interfaces:**
- Consumes: `RunEvent[]` 和 SSE `/events/stream`。
- Produces: 可展开的工具活动时间线。

- [ ] **Step 1: 写失败的事件归并测试**

```typescript
const state = reduceRunEvents([], [toolStart, toolResult]);
assert.equal(state[0].status, "success");
assert.equal(state[0].duration_ms, 840);
assert.equal(state[0].summary, "找到 18 份候选资料");
```

- [ ] **Step 2: 运行并确认失败**

Run: `npm --prefix frontend run test:frontend`

- [ ] **Step 3: 实现 SSE 连接和断线续传**

`api.ts` 创建 `subscribeRunEvents(runId, afterSequence, onEvent, onError)`；组件卸载时关闭 `EventSource`。SSE 失败时回退到每 2 秒请求事件列表。

- [ ] **Step 4: 实现时间线**

每项显示时间、中文标题、状态、摘要和耗时。仅 `tool_result/warning/error` 可展开公开详情。不显示提示词和模型原文。

- [ ] **Step 5: 测试、构建和提交**

```bash
npm --prefix frontend run test:frontend
npm --prefix frontend run build
git add frontend
git commit -m "feat: show live research tool activity"
```

---

### Task 10: 建立安全检索模型和 URL 门禁

**Files:**
- Create: `app/schemas/retrieval.py`
- Create: `app/retrieval/__init__.py`
- Create: `app/retrieval/security.py`
- Create: `tests/retrieval/test_security.py`
- Modify: `backend/config.py`

**Interfaces:**
- Produces: `SearchQuery`、`SearchHit`、`RetrievedDocument`、`validate_public_url`。

- [ ] **Step 1: 写失败的 SSRF 测试**

```python
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "https://169.254.169.254/latest/meta-data",
    "https://10.0.0.8/internal",
])
def test_private_targets_are_rejected(url):
    with pytest.raises(RetrievalSecurityError):
        validate_public_url(url, allowed_hosts={"www.cninfo.com.cn"})
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/retrieval/test_security.py -v`

- [ ] **Step 3: 实现 URL、DNS 和响应门禁**

仅允许 `https`；最终主机必须在白名单；DNS 解析到私网、回环、链路本地或保留地址时拒绝；每次重定向重新校验。下载限制 30 MB，允许 MIME 为 PDF、HTML、纯文本。

`app/schemas/retrieval.py` 定义：

```python
class SearchQuery(BaseModel):
    subject: str = Field(min_length=1)
    ticker: str | None = None
    query: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date
    categories: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    title: str
    source_url: HttpUrl
    publisher: str
    published_at: date
    source_type: Literal["annual_report", "interim_report", "announcement", "regulation", "company_release"]


class RetrievedDocument(SearchHit):
    downloaded_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_path: str
    review_status: Literal["verified", "pending", "rejected"]
```

- [ ] **Step 4: 增加配置**

`Settings` 增加：`retrieval_allowed_hosts`、`retrieval_max_documents=30`、`retrieval_max_bytes=31457280`、`retrieval_timeout_seconds=20`、`max_tool_calls=6`。

- [ ] **Step 5: 测试并提交**

```bash
python -m pytest tests/retrieval/test_security.py -q
git add app/retrieval app/schemas/retrieval.py backend/config.py tests/retrieval
git commit -m "feat: add secure retrieval boundary"
```

---

### Task 11: 实现巨潮资讯检索、下载和 Manifest 构建

**Files:**
- Create: `app/retrieval/cninfo.py`
- Create: `app/retrieval/service.py`
- Create: `tests/retrieval/test_cninfo.py`
- Create: `tests/retrieval/test_service.py`
- Modify: `backend/cases.py`

**Interfaces:**
- Produces: `CninfoConnector.search_filings`、`RetrievalService.prepare_online_request`。

- [ ] **Step 1: 写失败的响应解析测试**

将一份脱敏的巨潮公告查询响应保存为 `tests/fixtures/cninfo_announcements.json`，测试：

```python
def test_cninfo_result_maps_to_search_hit(load_fixture):
    hits = parse_cninfo_results(load_fixture("cninfo_announcements.json"))
    assert hits[0].publisher == "巨潮资讯"
    assert hits[0].published_at.isoformat() == "2026-04-17"
    assert hits[0].source_url.startswith("https://static.cninfo.com.cn/")
```

- [ ] **Step 2: 实现公告查询和下载**

连接器将公司名称或股票代码、日期范围和公告类别转换为巨潮公告查询请求；下载前后均经过 `validate_public_url`。响应 URL 必须属于 `www.cninfo.com.cn` 或 `static.cninfo.com.cn`。

- [ ] **Step 3: 实现去重和 Manifest**

按最终 URL 和 SHA-256 去重，将文件保存到 `outputs/retrieval/{run_id}/raw/`，Manifest 保存到 `outputs/retrieval/{run_id}/manifest.json`。每条记录写入 `published_at`、`downloaded_at`、publisher、source_type、review_status 和 local_path。

- [ ] **Step 4: 构建在线 ResearchRequest**

```python
def prepare_online_request(subject, ticker, industry_id, question, cutoff_date, run_id):
    documents = mandatory_discovery(...)
    manifest_path = write_manifest(run_id, documents)
    return ResearchRequest(
        run_id=run_id,
        company_name=subject,
        industry_id=industry_id,
        research_question=question,
        cutoff_date=cutoff_date,
        source_manifest_path=str(manifest_path),
        output_dir=str(outputs_dir / "reports" / run_id),
    )
```

- [ ] **Step 5: 运行检索测试并提交**

```bash
python -m pytest tests/retrieval -q
git add app/retrieval backend/cases.py tests/retrieval
git commit -m "feat: retrieve authoritative company filings"
```

---

### Task 12: 扩展模型 Transport 并实现 LLM 工具调用循环

**Files:**
- Create: `app/model/tool_types.py`
- Modify: `app/model/transport.py`
- Modify: `app/model/provider.py`
- Create: `app/retrieval/tool_registry.py`
- Modify: `backend/runner.py`
- Modify: `tests/core/test_model_transport.py`
- Modify: `tests/core/test_model_provider.py`
- Create: `tests/retrieval/test_tool_registry.py`

**Interfaces:**
- Produces: `ModelProvider.run_with_tools(messages, tools, dispatcher, response_model, max_tool_calls)`。

- [ ] **Step 1: 写失败的工具回合测试**

```python
def test_provider_executes_whitelisted_tool_then_returns_json():
    transport = FakeToolTransport([
        ToolTurn(tool_calls=[ToolCall(id="call-1", name="search_company_filings", arguments={"ticker": "600519"})]),
        ToolTurn(content='{"blocks": []}'),
    ])
    result = provider.run_with_tools(...)
    assert dispatcher.calls == [("search_company_filings", {"ticker": "600519"})]
    assert result == {"blocks": []}
```

再测试未知工具、非法参数、超过 6 次调用和工具异常。

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/core/test_model_transport.py tests/core/test_model_provider.py -k tool -v`

- [ ] **Step 3: 扩展 Chat Completions Transport**

请求体支持 `messages`、`tools` 和 `tool_choice="auto"`；解析 `choices[0].message.tool_calls`。保留现有 `generate_json` 路径，避免破坏已有 agents。

`app/model/tool_types.py` 定义：

```python
class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolTurn(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
```

- [ ] **Step 4: 实现白名单 Dispatcher**

`ToolRegistry` 只注册设计说明中的四个工具；参数先通过 Pydantic 模型校验，再调用实现。工具结果限制在 32 KB JSON，超长文本只返回摘要和 source IDs。

- [ ] **Step 5: 在 Runner 中执行强制检索和补充检索**

先运行 `mandatory_discovery`，再让 LLM 根据研究问题和 Evidence 缺口调用最多 6 次工具，最后生成 Narrative。

- [ ] **Step 6: 真实模型能力门禁**

在 staging 使用当前配置模型执行一次只读 `search_company_filings` 工具探针。必须观察到标准 `tool_calls` 字段和合法 JSON 最终输出；否则切换到支持工具调用的模型后再上线。

- [ ] **Step 7: 测试并提交**

```bash
python -m pytest tests/core/test_model_transport.py tests/core/test_model_provider.py tests/retrieval -q
git add app/model app/retrieval backend/runner.py tests
git commit -m "feat: allow LLM to call trusted research tools"
```

---

### Task 13: 开放在线研究表单并完成端到端上线

**Files:**
- Modify: `backend/main.py`
- Modify: `frontend/src/components/NewResearch.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `tests/api/test_workbench_api.py`
- Create: `tests/integration/test_online_research.py`
- Modify: `DEPLOYMENT.md`

**Interfaces:**
- Consumes: 在线 ResearchRequest、事件 SSE、强制 LLM 和检索工具。
- Produces: 从未预置公司输入到报告生成的完整用户链路。

- [ ] **Step 1: 写失败的在线研究 API 测试**

```python
def test_create_online_research_requires_subject_question_and_cutoff(client):
    response = client.post("/api/runs", json={
        "source_mode": "authoritative_online",
        "subject": "贵州茅台",
        "ticker": "600519",
        "research_question": "分析收入质量、渠道库存和主要风险",
        "cutoff_date": "2026-08-20",
    })
    assert response.status_code == 202
    assert response.json()["source_mode"] == "authoritative_online"
```

- [ ] **Step 2: 扩展 API 和数据库运行元数据**

保存 `subject`、ticker、research_question、source_mode 和 industry_id。预置案例仍允许通过 `source_mode="verified_case"` 加 case_id 创建。

- [ ] **Step 3: 实现前端表单**

默认显示公司名称/代码、研究问题和截止日期。预置案例放入“使用验证案例”次级入口。删除 AI 增强开关。

- [ ] **Step 4: 端到端测试**

集成测试使用本地 HTTP fixture server 和 FakeToolTransport，不访问真实互联网。断言：检索事件出现、截止日后文档被排除、报告句子绑定 Evidence、下载成功。

- [ ] **Step 5: 全量回归**

```bash
python -m pytest -q
npm --prefix frontend run test:frontend
npm --prefix frontend run build
docker compose config --quiet
```

Expected: 全部通过；双预置案例测试无回归。

- [ ] **Step 6: Staging 验收**

使用一个未预置 A 股代码运行：确认权威公告检索、日期过滤、工具时间线、句子引用、质量检查和报告下载。检查事件 JSON 不含 `api_key`、`prompt`、`messages` 字段。

- [ ] **Step 7: 小流量生产发布**

生产环境先限制：单 IP 每日 3 次在线研究、单次最多 30 文档、最多 6 次工具调用、全局单并发。保留双案例为无需在线检索的稳定演示入口。

- [ ] **Step 8: Commit**

```bash
git add backend frontend tests DEPLOYMENT.md
git commit -m "feat: launch experimental online research workbench"
```

---

## Final Verification Gate

- [ ] `python -m pytest -q` 全量通过。
- [ ] `npm --prefix frontend run test:frontend` 通过。
- [ ] `npm --prefix frontend run build` 通过。
- [ ] `docker compose config --quiet` 通过。
- [ ] 生产模型通过真实 `tool_calls` 能力探针。
- [ ] 未预置 A 股公司端到端运行成功。
- [ ] 每个正式正文句子至少有一个可打开的 Evidence。
- [ ] 空的正式结论、风险、待确认模块不再显示。
- [ ] 截止日后资料显示为“已自动排除”，不是红色错误。
- [ ] LLM 无法被前端或 API 关闭。
- [ ] SSE 断线续传不丢事件、不重复事件。
- [ ] 工具活动不包含密钥、完整提示词、隐藏思维链或模型原始消息。
- [ ] 双案例报告和下载功能无回归。
