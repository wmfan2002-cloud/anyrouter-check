# AnyRouter Check-in 多账号自动签到

多平台多账号自动签到工具，支持 **VPS 自部署（Docker + Web 管理面板）** 和 **GitHub Actions** 两种运行方式。理论上支持所有 NewAPI / OneAPI 平台，内置 AnyRouter 与 AgentRouter 配置，其它平台可自行添加。

用于 Claude Code 中转站 [AnyRouter](https://anyrouter.top/register?aff=qrQ2) 网站多账号每日签到，一次 $25。

## 功能特性

- 多平台支持（兼容 NewAPI / OneAPI）
- 多账号管理，支持启用 / 禁用
- 两种认证方式：**Cookie 模式** 和 **浏览器自动登录**（无需手动提取 Cookie）
- Web 管理面板（仪表盘、账号管理、Provider 管理、执行日志）
- 自定义签到间隔（1h / 2h / 4h / 6h / 8h / 12h / 24h / 自定义 Cron）
- 手动触发签到（全部 / 单个账号）
- 多种消息推送通知（Telegram / 钉钉 / 飞书 / 企业微信 / 邮箱等）
- 自动绕过 WAF 限制（Playwright 无头浏览器）
- Docker Compose 一键部署
- 数据持久化（SQLite）

---

## 目录

- [快速开始（Docker 部署）](#快速开始docker-部署)
- [Web 管理面板使用指南](#web-管理面板使用指南)
  - [登录](#登录)
  - [仪表盘](#仪表盘)
  - [账号管理](#账号管理)
  - [Provider 管理](#provider-管理)
  - [执行日志](#执行日志)
- [账号认证方式](#账号认证方式)
  - [Cookie 模式](#cookie-模式)
  - [浏览器自动登录](#浏览器自动登录)
- [签到间隔设置](#签到间隔设置)
- [通知配置](#通知配置)
- [GitHub Actions 方式](#github-actions-方式)
- [本地开发](#本地开发)
- [故障排除](#故障排除)
- [免责声明](#免责声明)

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

编辑 `docker-compose.yml`，修改管理密码和时区：

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
      - TZ=Asia/Shanghai          # 时区，根据你所在地区修改
      - ADMIN_PASSWORD=your_password  # 管理面板登录密码，请务必修改
    restart: unless-stopped
```

### 3. 构建并启动

```bash
docker compose up -d --build
```

首次构建需要下载 Chromium 浏览器，耐心等待即可。

### 4. 访问管理面板

打开浏览器访问：

```
http://你的服务器IP:8080
```

使用你在 `docker-compose.yml` 中设置的 `ADMIN_PASSWORD` 登录。

### 5. 更新版本

```bash
git pull
docker compose up -d --build
```

数据保存在 `./data` 目录中，更新不会丢失数据。

---

## Web 管理面板使用指南

### 登录

访问管理面板后会自动跳转到登录页面，输入 `ADMIN_PASSWORD` 中配置的密码即可登录。登录状态保持 7 天。

### 仪表盘

仪表盘是主页面，包含以下信息：

- **统计卡片**：账号总数、已启用数、签到成功数、签到失败数
- **签到间隔设置**：右上角的下拉菜单可以选择签到频率
- **下次签到时间**：显示下一次自动签到的时间
- **立即全部签到**：手动触发所有已启用账号的签到
- **账号状态卡片**：每个账号的详细状态（余额、已用额度、上次签到时间等）
- **最近执行记录**：最近 10 条签到日志

每个账号卡片上都有 **手动签到** 按钮，可以单独触发某个账号的签到。

### 账号管理

在「账号管理」页面可以进行：

- **添加账号**：点击「添加账号」按钮，填写账号信息
- **编辑账号**：修改账号名称、Provider、认证信息
- **删除账号**：删除不需要的账号
- **启用 / 禁用**：临时停用某个账号的自动签到

### Provider 管理

Provider 是签到目标平台的配置。系统内置了三个 Provider：

| 名称 | 域名 | WAF 绕过 |
|------|------|----------|
| new-api | https://new-api.example.com | waf_cookies |
| anyrouter | https://anyrouter.top | waf_cookies |
| agentrouter | https://agentrouter.org | waf_cookies |

内置 Provider 为只读，不可编辑或删除。如果你需要签到其他 NewAPI / OneAPI 平台，可以点击「添加 Provider」自行配置。

新增 Provider 时可先选择模板：
- `new-api 标准模板`：预填推荐域名和常用路径。
- `agentrouter 自动签到模板`：预填 agentrouter 推荐配置。
- `完全自定义`：保留当前填写内容，不覆盖任何字段。

模板只提供建议值，所有字段都可以继续手动修改并以最终输入值保存。

添加自定义 Provider 时需要填写：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| 名称 | 唯一标识，添加账号时会用到 | - |
| 域名 | 平台的完整域名，如 `https://example.com` | - |
| 登录路径 | 登录页面路径 | `/login` |
| 签到路径 | 签到 API 路径 | `/api/user/sign_in` |
| 用户信息路径 | 获取用户余额的 API 路径 | `/api/user/self` |
| API User Key | 请求头中的用户标识字段名 | `new-api-user` |
| WAF 绕过方式 | 无（直接访问）或 WAF Cookies（Playwright） | 无 |
| WAF Cookie 名称 | 需要获取的 WAF Cookie 名，逗号分隔 | - |

保存时会进行基础校验：域名必须为 `http(s)://` 完整地址；WAF Cookie 名称仅允许字母、数字、下划线和短横线。

### 执行日志

记录所有签到操作的详细日志，支持按 **状态**（成功 / 失败）和 **账号** 筛选，带分页功能。

每条日志包含：时间、账号、Provider、状态、余额、已用额度、触发方式（手动 / 定时）、详细信息。
系统会在展示层对失败信息做归类（如认证失败、WAF 拦截、网络错误、未知错误），并保留原始 message 便于排查。

---

## 账号认证方式

添加账号时可以选择两种认证方式：

### Cookie 模式

手动从浏览器提取 Cookie 和 API User ID，适合所有平台。

**获取 Cookie：**

1. 打开浏览器访问目标平台（如 https://anyrouter.top/）并登录
2. 按 F12 打开开发者工具
3. 切换到 **Application**（应用）选项卡
4. 在左侧找到 **Cookies**，点击对应域名
5. 找到 `session` 字段，复制其值

在添加账号时，Cookies 字段支持两种格式：

```
# JSON 格式
{"session": "你的session值"}

# 字符串格式
session=你的session值
```

**获取 API User ID：**

1. 在开发者工具中切换到 **Network**（网络）选项卡
2. 勾选 **Fetch/XHR** 过滤
3. 在页面上进行任意操作（如刷新页面）
4. 找到任意请求，查看请求头中的 `New-Api-User` 字段
5. 复制该值（一串数字）

### 浏览器自动登录

通过无头浏览器自动完成登录和签到，无需手动提取 Cookie。

只需填写：

- **用户名 / 邮箱**：你的登录账号
- **密码**：你的登录密码

系统会使用 Playwright 无头浏览器自动打开登录页面、填写账号密码、完成登录后自动签到并获取余额信息。

> **注意**：浏览器自动登录方式每次签到都会启动浏览器进程，资源消耗略高于 Cookie 模式。如果 Cookie 长期稳定，推荐使用 Cookie 模式。

---

## 签到间隔设置

在仪表盘右上角可以设置签到间隔，提供以下预设选项：

| 选项 | Cron 表达式 | 说明 |
|------|-------------|------|
| 每 1 小时 | `0 * * * *` | 每小时整点执行 |
| 每 2 小时 | `0 */2 * * *` | 每 2 小时执行 |
| 每 4 小时 | `0 */4 * * *` | 每 4 小时执行 |
| 每 6 小时 | `0 */6 * * *` | 默认值 |
| 每 8 小时 | `0 */8 * * *` | 每 8 小时执行 |
| 每 12 小时 | `0 */12 * * *` | 每 12 小时执行 |
| 每天一次 | `0 0 * * *` | 每天 0 点执行 |
| 自定义 | 自行输入 | 标准 5 字段 Cron 表达式 |

选择预设选项会立即生效；选择「自定义」后需要输入 Cron 表达式并点击「保存」。

设置会持久化到数据库，容器重启后保留。

> AnyRouter 的签到间隔约为 24 小时（非零点重置），建议设置为每 6 ~ 8 小时签到一次以确保不遗漏。

---

## 通知配置

签到失败时会自动发送通知。在 `docker-compose.yml` 中取消对应通知方式的注释并填入配置即可。

### Telegram Bot

```yaml
- TELEGRAM_BOT_TOKEN=你的Bot Token
- TELEGRAM_CHAT_ID=你的Chat ID
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
- BARK_KEY=你的Bark Key
# 可选，默认 https://api.day.app
- BARK_SERVER=自建Bark服务器地址
```

每种通知方式独立工作，可以同时启用多种。未配置或配置错误的通知方式会自动跳过。

修改通知配置后需要重启容器生效：

```bash
docker compose up -d
```

---

## GitHub Actions 方式

如果不想自建服务，也可以通过 GitHub Actions 运行。

### 1. Fork 本仓库

### 2. 配置 Environment Secret

1. 进入仓库 **Settings** → **Environments** → **New environment**
2. 新建名为 `production` 的环境
3. 添加 Secret：
   - Name: `ANYROUTER_ACCOUNTS`
   - Value: JSON 格式的账号配置

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

字段说明：

| 字段 | 必需 | 说明 |
|------|------|------|
| `cookies` | 是 | 身份验证 Cookie |
| `api_user` | 是 | New-Api-User 请求头的值 |
| `name` | 否 | 账号显示名称，默认为 `Account 1`、`Account 2` |
| `provider` | 否 | 服务商标识，默认 `anyrouter` |

### 3. 启用 Actions

1. 进入仓库 **Actions** 选项卡
2. 找到「AnyRouter 自动签到」workflow 并启用
3. 可以手动点击 **Run workflow** 测试

### 4. 自定义 Provider（可选）

如果需要签到其他平台，添加名为 `PROVIDERS` 的 Secret：

```json
{
  "customrouter": {
    "domain": "https://custom.example.com",
    "sign_in_path": "/api/user/sign_in",
    "user_info_path": "/api/user/self",
    "bypass_method": "waf_cookies",
    "waf_cookie_names": ["acw_tc"]
  }
}
```

### 5. 通知配置

在 `production` 环境的 Secrets 中添加对应的通知环境变量（参见 [通知配置](#通知配置) 章节）。

---

## 本地开发

```bash
# 安装依赖
uv sync --dev

# 安装 Playwright 浏览器
uv run playwright install chromium

# 启动 Web 服务（开发模式）
ADMIN_PASSWORD=admin uv run uvicorn web.app:app --host 0.0.0.0 --port 8080 --reload

# 或直接运行签到脚本（需配置 .env）
uv run checkin.py

# 运行测试
uv run pytest tests/
```

---

## 故障排除

### 签到失败

| 现象 | 可能原因 | 解决方法 |
|------|----------|----------|
| 401 错误 | Cookie 已过期 | 重新获取 Cookie 或改用浏览器自动登录 |
| Error 1040 Too many connections | 平台数据库问题 | 等待一段时间后重试 |
| 浏览器登录超时 | 网络问题或页面结构变化 | 检查容器日志 `docker logs anyrouter-checkin` |
| Provider not found | 账号关联的 Provider 不存在 | 在 Provider 管理中添加对应配置 |

### 容器相关

```bash
# 查看容器状态
docker ps --filter name=anyrouter-checkin

# 查看容器日志
docker logs anyrouter-checkin --tail 50

# 实时查看日志
docker logs -f anyrouter-checkin

# 重启容器
docker compose restart

# 完全重建
docker compose down && docker compose up -d --build
```

### 数据备份

所有数据保存在 `./data/checkin.db`（SQLite 数据库），备份此文件即可。

---

## 免责声明

本项目仅用于学习和研究目的，使用前请确保遵守相关网站的使用条款。
