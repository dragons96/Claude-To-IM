"""测试 /session:exec 临时会话不污染活跃列表"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.bridges.feishu.adapter import FeishuBridge
from src.core.message import IMMessage, MessageType


@pytest.mark.asyncio
async def test_session_exec_temporary_session_not_pollute_active_list():
    """
    测试 /session:exec 使用临时会话时不污染活跃会话列表

    验证：
    1. 临时创建的会话不在 self.claude_adapter.sessions 中
    2. 使用后会话被清理
    3. 活跃会话列表保持不变
    """
    mock_storage = Mock()
    mock_db = Mock()
    mock_claude_adapter = Mock()

    # 模拟数据库查询返回非活跃会话
    mock_session_record = Mock()
    mock_session_record.id = "db-session-id"
    mock_session_record.session_id = "sdk-session-id"
    mock_session_record.work_directory = "/path/to/session"
    mock_session_record.is_active = False

    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_session_record
    mock_storage.db = mock_db

    # 模拟 SDK adapter 内存中没有这个会话
    mock_claude_adapter.sessions = {}
    mock_claude_adapter.options = Mock()

    message = IMMessage(
        content="测试消息",
        message_type=MessageType.TEXT,
        message_id="msg-123",
        session_id="chat-456",
        user_id="user-789",
        user_name="Test User",
        is_private_chat=True,
    )

    with patch('src.bridges.feishu.adapter.FeishuBridge.__init__', return_value=None):
        adapter = FeishuBridge.__new__(FeishuBridge)
        adapter.session_manager = Mock()
        adapter.session_manager.storage = mock_storage
        adapter.claude_adapter = mock_claude_adapter
        adapter.platform = "feishu"
        adapter.send_message = AsyncMock(return_value="msg-response")
        adapter._process_attachments = AsyncMock()

        # Mock 临时 client
        mock_temp_client = MagicMock()
        mock_temp_client.__aenter__ = AsyncMock(return_value=None)
        mock_temp_client.__aexit__ = AsyncMock(return_value=None)
        mock_temp_client.query = AsyncMock()
        mock_temp_client.receive_messages = AsyncMock()

        # Mock 消息响应
        mock_assistant_msg = Mock()
        mock_text_block = Mock()
        mock_text_block.text = "这是响应内容"
        mock_assistant_msg.content = [mock_text_block]

        async def mock_receive():
            yield mock_assistant_msg

        mock_temp_client.receive_messages = mock_receive

        with patch('claude_agent_sdk.ClaudeSDKClient', return_value=mock_temp_client):
            # 执行
            await adapter.route_to_claude_with_session(message, "sdk-session-id")

            # 验证
            # 1. 临时会话被创建
            assert mock_temp_client.__aenter__.called

            # 2. 临时会话被使用
            assert mock_temp_client.query.called

            # 3. 临时会话被清理
            assert mock_temp_client.__aexit__.called

            # 4. 活跃会话列表没有被污染
            assert "sdk-session-id" not in mock_claude_adapter.sessions
            assert len(mock_claude_adapter.sessions) == 0


@pytest.mark.asyncio
async def test_session_exec_active_session_uses_standard_flow():
    """
    测试 /session:exec 访问活跃会话时使用标准流程
    """
    mock_storage = Mock()
    mock_db = Mock()
    mock_claude_adapter = Mock()

    # 模拟数据库查询返回活跃会话
    mock_session_record = Mock()
    mock_session_record.session_id = "active-session-id"
    mock_session_record.work_directory = "/path/to/session"
    mock_session_record.is_active = True

    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_session_record
    mock_storage.db = mock_db

    # 模拟会话在活跃列表中
    mock_claude_adapter.sessions = {
        "active-session-id": {
            "session": Mock(),
            "client": Mock()
        }
    }

    message = IMMessage(
        content="测试消息",
        message_type=MessageType.TEXT,
        message_id="msg-123",
        session_id="chat-456",
        user_id="user-789",
        user_name="Test User",
        is_private_chat=True,
    )

    with patch('src.bridges.feishu.adapter.FeishuBridge.__init__', return_value=None):
        adapter = FeishuBridge.__new__(FeishuBridge)
        adapter.session_manager = Mock()
        adapter.session_manager.storage = mock_storage
        adapter.claude_adapter = mock_claude_adapter
        adapter.platform = "feishu"
        adapter._stream_claude_response = AsyncMock()

        # 执行
        await adapter.route_to_claude_with_session(message, "active-session-id")

        # 验证：使用了标准流程
        adapter._stream_claude_response.assert_called_once_with(
            session_id="chat-456",
            claude_session_id="active-session-id",
            message_content="测试消息",
            user_message_id="msg-123"
        )


@pytest.mark.asyncio
async def test_session_exec_cleanup_on_error():
    """
    测试 /session:exec 即使出错也清理临时会话
    """
    mock_storage = Mock()
    mock_db = Mock()
    mock_claude_adapter = Mock()

    mock_session_record = Mock()
    mock_session_record.session_id = "temp-session-id"
    mock_session_record.work_directory = "/path/to/session"
    mock_session_record.is_active = False

    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_session_record
    mock_storage.db = mock_db
    mock_claude_adapter.sessions = {}
    mock_claude_adapter.options = Mock()

    message = IMMessage(
        content="测试消息",
        message_type=MessageType.TEXT,
        message_id="msg-123",
        session_id="chat-456",
        user_id="user-789",
        user_name="Test User",
        is_private_chat=True,
    )

    with patch('src.bridges.feishu.adapter.FeishuBridge.__init__', return_value=None):
        adapter = FeishuBridge.__new__(FeishuBridge)
        adapter.session_manager = Mock()
        adapter.session_manager.storage = mock_storage
        adapter.claude_adapter = mock_claude_adapter
        adapter.platform = "feishu"
        adapter.send_message = AsyncMock()
        adapter._process_attachments = AsyncMock()

        # Mock 临时 client（查询时抛出错误）
        mock_temp_client = MagicMock()
        mock_temp_client.__aenter__ = AsyncMock(return_value=None)
        mock_temp_client.__aexit__ = AsyncMock(return_value=None)
        mock_temp_client.query = AsyncMock(side_effect=Exception("查询失败"))

        with patch('claude_agent_sdk.ClaudeSDKClient', return_value=mock_temp_client):
            # 执行
            await adapter.route_to_claude_with_session(message, "temp-session-id")

            # 验证：即使出错也清理了临时会话
            assert mock_temp_client.__aexit__.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
