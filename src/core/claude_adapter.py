# src/core/claude_adapter.py
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, field
from src.core.message import StreamEvent


@dataclass
class ClaudeSession:
    """Claude 会话对象"""
    session_id: str
    work_directory: str
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClaudeAdapter(ABC):
    """Claude SDK 适配器基类"""

    @abstractmethod
    async def create_session(
        self,
        work_directory: str,
        session_id: Optional[str] = None
    ) -> ClaudeSession:
        """创建新的 Claude 会话

        Args:
            work_directory: 工作目录路径
            session_id: 可选的自定义会话 ID

        Returns:
            ClaudeSession: 创建的会话对象
        """
        pass

    @abstractmethod
    async def close_session(self, session_id: str) -> None:
        """关闭指定的会话

        Args:
            session_id: 要关闭的会话 ID
        """
        pass

    @abstractmethod
    async def send_message(
        self,
        session_id: str,
        message: str,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        """向 Claude 会话发送消息

        Args:
            session_id: 会话 ID
            message: 要发送的消息内容
            **kwargs: 其他参数

        Yields:
            StreamEvent: 流式响应事件
        """
        pass

    @abstractmethod
    async def get_session_info(self, session_id: str) -> Optional[ClaudeSession]:
        """获取会话信息

        Args:
            session_id: 会话 ID

        Returns:
            Optional[ClaudeSession]: 会话对象,如果不存在则返回 None
        """
        pass

    @abstractmethod
    async def list_sessions(self, **kwargs) -> List[ClaudeSession]:
        """列出所有会话

        Args:
            **kwargs: 筛选条件

        Returns:
            List[ClaudeSession]: 会话列表
        """
        pass
