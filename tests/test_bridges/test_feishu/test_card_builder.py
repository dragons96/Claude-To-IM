# tests/test_bridges/test_feishu/test_card_builder.py
import pytest
from src.bridges.feishu.card_builder import (
    create_session_list_card,
    create_tool_call_card,
    create_error_card,
    create_message_card
)


class TestSessionListCard:
    """测试会话列表卡片"""

    def test_create_session_list_card_with_sessions(self):
        """测试创建包含会话的列表卡片"""
        sessions = [
            {
                "session_id": "session_1",
                "user_name": "张三",
                "created_at": "2024-01-15 10:30:00",
                "message_count": 5
            },
            {
                "session_id": "session_2",
                "user_name": "李四",
                "created_at": "2024-01-15 11:00:00",
                "message_count": 3
            }
        ]

        card = create_session_list_card(sessions)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) >= 1

        # 检查标题
        header = card["elements"][0]
        assert header["tag"] == "div"
        assert "会话列表" in header["text"]["content"]

        # 检查会话内容
        session_found = False
        for element in card["elements"]:
            if element.get("tag") == "div":
                text = element.get("text", {})
                content = str(text.get("content", ""))
                if "张三" in content or "session_1" in content:
                    session_found = True
                    break

        assert session_found, "应该包含会话内容"

    def test_create_session_list_card_empty(self):
        """测试创建空会话列表卡片"""
        sessions = []

        card = create_session_list_card(sessions)

        assert card["config"]["wide_screen_mode"] is True
        assert "暂无会话" in str(card["elements"])


class TestToolCallCard:
    """测试工具调用卡片"""

    def test_create_tool_call_card(self):
        """测试创建工具调用卡片"""
        tool_name = "web_search"
        tool_input = {
            "query": "Python异步编程",
            "max_results": 5
        }

        card = create_tool_call_card(tool_name, tool_input)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) >= 1

        # 检查标题
        header = card["elements"][0]
        assert header["tag"] == "div"
        assert "工具调用" in header["text"]["content"]

        # 检查工具名称
        tool_name_found = False
        for element in card["elements"]:
            if element.get("tag") == "div":
                text = element.get("text", {})
                if "web_search" in str(text.get("content", "")):
                    tool_name_found = True
                    break

        assert tool_name_found, "应该包含工具名称"

    def test_create_tool_call_card_with_complex_input(self):
        """测试创建包含复杂输入的工具调用卡片"""
        tool_name = "data_analysis"
        tool_input = {
            "dataset": "sales_2024",
            "filters": {
                "region": "Asia",
                "quarter": "Q1"
            },
            "metrics": ["revenue", "growth"]
        }

        card = create_tool_call_card(tool_name, tool_input)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) > 0


class TestErrorCard:
    """测试错误卡片"""

    def test_create_error_card(self):
        """测试创建错误卡片"""
        error_message = "连接超时：无法访问API服务"

        card = create_error_card(error_message)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) >= 1

        # 检查错误标题
        header = card["elements"][0]
        assert header["tag"] == "div"
        assert "错误" in header["text"]["content"] or "Error" in header["text"]["content"]

        # 检查错误内容
        content_found = False
        for element in card["elements"]:
            if element.get("tag") == "div":
                text = element.get("text", {})
                if "连接超时" in str(text.get("content", "")):
                    content_found = True
                    break

        assert content_found, "应该包含错误消息"


class TestMessageCard:
    """测试消息卡片"""

    def test_create_message_card_with_plain_text(self):
        """测试创建纯文本消息卡片"""
        content = "你好，这是一条测试消息"

        card = create_message_card(content)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) >= 1

        # 检查消息内容
        message_found = False
        for element in card["elements"]:
            if element.get("tag") == "div":
                text = element.get("text", {})
                if "测试消息" in str(text.get("content", "")):
                    message_found = True
                    break

        assert message_found, "应该包含消息内容"

    def test_create_message_card_with_markdown(self):
        """测试创建Markdown消息卡片"""
        content = "**粗体文本** 和 *斜体文本*"

        card = create_message_card(content)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) > 0

    def test_create_message_card_with_long_content(self):
        """测试创建长消息卡片"""
        content = "这是一条很长的消息。" * 50

        card = create_message_card(content)

        assert card["config"]["wide_screen_mode"] is True
        assert len(card["elements"]) > 0


class TestCardStructure:
    """测试卡片结构"""

    def test_card_has_required_fields(self):
        """测试卡片包含必需字段"""
        card = create_message_card("测试")

        assert "config" in card
        assert "elements" in card
        assert isinstance(card["elements"], list)

    def test_card_elements_valid(self):
        """测试卡片元素有效"""
        card = create_session_list_card([])

        for element in card["elements"]:
            assert "tag" in element
            assert isinstance(element["tag"], str)
