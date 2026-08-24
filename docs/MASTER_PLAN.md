# 证据链与行业适配投研 Agent

## V2 项目总执行方案：四人编码版

> 截止时间：2026 年 8 月 30 日 20:00  
> 内部截止时间：2026 年 8 月 30 日 18:00  
> 团队前提：A/B/C/D 均按“没有 Git 团队协作基础”设计流程  
> 执行原则：接口先行、目录隔离、小步提交、测试后合并、结果可复现

---

## 一、结论

V2 不再采用“A 编写几乎全部代码，其他成员只提供资料或文档”的方式。

新的结构是：

- A 负责公共接口、主流程、模型调用、Critic 和集成；
- B 负责编码资料导入、PDF/HTML 解析、资料清单校验和证据定位；
- C 负责编码行业配置加载、行业指标检查、风险规则和对应测试；
- D 负责编码实验指标、红蓝测试、结果统计、Streamlit 页面和报告图表。

四人都承担可运行、可测试的代码任务，但只有 A 修改公共 Schema 和核心编排。B/C/D 通过固定接口接入，避免四个人生成四套不兼容的数据结构。

建议编码工作量大致分布：

| 角色 | 主要工作 | 预计编码量 |
|---|---|---|
| A | 核心引擎与集成 | 35%—40% |
| B | 资料处理与证据模块 | 20% |
| C | 行业配置与规则模块 | 20% |
| D | 评测、界面与报告模块 | 20%—25% |

比例不是考核指标，验收以实际交付物为准。

---

## 二、项目目标与边界

用户输入公司、行业、研究截止日期和比较区间，系统读取公开资料，生成带证据的研究变化简报。

必须完成：

- 食品饮料完整主案例；
- 银行简版迁移案例；
- 截止日期过滤；
- 证据链；
- 行业配置；
- 基本面、新闻政策和风险分析节点；
- Critic；
- Markdown 和 JSON 报告；
- E0—E3 对照实验；
- 红蓝测试；
- Streamlit 演示页；
- 运行日志和复现说明。

暂不做：

- 自动选股和自动交易；
- 真实账户连接；
- 具体目标价；
- 大规模实时爬虫；
- 向量数据库；
- 模型训练；
- 三个以上行业；
- 生产级前后端分离。

---

## 三、开源项目基础

项目可以参考或复用 TradingAgents、LangGraph 等开源项目，但必须在两小时内完成运行验证。

若实际复用开源代码，需要记录：

- 仓库地址；
- commit 或版本；
- 许可证；
- 复用文件；
- 修改文件；
- 自研部分。

若候选项目两小时内无法运行，立即使用简单 Python 状态机实现最小编排。报告只能根据真实情况写“基于开源代码开发”或“参考开源工作流设计”。

开源底座可复用：

- Agent 状态传递；
- 节点调度；
- 模型调用；
- 工具路由；
- 错误重试；
- 基础日志。

团队自研：

- 统一数据结构；
- 时间锁；
- 证据链；
- 行业配置；
- 行业规则检查；
- Critic；
- 人工确认状态；
- 评测和红蓝测试；
- 研究简报模板。

---

## 四、总体架构

~~~text
用户输入
  ↓
ResearchRequest
  ↓
A：Research Orchestrator
  ├── B：资料导入与解析
  ├── B：资料清单和日期字段校验
  ├── C：行业配置加载
  ├── C：必查指标和风险规则
  ├── A：基本面、新闻政策、风险分析节点
  ├── A：Critic 和报告生成
  └── D：实验统计、界面和图表
  ↓
ResearchReport + RunMetadata
~~~

主流程：

~~~text
读取本地资料
→ 标准化资料元数据
→ 截止日期过滤
→ PDF/HTML 文本抽取
→ 证据片段生成
→ 行业配置检查
→ 分析节点生成 Claim
→ Critic 生成 ValidationIssue
→ 过滤或标记未通过结论
→ 生成 JSON 和 Markdown 报告
→ 保存日志和实验指标
~~~

---

## 五、推荐技术栈

P0 必须：

- Python 3.11；
- Pydantic；
- PyYAML；
- pytest；
- JSONL/CSV；
- Jinja2；
- pypdf 或 pdfplumber；
- Streamlit。

P1 可加入：

- pandas；
- BeautifulSoup；
- httpx；
- LangGraph；
- 模型调用缓存。

比赛后再做：

- FastAPI；
- 向量数据库；
- 生产级数据库；
- 实时大规模爬虫；
- 复杂多轮辩论。

第一条端到端链路必须通过命令行运行。Streamlit 只消费已生成的结构化结果，不得成为核心流程的必要条件。

---

## 六、代码目录与所有权

~~~text
finresearch/
├── AGENTS.md
├── README.md
├── requirements.txt
├── app/
│   ├── main.py                         # A
│   ├── schemas/                        # A
│   │   ├── request.py
│   │   ├── source.py
│   │   ├── evidence.py
│   │   ├── claim.py
│   │   ├── validation.py
│   │   └── report.py
│   ├── orchestrator/                   # A
│   │   ├── state.py
│   │   └── graph.py
│   ├── model/                          # A
│   │   ├── provider.py
│   │   └── cache.py
│   ├── agents/                         # A
│   │   ├── fundamental.py
│   │   ├── news_policy.py
│   │   ├── risk.py
│   │   ├── critic.py
│   │   └── report.py
│   ├── ingestion/                      # B
│   │   ├── manifest.py
│   │   ├── pdf_extractor.py
│   │   ├── html_extractor.py
│   │   ├── chunker.py
│   │   └── evidence_locator.py
│   ├── industry/                       # C
│   │   ├── loader.py
│   │   ├── checklist.py
│   │   ├── metric_rules.py
│   │   └── risk_rules.py
│   └── ui/                             # D
│       ├── app.py
│       ├── components.py
│       └── evidence_view.py
├── configs/                            # C
│   ├── food_beverage.yaml
│   └── banking.yaml
├── evaluation/                         # D
│   ├── metrics.py
│   ├── experiment_runner.py
│   ├── red_team.py
│   └── charts.py
├── reports/                            # D
│   ├── template.md.j2
│   └── report_sections.md
├── scripts/
│   ├── run_case.py                     # A
│   ├── ingest_sources.py               # B
│   ├── validate_manifest.py            # B
│   └── evaluate.py                     # D
├── data/                               # B
│   ├── raw/
│   ├── manifests/
│   └── processed/
├── fixtures/
│   ├── sources/                        # B
│   ├── industry/                       # C
│   └── evaluation/                     # D
├── tests/
│   ├── core/                           # A
│   ├── ingestion/                      # B
│   ├── industry/                       # C
│   ├── evaluation/                     # D
│   └── integration/                    # A 主导，四人共同维护
├── outputs/
│   ├── reports/
│   ├── logs/
│   ├── experiments/
│   └── screenshots/
└── docs/
    ├── CONTRACTS.md
    ├── GIT_GUIDE.md
    ├── task_board.md
    └── roles/
~~~

任何人不得直接修改其他角色目录。需要跨目录修改时，在任务看板中提出，由 A 确认后执行。

---

## 七、公共接口冻结顺序

B/C/D 开始编码前，A 必须先提交：

1. ResearchRequest；
2. SourceDocument；
3. TextChunk；
4. Evidence；
5. IndustryConfig；
6. Claim；
7. ValidationIssue；
8. ResearchReport；
9. 每种结构的一份 JSON fixture；
10. 对应的最小导入测试。

公共接口冻结后，除非阻塞主流程，不再改字段名称。确需修改时：

- A 在 task_board 记录原因；
- B/C/D 确认受影响文件；
- A 修改 Schema；
- 相关角色更新模块和测试；
- D 记录重新运行范围。

---

## 八、四人编码任务

### A：核心工程

编码：

- 公共 Schema；
- ModelProvider；
- ResearchState；
- 时间锁；
- Agent 编排；
- 基本面、新闻政策和风险节点；
- Critic；
- 报告生成；
- 命令行入口；
- 集成测试；
- 主分支合并。

A 不负责替 B/C/D 重写未完成模块。

### B：资料处理与证据

编码：

- manifest CSV/JSON 读取；
- manifest 字段校验；
- PDF 文本和页码提取；
- HTML 清洗；
- 文本切分；
- Evidence 定位；
- 资料日期解析；
- 资料校验脚本；
- ingestion 单元测试。

B 同时负责核验正式资料来源。

### C：行业配置与规则

编码：

- YAML 配置；
- 配置加载器；
- 配置 Schema 校验；
- 必查指标检查；
- 缺失指标提示；
- 风险触发规则；
- 报告章节选择；
- 食品饮料和银行差异测试；
- 行业模块单元测试。

C 同时负责人工行业复核。

### D：评测、界面与报告

编码：

- E0—E3 指标计算；
- 实验运行器；
- 红蓝测试；
- 结果 CSV/JSON；
- 图表生成；
- Streamlit 页面；
- 证据详情展示；
- 报告模板；
- evaluation 和 UI 测试。

D 同时维护任务看板、实验日志和最终提交清单。

---

## 九、Git 协作模型

因为四人都没有 Git 团队协作基础，比赛期间只使用四个长期角色分支：

~~~text
main
role-a-core
role-b-ingestion
role-c-industry
role-d-eval-ui
~~~

规则：

- main 永远保持可运行；
- 所有人禁止直接向 main 提交；
- 每个人只在自己的角色分支工作；
- 每次提交只处理一个任务；
- 每个提交必须能说明修改目的；
- 合并通过 GitHub Pull Request；
- A 审查 B/C/D 的代码；
- D 按运行说明验证 A 的核心流程；
- 不使用 rebase、force push 或复杂 cherry-pick；
- 出现冲突立即停止，不自行删除别人代码。

完整命令见 Git 协作指南。

---

## 十、编码工具使用方式

每位成员开始任务前，让编码工具读取：

~~~text
AGENTS.md
docs/CONTRACTS.md
docs/GIT_GUIDE.md
docs/roles/{角色手册}.md
docs/task_board.md
当前任务涉及的代码和 fixture
~~~

第一轮只让工具回答：

- 当前任务是什么；
- 允许修改哪些文件；
- 禁止修改哪些文件；
- 依赖哪些输入；
- 输出是什么；
- 如何测试；
- 有哪些风险。

确认无误后再实现。

禁止：

- 一次性完成整个项目；
- 自动增加框架；
- 修改其他角色目录；
- 删除失败测试；
- 修改 fixture 让错误结果通过；
- 编造来源和实验数据；
- 未运行测试就提交。

---

## 十一、日程

### 8 月 24 日

A：

- 建仓库、目录和角色分支；
- 提交公共 Schema 和 fixture；
- 跑通一条最小链路。

B：

- 建立食品饮料资料清单；
- 编写 manifest 校验器骨架；
- 准备一份 PDF fixture。

C：

- 建立两份行业配置骨架；
- 编写配置加载器骨架；
- 固定必查指标清单。

D：

- 建立任务看板和实验数据结构；
- 编写 metrics 骨架；
- 建立 Streamlit 空页面。

### 8 月 25 日

- B 完成 manifest、PDF 解析、文本切分和测试；
- C 完成配置加载、指标检查、风险规则和测试；
- A 完成时间锁、证据链和三个分析节点；
- D 完成指标计算、红蓝 fixture 和页面框架；
- 晚上完成第一次集成。

### 8 月 26 日

- A 合并 B/C 模块；
- 跑通食品饮料端到端；
- D 接入最终 JSON 并展示报告和证据；
- B 抽查证据位置；
- C 检查行业配置是否生效；
- 当晚未跑通则砍掉复杂多空辩论、实时搜索和高级 UI。

### 8 月 27 日

- D 运行 E0—E3；
- D 运行红蓝测试；
- C 完成银行迁移检查；
- B 抽查银行证据；
- A 只修阻塞错误；
- 晚上冻结代码、数据和实验结果。

### 8 月 28—29 日

- A 写技术架构和实现边界；
- B 写数据来源和证据链；
- C 写行业配置和迁移；
- D 写实验、商业价值并整合总稿；
- 四人准备各自演示部分。

### 8 月 30 日

只处理：

- 测试；
- 引用；
- 文件路径；
- 报告格式；
- 演示检查；
- 提交。

18:00 后禁止结构性修改。

---

## 十二、集成顺序

第一次集成：

~~~text
A 公共 Schema
→ B manifest 与 PDF 解析
→ C 配置加载和指标检查
→ A 证据链与分析节点
→ A Critic 与报告
→ D 评测和界面
~~~

集成时一次只合并一个角色：

1. 合并 B，运行 ingestion 测试；
2. 合并 C，运行 industry 测试；
3. 运行 core 和 integration 测试；
4. 合并 D，运行 evaluation 和 UI 测试；
5. 运行完整案例。

如果某一模块失败，只回退该模块的 PR，不修改已经通过的其他模块。

---

## 十三、最低验收标准

工程：

- main 可以从零安装并运行；
- 所有公共结构通过 Pydantic 校验；
- 每个角色模块有独立测试；
- 失败时有明确错误；
- 运行结果保存到 outputs。

证据：

- 截止日期后资料进入正文数量为 0；
- 编造来源数量为 0；
- 正文关键数字 100% 有来源；
- 证据可定位到页码、章节或原文。

行业：

- 食品饮料和银行加载不同配置；
- 必查指标和风险规则发生变化；
- 缺失指标有明确提示；
- 银行迁移不修改核心编排。

实验：

- E0—E3 定义在运行前冻结；
- E0—E3 使用相同资料包、cutoff 和输出模板；
- E1—E3 使用相同模型、temperature 和提示词版本；
- 输入、输出和日志可复现；
- 红蓝测试至少覆盖未来资料、错误数字、无日期资料和证据冲突。

交付：

- 食品饮料完整报告；
- 银行简版报告；
- 实验结果和图表；
- 会议纪要、任务看板和复现说明；
- GitHub 仓库和许可证说明；
- 最终报告和演示材料。

---

## 十四、止损规则

- 开源底座两小时内无法运行：改用简单 Python 状态机；
- 8 月 25 日晚 B/C 模块未完成：只保留最小解析和最小行业规则；
- 8 月 26 日晚主案例未跑通：删除复杂多空、实时搜索和高级 UI；
- 8 月 27 日银行迁移失败：只展示配置切换和最小银行结果；
- 8 月 28 日后发现非阻塞问题：记录为局限，不再重构；
- Git 冲突无法判断：停止操作，保留现场，由 A 统一处理；
- 任何人不得使用 git reset --hard 或 git push --force。

---

## 十五、每日会议

每天固定一次 20 分钟会议。

每个人只回答：

1. 今天合并了什么；
2. 测试结果是什么；
3. 当前阻塞是什么；
4. 明天提交什么。

不以“写了多少代码”作为进度，只看可运行提交、测试和验收结果。

