# 快速部署参考

## 最快方式（Docker）

### 第 1 步：上传代码

```bash
bash upload.sh ubuntu 192.168.1.100 /opt/auto-register 18080
```

也可以手动上传：

```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' . ubuntu@192.168.1.100:/opt/auto-register/
```

### 第 2 步：配置

```bash
ssh ubuntu@192.168.1.100
cd /opt/auto-register
cp .env.example .env
nano .env
nano config.json
```

`config.json` 至少需要配置：

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

`.env` 只需要按需配置 UI 端口和代理。

### 第 3 步：启动服务

```bash
docker-compose up -d --build
docker logs -f auto-register
```

访问：

```text
http://192.168.1.100:18080
```

## 常用命令

| 操作 | 命令 |
|-----|------|
| 查看容器 | `docker ps` |
| 查看日志 | `docker logs -f auto-register` |
| 重启服务 | `docker-compose restart` |
| 停止服务 | `docker-compose down` |
| 更新代码 | `git pull && docker-compose up -d --build` |
| 进入容器 | `docker exec -it auto-register bash` |
| 查看端口占用 | `lsof -i :18080` 或 `netstat -tlnp` |

## 验证检查清单

- [ ] SSH 可以连接到服务器
- [ ] 文件已上传到 `/opt/auto-register`
- [ ] `.env` 已按需配置
- [ ] `config.json` 已配置 Worker 邮箱字段
- [ ] Docker 已安装：`docker --version`
- [ ] Docker Compose 已安装：`docker-compose --version`
- [ ] 端口 18080 未被占用
- [ ] Web UI 可访问：`curl http://localhost:18080/healthz`
- [ ] 成功注册后 `accounts.txt` 会追加 `email:password`

## 常见问题

**Docker not found**

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**Cannot connect to Docker daemon**

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

**Port 18080 already in use**

```bash
sudo lsof -i :18080
sudo kill -9 <PID>
```

或修改 `docker-compose.yml` 端口映射。
