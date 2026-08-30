# FinCouncil 匿名体验版部署说明

本文档提供通用部署流程。请将服务器 IP、域名、API Key 和其他环境信息只保存在服务器控制台或 `.env` 中，不要提交到 Git。

## 前置条件

- Ubuntu 服务器；
- Docker Engine 和 Docker Compose Plugin；
- 安全组/防火墙放行 `80`、`443`；
- 服务器可以访问 GitHub 和模型服务；
- 如启用 AI 增强，需要一个 OpenAI-compatible 模型服务和 API Key。

## 本地检查

```bash
python -m pytest tests/api tests/core -q
cd frontend && npm ci && npm run build && cd ..
```

## 服务器部署

```bash
sudo mkdir -p /opt/fincouncil
sudo chown "$USER" /opt/fincouncil
cd /opt/fincouncil

git clone https://github.com/aubreymark1/fincouncil-research-agent.git .
git switch main

cp .env.example .env
# 编辑 .env：
# DEMO_HOST=你的IP转换成短横线后的.sslip.io域名
# FINCOUNCIL_ENABLE_LLM_DEMO=true
# FINCOUNCIL_MODEL_API_KEY：只在服务器填写的真实 Key

docker compose up -d --build
```

## 验证

```bash
curl -fsS "https://${DEMO_HOST}/api/health"
curl -fsS "https://${DEMO_HOST}/api/cases"
curl -fsSI "https://${DEMO_HOST}" | head -n 1
docker compose ps
```

如果使用自定义域名，先把 DNS A 记录指向服务器，再等待 Caddy 自动申请 HTTPS 证书。证书失败时查看：

```bash
docker compose logs caddy --tail 200
```

不要把 HTTPS 静默降级为 HTTP；应先修复 DNS、端口或证书申请问题。

## 环境变量

必须按需配置：

- `DEMO_HOST`：公开访问域名；
- `FINCOUNCIL_ENABLE_LLM_DEMO`：是否启用 LLM；
- `FINCOUNCIL_MODEL_PROVIDER`、`FINCOUNCIL_MODEL_NAME`、`FINCOUNCIL_MODEL_BASE_URL`：模型服务配置；
- `FINCOUNCIL_MODEL_API_KEY`：服务器本地的模型 Key，不提交到 Git；
- `FINCOUNCIL_MODEL_TIMEOUT_SECONDS`、`FINCOUNCIL_MODEL_MAX_RETRIES`：模型超时和重试。

## 更新与回滚

```bash
cd /opt/fincouncil
git pull --ff-only origin main
docker compose up -d --build
```

更新前可以在服务器上备份 `docker-compose.yml` 和 `.env`。`.env` 只应保存在服务器本地，备份时注意访问权限。

## 运行边界

- 当前 MVP 只提供仓库中已配置的食品饮料和银行演示案例；
- 不包含自动交易、真实账户、目标价和大规模实时爬虫；
- 匿名体验版应配置限流，并禁止提交敏感资料；
- 报告内容不构成投资建议。
