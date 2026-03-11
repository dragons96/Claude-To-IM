# src/core/im_adapter.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.core.message import IMMessage, MessageType

class IMAdapter(ABC):
    """IM 平台适配器基类"""

    @abstractmethod
    async def start(self) -> None:
        """启动适配器，开始监听消息"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止适配器"""
        pass

    @abstractmethod
    async def send_message(
        self,
        session_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> str:
        """发送消息，返回消息 ID"""
        pass

    @abstractmethod
    async def update_message(
        self,
        message_id: str,
        new_content: str
    ) -> bool:
        """更新已发送的消息（用于流式输出）"""
        pass

    @abstractmethod
    async def download_resource(self, url: str) -> bytes:
        """下载资源文件"""
        pass

    @abstractmethod
    def should_respond(self, message: IMMessage) -> bool:
        """判断是否应该响应此消息"""
        pass

    @abstractmethod
    def format_quoted_message(self, message: IMMessage) -> str:
        """格式化引用消息"""
        pass
