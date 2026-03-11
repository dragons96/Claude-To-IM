import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk import (
    UserMessage,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    TaskProgressMessage,
    TaskNotificationMessage
)

async def main():
    # 配置选项
    options = ClaudeAgentOptions(
        max_turns=10,  # 增加到 10 轮，让 AI 有足够时间使用工具并完成分析
        model=os.getenv("ANTHROPIC_MODEL"),
        env={
            "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN"),
            "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL"),
        },
        cwd=os.getcwd(),
        include_partial_messages=True,  # 启用流式输出
        # 加载所有配置源：用户目录、项目目录、本地目录
        setting_sources=["user", "project", "local"]
    )

    # 使用 ClaudeSDKClient
    async with ClaudeSDKClient(options) as client:
        # 发送消息
        await client.query("/superpowers:")

        # 接收响应（持续监听，不自动停止）
        async for message in client.receive_messages():
            print(type(message))
            if isinstance(message, SystemMessage):
                # 处理系统消息
                if message.subtype == "init":
                    print(f"[初始化] 会话ID: {message.data.get('session_id')}")
                else:
                    print(f"[系统消息] {message.subtype}: {message.data}")

            elif isinstance(message, UserMessage):
                # 显示用户消息（包含工具结果）
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        # 显示工具结果（截断过长的输出）
                        result = str(block.content)[:500]
                        if len(str(block.content)) > 500:
                            result += "..."
                        print(f"\n[工具结果] {block.tool_use_id[:8]}...: {result}\n")

            elif isinstance(message, AssistantMessage):
                # 处理助手的回复 - 实时输出
                for block in message.content:
                    if isinstance(block, TextBlock):
                        # 实时输出文本
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        # 显示工具调用
                        print(f"\n\n[工具调用] {block.name}")
                        if block.input:
                            import json
                            print(f"参数: {json.dumps(block.input, ensure_ascii=False, indent=2)}")

            elif isinstance(message, TaskProgressMessage):
                # 处理任务进度消息
                print(f"\n[任务进度] {message.description}")

            elif isinstance(message, TaskNotificationMessage):
                # 处理任务通知
                print(f"\n[任务通知] {message.subtype}")

            elif isinstance(message, ResultMessage):
                # 处理结果（消息结束）
                print(f"\n\n[完成]")
                print(f"对话轮数: {message.num_turns}")
                print(f"耗时: {message.duration_ms}ms")
                if message.usage:
                    print(f"Token 使用: {message.usage}")
                if message.total_cost_usd:
                    print(f"成本: ${message.total_cost_usd:.4f}")
                break  # 收到结果消息后退出循环

if __name__ == "__main__":
    asyncio.run(main())
