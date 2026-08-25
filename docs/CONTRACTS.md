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
- pending 和 rejected Evidence 不得支撑正文关键结论。

## 六、IndustryConfig

~~~python
class MetricRule(BaseModel):
    metric_id: str
    display_name: str
    keywords: list[str]
    required: bool
    evidence_requirement: Literal["single", "multiple"]
    missing_action: Literal["warn", "review", "reject"]

class RiskRule(BaseModel):
    risk_id: str
    display_name: str
    trigger_description: str
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
- 食品饮料和银行配置必须有实质差异。

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
- review Claim 进入待人工确认章节。

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
class ResearchReport(BaseModel):
    run_id: str
    company_name: str
    industry_id: str
    cutoff_date: date
    summary: list[str]
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

## 十、RunMetadata

~~~python
class RunMetadata(BaseModel):
    run_id: str
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

locate_evidence(
    chunks: list[TextChunk],
    keywords: list[str]
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
    config: IndustryConfig
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
    config: IndustryConfig
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

## 十二、错误处理

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

## 十三、接口变更流程

1. 提出人在 task_board 新建 CONTRACT-CHANGE 任务；
2. 说明原因、字段变化和受影响模块；
3. A 修改本文件和 Schema；
4. B/C/D 在各自分支更新代码；
5. 四个模块测试全部通过；
6. A 合并；
7. D 记录需要重新运行的实验。

没有完成以上流程，不得私自改公共字段。

## 十四、已记录的 CONTRACT-CHANGE

| 变更 ID | 日期 | 变更内容 | 原因 | 受影响模块 | 实施说明 |
|---|---|---|---|---|---|
| CONTRACT-CHANGE-001 | 2026-08-25 | 扩大 E100 语义，覆盖资料不可用的完整错误集合 | 与 B-002 PDF 提取的统一错误处理对齐 | B ingestion 错误解释和下游调用方 | 本次只更新契约；详细失败原因继续写入错误消息，不修改 `app/ingestion/` |


