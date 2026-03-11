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
