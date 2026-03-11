# tests/test_bridges/test_feishu/test_adapter.py
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

from src.bridges.feishu.adapter import FeishuBridge
from src.core.message import IMMessage, MessageType, StreamEvent, StreamEventType
from src.core.exceptions import SessionNotFoundError


@pytest.fixture
def mock_config():
    """Mock 配置"""
    config = {
        "app_id": "test_app_id",
        "app_secret": "test_app_secret",
        "encrypt_key": "test_encrypt_key",
        "verification_token": "test_token",
        "bot_user_id": "bot_123",
    }
    return config


@pytest.fixture
def mock_claude_adapter():
    """Mock Claude 适配器"""
    adapter = Mock()
    adapter.create_session = AsyncMock()
    adapter.send_message = AsyncMock()
    adapter.get_session_info = AsyncMock()

    # Mock session
    mock_session = Mock()
    mock_session.session_id = "claude_sdk_session"
    mock_session.work_directory = "/tmp/test_session"
    mock_session.is_active = True
    adapter.create_session.return_value = mock_session
    adapter.get_session_info.return_value = mock_session

    return adapter


@pytest.fixture
def mock_session_manager():
    """Mock 会话管理器"""
    manager = Mock()
    manager.get_or_create_session = AsyncMock()
    manager.create_session = AsyncMock()
    manager.list_sessions = AsyncMock()
    manager.switch_session = AsyncMock()

    # Mock session
    mock_session = Mock()
    mock_session.session_id = "claude_sdk_session"
    mock_session.work_directory = "/tmp/test_session"
    manager.get_or_create_session.return_value = mock_session

    return manager


@pytest.fixture
def mock_resource_manager():
    """Mock 资源管理器"""
    manager = Mock()
    manager.download_resource = AsyncMock()
    manager.save_resource = AsyncMock()
    manager.download_resource.return_value = b"test content"
    manager.save_resource.return_value = "/tmp/saved_file.txt"
    return manager


@pytest.fixture
def mock_message_handler():
    """Mock 消息处理器"""
    handler = Mock()
    handler.parse_message_event = Mock()

    # 创建示例消息
    sample_message = IMMessage(
        content="Hello Claude",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=True,
    )
    handler.parse_message_event.return_value = sample_message
    return handler


@pytest.fixture
def mock_command_handler():
    """Mock 命令处理器"""
    handler = Mock()
    handler.handle = AsyncMock()
    return handler


@pytest.fixture
def mock_card_builder():
    """Mock 卡片构建器"""
    builder = Mock()
    builder.create_message_card = Mock(return_value={"elements": []})
    builder.create_tool_call_card = Mock(return_value={"elements": []})
    return builder


@pytest.fixture
def feishu_bridge(
    mock_config,
    mock_claude_adapter,
    mock_session_manager,
    mock_resource_manager,
    mock_message_handler,
    mock_command_handler,
    mock_card_builder,
):
    """创建 FeishuBridge 实例"""
    return FeishuBridge(
        config=mock_config,
        claude_adapter=mock_claude_adapter,
        session_manager=mock_session_manager,
        resource_manager=mock_resource_manager,
        message_handler=mock_message_handler,
        command_handler=mock_command_handler,
        card_builder=mock_card_builder,
    )


@pytest.mark.asyncio
async def test_start(feishu_bridge):
    """测试启动桥接器"""
    # Mock lark client
    mock_client_builder = MagicMock()
    mock_client = MagicMock()
    mock_client_builder.builder.return_value = mock_client_builder
    mock_client_builder.app_id.return_value = mock_client_builder
    mock_client_builder.app_secret.return_value = mock_client_builder
    mock_client_builder.build.return_value = mock_client
    mock_client.event.dispatcher.register_handler = MagicMock()

    with patch("src.bridges.feishu.adapter.Client.builder", return_value=mock_client_builder):
        # 启动
        await feishu_bridge.start()

        # 验证客户端创建和事件处理器注册
        assert feishu_bridge._client is not None
        assert feishu_bridge._running is True


@pytest.mark.asyncio
async def test_stop(feishu_bridge):
    """测试停止桥接器"""
    # Mock lark client
    mock_client = MagicMock()
    feishu_bridge._client = mock_client
    feishu_bridge._running = True

    # 停止
    await feishu_bridge.stop()

    # 验证
    assert feishu_bridge._running is False


@pytest.mark.asyncio
async def test_send_message_text(feishu_bridge):
    """测试发送文本消息"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_123"
    mock_client.im.v1.message.create = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 发送消息
    message_id = await feishu_bridge.send_message(
        session_id="chat_123",
        content="Hello World",
        message_type=MessageType.TEXT,
        receive_id_type="chat_id",
    )

    # 验证
    assert message_id == "sent_msg_123"
    assert mock_client.im.v1.message.create.called


@pytest.mark.asyncio
async def test_send_message_image(feishu_bridge):
    """测试发送图片消息"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_456"
    mock_client.im.v1.message.create = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 发送图片消息
    message_id = await feishu_bridge.send_message(
        session_id="chat_123",
        content="img_v2_123",
        message_type=MessageType.IMAGE,
        receive_id_type="chat_id",
    )

    # 验证
    assert message_id == "sent_msg_456"
    assert mock_client.im.v1.message.create.called


@pytest.mark.asyncio
async def test_update_message(feishu_bridge):
    """测试更新消息"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_client.im.v1.message.patch = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 更新消息
    result = await feishu_bridge.update_message(
        message_id="msg_123", new_content="Updated content"
    )

    # 验证
    assert result is True
    assert mock_client.im.v1.message.patch.called


@pytest.mark.asyncio
async def test_update_message_failure(feishu_bridge):
    """测试更新消息失败"""
    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 1  # Error code
    mock_response.msg = "Update failed"
    mock_client.im.v1.message.patch = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 更新消息
    result = await feishu_bridge.update_message(
        message_id="msg_123", new_content="Updated content"
    )

    # 验证
    assert result is False


@pytest.mark.asyncio
async def test_download_resource(feishu_bridge, mock_resource_manager):
    """测试下载资源"""
    # 下载资源
    content = await feishu_bridge.download_resource(url="https://example.com/file.pdf")

    # 验证
    assert content == b"test content"
    mock_resource_manager.download_resource.assert_called_once()


@pytest.mark.asyncio
async def test_should_respond_private_chat(feishu_bridge):
    """测试私聊消息应该响应"""
    # 创建私聊消息
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=False,
    )

    # 验证
    assert feishu_bridge.should_respond(message) is True


@pytest.mark.asyncio
async def test_should_respond_group_mentioned(feishu_bridge):
    """测试群聊且被@时应该响应"""
    # 创建群聊消息（被@）
    message = IMMessage(
        content="@Bot Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=False,
        mentioned_bot=True,
    )

    # 验证
    assert feishu_bridge.should_respond(message) is True


@pytest.mark.asyncio
async def test_should_not_respond_group_not_mentioned(feishu_bridge):
    """测试群聊未被@时不应该响应"""
    # 创建群聊消息（未被@）
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=False,
        mentioned_bot=False,
    )

    # 验证
    assert feishu_bridge.should_respond(message) is False


@pytest.mark.asyncio
async def test_format_quoted_message(feishu_bridge):
    """测试格式化引用消息"""
    # 创建被引用的消息
    quoted_message = IMMessage(
        content="Original message",
        message_type=MessageType.TEXT,
        message_id="msg_original",
        session_id="chat_123",
        user_id="user_original",
        user_name="Original User",
        is_private_chat=True,
        mentioned_bot=False,
    )

    # 格式化
    formatted = feishu_bridge.format_quoted_message(quoted_message)

    # 验证
    assert "> Original message" in formatted


@pytest.mark.asyncio
async def test_handle_message_receive_command(
    feishu_bridge, mock_command_handler, mock_message_handler
):
    """测试处理接收到的命令消息"""
    # Mock command handler
    mock_command_handler.handle.return_value = "Command executed"

    # 创建命令消息
    message = IMMessage(
        content="/sessions",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=True,
    )
    mock_message_handler.parse_message_event.return_value = message

    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_123"
    mock_client.im.v1.message.create = MagicMock(return_value=mock_response)
    feishu_bridge._client = mock_client

    # 创建事件数据
    event_data = {
        "header": {"event_id": "event_123", "event_type": "im.message.receive_v1"},
        "event": {
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_123",
                "chat_id": "chat_123",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text": "/sessions"}',
            },
        },
    }

    # 处理事件
    await feishu_bridge._handle_message_receive(event_data)

    # 验证命令被处理
    mock_command_handler.handle.assert_called_once_with(message)
    # 验证响应被发送
    assert mock_client.im.v1.message.create.called


@pytest.mark.asyncio
async def test_handle_message_receive_normal(
    feishu_bridge, mock_session_manager, mock_claude_adapter, mock_message_handler, mock_command_handler
):
    """测试处理接收到的普通消息"""
    # 创建普通消息
    message = IMMessage(
        content="Hello Claude",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=True,
    )
    mock_message_handler.parse_message_event.return_value = message

    # Mock command handler 返回 None (不是命令)
    mock_command_handler.handle.return_value = None

    # Mock Claude 响应流
    async def mock_stream():
        yield StreamEvent(
            event_type=StreamEventType.TEXT_DELTA, content="Hello", metadata={}
        )
        yield StreamEvent(
            event_type=StreamEventType.TEXT_DELTA, content=" User!", metadata={}
        )
        yield StreamEvent(event_type=StreamEventType.END, content="", metadata={})

    # 创建一个可调用的Mock，返回异步生成器
    send_mock = Mock()
    send_mock.return_value = mock_stream()
    mock_claude_adapter.send_message = send_mock

    # Mock lark client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.code = 0
    mock_response.data.message_id = "sent_msg_123"
    mock_client.im.v1.message.create = MagicMock(return_value=mock_response)
    mock_patch_response = MagicMock()
    mock_patch_response.code = 0
    mock_client.im.v1.message.patch = MagicMock(return_value=mock_patch_response)
    feishu_bridge._client = mock_client

    # 创建事件数据
    event_data = {
        "header": {"event_id": "event_123", "event_type": "im.message.receive_v1"},
        "event": {
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

    # 处理事件
    await feishu_bridge._handle_message_receive(event_data)

    # 验证会话被获取
    mock_session_manager.get_or_create_session.assert_called_once_with(
        platform="feishu", platform_session_id="chat_123"
    )

    # 验证消息被发送到 Claude
    assert send_mock.called

    # 验证响应被发送
    assert mock_client.im.v1.message.create.called
    assert mock_client.im.v1.message.patch.called


@pytest.mark.asyncio
async def test_handle_message_receive_not_respond(
    feishu_bridge, mock_message_handler
):
    """测试处理不应该响应的消息"""
    # 创建群聊未@消息
    message = IMMessage(
        content="Hello",
        message_type=MessageType.TEXT,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=False,
        mentioned_bot=False,
    )
    mock_message_handler.parse_message_event.return_value = message

    # Mock lark client
    mock_client = MagicMock()
    feishu_bridge._client = mock_client

    # 创建事件数据
    event_data = {
        "header": {"event_id": "event_123", "event_type": "im.message.receive_v1"},
        "event": {
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_123",
                "chat_id": "chat_123",
                "chat_type": "group",
                "message_type": "text",
                "content": '{"text": "Hello"}',
            },
        },
    }

    # 处理事件
    await feishu_bridge._handle_message_receive(event_data)

    # 验证没有发送消息
    assert not mock_client.im.v1.message.create.called


@pytest.mark.asyncio
async def test_handle_message_with_attachments(
    feishu_bridge, mock_session_manager, mock_claude_adapter, mock_message_handler, mock_command_handler
):
    """测试处理带附件的消息"""
    # 创建带附件的消息
    message = IMMessage(
        content="[图片]",
        message_type=MessageType.IMAGE,
        message_id="msg_123",
        session_id="chat_123",
        user_id="user_123",
        user_name="Test User",
        is_private_chat=True,
        mentioned_bot=True,
        attachments=[{"type": "image", "image_key": "img_v2_123"}],
    )
    mock_message_handler.parse_message_event.return_value = message

    # Mock command handler 返回 None (不是命令)
    mock_command_handler.handle.return_value = None

    # Mock Claude 响应流
    async def mock_stream():
        yield StreamEvent(event_type=StreamEventType.END, content="", metadata={})

    # 直接返回异步生成器
    mock_claude_adapter.send_message = lambda session_id, message, **kwargs: mock_stream()

    # Mock lark client
    mock_client = MagicMock()
    mock_client.im.v1.message.create = MagicMock()
    mock_client.im.v1.message.patch = MagicMock()
    feishu_bridge._client = mock_client

    # 创建事件数据
    event_data = {
        "header": {"event_id": "event_123", "event_type": "im.message.receive_v1"},
        "event": {
            "sender": {
                "sender_id": {"user_id": "user_123"},
                "name": "Test User",
            },
            "message": {
                "message_id": "msg_123",
                "chat_id": "chat_123",
                "chat_type": "p2p",
                "message_type": "image",
                "content": '{"image_key": "img_v2_123"}',
            },
        },
    }

    # 处理事件
    await feishu_bridge._handle_message_receive(event_data)

    # 验证会话被获取
    assert mock_session_manager.get_or_create_session.called
