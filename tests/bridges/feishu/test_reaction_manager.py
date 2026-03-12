# tests/bridges/feishu/test_reaction_manager.py

"""
FeishuReactionManager单元测试
"""

import pytest
from unittest.mock import AsyncMock, Mock
from src.bridges.feishu.reaction_manager import FeishuReactionManager


class TestFeishuReactionManager:

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        """测试成功添加表情"""
        # 准备mock
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 0
        mock_response.data = Mock()
        mock_response.data.reaction_id = "test_reaction_123"
        mock_http_client.im.v1.message_reaction.create.return_value = mock_response

        # 执行
        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_reaction("msg_456", "Typing")

        # 验证
        assert reaction_id == "test_reaction_123"
        mock_http_client.im.v1.message_reaction.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_api_error(self):
        """测试API返回错误码"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 231003  # 消息不存在
        mock_response.msg = "message not found"
        mock_http_client.im.v1.message_reaction.create.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_reaction("msg_456", "Typing")

        assert reaction_id is None

    @pytest.mark.asyncio
    async def test_add_reaction_exception(self):
        """测试网络异常"""
        mock_http_client = AsyncMock()
        mock_http_client.im.v1.message_reaction.create.side_effect = Exception("Network error")

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_reaction("msg_456", "Typing")

        assert reaction_id is None

    @pytest.mark.asyncio
    async def test_delete_reaction_success(self):
        """测试成功删除表情"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 0
        mock_http_client.im.v1.message_reaction.delete.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        success = await manager.delete_reaction("msg_456", "reaction_123")

        assert success is True
        mock_http_client.im.v1.message_reaction.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_reaction_failure(self):
        """测试删除失败"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 231003
        mock_response.msg = "reaction not found"
        mock_http_client.im.v1.message_reaction.delete.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        success = await manager.delete_reaction("msg_456", "reaction_123")

        assert success is False
