# Claude to IM 桥接服务架构设计文档

**创建日期**: 2026-03-11
**版本**: v1.0
**作者**: Claude Code

---

## 1. 项目概述

### 1.1 项目目标
构建一个通过飞书机器人直接调度 Claude Code CLI 的工具，实现：
- 多会话管理（飞书会话 ↔ Claude Code 会话）
- 私聊自动响应，群聊需 @ 机器人
- 支持引用/回复消息
- 文件、图片等资源处理
- 可扩展的桥接架构（支持未来接入钉钉、Slack 等平台）

### 1.2 技术栈
- **语言**: Python 3.11+
- **包管理**: uv
- **数据库**: SQLite + SQLAlchemy
- **飞书 SDK**: lark-oapi
- **Claude SDK**: claude-agent-sdk
- **异步框架**: asyncio
- **配置管理**: pydantic-settings

---

## 2. 架构设计

### 2.1 整体架构

采用**桥接模式**的分层架构：

```
┌─────────────────────────────────────────────────────────┐
│                   桥接实现层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  飞书桥接     │  │  钉钉桥接     │  │ Slack桥接    │ │
│  └───────┬──────┘  └──────┬───────┘  └──────┬───────┘ │
└──────────┼────────────────┼──────────────────┼─────────┘
           │                │                  │
           └────────────────┴──────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│                   核心抽象层                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │         IM 平台抽象 (IMAdapter)                   │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │    Claude Code CLI 抽象 (ClaudeAdapter)           │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │              共享服务层                            │  │
│  │  - SessionManager (会话管理)                      │  │
│  │  - PermissionManager (权限管理)                   │  │
│  │  - ResourceManager (资源管理)                     │  │
│  │  - StorageService (存储服务)                      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│                   数据持久化层                           │
│              SQLAlchemy + SQLite                        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 IM 平台抽象 (IMAdapter)

```python
class IMAdapter(ABC):
    """IM 平台适配器基类"""

    @abstractmethod
    async def start(self) -> None: pass

    @abstractmethod
    async def stop(self) -> None: pass

    @abstractmethod
    async def send_message(self, session_id: str, content: str, **kwargs) -> str: pass

    @abstractmethod
    async def update_message(self, message_id: str, new_content: str) -> bool: pass

    @abstractmethod
    async def download_resource(self, url: str) -> bytes: pass

    @abstractmethod
    def should_respond(self, message: IMMessage) -> bool: pass

    @abstractmethod
    def format_quoted_message(self, message: IMMessage) -> str: pass
```

#### 2.2.2 Claude CLI 抽象 (ClaudeAdapter)

```python
class ClaudeAdapter(ABC):
    """Claude Code CLI 适配器基类"""

    @abstractmethod
    async def create_session(self, work_directory: str, session_id: Optional[str] = None) -> ClaudeSession: pass

    @abstractmethod
    async def close_session(self, session_id: str) -> None: pass

    @abstractmethod
    async def send_message(self, session_id: str, message: str, **kwargs) -> AsyncIterator[StreamEvent]: pass

    @abstractmethod
    async def get_session_info(self, session_id: str) -> ClaudeSession: pass

    @abstractmethod
    async def list_sessions(self, **kwargs) -> List[ClaudeSession]: pass
```

---

## 3. 功能设计

### 3.1 会话管理

#### 3.1.1 会话创建逻辑

1. **自动创建**：用户直接发送消息时，在 `./sessions/<feishu_session_id>/` 创建会话
2. **/new 命令**：
   - `/new` → 在默认目录创建新会话
   - `/new <path>` → 在指定路径创建（需权限检查）
3. **会话切换**：`/switch <session_id>` 切换活跃会话
4. **会话列表**：`/sessions` 显示所有会话（ID + 摘要 + 活跃标记）

#### 3.1.2 会话摘要

- 取会话第一条用户消息的前 10 个字符
- 标记活跃会话（🟢 活跃 / ⚪ 非活跃）

#### 3.1.3 会话生命周期

- 默认永久保持
- 支持用户手动创建新会话
- 超时清理机制（24 小时无活动）

### 3.2 消息处理

#### 3.2.1 消息过滤规则

- **私聊**：所有消息都响应
- **群聊**：只有 @ 机器人的消息才响应

#### 3.2.2 引用消息处理

格式：
```markdown
> [被引用的消息内容]

[用户新发送的消息]
```

#### 3.2.3 消息发送策略

采用**消息更新流式**方案：
1. 创建初始消息："正在思考..."
2. 实时更新消息内容，实现打字机效果
3. 工具调用时发送单独的卡片消息

### 3.3 资源管理

#### 3.3.1 资源下载

- 图片、文件等资源下载到 `<work_dir>/.feishu_data/`
- 使用缓存避免重复下载
- 定期清理过期缓存（7 天）

#### 3.3.2 支持的消息类型

- 文本消息
- 图片消息
- 文件消息
- 富文本消息
- 卡片消息

### 3.4 权限管理

#### 3.4.1 目录权限配置

- 根目录：`./sessions/`（默认会话目录）
- 允许目录白名单：配置多个允许访问的目录
- 权限检查：只允许在白名单目录及其子目录创建会话

#### 3.4.2 权限检查逻辑

```python
def is_allowed(path: str) -> bool:
    """检查路径是否在允许的目录白名单中"""
    for allowed_dir in ALLOWED_DIRECTORIES:
        if path.startswith(allowed_dir) or path == allowed_dir:
            return True
    return False
```

---

## 4. 数据库设计

### 4.1 数据模型

```python
class IMSession(Base):
    """IM 平台会话映射表"""
    __tablename__ = 'im_sessions'
    id = Column(String(64), primary_key=True)
    platform = Column(String(32), nullable=False)
    platform_session_id = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

class ClaudeSession(Base):
    """Claude Code 会话表"""
    __tablename__ = 'claude_sessions'
    id = Column(String(64), primary_key=True)
    im_session_id = Column(String(64), ForeignKey('im_sessions.id'))
    session_id = Column(String(128), nullable=False, unique=True)
    work_directory = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    summary = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)

class MessageHistory(Base):
    """消息历史表"""
    __tablename__ = 'message_history'
    id = Column(String(64), primary_key=True)
    claude_session_id = Column(String(64), ForeignKey('claude_sessions.id'))
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PermissionConfig(Base):
    """权限配置表"""
    __tablename__ = 'permission_config'
    id = Column(String(64), primary_key=True)
    path = Column(String(512), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ResourceCache(Base):
    """资源缓存表"""
    __tablename__ = 'resource_cache'
    id = Column(String(64), primary_key=True)
    resource_key = Column(String(256), nullable=False, unique=True)
    local_path = Column(String(512), nullable=False)
    mime_type = Column(String(128))
    size = Column(BigInteger)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
```

---

## 5. 项目结构

```
claude-to-im/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
│
├── config/                          # 配置文件
│   ├── __init__.py
│   ├── settings.py                  # 全局配置
│   └── permissions.yaml             # 权限配置（可选）
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                        # 核心抽象层
│   │   ├── __init__.py
│   │   ├── im_adapter.py            # IM 平台抽象基类
│   │   ├── claude_adapter.py        # Claude CLI 抽象基类
│   │   ├── message.py               # 消息数据类
│   │   └── exceptions.py            # 自定义异常
│   │
│   ├── services/                    # 共享服务层
│   │   ├── __init__.py
│   │   ├── session_manager.py       # 会话管理服务
│   │   ├── permission_manager.py    # 权限管理服务
│   │   ├── resource_manager.py      # 资源下载/管理服务
│   │   └── storage_service.py       # 数据库存储服务
│   │
│   ├── bridges/                     # 桥接实现层
│   │   ├── __init__.py
│   │   ├── feishu/                  # 飞书桥接
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py           # FeishuBridge 实现
│   │   │   ├── message_handler.py   # 消息处理器
│   │   │   ├── command_handler.py   # 命令处理器
│   │   │   ├── card_builder.py      # 卡片构建器
│   │   │   └── utils.py             # 工具函数
│   │   │
│   │   └── dingtalk/                # 钉钉桥接（预留）
│   │       └── __init__.py
│   │
│   ├── claude/                      # Claude CLI 实现
│   │   ├── __init__.py
│   │   ├── sdk_adapter.py           # Claude SDK 适配器
│   │   └── stream_processor.py      # 流式响应处理器
│   │
│   └── cli/                         # 命令行入口
│       ├── __init__.py
│       ├── main.py                  # 主入口
│       └── commands.py              # CLI 命令
│
├── docs/
│   ├── plans/                       # 设计文档
│   │   └── 2026-03-11-architecture-design.md
│   ├── guides/                      # 使用指南
│   └── api/                         # API 文档
│
├── bin/                             # 脚本文件
│   ├── start.sh                     # 启动脚本
│   └── stop.sh                      # 停止脚本
│
├── sessions/                        # 默认会话目录（运行时生成）
│   ├── database.db                  # SQLite 数据库
│   └── <feishu_session_id>/         # 各会话工作目录
│       └── .feishu_data/            # 资源文件缓存
│
└── tests/                           # 测试
    ├── __init__.py
    ├── test_core/
    ├── test_services/
    ├── test_bridges/
    └── test_claude/
```

---

## 6. 配置管理

### 6.1 环境变量配置

```python
class Settings(BaseSettings):
    """全局配置"""

    # 应用配置
    APP_NAME: str = "claude-to-im"
    DEBUG: bool = False

    # 数据库配置
    DATABASE_URL: str = "sqlite:///sessions/database.db"

    # 会话配置
    DEFAULT_SESSION_ROOT: Path = Path("./sessions")
    SESSION_TIMEOUT_HOURS: int = 24
    MAX_SESSIONS_PER_IM: int = 10

    # 权限配置
    ALLOWED_DIRECTORIES: List[str] = []

    # Claude SDK 配置
    ANTHROPIC_AUTH_TOKEN: str
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "claude-opus-4-6"
    MAX_TURNS: int = 10

    # 飞书配置
    FEISHU_APP_ID: str
    FEISHU_APP_SECRET: str

    # 资源配置
    RESOURCE_CACHE_DAYS: int = 7
    MAX_FILE_SIZE_MB: int = 100
```

### 6.2 权限配置示例

```yaml
# config/permissions.yaml
allowed_directories:
  - D:/Codes
  - C:/Projects
  - /home/user/workspace

denied_patterns:
  - "/etc"
  - "/sys"
  - "C:\\Windows"
```

---

## 7. 错误处理

### 7.1 异常类型

```python
class ClaudeToIMException(Exception):
    """基础异常类"""

class SessionNotFoundError(ClaudeToIMException):
    """会话不存在"""

class PermissionDeniedError(ClaudeToIMException):
    """权限不足"""

class ClaudeSDKError(ClaudeToIMException):
    """Claude SDK 调用失败"""

class IMPlatformError(ClaudeToIMException):
    """IM 平台错误"""

class ResourceDownloadError(ClaudeToIMException):
    """资源下载失败"""

class CommandExecutionError(ClaudeToIMException):
    """命令执行错误"""
```

### 7.2 错误处理策略

- **服务层**：统一捕获错误，返回友好的错误消息
- **桥接层**：将平台错误转换为通用异常
- **CLI 层**：记录详细日志，向用户返回简化错误信息

---

## 8. 测试策略

### 8.1 测试类型

1. **单元测试**：测试各个组件的功能
2. **集成测试**：测试组件间的交互
3. **端到端测试**：测试完整的消息流程

### 8.2 测试覆盖

- 核心抽象层：100%
- 服务层：90%+
- 桥接层：80%+（依赖 Mock）

### 8.3 测试工具

- **pytest**: 测试框架
- **pytest-asyncio**: 异步测试支持
- **pytest-cov**: 覆盖率报告

---

## 9. 部署方案

### 9.1 部署方式

**系统服务**（systemd）：

```ini
[Unit]
Description=Claude to IM Bridge Service
After=network.target

[Service]
Type=simple
User=claude-bot
WorkingDirectory=/opt/claude-to-im
ExecStart=/opt/claude-to-im/.venv/bin/python -m src.cli.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9.2 启动脚本

```bash
#!/bin/bash
# bin/start.sh

set -e

# 激活虚拟环境
source .venv/bin/activate

# 检查环境变量
if [ ! -f .env ]; then
    echo "错误: .env 文件不存在"
    exit 1
fi

# 创建必要的目录
mkdir -p sessions logs

# 启动服务
python -m src.cli.main
```

### 9.3 日志管理

- 日志位置：`logs/` 目录
- 日志级别：DEBUG/INFO/WARNING/ERROR
- 日志轮转：每天轮转，保留 30 天

---

## 10. 未来扩展

### 10.1 新平台接入

通过实现 `IMAdapter` 接口，可以轻松接入新平台：
- 钉钉
- 企业微信
- Slack
- Discord

### 10.2 功能扩展

- 支持多模态输入（语音、视频）
- 支持文件协作编辑
- 支持群组管理功能
- 支持插件系统

---

## 11. 总结

本设计采用**桥接模式**实现了核心抽象层，将 IM 平台特性和 Claude CLI 特性解耦，使系统具有良好的可扩展性。

**核心优势**：
- ✅ 模块化设计，职责清晰
- ✅ 可扩展性强，易于接入新平台
- ✅ 测试友好，依赖注入
- ✅ 配置灵活，支持多种部署方式

**下一步**：创建详细的实施计划。
