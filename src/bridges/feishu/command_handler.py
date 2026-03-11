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
        elif command == "/help":
            return await self._handle_help(message, args)
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

            # 如果没有指定路径,使用默认路径（飞书会话ID）
            if not work_directory:
                # 使用 session_manager 的默认会话根目录
                from pathlib import Path
                default_root = getattr(self.session_manager, 'default_session_root', '/tmp/claude_sessions')
                # 确保 default_root 是字符串或可转换为字符串
                if not isinstance(default_root, (str, Path)):
                    default_root = '/tmp/claude_sessions'
                elif isinstance(default_root, Path):
                    default_root = str(default_root)

                # 使用飞书会话ID作为目录名
                work_directory = str(Path(default_root) / message.session_id)

            # 调用 session_manager 创建会话
            claude_session = await self.session_manager.create_session(
                platform=self.platform,
                platform_session_id=message.session_id,
                work_directory=work_directory,
                summary=f"通过 /new 创建于 {message.session_id}"
            )

            session_id = getattr(claude_session, 'session_id', 'unknown')
            work_dir = getattr(claude_session, 'work_directory', work_directory)

            return f"""✅ 成功创建新会话

📋 会话信息:
• 会话ID: {session_id}
• 工作目录: {work_dir}

💡 提示:
• 现在可以发送消息给 Claude 了
• 使用 /sessions 查看所有会话
• 使用 /help 查看所有可用命令"""

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
            args: 会话ID

        Returns:
            str: 切换结果
        """
        try:
            # 解析会话ID
            session_id = args.strip()
            if not session_id:
                return "❌ 请指定要切换的会话ID\n用法: /switch <session_id>"

            # 切换会话
            session = await self.session_manager.switch_session(
                platform=self.platform,
                platform_session_id=message.session_id,
                claude_session_id=session_id
            )

            work_dir = session.get("work_directory", "未知目录")
            return f"✅ 成功切换到会话\n会话ID: {session_id}\n工作目录: {work_dir}"

        except SessionNotFoundError as e:
            return f"❌ {str(e)}\n使用 /sessions 查看可用会话"
        except Exception as e:
            return f"❌ 切换会话失败: {str(e)}"

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

  示例:
  /switch abc123-def456

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

/help
  显示此帮助信息

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 使用提示:
• 私聊: 直接发送消息即可
• 群聊: 需要 @机器人 才会响应
• 支持引用/回复消息
• 支持文件和图片
• Claude CLI 命令需要在活跃会话中执行

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
