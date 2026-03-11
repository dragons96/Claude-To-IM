# tests/test_bridges/test_feishu/test_message_handler.py
import pytest
from unittest.mock import Mock, patch
from src.bridges.feishu.message_handler import FeishuMessageHandler
from src.core.message import MessageType, IMMessage


class TestFeishuMessageHandler:
    """测试飞书消息处理器"""

    @pytest.fixture
    def handler(self):
        """创建消息处理器实例"""
        return FeishuMessageHandler(bot_user_id="bot_123")

    @pytest.fixture
    def text_message_event(self):
        """创建文本消息事件"""
        return {
            "header": {
                "event_id": "test_event_123",
                "event_type": "im.message.receive_v1",
                "create_time": "1234567890000",
            },
            "event": {
                "sender": {
                    "sender_id": {
                        "user_id": "user_123",
                    },
                    "sender_type": "user",
                    "name": "测试用户",
                },
                "message": {
                    "message_id": "msg_123",
                    "chat_type": "group",
                    "chat_id": "chat_123",
                    "content": '{"text":"测试消息内容"}',
                    "message_type": "text",
                    "mentions": [
                        {
                            "id": {"user_id": "bot_123"},
                            "name": "测试机器人",
                            "mention_type": "mention_user",
                        }
                    ],
                },
                "app_id": "app_123",
            },
        }

    @pytest.fixture
    def image_message_event(self):
        """创建图片消息事件"""
        return {
            "header": {
                "event_id": "test_event_456",
                "event_type": "im.message.receive_v1",
                "create_time": "1234567890000",
            },
            "event": {
                "sender": {
                    "sender_id": {"user_id": "user_456"},
                    "sender_type": "user",
                    "name": "图片用户",
                },
                "message": {
                    "message_id": "msg_456",
                    "chat_type": "p2p",
                    "chat_id": "chat_456",
                    "content": '{"image_key":"img_v2_abcd1234"}',
                    "message_type": "image",
                    "mentions": [],
                },
                "app_id": "app_123",
            },
        }

    @pytest.fixture
    def file_message_event(self):
        """创建文件消息事件"""
        return {
            "header": {
                "event_id": "test_event_789",
                "event_type": "im.message.receive_v1",
                "create_time": "1234567890000",
            },
            "event": {
                "sender": {
                    "sender_id": {"user_id": "user_789"},
                    "sender_type": "user",
                    "name": "文件用户",
                },
                "message": {
                    "message_id": "msg_789",
                    "chat_type": "group",
                    "chat_id": "chat_789",
                    "content": '{"file_key":"file_v2_xyz789","name":"test.pdf"}',
                    "message_type": "file",
                    "mentions": [],
                },
                "app_id": "app_123",
            },
        }

    @pytest.fixture
    def quoted_message_event(self):
        """创建引用回复消息事件"""
        return {
            "header": {
                "event_id": "test_event_quoted",
                "event_type": "im.message.receive_v1",
                "create_time": "1234567890000",
            },
            "event": {
                "sender": {
                    "sender_id": {"user_id": "user_quoted"},
                    "sender_type": "user",
                    "name": "引用用户",
                },
                "message": {
                    "message_id": "msg_quoted",
                    "chat_type": "group",
                    "chat_id": "chat_quoted",
                    "content": '{"text":"这是回复消息"}',
                    "message_type": "text",
                    "mentions": [],
                    "parent_id": "parent_msg_123",
                    "quotes": [
                        {
                            "quoted_message_id": "parent_msg_123",
                            "quoted_message_content": '{"text":"原始消息"}',
                        }
                    ],
                },
                "app_id": "app_123",
            },
        }

    def test_parse_text_message(self, handler, text_message_event):
        """测试解析文本消息"""
        result = handler.parse_message_event(text_message_event)

        assert isinstance(result, IMMessage)
        assert result.message_type == MessageType.TEXT
        assert result.content == "测试消息内容"
        assert result.message_id == "msg_123"
        assert result.session_id == "chat_123"
        assert result.user_id == "user_123"
        assert result.user_name == "测试用户"
        assert result.is_private_chat is False
        assert result.mentioned_bot is True

    def test_parse_image_message(self, handler, image_message_event):
        """测试解析图片消息"""
        result = handler.parse_message_event(image_message_event)

        assert isinstance(result, IMMessage)
        assert result.message_type == MessageType.IMAGE
        assert result.message_id == "msg_456"
        assert result.session_id == "chat_456"
        assert result.user_id == "user_456"
        assert result.user_name == "图片用户"
        assert result.is_private_chat is True
        assert result.mentioned_bot is False
        assert len(result.attachments) == 1
        assert result.attachments[0]["type"] == "image"
        assert result.attachments[0]["image_key"] == "img_v2_abcd1234"

    def test_parse_file_message(self, handler, file_message_event):
        """测试解析文件消息"""
        result = handler.parse_message_event(file_message_event)

        assert isinstance(result, IMMessage)
        assert result.message_type == MessageType.FILE
        assert result.message_id == "msg_789"
        assert len(result.attachments) == 1
        assert result.attachments[0]["type"] == "file"
        assert result.attachments[0]["file_key"] == "file_v2_xyz789"
        assert result.attachments[0]["name"] == "test.pdf"

    def test_parse_quoted_message(self, handler, quoted_message_event):
        """测试解析引用回复消息"""
        result = handler.parse_message_event(quoted_message_event)

        assert isinstance(result, IMMessage)
        assert result.message_type == MessageType.TEXT
        assert result.content == "这是回复消息"
        assert result.quoted_message is not None
        assert result.quoted_message.content == "原始消息"
        assert result.metadata["parent_id"] == "parent_msg_123"

    def test_extract_text_content(self, handler):
        """测试提取文本内容"""
        text_msg = {"text": "这是文本内容"}
        result = handler.extract_text_content(text_msg)
        assert result == "这是文本内容"

    def test_extract_text_content_empty(self, handler):
        """测试提取空文本内容"""
        text_msg = {}
        result = handler.extract_text_content(text_msg)
        assert result == ""

    def test_extract_attachments_from_image(self, handler):
        """测试从图片消息提取附件"""
        image_content = {"image_key": "img_v2_test123"}
        result = handler.extract_attachments("image", image_content)
        assert len(result) == 1
        assert result[0]["type"] == "image"
        assert result[0]["image_key"] == "img_v2_test123"

    def test_extract_attachments_from_file(self, handler):
        """测试从文件消息提取附件"""
        file_content = {"file_key": "file_v2_test", "name": "document.pdf"}
        result = handler.extract_attachments("file", file_content)
        assert len(result) == 1
        assert result[0]["type"] == "file"
        assert result[0]["file_key"] == "file_v2_test"
        assert result[0]["name"] == "document.pdf"

    def test_extract_attachments_no_attachments(self, handler):
        """测试没有附件的消息"""
        text_content = {"text": "纯文本消息"}
        result = handler.extract_attachments("text", text_content)
        assert len(result) == 0

    def test_is_private_chat_p2p(self, handler):
        """测试判断是否为私聊 - p2p类型"""
        message_data = {"chat_type": "p2p"}
        assert handler.is_private_chat(message_data) is True

    def test_is_private_chat_group(self, handler):
        """测试判断是否为私聊 - group类型"""
        message_data = {"chat_type": "group"}
        assert handler.is_private_chat(message_data) is False

    def test_is_bot_mentioned_with_mention(self, handler):
        """测试判断机器人是否被提及 - 有提及"""
        message_data = {
            "mentions": [
                {"id": {"user_id": "bot_123"}, "mention_type": "mention_user"}
            ]
        }
        with patch.object(handler, "_bot_user_id", "bot_123"):
            assert handler.is_bot_mentioned(message_data) is True

    def test_is_bot_mentioned_no_mentions(self, handler):
        """测试判断机器人是否被提及 - 无提及"""
        message_data = {"mentions": []}
        assert handler.is_bot_mentioned(message_data) is False

    def test_is_bot_mentioned_none_mentions(self, handler):
        """测试判断机器人是否被提及 - mentions为None"""
        message_data = {}
        assert handler.is_bot_mentioned(message_data) is False

    def test_parse_message_event_missing_fields(self, handler):
        """测试解析缺少字段的消息事件"""
        incomplete_event = {
            "header": {"event_id": "test_event", "event_type": "im.message.receive_v1"},
            "event": {
                "sender": {
                    "sender_id": {"user_id": "user_123"},
                    "sender_type": "user",
                    "name": "测试用户",
                },
                "message": {
                    "message_id": "msg_123",
                    "chat_type": "group",
                    "content": '{"text":"测试"}',
                    "message_type": "text",
                },
                "app_id": "app_123",
            },
        }
        result = handler.parse_message_event(incomplete_event)
        assert result.session_id == ""  # 缺少chat_id

    def test_extract_text_content_with_mentions(self, handler):
        """测试提取包含提及的文本内容"""
        text_msg = {"text": "@测试机器人 你好"}
        result = handler.extract_text_content(text_msg)
        assert "@测试机器人 你好" in result
