# A 核心适配工作记录

> 维护人：A
> 更新时间：2026-08-25
> 范围基线：`docs/MASTER_PLAN.md`、`docs/CONTRACTS.md`、`docs/roles/A.md`
> 本文件记录 A 已提前完成但仍需接入 B/C 的适配工作，避免把 fixture/stub 误当成真实集成。

## 一、编号映射

当前文档存在编号不一致，暂按执行方案和 A 角色手册理解：

| A 角色手册编号 | 内容 | 当前状态 | 对应 PR |
|---|---|---|---|
| A-001 | 公共 Schema | 已完成并合并 | PR #1 |
| A-002 | 时间锁 | 已完成并合并 | PR #2 |
| A-003 | ModelProvider、Cache | 已完成并合并 | PR #5 |
| A-004 | 最小编排和 CLI | fixture/stub 版本已完成并合并；真实适配未完成 | PR #3 |
| A-005 | 基本面、新闻政策、风险分析节点 | 基础实现；multiple 独立来源与审查问题待闭环 | PR #7 |
| A-006 | Critic | 未完成 | — |
| A-007 | 报告生成 | 未完成 | — |
| A-008 | 第一次 B/C 集成 | 未完成 | — |

任务看板目前把“最小编排和 CLI”称为 A-003，并未单列 ModelProvider。该差异由 D 在任务看板中统一，不在本文件中擅自改动公共任务编号。

## 二、状态源规则

- `docs/task_board.md` 是任务状态的唯一来源；
- 本文件只记录 A 的适配设计、依赖、完成条件和交接细节；
- D 合并本文件后，应在任务看板中链接本文件，并把适配状态同步到任务看板；
- 两处内容冲突时，以任务看板的状态和 `docs/MASTER_PLAN.md` 的范围为准，不维护两套独立状态。

## 三、A-004 当前边界

已完成的最小链路：

~~~text
ResearchRequest
→ fixture manifest loader
→ A-002 时间锁
→ fixture text extractor
→ fixture industry loader
→ 测试 Claim
→ ResearchReport + RunMetadata
→ report.json + run_metadata.json
~~~

当前代码位置：

- `app/orchestrator/state.py`：`ResearchState`；
- `app/orchestrator/graph.py`：`run_pipeline` 和三个可注入 loader；
- `app/main.py`：`run_research`；
- `scripts/run_case.py`：命令行入口；
- `tests/core/test_orchestrator.py`：输出和 Schema 回读测试。

A-004 只有在下面的适配项完成后，才能称为真实 B/C 集成，而不是 stub 链路。

## 四、待 B/C 完成后的适配项

| 适配 ID | 适配内容 | 依赖 | 主要代码位置 | 完成标准 | 状态 |
|---|---|---|---|---|---|
| ADAPT-001 | 调用 B 的 `load_manifest` 后立即调用 `validate_manifest`，替换 `_stub_load_manifest` | B-001 | `app/main.py`、`app/orchestrator/graph.py` | 将返回的 `ValidationIssue` 写入 `ResearchState.validation_issues`；`error`/`critical` 阻止资料进入时间锁和后续分析，`warning`/`info` 可继续但不得丢弃；`load_manifest` 的 E100/E101/E102 异常直接使本次运行失败 | 待接入 |
| ADAPT-002 | 用 B 的 PDF/HTML 提取函数替换 fixture extractor | B-002、B-003 | `app/orchestrator/graph.py` | `TextChunk` 保留 `doc_id`、页码和定位 | 待 B 完成 |
| ADAPT-003 | 用 B 的 `locate_evidence` 替换 `_load_fixture_evidence` | B-004、B-005 | `app/orchestrator/graph.py` | Evidence 来自真实 chunk，关键词来自行业配置；B-003 仅负责 HTML 清洗，不代表证据定位已完成 | 待 B 完成 |
| ADAPT-004 | 用 C 的 `load_industry_config` 替换 `_stub_load_industry_config` | C 配置与 loader | `app/main.py`、`app/orchestrator/graph.py` | 食品饮料和银行加载不同配置 | 待 C 完成 |
| ADAPT-005 | 接入 C 的必查指标检查 | C checklist | `app/orchestrator/graph.py` | 缺失指标返回 E202，不静默跳过 | 待 C 完成 |
| ADAPT-006 | 接入 C 的风险规则 | C risk rules | `app/orchestrator/graph.py` | 风险 Claim 和 ValidationIssue 经过 Schema 校验 | 待 C 完成 |
| ADAPT-007 | 将真实 Evidence、行业检查结果并入 ResearchState | ADAPT-001—006 | `app/orchestrator/state.py`、`graph.py` | 不再使用 fixture evidence 作为正式正文依据 | 待接入 |
| ADAPT-008 | 接入真实模型 transport adapter | Provider 选型与凭据 | `app/model/`、A agents | Agent 只依赖 ModelProvider，不直接引用 SDK；密钥只来自环境变量 | 待选型 |
| ADAPT-009 | 第一次真实集成测试 | ADAPT-001—008、A-005—A-007 | `tests/integration/` | B/C 真实适配完成；A-005 分析节点、A-006 Critic、A-007 正式报告生成完成；core、ingestion、industry、integration 全通过 | 待接入 |
| ADAPT-010 | 食品饮料 CLI 真实运行 | ADAPT-009、A-007 | `scripts/run_case.py`、outputs | 不再生成测试 Claim；生成 JSON、Markdown、日志，关键 Claim 有可定位 Evidence，报告包含 Critic 结果 | 待接入 |
| ADAPT-011 | 为 multiple 指标提供上游独立来源确认 | B-005、manifest 去重/人工核验 | B/C 上游结果、`app/orchestrator/state.py` | 不修改公共 Evidence 字段的前提下提供已确认的独立来源集合；在确认前 multiple 指标必须保持 unresolved，不得标记 pass | 待设计 |

## 五、A 仍需并行完成的核心任务

这些任务不必等待 B/C，可以用公共 Schema 和共享 fixture 先完成：

1. **A-005 分析节点**：基础实现已在 PR #7；风险证据逐类型相关性已补测，multiple 指标仍等待 ADAPT-011，不应提前标记 pass。
2. **A-006 Critic**：`app/agents/critic.py`；检查截止日期、证据缺失、数字冲突、定位缺失和必查指标遗漏。
3. **A-007 报告生成**：`app/agents/report.py`；区分 pass、review、reject Claim，输出 JSON 和 Markdown。
4. **A-008 集成**：先合并 B，再合并 C，再运行 core、ingestion、industry 和 integration 测试。

## 六、适配时不可改变的边界

- 不创建第二套公共 Schema；
- 不修改 `docs/CONTRACTS.md` 字段来掩盖接口差异；
- 时间锁必须在证据进入正文前执行；
- `pending`、`rejected` 或 cutoff 后 Evidence 不得支撑正文关键结论；
- 不把 fixture、stub 或 mock 结果写成真实实验结果；
- B/C PR 未合并前，不复制 B/C 的正式实现到 A 目录；
- 接口不一致时先走 CONTRACT-CHANGE，再做适配。

## 七、适配完成后的验收命令

~~~powershell
pytest tests/core -q
pytest tests/ingestion -q
pytest tests/industry -q
pytest tests/integration -q
python scripts/run_case.py --request fixtures/shared/research_request.json
~~~

最后由 D 验证输出、日志和证据展示，并在 `docs/task_board.md` 中链接本清单、维护唯一任务状态。
