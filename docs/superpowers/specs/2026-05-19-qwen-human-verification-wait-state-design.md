# Qwen Human Verification Wait State Design

## Goal

当 Qwen 注册流程触发 `Access Verification` 等真人校验页面时，不将其视为普通失败，而是进入一个可恢复的“等待人工验证”运行阶段：

1. Web UI 弹出等待人工验证的遮罩层。
2. 保持当前 Playwright 浏览器会话存活。
3. 用户在可见浏览器窗口中手动完成真人校验。
4. 后端自动检测页面离开校验态后，继续后续激活邮件与本地账号保存流程。

## Current Problem

当前实现把注册提交流程视为线性自动化链路：

1. 提交注册表单
2. 立即等待激活邮件
3. 打开激活链接
4. 写入 `accounts.txt`

但真实运行中，Qwen 有时在提交注册后返回 `Access Verification` 页面。这时：

- 页面尚未进入待激活状态
- 后端仍继续等待邮件
- 最终表现为“收不到激活邮件”

根因不是邮箱服务必然故障，而是注册链路进入了需要人工干预的新状态。

## Requirements

### Functional Requirements

1. 后端必须识别 `Access Verification` 或等价真人校验页面。
2. 识别后，运行状态切换为 `waiting_human_verification`。
3. Web UI 在该状态下显示明显的人工验证提示层。
4. 校验阶段必须保持同一个 Playwright 浏览器会话和页面对象。
5. 用户应在可见浏览器窗口中完成手动验证。
6. 一旦页面离开校验态，后端自动恢复执行，不要求用户再点击“继续”。
7. 恢复后继续走激活邮件、激活链接、本地写入 `accounts.txt` 的既有流程。
8. 保留停止能力，用户在人工验证阶段也能中止任务。

### Non-Functional Requirements

1. 不引入 iframe 嵌入外部校验页面的假设。
2. 不依赖无头浏览器完成人工验证。
3. 不将“等待人工验证”与“失败”混淆。
4. 状态切换和日志应足够明确，便于排查卡在哪一层。

## Architecture

## Runtime States

当前 Web 运行态需要从简单的 `running/success/error` 扩展为更明确的状态机：

- `running`
- `waiting_human_verification`
- `success`
- `error`
- `stopped`

其中：

- `running`：正常自动执行
- `waiting_human_verification`：自动链路暂停，等待用户在浏览器中完成真人校验
- `success`：流程完成并已写入本地账号
- `error`：流程异常退出
- `stopped`：用户主动中止

## High-Level Flow

1. 创建邮箱并记录快照
2. 打开注册页并提交
3. 检查是否进入真人校验页
4. 若未进入：
   - 继续等待激活邮件
5. 若进入：
   - 状态切换到 `waiting_human_verification`
   - 浏览器保持打开
   - Web UI 显示等待人工验证遮罩
   - 后端持续轮询页面状态
6. 页面离开校验态后：
   - 状态恢复为 `running`
   - 自动进入激活邮件等待
7. 激活成功后写入 `accounts.txt`

## Browser Strategy

## Visible Browser Requirement

在 Web UI 模式下，一旦检测到真人校验需求，后端必须保证用户有一个可交互的浏览器窗口可以操作。

推荐策略：

- 当请求参数是 `headless=False` 时，直接使用现有可见浏览器。
- 当请求参数是 `headless=True` 时，如果流程进入真人校验阶段，记录日志并切换到可见浏览器模式。

设计原因：

- 人工验证无法依赖无头浏览器完成。
- 在无头会话上等待用户操作没有意义。
- 从架构上应把“人工验证阶段需要可见浏览器”作为显式规则，而不是隐含假设。

## Session Preservation

校验阶段必须保留：

- 当前 browser
- 当前 context
- 当前 page
- 当前注册会话中的 cookie / localStorage / challenge state

不能通过“关闭再重开”来过渡到人工验证阶段，否则很容易丢失挑战上下文。

## Detection Rules

## Human Verification Signals

注册提交后，需要在进入等邮件前检查页面是否处于真人校验状态。首版信号可以采用文本检测：

- `Access Verification`
- `Please complete the operation to verify that you are a real person`

同时保留 URL 和页面文案摘要到日志，便于定位：

- 当前 URL
- 页面 body 关键文本摘要

后续如 Qwen 校验 UI 变体增多，可扩展为：

- 文本规则
- 结构规则
- TraceID/错误块规则

## Exit Rules

后端每隔 1-2 秒重新检查当前 page：

- 若仍命中校验信号，继续等待
- 若页面离开校验信号，退出 `waiting_human_verification`
- 若页面被关闭，按错误处理
- 若用户发出停止请求，按停止处理

## Web UI Design

## Status Surface

`/api/status` 需要返回新的状态字段，例如：

- `phase`
- `waiting_human_verification`
- `phase_message`

当前日志仍保留，但不能只依赖日志让前端猜测是否处于人工验证阶段。

## Verification Overlay

当状态为 `waiting_human_verification` 时，Web UI 显示一个高优先级遮罩层：

- 标题：等待人工验证
- 文案：请在浏览器窗口完成真人校验，完成后流程会自动继续
- 辅助信息：
  - 当前步骤
  - 最近日志摘要
  - 是否已检测到页面离开校验态

此阶段不需要“继续”按钮，因为用户已经明确选择“自动等待直到完成”。

保留“停止”按钮，防止无限等待。

## Backend Integration

## RuntimeState Changes

`RuntimeState` 需要新增显式状态字段，而不是只靠：

- `running`
- `success`
- `error`

建议新增：

- `phase: str`
- `phase_message: Optional[str]`

并提供方法：

- `set_phase(phase, message=None)`

这样 `QwenPortalRunner` 可以通过回调把运行态从后端推给 Web 层。

## Runner Integration

`QwenPortalRunner` 需要新增一个可选回调，例如：

- `on_phase_change`

用于在以下节点发出状态切换：

- `running`
- `waiting_human_verification`
- `running`（从人工验证恢复）

这样不会把 Web 状态控制强耦合进 runner 本身。

## Error Handling

以下情况需要明确区分：

### User Stop

- 人工验证阶段用户点击停止
- 后端停止等待
- 浏览器关闭
- 流程进入 `stopped`

### Browser Closed

- 用户手动关闭了用于人工验证的浏览器
- 后端检测 page/browser 已失效
- 流程进入 `error`
- 日志明确标记：人工验证过程中浏览器已关闭

### Left Verification But Not Activated

若用户离开校验页后，页面没有进入待激活或可继续状态，而是回到了无效页面：

- 记录当前 URL 和页面摘要
- 流程按失败处理
- 不直接伪装成“收不到邮件”

### Repeated Verification

若同一轮中多次进入校验页：

- 复用同一个 `waiting_human_verification` 状态
- 不重复打开多层 UI
- 日志记录为再次进入校验态

## Testing Strategy

### Unit Tests

1. `qwen_portal.py`
   - 提交注册后命中校验页时进入 `waiting_human_verification`
   - 离开校验页后恢复 `running`
   - 恢复后继续等待激活邮件
   - 人工验证阶段收到停止请求会退出
   - 人工验证阶段浏览器关闭会失败

2. `web/app.py`
   - `/api/status` 返回新的 phase 信息
   - `RuntimeState` 能表示 `waiting_human_verification`

3. 前端状态渲染
   - `waiting_human_verification` 时显示遮罩
   - 恢复 `running` 时遮罩消失

### Manual Verification

需要一次真实流程验证：

1. 触发 `Access Verification`
2. Web UI 进入等待人工验证态
3. 用户在浏览器完成校验
4. 流程自动继续
5. 成功写入 `accounts.txt`

## Non-Goals

本次不做以下内容：

- 在 Web UI 中 iframe 内嵌外部校验页
- 在无头浏览器内完成人工验证
- 支持多个并发人工验证任务
- 自动求解验证码
- 重做 GUI 端同等交互
