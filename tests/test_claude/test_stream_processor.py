# tests/test_claude/test_stream_processor.py
import pytest
from src.claude.stream_processor import (
    format_tool_call,
    detect_event_type,
    extract_text_content
)
from src.core.message import StreamEventType
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
    SystemMessage,
    UserMessage
)


def test_format_tool_call():
    """测试格式化工具调用"""
    # 简单参数
    result = format_tool_call("search", {"query": "test"})
    assert "search" in result
    assert "query" in result
    assert "test" in result

    # 复杂参数
    result = format_tool_call("calculate", {
        "expression": "2+2",
        "precision": 4
    })
    assert "calculate" in result
    assert "expression" in result
    assert "2+2" in result
    assert "precision" in result

    # 空参数
    result = format_tool_call("noop", {})
    assert "noop" in result


def test_detect_event_type_text():
    """测试检测文本事件类型"""
    message = AssistantMessage(
        content=[TextBlock(text="Hello")],
        model="claude-3-5-sonnet-20241022"
    )

    event_type = detect_event_type(message)
    assert event_type == StreamEventType.TEXT_DELTA


def test_detect_event_type_tool_use():
    """测试检测工具使用事件类型"""
    message = AssistantMessage(
        content=[ToolUseBlock(
            id="tool-123",
            name="test_tool",
            input={"arg1": "value1"}
        )],
        model="claude-3-5-sonnet-20241022"
    )

    event_type = detect_event_type(message)
    assert event_type == StreamEventType.TOOL_USE


def test_detect_event_type_end():
    """测试检测结束事件类型"""
    message = ResultMessage(
        subtype="success",
        duration_ms=1000,
        duration_api_ms=800,
        is_error=False,
        num_turns=1,
        session_id="test_session"
    )

    event_type = detect_event_type(message)
    assert event_type == StreamEventType.END


def test_detect_event_type_unknown():
    """测试检测未知事件类型"""
    message = SystemMessage(subtype="info", data={"message": "System message"})

    event_type = detect_event_type(message)
    assert event_type == StreamEventType.TEXT_DELTA  # 默认返回文本类型


def test_extract_text_content():
    """测试提取文本内容"""
    # 单个文本块
    message = AssistantMessage(
        content=[TextBlock(text="Hello World")],
        model="claude-3-5-sonnet-20241022"
    )

    text = extract_text_content(message)
    assert text == "Hello World"

    # 多个文本块
    message = AssistantMessage(
        content=[
            TextBlock(text="Hello "),
            TextBlock(text="World")
        ],
        model="claude-3-5-sonnet-20241022"
    )

    text = extract_text_content(message)
    assert text == "Hello World"

    # 混合内容（工具使用和文本）
    message = AssistantMessage(
        content=[
            TextBlock(text="Before tool"),
            ToolUseBlock(
                id="tool-123",
                name="test_tool",
                input={"arg": "value"}
            )
        ],
        model="claude-3-5-sonnet-20241022"
    )

    text = extract_text_content(message)
    assert text == "Before tool"

    # 空内容
    message = AssistantMessage(
        content=[],
        model="claude-3-5-sonnet-20241022"
    )

    text = extract_text_content(message)
    assert text == ""

    # 非助手消息
    message = UserMessage(content="User message")
    text = extract_text_content(message)
    assert text == ""
