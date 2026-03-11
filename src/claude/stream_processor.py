# src/claude/stream_processor.py
"""流式响应处理工具模块

提供处理 Claude SDK 流式响应的实用函数，用于格式化和解析消息。
"""
from typing import Dict, Any
import json
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage
)
from src.core.message import StreamEventType


def format_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """格式化工具调用为可读文本

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数

    Returns:
        str: 格式化后的工具调用文本

    Examples:
        >>> format_tool_call("search", {"query": "test"})
        '🔧 工具调用: search\\n参数: query="test"'

        >>> format_tool_call("calculate", {"expression": "2+2", "precision": 4})
        '🔧 工具调用: calculate\\n参数: expression="2+2", precision=4'
    """
    if not tool_input:
        return f"🔧 工具调用: {tool_name}"

    # 格式化参数
    params = []
    for key, value in tool_input.items():
        if isinstance(value, str):
            params.append(f'{key}="{value}"')
        elif isinstance(value, (dict, list)):
            params.append(f"{key}={json.dumps(value, ensure_ascii=False)}")
        else:
            params.append(f"{key}={value}")

    params_str = ", ".join(params)
    return f"🔧 工具调用: {tool_name}\n参数: {params_str}"


def detect_event_type(message) -> StreamEventType:
    """从 SDK 消息检测事件类型

    Args:
        message: Claude SDK 返回的消息对象

    Returns:
        StreamEventType: 检测到的事件类型

    Examples:
        >>> msg = AssistantMessage(content=[TextBlock(text="Hi")], model="...")
        >>> detect_event_type(msg)
        <StreamEventType.TEXT_DELTA: 'text_delta'>

        >>> msg = ResultMessage(subtype="success", ...)
        >>> detect_event_type(msg)
        <StreamEventType.END: 'end'>
    """
    # 检查是否是结果消息（表示流结束）
    if isinstance(message, ResultMessage):
        return StreamEventType.END

    # 检查是否是助手消息
    if isinstance(message, AssistantMessage):
        # 检查内容中是否有工具使用
        if message.content:
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    return StreamEventType.TOOL_USE

            # 如果有文本块，返回文本增量事件
            for block in message.content:
                if isinstance(block, TextBlock):
                    return StreamEventType.TEXT_DELTA

    # 默认返回文本增量类型（用于未知消息类型）
    return StreamEventType.TEXT_DELTA


def extract_text_content(message) -> str:
    """从消息块中提取文本内容

    Args:
        message: Claude SDK 返回的消息对象

    Returns:
        str: 提取的文本内容，如果没有文本则返回空字符串

    Examples:
        >>> msg = AssistantMessage(
        ...     content=[TextBlock(text="Hello"), TextBlock(text=" World")],
        ...     model="..."
        ... )
        >>> extract_text_content(msg)
        'Hello World'

        >>> msg = AssistantMessage(
        ...     content=[ToolUseBlock(id="123", name="tool", input={})],
        ...     model="..."
        ... )
        >>> extract_text_content(msg)
        ''
    """
    # 只处理助手消息
    if not isinstance(message, AssistantMessage):
        return ""

    # 如果没有内容，返回空字符串
    if not message.content:
        return ""

    # 提取所有文本块的内容
    text_parts = []
    for block in message.content:
        if isinstance(block, TextBlock):
            text_parts.append(block.text)

    # 合并所有文本部分
    return "".join(text_parts)
