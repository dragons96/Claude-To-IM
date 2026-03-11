# tests/test_claude/test_sdk_adapter.py
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.claude.sdk_adapter import ClaudeSDKAdapter
from src.core.claude_adapter import ClaudeSession
from src.core.message import StreamEvent, StreamEventType


@pytest.fixture
def mock_sdk_client():
    """Mock ClaudeSDKClient"""
    with patch('src.claude.sdk_adapter.ClaudeSDKClient') as mock:
        yield mock


@pytest.fixture
def adapter(mock_sdk_client):
    """创建适配器实例"""
    # 创建 mock 客户端实例
    mock_client_instance = Mock()
    mock_sdk_client.return_value = mock_client_instance

    # 创建适配器
    from claude_agent_sdk import ClaudeAgentOptions
    options = ClaudeAgentOptions(
        model="claude-3-5-sonnet-20241022"
    )
    return ClaudeSDKAdapter(options)


@pytest.mark.asyncio
async def test_create_session(adapter, mock_sdk_client):
    """测试创建会话"""
    mock_client = mock_sdk_client.return_value

    # 调用创建会话
    session = await adapter.create_session("/tmp/work", "test_session")

    # 验证会话创建
    assert session.session_id == "test_session"
    assert session.work_directory == "/tmp/work"
    assert session.is_active is True
    assert "test_session" in adapter.sessions

    # 验证客户端创建
    mock_sdk_client.assert_called_once()
    assert adapter.sessions["test_session"]["client"] == mock_client


@pytest.mark.asyncio
async def test_create_session_with_auto_id(adapter, mock_sdk_client):
    """测试自动生成会话 ID"""
    mock_client = mock_sdk_client.return_value

    session = await adapter.create_session("/tmp/work")

    assert session.session_id is not None
    assert session.work_directory == "/tmp/work"
    assert session.is_active is True
    assert session.session_id in adapter.sessions


@pytest.mark.asyncio
async def test_send_message_with_text(adapter, mock_sdk_client):
    """测试发送消息并接收文本响应"""
    mock_client = mock_sdk_client.return_value

    # 创建会话
    session = await adapter.create_session("/tmp/work", "test_session")

    # 模拟 query 方法
    mock_client.query = AsyncMock()

    # 模拟 receive_messages 返回文本消息
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def mock_receive():
        yield AssistantMessage(
            content=[TextBlock(text="Hello")],
            model="claude-3-5-sonnet-20241022"
        )
        yield AssistantMessage(
            content=[TextBlock(text=" World")],
            model="claude-3-5-sonnet-20241022"
        )

    mock_client.receive_messages = mock_receive

    # 发送消息
    events = []
    async for event in adapter.send_message("test_session", "Hello"):
        events.append(event)

    # 验证事件
    assert len(events) == 3  # 2 TEXT_DELTA + 1 END
    assert events[0].event_type == StreamEventType.TEXT_DELTA
    assert events[0].content == "Hello"
    assert events[1].event_type == StreamEventType.TEXT_DELTA
    assert events[1].content == " World"
    assert events[2].event_type == StreamEventType.END

    # 验证调用
    mock_client.query.assert_called_once_with("Hello", "test_session")


@pytest.mark.asyncio
async def test_send_message_with_tool_use(adapter, mock_sdk_client):
    """测试发送消息并接收工具调用"""
    mock_client = mock_sdk_client.return_value

    # 创建会话
    session = await adapter.create_session("/tmp/work", "test_session")

    # 模拟 query 方法
    mock_client.query = AsyncMock()

    # 模拟 receive_messages 返回工具调用
    from claude_agent_sdk import AssistantMessage, ToolUseBlock

    async def mock_receive():
        yield AssistantMessage(
            content=[ToolUseBlock(
                id="tool-123",
                name="test_tool",
                input={"arg1": "value1"}
            )],
            model="claude-3-5-sonnet-20241022"
        )

    mock_client.receive_messages = mock_receive

    # 发送消息
    events = []
    async for event in adapter.send_message("test_session", "Use tool"):
        events.append(event)

    # 验证事件
    assert len(events) == 2  # 1 TOOL_USE + 1 END
    assert events[0].event_type == StreamEventType.TOOL_USE
    assert events[0].tool_name == "test_tool"
    assert events[0].tool_input == {"arg1": "value1"}
    assert events[1].event_type == StreamEventType.END


@pytest.mark.asyncio
async def test_close_session(adapter, mock_sdk_client):
    """测试关闭会话"""
    mock_client = mock_sdk_client.return_value

    # 创建会话
    session = await adapter.create_session("/tmp/work", "test_session")
    assert session.is_active is True

    # 模拟 close 方法
    mock_client.close = AsyncMock()

    # 关闭会话
    await adapter.close_session("test_session")

    # 验证会话已关闭
    session_info = await adapter.get_session_info("test_session")
    assert session_info is None  # 会话应被移除

    # 验证 close 被调用
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_session_info(adapter):
    """测试获取会话信息"""
    # 创建会话
    session = await adapter.create_session("/tmp/work", "test_session")

    # 获取会话信息
    session_info = await adapter.get_session_info("test_session")

    assert session_info is not None
    assert session_info.session_id == "test_session"
    assert session_info.work_directory == "/tmp/work"
    assert session_info.is_active is True

    # 测试不存在的会话
    nonexistent = await adapter.get_session_info("nonexistent")
    assert nonexistent is None


@pytest.mark.asyncio
async def test_list_sessions(adapter):
    """测试列出所有会话"""
    # 创建多个会话
    session1 = await adapter.create_session("/tmp/work1", "session1")
    session2 = await adapter.create_session("/tmp/work2", "session2")

    sessions = await adapter.list_sessions()

    assert len(sessions) == 2
    session_ids = {s.session_id for s in sessions}
    assert session_ids == {"session1", "session2"}


@pytest.mark.asyncio
async def test_send_message_nonexistent_session(adapter):
    """测试向不存在的会话发送消息"""
    with pytest.raises(ValueError, match="Session nonexistent not found"):
        async for _ in adapter.send_message("nonexistent", "Hello"):
            pass


@pytest.mark.asyncio
async def test_send_message_with_result_message(adapter, mock_sdk_client):
    """测试处理 ResultMessage"""
    mock_client = mock_sdk_client.return_value

    # 创建会话
    session = await adapter.create_session("/tmp/work", "test_session")

    # 模拟 query 方法
    mock_client.query = AsyncMock()

    # 模拟 receive_messages 返回结果消息
    from claude_agent_sdk import ResultMessage

    async def mock_receive():
        yield ResultMessage(
            subtype="success",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=1,
            session_id="test_session"
        )

    mock_client.receive_messages = mock_receive

    # 发送消息
    events = []
    async for event in adapter.send_message("test_session", "Hello"):
        events.append(event)

    # 验证事件
    assert len(events) == 1  # 1 END
    assert events[0].event_type == StreamEventType.END
