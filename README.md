# FinCouncil·智研

岭院商业策划比赛项目：证据链与行业适配的 A 股投研 Agent。

> [在线体验 FinCouncil 投研工作台](https://fincouncil.43-165-172-190.sslip.io/)

## 匿名体验版投研工作台

- 前端：`frontend/`（React + TypeScript + Vite）
- 后端：`backend/`（FastAPI，复用 `app.main.run_research`）
- 部署：`Dockerfile`、`docker-compose.yml`、`Caddyfile`、`DEPLOYMENT.md`
- 支持案例：`food_main`（食品饮料行业样本）、`bank_main`（中国工商银行样本）
- 默认运行确定性 `rule-engine`；AI 增强仅当 `FINCOUNCIL_ENABLE_LLM_DEMO=true` 且 DeepSeek 环境变量完整时开放。
- 详细部署步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

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
