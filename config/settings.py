# config/settings.py
"""配置管理模块

使用 pydantic-settings 管理应用配置，支持从 .env 文件加载。
"""
import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent


class Settings(BaseSettings):
    """应用配置类

    从环境变量和 .env 文件加载配置。
    所有字段都有类型验证和默认值。
    """

    # 应用配置
    APP_NAME: str = "claude-to-im"
    DEBUG: bool = False

    # 数据库配置
    DATABASE_URL: str

    # 会话配置
    DEFAULT_SESSION_ROOT: str = Field(default="./sessions", description="默认会话根目录")
    SESSION_TIMEOUT_HOURS: int = Field(default=24, description="会话超时时间（小时）")
    MAX_SESSIONS_PER_IM: int = Field(default=10, description="每个IM的最大会话数")

    # 权限配置（逗号分隔的目录列表）
    ALLOWED_DIRECTORIES: str = Field(default="", description="允许访问的目录列表（逗号分隔）")

    # Claude SDK 配置
    ANTHROPIC_AUTH_TOKEN: str = Field(default="", description="Anthropic API 认证令牌")
    ANTHROPIC_BASE_URL: str = Field(
        default="https://api.anthropic.com", description="Anthropic API 基础URL"
    )
    ANTHROPIC_MODEL: str = Field(default="claude-sonnet-4-6", description="使用的模型")
    MAX_TURNS: int = Field(default=10, description="最大对话轮数")

    # 飞书配置
    FEISHU_APP_ID: str = Field(default="", description="飞书应用ID")
    FEISHU_APP_SECRET: str = Field(default="", description="飞书应用密钥")
    FEISHU_ENCRYPT_KEY: Optional[str] = Field(default=None, description="飞书加密密钥（可选）")
    FEISHU_VERIFICATION_TOKEN: Optional[str] = Field(default=None, description="飞书验证令牌（可选）")
    FEISHU_BOT_USER_ID: Optional[str] = Field(default=None, description="飞书机器人用户ID（可选）")
    FEISHU_SEND_TOOL_MESSAGES: bool = Field(default=True, description="是否发送工具调用消息到飞书")

    # 工具权限配置（逗号分隔的工具名称列表，空表示允许所有工具）
    ALLOWED_TOOLS: str = Field(
        default="",
        description="允许的工具列表（逗号分隔，空=允许所有）"
    )
    DISALLOWED_TOOLS: str = Field(
        default="",
        description="禁止的工具列表（逗号分隔，优先级高于 ALLOWED_TOOLS）"
    )

    # 资源配置
    RESOURCE_CACHE_DAYS: int = Field(default=7, description="资源缓存天数")
    MAX_FILE_SIZE_MB: int = Field(default=100, description="最大文件大小（MB）")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FILE: str = Field(default="logs/app.log", description="日志文件路径")
    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024, description="日志文件最大大小（字节）")
    LOG_BACKUP_COUNT: int = Field(default=5, description="日志文件备份数量")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return get_project_root()

    @property
    def allowed_directory_list(self) -> List[str]:
        """获取允许访问的目录列表"""
        if not self.ALLOWED_DIRECTORIES:
            return []
        return [d.strip() for d in self.ALLOWED_DIRECTORIES.split(",") if d.strip()]

    @property
    def allowed_tools_list(self) -> List[str]:
        """获取允许的工具列表

        空列表表示允许所有工具（默认行为）

        支持的权限语法：
        - 精确匹配：Bash, Read, Write
        - MCP 通配符：mcp (所有 mcp__ 开头的工具)
        - MCP 服务器：mcp:pencil (mcp__pencil__*), mcp:godot (mcp__godot__*)
        - MCP 嵌套：mcp:plugin:playwright (mcp__plugin_playwright_playwright__*)
        """
        if not self.ALLOWED_TOOLS:
            return []  # 空列表 = 允许所有工具
        return [t.strip() for t in self.ALLOWED_TOOLS.split(",") if t.strip()]

    @property
    def disallowed_tools_list(self) -> List[str]:
        """获取禁止的工具列表

        空列表表示不禁止任何工具（默认行为）

        支持的权限语法（与 allowed_tools 相同）：
        - 精确匹配：Bash, Read, Write
        - MCP 通配符：mcp (所有 mcp__ 开头的工具)
        - MCP 服务器：mcp:pencil (mcp__pencil__*), mcp:godot (mcp__godot__*)
        - MCP 嵌套：mcp:plugin:playwright (mcp__plugin_playwright_playwright__*)

        注意：disallowed_tools 的优先级高于 allowed_tools
        """
        if not self.DISALLOWED_TOOLS:
            return []  # 空列表 = 不禁止任何工具
        return [t.strip() for t in self.DISALLOWED_TOOLS.split(",") if t.strip()]

    def _match_tool_pattern(self, pattern: str, tool_name: str) -> bool:
        """检查工具名称是否匹配权限模式

        Args:
            pattern: 权限模式（如 "Bash", "mcp", "mcp:pencil"）
            tool_name: 工具名称（如 "Bash", "mcp__pencil__batch_design"）

        Returns:
            bool: True 表示匹配
        """
        # 精确匹配
        if pattern == tool_name:
            return True

        # 处理 MCP 工具的特殊语法
        if pattern.startswith("mcp"):
            if pattern == "mcp":
                # "mcp" 匹配所有 mcp__ 开头的工具
                return tool_name.startswith("mcp__")

            # "mcp:xxx" 或 "mcp:xxx:yyy" 转换为 "mcp__xxx__" 或 "mcp__xxx_yyy__"
            if ":" in pattern:
                # 将 : 转换为 __，并添加 __ 后缀作为通配符
                parts = pattern.split(":")
                # 第一个部分是 "mcp"，后面是服务器/插件名称
                # 例如：mcp:pencil → mcp__pencil__
                # 例如：mcp:plugin:playwright → mcp__plugin_playwright_playwright__
                prefix = "__".join(parts) + "__"
                return tool_name.startswith(prefix)

        # 处理传统通配符（向后兼容）
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return tool_name.startswith(prefix)

        return False

    def is_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否被允许使用

        Args:
            tool_name: 工具名称

        Returns:
            bool: True 表示允许，False 表示禁止
        """
        allowed_tools = self.allowed_tools_list
        if not allowed_tools:
            # 空列表 = 允许所有工具
            return True

        # 检查每个权限模式
        for pattern in allowed_tools:
            if self._match_tool_pattern(pattern, tool_name):
                return True

        return False

    @property
    def database_path(self) -> Path:
        """获取数据库文件路径"""
        if self.DATABASE_URL.startswith("sqlite:///"):
            db_path = self.DATABASE_URL.replace("sqlite:///", "")
            # 如果是相对路径,则相对于项目根目录
            if not os.path.isabs(db_path):
                return self.project_root / db_path
            return Path(db_path)
        return Path(self.DATABASE_URL)

    @property
    def session_root_path(self) -> Path:
        """获取会话根目录路径"""
        session_root = self.DEFAULT_SESSION_ROOT
        # 如果是相对路径,则相对于项目根目录
        if not os.path.isabs(session_root):
            return self.project_root / session_root
        return Path(session_root)

    @property
    def log_file_path(self) -> Path:
        """获取日志文件路径"""
        log_file = self.LOG_FILE
        # 如果是相对路径,则相对于项目根目录
        if not os.path.isabs(log_file):
            return self.project_root / log_file
        return Path(log_file)


# 全局配置实例
_settings: Optional[Settings] = None


def _reset_settings():
    """重置全局配置实例（仅用于测试）"""
    global _settings
    _settings = None


def get_settings(config_path: Optional[str] = None) -> Settings:
    """获取全局配置实例（单例模式）

    Args:
        config_path: 配置文件路径(可选)

    Returns:
        Settings: 配置实例
    """
    global _settings
    if _settings is None:
        if config_path:
            _settings = Settings(_env_file=config_path)
        else:
            _settings = Settings()
    return _settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """重新加载配置

    Args:
        config_path: 配置文件路径(可选)

    Returns:
        Settings: 新的配置实例
    """
    global _settings
    _settings = None
    return get_settings(config_path)
