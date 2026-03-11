# src/claude/sdk_adapter.py
from typing import Optional, List, Dict, Any, AsyncIterator
import uuid
import asyncio
import copy
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock
)
from src.core.claude_adapter import ClaudeAdapter, ClaudeSession
from src.core.message import StreamEvent, StreamEventType


class ClaudeSDKAdapter(ClaudeAdapter):
    """Claude SDK 适配器实现"""

    def __init__(self, options: ClaudeAgentOptions):
        """初始化适配器

        Args:
            options: Claude SDK 选项
        """
        self.options = options
        self.sessions: Dict[str, Dict[str, Any]] = {}

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
        if session_id is None:
            session_id = str(uuid.uuid4())

        # 为这个会话创建独立的 options，设置工作目录
        session_options = copy.copy(self.options)
        session_options.cwd = work_directory

        # 创建 SDK 客户端并建立连接
        client = ClaudeSDKClient(session_options)

        # 手动建立连接（不使用 async with，因为需要长期保持连接）
        if hasattr(client, '__aenter__'):
            # 调用异步上下文管理器的进入方法
            await client.__aenter__()

        # 存储会话信息
        session = ClaudeSession(
            session_id=session_id,
            work_directory=work_directory,
            is_active=True,
            metadata={"client": client}
        )

        self.sessions[session_id] = {
            "session": session,
            "client": client
        }

        return session

    async def close_session(self, session_id: str) -> None:
        """关闭指定的会话

        Args:
            session_id: 要关闭的会话 ID
        """
        import logging
        logger = logging.getLogger(__name__)

        if session_id in self.sessions:
            session_data = self.sessions[session_id]
            client = session_data["client"]

            # 退出异步上下文管理器（关闭连接）
            if hasattr(client, '__aexit__'):
                try:
                    # 使用 shield 保护关闭操作，避免被外部取消
                    import asyncio
                    try:
                        # 添加超时保护，避免无限等待
                        await asyncio.shield(
                            asyncio.wait_for(
                                client.__aexit__(None, None, None),
                                timeout=3.0
                            )
                        )
                    except asyncio.CancelledError:
                        # 忽略取消错误，继续清理
                        logger.debug(f"关闭会话 {session_id} 时被取消，继续清理")
                    except RuntimeError as e:
                        # 忽略 cancel scope 错误（跨任务关闭）
                        if "cancel scope" in str(e):
                            logger.debug(f"关闭会话 {session_id} 时遇到 cancel scope 错误，已忽略")
                        else:
                            raise
                except asyncio.TimeoutError:
                    logger.warning(f"关闭会话 {session_id} 超时")
                except Exception as e:
                    logger.warning(f"关闭会话 {session_id} 时出错: {e}")

            # 从会话字典中移除
            del self.sessions[session_id]

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
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"ClaudeSDKAdapter.send_message 被调用 - session_id: {session_id}")
        logger.debug(f"消息内容: {message[:100]}...")

        if session_id not in self.sessions:
            logger.error(f"会话不存在: {session_id}")
            raise ValueError(f"Session {session_id} not found")

        session_data = self.sessions[session_id]
        client = session_data["client"]

        logger.info(f"准备调用 client.query()...")
        # 发送查询
        await client.query(message, session_id)

        logger.info(f"client.query() 完成，开始接收流式响应...")

        # 接收流式响应
        result_received = False
        message_count = 0

        async for sdk_message in client.receive_messages():
            message_count += 1
            # 减少日志噪音：只记录非 SystemMessage 和非 StreamEvent 的消息
            message_type = type(sdk_message).__name__
            if message_type not in ["SystemMessage", "StreamEvent"]:
                logger.info(f"收到 SDK 消息 #{message_count}: 类型={message_type}")

            # 根据消息类型转换为 StreamEvent
            if isinstance(sdk_message, SystemMessage):
                # 减少日志噪音：注释掉详细的 SystemMessage 日志
                # logger.info(f"SystemMessage: subtype={sdk_message.subtype}, data={sdk_message.data}")

                # 检查是否是有用的系统消息
                if sdk_message.subtype == "command_output":
                    # 命令输出，可能包含有用信息
                    output = sdk_message.data.get("output", "")
                    if output:
                        logger.info(f"命令输出: {output[:200]}...")
                        yield StreamEvent(
                            event_type=StreamEventType.TEXT_DELTA,
                            content=output,
                            metadata={"session_id": session_id, "source": "command_output"}
                        )
                elif sdk_message.subtype == "error":
                    # 错误消息
                    error = sdk_message.data.get("error", "Unknown error")
                    logger.warning(f"系统错误: {error}")
                    yield StreamEvent(
                        event_type=StreamEventType.ERROR,
                        content=error,
                        metadata={"session_id": session_id}
                    )
                else:
                    # 其他系统消息，只记录日志
                    logger.debug(f"忽略系统消息: subtype={sdk_message.subtype}")
                continue
            elif isinstance(sdk_message, UserMessage):
                # 忽略用户消息（通常包含工具结果）
                logger.debug(f"忽略用户消息")
                continue
            elif isinstance(sdk_message, AssistantMessage):
                # 处理助手消息
                logger.info(f"处理 AssistantMessage，content 包含 {len(sdk_message.content)} 个 block")
                for block in sdk_message.content:
                    logger.debug(f"Block 类型: {type(block).__name__}")
                    if isinstance(block, TextBlock):
                        # 文本块
                        text_length = len(block.text)
                        logger.info(f"TextBlock: 长度={text_length}, 内容={block.text[:100]}...")
                        yield StreamEvent(
                            event_type=StreamEventType.TEXT_DELTA,
                            content=block.text,
                            metadata={"session_id": session_id}
                        )
                    elif isinstance(block, ToolUseBlock):
                        # 工具使用块
                        logger.info(f"ToolUseBlock: name={block.name}")

                        # 检查是否是 AskUserQuestion 工具
                        if block.name == "AskUserQuestion":
                            logger.info(f"检测到 AskUserQuestion 工具调用")

                            # 解析工具输入
                            tool_input = block.input
                            questions = tool_input.get("questions", [])

                            if questions:
                                # 提取第一个问题（简化处理，实际可能需要处理多个问题）
                                question_data = questions[0]
                                question_text = question_data.get("question", "")
                                options_data = question_data.get("options", [])
                                header = question_data.get("header", "")
                                multi_select = question_data.get("multiSelect", False)

                                # 转换选项格式
                                options = []
                                for opt in options_data:
                                    option_obj = {
                                        "label": opt.get("label", ""),
                                        "description": opt.get("description", ""),
                                        "value": opt.get("value", "")
                                    }
                                    options.append(option_obj)

                                logger.info(f"用户决策问题: {question_text}")
                                logger.info(f"选项数量: {len(options)}")

                                # 生成唯一的问题ID
                                import uuid
                                question_id = str(uuid.uuid4())

                                # 发送用户问题事件
                                yield StreamEvent(
                                    event_type=StreamEventType.USER_QUESTION,
                                    content=f"**{header}**\n\n{question_text}" if header else question_text,
                                    tool_name=block.name,
                                    tool_input=block.input,
                                    metadata={
                                        "session_id": session_id,
                                        "tool_id": block.id,
                                        "question_id": question_id
                                    },
                                    question_id=question_id,
                                    question=question_text,
                                    options=options,
                                    multi_select=multi_select
                                )
                                return  # 暂停流式响应，等待用户输入
                            else:
                                logger.warning("AskUserQuestion 工具缺少 questions 参数")
                        else:
                            # 其他工具调用，正常处理
                            yield StreamEvent(
                                event_type=StreamEventType.TOOL_USE,
                                content="",
                                tool_name=block.name,
                                tool_input=block.input,
                                metadata={
                                    "session_id": session_id,
                                    "tool_id": block.id
                                }
                            )
            elif isinstance(sdk_message, ResultMessage):
                # 结果消息，表示结束
                logger.info(f"收到 ResultMessage，结束流式响应")
                logger.info(f"ResultMessage 详情: is_error={sdk_message.is_error}, result={sdk_message.result}")

                # 检查是否有错误信息
                error_msg = None

                # 检查 is_error 标志
                if sdk_message.is_error:
                    error_msg = sdk_message.result or "Unknown error"

                # 检查 result 字段是否包含错误信息
                elif sdk_message.result:
                    result_str = str(sdk_message.result)
                    # 检查常见的错误模式
                    error_patterns = [
                        "Unknown skill",
                        "Unknown command",
                        "Error:",
                        "Failed:",
                        "not found",
                        "unrecognized"
                    ]
                    if any(pattern.lower() in result_str.lower() for pattern in error_patterns):
                        error_msg = result_str

                # 如果有错误，发送错误事件
                if error_msg:
                    logger.warning(f"ResultMessage 包含错误: {error_msg}")
                    yield StreamEvent(
                        event_type=StreamEventType.ERROR,
                        content=error_msg,
                        metadata={"session_id": session_id}
                    )
                else:
                    # 正常结束
                    result_received = True
                    yield StreamEvent(
                        event_type=StreamEventType.END,
                        content="",
                        metadata={"session_id": session_id}
                    )
                break

        # 如果没有收到 ResultMessage，也要发送 END 事件
        if not result_received:
            yield StreamEvent(
                event_type=StreamEventType.END,
                content="",
                metadata={"session_id": session_id}
            )

    async def get_session_info(self, session_id: str) -> Optional[ClaudeSession]:
        """获取会话信息

        Args:
            session_id: 会话 ID

        Returns:
            Optional[ClaudeSession]: 会话对象,如果不存在则返回 None
        """
        if session_id in self.sessions:
            return self.sessions[session_id]["session"]
        return None

    async def list_sessions(self, **kwargs) -> List[ClaudeSession]:
        """列出所有会话

        Args:
            **kwargs: 筛选条件

        Returns:
            List[ClaudeSession]: 会话列表
        """
        sessions = [
            session_data["session"]
            for session_data in self.sessions.values()
        ]

        # 如果有筛选条件，可以在这里应用
        # 目前简单返回所有会话

        return sessions

    async def display_config_info(self, logger) -> None:
        """显示 Claude SDK 配置信息

        包括:
        - MCP 服务器状态
        - 可用的命令
        - 权限规则

        Args:
            logger: 日志记录器
        """
        try:
            logger.info("=" * 60)
            logger.info("Claude SDK 配置信息")
            logger.info("=" * 60)

            # 创建一个临时客户端来查询配置
            temp_client = ClaudeSDKClient(self.options)

            # 连接到 CLI
            try:
                await temp_client.connect()

                # 获取 MCP 服务器状态
                try:
                    mcp_status = await temp_client.get_mcp_status()
                    mcp_servers = mcp_status.get("mcpServers", [])

                    if mcp_servers:
                        logger.info(f"\n📦 MCP 服务器 ({len(mcp_servers)} 个):")

                        for server in mcp_servers:
                            status_icon = {
                                "connected": "✅",
                                "pending": "⏳",
                                "failed": "❌",
                                "needs-auth": "🔒",
                                "disabled": "⚪"
                            }.get(server.get("status", "unknown"), "❓")

                            logger.info(f"  {status_icon} {server.get('name', 'Unknown')}")

                            # 显示配置信息
                            config = server.get("config", {})
                            config_type = config.get("type", "unknown")
                            scope = config.get("scope", "unknown")
                            logger.info(f"     类型: {config_type}, 作用域: {scope}")

                            # 显示工具信息（如果已连接）
                            if server.get("status") == "connected":
                                server_info = server.get("serverInfo", {})
                                name = server_info.get("name", "Unknown")
                                version = server_info.get("version", "Unknown")
                                logger.info(f"     版本: {name} v{version}")

                                tools = server.get("tools", [])
                                if tools:
                                    logger.info(f"     工具: {len(tools)} 个")
                                    for tool in tools[:5]:  # 只显示前5个
                                        tool_name = tool.get("name", "Unknown")
                                        logger.info(f"       - {tool_name}")
                                    if len(tools) > 5:
                                        logger.info(f"       ... 还有 {len(tools) - 5} 个工具")
                                else:
                                    logger.info(f"     工具: 无")

                            # 显示错误（如果失败）
                            elif server.get("status") == "failed":
                                error = server.get("error", "Unknown error")
                                logger.info(f"     错误: {error}")
                    else:
                        logger.info("\n📦 MCP 服务器: 无")

                except Exception as e:
                    logger.warning(f"获取 MCP 状态失败: {e}")

                # 获取服务器信息（包括可用命令）
                try:
                    server_info = await temp_client.get_server_info()
                    logger.debug(f"服务器信息原始数据: {server_info}")

                    if server_info:
                        logger.info("\n🔧 可用命令:")

                        # 显示 slash commands
                        # 注意：可能使用不同的字段名
                        slash_commands = (
                            server_info.get("slashCommands") or
                            server_info.get("commands") or
                            server_info.get("availableCommands") or
                            {}
                        )
                        if slash_commands:
                            if isinstance(slash_commands, dict):
                                cmd_count = len(slash_commands)
                                logger.info(f"  斜杠命令 ({cmd_count} 个):")
                                for cmd_name in list(slash_commands.keys())[:10]:
                                    logger.info(f"    /{cmd_name}")
                                if cmd_count > 10:
                                    logger.info(f"    ... 还有 {cmd_count - 10} 个命令")
                            elif isinstance(slash_commands, list):
                                cmd_count = len(slash_commands)
                                logger.info(f"  斜杠命令 ({cmd_count} 个):")
                                for cmd in slash_commands[:10]:
                                    if isinstance(cmd, dict):
                                        cmd_name = cmd.get("name", cmd.get("command", "unknown"))
                                    else:
                                        cmd_name = str(cmd)
                                    logger.info(f"    /{cmd_name}")
                                if cmd_count > 10:
                                    logger.info(f"    ... 还有 {cmd_count - 10} 个命令")
                        else:
                            logger.info("  斜杠命令: 无")
                            logger.debug(f"可用的字段: {list(server_info.keys())}")

                        # 显示系统命令
                        system_commands = server_info.get("systemCommands", [])
                        if system_commands:
                            logger.info(f"  系统命令: {len(system_commands)} 个")
                        else:
                            logger.info("  系统命令: 无")
                    else:
                        logger.info("\n🔧 可用命令:")
                        logger.info("  服务器信息为空")

                except Exception as e:
                    logger.warning(f"获取服务器信息失败: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())

                logger.info("=" * 60)

            except Exception as e:
                logger.warning(f"连接到 Claude CLI 失败: {e}")
                logger.info("提示: 配置信息需要 Claude CLI 正在运行")

        except Exception as e:
            logger.warning(f"显示配置信息失败: {e}")
