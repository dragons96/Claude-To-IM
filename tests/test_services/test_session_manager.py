# tests/test_services/test_session_manager.py
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.services.session_manager import SessionManager
from src.core.exceptions import SessionNotFoundError, PermissionDeniedError


@pytest.fixture
def mock_claude_adapter():
    """Mock Claude Adapter"""
    adapter = Mock()
    adapter.create_session = AsyncMock()
    adapter.get_session_info = AsyncMock()
    adapter.close_session = AsyncMock()
    return adapter


@pytest.fixture
def mock_storage():
    """Mock Storage Service"""
    storage = Mock()
    storage.get_im_session_by_platform_id = AsyncMock()
    storage.create_im_session = AsyncMock()
    storage.get_active_claude_sessions = AsyncMock()
    storage.create_claude_session = AsyncMock()
    storage.get_claude_session = AsyncMock()
    storage.set_claude_session_active = AsyncMock()
    return storage


@pytest.fixture
def mock_permission_manager():
    """Mock Permission Manager"""
    manager = Mock()
    manager.is_allowed = Mock(return_value=True)
    manager.check_permission = Mock()
    return manager


@pytest.fixture
def session_manager(mock_claude_adapter, mock_storage, mock_permission_manager):
    """创建 SessionManager 实例"""
    return SessionManager(
        claude_adapter=mock_claude_adapter,
        storage=mock_storage,
        default_session_root="/tmp/claude_sessions",
        permission_manager=mock_permission_manager
    )


@pytest.mark.asyncio
async def test_get_or_create_session_auto_create(session_manager, mock_storage, mock_claude_adapter):
    """测试自动创建会话"""
    # Mock 返回 None,表示会话不存在
    mock_storage.get_im_session_by_platform_id.return_value = None
    mock_storage.create_im_session.return_value = Mock(id="im_123")

    # Mock 没有活跃会话
    mock_storage.get_active_claude_sessions.return_value = []

    # Mock 创建 Claude 会话
    mock_claude_session = Mock()
    mock_claude_session.session_id = "claude_sdk_123"
    mock_claude_session.work_directory = "/tmp/claude_sessions/default"
    mock_claude_session.is_active = True
    mock_claude_adapter.create_session.return_value = mock_claude_session

    # Mock 创建数据库 Claude 会话记录
    mock_db_claude_session = Mock()
    mock_db_claude_session.id = "claude_db_123"
    mock_db_claude_session.session_id = "claude_sdk_123"
    mock_db_claude_session.work_directory = "/tmp/claude_sessions/default"
    mock_db_claude_session.is_active = True
    mock_db_claude_session.summary = None
    mock_db_claude_session.created_at = None
    mock_storage.create_claude_session.return_value = mock_db_claude_session

    # 调用方法
    session = await session_manager.get_or_create_session(
        platform="feishu",
        platform_session_id="feishu_chat_123"
    )

    # 验证
    assert session is not None
    assert session.session_id == "claude_sdk_123"
    assert session.work_directory == "/tmp/claude_sessions/default"
    assert session.is_active is True

    # 验证调用
    mock_storage.get_im_session_by_platform_id.assert_called_once_with(
        "feishu", "feishu_chat_123"
    )
    mock_storage.create_im_session.assert_called_once()
    mock_claude_adapter.create_session.assert_called_once()
    mock_storage.create_claude_session.assert_called_once()


@pytest.mark.asyncio
async def test_create_session_with_custom_directory(session_manager, mock_storage, mock_claude_adapter, mock_permission_manager):
    """测试创建自定义目录会话"""
    # Mock IM 会话存在
    mock_im_session = Mock()
    mock_im_session.id = "im_456"
    mock_storage.get_im_session_by_platform_id.return_value = mock_im_session

    # Mock Claude 会话创建
    mock_claude_session = Mock()
    mock_claude_session.session_id = "claude_sdk_456"
    mock_claude_session.work_directory = "/custom/work/dir"
    mock_claude_session.is_active = True
    mock_claude_adapter.create_session.return_value = mock_claude_session

    # Mock 数据库会话创建
    mock_db_claude_session = Mock()
    mock_db_claude_session.id = "claude_db_456"
    mock_db_claude_session.session_id = "claude_sdk_456"
    mock_db_claude_session.work_directory = "/custom/work/dir"
    mock_db_claude_session.is_active = True
    mock_db_claude_session.summary = "TestSummary"
    mock_db_claude_session.created_at = None
    mock_storage.create_claude_session.return_value = mock_db_claude_session

    # 调用方法
    session = await session_manager.create_session(
        platform="feishu",
        platform_session_id="feishu_chat_456",
        work_directory="/custom/work/dir",
        summary="TestSummary"
    )

    # 验证权限检查
    mock_permission_manager.check_permission.assert_called_once_with("/custom/work/dir")

    # 验证会话创建
    assert session is not None
    assert session.session_id == "claude_sdk_456"
    assert session.work_directory == "/custom/work/dir"
    assert session.is_active is True


@pytest.mark.asyncio
async def test_create_session_permission_denied(session_manager, mock_permission_manager):
    """测试权限不足时拒绝创建"""
    # Mock 权限检查失败
    mock_permission_manager.check_permission.side_effect = PermissionDeniedError("没有权限访问目录")

    # 调用方法应该抛出异常
    with pytest.raises(PermissionDeniedError):
        await session_manager.create_session(
            platform="feishu",
            platform_session_id="feishu_chat_789",
            work_directory="/unauthorized/dir",
            summary="Test"
        )


@pytest.mark.asyncio
async def test_list_sessions(session_manager, mock_storage):
    """测试列出会话"""
    # Mock IM 会话存在
    mock_im_session = Mock()
    mock_im_session.id = "im_list_test"
    mock_storage.get_im_session_by_platform_id.return_value = mock_im_session

    # Mock 返回的活跃会话列表
    mock_session_1 = Mock()
    mock_session_1.id = "claude_1"
    mock_session_1.session_id = "sdk_1"
    mock_session_1.work_directory = "/work/1"
    mock_session_1.is_active = True
    mock_session_1.summary = "Summary 1"
    mock_session_1.created_at = None

    mock_session_2 = Mock()
    mock_session_2.id = "claude_2"
    mock_session_2.session_id = "sdk_2"
    mock_session_2.work_directory = "/work/2"
    mock_session_2.is_active = True
    mock_session_2.summary = "Summary 2"
    mock_session_2.created_at = None

    mock_storage.get_active_claude_sessions.return_value = [mock_session_1, mock_session_2]

    # 调用方法
    sessions = await session_manager.list_sessions(
        platform="feishu",
        platform_session_id="feishu_chat_list"
    )

    # 验证
    assert len(sessions) == 2
    assert sessions[0]["id"] == "claude_1"
    assert sessions[0]["session_id"] == "sdk_1"
    assert sessions[0]["work_directory"] == "/work/1"
    assert sessions[0]["is_active"] is True
    assert sessions[0]["summary"] == "Summary 1"

    assert sessions[1]["id"] == "claude_2"
    assert sessions[1]["session_id"] == "sdk_2"


@pytest.mark.asyncio
async def test_switch_session_success(session_manager, mock_storage):
    """测试切换会话成功"""
    # Mock IM 会话存在
    mock_im_session = Mock()
    mock_im_session.id = "im_switch_test"
    mock_storage.get_im_session_by_platform_id.return_value = mock_im_session

    # Mock 目标会话存在
    mock_target_session = Mock()
    mock_target_session.id = "claude_target"
    mock_target_session.session_id = "sdk_target"
    mock_target_session.work_directory = "/work/target"
    mock_target_session.is_active = False
    mock_target_session.summary = "Target"
    mock_target_session.created_at = None
    mock_target_session.im_session_id = "im_switch_test"  # 添加这个属性
    mock_storage.get_claude_session.return_value = mock_target_session

    # 调用方法
    result = await session_manager.switch_session(
        platform="feishu",
        platform_session_id="feishu_chat_switch",
        claude_session_id="claude_target"
    )

    # 验证
    assert result["id"] == "claude_target"
    assert result["session_id"] == "sdk_target"
    assert result["work_directory"] == "/work/target"
    assert result["is_active"] is True

    # 验证设置为活跃状态
    mock_storage.set_claude_session_active.assert_called_once_with("claude_target", True)


@pytest.mark.asyncio
async def test_switch_session_not_found(session_manager, mock_storage):
    """测试切换不存在的会话"""
    # Mock IM 会话存在
    mock_im_session = Mock()
    mock_im_session.id = "im_not_found"
    mock_storage.get_im_session_by_platform_id.return_value = mock_im_session

    # Mock 目标会话不存在
    mock_storage.get_claude_session.return_value = None

    # 调用方法应该抛出异常
    with pytest.raises(SessionNotFoundError):
        await session_manager.switch_session(
            platform="feishu",
            platform_session_id="feishu_chat_not_found",
            claude_session_id="non_existent"
        )
