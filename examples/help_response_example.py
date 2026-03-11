"""
示例：/help 命令的响应结构

这个文件展示了 claude-agent-sdk 调用 /help 命令时可能返回的事件结构。
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.message import StreamEventType


def simulate_help_response():
    """
    模拟 /help 命令的流式响应

    展示可能收到的事件序列
    """
    print("=" * 80)
    print("模拟 /help 命令的流式响应")
    print("=" * 80)

    # 模拟事件序列
    events = [
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "Cla Code v2.1.72  general   commands   custom-commands\n",
            "description": "帮助文本的第1部分"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "\nClaude understands your codebase, makes edits with your permission,\n",
            "description": "帮助文本的第2部分"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "and executes commands — right from your terminal.\n",
            "description": "帮助文本的第3部分"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "\nShortcuts\n! for bash mode           double tap esc to clear input\n",
            "description": "快捷键部分"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "/ for commands            ctrl + o for verbose outputedits\n",
            "description": "更多快捷键"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "& for background          \\⏎ for newlineggle tasks\n",
            "description": "快捷键续"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "ctrl + shift + - to undo    meta + p to switch model\n",
            "description": "快捷键结束"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "ctrl + g to edit in $EDITOR\n",
            "description": "最后一个快捷键"
        },
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": "\nFor more help: https://code.claude.com/docs/en/overview",
            "description": "帮助链接"
        },
        {
            "event_type": StreamEventType.END,
            "content": "",
            "description": "响应结束"
        },
    ]

    # 模拟处理流程
    accumulated = ""
    event_count = 0

    print("\n📤 发送命令: /help\n")
    print("=" * 80)

    for event_data in events:
        event_count += 1
        event_type = event_data["event_type"]
        content = event_data["content"]
        description = event_data["description"]

        print(f"\n事件 #{event_count}:")
        print(f"  类型: {event_type.value}")
        print(f"  说明: {description}")
        print(f"  内容长度: {len(content)}")

        if event_type == StreamEventType.TEXT_DELTA:
            accumulated += content
            print(f"  ✅ 累积总长度: {len(accumulated)}")
            print(f"  📝 内容预览: {repr(content[:50])}{'...' if len(content) > 50 else ''}")

        elif event_type == StreamEventType.TOOL_USE:
            print(f"  🔧 工具调用: {content}")

        elif event_type == StreamEventType.ERROR:
            print(f"  ❌ 错误: {content}")

        elif event_type == StreamEventType.END:
            print(f"  🏁 响应结束")
            break

    print("\n" + "=" * 80)
    print("最终累积的完整响应:")
    print("=" * 80)
    print(accumulated)
    print("\n" + "=" * 80)
    print(f"统计:")
    print(f"  事件总数: {event_count}")
    print(f"  内容长度: {len(accumulated)} 字符")
    print("=" * 80)


def simulate_alternative_response():
    """
    模拟另一种可能的响应：单个大块内容
    """
    print("\n\n" + "=" * 80)
    print("模拟情况2: 单个大块内容")
    print("=" * 80)

    # 可能只有 2 个事件：1个 TEXT_DELTA + 1个 END
    events = [
        {
            "event_type": StreamEventType.TEXT_DELTA,
            "content": """Cla Code v2.1.72  general   commands   custom-commands

Claude understands your codebase, makes edits with your permission,
and executes commands — right from your terminal.

Shortcuts
! for bash mode           double tap esc to clear input
/ for commands            ctrl + o for verbose outputedits
& for background          \\⏎ for newlineggle tasks
ctrl + shift + - to undo    meta + p to switch model
ctrl + g to edit in $EDITOR

For more help: https://code.claude.com/docs/en/overview"""
        },
        {
            "event_type": StreamEventType.END,
            "content": ""
        }
    ]

    accumulated = ""
    event_count = 0

    for event_data in events:
        event_count += 1
        event_type = event_data["event_type"]
        content = event_data["content"]

        print(f"\n事件 #{event_count}: {event_type.value}")
        print(f"  内容长度: {len(content)}")

        if event_type == StreamEventType.TEXT_DELTA:
            accumulated += content
            print(f"  ✅ 单次收到所有内容，长度: {len(accumulated)}")

        elif event_type == StreamEventType.END:
            print(f"  🏁 响应结束")
            break

    print("\n最终响应:")
    print(accumulated[:200] + "..." if len(accumulated) > 200 else accumulated)
    print(f"\n(总长度: {len(accumulated)} 字符, 事件数: {event_count})")


def show_event_processing_logic():
    """
    展示当前代码的事件处理逻辑
    """
    print("\n\n" + "=" * 80)
    print("当前代码的事件处理逻辑")
    print("=" * 80)

    print("""
流式响应处理流程:

1. 发送消息到 Claude
   ↓
2. 创建初始卡片消息 ("思考中...")
   message_id = send_message(content="思考中...")
   ↓
3. 循环接收事件
   accumulated_content = ""

   for event in claude_adapter.send_message(...):

       if event.type == TEXT_DELTA:
           # 累积文本
           accumulated_content += event.content

           # 立即更新消息到飞书
           update_message(message_id, accumulated_content)
           ↑
           实时显示给用户 (每次都会刷新卡片)

       elif event.type == TOOL_USE:
           # 处理工具调用 (可选发送通知)
           ...

       elif event.type == ERROR:
           # 显示错误
           update_message(message_id, accumulated_content + "\\n❌ 错误: " + event.content)

       elif event.type == END:
           # 响应结束
           # 最终更新一次
           if accumulated_content:
               update_message(message_id, accumulated_content)
           break

关键点:
✅ 每个 TEXT_DELTA 都会更新消息
✅ 用户可以看到实时响应
✅ END 事件也会做最终更新
✅ 不会丢失任何内容

如果一直显示"思考中...":
1. 检查日志中是否收到 TEXT_DELTA 事件
2. 检查 update_message 是否成功
3. 检查 accumulated_content 是否为空
""")


if __name__ == "__main__":
    simulate_help_response()
    simulate_alternative_response()
    show_event_processing_logic()
