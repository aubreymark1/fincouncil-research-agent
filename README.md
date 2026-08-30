# FinCouncil · 智研

FinCouncil 是一个面向行业研究的 AI 投研 Agent。它把研究对象、截止日期和资料包作为输入，先完成资料筛选与证据定位，再由 LLM 组织成可读的投研简报，并保留来源回溯和待确认事项。

## 在线体验

[FinCouncil 匿名体验版](https://fincouncil.43-165-172-190.sslip.io/)

> 演示环境仅用于评委体验。请勿提交个人信息、未公开资料或任何敏感文件。

## 系统流程

```text
研究对象 + 截止日期 + 资料包
              ↓
资料读取与文本切分
              ↓
时间锁：排除截止日期之后的资料
              ↓
行业配置：加载该行业的指标和风险规则
              ↓
证据定位与来源校验
              ↓
LLM 组织投研正文
              ↓
Critic 检查冲突、无依据数字和待确认事项
              ↓
投研简报 + 来源回溯 + JSON/Markdown 导出
```

## 项目特点

- LLM 负责把结构化证据组织成自然语言正文；
- 规则引擎负责时间锁、证据有效性和格式校验；
- Critic 对冲突来源、风险信号和无依据内容提出复核提示；
- 行业配置可以切换必查指标、风险规则和报告章节；
- 报告正文中的来源可以继续回溯到文档、页码或文本块；
- LLM 不可用时，系统可以回退到确定性的 rule-engine 路径。

## 当前范围

当前 MVP 包含两个演示案例：

- `food_main`：食品饮料行业样本；
- `bank_main`：银行业迁移样本。

项目不实现自动交易、真实账户连接、目标价预测或大规模实时爬虫。输出内容不构成投资建议。

## 本地运行

### Python 测试

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements-dev.txt
python -m pytest -q
```

### Docker 演示

```bash
cp .env.example .env
# 按需编辑 .env；API Key 只放在本地或服务器的 .env，不要提交到 Git
docker compose up -d --build
```

启用 LLM 时，在 `.env` 中填写 `FINCOUNCIL_ENABLE_LLM_DEMO=true` 和模型配置。默认适配 OpenAI-compatible API；LLM 失败时工作台会返回可解释的失败状态或回退结果。

## 目录结构

```text
app/                 核心 Schema、编排、行业规则、证据与模型适配
backend/             FastAPI 匿名工作台 API
frontend/            React + TypeScript + Vite 前端
configs/             行业配置
data/manifests/      资料清单和来源元数据
data/raw/            本地演示资料
fixtures/            测试输入和合成 fixture
evaluation/          指标、Gold、实验运行器和图表
prompts/             LLM 提示词
tests/               核心、集成、评测和 API 测试
DEPLOYMENT.md        通用 Docker/Caddy 部署说明
```

## 开源与安全说明

- `.env`、模型 API Key、运行数据库和 `outputs/` 运行产物不会进入版本库；
- 前端不接触模型 API Key，模型调用只发生在后端；
- 公开仓库中的资料仅用于演示和复现，请自行确认资料的使用权限；
- 当前仓库未附带开源许可证。公开可见不等于自动授予代码再使用权；如需正式开源，请由项目组确定许可证并补充 `LICENSE`。

## 进一步阅读

- [部署说明](DEPLOYMENT.md)
- [公共接口契约](docs/CONTRACTS.md)
- [系统总方案](docs/MASTER_PLAN.md)
- [提交清单](docs/submission_checklist.md)
- [CI 配置](.github/workflows/ci.yml)
