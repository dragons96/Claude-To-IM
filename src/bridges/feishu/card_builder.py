# src/bridges/feishu/card_builder.py
"""
飞书卡片构建器

用于创建飞书交互式卡片的工具函数。
参考文档：https://open.feishu.cn/document/common-capabilities/message-card/message-cards-content
"""

import json
from typing import Dict, Any, List, Optional


def _create_base_card() -> Dict[str, Any]:
    """创建基础卡片结构"""
    return {
        "config": {
            "wide_screen_mode": True
        },
        "elements": []
    }


def _create_header(text: str, tag: str = "plain_text") -> Dict[str, Any]:
    """创建卡片标题元素"""
    return {
        "tag": "div",
        "text": {
            "tag": tag,
            "content": text
        }
    }


def _create_text_element(content: str, tag: str = "plain_text") -> Dict[str, Any]:
    """创建文本元素"""
    return {
        "tag": "div",
        "text": {
            "tag": tag,
            "content": content
        }
    }


def _create_markdown_element(content: str) -> Dict[str, Any]:
    """创建Markdown元素"""
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": content
        }
    }


def _create_hr() -> Dict[str, Any]:
    """创建分隔线元素"""
    return {
        "tag": "hr"
    }


def create_session_list_card(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    创建会话列表卡片

    Args:
        sessions: 会话列表，每个会话包含:
            - session_id: 会话ID
            - user_name: 用户名称
            - created_at: 创建时间
            - message_count: 消息数量

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header("📋 会话列表"))

    if not sessions:
        card["elements"].append(_create_text_element("暂无会话"))
        return card

    # 添加会话列表
    for i, session in enumerate(sessions):
        if i > 0:
            card["elements"].append(_create_hr())

        session_text = (
            f"**用户**: {session.get('user_name', '未知')}\n"
            f"**会话ID**: {session.get('session_id', 'N/A')}\n"
            f"**创建时间**: {session.get('created_at', 'N/A')}\n"
            f"**消息数**: {session.get('message_count', 0)}"
        )

        card["elements"].append(_create_markdown_element(session_text))

    return card


def create_tool_call_card(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建工具调用卡片

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header("🔧 工具调用"))

    # 添加工具名称
    card["elements"].append(_create_text_element(f"工具: {tool_name}"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 格式化工具输入
    input_text = _format_tool_input(tool_input)
    card["elements"].append(_create_markdown_element(f"**输入参数**:\n{input_text}"))

    return card


def _format_tool_input(tool_input: Dict[str, Any], indent: int = 0) -> str:
    """
    格式化工具输入参数为Markdown

    Args:
        tool_input: 工具输入参数
        indent: 缩进级别

    Returns:
        格式化的Markdown字符串
    """
    lines = []
    prefix = "  " * indent

    for key, value in tool_input.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}**: ")
            lines.append(_format_tool_input(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}**: ")
            for item in value:
                if isinstance(item, dict):
                    lines.append(_format_tool_input(item, indent + 1))
                else:
                    lines.append(f"{prefix}- {item}")
        else:
            lines.append(f"{prefix}**{key}**: {value}")

    return "\n".join(lines)


def create_error_card(error_message: str) -> Dict[str, Any]:
    """
    创建错误卡片

    Args:
        error_message: 错误消息

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加错误标题
    card["elements"].append(_create_header("❌ 错误"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 添加错误消息
    card["elements"].append(_create_text_element(error_message))

    return card


def create_message_card(content: str) -> Dict[str, Any]:
    """
    创建文本消息卡片

    Args:
        content: 消息内容（支持Markdown格式）

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 检测是否包含Markdown语法
    markdown_markers = ["**", "*", "__", "_", "`", "```", "#"]
    has_markdown = any(marker in content for marker in markdown_markers)

    if has_markdown:
        # 使用Markdown元素
        card["elements"].append(_create_markdown_element(content))
    else:
        # 使用纯文本元素
        card["elements"].append(_create_text_element(content))

    return card


def create_info_card(title: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    创建信息卡片

    Args:
        title: 卡片标题
        items: 信息项列表，每项包含:
            - label: 标签
            - value: 值

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header(title))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 添加信息项
    for item in items:
        label = item.get("label", "")
        value = item.get("value", "")
        card["elements"].append(_create_markdown_element(f"**{label}**: {value}"))

    return card


def create_interactive_card(
    title: str,
    content: str,
    buttons: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    创建交互式卡片（带按钮）

    Args:
        title: 卡片标题
        content: 卡片内容
        buttons: 按钮列表，每个按钮包含:
            - text: 按钮文本
            - url: 按钮链接（可选）
            - value: 按钮值（可选）

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header(title))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 添加内容
    card["elements"].append(_create_markdown_element(content))

    # 添加按钮
    if buttons:
        button_elements = []
        for btn in buttons:
            button_element = {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": btn.get("text", "按钮")
                }
            }

            if "url" in btn:
                button_element["url"] = btn["url"]
            if "value" in btn:
                button_element["value"] = btn["value"]

            button_elements.append(button_element)

        if button_elements:
            card["elements"].append({
                "tag": "action",
                "actions": button_elements
            })

    return card


def create_user_choice_card(
    question: str,
    options: List[Dict[str, Any]],
    multi_select: bool = False,
    question_id: str = ""
) -> Dict[str, Any]:
    """
    创建用户决策卡片（使用交互式按钮）

    当 Claude 需要用户做决策时显示此卡片，包含问题文本和可选选项按钮。
    用户点击按钮来选择。

    Args:
        question: 问题描述
        options: 选项列表，每个选项包含:
            - label: 选项标签（简短描述）
            - description: 选项详细描述（可选）
            - value: 选项值（用于返回给Claude）
        multi_select: 是否支持多选
        question_id: 问题唯一标识（用于回调路由）

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header("🤔 需要您的决策"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 添加问题
    card["elements"].append(_create_markdown_element(f"**问题**:\n{question}"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 添加选项提示
    select_hint = "**请选择一个选项**:" if not multi_select else "**请选择选项（可多选）**:"
    card["elements"].append(_create_text_element(select_hint))

    # 创建按钮元素列表
    button_elements = []

    for i, option in enumerate(options, 1):
        label = option.get("label", "")
        description = option.get("description", "")
        value = option.get("value", "")

        # 按钮文本：如果有描述，使用 "序号. 标签" 格式
        button_text = f"{i}. {label}"
        if len(button_text) > 20:
            # 按钮文本过长，只显示序号和简短标签
            button_text = f"{i}. {label[:15]}..."

        # 创建按钮
        # 注意：value 字段必须是 Dict 类型，不能是 JSON 字符串
        button = {
            "tag": "button",
            "text": {
                "tag": "plain_text",
                "content": button_text
            },
            "type": "primary",
            "value": {
                "action": "user_choice",
                "question_id": question_id,
                "option_index": i - 1,  # 0-based index
                "option_value": value,
                "option_label": label,
                "multi_select": multi_select
            }
        }

        button_elements.append(button)

        # 如果有详细描述，添加为说明文本（带编号）
        if description:
            card["elements"].append(_create_markdown_element(f"   {i}. 💬 {description}"))

    # 添加按钮组到卡片
    if button_elements:
        # 飞书的 action 元素
        card["elements"].append({
            "tag": "action",
            "actions": button_elements
        })

    # 添加使用说明
    card["elements"].append(_create_hr())
    hint = "💡 **使用提示**: 点击上方按钮选择您想要的选项"
    card["elements"].append(_create_markdown_element(hint))

    return card


def create_custom_answer_result_card(
    question: str,
    custom_answer: str
) -> Dict[str, Any]:
    """
    创建用户自定义答案结果卡片

    当用户输入自定义内容（而非选项）时显示此卡片。

    Args:
        question: 原问题描述
        custom_answer: 用户自定义的回答

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header("✅ 已输入自定义答案"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 显示原问题
    card["elements"].append(_create_markdown_element(f"**问题**:\n{question}"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 显示用户的自定义回答
    card["elements"].append(_create_markdown_element(f"**您的回答**:\n{custom_answer}"))

    return card


def create_user_choice_result_card(
    question: str,
    options: List[Dict[str, Any]],
    selected_indices: List[int]
) -> Dict[str, Any]:
    """
    创建用户选择结果卡片（保留所有选项，标记已选择的）

    当用户做出选择后，更新原卡片显示选择结果。
    保留所有选项文本，只移除按钮，在底部显示用户的选择。

    Args:
        question: 原问题描述
        options: 所有选项列表
        selected_indices: 用户选择的选项索引列表（0-based）

    Returns:
        飞书卡片字典
    """
    card = _create_base_card()

    # 添加标题
    card["elements"].append(_create_header("✅ 已完成选择"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 显示原问题
    card["elements"].append(_create_markdown_element(f"**问题**:\n{question}"))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 显示所有选项（带编号）
    card["elements"].append(_create_text_element("**选项**:" if not selected_indices else "**所有选项**:"))

    for i, option in enumerate(options, 1):
        label = option.get("label", "")
        description = option.get("description", "")

        # 检查是否被选中
        is_selected = (i - 1) in selected_indices
        prefix = "✅ " if is_selected else "   "

        if description:
            option_text = f"{prefix}{i}. **{label}**\n      💬 {description}"
        else:
            option_text = f"{prefix}{i}. **{label}**"

        card["elements"].append(_create_markdown_element(option_text))

    # 添加分隔线
    card["elements"].append(_create_hr())

    # 在底部显示用户的选择（使用序号）
    selected_numbers = [i + 1 for i in selected_indices]
    if len(selected_indices) == 1:
        choice_text = f"**您的选择**: {selected_numbers[0]}"
    else:
        choice_text = f"**您的选择**: {', '.join(map(str, selected_numbers))}"

    card["elements"].append(_create_markdown_element(choice_text))

    return card
