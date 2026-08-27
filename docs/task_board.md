# 项目任务看板

> 更新时间：2026-08-27（Asia/Shanghai）
> 同步基线：PR #29 合并后的主分支状态
> 状态依据：GitHub 已合并 PR、主分支文件和已验证测试；未提交到 GitHub 的线下工作不作推测。
> Roles 文档和 `docs/MASTER_PLAN.md` 定义任务范围，本看板记录当前执行状态。
## 一、当前结论

- A-001～A-008：已全部完成并合并；主编排默认调用真实 B/C 链路，fixture/stub 已删除。
- B-001～B-006：已完成并合并；包含真实公开财报资料包和 HTML/PDF/切分/证据定位代码。
- C-001～C-007：已全部完成并合并。
- D-002 指标计算与 D-004 红蓝测试：已完成并合并；D-001 正式 Gold Standard 仍只有合成样例，真实食品饮料/银行 Gold 尚未签收。
- D-003 实验运行器：本 PR 首次提交（`evaluation/experiment_runner.py`、`evaluation/experiment_definitions.yaml`、`scripts/evaluate.py`、`tests/evaluation/test_experiment_runner.py`）；含 `{python}` 占位符替换修复、相对路径解析修复、E0 Gold 评分、聚合纳入 E0、hash 异常捕获、E1-E3 disabled 标记，56 项评测测试通过，待审查。
- INT-001、INT-002 已完成：integration 测试就位，RUN-DEMO 已用真实食品饮料资料生成 JSON/Markdown/日志三件套。
- 当前有 1 个 open PR（D-003，本 PR 首次提交，含 `{python}` 替换修复与测试隔离改造）。

## 二、里程碑

| 里程碑 | 状态 | 说明 |
|---|---|---|
| G0 公共接口和最小链路 | 已完成 | 公共 Schema、最小 fixture/stub 链路已合并 |
| G1 四个角色模块可独立测试 | 已完成 | A/B/C 模块和 D-002 指标均有独立测试；不等于端到端完成 |
| G2 食品饮料端到端 | 已完成 | A-008 接入真实资料；RUN-DEMO 全链运行产出三件套并通过验收抽查 |
| G3 实验、迁移和红蓝测试 | 进行中 | D-004 已完成并合并；D-003 已提交 PR 待审查；MIG-001 尚未开始 |
| G4 报告和演示可提交 | 待开始 | UI、图表、报告模板和完整输出尚未完成 |
| G5 最终提交 | 待开始 | 需完成实验、验收和交付材料 |

## 三、任务状态

### A：核心工程与集成

| ID | 任务 | 状态 | 依据/备注 |
|---|---|---|---|
| A-001 | 公共 Schema | 已完成 | PR #1 |
| A-002 | 时间锁 | 已完成 | PR #2 |
| A-003 | ModelProvider、Cache | 已完成 | PR #5 |
| A-004 | 最小编排和 CLI（fixture/stub） | 已完成 | PR #3；真实适配不属于本项 |
| A-005 | 基本面、新闻政策、风险分析节点 | 已完成 | PR #7；multiple/真实链路仍需集成验收 |
| A-006 | Critic | 已完成 | PR #11 |
| A-007 | 正式报告生成 | 已完成 | PR #13 |
| A-008 | 第一次真实 B/C 集成 | 已完成 | PR #29；主编排默认真实 ingestion/industry 链路＋显式验证策略＋report.md 落盘，`_stub_*` 全部移除 |

### B：资料处理与证据

| ID | 任务 | 状态 | 依据/备注 |
|---|---|---|---|
| B-001 | manifest 读取和校验 | 已完成 | PR #4 |
| B-002 | PDF 文本和页码提取 | 已完成 | PR #9 |
| B-003 | HTML 清洗 | 已完成 | PR #23；已覆盖 EOF/裸正文边界 |
| B-004 | 文本切分 | 已完成 | PR #14 |
| B-005 | 证据定位 | 已完成 | PR #14；documents/evidence_type 契约已对齐 |
| B-006 | 食品饮料和银行资料包 | 已完成 | PR #18；主分支已有真实公开财报 URL、formal 清单和红蓝资料 |

### C：行业配置与规则

| ID | 任务 | 状态 | 依据/备注 |
|---|---|---|---|
| C-001 | 行业配置文件 | 已完成 | PR #16 |
| C-002 | 配置加载器 | 已完成 | PR #16 |
| C-003 | 必查指标清单 | 已完成 | PR #17 |
| C-004 | 指标规则 | 已完成 | PR #24 |
| C-005 | 风险规则 | 已完成 | PR #20 |
| C-006 | 分析提示词要求 | 已完成 | PR #25；`prompts/` 四个节点提示词已合并 |
| C-007 | 人工复核清单 | 已完成 | PR #26；`docs/manual_review_checklist.md` 已合并 |

### D：评测、实验与交付

| ID | 任务 | 状态 | 依据/备注 |
|---|---|---|---|
| D-001 | Gold Standard 格式和真实 Gold | 进行中 | PR #19 只有合成 `metrics_gold_sample.json`；`food_gold.json`/`bank_gold.json` 及 B/C 签收仍缺 |
| D-002 | 指标计算 | 已完成 | PR #19；固定合成 fixture 可确定性计算 |
| D-003 | 实验运行器 | 待审查 | `evaluation/experiment_runner.py`、`evaluation/experiment_definitions.yaml`、`scripts/evaluate.py`、`tests/evaluation/test_experiment_runner.py` 已提交 PR；含 `{python}` 替换、相对路径解析、E0 Gold 评分、聚合纳入 E0、hash 异常捕获、E1-E3 disabled 标记，56 项评测测试通过 |
| D-004 | 红蓝测试 | 已完成 | PR #27 已合并；六类场景 + workflow_dispatch CI 285 passed |
| D-005 | 图表 | 待开始 | `evaluation/charts.py` 尚未提交 |
| D-006 | Streamlit 页面 | 待开始 | `app/ui/` 尚未提交 |
| D-007 | 报告模板 | 待开始 | `reports/` 和提交清单尚未提交 |

### 集成与交付门

| ID | 任务 | 状态 | 说明 |
|---|---|---|---|
| INT-001 | 真实 ingestion → industry → core 集成 | 已完成 | PR #29；`tests/integration` 五个用例（正式链/E202 单发/行业差异/E100/未知后缀） |
| INT-002 | 食品饮料完整运行 | 已完成 | `python scripts/run_case.py --request fixtures/shared/research_request.json`；产出 report.json/report.md/run_metadata.json，1580 条索引证据全 verified 且 cutoff 后资料零泄漏 |
| EXP-001 | E0—E3 可复现实验 | 待开始 | 依赖 INT-002、D-001、D-003；D-003 已就绪待合并，D-001 真实 Gold 仍缺 |
| MIG-001 | 银行迁移检查 | 待开始 | 依赖 INT-002；目标是不改核心编排完成银行简版报告 |

## 四、当前阻塞与下一步

| 优先级 | 事项 | 负责人 | 下一步 |
|---|---|---|---|
| P1 | 真实 Gold Standard 缺失 | B/C/D | 基于已核验资料制作并签收 food/bank Gold，禁止把合成样例当正式结果；链路已解锁（rule-engine v1-a008 口径） |
| P1 | MIG-001 银行迁移检查 | C/A | 用 bank_case 资料跑 `python scripts/run_case.py`（request 指向银行 manifest 与 banking 配置），验证不改核心编排 |
| P2 | 实验、UI、图表、模板未开始 | D | 按 D-003、D-005～D-007 顺序推进；EXP-001 仅差 D-001 与 D-003 |

## 五、接口变更记录

| 变更 ID | 日期 | 变更摘要 | 影响 |
|---|---|---|---|
| CONTRACT-CHANGE-001 | 2026-08-25 | E100 覆盖资料不存在、损坏、不支持、无法解密、无法解析或无文本 | B ingestion、下游错误处理 |
| CONTRACT-CHANGE-002 | 2026-08-25 | Evidence 元数据来源、multiple 独立来源、RiskRule→Claim 字段和 review 语义明确化 | A/B/C、Schema、fixture、集成 |
| CONTRACT-CHANGE-003 | 2026-08-26 | MetricRule 使用非空 evidence_types，统一 EvidenceType 词表和关键词校验 | A/B/C、Schema、configs、tests |
| CONTRACT-CHANGE-004 | 2026-08-26 | RiskRule 增加非空 trigger_terms，按明确方向/比较/信号触发 | A/C、configs、tests |
| CONTRACT-CHANGE-005 | 2026-08-26 | RiskRule 增加 exclude_terms，排除否定/已缓解语句 | A/C、configs、tests |
| CONTRACT-CHANGE-006 | 2026-08-26 | 拆分 financial inventory、inventory_volume 和 channel 口径，禁止裸关键词混用 | B/C/D、共享 fixture、集成 |
| CONTRACT-CHANGE-007 | 2026-08-27 | locate_evidence 产物按显式编排规则升级 verified（来源 formal ∧ 过时间锁 ∧ 行业匹配）；不做公司与请求相等比较；graph 层去重 Critic 对 checklist 缺指标的重复上报 | A/B/C/D、集成测试断言该语义 |

## 六、验收记录

| 任务 | 验收命令/证据 | 结果 |
|---|---|---|
| A-001～A-007 | `tests/core` 对应 PR #1/#2/#3/#5/#7/#11/#13 | 已合并并通过各自 CI |
| B-001～B-002 | `tests/ingestion` 对应 PR #4/#9 | 已合并并通过各自 CI |
| B-003 | `pytest tests/ingestion/test_html_extractor.py -q` | 10 passed；PR #23 |
| B-004～B-005 | `tests/ingestion/test_chunker.py`、`test_evidence_locator.py` | 已合并；PR #14 |
| B-006 | `data/manifests/*_case.csv`、真实 PDF 和红蓝资料 | 已合并；PR #18 |
| C-001～C-002 | `pytest tests/industry/test_loader.py -q` | 已合并；PR #16 |
| C-003 | `pytest tests/industry/test_checklist.py -q` | 已合并；PR #17 |
| C-004 | `pytest tests/industry/test_metric_rules.py -q` | 29 passed；PR #24 |
| C-005 | `pytest tests/industry/test_risk_rules.py -q` | 已合并；PR #20 |
| D-002 | `pytest tests/evaluation/test_metrics.py -q` | 合成 fixture 确定性测试已合并；PR #19 |
| C-006～C-007 | `prompts/` 四个文件和 `docs/manual_review_checklist.md` 进入主分支 | 已合并；PR #25/#26 |
| D-004 | `pytest tests/evaluation/test_red_team.py -q`；全量 `python -m pytest -q` | 11 项红队场景测试通过；全量 285 passed；PR #27 |
| D-003 | `pytest tests/evaluation -q` | 56 passed（定义/hash/失败保留/E0 导入/聚合输出/`{python}` 占位符替换真实执行路径/输出目录隔离/相对路径解析/缺失 manifest 失败捕获/E0 Gold 评分/聚合纳入 E0/disabled 标记）；全量 331 passed；PR 待合并 |
| 当前主分支 | `python -m pytest -q` | PR #29 合并后全量复核 305 passed |
| A-008 / INT-001 / INT-002 | `pytest tests/integration -q`；真实 RUN-DEMO 冒烟抽查 | 5 passed；三件套产出且红队/cutoff 后/rejected 资料零进入索引；PR #29 |

## 七、状态规则

- 只有已合并且测试通过的 PR 才标记“已完成”。
- “进行中”表示已有部分产物，但验收所需的正式资料或输出仍不完整。
- “待开始”不代表没有代码依赖，而是尚未形成可验收提交。
- fixture、mock、合成 Gold 和 stub 不能写成真实实验结果。
- 角色手册和总方案定义范围；本看板只同步 GitHub 可验证的执行状态。

