# src/core/message.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    CARD = "card"

class StreamEventType(Enum):
    """流式事件类型枚举"""
    TEXT_DELTA = "text_delta"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    USER_QUESTION = "user_question"  # 用户需要决策
    ERROR = "error"
    END = "end"

@dataclass
class StreamEvent:
    """流式事件对象"""
    event_type: StreamEventType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 用户决策相关字段
    question_id: Optional[str] = None  # 问题唯一标识
    question: Optional[str] = None  # 问题文本
    options: Optional[List[Dict[str, Any]]] = None  # 可选选项
    multi_select: bool = False  # 是否支持多选

@dataclass
class IMMessage:
    """平台无关的消息对象"""
    content: str
    message_type: MessageType
    message_id: str
    session_id: str
    user_id: str
    user_name: str
    is_private_chat: bool
    mentioned_bot: bool = False
    quoted_message: Optional['IMMessage'] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
