# src/bridges/feishu/command_handler.py
from typing import Optional
from src.core.message import IMMessage
from src.core.exceptions import SessionNotFoundError, PermissionDeniedError


class CommandHandler:
    """飞书命令处理器 - 处理用户发送的斜杠命令"""

    def __init__(self, bridge=None):
        """初始化命令处理器

        Args:
            bridge: FeishuBridge 实例,包含 session_manager 等依赖（可选，支持延迟设置）
        """
        self.bridge = bridge
        self._session_manager = None
        self._platform = None

        # 如果提供了 bridge，则立即初始化属性
        if bridge is not None:
            self._init_from_bridge()

    def _init_from_bridge(self):
        """从 bridge 初始化属性"""
        if self.bridge is not None:
            self._session_manager = self.bridge.session_manager
            self._platform = self.bridge.platform

    def set_bridge(self, bridge):
        """设置 bridge（用于延迟初始化）

        Args:
            bridge: FeishuBridge 实例
        """
        self.bridge = bridge
        self._init_from_bridge()

    @property
    def session_manager(self):
        """获取 session_manager"""
        if self._session_manager is None:
            raise RuntimeError("CommandHandler.bridge 尚未设置，请先调用 set_bridge() 或确保初始化时传入了 bridge")
        return self._session_manager

    @property
    def platform(self):
        """获取 platform"""
        if self._platform is None:
            raise RuntimeError("CommandHandler.bridge 尚未设置，请先调用 set_bridge() 或确保初始化时传入了 bridge")
        return self._platform

    async def handle(self, message: IMMessage) -> Optional[str]:
        """处理命令消息

        Args:
            message: IM 消息对象

        Returns:
            Optional[str]: 命令执行结果文本,如果不是命令则返回 None
        """
        # 检查是否是命令
        if not message.content or not message.content.startswith("/"):
            return None

        # 解析命令
        parts = message.content.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # 路由到具体的命令处理方法
        if command == "/new":
            return await self._handle_new(message, args)
        elif command == "/sessions":
            return await self._handle_sessions(message, args)
        elif command == "/switch":
            return await self._handle_switch(message, args)
        elif command == "/delete":
            return await self._handle_delete(message, args)
        elif command == "/session:exec":
            return await self._handle_session_exec(message, args)
        elif command == "/help":
            return await self._handle_help(message, args)
        elif command == "/help:mcp":
            return await self._handle_help_mcp(message, args)
        elif command == "/help:command":
            return await self._handle_help_command(message, args)
        elif command.startswith("/claude:"):
            # Claude 命令: /claude:plan xxx -> 提取 "plan" 和 "xxx"
            claude_cmd_name = command.split(":", 1)[1]  # 提取 "plan"
            claude_cmd_args = args  # "xxx" 部分
            return await self._handle_claude_command(message, claude_cmd_name, claude_cmd_args)
        else:
            return self._handle_unknown(message, command)

    async def _handle_new(self, message: IMMessage, args: str) -> str:
        """处理 /new 命令 - 创建新会话

        Args:
            message: 消息对象
            args: 命令参数 (可选的路径)

        Returns:
            str: 命令执行结果
        """
        try:
            # 解析工作目录
            work_directory = args.strip() if args.strip() else None

            # 调用 session_manager 创建会话
            # 如果没有指定路径，session_manager 会自动使用 Claude 会话ID作为目录名
            claude_session = await self.session_manager.create_session(
                platform=self.platform,
                platform_session_id=message.session_id,
                work_directory=work_directory,
                summary=f"通过 /new 创建"
            )

            # 获取数据库记录，使用数据库 id 作为用户可见的会话ID
            im_session = await self.session_manager.storage.get_im_session_by_platform_id(
                self.platform, message.session_id
            )
            db_session = await self.session_manager.storage.get_claude_session_by_sdk_id(
                claude_session.session_id
            )

            display_session_id = db_session.id if db_session else claude_session.session_id
            work_dir = getattr(claude_session, 'work_directory', work_directory)

            # 返回成功消息，并请求 AI 自我介绍
            return {
                "type": "new_session_created",
                "message": f"""✅ 成功创建新会话

📋 会话信息:
• 会话ID: {display_session_id}
• 工作目录: {work_dir}

💡 提示:
• 现在可以发送消息给 Claude 了
• 使用 /sessions 查看所有会话
• 使用 /help 查看所有可用命令""",
                "intro_message": "你好！请简单介绍一下你自己，包括你是什么助手，能帮助用户做什么。"
            }

        except PermissionDeniedError as e:
            return f"""❌ 权限不足

{str(e)}

💡 提示:
• 使用 /new 不带参数，将在默认目录创建会话
• 确保目录路径在允许访问的列表中
• 联系管理员添加目录权限"""

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"创建会话失败: {e}", exc_info=True)
            return f"""❌ 创建会话失败

错误: {str(e)}

💡 提示:
• 尝试使用 /new 不带参数
• 检查路径是否正确
• 联系管理员获取帮助"""

    async def _handle_sessions(self, message: IMMessage, args: str) -> str:
        """处理 /sessions 命令 - 列出所有会话

        Args:
            message: 消息对象
            args: 命令参数 (忽略)

        Returns:
            str: 会话列表
        """
        try:
            # 获取会话列表
            sessions = await self.session_manager.list_sessions(
                platform=self.platform,
                platform_session_id=message.session_id
            )

            if not sessions:
                return "📋 当前没有可用的会话\n使用 /new 创建新会话"

            # 格式化输出
            lines = ["📋 会话列表:"]
            for idx, session in enumerate(sessions, 1):
                active_marker = "✨ " if session.get("is_active") else "   "
                # 使用数据库 id 作为用户可见的会话ID
                session_id = session.get("id", "unknown")
                summary = session.get("summary", "无摘要")
                work_dir = session.get("work_directory", "未知目录")

                lines.append(f"{active_marker}{idx}. {session_id}")
                lines.append(f"   📁 {work_dir}")
                if summary:
                    lines.append(f"   📝 {summary}")

            return "\n".join(lines)

        except SessionNotFoundError as e:
            return f"❌ {str(e)}\n使用 /new 创建新会话"
        except Exception as e:
            return f"❌ 获取会话列表失败: {str(e)}"

    async def _handle_switch(self, message: IMMessage, args: str) -> str:
        """处理 /switch 命令 - 切换活跃会话

        Args:
            message: 消息对象
            args: 会话ID（数据库id）

        Returns:
            str: 切换结果
        """
        try:
            # 解析会话ID（数据库id）
            db_session_id = args.strip()
            if not db_session_id:
                return "❌ 请指定要切换的会话ID\n用法: /switch <session_id>"

            # 切换会话（使用数据库id）
            session = await self.session_manager.switch_session_by_db_id(
                platform=self.platform,
                platform_session_id=message.session_id,
                db_session_id=db_session_id
            )

            work_dir = session.get("work_directory", "未知目录")
            display_id = session.get("id", db_session_id)
            return f"✅ 成功切换到会话\n会话ID: {display_id}\n工作目录: {work_dir}"

        except SessionNotFoundError as e:
            return f"❌ {str(e)}\n使用 /sessions 查看可用会话"
        except Exception as e:
            return f"❌ 切换会话失败: {str(e)}"

    async def _handle_delete(self, message: IMMessage, args: str) -> str:
        """处理 /delete 命令 - 删除会话

        Args:
            message: 消息对象
            args: 会话ID（数据库id）

        Returns:
            str: 删除结果
        """
        try:
            # 解析会话ID（数据库id）
            db_session_id = args.strip()
            if not db_session_id:
                return "❌ 请指定要删除的会话ID\n用法: /delete <session_id>"

            # 删除会话（使用数据库id）
            session_info = await self.session_manager.delete_session_by_db_id(
                platform=self.platform,
                platform_session_id=message.session_id,
                db_session_id=db_session_id
            )

            return f"""✅ 成功删除会话

📋 已删除会话信息:
• 会话ID: {session_info['id']}
• 工作目录: {session_info['work_directory']}

💡 提示:
• 使用 /sessions 查看剩余会话
• 使用 /new 创建新会话"""

        except SessionNotFoundError as e:
            return f"❌ {str(e)}\n使用 /sessions 查看可用会话"
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"删除会话失败: {e}", exc_info=True)
            return f"❌ 删除会话失败: {str(e)}"

    async def _handle_session_exec(self, message: IMMessage, args: str):
        """处理 /session:exec 命令 - 在指定会话中执行内容

        Args:
            message: 消息对象
            args: 命令参数 (会话ID + 内容)

        Returns:
            Dict: 特殊标记，表示需要在指定会话中执行
        """
        try:
            # 解析参数: 第一个空格前是会话ID，后面都是要执行的内容
            parts = args.strip().split(maxsplit=1)
            if len(parts) < 2:
                return """❌ 参数不足

用法: /session:exec <会话ID> <内容>

示例:
/session:exec abc123-def456-7890 帮我分析这段代码

💡 提示:
• 会话ID可以通过 /sessions 查看
• 这个命令可以在不切换活跃会话的情况下，向指定会话发送消息"""

            target_session_id = parts[0].strip()
            content_to_exec = parts[1].strip()

            # 验证目标会话是否存在（使用数据库id）
            im_session = await self.session_manager.storage.get_im_session_by_platform_id(
                self.platform, message.session_id
            )

            if not im_session:
                return f"❌ 平台会话不存在: {message.session_id}"

            target_session = await self.session_manager.storage.get_claude_session(target_session_id)

            if not target_session or target_session.im_session_id != im_session.id:
                return f"""❌ 会话不存在或不属于当前平台会话

会话ID: {target_session_id}

💡 提示:
• 使用 /sessions 查看可用的会话ID"""

            # 构造新的消息对象，内容替换为要执行的内容
            from src.core.message import IMMessage
            import copy

            exec_message = copy.copy(message)
            exec_message.content = content_to_exec

            # 返回特殊标记，表示需要在指定会话中执行
            return {
                "type": "exec_in_session",
                "claude_session_id": target_session.session_id,  # SDK session_id（内部使用）
                "db_session_id": target_session.id,  # 数据库id（用户可见）
                "message": exec_message
            }

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"处理 session-exec 命令失败: {e}", exc_info=True)
            return f"❌ 执行命令失败: {str(e)}"

    def _handle_unknown(self, message: IMMessage, command: str) -> str:
        """处理未知命令

        Args:
            message: 消息对象
            command: 未知命令

        Returns:
            str: 帮助信息
        """
        return f"""❓ 未知命令: {command}

💡 输入 /help 查看所有可用命令和用法"""

    async def _handle_help(self, message: IMMessage, args: str) -> str:
        """处理 /help 命令 - 显示帮助信息

        Args:
            message: 消息对象
            args: 命令参数 (忽略)

        Returns:
            str: 帮助信息
        """
        return """📖 Claude Code Bot 命令帮助

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 会话管理命令:

/new [路径]
  创建新会话
  • 无参数: 在默认目录创建会话
  • 指定路径: 在指定目录创建会话 (需要权限)

  示例:
  /new
  /new D:/Projects/myproject

/sessions
  列出所有会话
  • 显示所有可用会话的ID和工作目录
  • ✨ 标记表示当前活跃会话

  示例:
  /sessions

/switch <会话ID>
  切换到指定会话
  • 切换后,消息将发送到该会话
  • 会话ID通过 /sessions 查看

  示例:
  /switch abc123-def456-7890

/delete <会话ID>
  删除指定会话
  • 删除会话及其消息历史
  • 删除后无法恢复
  • 会话ID通过 /sessions 查看

  示例:
  /delete abc123-def456-7890

/session:exec <会话ID> <内容>
  在指定会话中执行命令
  • 不切换活跃会话的情况下向指定会话发送消息
  • 适合同时管理多个会话
  • 会话ID通过 /sessions 查看

  示例:
  /session:exec abc123-def456-7890 帮我分析这段代码
  /session:exec xyz789-0123-4567 运行测试

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 Claude Code CLI 命令:

/claude:{command} [参数]
  执行 Claude Code CLI 命令
  • 所有 Claude CLI 的斜杠命令都支持
  • 命令结果通过流式响应返回

  常用命令示例:
  /claude:plan                 - 创建实施计划

  完整示例:
  /claude:plan 实现用户登录功能

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 帮助命令:

/help
  显示此帮助信息

/help:mcp
  查看已加载的 MCP 工具信息
  • 显示所有 MCP 服务器的连接状态
  • 显示每个服务器提供的工具列表
  • 显示工具的详细描述

  示例:
  /help:mcp

/help:command
  查看已加载的可用命令
  • 显示所有可用的斜杠命令
  • 显示命令的详细描述
  • 显示系统命令列表

  示例:
  /help:command

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 使用提示:
• 私聊: 直接发送消息即可
• 群聊: 需要 @机器人 才会响应
• 支持引用/回复消息
• 支持文件和图片
• Claude CLI 命令需要在活跃会话中执行
• 使用 /session:exec 可以在不切换会话的情况下管理多个会话
• 使用 /help:mcp 和 /help:command 查看详细的工具和命令信息

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    async def _handle_claude_command(self, message: IMMessage, cmd_name: str, cmd_args: str):
        """处理 Claude 命令

        执行 Claude Code CLI 的命令，如 /plan, /commit 等

        Args:
            message: 消息对象
            cmd_name: Claude 命令名称 (如 "plan", "commit")
            cmd_args: 命令参数

        Returns:
            None 或 IMMessage: None 表示错误，返回 IMMessage 表示需要转发到 Claude
        """
        try:
            # 获取当前活跃会话
            sessions = await self.session_manager.list_sessions(
                platform=self.platform,
                platform_session_id=message.session_id
            )

            # 找到活跃会话
            active_session = None
            for session in sessions:
                if session.get("is_active"):
                    active_session = session
                    break

            if not active_session:
                return f"""❌ 没有找到活跃的会话

请先使用 /new 创建会话，然后发送命令

💡 输入 /help 查看所有可用命令"""

            # 构造完整的命令消息（Claude SDK 会识别以 / 开头的命令）
            full_command = f"/{cmd_name}"
            if cmd_args.strip():
                full_command += f" {cmd_args}"

            # 返回转换后的命令消息，让 adapter.py 调用 route_to_claude
            # 注意：这里修改原消息的 content，但保留其他属性
            from src.core.message import IMMessage
            import copy

            command_message = copy.copy(message)
            command_message.content = full_command

            # 返回特殊标记，表示这是一个需要转发到 Claude 的命令
            return {"type": "forward_to_claude", "message": command_message}

        except SessionNotFoundError as e:
            return f"❌ {str(e)}\n使用 /new 创建会话"
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"执行 Claude 命令失败: {e}", exc_info=True)
            return f"❌ 执行命令失败: {str(e)}\n请检查会话状态"

    async def _handle_help_mcp(self, message: IMMessage, args: str) -> str:
        """处理 /help:mcp 命令 - 显示 MCP 工具信息

        Args:
            message: 消息对象
            args: 命令参数 (忽略)

        Returns:
            str: MCP 工具信息
        """
        try:
            # 获取 Claude 适配器
            claude_adapter = self.bridge.claude_adapter

            # 检查是否有 get_mcp_tools_info 方法
            if not hasattr(claude_adapter, 'get_mcp_tools_info'):
                return "❌ 当前适配器不支持查询 MCP 工具信息"

            # 获取 MCP 工具信息
            mcp_info = await claude_adapter.get_mcp_tools_info()

            # 检查是否有错误
            if "error" in mcp_info:
                return f"❌ 获取 MCP 工具信息失败: {mcp_info['error']}"

            # 格式化输出
            lines = ["🔌 MCP 工具详情", "=" * 50]

            mcp_servers = mcp_info.get("mcpServers", [])

            if not mcp_servers:
                lines.append("\n📦 当前没有加载的 MCP 服务器")
                return "\n".join(lines)

            lines.append(f"\n📦 已加载 {len(mcp_servers)} 个 MCP 服务器:\n")

            for server in mcp_servers:
                # 状态图标
                status_icon = {
                    "connected": "✅",
                    "pending": "⏳",
                    "failed": "❌",
                    "needs-auth": "🔒",
                    "disabled": "⚪"
                }.get(server.get("status", "unknown"), "❓")

                server_name = server.get("name", "Unknown")
                lines.append(f"{status_icon} **{server_name}**")

                # 配置信息
                config = server.get("config", {})
                config_type = config.get("type", "unknown")
                scope = config.get("scope", "unknown")
                lines.append(f"   类型: {config_type}")
                lines.append(f"   作用域: {scope}")

                # 服务器信息 (如果已连接)
                if server.get("status") == "connected":
                    server_info = server.get("serverInfo", {})
                    name = server_info.get("name", "Unknown")
                    version = server_info.get("version", "Unknown")
                    lines.append(f"   版本: {name} v{version}")

                    # 工具列表
                    tools = server.get("tools", [])
                    if tools:
                        lines.append(f"   工具: {len(tools)} 个")
                        for tool in tools:
                            tool_name = tool.get("name", "Unknown")
                            tool_desc = tool.get("description", "")
                            if tool_desc:
                                # 截断过长的描述
                                if len(tool_desc) > 60:
                                    tool_desc = tool_desc[:57] + "..."
                                lines.append(f"     • /{tool_name}")
                                lines.append(f"       {tool_desc}")
                            else:
                                lines.append(f"     • /{tool_name}")
                    else:
                        lines.append(f"   工具: 无")

                # 错误信息 (如果失败)
                elif server.get("status") == "failed":
                    error = server.get("error", "Unknown error")
                    lines.append(f"   错误: {error}")

                lines.append("")  # 空行分隔

            lines.append("=" * 50)
            return "\n".join(lines)

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"获取 MCP 工具信息失败: {e}", exc_info=True)
            return f"❌ 获取 MCP 工具信息失败: {str(e)}"

    async def _handle_help_command(self, message: IMMessage, args: str) -> str:
        """处理 /help:command 命令 - 显示可用命令列表

        Args:
            message: 消息对象
            args: 命令参数 (忽略)

        Returns:
            str: 可用命令列表
        """
        try:
            # 获取 Claude 适配器
            claude_adapter = self.bridge.claude_adapter

            # 检查是否有 get_commands_info 方法
            if not hasattr(claude_adapter, 'get_commands_info'):
                return "❌ 当前适配器不支持查询命令信息"

            # 获取命令信息
            commands_info = await claude_adapter.get_commands_info()

            # 检查是否有错误
            if "error" in commands_info:
                return f"❌ 获取命令信息失败: {commands_info['error']}"

            # 格式化输出
            lines = ["🔧 可用命令详情", "=" * 50]

            # 获取斜杠命令
            slash_commands = (
                commands_info.get("slashCommands") or
                commands_info.get("commands") or
                commands_info.get("availableCommands") or
                {}
            )

            if not slash_commands:
                lines.append("\n📋 当前没有可用的斜杠命令")
            else:
                lines.append(f"\n📋 斜杠命令:\n")

                # 处理不同格式的命令数据
                if isinstance(slash_commands, dict):
                    # 字典格式: {"command": {...}}
                    sorted_commands = sorted(slash_commands.items())
                    for cmd_name, cmd_info in sorted_commands:
                        lines.append(f"/{cmd_name}")
                        # 如果有描述信息,显示描述
                        if isinstance(cmd_info, dict) and cmd_info.get("description"):
                            desc = cmd_info["description"]
                            # 截断过长的描述
                            if len(desc) > 80:
                                desc = desc[:77] + "..."
                            lines.append(f"  {desc}")
                        lines.append("")  # 空行分隔

                elif isinstance(slash_commands, list):
                    # 列表格式: [{name: "...", description: "..."}]
                    for cmd in slash_commands:
                        if isinstance(cmd, dict):
                            cmd_name = cmd.get("name", cmd.get("command", "unknown"))
                            lines.append(f"/{cmd_name}")

                            # 显示描述
                            desc = cmd.get("description", "")
                            if desc:
                                if len(desc) > 80:
                                    desc = desc[:77] + "..."
                                lines.append(f"  {desc}")
                        else:
                            # 简单字符串
                            lines.append(f"/{cmd}")
                        lines.append("")  # 空行分隔

                else:
                    # 其他格式,直接转换
                    lines.append(f"{slash_commands}")

            # 获取系统命令
            system_commands = commands_info.get("systemCommands", [])
            if system_commands:
                lines.append(f"\n⚙️  系统命令: {len(system_commands)} 个")
                for cmd in system_commands[:10]:  # 只显示前10个
                    if isinstance(cmd, dict):
                        cmd_name = cmd.get("name", cmd.get("command", "unknown"))
                        lines.append(f"  • {cmd_name}")
                    else:
                        lines.append(f"  • {cmd}")
                if len(system_commands) > 10:
                    lines.append(f"  ... 还有 {len(system_commands) - 10} 个系统命令")

            lines.append("\n" + "=" * 50)
            lines.append("\n💡 提示:")
            lines.append("• 使用 /claude:{命令名} 执行上述斜杠命令")
            lines.append("• 使用 /help 查看所有可用命令")

            return "\n".join(lines)

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"获取命令信息失败: {e}", exc_info=True)
            return f"❌ 获取命令信息失败: {str(e)}"
