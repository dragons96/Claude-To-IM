# Claude to IM

> 将 Claude Code CLI 能力桥接到即时通讯(IM)平台的生产级服务

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 项目介绍

Claude to IM 是一个基于**桥接模式(Bridge Pattern)**架构的生产级服务,将 Anthropic Claude Code CLI 的强大能力无缝集成到即时通讯平台(目前支持飞书)。

通过本服务,用户可以在飞书中直接与 Claude 交互,就像在命令行中使用 Claude Code CLI 一样,享受完整的代码分析、文件操作、工具调用等功能。

### 核心价值

- **零学习成本**: 无需学习 Claude Code CLI 命令,直接在熟悉的环境中交互
- **企业级安全**: 支持目录权限控制、资源管理、会话隔离
- **生产级架构**: 采用桥接模式,易于扩展到其他 IM 平台
- **流式响应**: 实时显示 Claude 的思考和响应过程
- **完整会话管理**: 支持多会话、超时管理、持久化存储

## 功能特性

### 核心功能

- **🤖 Claude SDK 集成**
  - 完整的 Claude Code CLI SDK 支持
  - 流式响应处理
  - 工具调用支持(Bash, Read, Edit, Write等)
  - 会话管理(创建、关闭、查询)

- **💬 飞书集成**
  - 机器人消息接收与处理
  - 富文本卡片消息展示
  - 流式输出实时更新
  - 图片/文件资源处理
  - 消息引用和回复

- **🔒 安全与权限**
  - 目录访问白名单控制
  - 文件操作权限验证
  - 会话隔离和多实例支持
  - 资源下载和缓存管理

- **📊 会话管理**
  - 多会话并行支持
  - 会话超时自动清理
  - 工作目录隔离
  - 会话状态持久化

- **🎯 命令系统**
  - `/start` - 创建新会话
  - `/close` - 关闭当前会话
  - `/sessions` - 查看所有会话
  - `/switch` - 切换会话
  - `/help` - 显示帮助信息

### 技术特性

- **异步架构**: 基于 asyncio 的高性能异步处理
- **数据库持久化**: SQLAlchemy + SQLite/PostgreSQL
- **配置管理**: Pydantic Settings 环境变量配置
- **日志系统**: 完整的日志记录和轮转
- **优雅关闭**: 信号处理和资源清理
- **Docker 就绪**: 支持容器化部署

## 架构设计

本项目采用**桥接模式(Bridge Pattern)**,将抽象(IM 平台)与实现(Claude SDK)解耦,使其可以独立变化。

```
┌─────────────────────────────────────────────────────────────┐
│                         应用层                                │
│                      (CLI Entry)                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                       业务服务层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Session      │  │ Permission   │  │ Resource     │       │
│  │ Manager      │  │ Manager      │  │ Manager      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      桥接适配器层                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              IMAdapter (抽象)                          │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │         FeishuBridge (具体实现)                  │ │   │
│  │  │  ┌───────────┐  ┌───────────┐  ┌───────────┐   │ │   │
│  │  │  │ Message   │  │ Command   │  │ Card      │   │ │   │
│  │  │  │ Handler   │  │ Handler   │  │ Builder   │   │ │   │
│  │  │  └───────────┘  └───────────┘  └───────────┘   │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│  ┌────────────────────────▼──────────────────────────────┐  │
│  │           ClaudeAdapter (抽象)                         │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │       ClaudeSDKAdapter (具体实现)                │ │  │
│  │  │  ┌───────────────────────────────────────────┐  │ │  │
│  │  │  │      StreamProcessor (流式处理)            │  │ │  │
│  │  │  └───────────────────────────────────────────┘  │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      数据存储层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Database     │  │ File System  │  │ Cache        │       │
│  │ (SQLAlchemy) │  │ (Sessions)   │  │ (Resources)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

1. **IMAdapter (抽象接口)**
   - 定义了 IM 平台的统一接口
   - `start()`, `stop()`, `send_message()`, `update_message()`

2. **ClaudeAdapter (抽象接口)**
   - 定义了 Claude SDK 的统一接口
   - `create_session()`, `send_message()`, `close_session()`

3. **FeishuBridge (飞书桥接)**
   - 实现 IMAdapter 接口
   - 处理飞书平台特定的消息格式和 API

4. **ClaudeSDKAdapter (Claude SDK 桥接)**
   - 实现 ClaudeAdapter 接口
   - 封装 Claude Agent SDK 的调用

5. **业务服务层**
   - SessionManager: 会话生命周期管理
   - PermissionManager: 权限控制
   - ResourceManager: 资源下载和缓存

### 扩展性

通过桥接模式,可以轻松扩展支持其他 IM 平台:

```python
# 只需实现 IMAdapter 接口
class WeChatBridge(IMAdapter):
    async def start(self): ...
    async def send_message(self, ...): ...
    # ... 其他方法
```

## 安装说明

### 环境要求

- Python 3.11 或更高版本
- SQLite 3 或 PostgreSQL
- 飞书企业账号(用于创建机器人)

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/your-username/claude-to-im.git
cd claude-to-im
```

2. **创建虚拟环境**

```bash
# 使用 uv (推荐)
uv venv -p 3.11

# 或使用 venv
python3 -m venv .venv
```

3. **激活虚拟环境**

```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

4. **安装依赖**

```bash
# 使用 uv (推荐)
uv pip install -e .

# 或使用 pip
pip install -e .
```

5. **验证安装**

```bash
python -m src.cli --help
```

## 配置说明

### 环境变量配置

复制 `.env.example` 到 `.env` 并配置:

```bash
cp .env.example .env
```

### 配置项说明

```bash
# 应用配置
APP_NAME=claude-to-im          # 应用名称
DEBUG=false                     # 调试模式

# 数据库配置
DATABASE_URL=sqlite:///./sessions/database.db  # 数据库连接URL

# 会话配置
DEFAULT_SESSION_ROOT=./sessions          # 会话根目录
SESSION_TIMEOUT_HOURS=24                 # 会话超时时间(小时)
MAX_SESSIONS_PER_IM=10                   # 每个 IM 最多会话数

# 权限配置(逗号分隔)
ALLOWED_DIRECTORIES=D:/Codes,C:/Projects  # 允许访问的目录

# Claude SDK 配置
ANTHROPIC_AUTH_TOKEN=your_token_here      # Anthropic API Token
ANTHROPIC_BASE_URL=https://api.anthropic.com  # API Base URL
ANTHROPIC_MODEL=claude-sonnet-4-6         # 使用的模型
MAX_TURNS=10                             # 最大对话轮次

# 飞书配置
FEISHU_APP_ID=your_app_id                # 飞书应用 ID
FEISHU_APP_SECRET=your_app_secret        # 飞书应用密钥
FEISHU_ENCRYPT_KEY=                      # 加密密钥(可选)
FEISHU_VERIFICATION_TOKEN=               # 验证令牌(可选)
# FEISHU_BOT_USER_ID 会自动获取，无需手动配置
FEISHU_SEND_TOOL_MESSAGES=true           # 是否发送工具调用消息

# 资源配置
RESOURCE_CACHE_DAYS=7                    # 资源缓存天数
MAX_FILE_SIZE_MB=100                     # 最大文件大小(MB)

# 日志配置
LOG_LEVEL=INFO                           # 日志级别
LOG_FILE=logs/app.log                    # 日志文件路径
LOG_MAX_BYTES=10485760                   # 日志文件最大大小
LOG_BACKUP_COUNT=5                       # 日志备份数量
```

### 获取飞书应用凭证

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 **App ID** 和 **App Secret**
4. 配置事件订阅(机器人接收消息)
5. 发布应用到企业

> **💡 提示**: 只需配置 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 即可！
> - 首次在群聊中@机器人时，会自动提取并保存 bot_user_id
> - 下次启动时自动加载，无需手动配置

## 使用指南

### 启动服务

#### Windows

```bash
# 使用启动脚本
bin\start.bat

# 或直接运行
python -m src.cli
```

#### Linux/Mac

```bash
# 使用启动脚本
chmod +x bin/start.sh
./bin/start.sh

# 或直接运行
python -m src.cli
```

#### 带参数启动

```bash
# 启用调试模式
python -m src.cli --debug

# 使用自定义配置文件
python -m src.cli --config custom.env
```

### 命令说明

在飞书中与机器人对话时,可以使用以下命令:

- **`/start`** - 创建新的 Claude 会话
  ```
  /start
  ```
  每个会话有独立的工作目录和上下文

- **`/close`** - 关闭当前会话
  ```
  /close
  ```
  会释放资源并清理临时文件

- **`/sessions`** - 查看所有会话
  ```
  /sessions
  ```
  显示当前用户的所有活跃会话

- **`/switch <session_id>`** - 切换到指定会话
  ```
  /switch abc123
  ```
  切换上下文到指定会话

- **`/help`** - 显示帮助信息
  ```
  /help
  ```

### 飞书集成

#### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 点击"创建企业自建应用"
3. 填写应用名称和描述
4. 获取 App ID 和 App Secret

#### 2. 配置权限

在应用管理中,添加以下权限:

- `im:message` - 接收消息
- `im:message:send_as_bot` - 发送消息
- `im:chat` - 访问聊天信息

#### 3. 配置事件订阅

1. 在"事件订阅"中配置请求 URL
2. URL 格式: `https://your-domain.com/feishu/events`
3. 订阅事件:
   - **`im.message.receive_v1`** - 接收消息事件（必需）
   - 此事件包含所有消息类型：
     - 私聊消息（p2p）
     - 群聊消息（group）
     - 群聊中@机器人的消息

**注意**：本项目使用 WebSocket 连接接收事件，不需要配置 HTTP 回调 URL。只需在飞书开放平台订阅上述事件即可。

#### 4. 发布应用

1. 完成配置后,点击"发布"
2. 选择发布范围(全员/指定部门)
3. 发布后即可在飞书中使用

#### 5. 配置服务器

确保服务器可以被飞书访问:

- 本地开发: 使用 ngrok/frp 等内网穿透工具
- 生产环境: 配置域名和 SSL 证书

### 使用示例

#### 示例 1: 代码分析

在飞书中发送:

```
请帮我分析 src/cli/main.py 的架构设计
```

Claude 会读取文件并提供详细的架构分析。

#### 示例 2: 文件操作

```
在 docs 目录下创建一个 API.md 文件,内容是 "# API 文档"
```

Claude 会使用 Write 工具创建文件。

#### 示例 3: 工具调用

```
查看当前目录的文件列表
```

Claude 会使用 Bash 工具执行 `ls` 命令。

## 开发指南

### 项目结构

```
claude-to-im/
├── src/                    # 源代码
│   ├── cli/               # CLI 入口
│   ├── bridges/           # IM 桥接适配器
│   │   └── feishu/       # 飞书实现
│   ├── claude/            # Claude SDK 适配器
│   ├── core/              # 核心抽象接口
│   └── services/          # 业务服务
├── config/                # 配置管理
├── tests/                 # 测试代码
├── bin/                   # 启动脚本
├── docs/                  # 文档
├── sessions/              # 会话数据
└── logs/                  # 日志文件
```

### 开发环境设置

1. **安装开发依赖**

```bash
uv pip install -e ".[dev]"
```

2. **运行测试**

```bash
pytest
```

3. **代码格式化**

```bash
# 使用 black 格式化
black src/ tests/

# 使用 ruff 检查
ruff check src/ tests/
```

### 添加新的 IM 平台

1. 在 `src/bridges/` 下创建新目录
2. 实现 `IMAdapter` 接口
3. 在 `src/cli/main.py` 中注册新的桥接器

示例:

```python
# src/bridges/wechat/adapter.py
from src.core.im_adapter import IMAdapter

class WeChatBridge(IMAdapter):
    async def start(self):
        # 实现启动逻辑
        pass

    async def send_message(self, session_id, content, **kwargs):
        # 实现发送消息逻辑
        pass
```

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- 遵循 PEP 8 代码规范
- 使用类型注解
- 编写单元测试
- 更新文档

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [Anthropic Claude](https://www.anthropic.com/) - AI 能力支持
- [飞书开放平台](https://open.feishu.cn/) - IM 平台支持
- [Claude Agent SDK](https://github.com/anthropics/anthropic-sdk-python) - SDK 支持

## 联系方式

- 问题反馈: [GitHub Issues](https://github.com/dragons96/Claude-To-Im/issues)
- 邮箱: 521274311@qq.com

---

**注意**: 本服务需要有效的 Anthropic API Key 和飞书企业账号才能使用。
