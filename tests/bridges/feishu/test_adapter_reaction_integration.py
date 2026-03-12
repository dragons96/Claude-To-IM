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
