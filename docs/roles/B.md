# B 任务手册：资料处理与证据模块

## 一、你的目标

B 负责把原始资料转换成系统可以使用的 SourceDocument、TextChunk 和 Evidence。

你的完整链路：

~~~text
原始 PDF / HTML
→ manifest
→ 字段校验
→ 文本和页码提取
→ 文本切分
→ 证据定位
→ 输出结构化 Evidence
~~~

B 既负责编码，也负责人工核验来源。编码工具可以提取和整理，但不能替你确认资料是否真实、日期是否正确。

## 二、你的分支

~~~text
role-b-ingestion
~~~

第一次：

~~~powershell
git clone REPO_URL
cd finresearch
git fetch origin
git switch --track origin/role-b-ingestion
git branch --show-current
git status
~~~

开始工作前确认当前不是 main。

## 三、允许修改

~~~text
app/ingestion/
scripts/ingest_sources.py
scripts/validate_manifest.py
data/
fixtures/sources/
tests/ingestion/
docs/roles/B.md
~~~

不得直接修改：

~~~text
app/schemas/
app/orchestrator/
app/model/
app/agents/
app/industry/
evaluation/
~~~

如果 A 的 Schema 不满足需求，在 task_board 提出，不自行复制一个新 Schema。

## 四、开始前需要 A 提供

- SourceDocument；
- TextChunk；
- Evidence；
- ValidationIssue；
- JSON fixture；
- B 模块函数签名。

如果以上内容尚未提交，你可以先准备资料和测试样例，但不要自行定义公共字段。

## 五、资料目录

~~~text
data/raw/food_beverage/
data/raw/banking/
data/manifests/food_case.csv
data/manifests/bank_case.csv
data/processed/
fixtures/sources/
~~~

食品饮料准备 8—12 份高质量资料，银行准备 4—6 份核心资料。

优先：

- 上市公司财报和公告；
- 交易所公开文件；
- 政府和监管政策；
- 公司官网资料；
- 可核验日期的主流媒体材料。

来源不明、只有转载时间或无法定位原文的资料不能进入 formal。

## 六、任务顺序

### B-001：manifest 模板与读取

创建：

~~~text
app/ingestion/manifest.py
scripts/validate_manifest.py
tests/ingestion/test_manifest.py
fixtures/sources/manifest_valid.csv
fixtures/sources/manifest_invalid.csv
~~~

manifest 字段：

~~~text
doc_id
title
source_type
publisher
source_url
local_path
published_at
event_date
retrieved_at
company_name
industry_id
trust_level
review_status
~~~

实现：

~~~python
load_manifest(path: str) -> list[SourceDocument]

validate_manifest(
    documents: list[SourceDocument]
) -> list[ValidationIssue]
~~~

至少测试：

- 正常资料；
- 缺少 doc_id；
- published_at 格式错误；
- local_path 不存在；
- review_status 非法；
- formal 资料缺少公开日期；
- doc_id 重复。

测试：

~~~powershell
pytest tests/ingestion/test_manifest.py -q
~~~

### B-002：PDF 提取

创建：

~~~text
app/ingestion/pdf_extractor.py
tests/ingestion/test_pdf_extractor.py
fixtures/sources/sample_report.pdf
~~~

实现：

~~~python
extract_pdf(
    document: SourceDocument
) -> list[TextChunk]
~~~

要求：

- 按页读取；
- TextChunk 保留 page；
- 不跨文档；
- 空白页允许跳过但记录；
- 提取失败返回明确错误；
- 不修改原始 PDF；
- 不使用模型改写原文。

测试：

- 两页 PDF 输出至少两个有页码 chunk；
- 空白页不产生空文本；
- 文件不存在时返回 E100；
- 加密或损坏 PDF 有明确错误。

### B-003：HTML 清洗

创建：

~~~text
app/ingestion/html_extractor.py
tests/ingestion/test_html_extractor.py
fixtures/sources/sample_article.html
~~~

要求：

- 移除 script、style、导航和无关标签；
- 保留标题、正文和段落顺序；
- 不把发布日期自动猜成事件日期；
- 只处理本地 HTML fixture；
- 第一阶段不做实时网页抓取。

### B-004：文本切分

创建：

~~~text
app/ingestion/chunker.py
tests/ingestion/test_chunker.py
~~~

实现：

~~~python
chunk_text(
    chunks: list[TextChunk],
    max_chars: int
) -> list[TextChunk]
~~~

规则：

- 优先按页和段落切分；
- 不跨页合并；
- 保留 section、paragraph_index；
- 每个 chunk 有唯一 chunk_id；
- 不能截断数字和单位时尽量保持句子完整。

### B-005：证据定位

创建：

~~~text
app/ingestion/evidence_locator.py
tests/ingestion/test_evidence_locator.py
~~~

实现：

~~~python
locate_evidence(
    chunks: list[TextChunk],
    keywords: list[str],
    *,
    documents: list[SourceDocument],
    evidence_type: str
) -> list[Evidence]
~~~

第一版使用关键词匹配即可，不需要向量数据库。

要求：

- quote 必须来自原文；
- Evidence 绑定 doc_id 和 chunk_id；
- 保留 page、section、locator；
- published_at 来自 SourceDocument；
- 不自行生成来源 URL；
- 结果能通过 Evidence Schema；
- documents 必填，用于按 doc_id 提供 published_at、company_name、industry_id；
- evidence_type 由调用方显式提供，不使用 keyword_match 作为正式类型；
- 自动匹配结果固定 review_status=pending、confidence=0.5；
- 文档缺失、published_at 为空或 evidence_type 为空时明确失败，不得静默跳过或编造。

### B-006：资料包

完成：

~~~text
data/raw/food_beverage/
data/raw/banking/
data/manifests/food_case.csv
data/manifests/bank_case.csv
~~~

分类：

~~~text
formal
background
pending_date
red_team
rejected
~~~

准备红蓝材料：

- 一份 cutoff 后资料；
- 一份日期不明确资料；
- 一份来源冲突资料；
- 一份与目标公司无关资料。

## 七、验收标准

代码：

- manifest 读取和校验测试通过；
- PDF 提取保留页码；
- HTML 提取保留段落顺序；
- chunk 有稳定 ID；
- Evidence 能定位原文；
- 所有输出通过 A 的 Schema；
- 不修改原始文件。

资料：

- formal 资料来源和公开日期明确；
- 关键材料有页码或原文位置；
- 重复转载和独立来源有区分；
- cutoff 后资料被单独标记；
- B 模块输出可由 A 直接调用。

总测试：

~~~powershell
pytest tests/ingestion -q
python scripts/validate_manifest.py data/manifests/food_case.csv
~~~

## 八、编码工具首轮提示词

~~~text
我是项目 B，负责资料处理和证据模块。

请先读取：
1. AGENTS.md
2. docs/CONTRACTS.md
3. docs/GIT_GUIDE.md
4. docs/roles/B.md
5. docs/task_board.md
6. app/schemas 中与 SourceDocument、TextChunk、Evidence 相关的文件

暂时不要修改文件。

请回答：
1. 当前任务 ID；
2. 允许修改的文件；
3. 禁止修改的文件；
4. 依赖 A 的哪些结构；
5. 最多 5 步的实现计划；
6. 测试 fixture 和测试命令；
7. 如何保证页码、日期和原文不丢失。
~~~

确认后：

~~~text
现在只完成当前任务。

不要修改 app/schemas 和 app/orchestrator。
不要引入向量数据库或实时爬虫。
不要让模型改写 quote。
必须添加 tests/ingestion 下的测试。
完成后输出修改文件、测试结果和待人工核验事项。
~~~

## 九、Git 提交流程

每天开始：

~~~powershell
git status
git fetch origin
git switch role-b-ingestion
git merge origin/main
~~~

完成任务：

~~~powershell
git status
git diff
pytest tests/ingestion -q
git add 明确的B目录文件
git commit -m "feat(ingestion): add manifest validation"
git push
~~~

创建 PR，base 选择 main，compare 选择 role-b-ingestion。

如果出现冲突，停止并把 git status 发给 A。

## 十、人工核验流程

每份 formal 资料至少人工检查：

- 标题；
- 发布主体；
- 原始 URL；
- 公开日期；
- 文件版本；
- 目标公司或行业；
- 页码或定位；
- 是否属于 cutoff 之后；
- 是否重复转载。

编码工具生成的日期、链接和页码不能直接通过，必须抽查原始文件。

## 十一、每日交接

~~~text
B 当前任务：
新增资料：
新增或修改代码：
测试命令与结果：
formal 资料数量：
pending_date 数量：
red_team 数量：
需要 A 处理的接口问题：
需要 C 提供的关键词：
需要 D 纳入的标准答案：
~~~

## 十二、禁止事项

- 不直接修改公共 Schema；
- 不修改原始 PDF；
- 不把转载时间当原始发布时间；
- 不让模型生成 quote；
- 不添加实时搜索作为主流程依赖；
- 不把 red_team 资料放进 formal；
- 不使用 git add .；
- 不使用 reset hard 或 force push；
- 不为了测试通过修改真实资料。


