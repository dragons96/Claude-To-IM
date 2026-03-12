# tests/test_help_commands.py
"""测试 /help:mcp 和 /help:command 命令"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from src.bridges.feishu.command_handler import CommandHandler
from src.core.message import IMMessage, MessageType


class TestHelpMcpCommand:
    """测试 /help:mcp 命令"""

    @pytest.fixture
    def command_handler(self):
        """创建命令处理器实例"""
        handler = CommandHandler()

        # 创建 mock bridge
        bridge = Mock()
        bridge.platform = "feishu"

        # 创建 mock claude_adapter
        claude_adapter = Mock()
        claude_adapter.get_mcp_tools_info = AsyncMock()
        bridge.claude_adapter = claude_adapter

        # 创建 mock session_manager
        session_manager = Mock()
        bridge.session_manager = session_manager

        handler.set_bridge(bridge)
        return handler

    @pytest.fixture
    def test_message(self):
        """创建测试消息"""
        return IMMessage(
            content="/help:mcp",
            message_type=MessageType.TEXT,
            message_id="test_msg_id",
            session_id="test_session",
            user_id="test_user",
            user_name="Test User",
            is_private_chat=True
        )

    @pytest.mark.asyncio
    async def test_help_mcp_with_servers(self, command_handler, test_message):
        """测试显示 MCP 工具信息 - 有服务器"""
        # Mock MCP 信息
        mcp_info = {
            "mcpServers": [
                {
                    "name": "test-server",
                    "status": "connected",
                    "config": {
                        "type": "stdio",
                        "scope": "user"
                    },
                    "serverInfo": {
                        "name": "Test Server",
                        "version": "1.0.0"
                    },
                    "tools": [
                        {
                            "name": "test_tool",
                            "description": "A test tool for testing"
                        },
                        {
                            "name": "another_tool",
                            "description": "Another test tool"
                        }
                    ]
                }
            ]
        }

        command_handler.bridge.claude_adapter.get_mcp_tools_info.return_value = mcp_info

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "🔌 MCP 工具详情" in result
        assert "test-server" in result
        assert "✅" in result
        assert "test_tool" in result
        assert "another_tool" in result

    @pytest.mark.asyncio
    async def test_help_mcp_no_servers(self, command_handler, test_message):
        """测试显示 MCP 工具信息 - 无服务器"""
        # Mock 空的 MCP 信息
        mcp_info = {"mcpServers": []}

        command_handler.bridge.claude_adapter.get_mcp_tools_info.return_value = mcp_info

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "🔌 MCP 工具详情" in result
        assert "当前没有加载的 MCP 服务器" in result

    @pytest.mark.asyncio
    async def test_help_mcp_with_failed_server(self, command_handler, test_message):
        """测试显示 MCP 工具信息 - 有失败的服务器"""
        # Mock 包含失败服务器的 MCP 信息
        mcp_info = {
            "mcpServers": [
                {
                    "name": "failed-server",
                    "status": "failed",
                    "config": {
                        "type": "stdio",
                        "scope": "user"
                    },
                    "error": "Connection refused"
                }
            ]
        }

        command_handler.bridge.claude_adapter.get_mcp_tools_info.return_value = mcp_info

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "🔌 MCP 工具详情" in result
        assert "failed-server" in result
        assert "❌" in result
        assert "Connection refused" in result

    @pytest.mark.asyncio
    async def test_help_mcp_error(self, command_handler, test_message):
        """测试获取 MCP 信息失败"""
        # Mock 错误响应
        command_handler.bridge.claude_adapter.get_mcp_tools_info.return_value = {
            "error": "Connection timeout"
        }

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "❌" in result
        assert "Connection timeout" in result


class TestHelpCommandCommand:
    """测试 /help:command 命令"""

    @pytest.fixture
    def command_handler(self):
        """创建命令处理器实例"""
        handler = CommandHandler()

        # 创建 mock bridge
        bridge = Mock()
        bridge.platform = "feishu"

        # 创建 mock claude_adapter
        claude_adapter = Mock()
        claude_adapter.get_commands_info = AsyncMock()
        bridge.claude_adapter = claude_adapter

        # 创建 mock session_manager
        session_manager = Mock()
        bridge.session_manager = session_manager

        handler.set_bridge(bridge)
        return handler

    @pytest.fixture
    def test_message(self):
        """创建测试消息"""
        return IMMessage(
            content="/help:command",
            message_type=MessageType.TEXT,
            message_id="test_msg_id",
            session_id="test_session",
            user_id="test_user",
            user_name="Test User",
            is_private_chat=True
        )

    @pytest.mark.asyncio
    async def test_help_command_dict_format(self, command_handler, test_message):
        """测试显示命令信息 - 字典格式"""
        # Mock 命令信息
        commands_info = {
            "slashCommands": {
                "plan": {
                    "description": "Create implementation plan"
                },
                "commit": {
                    "description": "Create git commit"
                },
                "test": {
                    "description": "Run tests"
                }
            },
            "systemCommands": ["cmd1", "cmd2"]
        }

        command_handler.bridge.claude_adapter.get_commands_info.return_value = commands_info

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "🔧 可用命令详情" in result
        assert "/plan" in result
        assert "/commit" in result
        assert "/test" in result
        assert "Create implementation plan" in result
        assert "系统命令" in result

    @pytest.mark.asyncio
    async def test_help_command_list_format(self, command_handler, test_message):
        """测试显示命令信息 - 列表格式"""
        # Mock 命令信息
        commands_info = {
            "slashCommands": [
                {"name": "plan", "description": "Create plan"},
                {"name": "commit", "description": "Create commit"}
            ],
            "systemCommands": ["cmd1", "cmd2", "cmd3"]
        }

        command_handler.bridge.claude_adapter.get_commands_info.return_value = commands_info

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "🔧 可用命令详情" in result
        assert "/plan" in result
        assert "/commit" in result
        assert "系统命令: 3 个" in result

    @pytest.mark.asyncio
    async def test_help_command_no_commands(self, command_handler, test_message):
        """测试显示命令信息 - 无命令"""
        # Mock 空的命令信息
        commands_info = {
            "slashCommands": {},
            "systemCommands": []
        }

        command_handler.bridge.claude_adapter.get_commands_info.return_value = commands_info

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "🔧 可用命令详情" in result
        assert "当前没有可用的斜杠命令" in result

    @pytest.mark.asyncio
    async def test_help_command_error(self, command_handler, test_message):
        """测试获取命令信息失败"""
        # Mock 错误响应
        command_handler.bridge.claude_adapter.get_commands_info.return_value = {
            "error": "Failed to fetch commands"
        }

        # 执行命令
        result = await command_handler.handle(test_message)

        # 验证结果
        assert "❌" in result
        assert "Failed to fetch commands" in result


class TestHelpCommandIntegration:
    """集成测试"""

    @pytest.fixture
    def command_handler(self):
        """创建命令处理器实例"""
        handler = CommandHandler()

        # 创建 mock bridge
        bridge = Mock()
        bridge.platform = "feishu"

        # 创建 mock claude_adapter
        claude_adapter = Mock()
        claude_adapter.get_mcp_tools_info = AsyncMock()
        claude_adapter.get_commands_info = AsyncMock()
        bridge.claude_adapter = claude_adapter

        # 创建 mock session_manager
        session_manager = Mock()
        bridge.session_manager = session_manager

        handler.set_bridge(bridge)
        return handler

    @pytest.mark.asyncio
    async def test_help_includes_new_commands(self, command_handler):
        """测试 /help 命令包含新命令的说明"""
        message = IMMessage(
            content="/help",
            message_type=MessageType.TEXT,
            message_id="test_msg_id",
            session_id="test_session",
            user_id="test_user",
            user_name="Test User",
            is_private_chat=True
        )

        # 执行命令
        result = await command_handler.handle(message)

        # 验证新命令在帮助信息中
        assert "/help:mcp" in result
        assert "/help:command" in result
        assert "MCP 工具信息" in result
        assert "可用命令" in result

    @pytest.mark.asyncio
    async def test_command_routing(self, command_handler):
        """测试命令路由是否正确"""
        # 测试 /help:mcp 路由
        message1 = IMMessage(
            content="/help:mcp",
            message_type=MessageType.TEXT,
            message_id="test_msg_id_1",
            session_id="test_session",
            user_id="test_user",
            user_name="Test User",
            is_private_chat=True
        )

        command_handler.bridge.claude_adapter.get_mcp_tools_info.return_value = {"mcpServers": []}
        result1 = await command_handler.handle(message1)
        assert "🔌 MCP 工具详情" in result1

        # 测试 /help:command 路由
        message2 = IMMessage(
            content="/help:command",
            message_type=MessageType.TEXT,
            message_id="test_msg_id_2",
            session_id="test_session",
            user_id="test_user",
            user_name="Test User",
            is_private_chat=True
        )

        command_handler.bridge.claude_adapter.get_commands_info.return_value = {"slashCommands": {}}
        result2 = await command_handler.handle(message2)
        assert "🔧 可用命令详情" in result2
