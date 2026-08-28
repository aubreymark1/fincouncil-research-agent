# FinCouncil 匿名体验版投研工作台部署文档

> 部署目录固定为 `/opt/fincouncil`。  
> 域名使用 sslip.io 自动 HTTPS，例如 `fincouncil.43-165-172-190.sslip.io`。

## 1. 前置条件

- Ubuntu 服务器（已安装 Docker Engine + Docker Compose Plugin）；
- 公网 IP，且安全组/防火墙放行 `80`、`443`；
- 服务器可访问 `github.com` 或本仓库可被拷贝到 `/opt/fincouncil`；
- 如启用 AI 增强模式，需要 DeepSeek API Key；
- 不得修改服务器上 `/opt/fincouncil` 以外的文件，尤其不得触碰 `/opt/matrix_oj_clone`。

## 2. 本地验证

```bash
# 后端 API 测试
python -m pytest tests/api tests/core -q

# 前端 production build
cd frontend && npm ci && npm run build && cd ..

# 本地 Docker Compose 启动
cp .env.example .env   # 按需修改 DEMO_HOST 和 API Key
docker compose up -d --build
curl http://localhost/api/health
```

## 3. 服务器部署

```bash
# 3.1 创建部署目录并进入
sudo mkdir -p /opt/fincouncil
sudo chown $USER /opt/fincouncil
cd /opt/fincouncil

# 3.2 获取代码（若服务器能访问 GitHub）
git clone https://github.com/aubreymark1/fincouncil-research-agent.git .
git checkout feature/anonymous-workbench-deploy

# 3.3 创建 .env（服务器上人工填写）
cp .env.example .env
# 必须填写：
#   DEMO_HOST=你的sslip域名
#   如果启用 LLM：FINCOUNCIL_ENABLE_LLM_DEMO=true
#   FINCOUNCIL_MODEL_API_KEY=你的DeepSeek Key
#   FINCOUNCIL_MODEL_PROVIDER/NAME/BASE_URL 按默认即可

# 3.4 启动
docker compose up -d --build

# 3.5 验证
curl -fsS https://${DEMO_HOST}/api/health
curl -fsSI https://${DEMO_HOST} | head -n 1
curl -fsS https://${DEMO_HOST}/api/cases
```

## 4. HTTPS 证书失败处理

Caddy 配置为自动 HTTPS。启动后必须执行：

```bash
docker compose logs caddy --tail 200
curl -fsSI https://${DEMO_HOST} | head -n 1
```

如果证书获取失败（例如 DNS 未指向本机、80/443 未放行、Caddy 日志出现 `certificate` 或 `HTTP-01` 错误），必须**停止并报告**，不能静默降级为 HTTP：

```bash
docker compose down
```

报告内容至少包含：端口检查、DNS 解析结果、Caddy 日志中的 HTTP-01 检查结果。

## 5. 回滚

```bash
cd /opt/fincouncil
# 备份当前部署（仅备份本目录内文件）
ts=$(date +%Y%m%d-%H%M%S)
cp docker-compose.yml docker-compose.yml.bak-$ts
cp .env .env.bak-$ts
# 回滚到上一个 git commit（不使用 rebase/force push）
git checkout <上一个可用commit>
docker compose up -d --build
```

如果镜像构建失败，可回退到上一份 `docker-compose.yml.bak-*`：

```bash
cp docker-compose.yml.bak-<ts> docker-compose.yml
docker compose up -d --build
```

## 6. 服务器 .env 需要人工填写的字段

- `DEMO_HOST`
- `FINCOUNCIL_ENABLE_LLM_DEMO`（只有需要 AI 增强才设 `true`）
- `FINCOUNCIL_MODEL_API_KEY`（DeepSeek API Key，服务器上只存在 `.env`）

其他字段有默认值，可按需调整。

## 7. 产品边界提醒

- 仅支持 `food_main`、`bank_main` 两个已验证资料包；
- 不做任意公司实时大规模爬虫；
- 不做登录、账户、多人协作、Redis、Celery、数据库集群；
- 不做自动交易、目标价、真实账户；
- 不暴露 API Key；
- 不生成 Gold 未签收情况下的正式 E0–E3 分数。
