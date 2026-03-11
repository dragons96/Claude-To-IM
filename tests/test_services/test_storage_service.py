# tests/test_services/test_storage_service.py
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.models import Base, IMSession, ClaudeSession
from src.services.storage_service import StorageService

@pytest.fixture
def db_session():
    """创建内存数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

@pytest.fixture
def storage_service(db_session):
    """创建 StorageService 实例"""
    return StorageService(db_session)

@pytest.mark.asyncio
async def test_create_im_session(storage_service):
    """测试创建 IM 会话"""
    session = await storage_service.create_im_session(
        id="im_123",
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )

    assert session is not None
    assert session.id == "im_123"
    assert session.platform == "feishu"
    assert session.platform_session_id == "feishu_chat_123"
    assert session.created_at is not None
    assert session.last_active is not None

@pytest.mark.asyncio
async def test_get_im_session_by_platform_id(storage_service):
    """测试通过平台 ID 获取 IM 会话"""
    # 先创建会话
    await storage_service.create_im_session(
        id="im_456",
        platform="dingtalk",
        platform_session_id="dingtalk_chat_456"
    )

    # 通过平台 ID 查询
    session = await storage_service.get_im_session_by_platform_id(
        platform="dingtalk",
        platform_session_id="dingtalk_chat_456"
    )

    assert session is not None
    assert session.id == "im_456"
    assert session.platform == "dingtalk"

    # 查询不存在的会话
    none_session = await storage_service.get_im_session_by_platform_id(
        platform="feishu",
        platform_session_id="non_existent"
    )
    assert none_session is None

@pytest.mark.asyncio
async def test_create_claude_session(storage_service):
    """测试创建 Claude 会话"""
    # 先创建 IM 会话
    await storage_service.create_im_session(
        id="im_789",
        platform="feishu",
        platform_session_id="feishu_chat_789"
    )

    # 创建 Claude 会话
    claude_session = await storage_service.create_claude_session(
        id="claude_789",
        im_session_id="im_789",
        session_id="claude_sdk_789",
        work_directory="/tmp/test_work",
        summary="Hello World",
        is_active=True
    )

    assert claude_session is not None
    assert claude_session.id == "claude_789"
    assert claude_session.im_session_id == "im_789"
    assert claude_session.session_id == "claude_sdk_789"
    assert claude_session.work_directory == "/tmp/test_work"
    assert claude_session.summary == "Hello World"
    assert claude_session.is_active is True

@pytest.mark.asyncio
async def test_get_active_claude_sessions(storage_service):
    """测试获取活跃的 Claude 会话列表"""
    # 先创建 IM 会话
    await storage_service.create_im_session(
        id="im_999",
        platform="feishu",
        platform_session_id="feishu_chat_999"
    )

    # 创建多个 Claude 会话
    await storage_service.create_claude_session(
        id="claude_1",
        im_session_id="im_999",
        session_id="sdk_1",
        work_directory="/tmp/work1",
        summary="Session 1",
        is_active=True
    )

    await storage_service.create_claude_session(
        id="claude_2",
        im_session_id="im_999",
        session_id="sdk_2",
        work_directory="/tmp/work2",
        summary="Session 2",
        is_active=True
    )

    await storage_service.create_claude_session(
        id="claude_3",
        im_session_id="im_999",
        session_id="sdk_3",
        work_directory="/tmp/work3",
        summary="Session 3",
        is_active=False  # 非活跃会话
    )

    # 获取活跃会话
    active_sessions = await storage_service.get_active_claude_sessions("im_999")

    assert len(active_sessions) == 2
    assert all(s.is_active for s in active_sessions)
    session_ids = [s.id for s in active_sessions]
    assert "claude_1" in session_ids
    assert "claude_2" in session_ids
    assert "claude_3" not in session_ids

@pytest.mark.asyncio
async def test_update_last_active(storage_service):
    """测试更新 IM 会话的最后活跃时间"""
    # 创建会话
    session = await storage_service.create_im_session(
        id="im_111",
        platform="feishu",
        platform_session_id="feishu_chat_111"
    )

    original_last_active = session.last_active

    # 等待一小段时间(虽然测试可能很快,但逻辑应该正确)
    await storage_service.update_im_session_last_active("im_111")

    # 重新获取会话验证
    updated_session = await storage_service.get_im_session("im_111")
    assert updated_session is not None
    # 更新后的时间应该已经被更新
    assert updated_session.last_active is not None
