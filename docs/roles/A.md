# A 任务手册：核心工程与系统集成

## 一、你的目标

A 负责让系统从输入运行到输出，并保证公共接口稳定。

你的结果不是“写了很多代码”，而是：

~~~text
输入 ResearchRequest
→ 调用 B 的资料模块
→ 应用时间锁
→ 调用 C 的行业模块
→ 生成 Claim
→ 运行 Critic
→ 输出 ResearchReport
→ 保存日志
~~~

A 是 main 的技术维护人，但也按普通分支和 PR 流程工作。不要直接在 main 开发。

## 二、你的分支

~~~text
role-a-core
~~~

第一次：

~~~powershell
git clone REPO_URL
cd finresearch
git fetch origin
git switch --track origin/role-a-core
git branch --show-current
git status
~~~

正常输出必须是 role-a-core。

## 三、允许修改

~~~text
app/main.py
app/schemas/
app/orchestrator/
app/model/
app/agents/
app/validators/
scripts/run_case.py
tests/core/
tests/integration/
fixtures/shared/
AGENTS.md
docs/CONTRACTS.md
requirements.txt
README.md
~~~

需要修改 B/C/D 目录时，先在 task_board 提出，不直接修改。

## 四、开始前先完成仓库初始化

### 1. 建目录

按总方案建立项目目录。每个 Python 包需要最小的 __init__.py。

### 2. 建角色分支

如果远程还没有角色分支：

~~~powershell
git switch main
git pull --ff-only
git switch -c role-a-core
git push -u origin role-a-core

git switch main
git switch -c role-b-ingestion
git push -u origin role-b-ingestion

git switch main
git switch -c role-c-industry
git push -u origin role-c-industry

git switch main
git switch -c role-d-eval-ui
git push -u origin role-d-eval-ui

git switch role-a-core
~~~

创建完成后通知 B/C/D 克隆并切换各自分支。

### 3. 提交公共文档

首先提交：

~~~text
AGENTS.md
docs/CONTRACTS.md
docs/GIT_GUIDE.md
docs/task_board.md
docs/roles/
~~~

## 五、任务顺序

### A-001：公共 Schema

创建：

~~~text
app/schemas/request.py
app/schemas/source.py
app/schemas/evidence.py
app/schemas/industry.py
app/schemas/claim.py
app/schemas/validation.py
app/schemas/report.py
~~~

实现公共接口契约中的：

- ResearchRequest；
- SourceDocument；
- TextChunk；
- Evidence；
- IndustryConfig；
- Claim；
- ValidationIssue；
- ResearchReport；
- RunMetadata。

同时创建：

~~~text
fixtures/shared/research_request.json
fixtures/shared/source_document.json
fixtures/shared/evidence.json
fixtures/shared/food_config.json
fixtures/shared/report.json
tests/core/test_schemas.py
~~~

验收：

~~~powershell
pytest tests/core/test_schemas.py -q
~~~

必须全部通过。

完成后立即提交并通知 B/C/D。其他角色只有拿到 Schema 和 fixture 才能稳定编码。

### A-002：时间锁

创建：

~~~text
app/validators/date_validator.py
tests/core/test_date_validator.py
~~~

至少测试：

1. published_at 早于 cutoff，允许；
2. published_at 等于 cutoff，允许；
3. published_at 晚于 cutoff，拒绝；
4. published_at 为空，进入待核验；
5. event_date 晚于 cutoff，但 published_at 早于 cutoff，允许并保留说明。

函数必须返回允许资料和 ValidationIssue，不要只返回 True/False。

验收：

~~~powershell
pytest tests/core/test_date_validator.py -q
~~~

### A-003：ModelProvider

创建：

~~~text
app/model/provider.py
app/model/cache.py
tests/core/test_model_provider.py
~~~

要求：

- 模型配置从环境变量读取；
- Agent 不直接引用具体 SDK；
- temperature 默认 0；
- 支持结构化 JSON 输出；
- 调用失败有重试上限；
- API Key 不进入 Git；
- 测试使用 mock，不调用真实付费 API。

### A-004：最小编排

创建：

~~~text
app/orchestrator/state.py
app/orchestrator/graph.py
app/main.py
scripts/run_case.py
tests/core/test_orchestrator.py
~~~

第一版只需要：

~~~text
读取 ResearchRequest
→ 调用 load_manifest
→ 应用时间锁
→ 调用 extract_pdf
→ 调用 load_industry_config
→ 生成一条测试 Claim
→ 输出最小 report.json
~~~

在 B/C 模块未完成前，使用 fixture 或 stub。不要自行复制 B/C 的正式实现。

验收命令：

~~~powershell
python scripts/run_case.py --request fixtures/shared/research_request.json
~~~

预期生成：

~~~text
outputs/reports/RUN-DEMO/report.json
outputs/logs/RUN-DEMO/run_metadata.json
~~~

### A-005：分析节点

创建：

~~~text
app/agents/fundamental.py
app/agents/news_policy.py
app/agents/risk.py
tests/core/test_agents.py
~~~

每个节点：

- 只接收 Evidence 和 IndustryConfig；
- 只输出 Claim；
- 不自行创造 URL；
- 不使用 cutoff 后证据；
- 无法判断时输出 unresolved；
- 输出经过 Pydantic 校验。

### A-006：Critic

创建：

~~~text
app/agents/critic.py
tests/core/test_critic.py
~~~

至少检查：

- cutoff 违规；
- Claim 无证据；
- 数字没有来源；
- evidence_id 不存在；
- 页码和定位缺失；
- 管理层计划被写成事实；
- 必查指标遗漏；
- 冲突证据；
- 模型输出无法解析。

Critic 输出 ValidationIssue。

### A-007：报告生成

创建：

~~~text
app/agents/report.py
tests/core/test_report.py
~~~

要求：

- pass Claim 进入正文；
- review Claim 进入待确认；
- reject Claim 不进入正文；
- 报告包含 evidence index；
- 同时输出 JSON 和 Markdown；
- 报告 Agent 不新增事实。

### A-008：第一次集成

按顺序合并：

1. B 的 ingestion PR；
2. C 的 industry PR；
3. 运行 core、ingestion、industry；
4. 运行 integration；
5. 合并 D 的 evaluation 和 UI。

每合并一个 PR 都运行相关测试，不一次合并三个再统一排错。

## 六、你与 B/C/D 的接口

给 B：

- SourceDocument；
- TextChunk；
- Evidence；
- fixture；
- B 模块函数签名。

给 C：

- IndustryConfig；
- Claim；
- ValidationIssue；
- fixture；
- C 模块函数签名。

给 D：

- ResearchReport；
- RunMetadata；
- report.json fixture；
- 输出目录规则。

如果接口发生变化，必须先更新 CONTRACTS 和 fixture，再通知其他人。

## 七、编码工具首轮提示词

~~~text
我是项目 A，负责核心工程和系统集成。

请先读取：
1. AGENTS.md
2. docs/CONTRACTS.md
3. docs/GIT_GUIDE.md
4. docs/roles/A.md
5. docs/task_board.md

暂时不要修改文件。

请回答：
1. 当前任务 ID 和目标；
2. 允许修改的文件；
3. 不能修改的文件；
4. 依赖 B/C/D 的哪些接口；
5. 最多 5 步的实现计划；
6. 测试命令；
7. 可能影响公共接口的风险。
~~~

确认后：

~~~text
现在只完成当前任务，不继续下一个任务。

保持公共接口与 docs/CONTRACTS.md 一致。
不要修改 B/C/D 的责任目录。
必须补充测试。
完成后输出修改文件、测试结果和仍未解决的问题。
~~~

## 八、提交流程

~~~powershell
git status
git diff
pytest tests/core -q
git add 明确文件
git commit -m "feat(core): implement research schemas"
git push
~~~

创建 PR，说明：

- 修改公共接口；
- 影响哪些角色；
- 测试结果；
- 是否需要 B/C/D 更新。

A 的核心 PR 由 D 按运行说明验证，验证完成后 A 合并。

## 九、每日检查

- [ ] main 当前可运行；
- [ ] 公共 Schema 没有未经记录的变化；
- [ ] B/C/D 知道自己依赖的接口版本；
- [ ] 已审查待合并 PR；
- [ ] integration 测试已运行；
- [ ] 输出和日志可以复现；
- [ ] task_board 已更新。

## 十、禁止事项

- 不直接在 main 开发；
- 不替 B/C/D 悄悄重写模块；
- 不在没有 fixture 的情况下改 Schema；
- 不把真实 API Key 提交到 Git；
- 不让报告 Agent 新增事实；
- 不删除失败测试；
- 不使用 reset hard 或 force push；
- 不在 8 月 27 日后重构核心架构。

## 十一、交接模板

~~~text
A 当前版本：
公共接口版本：
已合并模块：
运行命令：
测试结果：
当前阻塞：
需要 B 提供：
需要 C 提供：
需要 D 验证：
下一次集成时间：
~~~


