# src/bridges/feishu/adapter.py
"""飞书桥接适配器

这是核心的集成组件,连接飞书平台和Claude SDK。
"""
import logging
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    PatchMessageRequest,
    ReplyMessageRequest,
)
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger

from src.core.im_adapter import IMAdapter
from src.core.message import IMMessage, MessageType, StreamEvent, StreamEventType
from src.core.exceptions import SessionNotFoundError
from .reaction_manager import FeishuReactionManager
from .bot_info import get_bot_info


logger = logging.getLogger(__name__)


class FeishuBridge(IMAdapter):
    """飞书桥接适配器

    集成所有飞书组件,连接到Claude SDK和服务。

    功能:
    - 启动WebSocket客户端监听飞书事件
    - 解析消息并判断是否需要响应
    - 处理命令和普通消息
    - 流式发送Claude响应
    - 支持消息更新
    - 管理资源和附件
    """

    def __init__(
        self,
        config: Dict[str, Any],
        claude_adapter,
        session_manager,
        resource_manager,
        message_handler,
        command_handler,
        card_builder,
        session_root_path: Optional[str] = None,
    ):
        """初始化飞书桥接适配器

        Args:
            config: 飞书配置
                - app_id: 应用ID
                - app_secret: 应用密钥
                - encrypt_key: 加密密钥(可选)
                - verification_token: 验证令牌(可选)
                - bot_user_id: 机器人用户ID(用于检测@机器人)
            claude_adapter: Claude适配器实例
            session_manager: 会话管理器实例
            resource_manager: 资源管理器实例
            message_handler: 飞书消息处理器
            command_handler: 命令处理器
            card_builder: 卡片构建器
            session_root_path: 会话根目录路径（用于保存 bot_user_id 文件）
        """
        self.config = config
        self.claude_adapter = claude_adapter
        self.session_manager = session_manager
        self.resource_manager = resource_manager
        self.message_handler = message_handler
        self.command_handler = command_handler
        self.card_builder = card_builder

        # 会话根目录（用于保存 bot_user_id 文件）
        self.session_root_path = Path(session_root_path) if session_root_path else Path("./sessions")

        # 配置项
        self.send_tool_messages = config.get("send_tool_messages", True)

        # 保存 settings 对象用于工具权限检查
        self.settings = config.get("settings")

        # 设置机器人用户ID到消息处理器
        if "bot_user_id" in config:
            self.message_handler.set_bot_user_id(config["bot_user_id"])

        # 平台标识
        self.platform = "feishu"

        # 运行状态
        self._ws_client: Optional[lark.ws.Client] = None  # WebSocket 客户端（接收事件）
        self._http_client: Optional[lark.Client] = None   # HTTP 客户端（调用 API）
        self._running = False
        self._client_thread: Optional[threading.Thread] = None

        # 用户决策等待机制
        # 格式: {session_id: {"question_id": ..., "question": ..., "options": ..., "multi_select": bool, "message_id": ...}
        self._pending_questions: Dict[str, Dict[str, Any]] = {}

        # 表情管理器（初始化时为None，start方法中创建http_client后再初始化）
        self.reaction_manager = None

        # 状态管理 - 存储每个会话的表情信息
        # 结构: {session_id: {"user_message_id": str, "reaction_id": str}}
        self._pending_reactions: Dict[str, Dict[str, str]] = {}

    async def start(self) -> None:
        """启动适配器

        创建HTTP客户端和WebSocket客户端
        """
        try:
            # 创建 HTTP 客户端（用于调用 API）
            self._http_client = lark.Client.builder() \
                .app_id(self.config["app_id"]) \
                .app_secret(self.config["app_secret"]) \
                .build()

            # 初始化表情管理器
            self.reaction_manager = FeishuReactionManager(
                http_client=self._http_client,
                bot_user_id=self.config.get("bot_user_id")
            )

            # 获取机器人用户ID（优先级：配置 > API > 文件 > 未设置）
            bot_user_id = self.config.get("bot_user_id")
            source = None

            # 如果配置中没有，尝试通过 API 获取
            if not bot_user_id:
                logger.info("🔍 正在通过飞书 API 获取机器人信息...")
                bot_info = get_bot_info(self._http_client)
                if bot_info and bot_info.get("open_id"):
                    bot_user_id = bot_info["open_id"]
                    source = "API"
                    logger.info(f"✅ 通过 API 获取到机器人信息:")
                    logger.info(f"   - Open ID: {bot_user_id}")
                    if bot_info.get("app_name"):
                        logger.info(f"   - 应用名称: {bot_info['app_name']}")
                    if bot_info.get("activate_status"):
                        status_map = {
                            0: "初始化",
                            1: "租户停用",
                            2: "租户启用",
                            3: "安装后待启用",
                            4: "升级待启用",
                            5: "license过期停用",
                            6: "Lark套餐到期或降级停用"
                        }
                        logger.info(f"   - 激活状态: {status_map.get(bot_info['activate_status'], bot_info['activate_status'])}")

                    # 保存到文件，下次启动时可以直接使用
                    self._save_bot_user_id_to_file(bot_user_id)

            # 如果 API 获取失败，尝试从文件加载
            if not bot_user_id:
                bot_user_id = self._load_bot_user_id_from_file()
                if bot_user_id:
                    source = "文件"

            if bot_user_id:
                # 设置机器人用户ID到消息处理器（如果还没有设置）
                if not self.message_handler.bot_user_id:
                    self.message_handler.set_bot_user_id(bot_user_id)
                if not source:
                    source = "配置" if self.config.get("bot_user_id") else "文件"
                logger.info(f"✅ 使用{source}中的机器人用户ID: {bot_user_id}")
            else:
                logger.info("💡 未配置 bot_user_id")
                logger.info("   - 私聊消息会正常响应")
                logger.info("   - 群聊消息需要@机器人才会响应")
                logger.info("   - 首次收到@机器人的消息时会自动提取并保存到文件")

            # 创建事件处理器
            # 注册消息接收事件和卡片回调事件
            event_handler_builder = lark.EventDispatcherHandler.builder(
                self.config.get("encrypt_key", ""),
                self.config.get("verification_token", "")
            ).register_p2_im_message_receive_v1(
                self._handle_message_receive
            ).register_p2_card_action_trigger(
                self._handle_card_action_callback
            )

            # 尝试注册表情反应创建事件处理器（如果 SDK 支持）
            try:
                event_handler_builder = event_handler_builder.register_p2_im_message_reaction_created_v1(
                    self._handle_reaction_created
                )
                logger.info("已注册表情反应创建事件处理器")
            except AttributeError:
                # 如果 SDK 版本不支持此方法，忽略
                logger.debug("当前 SDK 版本不支持 register_p2_im_message_reaction_created_v1")

            event_handler = event_handler_builder.build()

            # 创建 WebSocket 客户端（用于接收事件）
            self._ws_client = lark.ws.Client(
                self.config["app_id"],
                self.config["app_secret"],
                event_handler=event_handler,
                log_level=lark.LogLevel.INFO
            )

            # 在单独的线程中启动 WebSocket 客户端，避免事件循环冲突
            # 设置为守护线程，这样主程序退出时线程会自动结束
            self._client_thread = threading.Thread(
                target=self._run_client,
                name="FeishuWSClient",
                daemon=True  # 关键：设置为守护线程
            )
            self._client_thread.start()

            self._running = True
            logger.info("Feishu bridge started successfully")

        except Exception as e:
            logger.error(f"Failed to start Feishu bridge: {e}")
            raise

    def _run_client(self) -> None:
        """在单独的线程中运行飞书 WebSocket 客户端"""
        try:
            self._ws_client.start()
        except Exception as e:
            logger.error(f"Feishu WebSocket client thread error: {e}")

    async def stop(self) -> None:
        """停止适配器"""
        try:
            # 标记为未运行状态
            self._running = False

            # 尝试停止 WebSocket 客户端
            if self._ws_client:
                # 方法1: 尝试调用 stop()
                if hasattr(self._ws_client, 'stop'):
                    try:
                        self._ws_client.stop()
                        logger.info("WebSocket 客户端已通过 stop() 停止")
                    except Exception as e:
                        logger.warning(f"stop() 调用失败: {e}")

                # 方法2: 尝试关闭内部连接
                if hasattr(self._ws_client, '_client') and hasattr(self._ws_client._client, 'close'):
                    try:
                        self._ws_client._client.close()
                        logger.info("WebSocket 连接已手动关闭")
                    except Exception as e:
                        logger.warning(f"手动关闭连接失败: {e}")

            # 注意：不等待线程结束，因为是守护线程
            logger.info("Feishu bridge stopped")

        except Exception as e:
            logger.error(f"Failed to stop Feishu bridge: {e}")
            # 不抛出异常，允许继续关闭其他组件

    async def send_message(
        self,
        session_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> str:
        """发送消息到飞书

        Args:
            session_id: 会话ID (chat_id)
            content: 消息内容
            message_type: 消息类型
            **kwargs: 额外参数
                - receive_id_type: 接收者ID类型 (chat_id, open_id等)
                - parent_id: 父消息ID (用于回复)

        Returns:
            str: 消息ID

        Raises:
            Exception: 发送失败时抛出
        """
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized. Call start() first.")

        try:
            receive_id_type = kwargs.get("receive_id_type", "chat_id")
            parent_id = kwargs.get("parent_id")

            # 调试日志
            if parent_id:
                logger.info(f"🔍 send_message: parent_id = {parent_id}, 类型 = {type(parent_id)}")
            else:
                logger.warning("⚠️ send_message: parent_id 未提供")

            # 构建消息体
            msg_type, msg_content = self._build_message_content(
                content, message_type
            )

            # 构建请求体
            from lark_oapi.api.im.v1 import CreateMessageRequestBody

            request_body = CreateMessageRequestBody.builder() \
                .receive_id(session_id) \
                .msg_type(msg_type) \
                .content(msg_content) \
                .build()

            # 添加parent_id (回复消息)
            if parent_id:
                request_body.parent_id = parent_id
                logger.info(f"✅ 已设置 request_body.parent_id = {parent_id}")
                # 验证设置是否成功
                if hasattr(request_body, 'parent_id'):
                    logger.info(f"✅ 验证: request_body.parent_id = {request_body.parent_id}")
                else:
                    logger.error("❌ 验证失败: request_body 没有 parent_id 属性！")

            # 创建请求
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(request_body) \
                .build()

            # 发送消息
            logger.info(f"发送请求到飞书 API: msg_type={msg_type}, parent_id={parent_id}")
            response = self._http_client.im.v1.message.create(request)

            if response.code != 0:
                raise Exception(
                    f"Failed to send message: {response.code} - {response.msg}"
                )

            return response.data.message_id

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def reply_message(
        self,
        parent_message_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        reply_in_thread: bool = False,
    ) -> str:
        """回复消息到飞书（使用专门的回复API）

        使用飞书的 ReplyMessage API，回复关系会自动建立。

        Args:
            parent_message_id: 要回复的消息ID
            content: 消息内容
            message_type: 消息类型
            reply_in_thread: 是否在话题中回复

        Returns:
            str: 新消息的ID

        Raises:
            Exception: 发送失败时抛出
        """
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized. Call start first.")

        try:
            logger.info(f"准备回复消息: parent_message_id={parent_message_id}")

            # 构建消息体
            msg_type, msg_content = self._build_message_content(
                content, message_type
            )

            # 构建请求体
            from lark_oapi.api.im.v1.model.reply_message_request_body import ReplyMessageRequestBody

            request_body = ReplyMessageRequestBody.builder() \
                .msg_type(msg_type) \
                .content(msg_content) \
                .reply_in_thread(reply_in_thread) \
                .build()

            # 创建请求
            request = ReplyMessageRequest.builder() \
                .message_id(parent_message_id) \
                .request_body(request_body) \
                .build()

            logger.info(f"发送回复请求: msg_type={msg_type}, reply_in_thread={reply_in_thread}")

            # 发送回复
            response = self._http_client.im.v1.message.reply(request)

            if response.code != 0:
                raise Exception(
                    f"Failed to reply message: {response.code} - {response.msg}"
                )

            logger.info(f"✅ 回复成功，新消息ID: {response.data.message_id}")
            return response.data.message_id

        except Exception as e:
            logger.error(f"Failed to reply message: {e}")
            raise

    async def update_message(
        self,
        message_id: str,
        new_content
    ) -> bool:
        """更新已发送的消息

        用于流式输出时更新消息内容

        注意：飞书只能更新卡片消息，不能更新文本消息

        Args:
            message_id: 消息ID
            new_content: 新内容（字符串或卡片字典）

        Returns:
            bool: 是否更新成功
        """
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized. Call start() first.")

        try:
            # 智能处理内容类型
            if isinstance(new_content, dict):
                # 已经是卡片字典，直接使用
                card = new_content
                logger.info(f"更新消息 {message_id} (卡片字典)")
            else:
                # 字符串内容，转换为卡片格式（飞书要求）
                card = self.card_builder.create_message_card(new_content)
                logger.info(f"更新消息 {message_id}, 新内容长度: {len(new_content)}")
                logger.debug(f"新内容预览: {new_content[:100]}...")

            content_json = json.dumps(card)

            # 构建请求体
            from lark_oapi.api.im.v1 import PatchMessageRequestBody

            request_body = PatchMessageRequestBody.builder() \
                .content(content_json) \
                .build()

            # 创建请求
            request = PatchMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(request_body) \
                .build()

            logger.debug(f"发送更新卡片请求...")

            # 更新消息
            response = self._http_client.im.v1.message.patch(request)

            logger.info(f"更新消息响应: code={response.code}, msg={response.msg}")

            if response.code != 0:
                logger.error(f"更新消息失败: code={response.code}, msg={response.msg}")
            else:
                logger.info("卡片更新成功")

            return response.code == 0

        except Exception as e:
            logger.error(f"Failed to update message {message_id}: {e}")
            return False

    async def download_resource(self, url: str) -> bytes:
        """下载资源文件

        Args:
            url: 资源URL

        Returns:
            bytes: 资源内容

        Raises:
            Exception: 下载失败时抛出
        """
        try:
            # 使用资源管理器下载
            resource_key = url.split("/")[-1]  # 简单提取key
            content = await self.resource_manager.download_resource(
                url=url,
                resource_key=resource_key,
                use_cache=True
            )
            return content

        except Exception as e:
            logger.error(f"Failed to download resource from {url}: {e}")
            raise

    def should_respond(self, message: IMMessage) -> bool:
        """判断是否应该响应此消息

        规则:
        - 私聊消息: 总是响应
        - 群聊消息: 只有被@时才响应

        Args:
            message: IM消息对象

        Returns:
            bool: 是否应该响应
        """
        if message.is_private_chat:
            return True

        if message.mentioned_bot:
            return True

        return False

    def format_quoted_message(self, message: IMMessage) -> str:
        """格式化引用消息

        使用Markdown格式: "> quoted\\n\\nnew"

        Args:
            message: 被引用的消息

        Returns:
            str: 格式化后的引用文本
        """
        quoted_text = message.content.strip()
        return f"> {quoted_text}\n\n"

    def _build_message_content(
        self,
        content: str,
        message_type: MessageType
    ) -> tuple:
        """构建飞书消息内容

        Args:
            content: 内容
            message_type: 消息类型

        Returns:
            tuple: (msg_type, content_json)
        """
        if message_type == MessageType.TEXT:
            msg_type = "text"
            content_json = json.dumps({"text": content})

        elif message_type == MessageType.IMAGE:
            msg_type = "image"
            content_json = json.dumps({"image_key": content})

        elif message_type == MessageType.FILE:
            msg_type = "file"
            content_json = json.dumps({"file_key": content})

        elif message_type == MessageType.CARD:
            msg_type = "interactive"
            content_json = json.dumps(content)

        else:
            # 默认为文本
            msg_type = "text"
            content_json = json.dumps({"text": str(content)})

        return msg_type, content_json

    def _get_bot_user_id_file_path(self) -> Path:
        """获取 bot_user_id 文件路径

        Returns:
            Path: robot_id.txt 文件的完整路径
        """
        return self.session_root_path / "robot_id.txt"

    def _load_bot_user_id_from_file(self) -> Optional[str]:
        """从文件加载 bot_user_id

        Returns:
            Optional[str]: bot_user_id，如果文件不存在或读取失败则返回None
        """
        try:
            file_path = self._get_bot_user_id_file_path()
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8").strip()
                if content:
                    logger.info(f"✅ 从文件加载到 bot_user_id: {content}")
                    return content
            return None
        except Exception as e:
            logger.warning(f"从文件加载 bot_user_id 失败: {e}")
            return None

    def _save_bot_user_id_to_file(self, bot_user_id: str) -> bool:
        """保存 bot_user_id 到文件

        Args:
            bot_user_id: 要保存的机器人用户ID

        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保目录存在
            file_path = self._get_bot_user_id_file_path()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            file_path.write_text(bot_user_id, encoding="utf-8")
            logger.info(f"✅ bot_user_id 已保存到文件: {file_path}")
            logger.info(f"💡 下次启动将自动加载此 ID")
            return True
        except Exception as e:
            logger.warning(f"保存 bot_user_id 到文件失败: {e}")
            return False

    def _convert_event_to_dict(self, event_data: lark.im.v1.P2ImMessageReceiveV1) -> Dict[str, Any]:
        """将 P2ImMessageReceiveV1 对象转换为字典格式

        Args:
            event_data: 飞书消息事件对象

        Returns:
            Dict[str, Any]: 字典格式的消息事件数据
        """
        # 将事件对象序列化为 JSON，然后再反序列化为字典
        # 这样可以保持 message_handler.parse_message_event 的接口不变
        event_json = lark.JSON.marshal(event_data)
        event_dict = json.loads(event_json)
        return event_dict

    def _extract_bot_user_id(self, event_dict: Dict[str, Any], message: IMMessage) -> Optional[str]:
        """从消息事件中提取机器人用户ID

        当机器人在群聊中被@时，mentions 列表会包含机器人的信息。
        我们可以从中提取 bot_user_id。

        Args:
            event_dict: 消息事件字典
            message: 解析后的消息对象

        Returns:
            Optional[str]: 机器人用户ID，如果无法提取则返回None
        """
        try:
            # 从 mentions 中提取（群聊中@机器人时）
            if "event" in event_dict and "message" in event_dict["event"]:
                event_message = event_dict["event"]["message"]
                mentions = event_message.get("mentions", [])

                if mentions:
                    # 提取第一个被 @ 的 ID
                    # 在大多数情况下，第一个被 @ 的就是机器人
                    first_mention = mentions[0]
                    bot_id = (
                        first_mention.get("id", {}).get("user_id") or
                        first_mention.get("id", {}).get("open_id")
                    )
                    if bot_id:
                        logger.info(f"✅ 从消息 mentions 中提取到 bot_user_id: {bot_id}")
                        return bot_id

            logger.debug("当前消息无法提取 bot_user_id（需要有人在群聊中@机器人）")
            return None

        except Exception as e:
            logger.warning(f"提取 bot_user_id 时出错: {e}")
            return None

    def _handle_message_receive(self, event_data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """处理消息接收事件

        这是飞书事件的主要入口点（同步回调函数）

        Args:
            event_data: 飞书消息事件数据 (P2ImMessageReceiveV1)
        """
        # 从 WebSocket 线程中安全地调度异步任务到主事件循环
        import asyncio
        try:
            logger.info("收到飞书消息事件（WebSocket 回调）")
            logger.debug(f"事件类型: {type(event_data).__name__}")

            # 获取主事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.error("没有找到运行中的事件循环")
                return

            logger.info("准备调度异步任务...")

            # 使用 call_soon_threadsafe 从其他线程安全地调度协程
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._handle_message_receive_async(event_data))
            )

            logger.info("消息事件已调度到异步处理队列")

        except Exception as e:
            logger.error(f"调度消息处理失败: {e}", exc_info=True)

    def _handle_reaction_created(self, event_data) -> None:
        """处理表情反应创建事件

        这是一个空处理器，用于避免飞书 SDK 报错 "processor not found"。
        我们不需要处理表情反应创建事件，因为我们只是添加表情，不需要响应。

        Args:
            event_data: 飞书表情反应事件数据
        """
        try:
            logger.debug(
                "收到表情反应创建事件（已忽略）",
                event_type=getattr(event_data, 'type', 'unknown'),
                message_id=getattr(event_data, 'message_id', 'unknown')
            )
            # 不需要做任何处理，只是避免 SDK 报错
        except Exception as e:
            logger.debug(f"处理表情反应事件时出错（已忽略）: {e}")

    def _handle_card_action_callback(self, event_data: P2CardActionTrigger):
        """处理卡片按钮回调（长连接方式）

        这是飞书卡片按钮的回调处理函数（同步函数，需要立即返回响应）

        Args:
            event_data: 飞书卡片动作事件数据 (P2CardActionTrigger)

        Returns:
            P2CardActionTriggerResponse: 回调响应
        """
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
        from lark_oapi.event.callback.model.p2_card_action_trigger import CallBackToast

        try:
            logger.info("=" * 60)
            logger.info("收到飞书卡片按钮回调（长连接）")

            # 提取回调数据
            if not event_data or not event_data.event:
                logger.warning("卡片回调数据为空")
                return P2CardActionTriggerResponse()

            action = event_data.event.action
            operator = event_data.event.operator
            context = event_data.event.context

            # 获取会话信息
            chat_id = context.open_chat_id if context else ""
            user_id = operator.user_id if operator else ""

            logger.info(f"卡片回调 - chat_id: {chat_id}, user_id: {user_id}")
            logger.debug(f"Action数据: {action}")

            # 解析按钮值
            action_value = action.value if action and action.value else {}
            if not action_value:
                logger.warning("按钮值为空")
                # 返回空响应
                return P2CardActionTriggerResponse()

            try:
                # 按钮值是 JSON 字符串
                if isinstance(action_value, str):
                    value_data = json.loads(action_value)
                else:
                    value_data = action_value

                logger.info(f"按钮数据: {value_data}")
            except json.JSONDecodeError:
                logger.error(f"无法解析按钮值: {action_value}")
                # 返回错误提示
                toast = CallBackToast()
                toast.type = "error"
                toast.content = "无法识别您的选择"

                response = P2CardActionTriggerResponse()
                response.toast = toast
                return response

            # 检查是否是用户选择动作
            if value_data.get("action") == "user_choice":
                question_id = value_data.get("question_id")
                option_index = value_data.get("option_index")
                option_value = value_data.get("option_value")
                option_label = value_data.get("option_label")

                logger.info(f"用户选择 - question_id: {question_id}, 选项: {option_label}")

                # 检查是否有待处理的问题
                if chat_id not in self._pending_questions:
                    logger.warning(f"没有找到待处理的问题: {chat_id}")
                    # 返回错误提示
                    toast = CallBackToast()
                    toast.type = "error"
                    toast.content = "此选择已过期或不存在"

                    response = P2CardActionTriggerResponse()
                    response.toast = toast
                    return response

                pending = self._pending_questions[chat_id]

                # 验证 question_id 是否匹配
                if pending["question_id"] != question_id:
                    logger.warning(f"问题ID不匹配: 期望 {pending['question_id']}, 收到 {question_id}")
                    # 返回错误提示
                    toast = CallBackToast()
                    toast.type = "error"
                    toast.content = "问题已过期"

                    response = P2CardActionTriggerResponse()
                    response.toast = toast
                    return response

                # 获取卡片消息ID
                card_message_id = pending.get("card_message_id", "")

                # 获取选中的选项
                selected_option = pending["options"][option_index]
                option_label = selected_option.get("label", "未知选项")

                # 返回成功提示
                toast = CallBackToast()
                toast.type = "success"
                toast.content = f"✅ 已选择: {option_label}"

                response = P2CardActionTriggerResponse()
                response.toast = toast

                # 异步处理用户选择，不阻塞回调响应
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    logger.warning("没有找到运行中的事件循环")
                    return response

                # 调度异步处理任务
                async def process_choice():
                    try:
                        # 先更新原卡片为选择结果（保留所有选项，移除按钮）
                        if card_message_id:
                            try:
                                result_card = self.card_builder.create_user_choice_result_card(
                                    question=pending["question"],
                                    options=pending["options"],
                                    selected_indices=[option_index]
                                )

                                # 更新原卡片
                                update_success = await self.update_message(card_message_id, result_card)
                                logger.info(f"原卡片更新结果: {'成功' if update_success else '失败'}")
                            except Exception as e:
                                logger.error(f"更新卡片失败: {e}", exc_info=True)

                        # 清除待处理问题（在继续对话之前清理）
                        if chat_id in self._pending_questions:
                            del self._pending_questions[chat_id]
                            logger.info(f"已清除待处理问题: {chat_id}")

                        # 构建回复给 Claude 的消息（符合 AskUserQuestion 的答案格式）
                        # 格式：[Answer] <问题文本>\n<选择序号>: <选项标签> - <选项描述>
                        option_desc = selected_option.get("description", "")
                        if option_desc:
                            choice_message = f"[Answer]\n{pending['question']}\n选择: {option_index + 1}. {option_label} - {option_desc}"
                        else:
                            choice_message = f"[Answer]\n{pending['question']}\n选择: {option_index + 1}. {option_label}"

                        # 创建新的消息对象
                        from src.core.message import IMMessage as Msg
                        choice_msg = Msg(
                            content=choice_message,
                            message_type=MessageType.TEXT,
                            message_id=f"card_action_{question_id}",
                            session_id=chat_id,
                            user_id=user_id,
                            user_name="用户",
                            is_private_chat=True,
                            mentioned_bot=False,
                            quoted_message=None,
                            attachments=[],
                            metadata={
                                "source": "card_action",
                                "tool_id": pending.get("tool_id"),
                                "question_id": question_id,
                                "answers": {
                                    pending["question"]: option_label
                                }
                            }
                        )

                        # 继续路由到 Claude
                        await self.route_to_claude(choice_msg)
                    except Exception as e:
                        logger.error(f"异步处理用户选择失败: {e}", exc_info=True)
                        # 出错时也清理待处理问题
                        if chat_id in self._pending_questions:
                            del self._pending_questions[chat_id]

                loop.call_soon_threadsafe(lambda: asyncio.create_task(process_choice()))

                logger.info(f"卡片回调处理完成，返回响应")
                return response

            else:
                logger.warning(f"未知的卡片动作: {value_data.get('action')}")
                # 返回未知动作提示
                toast = CallBackToast()
                toast.type = "error"
                toast.content = "未知的操作"

                response = P2CardActionTriggerResponse()
                response.toast = toast
                return response

        except Exception as e:
            logger.error(f"处理卡片回调失败: {e}", exc_info=True)
            # 返回错误提示
            from lark_oapi.event.callback.model.p2_card_action_trigger import CallBackToast, P2CardActionTriggerResponse

            toast = CallBackToast()
            toast.type = "error"
            toast.content = f"处理选择时出错: {str(e)}"

            response = P2CardActionTriggerResponse()
            response.toast = toast
            return response

    async def _handle_message_receive_async(self, event_data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """异步处理消息接收事件

        Args:
            event_data: 飞书消息事件数据 (P2ImMessageReceiveV1)
        """
        try:
            logger.info("=" * 60)
            logger.info("开始处理飞书消息事件")

            # 将 P2ImMessageReceiveV1 对象转换为字典格式
            # 这样可以保持 message_handler.parse_message_event 的接口不变
            event_dict = self._convert_event_to_dict(event_data)
            logger.debug(f"事件数据已转换为字典: {list(event_dict.keys())}")

            # 解析消息
            message = self.message_handler.parse_message_event(event_dict)
            logger.info(f"消息解析成功 - session_id: {message.session_id}, user_id: {message.user_id}")
            logger.debug(f"消息内容: {message.content[:100]}...")
            logger.debug(f"消息类型: {message.message_type}, 是否私聊: {message.is_private_chat}, 是否@机器人: {message.mentioned_bot}")

            # 自动提取 bot_user_id（如果还没有设置）
            if not self.message_handler.bot_user_id:
                bot_user_id = self._extract_bot_user_id(event_dict, message)
                if bot_user_id:
                    self.message_handler.set_bot_user_id(bot_user_id)
                    logger.info(f"✅ 成功自动提取机器人用户ID: {bot_user_id}")

                    # 保存到文件，下次启动时自动加载
                    self._save_bot_user_id_to_file(bot_user_id)

            # 判断是否应该响应
            if not self.should_respond(message):
                logger.info(f"跳过消息 - 不满足响应条件 (群聊且未@机器人)")
                return

            logger.info("消息通过响应检查，开始处理...")

            # 检查是否有待处理的用户决策问题
            if message.session_id in self._pending_questions:
                # 尝试解析用户的选择
                pending = self._pending_questions[message.session_id]
                logger.info(f"检测到待处理的用户决策问题: {pending['question_id']}")

                # 尝试解析用户输入（期望是数字或数字列表）
                try:
                    user_input = message.content.strip()

                    # 解析选择（支持单个数字或空格分隔的多个数字）
                    selections = []
                    for part in user_input.split():
                        try:
                            num = int(part)
                            if 1 <= num <= len(pending['options']):
                                selections.append(num)
                        except ValueError:
                            continue

                    if selections:
                        # 用户提供了有效的选择
                        logger.info(f"用户选择: {selections}")

                        # 保存卡片消息ID，用于更新
                        card_message_id = pending.get('card_message_id')

                        # 更新原卡片为结果卡片（保留所有选项，移除按钮）
                        if card_message_id:
                            # 使用 card_builder 创建结果卡片
                            result_card = self.card_builder.create_user_choice_result_card(
                                question=pending['question'],
                                options=pending['options'],
                                selected_indices=[s - 1 for s in selections]  # 转换为0-based索引
                            )

                            # 更新原卡片
                            update_success = await self.update_message(
                                message_id=card_message_id,
                                new_content=result_card
                            )

                            if not update_success:
                                logger.warning(f"更新卡片失败，消息ID: {card_message_id}")
                        else:
                            logger.warning("未找到卡片消息ID，无法更新卡片")

                        # 清除待处理问题
                        del self._pending_questions[message.session_id]

                        # 构建回复给 Claude 的消息（符合 AskUserQuestion 的答案格式）
                        # 格式：[Answer] <问题文本>\n<选择序号>: <选项标签> - <选项描述>
                        if len(selections) == 1:
                            # 单选
                            idx = selections[0] - 1  # 转换为0-based索引
                            option = pending['options'][idx]
                            label = option.get('label', '')
                            description = option.get('description', '')
                            if description:
                                choice_message = f"[Answer]\n{pending['question']}\n选择: {selections[0]}. {label} - {description}"
                            else:
                                choice_message = f"[Answer]\n{pending['question']}\n选择: {selections[0]}. {label}"
                        else:
                            # 多选
                            choice_lines = [f"[Answer]\n{pending['question']}\n选择:"]
                            for selection in selections:
                                idx = selection - 1  # 转换为0-based索引
                                option = pending['options'][idx]
                                label = option.get('label', '')
                                description = option.get('description', '')
                                if description:
                                    choice_lines.append(f"{selection}. {label} - {description}")
                                else:
                                    choice_lines.append(f"{selection}. {label}")
                            choice_message = '\n'.join(choice_lines)

                        # 创建新的消息对象，包含用户的选择
                        from src.core.message import IMMessage as Msg

                        # 构建answers对象（单选或多选）
                        if len(selections) == 1:
                            idx = selections[0] - 1
                            answers = {
                                pending['question']: pending['options'][idx].get('label', '')
                            }
                        else:
                            # 多选：用逗号连接所有选择的标签
                            labels = [pending['options'][s - 1].get('label', '') for s in selections]
                            answers = {
                                pending['question']: ', '.join(labels)
                            }

                        # 合并metadata并添加answers
                        choice_metadata = dict(message.metadata) if message.metadata else {}
                        choice_metadata.update({
                            "source": "text_choice",
                            "tool_id": pending.get("tool_id"),
                            "question_id": pending.get("question_id"),
                            "answers": answers
                        })

                        choice_msg = Msg(
                            content=choice_message,
                            message_type=message.message_type,
                            message_id=message.message_id,
                            session_id=message.session_id,
                            user_id=message.user_id,
                            user_name=message.user_name,
                            is_private_chat=message.is_private_chat,
                            mentioned_bot=message.mentioned_bot,
                            quoted_message=message.quoted_message,
                            attachments=message.attachments,
                            metadata=choice_metadata
                        )

                        # 继续路由到 Claude
                        await self.route_to_claude(choice_msg)
                        return
                    else:
                        # 用户输入的不是数字选项，作为自定义答案处理
                        logger.info(f"用户自定义输入（非选项）: {user_input}")

                        # 保存卡片消息ID，用于更新
                        card_message_id = pending.get('card_message_id')

                        # 更新原卡片，显示用户的自定义输入
                        if card_message_id:
                            # 使用 card_builder 创建自定义答案卡片
                            custom_answer_card = self.card_builder.create_custom_answer_result_card(
                                question=pending['question'],
                                custom_answer=user_input
                            )

                            # 更新原卡片
                            update_success = await self.update_message(
                                message_id=card_message_id,
                                new_content=custom_answer_card
                            )

                            if not update_success:
                                logger.warning(f"更新卡片失败，消息ID: {card_message_id}")

                        # 清除待处理问题
                        del self._pending_questions[message.session_id]

                        # 构建回复给 Claude 的消息（自定义答案格式）
                        # 格式：[Answer] <问题文本>\n<自定义回答>
                        choice_message = f"[Answer]\n{pending['question']}\n{user_input}"

                        # 创建新的消息对象，包含用户的自定义答案
                        from src.core.message import IMMessage as Msg

                        # 构建answers对象（自定义答案）
                        answers = {
                            pending['question']: user_input
                        }

                        # 合并metadata并添加answers
                        choice_metadata = dict(message.metadata) if message.metadata else {}
                        choice_metadata.update({
                            "source": "text_custom_answer",
                            "tool_id": pending.get("tool_id"),
                            "question_id": pending.get("question_id"),
                            "answers": answers,
                            "custom_answer": True  # 标记为自定义答案
                        })

                        choice_msg = Msg(
                            content=choice_message,
                            message_type=message.message_type,
                            message_id=message.message_id,
                            session_id=message.session_id,
                            user_id=message.user_id,
                            user_name=message.user_name,
                            is_private_chat=message.is_private_chat,
                            mentioned_bot=message.mentioned_bot,
                            quoted_message=message.quoted_message,
                            attachments=message.attachments,
                            metadata=choice_metadata
                        )

                        # 继续路由到 Claude
                        await self.route_to_claude(choice_msg)
                        return

                except Exception as e:
                    logger.error(f"处理用户选择失败: {e}", exc_info=True)
                    # 清除待处理问题
                    if message.session_id in self._pending_questions:
                        del self._pending_questions[message.session_id]
                    # 继续正常流程

            # 尝试处理为命令
            command_result = await self.command_handler.handle(message)

            # 处理命令结果
            if command_result is not None:
                # 检查是否是特殊返回值（需要在指定会话中执行）
                if isinstance(command_result, dict) and command_result.get("type") == "exec_in_session":
                    # 在指定会话中执行消息
                    claude_session_id = command_result.get("claude_session_id")
                    exec_message = command_result.get("message")
                    logger.info(f"在指定会话中执行: claude_session_id={claude_session_id}, content={exec_message.content[:50]}...")
                    await self.route_to_claude_with_session(exec_message, claude_session_id)
                    return

                # 检查是否是特殊返回值（需要转发到 Claude）
                if isinstance(command_result, dict) and command_result.get("type") == "forward_to_claude":
                    # 提取转换后的消息，转发到 Claude
                    logger.info(f"命令需要转发到 Claude: {command_result['message'].content[:50]}...")
                    await self.route_to_claude(command_result["message"])
                    return

                # 如果是普通字符串，发送结果
                if command_result:
                    logger.info(f"命令处理结果: {command_result[:100]}...")
                    await self.send_message(
                        session_id=message.session_id,
                        content=command_result,
                        message_type=MessageType.TEXT,
                        receive_id_type="chat_id",
                    )
                return

            # 普通消息,转发到Claude会话
            logger.info("不是命令，转发到 Claude 会话处理...")
            await self.route_to_claude(message)

        except Exception as e:
            logger.error(f"处理消息事件失败: {e}", exc_info=True)
            # 发送错误提示
            try:
                error_card = self.card_builder.create_error_card(str(e))
                await self.send_message(
                    session_id=message.session_id,
                    content=error_card,
                    message_type=MessageType.CARD,
                    receive_id_type="chat_id",
                )
            except Exception:
                pass  # 忽略错误提示的失败

    async def route_to_claude(self, message: IMMessage) -> None:
        """路由消息到Claude会话

        获取或创建会话,发送消息,流式处理响应

        Args:
            message: IM消息对象
        """
        try:
            logger.info("开始路由到 Claude 会话...")
            logger.debug(f"平台: {self.platform}, 平台会话ID: {message.session_id}")

            # 获取或创建Claude会话
            logger.info("获取或创建 Claude 会话...")
            claude_session = await self.session_manager.get_or_create_session(
                platform=self.platform,
                platform_session_id=message.session_id
            )

            if not claude_session:
                error_msg = f"无法获取或创建会话: {message.session_id}"
                logger.error(error_msg)
                await self.send_message(
                    session_id=message.session_id,
                    content=f"❌ {error_msg}\n\n请稍后重试或使用 /new 创建新会话",
                    message_type=MessageType.TEXT,
                    receive_id_type="chat_id",
                )
                return

            logger.info(f"Claude 会话获取成功 - session_id: {claude_session.session_id}")
            logger.debug(f"工作目录: {claude_session.work_directory}")

            # 处理附件
            if message.attachments:
                logger.info(f"处理附件: {len(message.attachments)} 个")
                await self._process_attachments(
                    message.attachments,
                    claude_session.work_directory
                )

            # 构建完整消息内容 (包含引用)
            full_content = message.content
            if message.quoted_message:
                logger.info("检测到引用消息，进行格式化...")
                quoted = self.format_quoted_message(message.quoted_message)
                full_content = quoted + full_content

            logger.info(f"准备发送到 Claude，消息内容长度: {len(full_content)} 字符")

            # 发送到Claude并流式处理响应
            await self._stream_claude_response(
                session_id=message.session_id,
                claude_session_id=claude_session.session_id,
                message_content=full_content,
                user_message_id=message.message_id,  # 新增参数
            )

        except RuntimeError as e:
            # 会话创建或获取失败
            logger.error(f"会话操作失败: {e}", exc_info=True)
            await self.send_message(
                session_id=message.session_id,
                content=f"❌ 会话操作失败\n\n{str(e)}\n\n💡 提示：使用 /new 创建新会话",
                message_type=MessageType.TEXT,
                receive_id_type="chat_id",
            )
        except Exception as e:
            logger.error(f"路由消息到 Claude 失败: {e}", exc_info=True)
            # 发送友好的错误消息
            try:
                await self.send_message(
                    session_id=message.session_id,
                    content=f"❌ 处理消息时出错\n\n{str(e)}",
                    message_type=MessageType.TEXT,
                    receive_id_type="chat_id",
                )
            except Exception:
                pass  # 忽略错误消息发送失败

    async def route_to_claude_with_session(self, message: IMMessage, claude_session_id: str) -> None:
        """路由消息到指定的Claude会话

        不获取或创建会话，直接使用指定的会话ID发送消息

        Args:
            message: IM消息对象
            claude_session_id: Claude SDK session_id
        """
        try:
            logger.info(f"开始路由到指定的 Claude 会话: {claude_session_id}")
            logger.debug(f"平台: {self.platform}, 平台会话ID: {message.session_id}")

            # 获取指定会话的信息
            from src.services.models import ClaudeSession
            db_session = self.session_manager.storage.db
            session_record = db_session.query(ClaudeSession).filter_by(
                session_id=claude_session_id
            ).first()

            if not session_record:
                error_msg = f"找不到指定的会话: {claude_session_id}"
                logger.error(error_msg)
                await self.send_message(
                    session_id=message.session_id,
                    content=f"❌ {error_msg}\n\n请使用 /sessions 查看可用会话",
                    message_type=MessageType.TEXT,
                    receive_id_type="chat_id",
                )
                return

            logger.info(f"找到会话记录 - session_id: {session_record.session_id}")
            logger.debug(f"工作目录: {session_record.work_directory}")

            # 构建会话对象
            from src.core.claude_adapter import ClaudeSession
            claude_session = ClaudeSession(
                session_id=session_record.session_id,
                work_directory=session_record.work_directory
            )

            # 处理附件
            if message.attachments:
                logger.info(f"处理附件: {len(message.attachments)} 个")
                await self._process_attachments(
                    message.attachments,
                    claude_session.work_directory
                )

            # 构建完整消息内容 (包含引用)
            full_content = message.content
            if message.quoted_message:
                logger.info("检测到引用消息，进行格式化...")
                quoted = self.format_quoted_message(message.quoted_message)
                full_content = quoted + full_content

            logger.info(f"准备发送到 Claude，消息内容长度: {len(full_content)} 字符")

            # 发送到Claude并流式处理响应
            await self._stream_claude_response(
                session_id=message.session_id,
                claude_session_id=claude_session.session_id,
                message_content=full_content,
                user_message_id=message.message_id,  # 新增参数
            )

        except Exception as e:
            logger.error(f"路由消息到指定 Claude 会话失败: {e}", exc_info=True)
            # 发送友好的错误消息
            try:
                await self.send_message(
                    session_id=message.session_id,
                    content=f"❌ 处理消息时出错\n\n{str(e)}",
                    message_type=MessageType.TEXT,
                    receive_id_type="chat_id",
                )
            except Exception:
                pass  # 忽略错误消息发送失败

    async def _process_attachments(
        self,
        attachments: list,
        work_directory: str
    ) -> None:
        """处理消息附件

        下载附件并保存到工作目录

        Args:
            attachments: 附件列表
            work_directory: 工作目录
        """
        for attachment in attachments:
            try:
                # 获取附件URL (这里需要根据实际的飞书API调整)
                # 简化处理: 假设附件中有image_key或file_key
                if "image_key" in attachment:
                    # 下载图片
                    image_key = attachment["image_key"]
                    # TODO: 调用飞书API获取图片URL
                    # url = self._get_image_url(image_key)
                    # content = await self.download_resource(url)
                    # await self.resource_manager.save_resource(
                    #     content, work_directory, filename=f"{image_key}.png"
                    # )
                    pass

                elif "file_key" in attachment:
                    # 下载文件
                    file_key = attachment["file_key"]
                    # TODO: 调用飞书API获取文件URL
                    # url = self._get_file_url(file_key)
                    # content = await self.download_resource(url)
                    # await self.resource_manager.save_resource(
                    #     content,
                    #     work_directory,
                    #     filename=attachment.get("name", file_key)
                    # )
                    pass

            except Exception as e:
                logger.error(f"Failed to process attachment: {e}")
                # 继续处理其他附件

    async def _stream_claude_response(
        self,
        session_id: str,
        claude_session_id: str,
        message_content: str,
        user_message_id: str,  # 新增参数
    ) -> None:
        """流式处理Claude响应

        发送消息到Claude,流式接收响应并更新消息

        Args:
            session_id: 平台会话ID
            claude_session_id: Claude会话ID
            message_content: 消息内容
            user_message_id: 用户消息ID，用于添加表情和引用
        """
        try:
            logger.info("开始流式处理 Claude 响应...")
            logger.debug(f"Claude 会话 ID: {claude_session_id}")

            # ===== 新增：表情处理开始 =====
            # 步骤1: 添加"敲键盘"表情
            logger.info(f"准备添加敲键盘表情 - session_id: {session_id}, user_message_id: {user_message_id}")
            reaction_id = await self.reaction_manager.add_typing(user_message_id)

            # 步骤2: 存储状态
            if reaction_id:
                self._pending_reactions[session_id] = {
                    "user_message_id": user_message_id,
                    "reaction_id": reaction_id
                }
                logger.info(
                    f"已添加敲键盘表情 - session_id: {session_id}, "
                    f"user_message_id: {user_message_id}, reaction_id: {reaction_id}, "
                    f"pending_reactions_count: {len(self._pending_reactions)}"
                )
            else:
                logger.warning(
                    f"添加敲键盘表情失败，继续处理消息 - session_id: {session_id}, "
                    f"user_message_id: {user_message_id}"
                )
            # ===== 表情处理结束 =====

            # 创建初始卡片（飞书只能更新卡片消息，不能更新文本消息）
            initial_card = self.card_builder.create_message_card("思考中...")
            logger.info(f"发送初始卡片: 思考中...")
            logger.info(f"🔍 调试: user_message_id = {user_message_id}, 类型 = {type(user_message_id)}")
            logger.info(f"🔍 调试: session_id = {session_id}")
            if not user_message_id:
                logger.error("❌ user_message_id 为空，无法回复用户消息！")
                # 如果没有 user_message_id，回退到普通发送
                message_id = await self.send_message(
                    session_id=session_id,
                    content=initial_card,
                    message_type=MessageType.CARD,
                    receive_id_type="chat_id",
                )
            else:
                # 使用专门的回复API
                message_id = await self.reply_message(
                    parent_message_id=user_message_id,
                    content=initial_card,
                    message_type=MessageType.CARD,
                    reply_in_thread=False,  # 不在话题中回复
                )
            logger.info(f"✅ 初始卡片已发送，消息 ID: {message_id}")

            # 流式接收响应
            accumulated_content = ""
            event_count = 0

            logger.info(f"开始向 Claude 发送消息并接收响应...")
            async for event in self.claude_adapter.send_message(
                session_id=claude_session_id,
                message=message_content
            ):
                event_count += 1

                # 记录每个事件的类型
                logger.info(f"收到事件 #{event_count}: type={event.event_type}, content长度={len(event.content) if event.content else 0}")

                if event.event_type == StreamEventType.TEXT_DELTA:
                    # 累积文本
                    accumulated_content += event.content
                    logger.info(f"TEXT_DELTA: 累积内容长度: {len(accumulated_content)}, 本次新增: {len(event.content)}")
                    if event_count % 10 == 0:  # 每10个事件记录一次
                        logger.debug(f"收到文本块 #{event_count}, 总长度: {len(accumulated_content)}")

                    # 更新消息
                    logger.info(f"准备更新消息 {message_id}...")
                    update_success = await self.update_message(message_id, accumulated_content)
                    logger.info(f"消息更新结果: {'成功' if update_success else '失败'}")

                elif event.event_type == StreamEventType.USER_QUESTION:
                    # 用户需要决策
                    logger.info(f"检测到用户决策请求: {event.question_id}")

                    # 发送用户决策卡片
                    choice_card = self.card_builder.create_user_choice_card(
                        question=event.question,
                        options=event.options,
                        multi_select=event.multi_select,
                        question_id=event.question_id
                    )

                    # 发送卡片并获取消息ID
                    if user_message_id:
                        # 使用回复API
                        card_message_id = await self.reply_message(
                            parent_message_id=user_message_id,
                            content=choice_card,
                            message_type=MessageType.CARD,
                        )
                    else:
                        # 回退到普通发送
                        card_message_id = await self.send_message(
                            session_id=session_id,
                            content=choice_card,
                            message_type=MessageType.CARD,
                            receive_id_type="chat_id",
                        )

                    logger.info(f"用户决策卡片已发送，消息ID: {card_message_id}")

                    # 保存问题信息到待处理列表（包含消息ID）
                    self._pending_questions[session_id] = {
                        "question_id": event.question_id,
                        "question": event.question,
                        "options": event.options,
                        "multi_select": event.multi_select,
                        "tool_id": event.metadata.get("tool_id"),
                        "claude_session_id": claude_session_id,
                        "card_message_id": card_message_id  # 保存卡片消息ID，用于后续更新
                    }

                    logger.info(f"用户决策卡片已发送，等待用户回复...")
                    # 暂停流式响应，等待用户回复
                    return

                elif event.event_type == StreamEventType.TOOL_USE:
                    # 工具调用
                    logger.info(f"检测到工具调用: {event.tool_name}")

                    # 检查工具权限
                    if self.settings and not self.settings.is_tool_allowed(event.tool_name):
                        logger.warning(f"工具 {event.tool_name} 未被允许使用，已跳过")
                        # 发送权限提示消息
                        if user_message_id:
                            await self.reply_message(
                                parent_message_id=user_message_id,
                                content=f"⚠️ 工具 `{event.tool_name}` 未被授权使用，请联系管理员",
                                message_type=MessageType.TEXT,
                            )
                        else:
                            await self.send_message(
                                session_id=session_id,
                                content=f"⚠️ 工具 `{event.tool_name}` 未被授权使用，请联系管理员",
                                message_type=MessageType.TEXT,
                                receive_id_type="chat_id",
                            )
                        # 继续处理，不中断流程
                        continue

                    # 检查配置：是否发送工具调用消息
                    if self.send_tool_messages:
                        tool_card = self.card_builder.create_tool_call_card(
                            event.tool_name,
                            event.tool_input
                        )
                        # 发送工具调用卡片
                        if user_message_id:
                            await self.reply_message(
                                parent_message_id=user_message_id,
                                content=tool_card,
                                message_type=MessageType.CARD,
                            )
                        else:
                            await self.send_message(
                                session_id=session_id,
                                content=tool_card,
                                message_type=MessageType.CARD,
                                receive_id_type="chat_id",
                            )
                    else:
                        logger.debug(f"配置禁用工具消息发送，不在飞书显示工具调用卡片: {event.tool_name}")

                elif event.event_type == StreamEventType.ERROR:
                    # 错误
                    logger.error(f"流式响应错误: {event.content}")
                    await self.update_message(
                        message_id,
                        f"{accumulated_content}\n\n❌ 错误: {event.content}"
                    )

                elif event.event_type == StreamEventType.END:
                    # 结束
                    logger.info(f"流式响应结束，共处理 {event_count} 个事件")
                    logger.info(f"最终响应长度: {len(accumulated_content)} 字符")

                    # 如果有内容但从未通过 TEXT_DELTA 更新过，现在更新
                    # 这种情况通常发生在响应很短或没有流式输出的情况下
                    if accumulated_content:
                        logger.info(f"最终内容: {accumulated_content[:100]}{'...' if len(accumulated_content) > 100 else ''}")
                        logger.info(f"准备更新消息 {message_id}...")
                        update_success = await self.update_message(message_id, accumulated_content)
                        logger.info(f"最终消息更新结果: {'成功' if update_success else '失败'}")

                    # 结束
                    logger.debug("Stream ended")
                    break

        except Exception as e:
            logger.error(f"Failed to stream Claude response: {e}")
            raise
        finally:
            # ===== 新增：确保完成表情处理 =====
            await self._finalize_reaction(session_id)
            # ===== 结束 =====

    async def _fetch_bot_user_id(self) -> Optional[str]:
        """获取机器人用户ID

        通过飞书 API 自动获取当前机器人的用户ID

        Returns:
            Optional[str]: 机器人用户ID，如果获取失败则返回 None
        """
        try:
            logger.info("调用飞书 API 获取机器人信息...")

            # 导入飞书 API 请求类
            from lark_oapi.api.bot.v3 import GetBotInfoRequest, GetBotInfoResponseBody

            # 创建请求
            request = GetBotInfoRequest.builder().build()

            # 发送请求
            response = self._http_client.bot.v3.info.get(request)

            # 检查响应
            if response.code == 0 and response.data:
                bot_user_id = response.data.bot.open_id
                logger.info(f"成功获取机器人信息: bot_user_id={bot_user_id}")
                return bot_user_id
            else:
                logger.error(f"获取机器人信息失败: code={response.code}, msg={response.msg}")
                return None

        except Exception as e:
            logger.error(f"获取机器人用户ID时发生错误: {e}", exc_info=True)
            return None

    async def _finalize_reaction(self, session_id: str) -> None:
        """完成会话时的表情处理：移除Typing，添加Done

        Args:
            session_id: 会话ID
        """
        logger.debug(
            f"尝试完成表情处理 - session_id: {session_id}, "
            f"pending_reactions_keys: {list(self._pending_reactions.keys())}"
        )

        reaction_info = self._pending_reactions.get(session_id)

        if not reaction_info:
            # 如果没有表情信息，可能是因为添加表情失败了，这是正常情况
            # 不需要记录警告，只在 debug 级别记录
            logger.debug(
                f"未找到会话的表情信息（可能添加表情失败或已被清理）"
                f" - session_id: {session_id}, "
                f"available_sessions: {list(self._pending_reactions.keys()) if self._pending_reactions else []}"
            )
            return

        try:
            user_message_id = reaction_info["user_message_id"]
            reaction_id = reaction_info["reaction_id"]

            # 替换表情：Typing -> Done
            success = await self.reaction_manager.replace_with_done(
                user_message_id,
                reaction_id
            )

            if success:
                logger.info(f"会话 {session_id} 表情替换成功")
            else:
                logger.warning(f"会话 {session_id} 表情替换失败")

        except Exception as e:
            logger.error(
                f"完成表情处理失败: {e}, session_id={session_id}",
                exc_info=True
            )
        finally:
            # 清理状态
            self._pending_reactions.pop(session_id, None)
