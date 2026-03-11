# tests/test_bridges/test_feishu/test_command_handler.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.bridges.feishu.command_handler import CommandHandler
from src.core.message import IMMessage, MessageType
from src.core.exceptions import SessionNotFoundError, PermissionDeniedError


@pytest.fixture
def mock_bridge():
    """Mock FeishuBridge"""
    bridge = Mock()
    bridge.session_manager = Mock()
    bridge.platform = "feishu"

    # Mock session manager methods
    bridge.session_manager.create_session = AsyncMock()
    bridge.session_manager.list_sessions = AsyncMock()
    bridge.session_manager.switch_session = AsyncMock()

    return bridge


@pytest.fixture
def command_handler(mock_bridge):
    """创建 CommandHandler 实例"""
    return CommandHandler(mock_bridge)


@pytest.fixture
def sample_message():
    """创建示例消息"""
    return IMMessage(
        content="/new",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="feishu_chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=True
    )


@pytest.mark.asyncio
async def test_handle_new_command_no_path(command_handler, mock_bridge, sample_message):
    """测试 /new 命令不带路径参数"""
    # Mock 创建会话成功
    mock_claude_session = Mock()
    mock_claude_session.session_id = "claude_sdk_123"
    mock_claude_session.work_directory = "/tmp/claude_sessions/feishu_chat_123"
    mock_bridge.session_manager.create_session.return_value = mock_claude_session

    # 修改消息内容
    sample_message.content = "/new"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证
    assert result is not None
    assert "成功创建新会话" in result or "会话已创建" in result
    assert "claude_sdk_123" in result

    # 验证调用
    mock_bridge.session_manager.create_session.assert_called_once()


@pytest.mark.asyncio
async def test_handle_new_command_with_path(command_handler, mock_bridge, sample_message):
    """测试 /new 命令带路径参数"""
    # Mock 创建会话成功
    mock_claude_session = Mock()
    mock_claude_session.session_id = "claude_sdk_456"
    mock_claude_session.work_directory = "/custom/path"
    mock_bridge.session_manager.create_session.return_value = mock_claude_session

    # 修改消息内容
    sample_message.content = "/new /custom/path"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证
    assert result is not None
    assert "成功创建新会话" in result or "会话已创建" in result
    assert "claude_sdk_456" in result
    assert "/custom/path" in result

    # 验证调用时包含路径
    mock_bridge.session_manager.create_session.assert_called_once_with(
        platform="feishu",
        platform_session_id="feishu_chat_123",
        work_directory="/custom/path",
        summary=f"会话创建于 feishu_chat_123"
    )


@pytest.mark.asyncio
async def test_handle_new_command_permission_denied(command_handler, mock_bridge, sample_message):
    """测试 /new 命令权限不足"""
    # Mock 权限检查失败
    mock_bridge.session_manager.create_session.side_effect = PermissionDeniedError("没有权限访问目录")

    # 修改消息内容
    sample_message.content = "/new /unauthorized/path"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证错误信息
    assert result is not None
    assert "权限" in result or "不允许" in result


@pytest.mark.asyncio
async def test_handle_sessions_command(command_handler, mock_bridge, sample_message):
    """测试 /sessions 命令"""
    # Mock 会话列表
    mock_sessions = [
        {
            "id": "session_1",
            "session_id": "sdk_1",
            "work_directory": "/work/1",
            "is_active": True,
            "summary": "Session 1",
            "created_at": "2024-01-01T00:00:00"
        },
        {
            "id": "session_2",
            "session_id": "sdk_2",
            "work_directory": "/work/2",
            "is_active": False,
            "summary": "Session 2",
            "created_at": "2024-01-02T00:00:00"
        }
    ]
    mock_bridge.session_manager.list_sessions.return_value = mock_sessions

    # 修改消息内容
    sample_message.content = "/sessions"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证
    assert result is not None
    assert "session_1" in result or "sdk_1" in result
    # 检查活跃标记 (使用 ✨ emoji 而不是文字)
    assert "✨" in result

    # 验证调用 - 使用关键字参数
    mock_bridge.session_manager.list_sessions.assert_called_once_with(
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )


@pytest.mark.asyncio
async def test_handle_switch_command(command_handler, mock_bridge, sample_message):
    """测试 /switch 命令"""
    # Mock 切换会话成功
    mock_session = {
        "id": "session_target",
        "session_id": "sdk_target",
        "work_directory": "/work/target",
        "is_active": True,
        "summary": "Target Session",
        "created_at": "2024-01-01T00:00:00"
    }
    mock_bridge.session_manager.switch_session.return_value = mock_session

    # 修改消息内容
    sample_message.content = "/switch session_target"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证
    assert result is not None
    assert "切换成功" in result or "已切换" in result or "session_target" in result

    # 验证调用 - 使用关键字参数
    mock_bridge.session_manager.switch_session.assert_called_once_with(
        platform="feishu",
        platform_session_id="feishu_chat_123",
        claude_session_id="session_target"
    )


@pytest.mark.asyncio
async def test_handle_switch_not_found(command_handler, mock_bridge, sample_message):
    """测试 /switch 命令切换不存在的会话"""
    # Mock 切换会话失败
    mock_bridge.session_manager.switch_session.side_effect = SessionNotFoundError("会话不存在")

    # 修改消息内容
    sample_message.content = "/switch non_existent"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证错误信息
    assert result is not None
    assert "不存在" in result or "未找到" in result


@pytest.mark.asyncio
async def test_handle_unknown_command(command_handler, sample_message):
    """测试未知命令"""
    # 修改消息内容为未知命令
    sample_message.content = "/unknown_command"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证
    assert result is not None
    assert "未知" in result or "无法识别" in result or "帮助" in result


@pytest.mark.asyncio
async def test_handle_non_command_message(command_handler, sample_message):
    """测试非命令消息"""
    # 修改消息内容为普通文本
    sample_message.content = "Hello, how are you?"

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证返回 None (非命令消息不处理)
    assert result is None


@pytest.mark.asyncio
async def test_handle_empty_command(command_handler, sample_message):
    """测试空命令"""
    # 修改消息内容为空
    sample_message.content = ""

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证返回 None
    assert result is None


@pytest.mark.asyncio
async def test_handle_new_command_with_empty_path(command_handler, mock_bridge, sample_message):
    """测试 /new 命令带空路径"""
    # Mock 创建会话成功
    mock_claude_session = Mock()
    mock_claude_session.session_id = "claude_sdk_789"
    mock_claude_session.work_directory = "/tmp/claude_sessions/feishu_chat_123"
    mock_bridge.session_manager.create_session.return_value = mock_claude_session

    # 修改消息内容,只有路径前缀没有实际路径
    sample_message.content = "/new   "

    # 调用处理方法
    result = await command_handler.handle(sample_message)

    # 验证 - 应该使用默认路径
    assert result is not None
    assert "成功创建新会话" in result or "会话已创建" in result
    mock_bridge.session_manager.create_session.assert_called_once()
