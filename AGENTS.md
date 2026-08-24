# 公共 AGENTS.md 模板

> 项目仓库创建后，将本文件内容复制到仓库根目录 AGENTS.md。

## 项目目标

构建证据链与行业适配的 A 股投研研究简报 Agent。

比赛阶段只完成：

- 食品饮料主案例；
- 银行迁移案例；
- 时间锁；
- 证据链；
- 行业配置；
- Critic；
- 评测；
- Streamlit 演示。

不实现自动交易、目标价、真实账户和大规模实时爬虫。

## 工作语言

默认使用中文说明任务、错误、日志和交接。代码标识符使用英文。

## 修改前必须执行

1. 读取 docs/CONTRACTS.md；
2. 读取 docs/GIT_GUIDE.md；
3. 读取自己的角色手册；
4. 读取 docs/task_board.md；
5. 运行 git branch --show-current；
6. 运行 git status；
7. 复述当前任务和文件范围。

未经确认不得开始修改。

## 角色目录

A：

~~~text
app/schemas/
app/orchestrator/
app/model/
app/agents/
app/validators/
app/main.py
scripts/run_case.py
tests/core/
tests/integration/
~~~

B：

~~~text
app/ingestion/
data/
fixtures/sources/
scripts/ingest_sources.py
scripts/validate_manifest.py
tests/ingestion/
~~~

C：

~~~text
app/industry/
configs/
prompts/
fixtures/industry/
tests/industry/
docs/manual_review_checklist.md
~~~

D：

~~~text
evaluation/
app/ui/
reports/
fixtures/evaluation/
tests/evaluation/
scripts/evaluate.py
outputs/experiments/
outputs/screenshots/
docs/task_board.md
~~~

不要修改其他角色目录。确需跨目录修改时，先更新 task_board 并获得 A 确认。

## 公共接口

公共字段只以 docs/CONTRACTS.md 和 app/schemas 为准。

禁止：

- 创建第二套同名 Schema；
- 私自修改字段名；
- 使用空字符串代替 null；
- 改 fixture 来掩盖错误；
- 绕过 Pydantic 校验；
- 静默忽略错误。

## 编码要求

- 一次只实现一个 task_board 任务；
- 函数保持小而清楚；
- 错误信息说明模块、文件和原因；
- 新功能必须有测试；
- 不引入任务之外的框架；
- 不做无关重构；
- 不在日志中输出 API Key；
- 模型输出必须经过结构校验；
- 报告不得新增无证据事实。

## 数据要求

- 不修改原始资料；
- quote 必须来自原文；
- cutoff 后资料不得进入正文；
- 日期不明资料进入 pending；
- red_team 资料不得混入 formal；
- 编码工具生成的 URL、日期和页码必须人工核验；
- 不编造实验结果。

## Git 要求

- 禁止直接提交 main；
- 只使用自己的角色分支；
- 提交前运行 git status 和 git diff；
- 使用明确文件执行 git add；
- 提交前运行相关测试；
- 通过 Pull Request 合并；
- 冲突时停止并联系 A。

禁止命令：

~~~text
git reset --hard
git push --force
git push -f
git rebase
git clean -fd
git checkout .
git restore .
~~~

## 完成任务后的输出

~~~text
任务 ID：
修改文件：
实现结果：
测试命令：
测试结果：
未解决问题：
是否影响公共接口：
需要谁复核：
建议 commit message：
~~~

不要自动继续下一个任务。


