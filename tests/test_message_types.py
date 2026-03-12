"""测试 SDK 消息类型，找出 task 相关消息的来源"""
import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ResultMessage,
    TaskProgressMessage,
    TaskNotificationMessage
)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_message_types():
    """测试所有消息类型"""

    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN"),
            "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL"),
        },
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_turns=10,
        include_partial_messages=True
    )

    client = ClaudeSDKClient(options)

    try:
        if hasattr(client, '__aenter__'):
            await client.__aenter__()

        logger.info("=" * 80)
        logger.info("开始捕获所有消息类型")
        logger.info("=" * 80)

        # 发送一个会触发子代理的命令
        message_count = 0
        system_message_subtypes = {}

        await client.query("/superpowers:", "test_session")

        async for sdk_message in client.receive_messages():
            message_count += 1
            msg_type = type(sdk_message).__name__

            logger.info(f"\n{'─' * 80}")
            logger.info(f"消息 #{message_count}")
            logger.info(f"类型: {msg_type}")

            if isinstance(sdk_message, SystemMessage):
                subtype = sdk_message.subtype
                system_message_subtypes[subtype] = system_message_subtypes.get(subtype, 0) + 1

                logger.info(f"  subtype: {subtype}")
                logger.info(f"  data keys: {list(sdk_message.data.keys()) if sdk_message.data else []}")

                # 显示关键数据
                if sdk_message.data:
                    for key, value in list(sdk_message.data.items())[:3]:  # 只显示前3个
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        logger.info(f"  {key}: {value}")

            elif isinstance(sdk_message, TaskProgressMessage):
                logger.info(f"  description: {sdk_message.description}")
                logger.info("  ✅ 这是 TaskProgressMessage！")

            elif isinstance(sdk_message, TaskNotificationMessage):
                logger.info(f"  subtype: {sdk_message.subtype}")
                logger.info("  ✅ 这是 TaskNotificationMessage！")

            elif isinstance(sdk_message, AssistantMessage):
                logger.info(f"  content blocks: {len(sdk_message.content)}")

            elif isinstance(sdk_message, ResultMessage):
                logger.info(f"  is_error: {sdk_message.is_error}")
                logger.info("  🏁 流结束")
                break

        # 统计 SystemMessage subtypes
        logger.info("\n" + "=" * 80)
        logger.info("SystemMessage subtype 统计:")
        logger.info("=" * 80)
        for subtype, count in sorted(system_message_subtypes.items()):
            logger.info(f"  {subtype}: {count} 次")

        logger.info(f"\n总消息数: {message_count}")

    finally:
        if hasattr(client, '__aexit__'):
            await client.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(test_message_types())
