# tests/test_core/test_message.py
import pytest
from src.core.message import IMMessage, MessageType, StreamEvent, StreamEventType

def test_im_message_creation():
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=False
    )
    assert message.content == "Hello"
    assert message.message_type == MessageType.TEXT
    assert message.is_private_chat is True
    assert message.mentioned_bot is False

def test_im_message_with_quote():
    quoted = IMMessage(
        content="Previous message",
        message_type=MessageType.TEXT,
        message_id="msg_122",
        session_id="session_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True
    )
    message = IMMessage(
        content="Reply",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="session_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        quoted_message=quoted
    )
    assert message.quoted_message is not None
    assert message.quoted_message.content == "Previous message"

def test_stream_event():
    event = StreamEvent(
        event_type=StreamEventType.TEXT_DELTA,
        content="Hello"
    )
    assert event.event_type == StreamEventType.TEXT_DELTA
    assert event.content == "Hello"
