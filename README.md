# FinCouncil·智研

岭院商业策划比赛项目：证据链与行业适配的 A 股投研 Agent。

## 匿名体验版投研工作台

- 前端：`frontend/`（React + TypeScript + Vite）
- 后端：`backend/`（FastAPI，复用 `app.main.run_research`）
- 部署：`Dockerfile`、`docker-compose.yml`、`Caddyfile`、`DEPLOYMENT.md`
- 支持案例：`food_main`（食品饮料行业样本）、`bank_main`（中国工商银行样本）
- 工作台在 LLM 可用时默认开启 AI 增强；LLM 负责组织投研正文，规则引擎负责时间锁、证据校验和失败兜底。
- 线上体验：[FinCouncil 匿名工作台](https://fincouncil.43-165-172-190.sslip.io/)
- 详细部署步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 项目范围

比赛阶段完成食品饮料完整主案例和银行迁移案例，重点验证：

- 截止日期过滤；
- 证据链与来源回溯；
- 行业配置；
- Critic 检查；
- 报告正文生成与导出。

项目不包含自动交易、真实账户连接和目标价预测。

## 开始阅读

1. [总执行方案](docs/MASTER_PLAN.md)
2. [公共接口契约](docs/CONTRACTS.md)
3. [GitHub 协作指南](docs/GIT_GUIDE.md)
4. [任务看板](docs/task_board.md)
5. [最终提交清单](docs/submission_checklist.md)
6. 根据角色阅读 docs/roles/A.md、B.md、C.md 或 D.md

## 分支

- `main`：当前 MVP 冻结版本，作为报告和演示基线。
- `role-*`、历史 `feature/*`：开发历史，仅用于追溯，不作为交付入口。
- 新修改必须从 `main` 建分支并通过 Pull Request 合并。

## 协作规则

不要直接向 main 提交。每个任务在对应角色分支完成，运行测试后提交 Pull Request，由 A 负责合并。

## 当前状态

MVP 已冻结：支持食品饮料和银行资料包，能够完成时间锁、证据定位、LLM 正文生成、来源回溯、Critic 校验和报告下载。正式 E0–E3 对比实验暂缓，不将失败或未运行的实验写成结果。
