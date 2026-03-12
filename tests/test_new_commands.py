# tests/test_new_commands.py
"""测试新增的命令功能"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from src.bridges.feishu.command_handler import CommandHandler
from src.core.message import IMMessage, MessageType


@pytest.fixture
def mock_bridge():
    """创建模拟的 bridge 对象"""
    bridge = Mock()

    # 模拟 session_manager
    bridge.session_manager = Mock()
    bridge.session_manager.delete_session = AsyncMock()
    bridge.session_manager.delete_session_by_db_id = AsyncMock()
    bridge.session_manager.storage = Mock()

    # 模拟 platform
    bridge.platform = "feishu"

    return bridge


@pytest.fixture
def command_handler(mock_bridge):
    """创建命令处理器实例"""
    handler = CommandHandler(bridge=mock_bridge)
    return handler


@pytest.fixture
def sample_message():
    """创建示例消息"""
    return IMMessage(
        content="test message",
        message_type=MessageType.TEXT,
        message_id="msg123",
        session_id="chat456",
        user_id="user789",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=False,
    )


@pytest.mark.asyncio
async def test_handle_delete_success(command_handler, sample_message, mock_bridge):
    """测试 /delete 命令 - 成功删除会话"""
    # 设置模拟返回值（使用新的 delete_session_by_db_id 方法）
    mock_bridge.session_manager.delete_session_by_db_id = AsyncMock(return_value={
        "id": "session123",
        "session_id": "sdk-session-123",
        "work_directory": "/path/to/session",
        "summary": "Test session",
    })

    # 执行命令
    result = await command_handler._handle_delete(sample_message, "session123")

    # 验证返回值（现在显示的是数据库 id）
    assert "✅ 成功删除会话" in result
    assert "session123" in result  # 显示数据库 id
    assert "/path/to/session" in result

    # 验证调用了正确的方法
    mock_bridge.session_manager.delete_session_by_db_id.assert_called_once_with(
        platform="feishu",
        platform_session_id="chat456",
        db_session_id="session123"
    )


@pytest.mark.asyncio
async def test_handle_delete_missing_session_id(command_handler, sample_message):
    """测试 /delete 命令 - 缺少会话ID"""
    result = await command_handler._handle_delete(sample_message, "")

    # 验证错误提示
    assert "❌ 请指定要删除的会话ID" in result
    assert "用法:" in result


@pytest.mark.asyncio
async def test_session_exec_success(command_handler, sample_message, mock_bridge):
    """测试 /session:exec 命令 - 成功在指定会话执行"""
    # 模拟存储服务
    mock_im_session = Mock()
    mock_im_session.id = "im_session_123"

    mock_claude_session = Mock()
    mock_claude_session.id = "db-session-123"  # 数据库id
    mock_claude_session.im_session_id = "im_session_123"
    mock_claude_session.session_id = "sdk-session-abc"  # SDK session_id

    mock_bridge.session_manager.storage.get_im_session_by_platform_id = AsyncMock(
        return_value=mock_im_session
    )
    # 修改为使用 get_claude_session（数据库id查询）而不是 get_claude_session_by_sdk_id
    mock_bridge.session_manager.storage.get_claude_session = AsyncMock(
        return_value=mock_claude_session
    )

    # 执行命令（使用数据库id）
    result = await command_handler._handle_session_exec(
        sample_message,
        "db-session-123 帮我分析这段代码"  # 使用数据库id
    )

    # 验证返回值类型
    assert isinstance(result, dict)
    assert result["type"] == "exec_in_session"
    assert result["claude_session_id"] == "sdk-session-abc"
    assert result["db_session_id"] == "db-session-123"
    assert result["message"].content == "帮我分析这段代码"


@pytest.mark.asyncio
async def test_session_exec_missing_params(command_handler, sample_message):
    """测试 /session:exec 命令 - 参数不足"""
    result = await command_handler._handle_session_exec(
        sample_message,
        "db-session-123"
    )

    # 验证错误提示
    assert "❌ 参数不足" in result
    assert "用法:" in result


@pytest.mark.asyncio
async def test_session_exec_session_not_found(command_handler, sample_message, mock_bridge):
    """测试 /session:exec 命令 - 会话不存在"""
    # 模拟存储服务返回 None
    mock_bridge.session_manager.storage.get_im_session_by_platform_id = AsyncMock(
        return_value=None
    )

    # 执行命令
    result = await command_handler._handle_session_exec(
        sample_message,
        "invalid-session 帮我分析这段代码"
    )

    # 验证错误提示
    assert "❌" in result
    assert "不存在" in result or "不属于" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
