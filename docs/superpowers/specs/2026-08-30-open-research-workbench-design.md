# FinCouncil 开放研究工作台设计说明

## 目标

将当前双预置案例工作台升级为可输入 A 股公司或股票代码、由 LLM 调用可信检索工具、实时展示研究活动，并生成句子级证据引用的在线研究工作台。

## 产品边界

- 第一阶段在线检索仅覆盖 A 股公司公告、定期报告、监管政策和公司投资者关系页面。
- 预置的 `food_main`、`bank_main` 继续保留，作为稳定演示和回归基准。
- 新增能力标记为“实验性在线研究”，不宣称已经完成原报告中的大样本验证。
- LLM 每次研究必须启用；时间锁、来源验证、去重和 Critic 继续由确定性程序执行。
- 页面展示工具活动和结果摘要，不展示隐藏思维链、系统提示词、API Key 或原始模型内部消息。
- 不提供自动交易、目标价、真实账户连接和收益承诺。

## 总体架构

```text
用户输入公司/代码、研究问题、截止日期
  -> 强制检索公司公告和定期报告
  -> LLM 识别信息缺口并调用补充检索工具
  -> 下载、去重、校验发布日期和来源等级
  -> 生成本次运行的 Source Manifest
  -> 时间锁、解析、Evidence 定位
  -> LLM 生成句子级证据绑定的研究正文
  -> Critic 和行业规则检查
  -> 报告、证据浮层、质量检查、运行活动时间线
```

检索执行发生在后端工具层。LLM 只能选择白名单工具和参数，不能直接访问任意 URL。

## 核心数据契约

### 创建研究

```python
class CreateRunRequest(BaseModel):
    subject: str
    ticker: str | None = None
    industry_id: str | None = None
    research_question: str
    cutoff_date: date
    source_mode: Literal["verified_case", "authoritative_online"]
    case_id: str | None = None
```

`llm_enabled` 从接口中删除。服务端在模型不可用时返回 `503`，不会生成纯规则替代报告。

### 句子级引用

```python
class NarrativeSegment(BaseModel):
    segment_id: str
    text: str
    evidence_ids: list[str]
    claim_type: Literal["fact", "change", "analysis", "risk", "unresolved"]
    status: Literal["pass", "review"]

class NarrativeBlock(BaseModel):
    section: str
    segments: list[NarrativeSegment]
```

每个非 `unresolved` 句子必须至少关联一个 `EV-` Evidence。前端不得根据段落来源自行猜测句子来源。

### 运行活动

```python
class RunEvent(BaseModel):
    event_id: str
    run_id: str
    sequence: int
    occurred_at: datetime
    kind: Literal["stage", "tool_start", "tool_result", "warning", "error"]
    tool_name: str | None
    title: str
    summary: str
    status: Literal["running", "success", "warning", "failed"]
    duration_ms: int | None
    source_ids: list[str]
    public_details: dict[str, str | int | float | bool]
```

`public_details` 只允许通过显式白名单写入。提示词、密钥、完整模型消息不允许进入事件表。

### 检索工具

首批工具固定为：

- `search_company_filings(company, ticker, start_date, end_date, categories)`
- `search_regulations(industry, query, start_date, end_date)`
- `fetch_authoritative_document(source_url)`
- `inspect_evidence_gap(metric_ids)`

工具返回 `SearchHit` 或 `RetrievedDocument`，包含来源 URL、发布机构、发布日期、下载时间、SHA-256、来源等级和本地路径。

## 检索策略

1. 系统首先强制调用 `search_company_filings`，保证财报和公告不会因为 LLM 判断失误而缺失。
2. 初步 Evidence 建成后，将缺失指标和研究问题交给 LLM。
3. LLM 可在最多 6 次工具调用内补充检索。
4. 只有通过白名单、发布日期校验、内容类型检查、大小限制和 SHA-256 去重的文档才能进入 Manifest。
5. 截止日期后的资料仍保存审计记录，但不得进入正文。

## 模型策略

- 启动研究前检查模型配置和工具调用能力。
- 模型必须支持标准 `tool_calls` 和结构化 JSON 输出。
- 当前模型若不能稳定返回工具调用，部署时必须切换到已通过验收的模型，不允许用文本正则模拟工具调用。
- 模型调用失败按现有重试策略执行；最终失败后任务标记失败，不降级成纯规则报告。
- 时间锁、Evidence 状态、行业规则和 Critic 的确定性检查保持不变。

## 前端信息架构

### 新建研究

- 公司名称或股票代码
- 研究问题
- 研究截止日期
- 资料范围：权威在线资料或预置验证案例
- 删除 AI 增强开关
- 模型不可用时禁用“开始研究”，直接显示原因

### 运行页面

- 主区域显示研究活动时间线
- 工具项可展开查看查询摘要、来源数量、耗时和公开错误
- 顶部显示当前阶段、累计资料数和 Evidence 数
- 使用 SSE 接收事件；断线后通过最后 `sequence` 自动续传

### 报告页面

- 正文采用连续文档流，卡片圆角统一降到 4-6px
- 引用标记紧跟句子，点击后显示来源弹层
- 空的正式结论、风险和待确认模块不渲染
- “校验问题”改名为“研究质量检查”
- 主界面使用中文解释；内部错误码和英文原文放入折叠的技术详情
- 时间锁自动排除属于成功状态，不显示为红色错误

## 安全与资源控制

- 网络访问仅允许 `https` 和配置的域名白名单。
- 拒绝私网、回环、链路本地、云元数据地址和重定向到非白名单域名的请求。
- 单文档上限 30 MB，单次运行最多 30 份文档，LLM 工具调用最多 6 次。
- 下载设置连接和读取超时，校验 MIME、文件签名和最终 URL。
- 按 IP 设置创建任务频率、每日在线检索次数和并发限制。
- 搜索结果和下载文件按查询及 SHA-256 缓存，减少成本和重复访问。

## 上线顺序

1. 句子级引用和报告界面整理。
2. 强制 LLM 和模型可用性门禁。
3. 结构化运行事件和 SSE 时间线。
4. 权威公告检索和 Manifest 自动构建。
5. LLM 补充检索工具循环。
6. 小流量开放实验性在线研究。

## 验收标准

- 任意一条事实、变化、分析或风险句子均可回溯至少一个 Evidence。
- 无 Evidence 的句子只能标记为 `unresolved/review`，不能进入正式正文。
- 前端和 API 均无法提交关闭 LLM 的研究任务。
- 模型不可用时任务不会启动。
- 运行页面能看到真实工具事件、耗时、来源数量和错误摘要。
- 事件中不出现密钥、完整提示词和隐藏思维链。
- 输入一个未预置的 A 股代码后，可以检索权威公告、建立 Manifest、应用时间锁并生成报告。
- 预置食品饮料和银行案例仍通过现有回归测试。
