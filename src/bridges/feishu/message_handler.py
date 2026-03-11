# src/bridges/feishu/message_handler.py
"""飞书消息处理器

负责解析飞书消息事件并将其转换为平台无关的IMMessage格式
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any

from src.core.message import IMMessage, MessageType

logger = logging.getLogger(__name__)


class FeishuMessageHandler:
    """飞书消息处理器

    将lark-oapi的飞书消息事件转换为IMMessage格式
    支持文本、图片、文件等多种消息类型
    """

    def __init__(self, bot_user_id: Optional[str] = None):
        """初始化消息处理器

        Args:
            bot_user_id: 机器人的user_id,用于检测@机器人
        """
        self._bot_user_id = bot_user_id

    @property
    def bot_user_id(self) -> Optional[str]:
        """获取机器人用户ID"""
        return self._bot_user_id

    def set_bot_user_id(self, bot_user_id: str) -> None:
        """设置机器人用户ID

        Args:
            bot_user_id: 机器人的用户ID
        """
        self._bot_user_id = bot_user_id
        logger.info(f"机器人用户ID已更新: {bot_user_id}")

    def parse_message_event(self, event_data: Dict[str, Any]) -> IMMessage:
        """解析飞书消息事件

        Args:
            event_data: 飞书消息事件数据

        Returns:
            IMMessage: 标准化的消息对象

        Raises:
            KeyError: 当必要字段缺失时
            ValueError: 当消息内容解析失败时
        """
        try:
            header = event_data.get("header", {})
            event = event_data.get("event", {})
            sender = event.get("sender", {})
            message = event.get("message", {})

            # 基本信息
            message_id = message.get("message_id", "")
            session_id = message.get("chat_id", "")
            chat_type = message.get("chat_type", "")

            # 发送者信息
            sender_id_info = sender.get("sender_id", {})
            user_id = sender_id_info.get("user_id", "")
            user_name = sender.get("name", "")

            # 消息类型和内容
            message_type_str = message.get("message_type", "text")
            content_str = message.get("content", "{}")

            # 解析消息内容
            try:
                content_data = json.loads(content_str) if isinstance(content_str, str) else content_str
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message content: {content_str}, error: {e}")
                content_data = {}

            # 转换消息类型
            message_type = self._convert_message_type(message_type_str)

            # 提取文本内容
            text_content = self.extract_text_content(content_data)

            # 清理文本中的@提及标记（群聊中@机器人时会包含这些标记）
            mentions = message.get("mentions", [])
            if mentions and text_content:
                text_content = self.clean_mentions(text_content, mentions)
                logger.debug(f"清理@标记后的文本: {text_content}")

            # 提取附件
            attachments = self.extract_attachments(message_type_str, content_data)

            # 判断是否为私聊
            is_private = self.is_private_chat(message)

            # 判断是否提及机器人
            mentioned_bot = self.is_bot_mentioned(message)

            # 处理引用/回复消息
            quoted_message = None
            parent_id = message.get("parent_id")
            quotes = message.get("quotes", [])
            if parent_id and quotes:
                quoted_message = self._parse_quoted_message(quotes[0])

            # 构建metadata
            metadata = {
                "event_id": header.get("event_id", ""),
                "event_type": header.get("event_type", ""),
                "create_time": header.get("create_time", ""),
                "app_id": event.get("app_id", ""),
                "chat_type": chat_type,
            }

            if parent_id:
                metadata["parent_id"] = parent_id

            return IMMessage(
                content=text_content,
                message_type=message_type,
                message_id=message_id,
                session_id=session_id,
                user_id=user_id,
                user_name=user_name,
                is_private_chat=is_private,
                mentioned_bot=mentioned_bot,
                quoted_message=quoted_message,
                attachments=attachments,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to parse message event: {e}, event_data: {event_data}")
            raise

    def extract_text_content(self, message: Dict[str, Any]) -> str:
        """从消息内容中提取文本

        Args:
            message: 消息内容字典

        Returns:
            str: 提取的文本内容
        """
        if not message:
            return ""

        # 文本消息直接返回text字段
        text = message.get("text", "")

        # 如果是其他类型消息,尝试构建描述文本
        if not text:
            message_type = message.get("type", "")
            if message_type == "image":
                text = "[图片]"
            elif message_type == "file":
                file_name = message.get("name", "文件")
                text = f"[文件: {file_name}]"
            elif message_type == "audio":
                text = "[音频]"
            elif message_type == "video":
                text = "[视频]"
            elif message_type == "sticker":
                text = "[表情]"
            else:
                text = "[多媒体消息]"

        return text

    def clean_mentions(self, text: str, mentions: List[Dict[str, Any]]) -> str:
        """清理文本中的@提及标记

        在群聊中@机器人时，文本会包含@标记，例如：
        - "@机器人 /help"
        - "<at user_id=cli_xxx>机器人</at> /help"

        这个方法会清理这些标记，提取纯净的文本内容。

        Args:
            text: 原始文本内容
            mentions: 提及列表

        Returns:
            str: 清理后的文本内容
        """
        if not text:
            return text

        # 方法1: 清理 XML 格式的 @标记 <at user_id=xxx>name</at>
        # 一次性移除整个 <at>...</at> 标签及其内容
        text = re.sub(r'<at[^>]*>.*?</at>', '', text, flags=re.DOTALL)

        # 方法2: 清理纯文本格式的 @用户名
        # 移除开头的 @用户名（例如 "@机器人 /help" -> "/help"）
        # 但要保留命令中的 @（例如 "/claude:commit @someone"）

        # 如果文本以 @ 开头，尝试移除第一个 @提及
        # 匹配模式：@用户名 后面跟空格或命令
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # 匹配行首的 @用户名
            # 例如 "@机器人 /help" -> "/help"
            # "@机器人 帮我分析代码" -> "帮我分析代码"
            pattern = r'^@[^\s]+\s*'
            match = re.match(pattern, line)
            if match:
                # 移除行首的 @用户名
                line = line[match.end():]

            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # 清理多余的空格
        text = text.strip()

        return text

        # 方法2: 清理纯文本格式的 @用户名
        # 移除开头的 @用户名（例如 "@机器人 /help" -> "/help"）
        # 但要保留命令中的 @（例如 "/claude:commit @someone"）

        # 如果文本以 @ 开头，尝试移除第一个 @提及
        # 匹配模式：@用户名 后面跟空格或命令
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # 匹配行首的 @用户名
            # 例如 "@机器人 /help" -> "/help"
            # "@机器人 帮我分析代码" -> "帮我分析代码"
            pattern = r'^@[^\s]+\s*'
            match = re.match(pattern, line)
            if match:
                # 移除行首的 @用户名
                line = line[match.end():]

            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # 清理多余的空格
        text = text.strip()

        return text

    def extract_attachments(self, message_type: str, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从消息内容中提取附件信息

        Args:
            message_type: 消息类型 (text, image, file等)
            content: 消息内容字典

        Returns:
            List[Dict]: 附件信息列表
        """
        attachments = []

        if not content:
            return attachments

        try:
            if message_type == "image":
                # 图片消息
                image_key = content.get("image_key")
                if image_key:
                    attachments.append(
                        {
                            "type": "image",
                            "image_key": image_key,
                            "metadata": content,
                        }
                    )

            elif message_type == "file":
                # 文件消息
                file_key = content.get("file_key")
                file_name = content.get("name", "")
                if file_key:
                    attachments.append(
                        {
                            "type": "file",
                            "file_key": file_key,
                            "name": file_name,
                            "metadata": content,
                        }
                    )

            elif message_type == "audio":
                # 音频消息
                file_key = content.get("file_key")
                if file_key:
                    attachments.append(
                        {
                            "type": "audio",
                            "file_key": file_key,
                            "metadata": content,
                        }
                    )

            elif message_type == "video":
                # 视频消息
                file_key = content.get("file_key")
                if file_key:
                    attachments.append(
                        {
                            "type": "video",
                            "file_key": file_key,
                            "metadata": content,
                        }
                    )

            elif message_type == "media":
                # 媒体消息(可能包含多个)
                if "image_key" in content:
                    attachments.append(
                        {
                            "type": "image",
                            "image_key": content["image_key"],
                            "metadata": content,
                        }
                    )
                if "file_key" in content:
                    attachments.append(
                        {
                            "type": "file",
                            "file_key": content["file_key"],
                            "metadata": content,
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to extract attachments: {e}, content: {content}")

        return attachments

    def is_private_chat(self, message: Dict[str, Any]) -> bool:
        """判断是否为私聊消息

        Args:
            message: 消息数据

        Returns:
            bool: True表示私聊,False表示群聊
        """
        chat_type = message.get("chat_type", "")
        return chat_type == "p2p"

    def is_bot_mentioned(self, message: Dict[str, Any]) -> bool:
        """判断机器人是否被提及

        Args:
            message: 消息数据

        Returns:
            bool: True表示机器人被提及

        注意:
        - 如果有 bot_user_id: 精确判断机器人是否被@
        - 如果没有 bot_user_id: 有 mentions 列表就认为可能被@（宽松模式）
        """
        mentions = message.get("mentions", [])
        if not mentions:
            return False

        # 如果还没有设置 bot_user_id，采用宽松模式
        # 只要消息有 @ 任何人，就认为可能@了机器人
        # 这样可以在首次使用时就自动提取 bot_user_id
        if not self._bot_user_id:
            logger.debug("bot_user_id 未设置，采用宽松模式检测@（有 mentions 就响应）")
            return True

        # 精确模式：检查 mentions 中是否包含机器人
        for mention in mentions:
            if isinstance(mention, dict):
                mention_id = mention.get("id", {})
                if isinstance(mention_id, dict):
                    mentioned_user_id = (
                        mention_id.get("user_id") or
                        mention_id.get("open_id")
                    )
                    if mentioned_user_id == self._bot_user_id:
                        return True

        return False

    def _convert_message_type(self, feishu_type: str) -> MessageType:
        """转换飞书消息类型到IMMessage类型

        Args:
            feishu_type: 飞书消息类型

        Returns:
            MessageType: 标准化的消息类型
        """
        type_mapping = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "file": MessageType.FILE,
            "audio": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "sticker": MessageType.TEXT,  # 表情包当作文本处理
            "media": MessageType.FILE,  # 媒体消息当作文件处理
        }

        return type_mapping.get(feishu_type, MessageType.TEXT)

    def _parse_quoted_message(self, quote_data: Dict[str, Any]) -> Optional[IMMessage]:
        """解析引用/回复消息

        Args:
            quote_data: 引用消息数据

        Returns:
            Optional[IMMessage]: 引用的消息对象
        """
        if not quote_data:
            return None

        try:
            # 获取引用消息的内容
            quoted_message_id = quote_data.get("quoted_message_id", "")
            content_str = quote_data.get("quoted_message_content", "{}")

            # 解析内容
            try:
                content_data = json.loads(content_str) if isinstance(content_str, str) else content_str
            except json.JSONDecodeError:
                content_data = {}

            # 提取文本
            text_content = self.extract_text_content(content_data)

            # 构建简化的引用消息对象
            return IMMessage(
                content=text_content,
                message_type=MessageType.TEXT,
                message_id=quoted_message_id,
                session_id="",  # 引用消息不需要session_id
                user_id="",  # 引用消息不需要user_id
                user_name="",  # 引用消息不需要user_name
                is_private_chat=False,
                mentioned_bot=False,
            )

        except Exception as e:
            logger.error(f"Failed to parse quoted message: {e}, quote_data: {quote_data}")
            return None

    def set_bot_user_id(self, bot_user_id: str):
        """设置机器人user_id

        Args:
            bot_user_id: 机器人的user_id
        """
        self._bot_user_id = bot_user_id
