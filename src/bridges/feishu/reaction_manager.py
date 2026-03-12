# src/bridges/feishu/reaction_manager.py

"""
飞书消息表情反应管理器

负责处理飞书消息的表情反应操作，包括添加、删除和替换表情。
"""

from typing import Optional
import structlog

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
