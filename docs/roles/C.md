# C 任务手册：行业配置与规则模块

## 一、你的目标

C 负责让同一套核心系统在食品饮料和银行中执行不同的检查。

你的完整链路：

~~~text
industry_id
→ 加载 YAML
→ 校验 IndustryConfig
→ 生成必查指标清单
→ 检查 Evidence 覆盖
→ 触发风险规则
→ 决定报告章节
→ 返回 Claim 和 ValidationIssue
~~~

C 既负责编码，也负责行业内容的人工复核。

## 二、你的分支

~~~text
role-c-industry
~~~

第一次：

~~~powershell
git clone REPO_URL
cd finresearch
git fetch origin
git switch --track origin/role-c-industry
git branch --show-current
git status
~~~

确认当前不是 main。

## 三、允许修改

~~~text
app/industry/
configs/
prompts/
fixtures/industry/
tests/industry/
docs/manual_review_checklist.md
docs/roles/C.md
~~~

不得直接修改：

~~~text
app/schemas/
app/orchestrator/
app/model/
app/ingestion/
evaluation/
~~~

如果 IndustryConfig Schema 不够用，在 task_board 提出，不自行创建另一套模型。

## 四、开始前需要 A 提供

- IndustryConfig；
- MetricRule；
- RiskRule；
- Evidence；
- Claim；
- ValidationIssue；
- 配置 JSON fixture；
- C 模块函数签名。

需要 B 提供：

- 资料中常见指标关键词；
- Evidence 示例；
- 食品饮料和银行资料的实际字段。

## 五、任务顺序

### C-001：行业配置文件

创建：

~~~text
configs/food_beverage.yaml
configs/banking.yaml
fixtures/industry/food_config_expected.json
fixtures/industry/bank_config_expected.json
~~~

食品饮料至少包含：

- revenue_growth；
- gross_margin；
- sales_expense_rate；
- inventory；
- volume；
- channel；
- raw_material_cost；
- food_safety。

银行至少包含：

- net_interest_margin；
- loan_growth；
- deposit_structure；
- non_performing_loan_ratio；
- provision_coverage；
- capital_adequacy；
- liquidity；
- real_estate_exposure。

每个 metric 包含：

~~~text
metric_id
display_name
keywords
required
evidence_requirement
missing_action
~~~

每个配置还包含：

- event_taxonomy；
- risk_rules；
- report_sections；
- retrieval_keywords。

### C-002：配置加载器

创建：

~~~text
app/industry/loader.py
tests/industry/test_loader.py
~~~

实现：

~~~python
load_industry_config(
    industry_id: str
) -> IndustryConfig
~~~

至少测试：

- 正常加载食品饮料；
- 正常加载银行；
- 配置文件不存在；
- YAML 格式错误；
- required_metrics 为空；
- metric_id 重复；
- report_sections 为空；
- 非法 missing_action。

测试：

~~~powershell
pytest tests/industry/test_loader.py -q
~~~

### C-003：必查指标清单

创建：

~~~text
app/industry/checklist.py
tests/industry/test_checklist.py
~~~

实现：

~~~python
build_industry_checklist(
    config: IndustryConfig
) -> list[str]

check_required_metrics(
    evidence: list[Evidence],
    config: IndustryConfig
) -> list[ValidationIssue]
~~~

规则：

- required 为 true 的指标必须检查；
- 找不到证据时按 missing_action 返回 warn、review 或 reject；
- 不静默跳过；
- Evidence 类型和关键词不匹配时不能算覆盖；
- 多来源要求必须至少有两个独立来源。

关键测试：

- 食品饮料配置要求 inventory；
- 银行配置不要求 inventory；
- 银行配置要求 net_interest_margin；
- 食品饮料配置不要求 net_interest_margin；
- 必查指标缺失返回 E202；
- optional 指标缺失不导致 reject。

### C-004：指标规则

创建：

~~~text
app/industry/metric_rules.py
tests/industry/test_metric_rules.py
~~~

食品饮料第一版规则：

- 存货增速明显高于收入增速时标记库存风险；
- 毛利率变化必须说明比较期间；
- 销量和价格不能在无证据时相互替代；
- 管理层计划不能当作已完成事实。

银行第一版规则：

- 不良率、关注类贷款和拨备覆盖率联合检查；
- 净息差变化必须说明期间；
- 资本充足率必须保留原始口径；
- 房地产风险不能由单一行业新闻直接推导到目标银行。

规则函数不要自行改 Claim 文本，只返回 ValidationIssue 或补充标记。

### C-005：风险规则

创建：

~~~text
app/industry/risk_rules.py
tests/industry/test_risk_rules.py
~~~

实现：

~~~python
apply_risk_rules(
    evidence: list[Evidence],
    config: IndustryConfig
) -> list[Claim]
~~~

要求：

- 风险 Claim 标记 claim_type=risk；
- 绑定 Evidence；
- 没有足够证据时使用 unresolved；
- 不能给出确定性股价判断；
- severity 来自配置；
- 每条风险包含观察指标。

### C-006：提示词要求

创建：

~~~text
prompts/fundamental.md
prompts/news_policy.md
prompts/risk.md
prompts/critic_industry.md
~~~

提示词必须要求：

- 只使用给定 Evidence；
- 输出符合 Claim Schema；
- fact、change、analysis、risk 分层；
- 无法判断输出 unresolved；
- 精确数字绑定 evidence_id；
- 不生成 URL；
- 不预测目标价。

C 负责内容要求，A 负责在 Agent 中调用。

### C-007：人工复核清单

创建：

~~~text
docs/manual_review_checklist.md
~~~

食品饮料复核：

- 收入、销量、价格是否混淆；
- 库存和动销是否有公司证据；
- 管理层计划是否被写成事实；
- 毛利率和费用率口径是否一致；
- 食品安全信息是否适用于目标公司。

银行复核：

- 净息差期间是否一致；
- 不良率和拨备是否联合解释；
- 资本充足率口径是否准确；
- 房地产或地方债风险是否过度推断；
- 行业政策是否直接套到目标银行。

## 六、验收标准

代码：

- 两份 YAML 通过 Schema；
- loader 测试通过；
- checklist 能返回缺失指标；
- 风险规则能生成结构化 Claim；
- 两个行业的检查项有实质差异；
- 不修改核心编排；
- 所有返回符合 A 的 Schema。

总测试：

~~~powershell
pytest tests/industry -q
~~~

人工：

- 配置内容有资料或行业常识依据；
- 指标含义和单位清楚；
- 风险规则不会把行业新闻直接套到公司；
- 报告章节能体现行业差异；
- 银行迁移无需修改 A 的核心代码。

## 七、编码工具首轮提示词

~~~text
我是项目 C，负责行业配置和规则模块。

请先读取：
1. AGENTS.md
2. docs/CONTRACTS.md
3. docs/GIT_GUIDE.md
4. docs/roles/C.md
5. docs/task_board.md
6. app/schemas 中 IndustryConfig、Evidence、Claim、ValidationIssue

暂时不要修改文件。

请回答：
1. 当前任务 ID；
2. 允许和禁止修改的文件；
3. 依赖 A 的哪些结构；
4. 依赖 B 的哪些 Evidence 示例；
5. 最多 5 步的实现计划；
6. 测试用例；
7. 如何证明食品饮料和银行配置有实质差异。
~~~

确认后：

~~~text
现在只完成当前任务。

不要修改 app/schemas、app/orchestrator 和 app/model。
不要新增第三个行业。
不要把行业新闻直接写成目标公司的事实。
必须添加 tests/industry 下的测试。
完成后输出修改文件、测试结果和需要人工确认的行业问题。
~~~

## 八、Git 提交流程

每天开始：

~~~powershell
git status
git fetch origin
git switch role-c-industry
git merge origin/main
~~~

完成任务：

~~~powershell
git status
git diff
pytest tests/industry -q
git add 明确的C目录文件
git commit -m "feat(industry): add food and banking configs"
git push
~~~

创建 PR，base 选择 main，compare 选择 role-c-industry。

## 九、PR 说明重点

必须说明：

- 哪些配置发生变化；
- 新增哪些必查指标；
- 新增哪些风险规则；
- 对 A 的接口有无影响；
- 对 B 的资料有什么要求；
- 测试如何证明两个行业不同。

## 十、每日交接

~~~text
C 当前任务：
新增或修改配置：
新增或修改代码：
测试命令与结果：
新增必查指标：
新增风险规则：
需要 B 补充的 Evidence：
需要 A 处理的接口问题：
需要 D 记录的实验变量：
~~~

## 十一、禁止事项

- 不直接改公共 Schema；
- 不修改核心编排；
- 不新增第三个行业；
- 不把提示词当作唯一行业适配；
- 不把单一季度变化写成长趋势；
- 不把管理层计划写成事实；
- 不把行业风险直接套到目标公司；
- 不使用 git add .；
- 不使用 reset hard 或 force push；
- 不为了测试通过降低必查标准。


