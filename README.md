# AutoRegister - Qwen Register + Activate + Local Accounts

当前版本目标：

1. 自动注册 Qwen 账号
2. 自动完成邮箱激活
3. 激活成功后将 `email:password` 追加保存到本地文本文件

本地 OAuth、远程 CLI Proxy 认证、CPA 上传、OpenClaw Gateway 相关逻辑不在当前活动链路中执行。

## 当前流程

1. 使用 Cloudflare Worker 临时邮箱创建邮箱
2. 打开 Qwen 注册页并提交注册
3. 按 Worker 拉信接口轮询新邮件
4. 从激活邮件中提取链接并打开
5. 将本次注册凭据追加写入本地 `accounts.txt`

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 快速启动（Windows）

```powershell
.\scripts\start.ps1
```

默认会启动 Web 控制台（端口 18080）。首次建议不加 `-SkipInstall`。依赖已准备好后可使用：

```powershell
.\scripts\start.ps1 -SkipInstall
```

打开浏览器访问：

```text
http://127.0.0.1:18080
```

如需桌面 GUI：

```powershell
.\scripts\start.ps1 -Mode gui
```

## Docker Compose 启动

```bash
docker compose up -d --build
```

访问：

```text
http://127.0.0.1:18080
```

停止：

```bash
docker compose down
```

## 关键配置

### Worker 邮箱与账号输出

当前项目使用根目录 `config.json` 维护邮箱和本地输出配置，字段名与 `codexoauthloop` 的 Cloudflare Worker 邮箱字段保持一致：

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

字段说明：

- `cf_worker_domain`：Cloudflare Worker 邮箱服务域名，不包含协议。
- `cf_email_domain`：可创建邮箱的域名列表。
- `cf_admin_password`：Worker `/admin/new_address` 使用的管理密码。
- `cf_enable_random_subdomain`：创建邮箱时是否启用随机子域。
- `accounts_file`：激活成功后追加写入的本地账号文件。

输出格式：

```text
email@example.com:Password123
```

### 浏览器代理（注册/激活页）

Playwright 浏览器会按以下优先级读取代理：

1. `QWEN_PLAYWRIGHT_PROXY`
2. `PLAYWRIGHT_PROXY`
3. `HTTPS_PROXY`
4. `HTTP_PROXY`

示例：

```dotenv
QWEN_PLAYWRIGHT_PROXY=http://127.0.0.1:7897
QWEN_PLAYWRIGHT_PROXY_BYPASS=127.0.0.1,localhost,192.168.10.219
```

在 Docker 内如果代理在宿主机，请用 `host.docker.internal`：

```dotenv
HTTP_PROXY=http://host.docker.internal:7897
HTTPS_PROXY=http://host.docker.internal:7897
```

## 归档说明

归档说明文档：

1. `src/auto_register/archive/README.md`
2. `src/auto_register/integrations/ARCHIVED_LEGACY.md`
3. `src/auto_register/utils/ARCHIVED_LEGACY.md`
4. `src/auto_register/writer/ARCHIVED_LEGACY.md`
