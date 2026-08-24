# FinCouncil·智研

岭院商业策划比赛项目：证据链与行业适配的 A 股投研 Agent。

## 项目范围

比赛阶段完成食品饮料完整主案例和银行迁移案例，重点验证：

- 截止日期过滤；
- 证据链与来源回溯；
- 行业配置；
- Critic 检查；
- 实验可复现。

项目不包含自动交易、真实账户连接和目标价预测。

## 开始阅读

1. [总执行方案](docs/MASTER_PLAN.md)
2. [公共接口契约](docs/CONTRACTS.md)
3. [GitHub 协作指南](docs/GIT_GUIDE.md)
4. [任务看板](docs/task_board.md)
5. 根据角色阅读 docs/roles/A.md、B.md、C.md 或 D.md

## 分支

- main：稳定版本
- role-a-core：核心工程
- role-b-ingestion：资料处理
- role-c-industry：行业配置
- role-d-eval-ui：评测与界面

## 协作规则

不要直接向 main 提交。每个任务在对应角色分支完成，运行测试后提交 Pull Request，由 A 负责合并。

## 当前状态

仓库已完成协作规范和任务手册初始化，下一步从公共 Schema、资料清单、行业配置和评测骨架开始。
