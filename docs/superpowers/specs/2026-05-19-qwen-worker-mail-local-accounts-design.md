# Qwen Worker Mail Local Accounts Design

## Goal

将当前项目的邮箱创建与收信链路改为复用 `codexoauthloop` 中的 Cloudflare Worker 模式，并在 Qwen 邮箱激活成功后立即结束流程，只将 `email:password` 追加写入本地文本文件。

## Current State

当前项目的活动链路为：

1. 使用 `Mail.tm / 1secMail / 旧 Cloud Mail` 创建临时邮箱
2. Playwright 打开 Qwen 注册页并提交
3. 轮询邮箱获取激活链接并打开
4. 调用远程 CLI Proxy API 获取登录链接
5. 自动完成远程授权页登录与确认
6. 认证文件由远程服务维护

这个设计会移除第 4-6 步，并替换第 1、3 步的邮件实现。

## Requirements

### Functional Requirements

1. 邮箱创建方式改为 `codexoauthloop` 的 Cloudflare Worker 方式。
2. 接取邮件并提取激活链接的方式改为 `codexoauthloop` 的 Worker 拉信方式与“快照后轮询新邮件”模式。
3. 不使用 LuckMail。
4. 不使用 Outlook 池。
5. 不读取上级目录 `codexoauthloop/config.json`。
6. 当前项目自行维护一份 `config.json`，字段命名复用 `codexoauthloop` 的邮件配置字段。
7. 在邮箱激活成功后立即结束，不再调用远程 `CLI Proxy API`。
8. 成功时将 `email:password` 按行追加到本地文本文件。
9. 不上传 CPA，不写远端认证文件。

### Non-Functional Requirements

1. 保持现有 Web / GUI 入口结构不变。
2. 邮件配置与运行时 `.env` 配置分离。
3. 新邮件轮询逻辑应避免消费旧邮件。
4. 写入账号文件时应明确失败，不允许静默丢失。

## Config Design

### New Config File

在仓库根目录新增 `config.json`，只承载邮件相关配置。

### Config Keys

配置字段沿用 `codexoauthloop` 命名：

- `cf_worker_domain`
- `cf_email_domain`
- `cf_admin_password`
- `cf_enable_random_subdomain`

### Config Boundaries

- `config.json`
  - 用于 Cloudflare Worker 邮箱创建、拉信。
- `.env`
  - 继续用于 UI 模式、服务端口、Playwright 代理等运行时配置。

账号输出路径固定为项目根目录 `accounts.txt`。

不会将 LuckMail、Outlook、CPA、远程认证相关配置迁入当前活动链路。

## Architecture

### High-Level Flow

1. 读取 `.env`，启动 Web 或 GUI。
2. 读取当前项目 `config.json` 中的 Worker 邮件配置。
3. 使用 Cloudflare Worker 创建临时邮箱。
4. Playwright 打开 Qwen 注册页并提交注册。
5. 记录当前邮箱快照，仅轮询后续新邮件。
6. 从新邮件正文中提取激活链接。
7. 浏览器打开激活链接完成邮箱激活。
8. 将 `email:password` 追加写入本地账号文件。
9. 流程结束。

### Removed Flow

以下链路从当前活动流程中移除：

- `CLI_PROXY_API_BASE_URL` / `CLI_PROXY_API_KEY` 远程管理 API 调用
- `qwen-auth-url` 获取登录链接
- 打开远程授权页并自动确认
- `get-auth-status` 轮询
- 远端认证文件观测

## File-Level Design

### Add `config.json`

职责：

- 保存当前项目自己的 Cloudflare Worker 邮件配置

### Add `src/auto_register/config.py`

职责：

- 从仓库根目录读取 `config.json`
- 校验必须字段
- 为其他模块提供受控读取接口

设计原则：

- 不与 `.env` 读取逻辑耦合
- 缺失字段时抛出明确错误

### Replace `src/auto_register/providers/one_sec_mail_provider.py`

职责重构为：

- 创建 Cloudflare Worker 临时邮箱
- 拉取 Worker 邮件列表
- 记录旧邮件快照
- 轮询新邮件
- 从邮件正文提取激活链接

不再作为当前主链路保留：

- `Mail.tm`
- `1secMail`
- 旧 `cloudflare/cloudmail/mailcraft` 配置模式
- LuckMail

### Add `src/auto_register/writer/accounts_writer.py`

职责：

- 将 `email:password` 追加写入文本文件
- 必要时创建父目录
- 提供清晰异常给调用方

输出格式固定为：

```text
email@example.com:Password123
```

### Modify `src/auto_register/integrations/qwen_portal.py`

职责变化：

- 保留注册页自动填写、提交、激活链接打开
- 移除远程认证模式判断与执行
- 在激活成功后调用本地账号写入器
- 成功条件改为“激活成功且本地写入成功”

### Keep `src/auto_register/web/app.py`

保留现有控制台和任务调度框架，但文案和日志应体现新的结束条件：

- 注册
- 激活
- 本地保存

而不是远程认证。

## Mail Data Model

Worker 邮件轮询层统一把邮件标准化为如下结构：

- `id`
- `subject`
- `source`
- `raw`

这样可以复用同一种“快照 -> 轮询 -> 提取链接”的逻辑，而不把 Worker 原始返回结构传播到业务层。

## Activation Link Extraction

### Source

从标准化邮件对象的 `raw` 字段中提取激活链接。

### Extraction Rule

提取逻辑沿用当前项目已有思路：

- 先匹配 `https://...`
- 优先选择包含 `verify` / `activate` / `confirm` / `token` / `auth` 等关键词的链接
- 若没有关键词匹配，则回退为第一条 `https` 链接

### Polling Rule

采用 `codexoauthloop` 风格的新邮件轮询：

1. 进入等待阶段前先记录当前邮箱已有邮件 ID 快照
2. 后续轮询只消费不在快照中的邮件
3. 收到新邮件后立即尝试提取链接
4. 超时前持续轮询

## Success and Failure Semantics

### Success

只有在以下条件全部满足时才视为成功：

1. 临时邮箱创建成功
2. 注册表单提交成功
3. 收到新邮件并提取到激活链接
4. 激活链接打开成功
5. `email:password` 成功写入本地账号文件

### Failure

以下任一情况都视为失败，并且不得写入账号文件：

- 邮箱创建失败
- 注册页操作失败
- 激活邮件等待超时
- 邮件存在但无法提取激活链接
- 打开激活链接失败

若激活成功但本地文件写入失败，也按整体失败处理，并暴露明确错误，防止出现实际成功但本地无记录的隐性状态。

## Testing Strategy

### Unit Tests

1. `config.py`
   - 成功读取 `config.json`
   - 缺失必填字段时报错

2. Worker 邮件 provider
   - 创建邮箱请求体包含正确字段
   - 能记录快照并跳过旧邮件
   - 能从新邮件正文提取激活链接
   - 超时时返回失败

3. `accounts_writer.py`
   - 能按行追加 `email:password`
   - 多次写入不会覆盖旧内容

4. `qwen_portal.py`
   - 激活成功后调用本地写入器并结束
   - 不再调用远程认证分支

### Verification Scope

本次实现默认做低风险验证：

- 测试文件运行
- 导入检查
- 必要的静态运行检查

不默认执行真实网络注册。

## Migration Notes

### Documentation Updates

需要同步更新：

- `README.md`
- `ARCHITECTURE.md`
- `.env.example`

重点修改：

- 删除当前活动链路中的远程认证描述
- 增加 `config.json` 的邮件配置说明
- 说明输出文件固定为本地 `accounts.txt`

### Backward Compatibility

本次改动不保证兼容旧的远程认证链路配置。

旧环境中的以下配置将不再是主流程必需项：

- `QWEN_AUTH_MODE`
- `CLI_PROXY_API_BASE_URL`
- `CLI_PROXY_API_KEY`

这些字段可以暂时保留在 `.env.example` 中作为历史兼容说明，但活动流程不再依赖它们。

## Non-Goals

本次不做以下事项：

- 集成 LuckMail
- 集成 Outlook 邮箱池
- 保留或重做 CPA 上传
- 保留远程 CLI Proxy API 认证接力
- 引入新的数据库或持久化层
- 重做 Web / GUI 架构
