"""
FeishuBridge表情管理集成测试
"""

import pytest
from unittest.mock import Mock, patch
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
