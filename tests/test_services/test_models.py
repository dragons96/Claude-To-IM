# tests/test_services/test_models.py
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.models import Base, IMSession, ClaudeSession, MessageHistory, PermissionConfig, ResourceCache

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def test_im_session_creation(in_memory_db):
    session = IMSession(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )
    in_memory_db.add(session)
    in_memory_db.commit()

    retrieved = in_memory_db.query(IMSession).filter_by(id="im_123").first()
    assert retrieved is not None
    assert retrieved.platform == "feishu"

def test_claude_session_creation(in_memory_db):
    # 先创建 IM 会话
    im_session = IMSession(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )
    in_memory_db.add(im_session)

    # 创建 Claude 会话
    claude_session = ClaudeSession(
        id="claude_123",
        im_session_id="im_123",
        session_id="claude_sdk_123",
        work_directory="/tmp/test",
        summary="Hello World"
    )
    in_memory_db.add(claude_session)
    in_memory_db.commit()

    retrieved = in_memory_db.query(ClaudeSession).filter_by(id="claude_123").first()
    assert retrieved is not None
    assert retrieved.work_directory == "/tmp/test"

def test_message_history_creation(in_memory_db):
    message = MessageHistory(
        id="msg_123",
        claude_session_id="claude_123",
        role="user",
        content="Hello"
    )
    in_memory_db.add(message)
    in_memory_db.commit()

    retrieved = in_memory_db.query(MessageHistory).filter_by(id="msg_123").first()
    assert retrieved.content == "Hello"

def test_permission_config_creation(in_memory_db):
    config = PermissionConfig(
        id="perm_123",
        path="D:/Codes"
    )
    in_memory_db.add(config)
    in_memory_db.commit()

    retrieved = in_memory_db.query(PermissionConfig).filter_by(id="perm_123").first()
    assert retrieved.path == "D:/Codes"

def test_resource_cache_creation(in_memory_db):
    cache = ResourceCache(
        id="cache_123",
        resource_key="file_key_123",
        local_path="/tmp/file.png",
        mime_type="image/png",
        size=1024
    )
    in_memory_db.add(cache)
    in_memory_db.commit()

    retrieved = in_memory_db.query(ResourceCache).filter_by(id="cache_123").first()
    assert retrieved.local_path == "/tmp/file.png"
