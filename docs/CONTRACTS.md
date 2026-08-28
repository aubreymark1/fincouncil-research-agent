# 公共接口契约

> 本文件由 A 维护。B/C/D 可以提出修改建议，但不得直接改变公共字段。  
> 所有模块必须依赖这里定义的输入输出，不得创建同名但结构不同的数据模型。

## 一、公共约定

- 日期统一使用 YYYY-MM-DD；
- 时间统一使用 ISO 8601；
- 文件编码统一使用 UTF-8；
- 金额保留原始单位，同时记录 normalized_unit；
- 比率内部使用小数，展示层再转换为百分比；
- 所有 ID 使用稳定前缀；
- 无法确认的数据使用 null，不使用空字符串代替；
- 错误通过 ValidationIssue 返回，不静默忽略。

ID 前缀：

~~~text
RUN-       运行
DOC-       资料
CHUNK-     文本块
EV-        证据
CL-        结论
ISSUE-     检查问题
~~~

## 二、ResearchRequest

~~~python
class ResearchRequest(BaseModel):
    run_id: str
    company_name: str
    ticker: str | None
    industry_id: str
    cutoff_date: date
    comparison_start: date | None
    comparison_end: date | None
    source_manifest_path: str
    output_dir: str
~~~

必须校验：

- cutoff_date 存在；
- industry_id 对应配置文件存在；
- source_manifest_path 存在；
- output_dir 位于项目 outputs 目录；
- comparison_start 不晚于 comparison_end。

## 三、SourceDocument

~~~python
class SourceDocument(BaseModel):
    doc_id: str
    title: str
    source_type: str
    publisher: str
    source_url: str | None
    local_path: str
    published_at: date | None
    event_date: date | None
    retrieved_at: datetime
    company_name: str | None
    industry_id: str | None
    trust_level: int
    content_hash: str
    review_status: Literal[
        "formal",
        "background",
        "pending_date",
        "red_team",
        "rejected"
    ]
~~~

source_type 建议：

~~~text
annual_report
interim_report
announcement
policy
news
market_data
company_release
other
~~~

## 四、TextChunk

~~~python
class TextChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    page: int | None
    section: str | None
    paragraph_index: int | None
    char_start: int | None
    char_end: int | None
~~~

要求：

- text 不能为空；
- 必须保留 doc_id；
- PDF 能获取页码时必须填写 page；
- chunk 不得跨越两个文档。

## 五、Evidence

~~~python
class Evidence(BaseModel):
    evidence_id: str
    doc_id: str
    chunk_id: str
    fact_text: str
    quote: str
    published_at: date
    page: int | None
    section: str | None
    locator: str
    company_name: str | None
    industry_id: str | None
    evidence_type: str
    confidence: float
    review_status: Literal["verified", "pending", "rejected"]
~~~

强制规则：

- formal Evidence 必须有 published_at；
- quote 不得由模型改写；
- locator 必须能让人工找到原文；
- cutoff_date 之后的 Evidence 直接 rejected；
- pending 和 rejected Evidence 不得支撑正文关键结论；
- `published_at`、`company_name`、`industry_id` 必须从对应 `SourceDocument` 复制，不得从文本猜测；
- 关键词定位产生的 Evidence 默认 `review_status="pending"`，只能经人工或明确规则确认后改为 `verified`；
- `evidence_type` 由调用方按分析通道显式提供，推荐值为 `financial`、`operating`、`policy`、`news`、`company_release`、`market_data`、`other`；不得使用含义模糊的 `keyword_match` 作为正式类型；
- `confidence` 表示定位匹配置信度，不代表事实真实性；第一版关键词精确命中的默认值为 0.5。

## 六、IndustryConfig

~~~python
class MetricRule(BaseModel):
    metric_id: str
    display_name: str
    keywords: list[str]
    evidence_types: list[str]
    required: bool
    evidence_requirement: Literal["single", "multiple"]
    missing_action: Literal["warn", "review", "reject"]

class RiskRule(BaseModel):
    risk_id: str
    display_name: str
    trigger_description: str
    trigger_terms: list[str]
    exclude_terms: list[str]
    metric_ids: list[str]
    required_evidence_types: list[str]
    severity: Literal["low", "medium", "high"]

class IndustryConfig(BaseModel):
    industry_id: str
    display_name: str
    required_metrics: list[MetricRule]
    event_taxonomy: list[str]
    risk_rules: list[RiskRule]
    report_sections: list[str]
    retrieval_keywords: list[str]
~~~

要求：

- required_metrics 不为空；
- metric_id 在单个配置中唯一；
- report_sections 不为空；
- 食品饮料和银行配置必须有实质差异；
- risk_id 在单个配置中唯一；
- 每个 MetricRule.evidence_types 非空，且值属于 Evidence.evidence_type 词表；
- 每个 RiskRule.trigger_terms 非空，用于表达可触发该风险的方向/比较/明确信号，避免无方向关键词误触发；
- RiskRule.exclude_terms 用于表达否定/已解除/已缓解信号，命中时不得触发该风险；
- 每个 RiskRule.metric_ids 不为空，且必须引用同一 IndustryConfig.required_metrics 中存在的 metric_id；
- RiskRule.required_evidence_types 与 Evidence.evidence_type 使用同一套类型词表。

### 指标口径约定（食品饮料）

- `inventory` 专指财务存货（资产负债表存货科目），`evidence_types` 只允许 `["financial"]`，`evidence_requirement="single"`；
- `inventory` 的 `keywords` 不得包含裸关键词 `库存` 或 `动销`，避免把 `库存量`、`库存股`、`动销` 等经营/渠道口径子串混入财务存货口径；
- 新增 optional 指标 `inventory_volume`，专指实物库存量（如产销量表中的期末库存量、产成品库存量，单位吨/件等），`evidence_types` 只允许 `["operating"]`，`required=false`；关键词至少包含 `库存量`、`期末库存量`、`产成品库存量`；
- 新增 optional 指标 `channel`，专指渠道库存、经销商库存、动销等渠道流转状态，`evidence_types` 允许 `["operating", "company_release", "news"]`，`required=false`；
- `动销`、`渠道库存`、`经销商库存` 明确归入 `channel`，不得归入 `inventory` 或 `inventory_volume`；
- 任何模块不得用裸关键词 `库存`/`动销` 同时覆盖多个指标；关键词匹配必须与 `evidence_types` 同时生效。

## 七、Claim

~~~python
class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: Literal[
        "fact",
        "change",
        "analysis",
        "risk",
        "unresolved"
    ]
    risk_severity: Literal["low", "medium", "high"] | None
    evidence_ids: list[str]
    calculation: str | None
    confidence: float
    industry_metric_ids: list[str]
    status: Literal["draft", "pass", "review", "reject"]
~~~

规则：

- fact、change、analysis 和 risk 必须有 evidence_ids；
- 精确数字必须有 evidence 或 calculation；
- unresolved 可以没有证据，但必须说明缺失内容；
- report 只能直接使用 pass Claim；
- review Claim 进入待人工确认章节；
- claim_type=risk 时 risk_severity 必填，并从 RiskRule.severity 复制；
- 风险 Claim 的 industry_metric_ids 必须来自 RiskRule.metric_ids；
- fact、change、analysis Claim 不得设置 risk_severity。

## 八、ValidationIssue

~~~python
class ValidationIssue(BaseModel):
    issue_id: str
    check_name: str
    severity: Literal["info", "warning", "error", "critical"]
    issue_type: str
    message: str
    claim_id: str | None
    evidence_id: str | None
    report_section: str | None
    rerun_required: bool
    human_confirmation_required: bool
    status: Literal["open", "resolved", "accepted_risk"]
~~~

critical 示例：

- 使用截止日期之后的证据；
- 编造来源；
- 关键数字与原文不一致；
- 正文关键结论没有证据。

## 九、ResearchReport

~~~python
class ReportBlock(BaseModel):
    section: str
    text: str
    evidence_ids: list[str]

class ResearchReport(BaseModel):
    run_id: str
    company_name: str
    industry_id: str
    cutoff_date: date
    summary: list[str]
    narrative: list[ReportBlock]
    claims: list[Claim]
    risks: list[Claim]
    unresolved_items: list[Claim]
    evidence_index: list[Evidence]
    validation_issues: list[ValidationIssue]
    generated_at: datetime
    report_version: str
~~~

输出文件：

~~~text
outputs/reports/{run_id}/report.json
outputs/reports/{run_id}/report.md
outputs/logs/{run_id}/run_metadata.json
~~~

JSON/Markdown 分流约定：

- `claims` 和 `risks` 可以保留 status=review 的 Claim，供 UI 与 Markdown 放入“待人工确认”；
- `narrative` 是面向用户的自然语言正文段落；每个有事实判断的段落必须绑定报告内可验证的 Evidence ID；
- 只有 status=pass 的 Claim 可以进入正式正文和正式风险章节；
- `unresolved_items` 只放 claim_type=unresolved；
- evidence_index 收录报告内 Claim 或 narrative 实际引用且 review_status=verified 的 Evidence。

## 十、RunMetadata

~~~python
class RunMetadata(BaseModel):
    run_id: str
    mode: str
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "success", "partial", "failed"]
    model_provider: str
    model_name: str
    prompt_versions: dict[str, str]
    input_hashes: dict[str, str]
    module_versions: dict[str, str]
    errors: list[str]
~~~

`mode` 记录本次运行的实验模式，取值为 `rule-engine`、`E1`、`E2` 或 `E3`。默认 `rule-engine` 保持现有确定性链路；E1/E2/E3 为实验模式，必须显式提供模型，未提供模型时不得用 rule-engine 伪造实验结果。

## 十一、模块函数契约

### B 模块

~~~python
load_manifest(path: str) -> list[SourceDocument]

validate_manifest(
    documents: list[SourceDocument]
) -> list[ValidationIssue]

extract_pdf(
    document: SourceDocument
) -> list[TextChunk]

extract_html(
    document: SourceDocument
) -> list[TextChunk]

chunk_text(
    chunks: list[TextChunk],
    max_chars: int
) -> list[TextChunk]

locate_evidence(
    chunks: list[TextChunk],
    keywords: list[str],
    *,
    documents: list[SourceDocument],
    evidence_type: str
) -> list[Evidence]
~~~

### C 模块

~~~python
load_industry_config(
    industry_id: str
) -> IndustryConfig

build_industry_checklist(
    config: IndustryConfig
) -> list[str]

check_required_metrics(
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument]
) -> list[ValidationIssue]

apply_risk_rules(
    evidence: list[Evidence],
    config: IndustryConfig
) -> list[Claim]
~~~

### A 模块

~~~python
apply_time_lock(
    documents: list[SourceDocument],
    cutoff_date: date
) -> tuple[list[SourceDocument], list[ValidationIssue]]

run_analysis(
    request: ResearchRequest,
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument]
) -> list[Claim]

run_critic(
    request: ResearchRequest,
    claims: list[Claim],
    evidence: list[Evidence],
    config: IndustryConfig
) -> list[ValidationIssue]

render_report(
    request: ResearchRequest,
    claims: list[Claim],
    evidence: list[Evidence],
    issues: list[ValidationIssue]
) -> ResearchReport

run_research(
    request: ResearchRequest
) -> ResearchReport
~~~

### D 模块

~~~python
evaluate_report(
    report: ResearchReport,
    gold_path: str
) -> dict[str, float]

run_experiment(
    experiment_id: str,
    request: ResearchRequest
) -> dict

run_red_team(
    request: ResearchRequest,
    fixture_dir: str
) -> list[ValidationIssue]

build_charts(
    experiment_results: list[dict]
) -> list[str]

show_report(
    report_path: str
) -> None
~~~

## 十二、跨模块数据依赖约定

### Evidence 定位

- `documents` 是必填 keyword-only 参数；按 `doc_id` 为 TextChunk 补齐 SourceDocument 元数据；
- chunk 找不到对应文档、文档缺少 published_at 或 evidence_type 为空时必须明确失败，不得跳过或编造；
- evidence_type 由调用方按本轮检索/分析通道显式传入；
- 自动关键词匹配的 review_status 固定为 pending。

### multiple 独立来源

- 仅不同 doc_id 不足以证明独立；
- check_required_metrics 与 run_analysis 必须接收 documents；
- 第一版独立来源要求至少两个不同 publisher，且 content_hash 也不同；
- 无法确认独立性时输出 ValidationIssue 或 unresolved Claim，不得标记 pass。

### RiskRule 到 Claim

- RiskRule.metric_ids 负责声明观察指标；
- Claim.industry_metric_ids 从 RiskRule.metric_ids 复制；
- Claim.risk_severity 从 RiskRule.severity 复制。

## 十三、错误处理

统一错误代码：

~~~text
E100 资料文件不可用（不存在、损坏、不支持、无法解密、无法解析或无可提取文本）
E101 manifest 字段缺失
E102 公开日期无法解析
E103 资料晚于 cutoff
E200 配置文件不存在
E201 配置校验失败
E202 必查指标缺失
E300 模型调用失败
E301 模型输出无法解析
E400 Claim 缺少证据
E401 数字与证据冲突
E402 来源无法定位
E500 报告生成失败
E600 实验输入不一致
~~~

模块不得只抛出模糊的 Exception。CLI 层需要输出错误代码、模块、文件和建议动作。

## 十四、接口变更流程

1. 提出人在 task_board 新建 CONTRACT-CHANGE 任务；
2. 说明原因、字段变化和受影响模块；
3. A 修改本文件和 Schema；
4. B/C/D 在各自分支更新代码；
5. 四个模块测试全部通过；
6. A 合并；
7. D 记录需要重新运行的实验。

没有完成以上流程，不得私自改公共字段。

## 十五、已记录的 CONTRACT-CHANGE

| 变更 ID | 日期 | 变更内容 | 原因 | 受影响模块 | 实施说明 |
|---|---|---|---|---|---|
| CONTRACT-CHANGE-001 | 2026-08-25 | 扩大 E100 语义，覆盖资料不可用的完整错误集合 | 与 B-002 PDF 提取的统一错误处理对齐 | B ingestion 错误解释和下游调用方 | 本次只更新契约；详细失败原因继续写入错误消息，不修改 `app/ingestion/` |
| CONTRACT-CHANGE-002 | 2026-08-25 | 补齐 Evidence 元数据来源、multiple 独立来源、RiskRule→Claim 字段和报告 review 语义 | 系统复检发现多个输出字段无法由原函数输入可靠构造 | A/B/C、公共 Schema、fixture、集成 | documents/evidence_type 改为显式输入；新增 RiskRule.metric_ids 与 Claim.risk_severity |
| CONTRACT-CHANGE-003 | 2026-08-26 | MetricRule 新增非空 `evidence_types`，指标级证据类型由配置驱动；公共 Schema 共享 EvidenceType 词表并校验关键词非空 | C-002 复审发现硬编码类型映射会随行业迁移失效、直接构造可绕过 loader | A/B/C、Evidence/IndustryConfig、configs、fixtures、tests | 新增 `app/schemas/evidence_types.py`；Evidence/RiskRule/MetricRule 共用 EvidenceType；Schema 拒绝空/空白关键词与非法 evidence_type |
| CONTRACT-CHANGE-004 | 2026-08-26 | RiskRule 新增非空 `trigger_terms`，用明确方向/比较/信号词触发风险 | C-003 复审发现无方向关键词会误触发正面改善风险、联合指标覆盖不完整 | A/C、IndustryConfig、configs、fixtures、tests/industry | risk_rules 改为按 trigger_terms 判断方向，并按 metric_ids 建立覆盖矩阵 |
| CONTRACT-CHANGE-005 | 2026-08-26 | RiskRule 新增 `exclude_terms`，命中否定/已解除/已缓解语句时不触发风险 | C-003 复审发现子串命中会把“未出现/风险已消除/压力缓解”误判为风险 | A/C、IndustryConfig、configs、fixtures、tests/industry | risk_rules 增加排除词判断；metric 覆盖同时执行 MetricRule.evidence_types |
| CONTRACT-CHANGE-006 | 2026-08-26 | 拆分库存口径：`inventory` 仅指财务存货（financial/single）；新增 optional `inventory_volume` 仅指实物库存量（operating，关键词含“库存量/期末库存量/产成品库存量”）；新增 optional `channel` 承接“动销、渠道库存、经销商库存”；禁止 `inventory` 使用裸关键词“库存/动销” | 避免“库存量、存货、库存股”等被子串匹配混为同一口径 | C configs/风险规则、B evidence locator、D Gold、共享 fixtures、集成测试 | A 更新公共契约与共享 fixture；C YAML 与 B 真实资料暂不改动 |
| CONTRACT-CHANGE-008 | 2026-08-27 | RunMetadata 新增 `mode` 字段，记录 `rule-engine`/`E1`/`E2`/`E3`；E1/E2/E3 实验模式必须显式提供模型，未提供模型时报 E300 并拒绝运行 | A 实现 E1/E2/E3 模式开关，需要可复现地记录每次运行的实验模式 | A RunMetadata、CLI、orchestrator、tests | `mode` 默认 `rule-engine`；旧 metadata 缺省时按默认值兼容 |
| CONTRACT-CHANGE-009 | 2026-08-28 | ResearchReport 增加向后兼容的 `narrative` 正文段落列表，每段绑定 Evidence ID；旧报告缺省为空列表 | 结构化 Claim 卡片不能满足最终投研简报的连贯阅读需求，需让 LLM 输出正文并保留来源气泡 | A compact LLM、报告渲染、工作台前端、tests | 字段有默认空列表；旧 report.json 可继续加载 |


