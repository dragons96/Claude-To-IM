# src/bridges/feishu/reaction_manager.py

"""
飞书消息表情反应管理器

负责处理飞书消息的表情反应操作，包括添加、删除和替换表情。
"""

from typing import Optional
import structlog
from lark_oapi.api.im.v1 import CreateMessageReactionRequest

logger = structlog.get_logger(__name__)


class FeishuReactionManager:
    """飞书消息表情反应管理器"""

    # 表情类型常量
    EMOJI_TYPING = "Typing"
    EMOJI_DONE = "DONE"

    def __init__(self, http_client, bot_user_id: str):
        """
        初始化表情管理器

        Args:
            http_client: 飞书HTTP客户端
            bot_user_id: 机器人的user_id，用于指定操作者
        """
        self._http_client = http_client
        self._bot_user_id = bot_user_id

    async def add_reaction(self, message_id: str, emoji_type: str) -> Optional[str]:
        """
        通用方法：添加表情反应

        Args:
            message_id: 消息ID
            emoji_type: 表情类型（如"Typing", "DONE"）

        Returns:
            reaction_id: 表情反应ID，失败返回None
        """
        try:
            # 导入Emoji和CreateMessageReactionRequestBody
            from lark_oapi.api.im.v1.model.emoji import Emoji
            from lark_oapi.api.im.v1.model.create_message_reaction_request_body import (
                CreateMessageReactionRequestBody,
            )

            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                        .reaction_type(
                            Emoji.builder()
                                .emoji_type(emoji_type)
                                .build()
                        )
                        .build()
                ) \
                .build()

            response = await self._http_client.im.v1.message_reaction.create(request)

            if response.code == 0 and response.data:
                reaction_id = response.data.reaction_id
                logger.info(
                    f"成功添加表情 {emoji_type} 到消息 {message_id}",
                    reaction_id=reaction_id
                )
                return reaction_id
            else:
                logger.error(
                    f"添加表情失败: code={response.code}, msg={response.msg}",
                    message_id=message_id,
                    emoji_type=emoji_type
                )
                return None

        except Exception as e:
            logger.error(
                f"添加表情异常: {e}",
                exc_info=True,
                message_id=message_id,
                emoji_type=emoji_type
            )
            return None
