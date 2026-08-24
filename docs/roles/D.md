# D 任务手册：评测、界面与交付模块

## 一、你的目标

D 负责证明系统是否有效，并把可复现结果呈现出来。

你的完整链路：

~~~text
ResearchReport + Gold Standard
→ 计算指标
→ 运行 E0—E3
→ 运行红蓝测试
→ 保存实验结果
→ 生成图表
→ Streamlit 展示
→ 报告和演示材料
~~~

D 同时维护任务看板。没有输入、日志或统一评分标准的结果不能进入最终报告。

## 二、你的分支

~~~text
role-d-eval-ui
~~~

第一次：

~~~powershell
git clone REPO_URL
cd finresearch
git fetch origin
git switch --track origin/role-d-eval-ui
git branch --show-current
git status
~~~

确认当前不是 main。

## 三、允许修改

~~~text
evaluation/
app/ui/
reports/
scripts/evaluate.py
fixtures/evaluation/
tests/evaluation/
outputs/experiments/
outputs/screenshots/
docs/task_board.md
docs/submission_checklist.md
docs/roles/D.md
~~~

不得直接修改：

~~~text
app/schemas/
app/orchestrator/
app/model/
app/agents/
app/ingestion/
app/industry/
~~~

如果 report.json 结构无法满足评测或页面需求，在 task_board 提出，不自行改 Schema。

## 四、开始前需要 A 提供

- ResearchReport；
- RunMetadata；
- report.json fixture；
- 输出目录规则；
- 运行命令；
- E0—E3 的模式开关。

需要 B 提供：

- Gold Standard 的证据和正确来源；
- red_team 资料；
- 标准答案对应的页码。

需要 C 提供：

- 行业必查指标；
- 指标和风险的标准答案结构；
- 银行迁移验收清单。

## 五、冻结实验定义

实验开始前，把定义写入：

~~~text
evaluation/experiment_definitions.yaml
~~~

推荐：

~~~yaml
experiments:
  E0:
    name: manual_baseline
    description: 人工检索和整理
  E1:
    name: generic_agent
    description: 通用 Agent，不加载行业配置
  E2:
    name: industry_agent
    description: 通用 Agent 加载行业配置
  E3:
    name: full_system
    description: 行业配置、时间锁、证据链和 Critic
~~~

如果团队最终调整定义，必须在第一次正式运行前冻结，并同步修改总方案和报告。运行后不得根据结果改组。

所有实验使用相同资料包、cutoff 和报告模板。E1—E3 额外保持相同模型、temperature 和提示词版本。

E0 是人工基线：由指定成员使用同一资料包完成人工简报，记录开始时间、结束时间、使用资料和最终文本。E0 不调用模型，但同样使用 Gold Standard 评分。

为统一评分，D 需要把 E0 人工简报整理成与 ResearchReport 对应的评测记录，但不得修改人工原文或补充人工当时没有写出的结论。

## 六、任务顺序

### D-001：Gold Standard 格式

创建：

~~~text
fixtures/evaluation/food_gold.json
fixtures/evaluation/bank_gold.json
tests/evaluation/test_gold_schema.py
~~~

建议字段：

~~~text
item_id
item_type
expected_text
expected_value
unit
required
source_doc_id
source_page
industry_metric_id
evidence_requirement
~~~

Gold Standard 内容由 B/C 提供，D 负责统一格式和校验。

### D-002：指标计算

创建：

~~~text
evaluation/metrics.py
tests/evaluation/test_metrics.py
fixtures/evaluation/report_sample.json
~~~

实现：

~~~python
evaluate_report(
    report: ResearchReport,
    gold_path: str
) -> dict[str, float]
~~~

至少计算：

关键因素覆盖率：

~~~text
正确识别的 required 项 / Gold Standard required 项总数
~~~

证据有效率：

~~~text
存在、日期合规且能支持结论的引用 / 被检查引用总数
~~~

引用定位准确率：

~~~text
页码或原文定位正确的引用 / 被检查引用总数
~~~

数字错误率：

~~~text
错误数字 / 被检查数字总数
~~~

截止日期违规次数：

~~~text
进入正文的 cutoff 后证据数量
~~~

行业必查指标覆盖率：

~~~text
已检查的 required_metrics / 配置中的 required_metrics
~~~

测试必须使用固定输入和确定结果，不调用模型。

### D-003：实验运行器

创建：

~~~text
evaluation/experiment_runner.py
scripts/evaluate.py
tests/evaluation/test_experiment_runner.py
~~~

要求：

- 读取 experiment_definitions.yaml；
- 记录 experiment_id；
- 保存输入 hash；
- E0 导入人工简报和计时记录；
- E1—E3 调用 A 提供的运行命令；
- 保存 report.json 和 run_metadata；
- 计算指标；
- 输出 results.csv 和 results.json；
- 失败不丢弃，记录 failed 和错误信息。

输出：

~~~text
outputs/experiments/{case_id}/{experiment_id}/
├── request.json
├── report.json
├── run_metadata.json
├── metrics.json
└── error.txt
~~~

### D-004：红蓝测试

创建：

~~~text
evaluation/red_team.py
tests/evaluation/test_red_team.py
fixtures/evaluation/red_team/
~~~

至少覆盖：

1. cutoff 后新闻；
2. 错误数字；
3. 无日期资料；
4. 与公司无关资料；
5. 两个来源数字冲突；
6. 无证据观点。

验收结果：

- cutoff 后资料不进入正文；
- 错误数字产生 ValidationIssue；
- 无日期资料进入 pending；
- 无关资料不算有效证据；
- 冲突资料进入人工确认；
- 无证据观点被 reject 或 review。

### D-005：图表

创建：

~~~text
evaluation/charts.py
tests/evaluation/test_charts.py
~~~

至少生成：

- E0—E3 覆盖率对比；
- E0—E3 证据有效率对比；
- 错误和 Critic 拦截数量；
- 人工修改时间；
- 银行迁移指标覆盖。

图表只读取 results.csv，不手工填写结果。

### D-006：Streamlit 页面

创建：

~~~text
app/ui/app.py
app/ui/components.py
app/ui/evidence_view.py
tests/evaluation/test_ui_data.py
~~~

页面只读取结构化文件：

~~~text
report.json
run_metadata.json
metrics.json
~~~

至少展示：

- 公司、行业和 cutoff；
- 结论摘要；
- 行业必查指标；
- 风险和待确认项；
- 点击 Claim 查看 Evidence；
- ValidationIssue；
- 实验指标；
- 银行配置切换结果。

页面不得直接调用模型或修改报告内容。

### D-007：报告模板

创建：

~~~text
reports/template.md.j2
reports/report_sections.md
docs/submission_checklist.md
~~~

报告中实验数字必须来自 results.csv 或 metrics.json。

需要写清：

- 成功结果；
- 失败案例；
- 哪些内容需人工确认；
- 哪些资料被拒绝；
- 银行迁移复用了什么；
- 行业配置实际改变了什么；
- 项目局限。

## 七、验收标准

代码：

- metrics 使用固定 fixture 得到确定结果；
- experiment runner 保存完整目录；
- 失败实验有日志；
- red_team 覆盖六类样例；
- 图表来自 results.csv；
- Streamlit 能读取 report.json；
- 页面不修改核心数据；
- 所有测试通过。

测试：

~~~powershell
pytest tests/evaluation -q
python scripts/evaluate.py --case food_main
streamlit run app/ui/app.py
~~~

实验：

- E0—E3 输入条件一致；
- 定义在实验前冻结；
- 每组结果有 input hash；
- 指标有计算过程；
- 失败案例不被删除；
- 任何无法复现结果不进入报告。

## 八、编码工具首轮提示词

~~~text
我是项目 D，负责评测、界面和最终交付模块。

请先读取：
1. AGENTS.md
2. docs/CONTRACTS.md
3. docs/GIT_GUIDE.md
4. docs/roles/D.md
5. docs/task_board.md
6. A 提供的 ResearchReport 和 RunMetadata fixture

暂时不要修改文件。

请回答：
1. 当前任务 ID；
2. 允许和禁止修改的文件；
3. 依赖 A/B/C 的哪些输入；
4. 最多 5 步的实现计划；
5. 测试 fixture 和预期结果；
6. 如何保证实验输入一致；
7. 如何保证页面不修改核心结果。
~~~

确认后：

~~~text
现在只完成当前任务。

不要修改 app/schemas、app/orchestrator、app/agents。
不要生成或猜测实验数字。
所有指标必须由 fixture 或 results 文件计算。
必须添加 tests/evaluation 下的测试。
完成后输出修改文件、测试结果和无法复现的内容。
~~~

## 九、Git 提交流程

每天开始：

~~~powershell
git status
git fetch origin
git switch role-d-eval-ui
git merge origin/main
~~~

完成任务：

~~~powershell
git status
git diff
pytest tests/evaluation -q
git add 明确的D目录文件
git commit -m "feat(evaluation): add evidence validity metrics"
git push
~~~

创建 PR，base 选择 main，compare 选择 role-d-eval-ui。

## 十、验证 A 的核心 PR

A 提交核心 PR 后，D 不需要逐行审查所有代码，但要按照 A 提供的运行命令验证：

~~~text
能否安装
能否运行
是否生成 report.json
是否生成日志
失败时是否有错误信息
是否符合 CONTRACTS
~~~

验证结果写入 PR：

~~~text
运行环境：
运行命令：
运行结果：
生成文件：
发现问题：
是否建议合并：
~~~

## 十一、任务看板维护

每次更新：

- 任务开始；
- commit 完成；
- PR 创建；
- PR 合并；
- 测试失败；
- 出现阻塞；
- 接口变更；
- 实验重跑。

状态只用：

~~~text
待开始
进行中
待审查
已完成
阻塞
~~~

## 十二、每日交接

~~~text
D 当前任务：
任务看板更新：
新增或修改代码：
测试命令与结果：
已运行实验：
失败实验：
新增图表：
页面状态：
需要 A 提供：
需要 B 核验：
需要 C 签收：
~~~

## 十三、禁止事项

- 不修改公共 Schema；
- 不修改核心编排；
- 不根据结果修改实验分组；
- 不手工填写实验数字；
- 不删除失败实验；
- 不只保留最好的一次运行；
- 不让 Streamlit 直接调用模型；
- 不把页面展示值和 report.json 写成不同内容；
- 不使用 git add .；
- 不使用 reset hard 或 force push。

