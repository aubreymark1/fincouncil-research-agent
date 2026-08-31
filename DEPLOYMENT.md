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
curl http://127.0.0.1:18000/api/health
curl http://127.0.0.1:18000/
```

默认 Compose 只启动 backend。backend 镜像已经包含前端构建产物，并从
`WORKBENCH_STATIC_DIR` 提供 SPA；`caddy` 保留为可选的 standalone profile，
避免与服务器已有 Nginx 争用 80/443。

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

# 3.4 启动 backend（服务器已有 Nginx 时不要启用 standalone Caddy）
docker compose up -d --build

# 3.5 验证
curl -fsS http://127.0.0.1:18000/api/health
curl -fsSI https://${DEMO_HOST} | head -n 1
curl -fsS https://${DEMO_HOST}/api/cases
```

服务器已有 Nginx 时，应增加一个只属于 FinCouncil 的虚拟主机：

```nginx
server {
    listen 80;
    server_name fincouncil.43-165-172-190.sslip.io;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name fincouncil.43-165-172-190.sslip.io;
    # ssl_certificate /etc/letsencrypt/live/<host>/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/<host>/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

证书申请完成后，先从服务器本机检查 `curl -fsS
http://127.0.0.1:18000/`，再从公网检查 HTTPS 页面和 `/api/health`。

## 4. HTTPS 证书失败处理

公网 HTTPS 由服务器已有 Nginx 和 certbot 管理。backend 本身只监听
`127.0.0.1:18000`，不会申请或终止公网证书。配置 Nginx 后必须执行：

```bash
curl -fsS http://127.0.0.1:18000/api/health
curl -fsSI https://${DEMO_HOST} | head -n 1
```

如果证书获取失败（例如 DNS 未指向本机、80/443 未放行、certbot 的
HTTP-01 检查失败），必须**停止并报告**，不能静默降级为 HTTP：

```bash
docker compose down
```

报告内容至少包含：端口检查、DNS 解析结果、Nginx 错误日志和 certbot
HTTP-01 检查结果。

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
- `FINCOUNCIL_MODEL_TIMEOUT_SECONDS`（默认 120 秒，避免研究上下文较大时过早超时）
- `FINCOUNCIL_MODEL_MAX_TOKENS`（默认 8192，为推理和结构化正文保留足够输出空间）

其他字段有默认值，可按需调整。

## 7. 产品边界提醒

- 仅支持 `food_main`、`bank_main` 两个已验证资料包；
- 不做任意公司实时大规模爬虫；
- 不做登录、账户、多人协作、Redis、Celery、数据库集群；
- 不做自动交易、目标价、真实账户；
- 不暴露 API Key；
- 不生成 Gold 未签收情况下的正式 E0–E3 分数。
