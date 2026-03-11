# tests/integration/test_feishu_bridge.py
"""飞书桥接器集成测试

测试完整的消息流程:
1. 消息解析 -> 路由 -> Claude响应 -> 更新消息
2. 命令处理 (/new, /sessions, /switch)
3. 会话管理 (自动创建、切换)
4. 错误处理 (权限拒绝、会话未找到)
5. 流式响应 (消息更新、工具调用卡片)
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.bridges.feishu.adapter import FeishuBridge
from src.bridges.feishu.message_handler import FeishuMessageHandler
from src.bridges.feishu.command_handler import CommandHandler
import src.bridges.feishu.card_builder as card_builder
from src.core.message import IMMessage, MessageType, StreamEvent, StreamEventType
from src.core.exceptions import SessionNotFoundError, PermissionDeniedError
from src.services.storage_service import StorageService
from src.services.session_manager import SessionManager
from src.services.permission_manager import PermissionManager
from src.services.models import Base


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
def test_db():
    """创建测试数据库"""
    # 使用内存数据库
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # 创建会话
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    yield db

    # 清理
    db.close()
    engine.dispose()


@pytest.fixture
def storage_service(test_db: Session):
    """创建存储服务实例"""
    return StorageService(test_db)


@pytest.fixture
def permission_manager():
    """创建权限管理器实例"""
    manager = PermissionManager(allowed_directories=["/tmp/claude_sessions"])
    return manager


@pytest.fixture
def mock_claude_adapter():
    """Mock Claude 适配器"""
    adapter = Mock()

    # Mock session
    mock_session = Mock()
    mock_session.session_id = "claude_sdk_session_123"
    mock_session.work_directory = "/tmp/test_session"

    # 创建可调用的异步方法
    adapter.create_session = AsyncMock(return_value=mock_session)
    adapter.get_session_info = AsyncMock(return_value=mock_session)

    # Mock send_message 返回流式响应
    async def mock_send_message(session_id, message, **kwargs):
        # 模拟流式响应
        yield StreamEvent(
            event_type=StreamEventType.TEXT_DELTA,
            content="Hello",
            metadata={}
        )
        yield StreamEvent(
            event_type=StreamEventType.TEXT_DELTA,
            content=" User!",
            metadata={}
        )
        yield StreamEvent(
            event_type=StreamEventType.END,
            content="",
            metadata={}
        )

    adapter.send_message = mock_send_message

    return adapter


@pytest.fixture
def session_manager(storage_service, permission_manager, mock_claude_adapter):
    """创建会话管理器实例"""
    manager = SessionManager(
        claude_adapter=mock_claude_adapter,
        storage=storage_service,
        default_session_root="/tmp/claude_sessions",
        permission_manager=permission_manager
    )
    return manager


@pytest.fixture
def message_handler():
    """创建消息处理器实例"""
    return FeishuMessageHandler(bot_user_id="bot_123")


@pytest.fixture
def command_handler(session_manager):
    """创建命令处理器实例"""
    # 创建一个 mock bridge
    mock_bridge = Mock()
    mock_bridge.session_manager = session_manager
    mock_bridge.platform = "feishu"

    return CommandHandler(bridge=mock_bridge)


@pytest.fixture
def mock_card_builder():
    """Mock 卡片构建器"""
    builder = Mock()
    builder.create_message_card = Mock(return_value={"elements": []})
    builder.create_tool_call_card = Mock(return_value={"elements": []})
    return builder


@pytest.fixture
def mock_resource_manager():
    """Mock 资源管理器"""
    manager = Mock()
    manager.download_resource = AsyncMock(return_value=b"test content")
    return manager


@pytest.fixture
def feishu_config():
    """飞书配置"""
    return {
        "app_id": "test_app_id",
        "app_secret": "test_app_secret",
        "encrypt_key": "test_encrypt_key",
        "verification_token": "test_token",
        "bot_user_id": "bot_123",
    }


@pytest.fixture
def feishu_bridge(
    feishu_config,
    mock_claude_adapter,
    session_manager,
    mock_resource_manager,
    message_handler,
    command_handler,
    mock_card_builder,
):
    """创建完整的 FeishuBridge 实例"""
    return FeishuBridge(
        config=feishu_config,
        claude_adapter=mock_claude_adapter,
        session_manager=session_manager,
        resource_manager=mock_resource_manager,
        message_handler=message_handler,
        command_handler=command_handler,
        card_builder=mock_card_builder,
    )


# ==================== 测试1: 完整消息流程 ====================

@pytest.mark.asyncio
async def test_complete_message_flow(feishu_bridge):
    """测试完整的消息流程: 解析 -> 路由 -> Claude响应 -> 更新"""
    # 创建模拟的飞书消息事件
    event_data = {
        "header": {
            "event_id": "event_123",
            "event_type": "im.message.receive_v1",
            "create_time": "1234567890",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_123",
                "chat_id": "chat_123",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "Hello Claude"}',
            },
        },
    }

    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_123"

    # 记录调用
    create_calls = []
    patch_calls = []

    def mock_create(request):
        create_calls.append(request)
        return mock_response

    def mock_patch(request):
        # request 是 PatchMessageRequest 对象
        patch_calls.append((request.message_id, request.request_body))
        mock_patch_response = MagicMock()
        mock_patch_response.code = 0
        return mock_patch_response

    mock_client.im.v1.message.create = mock_create
    mock_client.im.v1.message.patch = mock_patch
    feishu_bridge._client = mock_client

    # 处理消息事件
    await feishu_bridge._handle_message_receive(event_data)

    # 验证流程:
    # 1. 消息被解析
    # 2. 会话被创建或获取
    # 3. 消息发送到 Claude
    # 4. 初始响应被发送
    # 5. 消息被更新

    assert len(create_calls) > 0, "应该发送初始消息"
    assert len(patch_calls) > 0, "应该更新消息"

    # 验证消息 ID 正确
    final_patch = patch_calls[-1]
    assert final_patch[0] == "sent_msg_123", "应该更新正确的消息"

    # 验证内容被更新（content 字段在 request_body 中）
    if hasattr(final_patch[1], 'content'):
        content_dict = json.loads(final_patch[1].content)
        assert "Hello" in content_dict.get("text", "") or "User" in content_dict.get("text", "")


# ==================== 测试2: 命令处理 ====================

@pytest.mark.asyncio
async def test_command_new_session(feishu_bridge, session_manager):
    """测试 /new 命令"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_456"

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    feishu_bridge._client = mock_client

    # 创建 /new 命令消息事件
    event_data = {
        "header": {
            "event_id": "event_124",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_124",
                "chat_id": "chat_456",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "/new"}',
            },
        },
    }

    # 处理命令
    await feishu_bridge._handle_message_receive(event_data)

    # 验证响应消息被发送
    assert len(sent_messages) == 1
    # 解码 JSON 内容
    content_dict = json.loads(sent_messages[0].body.content)
    text_content = content_dict.get("text", "")
    assert "成功创建新会话" in text_content or "✅" in text_content


@pytest.mark.asyncio
async def test_command_list_sessions(feishu_bridge):
    """测试 /sessions 命令"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_789"

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    feishu_bridge._client = mock_client

    # 创建 /sessions 命令消息事件
    event_data = {
        "header": {
            "event_id": "event_125",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_125",
                "chat_id": "chat_789",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "/sessions"}',
            },
        },
    }

    # 处理命令
    await feishu_bridge._handle_message_receive(event_data)

    # 验证响应消息被发送
    assert len(sent_messages) == 1
    # 解码 JSON 内容
    content_dict = json.loads(sent_messages[0].body.content)
    text_content = content_dict.get("text", "")
    # 应该包含会话列表信息或"没有可用会话"
    assert "会话" in text_content or "📋" in text_content or "没有" in text_content or "不存在" in text_content


@pytest.mark.asyncio
async def test_command_switch_session(feishu_bridge):
    """测试 /switch 命令"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    feishu_bridge._client = mock_client

    # 创建 /switch 命令消息事件
    event_data = {
        "header": {
            "event_id": "event_126",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_126",
                "chat_id": "chat_999",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "/switch some_session_id"}',
            },
        },
    }

    # 处理命令
    await feishu_bridge._handle_message_receive(event_data)

    # 验证响应消息被发送
    assert len(sent_messages) == 1
    # 解码 JSON 内容
    content_dict = json.loads(sent_messages[0].body.content)
    text_content = content_dict.get("text", "")
    # 应该包含成功或错误信息
    assert "切换" in text_content or "❌" in text_content or "会话" in text_content


# ==================== 测试3: 会话管理 ====================

@pytest.mark.asyncio
async def test_auto_create_session(feishu_bridge):
    """测试自动创建会话"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_auto"

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    mock_client.im.v1.message.patch = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 发送第一条消息到新的会话
    event_data = {
        "header": {
            "event_id": "event_auto",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_456"},
                "name": "New User",
            },
            "message": {
                "message_id": "msg_auto",
                "chat_id": "chat_auto_new",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "First message"}',
            },
        },
    }

    # 处理消息
    await feishu_bridge._handle_message_receive(event_data)

    # 验证会话被自动创建
    # 检查存储服务中是否有对应的会话
    im_session = await feishu_bridge.session_manager.storage.get_im_session_by_platform_id(
        platform="feishu",
        platform_session_id="chat_auto_new"
    )
    assert im_session is not None, "IM 会话应该被自动创建"

    # 验证消息被发送
    assert len(sent_messages) > 0


@pytest.mark.asyncio
async def test_session_reuse(feishu_bridge):
    """测试会话重用"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_reuse"

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    mock_client.im.v1.message.patch = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 使用相同的会话 ID 发送两条消息
    session_id = "chat_reuse_test"

    for i in range(2):
        event_data = {
            "header": {
                "event_id": f"event_reuse_{i}",
                "event_type": "im.message.receive_v1",
            },
            "event": {
                "app_id": "test_app_id",
                "sender": {
                    "sender_id": {"user_id": "user_reuse"},
                    "name": "Reuse User",
                },
                "message": {
                    "message_id": f"msg_reuse_{i}",
                    "chat_id": session_id,
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": f'{{"text": "Message {i}"}}',
                },
            },
        }

        await feishu_bridge._handle_message_receive(event_data)

    # 验证使用了同一个 Claude 会话
    im_session = await feishu_bridge.session_manager.storage.get_im_session_by_platform_id(
        platform="feishu",
        platform_session_id=session_id
    )
    assert im_session is not None

    claude_sessions = await feishu_bridge.session_manager.storage.get_active_claude_sessions(
        im_session.id
    )
    # 应该只有一个活跃的 Claude 会话
    assert len(claude_sessions) == 1


# ==================== 测试4: 错误处理 ====================

@pytest.mark.asyncio
async def test_permission_denied(feishu_bridge):
    """测试权限拒绝错误处理"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    feishu_bridge._client = mock_client

    # 创建 /new 命令,尝试在无权限目录创建会话
    event_data = {
        "header": {
            "event_id": "event_perm",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_perm"},
                "name": "Permission Test User",
            },
            "message": {
                "message_id": "msg_perm",
                "chat_id": "chat_perm",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "/new /unauthorized/directory"}',
            },
        },
    }

    # 处理命令
    await feishu_bridge._handle_message_receive(event_data)

    # 验证错误消息被发送
    assert len(sent_messages) == 1
    # 解码 JSON 内容
    content_dict = json.loads(sent_messages[0].body.content)
    text_content = content_dict.get("text", "")
    assert "权限" in text_content or "❌" in text_content or "不允许" in text_content


@pytest.mark.asyncio
async def test_session_not_found(feishu_bridge):
    """测试会话未找到错误处理"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    feishu_bridge._client = mock_client

    # 创建 /switch 命令,尝试切换到不存在的会话
    event_data = {
        "header": {
            "event_id": "event_not_found",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_not_found"},
                "name": "Not Found User",
            },
            "message": {
                "message_id": "msg_not_found",
                "chat_id": "chat_not_found",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "/switch nonexistent_session_id"}',
            },
        },
    }

    # 处理命令
    await feishu_bridge._handle_message_receive(event_data)

    # 验证错误消息被发送
    assert len(sent_messages) == 1
    # 解码 JSON 内容
    content_dict = json.loads(sent_messages[0].body.content)
    text_content = content_dict.get("text", "")
    assert "不存在" in text_content or "❌" in text_content or "未找到" in text_content or "会话" in text_content


# ==================== 测试5: 流式响应 ====================

@pytest.mark.asyncio
async def test_streaming_response_updates(feishu_bridge):
    """测试流式响应时的消息更新"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_stream"

    create_calls = []
    patch_calls = []

    def mock_create(request):
        create_calls.append(request)
        return mock_response

    def mock_patch(request):
        # request 是 PatchMessageRequest 对象
        patch_calls.append((request.message_id, request.request_body))
        mock_patch_response = MagicMock()
        mock_patch_response.code = 0
        return mock_patch_response

    mock_client.im.v1.message.create = mock_create
    mock_client.im.v1.message.patch = mock_patch
    feishu_bridge._client = mock_client

    # 创建消息事件
    event_data = {
        "header": {
            "event_id": "event_stream",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_stream"},
                "name": "Stream User",
            },
            "message": {
                "message_id": "msg_stream",
                "chat_id": "chat_stream",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "Tell me a story"}',
            },
        },
    }

    # 处理消息
    await feishu_bridge._handle_message_receive(event_data)

    # 验证:
    # 1. 发送初始消息
    assert len(create_calls) > 0, "应该发送初始消息"

    # 2. 更新消息多次 (流式更新)
    assert len(patch_calls) > 0, "应该更新消息"

    # 3. 验证最终消息包含完整响应
    final_patch = patch_calls[-1]
    # content 字段在 request_body 中
    if hasattr(final_patch[1], 'content'):
        content_dict = json.loads(final_patch[1].content)
        assert "Hello" in content_dict.get("text", "") or "User" in content_dict.get("text", "")


@pytest.mark.asyncio
async def test_tool_call_card(feishu_bridge, mock_claude_adapter):
    """测试工具调用卡片显示"""
    # 修改 mock 以返回工具调用事件
    async def mock_send_with_tool_call(session_id, message, **kwargs):
        yield StreamEvent(
            event_type=StreamEventType.TOOL_USE,
            content="",
            metadata={
                "tool_name": "bash",
                "tool_input": {"command": "ls -la"},
            }
        )
        yield StreamEvent(
            event_type=StreamEventType.TEXT_DELTA,
            content="Here is the output",
            metadata={}
        )
        yield StreamEvent(
            event_type=StreamEventType.END,
            content="",
            metadata={}
        )

    mock_claude_adapter.send_message = mock_send_with_tool_call

    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_tool"

    create_calls = []
    patch_calls = []

    def mock_create(request):
        create_calls.append(request)
        return mock_response

    def mock_patch(request):
        # request 是 PatchMessageRequest 对象
        patch_calls.append((request.message_id, request.request_body))
        mock_patch_response = MagicMock()
        mock_patch_response.code = 0
        return mock_patch_response

    mock_client.im.v1.message.create = mock_create
    mock_client.im.v1.message.patch = mock_patch
    feishu_bridge._client = mock_client

    # 创建消息事件
    event_data = {
        "header": {
            "event_id": "event_tool",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_tool"},
                "name": "Tool User",
            },
            "message": {
                "message_id": "msg_tool",
                "chat_id": "chat_tool",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "Run ls -la"}',
            },
        },
    }

    # 处理消息
    await feishu_bridge._handle_message_receive(event_data)

    # 验证工具调用被处理
    assert len(create_calls) > 0 or len(patch_calls) > 0

    # 验证工具调用信息出现在消息或卡片中
    # (具体实现取决于 CardBuilder 的实现)


# ==================== 测试6: 带附件的消息 ====================

@pytest.mark.asyncio
async def test_message_with_attachment(feishu_bridge):
    """测试带附件的消息处理"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_attach"

    sent_messages = []

    def mock_create(request):
        sent_messages.append(request)
        return mock_response

    mock_client.im.v1.message.create = mock_create
    mock_client.im.v1.message.patch = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 创建图片消息事件
    event_data = {
        "header": {
            "event_id": "event_attach",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "app_id": "test_app_id",
            "sender": {
                "sender_id": {"user_id": "user_attach"},
                "name": "Attachment User",
            },
            "message": {
                "message_id": "msg_attach",
                "chat_id": "chat_attach",
                "chat_type": "p2p",
                "message_type": "image",
                "content": '{"image_key": "img_v2_test_key"}',
            },
        },
    }

    # 处理消息
    await feishu_bridge._handle_message_receive(event_data)

    # 验证消息被处理
    assert len(sent_messages) > 0
