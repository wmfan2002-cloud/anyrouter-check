# AnyRouter Check-in 自动签到

多平台多账号自动签到工具，支持 Docker 自部署（Web 管理面板）和 GitHub Actions 两种运行方式。兼容所有 NewAPI / OneAPI 平台，内置 AnyRouter 与 AgentRouter 配置。

## 功能特性

- 兼容 NewAPI / OneAPI 全系列平台
- 多账号管理，支持启用/禁用
- 两种认证方式：Cookie 模式 和 浏览器自动登录（无需手动提取 Cookie）
- NewAPI 模板 Provider：多个 NewAPI 站点只需创建账号时填域名，无需重复创建 Provider
- Web 管理面板（仪表盘、账号管理、Provider 管理、执行日志）
- 可配置签到间隔（1h ~ 24h / 自定义 Cron）
- 手动触发签到（全部/单个账号）
- WAF 自动绕过（Playwright 无头浏览器），误开 WAF 时自动回退重试
- 多种消息推送（Telegram / 钉钉 / 飞书 / 企业微信 / 邮箱 / PushPlus / Server酱 / Gotify / Bark）
- Docker Compose 一键部署，SQLite 数据持久化

---

## 快速开始（Docker 部署）

### 前置条件

- 一台 VPS 或本地服务器
- 已安装 Docker 和 Docker Compose

### 1. 克隆仓库

```bash
git clone https://github.com/wmfan2002-cloud/anyrouter-check.git
cd anyrouter-check
```

### 2. 修改配置

编辑 `docker-compose.yml`，修改管理密码：

```yaml
services:
  checkin:
    build: .
    container_name: anyrouter-checkin
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai              # 时区
      - ADMIN_PASSWORD=your_password   # 管理面板密码，请务必修改
    restart: unless-stopped
```

### 3. 构建并启动

```bash
docker compose up -d --build
```

首次构建需要下载 Chromium 浏览器，耐心等待。

### 4. 访问管理面板

浏览器打开 `http://你的服务器IP:8080`，使用设置的密码登录。

### 5. 更新版本

```bash
git pull
docker compose up -d --build
```

数据保存在 `./data` 目录中，更新不会丢失数据。

---

## 使用教程

### 仪表盘

登录后进入仪表盘，包含：

- **统计卡片**：账号总数、已启用数、签到成功/失败数
- **签到间隔**：右上角下拉菜单选择签到频率（默认每 6 小时）
- **立即全部签到**：手动触发所有已启用账号签到
- **账号状态卡片**：每个账号的余额、已用额度、上次签到时间，可单独手动签到
- **最近执行记录**：最近 10 条签到日志

### 添加账号

进入「账号管理」→ 点击「添加账号」，填写以下信息：

1. **名称**：自定义，便于识别
2. **Provider**：选择签到目标平台（见下方说明）
3. **域名**：选择 `newapi` 或 `newapi-waf` 模板时需要填写你的站点域名
4. **认证方式**：Cookie 模式 或 浏览器登录（二选一）

#### Cookie 模式

需要手动从浏览器提取两个值：

**获取 Cookie：**

1. 打开目标平台网站并登录
2. 按 F12 打开开发者工具
3. 进入 **Application**（应用）→ **Cookies** → 点击对应域名
4. 找到 `session` 字段，复制其值

Cookies 字段支持两种格式：

```
# 直接粘贴 session 值
eyJhbGciOiJIUzI1NiIs...

# 或 JSON 格式
{"session": "eyJhbGciOiJIUzI1NiIs..."}
```

**获取 API User ID：**

1. 在开发者工具中进入 **Network**（网络）选项卡
2. 勾选 **Fetch/XHR** 过滤
3. 刷新页面或进行任意操作
4. 点击任意请求，在请求头中找到 `New-Api-User` 字段
5. 复制该值（一串数字）

#### 浏览器自动登录

无需手动提取 Cookie，只需填写用户名/邮箱和密码。系统会通过无头浏览器自动完成登录、签到和余额查询。

> 浏览器模式每次签到会启动浏览器进程，资源消耗略高。如果 Cookie 长期稳定，推荐 Cookie 模式。

### Provider 说明

Provider 是签到目标平台的配置。系统内置以下 Provider：

| 名称 | 说明 | 域名 |
|------|------|------|
| `newapi` | NewAPI 标准模板（无 WAF） | 创建账号时填写 |
| `newapi-waf` | NewAPI + WAF 绕过模板 | 创建账号时填写 |
| `anyrouter` | AnyRouter 平台 | anyrouter.top（固定） |
| `agentrouter` | AgentRouter 平台 | agentrouter.org（固定） |

**签到 AnyRouter / AgentRouter**：直接选择对应 Provider，无需填域名。

**签到其他 NewAPI 站点**：选择 `newapi`（大多数情况）或 `newapi-waf`（站点有阿里云 WAF 防护时），然后在域名栏填写站点地址，如 `https://api.example.com`。多个 NewAPI 站点只需创建多个账号，分别填不同域名即可，不用重复创建 Provider。

**自定义 Provider**：如果目标平台的 API 路径与 NewAPI 标准不同，可在「Provider 管理」中添加自定义 Provider，手动配置所有字段。

### WAF 绕过

部分站点使用 WAF（如阿里云 WAF）防护，直接请求会被拦截。选择 `newapi-waf` 模板或在自定义 Provider 中设置 WAF 绕过为 `waf_cookies` 即可。

如果你不确定是否需要 WAF 绕过，可以先选 `newapi`（不绕过）。如果签到失败且开启了 WAF 绕过，系统会自动尝试关闭 WAF 重试，并在日志中提示你调整设置。

### 签到间隔

在仪表盘右上角选择签到频率：

| 选项 | Cron 表达式 |
|------|------------|
| 每 1 小时 | `0 * * * *` |
| 每 2 小时 | `0 */2 * * *` |
| 每 4 小时 | `0 */4 * * *` |
| 每 6 小时 | `0 */6 * * *`（默认） |
| 每 8 小时 | `0 */8 * * *` |
| 每 12 小时 | `0 */12 * * *` |
| 每天一次 | `0 0 * * *` |
| 自定义 | 标准 5 字段 Cron |

> AnyRouter 签到间隔约 24 小时（非零点重置），建议每 6~8 小时签到一次以确保不遗漏。

### 执行日志

「执行日志」页面记录所有签到操作，支持按状态和账号筛选，带分页。

每条日志包含：时间、账号、Provider、状态、余额、已用额度、触发方式（手动/定时）、详细信息。失败日志会自动归类原因并给出建议。

---

## 通知配置

签到失败或余额变化时自动发送通知。在 `docker-compose.yml` 中取消对应通知方式的注释并填入配置：

### Telegram Bot

```yaml
- TELEGRAM_BOT_TOKEN=你的Bot_Token
- TELEGRAM_CHAT_ID=你的Chat_ID
```

### 钉钉机器人

```yaml
- DINGDING_WEBHOOK=你的Webhook地址
```

> 创建钉钉机器人时选择「自定义关键词」，填写 `AnyRouter`。

### 飞书机器人

```yaml
- FEISHU_WEBHOOK=你的Webhook地址
```

### 企业微信机器人

```yaml
- WEIXIN_WEBHOOK=你的Webhook地址
```

### PushPlus

```yaml
- PUSHPLUS_TOKEN=你的Token
```

### Server 酱

```yaml
- SERVERPUSHKEY=你的SendKey
```

### 邮箱（SMTP）

```yaml
- EMAIL_USER=发件人邮箱地址
- EMAIL_PASS=邮箱密码或授权码
- EMAIL_TO=收件人邮箱地址
# 可选
- EMAIL_SENDER=显示的发件人地址
- CUSTOM_SMTP_SERVER=自定义SMTP服务器
```

### Gotify

```yaml
- GOTIFY_URL=https://your-gotify-server/message
- GOTIFY_TOKEN=应用访问令牌
- GOTIFY_PRIORITY=9
```

### Bark

```yaml
- BARK_KEY=你的Bark_Key
# 可选，默认 https://api.day.app
- BARK_SERVER=自建Bark服务器地址
```

可同时启用多种通知方式。修改后需重启容器：

```bash
docker compose up -d
```

---

## GitHub Actions 方式

不想自建服务器也可通过 GitHub Actions 运行。

### 1. Fork 本仓库

### 2. 配置 Secrets

进入仓库 **Settings** → **Environments** → 新建 `production` 环境，添加 Secret：

- Name: `ANYROUTER_ACCOUNTS`
- Value: JSON 格式账号配置

```json
[
  {
    "name": "我的主账号",
    "cookies": { "session": "你的session值" },
    "api_user": "12345"
  },
  {
    "name": "AgentRouter 账号",
    "provider": "agentrouter",
    "cookies": { "session": "你的session值" },
    "api_user": "67890"
  }
]
```

| 字段 | 必需 | 说明 |
|------|------|------|
| `cookies` | 是 | 身份验证 Cookie |
| `api_user` | 是 | New-Api-User 请求头的值 |
| `name` | 否 | 显示名称 |
| `provider` | 否 | Provider 标识，默认 `anyrouter` |

### 3. 启用 Actions

进入 **Actions** → 启用「AnyRouter 自动签到」→ 可手动 **Run workflow** 测试。

### 4. 通知配置（可选）

在 `production` 环境的 Secrets 中添加对应通知环境变量（参见上方通知配置章节）。

---

## 故障排除

| 现象 | 可能原因 | 解决方法 |
|------|----------|----------|
| 401 错误 | Cookie 已过期 | 重新获取 Cookie 或改用浏览器自动登录 |
| Turnstile token 为空 | 站点启用了 Cloudflare Turnstile 验证 | 该站点暂不支持 Cookie 模式签到 |
| 浏览器登录超时 | 网络问题或页面结构变化 | 检查日志 `docker logs anyrouter-checkin` |
| Provider not found | 账号关联的 Provider 不存在 | 在 Provider 管理中添加对应配置 |
| WAF 绕过提示 | 不需要 WAF 绕过 | 将 Provider 的 WAF 绕过设置为空 |

### 常用命令

```bash
# 查看日志
docker logs anyrouter-checkin --tail 50

# 实时查看日志
docker logs -f anyrouter-checkin

# 重启
docker compose restart

# 完全重建
docker compose down && docker compose up -d --build
```

### 数据备份

所有数据保存在 `./data/checkin.db`（SQLite），备份此文件即可。

---

## 免责声明

本项目仅用于学习和研究目的，使用前请确保遵守相关网站的使用条款。
