# tests/test_core/test_claude_adapter.py
import pytest
from abc import ABC
from src.core.claude_adapter import ClaudeAdapter, ClaudeSession
from src.core.message import StreamEvent, StreamEventType


class MockClaudeAdapter(ClaudeAdapter):
    """用于测试的 Mock 实现"""

    def __init__(self):
        self.sessions = {}

    async def create_session(self, work_directory, session_id=None):
        """创建会话"""
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())

        session = ClaudeSession(
            session_id=session_id,
            work_directory=work_directory,
            is_active=True,
            metadata={}
        )
        self.sessions[session_id] = session
        return session

    async def close_session(self, session_id):
        """关闭会话"""
        if session_id in self.sessions:
            self.sessions[session_id].is_active = False

    async def send_message(self, session_id, message, **kwargs):
        """发送消息并返回流式事件"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        # 模拟流式响应
        events = [
            StreamEvent(
                event_type=StreamEventType.TEXT_DELTA,
                content="Hello",
                metadata={"session_id": session_id}
            ),
            StreamEvent(
                event_type=StreamEventType.TEXT_DELTA,
                content=" World",
                metadata={"session_id": session_id}
            ),
            StreamEvent(
                event_type=StreamEventType.END,
                content="",
                metadata={"session_id": session_id}
            )
        ]

        for event in events:
            yield event

    async def get_session_info(self, session_id):
        """获取会话信息"""
        return self.sessions.get(session_id)

    async def list_sessions(self, **kwargs):
        """列出所有会话"""
        return list(self.sessions.values())


@pytest.mark.asyncio
async def test_create_session():
    """测试创建会话"""
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/work")

    assert session.session_id is not None
    assert session.work_directory == "/tmp/work"
    assert session.is_active is True
    assert session.metadata == {}


@pytest.mark.asyncio
async def test_create_session_with_custom_id():
    """测试使用自定义 ID 创建会话"""
    adapter = MockClaudeAdapter()
    custom_id = "custom_session_123"
    session = await adapter.create_session("/tmp/work", session_id=custom_id)

    assert session.session_id == custom_id
    assert session.work_directory == "/tmp/work"
    assert session.is_active is True


@pytest.mark.asyncio
async def test_send_message():
    """测试发送消息"""
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/work")

    events = []
    async for event in adapter.send_message(session.session_id, "Hello"):
        events.append(event)

    assert len(events) == 3
    assert events[0].event_type == StreamEventType.TEXT_DELTA
    assert events[0].content == "Hello"
    assert events[1].content == " World"
    assert events[2].event_type == StreamEventType.END


@pytest.mark.asyncio
async def test_close_session():
    """测试关闭会话"""
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/work")

    assert session.is_active is True

    await adapter.close_session(session.session_id)

    session_info = await adapter.get_session_info(session.session_id)
    assert session_info.is_active is False


@pytest.mark.asyncio
async def test_get_session_info():
    """测试获取会话信息"""
    adapter = MockClaudeAdapter()
    session = await adapter.create_session("/tmp/work", session_id="test_session")

    session_info = await adapter.get_session_info("test_session")

    assert session_info is not None
    assert session_info.session_id == "test_session"
    assert session_info.work_directory == "/tmp/work"

    # 测试不存在的会话
    nonexistent = await adapter.get_session_info("nonexistent")
    assert nonexistent is None


@pytest.mark.asyncio
async def test_list_sessions():
    """测试列出所有会话"""
    adapter = MockClaudeAdapter()

    # 创建多个会话
    session1 = await adapter.create_session("/tmp/work1", session_id="session1")
    session2 = await adapter.create_session("/tmp/work2", session_id="session2")

    sessions = await adapter.list_sessions()

    assert len(sessions) == 2
    session_ids = {s.session_id for s in sessions}
    assert session_ids == {"session1", "session2"}
