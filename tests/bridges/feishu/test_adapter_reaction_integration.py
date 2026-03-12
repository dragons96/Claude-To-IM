"""
FeishuBridge表情管理集成测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.bridges.feishu.adapter import FeishuBridge
from src.bridges.feishu.reaction_manager import FeishuReactionManager


class TestFeishuBridgeReactionIntegration:
    """测试FeishuBridge与ReactionManager的集成"""

    @pytest.mark.asyncio
    async def test_adapter_has_reaction_manager(self):
        """测试Adapter启动时创建reaction_manager"""
        # 创建mock依赖
        mock_claude_adapter = Mock()
        mock_session_manager = Mock()
        mock_resource_manager = Mock()
        mock_message_handler = Mock()
        mock_message_handler.bot_user_id = None
        mock_command_handler = Mock()
        mock_card_builder = Mock()

        config = {
            "app_id": "test_app",
            "app_secret": "test_secret",
            "encrypt_key": "test_key",
            "verification_token": "test_token",
            "bot_user_id": "bot_123"
        }

        # 创建adapter
        adapter = FeishuBridge(
            config=config,
            claude_adapter=mock_claude_adapter,
            session_manager=mock_session_manager,
            resource_manager=mock_resource_manager,
            message_handler=mock_message_handler,
            command_handler=mock_command_handler,
            card_builder=mock_card_builder
        )

        # 验证初始化时为None
        assert adapter.reaction_manager is None

        # Mock WebSocket客户端创建
        with patch('lark_oapi.ws.Client'):
            # 启动adapter
            await adapter.start()

            # 验证启动后已创建reaction_manager
            assert hasattr(adapter, 'reaction_manager')
            assert isinstance(adapter.reaction_manager, FeishuReactionManager)
            assert adapter.reaction_manager._bot_user_id == "bot_123"

    def test_adapter_has_pending_reactions_state(self):
        """测试Adapter有pending_reactions状态管理"""
        # 创建mock依赖
        mock_claude_adapter = Mock()
        mock_session_manager = Mock()
        mock_resource_manager = Mock()
        mock_message_handler = Mock()
        mock_message_handler.bot_user_id = None
        mock_command_handler = Mock()
        mock_card_builder = Mock()

        config = {
            "app_id": "test_app",
            "app_secret": "test_secret",
            "encrypt_key": "test_key",
            "verification_token": "test_token",
            "bot_user_id": "bot_123"
        }

        # 创建adapter
        adapter = FeishuBridge(
            config=config,
            claude_adapter=mock_claude_adapter,
            session_manager=mock_session_manager,
            resource_manager=mock_resource_manager,
            message_handler=mock_message_handler,
            command_handler=mock_command_handler,
            card_builder=mock_card_builder
        )

        # Mock WebSocket客户端创建并启动
        with patch('lark_oapi.ws.Client'):
            import asyncio
            asyncio.run(adapter.start())

        # 验证状态字典存在
        assert hasattr(adapter, '_pending_reactions')
        assert isinstance(adapter._pending_reactions, dict)

        # 验证可以存储和读取状态
        adapter._pending_reactions["session_123"] = {
            "user_message_id": "msg_456",
            "reaction_id": "reaction_789"
        }

        assert adapter._pending_reactions["session_123"]["user_message_id"] == "msg_456"
        assert adapter._pending_reactions["session_123"]["reaction_id"] == "reaction_789"

    @pytest.mark.asyncio
    async def test_finalize_reaction_success(self):
        """测试成功完成表情处理"""
        mock_claude_adapter = Mock()
        mock_session_manager = Mock()
        mock_resource_manager = Mock()
        mock_message_handler = Mock()
        mock_message_handler.bot_user_id = None
        mock_command_handler = Mock()
        mock_card_builder = Mock()

        config = {
            "app_id": "test_app",
            "app_secret": "test_secret",
            "encrypt_key": "test_key",
            "verification_token": "test_token",
            "bot_user_id": "bot_123"
        }

        adapter = FeishuBridge(
            config=config,
            claude_adapter=mock_claude_adapter,
            session_manager=mock_session_manager,
            resource_manager=mock_resource_manager,
            message_handler=mock_message_handler,
            command_handler=mock_command_handler,
            card_builder=mock_card_builder
        )

        # Mock WebSocket客户端创建并启动
        with patch('lark_oapi.ws.Client'):
            await adapter.start()

        # 设置状态
        adapter._pending_reactions["session_123"] = {
            "user_message_id": "msg_456",
            "reaction_id": "reaction_789"
        }

        # Mock reaction_manager
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        # 执行
        await adapter._finalize_reaction("session_123")

        # 验证
        adapter.reaction_manager.replace_with_done.assert_called_once_with("msg_456", "reaction_789")
        assert "session_123" not in adapter._pending_reactions

    @pytest.mark.asyncio
    async def test_finalize_reaction_no_state(self):
        """测试没有对应状态时不应报错"""
        mock_claude_adapter = Mock()
        mock_session_manager = Mock()
        mock_resource_manager = Mock()
        mock_message_handler = Mock()
        mock_message_handler.bot_user_id = None
        mock_command_handler = Mock()
        mock_card_builder = Mock()

        config = {
            "app_id": "test_app",
            "app_secret": "test_secret",
            "encrypt_key": "test_key",
            "verification_token": "test_token",
            "bot_user_id": "bot_123"
        }

        adapter = FeishuBridge(
            config=config,
            claude_adapter=mock_claude_adapter,
            session_manager=mock_session_manager,
            resource_manager=mock_resource_manager,
            message_handler=mock_message_handler,
            command_handler=mock_command_handler,
            card_builder=mock_card_builder
        )

        # Mock WebSocket客户端创建并启动
        with patch('lark_oapi.ws.Client'):
            await adapter.start()

        # Mock reaction_manager
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        # 执行 - 不应抛出异常
        await adapter._finalize_reaction("nonexistent_session")

        # 验证没有调用replace_with_done
        adapter.reaction_manager.replace_with_done.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_reaction_exception_handling(self):
        """测试异常时仍然清理状态"""
        mock_claude_adapter = Mock()
        mock_session_manager = Mock()
        mock_resource_manager = Mock()
        mock_message_handler = Mock()
        mock_message_handler.bot_user_id = None
        mock_command_handler = Mock()
        mock_card_builder = Mock()

        config = {
            "app_id": "test_app",
            "app_secret": "test_secret",
            "encrypt_key": "test_key",
            "verification_token": "test_token",
            "bot_user_id": "bot_123"
        }

        adapter = FeishuBridge(
            config=config,
            claude_adapter=mock_claude_adapter,
            session_manager=mock_session_manager,
            resource_manager=mock_resource_manager,
            message_handler=mock_message_handler,
            command_handler=mock_command_handler,
            card_builder=mock_card_builder
        )

        # Mock WebSocket客户端创建并启动
        with patch('lark_oapi.ws.Client'):
            await adapter.start()

        # 设置状态
        adapter._pending_reactions["session_123"] = {
            "user_message_id": "msg_456",
            "reaction_id": "reaction_789"
        }

        # Mock抛出异常
        adapter.reaction_manager.replace_with_done = AsyncMock(side_effect=Exception("API error"))

        # 执行 - 不应抛出异常
        await adapter._finalize_reaction("session_123")

        # 验证状态仍然被清理
        assert "session_123" not in adapter._pending_reactions

    @pytest.mark.asyncio
    async def test_full_message_flow_with_reactions(self):
        """测试完整的消息处理流程（包含表情）"""
        # 创建mock依赖
        mock_claude_adapter = Mock()
        mock_session_manager = Mock()
        mock_resource_manager = Mock()
        mock_message_handler = Mock()
        mock_message_handler.bot_user_id = None
        mock_command_handler = Mock()
        mock_card_builder = Mock()

        config = {
            "app_id": "test_app",
            "app_secret": "test_secret",
            "encrypt_key": "test_key",
            "verification_token": "test_token",
            "bot_user_id": "bot_123"
        }

        # 创建adapter
        adapter = FeishuBridge(
            config=config,
            claude_adapter=mock_claude_adapter,
            session_manager=mock_session_manager,
            resource_manager=mock_resource_manager,
            message_handler=mock_message_handler,
            command_handler=mock_command_handler,
            card_builder=mock_card_builder
        )

        # Mock WebSocket客户端创建并启动
        with patch('lark_oapi.ws.Client'):
            await adapter.start()

        # 准备测试消息
        from src.core.message import IMMessage, MessageType
        test_message = IMMessage(
            session_id="chat_test_123",
            message_id="user_msg_456",
            content="Hello",
            message_type=MessageType.TEXT,
            user_id="user_789",
            user_name="Test User",
            is_private_chat=False
        )

        # Mock reaction_manager
        adapter.reaction_manager.add_typing = AsyncMock(return_value="reaction_abc")
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        # Mock send_message（用于发送卡片）
        adapter.send_message = AsyncMock(return_value="card_msg_id")

        # Mock claude_adapter和session_manager
        mock_claude_session = Mock()
        mock_claude_session.session_id = "claude_session_xyz"

        adapter.session_manager.get_or_create_session = AsyncMock(return_value=mock_claude_session)

        # Mock流式响应
        async def mock_send_message(*args, **kwargs):
            from src.core.message import StreamEvent, StreamEventType
            yield StreamEvent(
                event_type=StreamEventType.TEXT_DELTA,
                content="Hi",
                metadata={}
            )
            yield StreamEvent(
                event_type=StreamEventType.END,
                content="",
                metadata={}
            )

        adapter.claude_adapter.send_message = mock_send_message
        adapter.card_builder.create_message_card = Mock(return_value="{}")
        adapter.card_builder.create_text_card = Mock(return_value="{}")
        adapter.update_message = AsyncMock(return_value=True)

        # 执行
        await adapter.route_to_claude(test_message)

        # 验证完整流程
        # 1. 添加了Typing表情
        adapter.reaction_manager.add_typing.assert_called_once_with("user_msg_456")

        # 2. 状态被保存（注意：状态在finally块中被清理，所以无法在这里验证）
        # 改为验证方法被调用过
        assert adapter.reaction_manager.add_typing.called

        # 3. 发送卡片时传入了parent_id
        adapter.send_message.assert_called()
        call_kwargs = adapter.send_message.call_args[1]
        assert call_kwargs.get("parent_id") == "user_msg_456"

        # 4. 表情被替换为Done
        adapter.reaction_manager.replace_with_done.assert_called_once_with("user_msg_456", "reaction_abc")

        # 5. 状态被清理（在finally块中执行）
        assert "chat_test_123" not in adapter._pending_reactions

        # 3. 发送卡片时传入了parent_id
        adapter.send_message.assert_called()
        call_kwargs = adapter.send_message.call_args[1]
        assert call_kwargs.get("parent_id") == "user_msg_456"

        # 4. 表情被替换为Done
        adapter.reaction_manager.replace_with_done.assert_called_once_with("user_msg_456", "reaction_abc")

        # 5. 状态被清理
        assert "chat_test_123" not in adapter._pending_reactions
