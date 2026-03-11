# Claude to IM 桥接服务实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个可扩展的飞书机器人桥接服务，通过抽象层支持多平台接入，实现会话管理、消息处理和资源管理。

**Architecture:** 采用桥接模式分层架构：核心抽象层定义接口（IMAdapter、ClaudeAdapter），飞书桥接层实现具体逻辑，共享服务层处理会话、权限和资源管理。使用 SQLAlchemy + SQLite 持久化数据。

**Tech Stack:** Python 3.11+, asyncio, SQLAlchemy, lark-oapi, claude-agent-sdk, pydantic-settings, pytest

---

## 任务概述

本实施计划分为以下阶段：

1. **项目基础设施** - 配置、依赖、目录结构
2. **核心抽象层** - IMAdapter、ClaudeAdapter、消息模型
3. **数据持久化层** - SQLAlchemy 模型、数据库服务
4. **共享服务层** - 会话管理、权限管理、资源管理
5. **Claude SDK 实现** - ClaudeAdapter 实现、流式处理
6. **飞书桥接实现** - FeishuBridge、消息处理、命令处理
7. **CLI 入口** - 启动脚本、系统服务配置
8. **测试和文档** - 单元测试、集成测试、使用文档

---

## Task 1: 项目基础设施搭建

### Task 1.1: 配置项目依赖

**Files:**
- Modify: `pyproject.toml`

**Step 1: 更新 pyproject.toml 依赖**

```toml
[project]
name = "claude-to-im"
version = "0.1.0"
description = "Claude Code CLI to IM bridge service"
requires-python = ">=3.11"
dependencies = [
    "lark-oapi>=1.2.0",
    "claude-agent-sdk>=0.1.0",
    "sqlalchemy>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "aiofiles>=23.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I"]
```

**Step 2: 安装依赖**

Run: `uv sync`
Expected: 依赖安装成功，无错误

**Step 3: 创建 .env.example**

```bash
# .env.example

# 应用配置
APP_NAME=claude-to-im
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///sessions/database.db

# 会话配置
DEFAULT_SESSION_ROOT=./sessions
SESSION_TIMEOUT_HOURS=24
MAX_SESSIONS_PER_IM=10

# 权限配置（逗号分隔）
ALLOWED_DIRECTORIES=D:/Codes,C:/Projects

# Claude SDK 配置
ANTHROPIC_AUTH_TOKEN=your_token_here
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-opus-4-6
MAX_TURNS=10

# 飞书配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# 资源配置
RESOURCE_CACHE_DAYS=7
MAX_FILE_SIZE_MB=100
```

**Step 4: 创建项目目录结构**

Run:
```bash
mkdir -p src/core src/services src/bridges/feishu src/claude src/cli config docs/plans docs/guides docs/api bin tests/test_core tests/test_services tests/test_bridges tests/test_claude
touch src/__init__.py src/core/__init__.py src/services/__init__.py src/bridges/__init__.py src/bridges/feishu/__init__.py src/claude/__init__.py src/cli/__init__.py tests/__init__.py
```

**Step 5: 提交**

```bash
git add pyproject.toml .env.example
git commit -m "feat: 配置项目依赖和目录结构"
```

---

## Task 2: 核心抽象层 - 数据模型

### Task 2.1: 创建消息数据模型

**Files:**
- Create: `src/core/message.py`
- Test: `tests/test_core/test_message.py`

**Step 1: 编写测试**

```python
# tests/test_core/test_message.py
import pytest
from src.core.message import IMMessage, MessageType, StreamEvent, StreamEventType

def test_im_message_creation():
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=False
    )
    assert message.content == "Hello"
    assert message.message_type == MessageType.TEXT
    assert message.is_private_chat is True
    assert message.mentioned_bot is False

def test_im_message_with_quote():
    quoted = IMMessage(
        content="Previous message",
        message_type=MessageType.TEXT,
        message_id="msg_122",
        session_id="session_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True
    )
    message = IMMessage(
        content="Reply",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        quoted_message=quoted
    )
    assert message.quoted_message is not None
    assert message.quoted_message.content == "Previous message"

def test_stream_event():
    event = StreamEvent(
        event_type=StreamEventType.TEXT_DELTA,
        content="Hello"
    )
    assert event.event_type == StreamEventType.TEXT_DELTA
    assert event.content == "Hello"
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_core/test_message.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.core.message'"

**Step 3: 实现数据模型**

```python
# src/core/message.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    CARD = "card"

class StreamEventType(Enum):
    """流式事件类型枚举"""
    TEXT_DELTA = "text_delta"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    END = "end"

@dataclass
class StreamEvent:
    """流式事件对象"""
    event_type: StreamEventType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IMMessage:
    """平台无关的消息对象"""
    content: str
    message_type: MessageType
    message_id: str
    session_id: str
    user_id: str
    user_name: str
    is_private_chat: bool
    mentioned_bot: bool = False
    quoted_message: Optional['IMMessage'] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_core/test_message.py -v`
Expected: PASS (3 tests)

**Step 5: 提交**

```bash
git add src/core/message.py tests/test_core/test_message.py
git commit -m "feat: 添加核心消息数据模型"
```

---

### Task 2.2: 创建异常类

**Files:**
- Create: `src/core/exceptions.py`
- Test: `tests/test_core/test_exceptions.py`

**Step 1: 编写测试**

```python
# tests/test_core/test_exceptions.py
import pytest
from src.core.exceptions import (
    ClaudeToIMException,
    SessionNotFoundError,
    PermissionDeniedError,
    ClaudeSDKError,
    IMPlatformError,
    ResourceDownloadError,
    CommandExecutionError
)

def test_exception_hierarchy():
    assert issubclass(SessionNotFoundError, ClaudeToIMException)
    assert issubclass(PermissionDeniedError, ClaudeToIMException)
    assert issubclass(ClaudeSDKError, ClaudeToIMException)

def test_exception_messages():
    error = SessionNotFoundError("Session not found")
    assert str(error) == "Session not found"
    assert isinstance(error, ClaudeToIMException)
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_core/test_exceptions.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.core.exceptions'"

**Step 3: 实现异常类**

```python
# src/core/exceptions.py
class ClaudeToIMException(Exception):
    """基础异常类"""
    pass

class SessionNotFoundError(ClaudeToIMException):
    """会话不存在异常"""
    pass

class PermissionDeniedError(ClaudeToIMException):
    """权限不足异常"""
    pass

class ClaudeSDKError(ClaudeToIMException):
    """Claude SDK 调用失败异常"""
    pass

class IMPlatformError(ClaudeToIMException):
    """IM 平台错误异常"""
    pass

class ResourceDownloadError(ClaudeToIMException):
    """资源下载失败异常"""
    pass

class CommandExecutionError(ClaudeToIMException):
    """命令执行错误异常"""
    pass
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_core/test_exceptions.py -v`
Expected: PASS (2 tests)

**Step 5: 提交**

```bash
git add src/core/exceptions.py tests/test_core/test_exceptions.py
git commit -m "feat: 添加异常类"
```

---

### Task 2.3: 创建 IM 适配器抽象基类

**Files:**
- Create: `src/core/im_adapter.py`
- Test: `tests/test_core/test_im_adapter.py`

**Step 1: 编写测试**

```python
# tests/test_core/test_im_adapter.py
import pytest
from abc import ABC
from src.core.im_adapter import IMAdapter
from src.core.message import IMMessage, MessageType

class MockIMAdapter(IMAdapter):
    """用于测试的 Mock 实现"""
    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    async def send_message(self, session_id, content, **kwargs):
        return f"msg_{session_id}"

    async def update_message(self, message_id, new_content):
        return True

    async def download_resource(self, url):
        return b"content"

    def should_respond(self, message):
        if message.is_private_chat:
            return True
        return message.mentioned_bot

    def format_quoted_message(self, message):
        if message.quoted_message:
            return f"> {message.quoted_message.content}\n\n{message.content}"
        return message.content

@pytest.mark.asyncio
async def test_adapter_lifecycle():
    adapter = MockIMAdapter()
    await adapter.start()
    assert adapter.started is True
    await adapter.stop()
    assert adapter.started is False

@pytest.mark.asyncio
async def test_send_message():
    adapter = MockIMAdapter()
    msg_id = await adapter.send_message("session_123", "Hello")
    assert msg_id == "msg_session_123"

@pytest.mark.asyncio
async def test_update_message():
    adapter = MockIMAdapter()
    result = await adapter.update_message("msg_123", "New content")
    assert result is True

@pytest.mark.asyncio
async def test_download_resource():
    adapter = MockIMAdapter()
    content = await adapter.download_resource("http://example.com/file.png")
    assert content == b"content"

def test_should_respond_private_chat():
    adapter = MockIMAdapter()
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test",
        is_private_chat=True
    )
    assert adapter.should_respond(message) is True

def test_should_respond_group_chat_with_mention():
    adapter = MockIMAdapter()
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test",
        is_private_chat=False,
        mentioned_bot=True
    )
    assert adapter.should_respond(message) is True

def test_should_respond_group_chat_without_mention():
    adapter = MockIMAdapter()
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test",
        is_private_chat=False,
        mentioned_bot=False
    )
    assert adapter.should_respond(message) is False

def test_format_quoted_message():
    adapter = MockIMAdapter()
    quoted = IMMessage(
        content="Original",
        message_type=MessageType.TEXT,
        message_id="msg_122",
        session_id="session_123",
        user_id="user_123",
        user_name="Test",
        is_private_chat=True
    )
    message = IMMessage(
        content="Reply",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test",
        is_private_chat=True,
        quoted_message=quoted
    )
    formatted = adapter.format_quoted_message(message)
    assert formatted == "> Original\n\nReply"

def test_format_message_without_quote():
    adapter = MockIMAdapter()
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test",
        is_private_chat=True
    )
    formatted = adapter.format_quoted_message(message)
    assert formatted == "Hello"
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_core/test_im_adapter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.core.im_adapter'"

**Step 3: 实现抽象基类**

```python
# src/core/im_adapter.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.core.message import IMMessage, MessageType

class IMAdapter(ABC):
    """IM 平台适配器基类"""

    @abstractmethod
    async def start(self) -> None:
        """启动适配器，开始监听消息"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止适配器"""
        pass

    @abstractmethod
    async def send_message(
        self,
        session_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> str:
        """发送消息，返回消息 ID"""
        pass

    @abstractmethod
    async def update_message(
        self,
        message_id: str,
        new_content: str
    ) -> bool:
        """更新已发送的消息（用于流式输出）"""
        pass

    @abstractmethod
    async def download_resource(self, url: str) -> bytes:
        """下载资源文件"""
        pass

    @abstractmethod
    def should_respond(self, message: IMMessage) -> bool:
        """判断是否应该响应此消息"""
        pass

    @abstractmethod
    def format_quoted_message(self, message: IMMessage) -> str:
        """格式化引用消息"""
        pass
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_core/test_im_adapter.py -v`
Expected: PASS (9 tests)

**Step 5: 提交**

```bash
git add src/core/im_adapter.py tests/test_core/test_im_adapter.py
git commit -m "feat: 添加 IM 适配器抽象基类"
```

---

### Task 2.4: 创建 Claude 适配器抽象基类

**Files:**
- Create: `src/core/claude_adapter.py`
- Test: `tests/test_core/test_claude_adapter.py`

**Step 1: 编写测试**

```python
# tests/test_core/test_claude_adapter.py
import pytest
from src.core.claude_adapter import ClaudeAdapter, ClaudeSession
from src.core.message import StreamEvent, StreamEventType

class MockClaudeAdapter(ClaudeAdapter):
    """用于测试的 Mock 实现"""
    def __init__(self):
        self.sessions = {}

    async def create_session(self, work_directory, session_id=None):
        import uuid
        sid = session_id or str(uuid.uuid4())
        session = ClaudeSession(
            session_id=sid,
            work_directory=work_directory
        )
        self.sessions[sid] = session
        return session

    async def close_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def send_message(self, session_id, message, **kwargs):
        yield StreamEvent(StreamEventType.TEXT_DELTA, "Hello ")
        yield StreamEvent(StreamEventType.TEXT_DELTA, "World!")
        yield StreamEvent(StreamEventType.END, "")

    async def get_session_info(self, session_id):
        return self.sessions.get(session_id)

    async def list_sessions(self, **kwargs):
        return list(self.sessions.values())

@pytest.mark.asyncio
async def test_create_session():
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/test")
    assert session.session_id is not None
    assert session.work_directory == "/tmp/test"
    assert session.is_active is True

@pytest.mark.asyncio
async def test_create_session_with_custom_id():
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/test", "custom_id")
    assert session.session_id == "custom_id"

@pytest.mark.asyncio
async def test_send_message():
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/test")
    events = []
    async for event in adapter.send_message(session.session_id, "Hello"):
        events.append(event)
    assert len(events) == 3
    assert events[0].content == "Hello "
    assert events[1].content == "World!"
    assert events[2].event_type == StreamEventType.END

@pytest.mark.asyncio
async def test_close_session():
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/test")
    await adapter.close_session(session.session_id)
    assert session.session_id not in adapter.sessions

@pytest.mark.asyncio
async def test_get_session_info():
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/test", "test_id")
    info = await adapter.get_session_info("test_id")
    assert info is not None
    assert info.session_id == "test_id"

@pytest.mark.asyncio
async def test_list_sessions():
    adapter = MockClaudeAdapter()
    await adapter.create_session("/tmp/test1", "id1")
    await adapter.create_session("/tmp/test2", "id2")
    sessions = await adapter.list_sessions()
    assert len(sessions) == 2
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_core/test_claude_adapter.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.core.claude_adapter'"

**Step 3: 实现抽象基类和数据类**

```python
# src/core/claude_adapter.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, List, Dict, Any
from dataclasses import dataclass
from src.core.message import StreamEvent

@dataclass
class ClaudeSession:
    """Claude 会话对象"""
    session_id: str
    work_directory: str
    is_active: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ClaudeAdapter(ABC):
    """Claude Code CLI 适配器基类"""

    @abstractmethod
    async def create_session(
        self,
        work_directory: str,
        session_id: Optional[str] = None
    ) -> ClaudeSession:
        """创建新会话"""
        pass

    @abstractmethod
    async def close_session(self, session_id: str) -> None:
        """关闭会话"""
        pass

    @abstractmethod
    async def send_message(
        self,
        session_id: str,
        message: str,
        include_partial: bool = True
    ) -> AsyncIterator[StreamEvent]:
        """发送消息并流式接收响应"""
        pass

    @abstractmethod
    async def get_session_info(self, session_id: str) -> Optional[ClaudeSession]:
        """获取会话信息"""
        pass

    @abstractmethod
    async def list_sessions(self, **kwargs) -> List[ClaudeSession]:
        """列出会话"""
        pass
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_core/test_claude_adapter.py -v`
Expected: PASS (6 tests)

**Step 5: 提交**

```bash
git add src/core/claude_adapter.py tests/test_core/test_claude_adapter.py
git commit -m "feat: 添加 Claude 适配器抽象基类"
```

---

## Task 3: 数据持久化层

### Task 3.1: 创建 SQLAlchemy 模型

**Files:**
- Create: `src/services/models.py`
- Test: `tests/test_services/test_models.py`

**Step 1: 编写测试**

```python
# tests/test_services/test_models.py
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.models import Base, IMSession, ClaudeSession, MessageHistory, PermissionConfig, ResourceCache

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def test_im_session_creation(in_memory_db):
    session = IMSession(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )
    in_memory_db.add(session)
    in_memory_db.commit()

    retrieved = in_memory_db.query(IMSession).filter_by(id="im_123").first()
    assert retrieved is not None
    assert retrieved.platform == "feishu"

def test_claude_session_creation(in_memory_db):
    # 先创建 IM 会话
    im_session = IMSession(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )
    in_memory_db.add(im_session)

    # 创建 Claude 会话
    claude_session = ClaudeSession(
        id="claude_123",
        im_session_id="im_123",
        session_id="claude_sdk_123",
        work_directory="/tmp/test",
        summary="Hello World"
    )
    in_memory_db.add(claude_session)
    in_memory_db.commit()

    retrieved = in_memory_db.query(ClaudeSession).filter_by(id="claude_123").first()
    assert retrieved is not None
    assert retrieved.work_directory == "/tmp/test"

def test_message_history_creation(in_memory_db):
    message = MessageHistory(
        id="msg_123",
        claude_session_id="claude_123",
        role="user",
        content="Hello"
    )
    in_memory_db.add(message)
    in_memory_db.commit()

    retrieved = in_memory_db.query(MessageHistory).filter_by(id="msg_123").first()
    assert retrieved.content == "Hello"

def test_permission_config_creation(in_memory_db):
    config = PermissionConfig(
        id="perm_123",
        path="D:/Codes"
    )
    in_memory_db.add(config)
    in_memory_db.commit()

    retrieved = in_memory_db.query(PermissionConfig).filter_by(id="perm_123").first()
    assert retrieved.path == "D:/Codes"

def test_resource_cache_creation(in_memory_db):
    cache = ResourceCache(
        id="cache_123",
        resource_key="file_key_123",
        local_path="/tmp/file.png",
        mime_type="image/png",
        size=1024
    )
    in_memory_db.add(cache)
    in_memory_db.commit()

    retrieved = in_memory_db.query(ResourceCache).filter_by(id="cache_123").first()
    assert retrieved.local_path == "/tmp/file.png"
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_services/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.services.models'"

**Step 3: 实现数据模型**

```python
# src/services/models.py
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class IMSession(Base):
    """IM 平台会话映射表"""
    __tablename__ = 'im_sessions'

    id = Column(String(64), primary_key=True)
    platform = Column(String(32), nullable=False)  # 'feishu', 'dingtalk', etc.
    platform_session_id = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ClaudeSession(Base):
    """Claude Code 会话表"""
    __tablename__ = 'claude_sessions'

    id = Column(String(64), primary_key=True)
    im_session_id = Column(String(64), ForeignKey('im_sessions.id'))
    session_id = Column(String(128), nullable=False, unique=True)  # Claude SDK session_id
    work_directory = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    summary = Column(String(10))  # 第一条消息前10字符
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    im_session = relationship("IMSession", backref="claude_sessions")

class MessageHistory(Base):
    """消息历史表"""
    __tablename__ = 'message_history'

    id = Column(String(64), primary_key=True)
    claude_session_id = Column(String(64), ForeignKey('claude_sessions.id'))
    role = Column(String(16), nullable=False)  # 'user' or 'assistant'
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
    """资源缓存表（飞书文件下载缓存）"""
    __tablename__ = 'resource_cache'

    id = Column(String(64), primary_key=True)
    resource_key = Column(String(256), nullable=False, unique=True)  # 飞书文件key
    local_path = Column(String(512), nullable=False)
    mime_type = Column(String(128))
    size = Column(BigInteger)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # 过期时间，可定期清理
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_services/test_models.py -v`
Expected: PASS (5 tests)

**Step 5: 提交**

```bash
git add src/services/models.py tests/test_services/test_models.py
git commit -m "feat: 添加 SQLAlchemy 数据模型"
```

---

### Task 3.2: 创建存储服务

**Files:**
- Create: `src/services/storage_service.py`
- Test: `tests/test_services/test_storage_service.py`

**Step 1: 编写测试**

```python
# tests/test_services/test_storage_service.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.storage_service import StorageService
from src.services.models import Base, IMSession, ClaudeSession

@pytest.fixture
def storage_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return StorageService(Session())

@pytest.mark.asyncio
async def test_create_im_session(storage_service):
    im_session = await storage_service.create_im_session(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )
    assert im_session.id == "im_123"
    assert im_session.platform == "feishu"

@pytest.mark.asyncio
async def test_get_im_session_by_platform_id(storage_service):
    # 创建会话
    await storage_service.create_im_session(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )

    # 查询会话
    session = await storage_service.get_im_session_by_platform_id("feishu", "feishu_chat_123")
    assert session is not None
    assert session.id == "im_123"

@pytest.mark.asyncio
async def test_create_claude_session(storage_service):
    # 先创建 IM 会话
    await storage_service.create_im_session(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )

    # 创建 Claude 会话
    claude_session = await storage_service.create_claude_session(
        id="claude_123",
        im_session_id="im_123",
        session_id="claude_sdk_123",
        work_directory="/tmp/test",
        summary="Hello"
    )
    assert claude_session.id == "claude_123"
    assert claude_session.work_directory == "/tmp/test"

@pytest.mark.asyncio
async def test_get_active_claude_sessions(storage_service):
    # 创建 IM 会话
    await storage_service.create_im_session(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )

    # 创建多个 Claude 会话
    await storage_service.create_claude_session(
        id="claude_1",
        im_session_id="im_123",
        session_id="sdk_1",
        work_directory="/tmp/test1",
        summary="Session 1",
        is_active=True
    )
    await storage_service.create_claude_session(
        id="claude_2",
        im_session_id="im_123",
        session_id="sdk_2",
        work_directory="/tmp/test2",
        summary="Session 2",
        is_active=False
    )

    # 查询活跃会话
    sessions = await storage_service.get_active_claude_sessions("im_123")
    assert len(sessions) == 1
    assert sessions[0].id == "claude_1"

@pytest.mark.asyncio
async def test_update_last_active(storage_service):
    im_session = await storage_service.create_im_session(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )

    # 更新活跃时间
    await storage_service.update_im_session_last_active("im_123")

    # 验证更新
    session = await storage_service.get_im_session("im_123")
    assert session.last_active is not None
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_services/test_storage_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.services.storage_service'"

**Step 3: 实现存储服务**

```python
# src/services/storage_service.py
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
from src.services.models import IMSession, ClaudeSession, MessageHistory, PermissionConfig, ResourceCache
from src.core.exceptions import SessionNotFoundError

class StorageService:
    """数据库存储服务"""

    def __init__(self, db_session: Session):
        self.db = db_session

    async def create_im_session(
        self,
        id: str,
        platform: str,
        platform_session_id: str
    ) -> IMSession:
        """创建 IM 会话"""
        session = IMSession(
            id=id,
            platform=platform,
            platform_session_id=platform_session_id
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def get_im_session(self, session_id: str) -> Optional[IMSession]:
        """获取 IM 会话"""
        return self.db.query(IMSession).filter_by(id=session_id).first()

    async def get_im_session_by_platform_id(
        self,
        platform: str,
        platform_session_id: str
    ) -> Optional[IMSession]:
        """通过平台 ID 获取 IM 会话"""
        return self.db.query(IMSession).filter_by(
            platform=platform,
            platform_session_id=platform_session_id
        ).first()

    async def update_im_session_last_active(self, session_id: str) -> None:
        """更新 IM 会话最后活跃时间"""
        session = await self.get_im_session(session_id)
        if session:
            session.last_active = datetime.utcnow()
            self.db.commit()

    async def create_claude_session(
        self,
        id: str,
        im_session_id: str,
        session_id: str,
        work_directory: str,
        summary: Optional[str] = None,
        is_active: bool = True
    ) -> ClaudeSession:
        """创建 Claude 会话"""
        session = ClaudeSession(
            id=id,
            im_session_id=im_session_id,
            session_id=session_id,
            work_directory=work_directory,
            summary=summary,
            is_active=is_active
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def get_claude_session(self, session_id: str) -> Optional[ClaudeSession]:
        """获取 Claude 会话"""
        return self.db.query(ClaudeSession).filter_by(id=session_id).first()

    async def get_claude_session_by_sdk_id(self, sdk_session_id: str) -> Optional[ClaudeSession]:
        """通过 SDK session_id 获取 Claude 会话"""
        return self.db.query(ClaudeSession).filter_by(session_id=sdk_session_id).first()

    async def get_active_claude_sessions(self, im_session_id: str) -> List[ClaudeSession]:
        """获取活跃的 Claude 会话列表"""
        return self.db.query(ClaudeSession).filter_by(
            im_session_id=im_session_id,
            is_active=True
        ).order_by(desc(ClaudeSession.created_at)).all()

    async def set_claude_session_active(self, session_id: str, is_active: bool) -> None:
        """设置 Claude 会话活跃状态"""
        session = await self.get_claude_session(session_id)
        if session:
            session.is_active = is_active
            self.db.commit()

    async def save_message(
        self,
        claude_session_id: str,
        role: str,
        content: str
    ) -> MessageHistory:
        """保存消息"""
        import uuid
        message = MessageHistory(
            id=str(uuid.uuid4()),
            claude_session_id=claude_session_id,
            role=role,
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    async def get_permission_configs(self) -> List[PermissionConfig]:
        """获取所有权限配置"""
        return self.db.query(PermissionConfig).filter_by(is_active=True).all()

    async def create_permission_config(self, path: str) -> PermissionConfig:
        """创建权限配置"""
        import uuid
        config = PermissionConfig(
            id=str(uuid.uuid4()),
            path=path
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    async def cache_resource(
        self,
        resource_key: str,
        local_path: str,
        mime_type: Optional[str] = None,
        size: Optional[int] = None,
        expires_days: int = 7
    ) -> ResourceCache:
        """缓存资源"""
        from datetime import timedelta
        import uuid

        # 检查是否已存在
        existing = self.db.query(ResourceCache).filter_by(resource_key=resource_key).first()
        if existing:
            return existing

        cache = ResourceCache(
            id=str(uuid.uuid4()),
            resource_key=resource_key,
            local_path=local_path,
            mime_type=mime_type,
            size=size,
            expires_at=datetime.utcnow() + timedelta(days=expires_days)
        )
        self.db.add(cache)
        self.db.commit()
        self.db.refresh(cache)
        return cache

    async def get_cached_resource(self, resource_key: str) -> Optional[ResourceCache]:
        """获取缓存的资源"""
        cache = self.db.query(ResourceCache).filter_by(resource_key=resource_key).first()
        if cache and cache.expires_at > datetime.utcnow():
            return cache
        return None
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_services/test_storage_service.py -v`
Expected: PASS (6 tests)

**Step 5: 提交**

```bash
git add src/services/storage_service.py tests/test_services/test_storage_service.py
git commit -m "feat: 添加存储服务"
```

---

## Task 4: 共享服务层

### Task 4.1: 创建权限管理器

**Files:**
- Create: `src/services/permission_manager.py`
- Test: `tests/test_services/test_permission_manager.py`

**Step 1: 编写测试**

```python
# tests/test_services/test_permission_manager.py
import pytest
from src.services.permission_manager import PermissionManager
from src.core.exceptions import PermissionDeniedError

@pytest.mark.asyncio
async def test_default_no_permissions():
    manager = PermissionManager([])
    assert manager.is_allowed("/tmp/test") is False
    assert manager.is_allowed("D:/Codes") is False

@pytest.mark.asyncio
async def test_add_allowed_directory():
    manager = PermissionManager([])
    manager.add_allowed_directory("D:/Codes")
    assert manager.is_allowed("D:/Codes") is True
    assert manager.is_allowed("D:/Codes/project") is True
    assert manager.is_allowed("D:/xxx") is False

@pytest.mark.asyncio
async def test_multiple_allowed_directories():
    manager = PermissionManager(["D:/Codes", "C:/Projects"])
    assert manager.is_allowed("D:/Codes/project") is True
    assert manager.is_allowed("C:/Projects/app") is True
    assert manager.is_allowed("E:/Data") is False

@pytest.mark.asyncio
async def test_windows_path_handling():
    manager = PermissionManager(["D:\\Codes"])
    assert manager.is_allowed("D:/Codes/project") is True
    assert manager.is_allowed("D:\\Codes\\project") is True

@pytest.mark.asyncio
async def test_remove_allowed_directory():
    manager = PermissionManager(["D:/Codes", "C:/Projects"])
    manager.remove_allowed_directory("D:/Codes")
    assert manager.is_allowed("D:/Codes") is False
    assert manager.is_allowed("C:/Projects") is True

@pytest.mark.asyncio
async def test_check_with_exception():
    manager = PermissionManager(["D:/Codes"])
    # 不应该抛出异常
    manager.check_permission("D:/Codes/project")

    # 应该抛出异常
    with pytest.raises(PermissionDeniedError):
        manager.check_permission("E:/Data")
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_services/test_permission_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.services.permission_manager'"

**Step 3: 实现权限管理器**

```python
# src/services/permission_manager.py
from typing import List
import os
from src.core.exceptions import PermissionDeniedError

class PermissionManager:
    """目录权限管理器"""

    def __init__(self, allowed_directories: List[str] = None):
        """初始化权限管理器

        Args:
            allowed_directories: 允许访问的目录列表
        """
        self.allowed_directories = allowed_directories or []

    def add_allowed_directory(self, path: str) -> None:
        """添加允许的目录"""
        normalized = self._normalize_path(path)
        if normalized not in self.allowed_directories:
            self.allowed_directories.append(normalized)

    def remove_allowed_directory(self, path: str) -> None:
        """移除允许的目录"""
        normalized = self._normalize_path(path)
        if normalized in self.allowed_directories:
            self.allowed_directories.remove(normalized)

    def is_allowed(self, path: str) -> bool:
        """检查路径是否允许访问"""
        if not self.allowed_directories:
            return False

        normalized = self._normalize_path(path)

        # 检查是否在允许的目录或其子目录中
        for allowed_dir in self.allowed_directories:
            if normalized == allowed_dir or normalized.startswith(allowed_dir + os.sep):
                return True

        return False

    def check_permission(self, path: str) -> None:
        """检查权限，无权限时抛出异常"""
        if not self.is_allowed(path):
            raise PermissionDeniedError(f"没有权限访问目录: {path}")

    def _normalize_path(self, path: str) -> str:
        """标准化路径（处理 Windows 路径分隔符）"""
        # 转换为绝对路径并标准化分隔符
        normalized = os.path.normpath(os.path.abspath(path))
        # 统一使用正斜线
        return normalized.replace("\\", "/")
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_services/test_permission_manager.py -v`
Expected: PASS (7 tests)

**Step 5: 提交**

```bash
git add src/services/permission_manager.py tests/test_services/test_permission_manager.py
git commit -m "feat: 添加权限管理器"
```

---

### Task 4.2: 创建会话管理器

**Files:**
- Create: `src/services/session_manager.py`
- Test: `tests/test_services/test_session_manager.py`

**Step 1: 编写测试**

```python
# tests/test_services/test_session_manager.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.services.session_manager import SessionManager
from src.core.claude_adapter import ClaudeSession
from src.core.exceptions import SessionNotFoundError
import tempfile
import os

@pytest.fixture
def mock_claude_adapter():
    adapter = Mock()
    adapter.create_session = AsyncMock()
    adapter.close_session = AsyncMock()
    adapter.get_session_info = AsyncMock()
    return adapter

@pytest.fixture
def mock_storage_service():
    from unittest.mock import MagicMock
    storage = MagicMock()
    storage.get_im_session_by_platform_id = AsyncMock(return_value=None)
    storage.create_im_session = AsyncMock()
    storage.get_active_claude_sessions = AsyncMock(return_value=[])
    storage.create_claude_session = AsyncMock()
    storage.set_claude_session_active = AsyncMock()
    return storage

@pytest.mark.asyncio
async def test_get_or_create_session_new_session(mock_claude_adapter, mock_storage_service):
    # 模拟存储服务返回 None（新会话）
    mock_storage_service.get_im_session_by_platform_id.return_value = None
    mock_storage_service.create_im_session.return_value = Mock(id="im_123")

    # 模拟 Claude 适配器创建会话
    mock_claude_adapter.create_session.return_value = ClaudeSession(
        session_id="claude_sdk_123",
        work_directory="./sessions/test_chat"
    )

    manager = SessionManager(mock_claude_adapter, mock_storage_service, "./sessions")

    session = await manager.get_or_create_session("feishu", "test_chat")

    assert session is not None
    assert session.session_id == "claude_sdk_123"

@pytest.mark.asyncio
async def test_create_session_with_custom_path(mock_claude_adapter, mock_storage_service):
    mock_storage_service.get_im_session_by_platform_id.return_value = Mock(id="im_123")
    mock_storage_service.get_active_claude_sessions.return_value = []

    mock_claude_adapter.create_session.return_value = ClaudeSession(
        session_id="claude_sdk_123",
        work_directory="/tmp/custom_path"
    )

    manager = SessionManager(
        mock_claude_adapter,
        mock_storage_service,
        "./sessions",
        permission_manager=Mock(is_allowed=lambda x: True)
    )

    session = await manager.create_session("feishu", "test_chat", "/tmp/custom_path")

    assert session.work_directory == "/tmp/custom_path"
    mock_claude_adapter.create_session.assert_called_once()

@pytest.mark.asyncio
async def test_list_sessions(mock_claude_adapter, mock_storage_service):
    mock_storage_service.get_im_session_by_platform_id.return_value = Mock(id="im_123")

    # 模拟返回两个会话
    mock_storage_service.get_active_claude_sessions.return_value = [
        Mock(id="c1", session_id="sdk_1", work_directory="/tmp/1", summary="Hello", is_active=True),
        Mock(id="c2", session_id="sdk_2", work_directory="/tmp/2", summary="World", is_active=False)
    ]

    manager = SessionManager(mock_claude_adapter, mock_storage_service, "./sessions")

    sessions = await manager.list_sessions("feishu", "test_chat")

    assert len(sessions) == 2
    assert sessions[0]['summary'] == "Hello"
    assert sessions[0]['is_active'] is True
    assert sessions[1]['is_active'] is False

@pytest.mark.asyncio
async def test_switch_session(mock_claude_adapter, mock_storage_service):
    mock_storage_service.get_im_session_by_platform_id.return_value = Mock(id="im_123")

    # 模拟会话列表
    mock_storage_service.get_active_claude_sessions.return_value = [
        Mock(id="c1", session_id="sdk_1", work_directory="/tmp/1", is_active=True),
        Mock(id="c2", session_id="sdk_2", work_directory="/tmp/2", is_active=False)
    ]

    manager = SessionManager(mock_claude_adapter, mock_storage_service, "./sessions")

    # 切换到第二个会话
    session = await manager.switch_session("feishu", "test_chat", "sdk_2")

    assert session['session_id'] == "sdk_2"
    # 验证将旧会话设为非活跃
    mock_storage_service.set_claude_session_active.assert_any_call("c1", False)
    # 验证将新会话设为活跃
    mock_storage_service.set_claude_session_active.assert_any_call("c2", True)

@pytest.mark.asyncio
async def test_switch_session_not_found(mock_claude_adapter, mock_storage_service):
    mock_storage_service.get_im_session_by_platform_id.return_value = Mock(id="im_123")
    mock_storage_service.get_active_claude_sessions.return_value = []

    manager = SessionManager(mock_claude_adapter, mock_storage_service, "./sessions")

    with pytest.raises(SessionNotFoundError):
        await manager.switch_session("feishu", "test_chat", "nonexistent")
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_services/test_session_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.services.session_manager'"

**Step 3: 实现会话管理器**

```python
# src/services/session_manager.py
import os
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.core.claude_adapter import ClaudeAdapter, ClaudeSession
from src.services.storage_service import StorageService
from src.services.permission_manager import PermissionManager
from src.core.exceptions import SessionNotFoundError

class SessionManager:
    """会话管理器"""

    def __init__(
        self,
        claude_adapter: ClaudeAdapter,
        storage: StorageService,
        default_session_root: str = "./sessions",
        permission_manager: Optional[PermissionManager] = None
    ):
        """初始化会话管理器

        Args:
            claude_adapter: Claude 适配器
            storage: 存储服务
            default_session_root: 默认会话根目录
            permission_manager: 权限管理器（可选）
        """
        self.claude = claude_adapter
        self.storage = storage
        self.default_root = Path(default_session_root)
        self.permission = permission_manager or PermissionManager()

        # 确保默认根目录存在
        self.default_root.mkdir(parents=True, exist_ok=True)

    async def get_or_create_session(
        self,
        platform: str,
        platform_session_id: str
    ) -> ClaudeSession:
        """获取或创建会话

        Args:
            platform: 平台名称（如 'feishu'）
            platform_session_id: 平台会话 ID

        Returns:
            ClaudeSession 对象
        """
        # 尝试获取现有的 IM 会话
        im_session = await self.storage.get_im_session_by_platform_id(
            platform,
            platform_session_id
        )

        if not im_session:
            # 创建新的 IM 会话
            im_session = await self.storage.create_im_session(
                id=str(uuid.uuid4()),
                platform=platform,
                platform_session_id=platform_session_id
            )

        # 获取活跃的 Claude 会话
        active_sessions = await self.storage.get_active_claude_sessions(im_session.id)

        if active_sessions:
            # 返回第一个活跃会话
            sdk_session_id = active_sessions[0].session_id
            session = await self.claude.get_session_info(sdk_session_id)
            if session:
                return session

        # 没有活跃会话，创建新会话
        work_dir = self.default_root / platform_session_id
        work_dir.mkdir(parents=True, exist_ok=True)

        claude_session = await self.claude.create_session(str(work_dir))

        # 保存到数据库
        await self.storage.create_claude_session(
            id=str(uuid.uuid4()),
            im_session_id=im_session.id,
            session_id=claude_session.session_id,
            work_directory=str(work_dir),
            is_active=True
        )

        return claude_session

    async def create_session(
        self,
        platform: str,
        platform_session_id: str,
        work_directory: Optional[str] = None,
        summary: Optional[str] = None
    ) -> ClaudeSession:
        """创建新会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID
            work_directory: 工作目录（可选，默认使用会话 ID 创建）
            summary: 会话摘要（可选）

        Returns:
            ClaudeSession 对象
        """
        # 获取或创建 IM 会话
        im_session = await self.storage.get_im_session_by_platform_id(
            platform,
            platform_session_id
        )

        if not im_session:
            im_session = await self.storage.create_im_session(
                id=str(uuid.uuid4()),
                platform=platform,
                platform_session_id=platform_session_id
            )

        # 确定工作目录
        if work_directory:
            # 检查权限
            self.permission.check_permission(work_directory)
            work_dir = Path(work_directory)
        else:
            # 使用默认目录
            work_dir = self.default_root / platform_session_id

        work_dir.mkdir(parents=True, exist_ok=True)

        # 创建 Claude 会话
        claude_session = await self.claude.create_session(str(work_dir))

        # 将所有现有会话设为非活跃
        active_sessions = await self.storage.get_active_claude_sessions(im_session.id)
        for session in active_sessions:
            await self.storage.set_claude_session_active(session.id, False)

        # 保存新会话
        await self.storage.create_claude_session(
            id=str(uuid.uuid4()),
            im_session_id=im_session.id,
            session_id=claude_session.session_id,
            work_directory=str(work_dir),
            summary=summary or claude_session.session_id[:10],
            is_active=True
        )

        return claude_session

    async def list_sessions(
        self,
        platform: str,
        platform_session_id: str
    ) -> List[Dict[str, Any]]:
        """列出所有会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID

        Returns:
            会话列表，包含 session_id, summary, is_active 等信息
        """
        im_session = await self.storage.get_im_session_by_platform_id(
            platform,
            platform_session_id
        )

        if not im_session:
            return []

        sessions = await self.storage.get_active_claude_sessions(im_session.id)

        return [
            {
                'id': s.id,
                'session_id': s.session_id,
                'summary': s.summary or s.session_id[:10],
                'is_active': s.is_active,
                'work_directory': s.work_directory
            }
            for s in sessions
        ]

    async def switch_session(
        self,
        platform: str,
        platform_session_id: str,
        claude_session_id: str
    ) -> Dict[str, Any]:
        """切换活跃会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID
            claude_session_id: Claude SDK 会话 ID

        Returns:
            切换后的会话信息

        Raises:
            SessionNotFoundError: 会话不存在
        """
        im_session = await self.storage.get_im_session_by_platform_id(
            platform,
            platform_session_id
        )

        if not im_session:
            raise SessionNotFoundError(f"会话不存在: {platform_session_id}")

        # 查找目标会话
        from src.services.models import ClaudeSession as CS
        sessions = await self.storage.get_active_claude_sessions(im_session.id)

        target_session = None
        for s in sessions:
            if s.session_id == claude_session_id:
                target_session = s
                break

        if not target_session:
            raise SessionNotFoundError(f"Claude 会话不存在: {claude_session_id}")

        # 将所有会话设为非活跃
        for s in sessions:
            await self.storage.set_claude_session_active(s.id, False)

        # 将目标会话设为活跃
        await self.storage.set_claude_session_active(target_session.id, True)

        return {
            'id': target_session.id,
            'session_id': target_session.session_id,
            'summary': target_session.summary,
            'is_active': True,
            'work_directory': target_session.work_directory
        }
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_services/test_session_manager.py -v`
Expected: PASS (5 tests)

**Step 5: 提交**

```bash
git add src/services/session_manager.py tests/test_services/test_session_manager.py
git commit -m "feat: 添加会话管理器"
```

---

### Task 4.3: 创建资源管理器

**Files:**
- Create: `src/services/resource_manager.py`
- Test: `tests/test_services/test_resource_manager.py`

**Step 1: 编写测试**

```python
# tests/test_services/test_resource_manager.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.services.resource_manager import ResourceManager
import tempfile
import os

@pytest.fixture
def mock_storage():
    storage = Mock()
    storage.get_cached_resource = AsyncMock(return_value=None)
    storage.cache_resource = AsyncMock()
    return storage

@pytest.mark.asyncio
async def test_download_resource_new(mock_storage):
    manager = ResourceManager(mock_storage, cache_dir="/tmp/cache")

    # Mock HTTP 请求
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_resp = Mock()
        mock_resp.read = AsyncMock(return_value=b"file content")
        mock_resp.raise_for_status = Mock()
        mock_get.return_value.__aenter__.return_value = mock_resp

        content = await manager.download_resource("http://example.com/file.png", "file_key")

        assert content == b"file content"
        # 验证缓存
        mock_storage.cache_resource.assert_called_once()

@pytest.mark.asyncio
async def test_download_resource_from_cache(mock_storage):
    # 模拟缓存命中
    mock_cache = Mock()
    mock_cache.local_path = "/tmp/cached_file.png"
    mock_storage.get_cached_resource.return_value = mock_cache

    manager = ResourceManager(mock_storage, cache_dir="/tmp/cache")

    with patch('aiofiles.open', create=True) as mock_open:
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=b"cached content")
        mock_open.return_value.__aenter__.return_value = mock_file

        content = await manager.download_resource("http://example.com/file.png", "file_key")

        assert content == b"cached content"
        # 不应该重新下载
        mock_storage.cache_resource.assert_not_called()

@pytest.mark.asyncio
async def test_save_resource_to_workdir(mock_storage):
    manager = ResourceManager(mock_storage, cache_dir="/tmp/cache")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock 文件写入
        with patch('aiofiles.open', create=True) as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            await manager.save_resource(
                b"content",
                tmpdir,
                ".feishu_data",
                "image.png"
            )

            # 验证调用
            mock_file.write.assert_called_once()
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/test_services/test_resource_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.services.resource_manager'"

**Step 3: 实现资源管理器**

```python
# src/services/resource_manager.py
import os
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from src.services.storage_service import StorageService
from src.core.exceptions import ResourceDownloadError

class ResourceManager:
    """资源管理器"""

    def __init__(self, storage: StorageService, cache_dir: str = "/tmp/feishu_cache"):
        """初始化资源管理器

        Args:
            storage: 存储服务
            cache_dir: 缓存目录
        """
        self.storage = storage
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def download_resource(
        self,
        url: str,
        resource_key: str,
        use_cache: bool = True
    ) -> bytes:
        """下载资源文件

        Args:
            url: 资源 URL
            resource_key: 资源唯一标识
            use_cache: 是否使用缓存

        Returns:
            文件内容
        """
        # 检查缓存
        if use_cache:
            cached = await self.storage.get_cached_resource(resource_key)
            if cached:
                # 从缓存读取
                try:
                    async with aiofiles.open(cached.local_path, 'rb') as f:
                        return await f.read()
                except Exception:
                    pass  # 缓存读取失败，重新下载

        # 下载文件
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    content = await response.read()

                    # 缓存文件
                    cache_path = self.cache_dir / resource_key
                    async with aiofiles.open(cache_path, 'wb') as f:
                        await f.write(content)

                    # 保存缓存记录
                    await self.storage.cache_resource(
                        resource_key=resource_key,
                        local_path=str(cache_path),
                        size=len(content)
                    )

                    return content

        except Exception as e:
            raise ResourceDownloadError(f"下载资源失败: {url}, 错误: {str(e)}")

    async def save_resource(
        self,
        content: bytes,
        work_dir: str,
        subdir: str = ".feishu_data",
        filename: str = None
    ) -> str:
        """保存资源到工作目录

        Args:
            content: 文件内容
            work_dir: 工作目录
            subdir: 子目录名称
            filename: 文件名（可选，自动生成）

        Returns:
            保存的文件路径
        """
        import uuid

        # 创建子目录
        target_dir = Path(work_dir) / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        if not filename:
            filename = f"{uuid.uuid4()}"

        file_path = target_dir / filename

        # 写入文件
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        return str(file_path)
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/test_services/test_resource_manager.py -v`
Expected: PASS (3 tests)

**Step 5: 提交**

```bash
git add src/services/resource_manager.py tests/test_services/test_resource_manager.py
git commit -m "feat: 添加资源管理器"
```

---

## Task 5: Claude SDK 实现

由于实施计划非常详细且篇幅很长，我已经完成了核心抽象层、数据持久化层和共享服务层的实施步骤。接下来需要：

- Task 5: Claude SDK 实现
- Task 6: 飞书桥接实现（最复杂的部分）
- Task 7: CLI 入口
- Task 8: 测试和文档

由于剩余部分仍然很详细，我建议在这里暂停，确认当前的设计方向是否符合你的预期。当前已完成的部分包括：

✅ **已完成的设计部分**：
1. 项目基础设施
2. 核心抽象层（IMAdapter、ClaudeAdapter、消息模型、异常类）
3. 数据持久化层（SQLAlchemy 模型、存储服务）
4. 共享服务层（权限管理器、会话管理器、资源管理器）

📋 **待完成的部分**：
5. Claude SDK 实现（claude-agent-sdk 的适配）
6. 飞书桥接实现（FeishuBridge、消息处理、命令处理）
7. CLI 入口（启动脚本、配置加载）
8. 完整测试和文档

你想让我继续完成剩余的实施计划吗？或者你对当前的设计有任何调整建议？
