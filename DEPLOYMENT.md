# AutoRegister 部署指南

## 前置条件

服务器端要求：

- Python 3.10+ 或 Docker
- Linux 系统（推荐 Ubuntu 20.04+）
- 至少 2GB 可用内存
- 至少 5GB 磁盘空间
- 可访问 Qwen 注册页与 Cloudflare Worker 邮箱服务

## 配置文件

当前项目有两类配置：

- `.env`：UI 模式、端口、浏览器代理等运行参数。
- `config.json`：Cloudflare Worker 邮箱与本地账号输出。

`config.json` 示例：

```json
{
  "cf_worker_domain": "mail.example.com",
  "cf_email_domain": [
    "example.com"
  ],
  "cf_admin_password": "replace-with-admin-password",
  "cf_enable_random_subdomain": true,
  "accounts_file": "accounts.txt"
}
```

成功注册并激活后，账号会追加写入 `accounts_file` 指向的文件，格式为：

```text
email@example.com:Password123
```

## 方案 A：使用 Docker 部署

### 1. 上传项目

```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  . username@your-server.com:/opt/auto-register/
```

### 2. 配置

```bash
ssh username@your-server.com
cd /opt/auto-register
cp .env.example .env
nano .env
nano config.json
```

### 3. 启动

```bash
docker-compose up -d --build
```

### 4. 验证

```bash
docker ps | grep auto-register
docker logs -f auto-register
curl http://localhost:18080/healthz
```

访问：

```text
http://your-server.com:18080
```

## 方案 B：直接部署

### 1. 上传项目

```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  . username@your-server.com:/opt/auto-register/
```

### 2. 安装依赖

```bash
ssh username@your-server.com
cd /opt/auto-register
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
playwright install chromium
```

### 3. 配置

```bash
cp .env.example .env
nano .env
nano config.json
```

### 4. 启动 Web 控制台

```bash
python -m auto_register --mode web --host 0.0.0.0 --port 18080
```

## systemd 服务示例

```bash
sudo tee /etc/systemd/system/auto-register.service > /dev/null << 'EOF'
[Unit]
Description=AutoRegister Web Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/auto-register
Environment="PATH=/opt/auto-register/.venv/bin"
ExecStart=/opt/auto-register/.venv/bin/python -m auto_register --mode web --host 0.0.0.0 --port 18080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable auto-register
sudo systemctl start auto-register
sudo journalctl -u auto-register -f
```

## 常用命令

```bash
docker-compose down
docker-compose restart
docker-compose up -d --build
docker logs auto-register
docker exec -it auto-register bash
```

## 代理配置

Playwright 浏览器读取代理的优先级：

1. `QWEN_PLAYWRIGHT_PROXY`
2. `PLAYWRIGHT_PROXY`
3. `HTTPS_PROXY`
4. `HTTP_PROXY`

示例：

```dotenv
QWEN_PLAYWRIGHT_PROXY=http://127.0.0.1:7897
QWEN_PLAYWRIGHT_PROXY_BYPASS=127.0.0.1,localhost
```
