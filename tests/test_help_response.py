# test_help_response.py
"""测试 /help 命令的响应结构"""
from dotenv import load_dotenv

load_dotenv()

import os

import asyncio
import logging
from pathlib import Path

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent))

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from src.core.message import StreamEventType

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_help_command():
    """测试 /help 命令的响应"""

    # 创建 Claude 选项
    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN"),
            "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL"),
        },
        model="claude-opus-4-6",
        max_turns=10,
        include_partial_messages=True
    )

    # 创建客户端
    client = ClaudeSDKClient(options)

    try:
        # 初始化客户端
        if hasattr(client, '__aenter__'):
            await client.__aenter__()

        logger.info("=" * 80)
        logger.info("开始测试 /help 命令")
        logger.info("=" * 80)

        # 发送 /help 命令
        accumulated_content = ""
        event_count = 0

        logger.info("\n📤 发送命令: /help\n")

        async for event in client.send_message(
            session_id="test_session",
            message="/help"
        ):
            event_count += 1

            logger.info(f"\n{'─' * 80}")
            logger.info(f"事件 #{event_count}")
            logger.info(f"类型: {event.event_type}")
            logger.info(f"内容长度: {len(event.content) if event.content else 0}")

            # 显示内容前 200 字符
            if event.content:
                preview = event.content[:200]
                if len(event.content) > 200:
                    preview += "...(截断)"
                logger.info(f"内容预览: {repr(preview)}")

            if event.event_type == StreamEventType.TEXT_DELTA:
                accumulated_content += event.content
                logger.info(f"✅ TEXT_DELTA - 累积总长度: {len(accumulated_content)}")

            elif event.event_type == StreamEventType.TOOL_USE:
                logger.info(f"🔧 TOOL_USE - 工具: {event.tool_name}")
                logger.info(f"   输入: {event.tool_input}")

            elif event.event_type == StreamEventType.ERROR:
                logger.error(f"❌ ERROR - {event.content}")

            elif event.event_type == StreamEventType.END:
                logger.info(f"🏁 END - 流式响应结束")
                logger.info(f"总事件数: {event_count}")
                logger.info(f"总内容长度: {len(accumulated_content)}")
                break

        logger.info("\n" + "=" * 80)
        logger.info("完整响应内容:")
        logger.info("=" * 80)
        print(accumulated_content)
        logger.info("\n" + "=" * 80)
        logger.info(f"响应统计:")
        logger.info(f"  - 事件总数: {event_count}")
        logger.info(f"  - 内容长度: {len(accumulated_content)} 字符")
        logger.info(f"  - TEXT_DELTA 事件: {sum(1 for _ in filter(lambda e: e.event_type == StreamEventType.TEXT_DELTA, []))}")
        logger.info("=" * 80)

    finally:
        # 清理
        if hasattr(client, '__aexit__'):
            await client.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(test_help_command())
