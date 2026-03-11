# src/core/exceptions.py
class ClaudeToIMException(Exception):
    """基础异常类"""
    pass

class SessionNotFoundError(ClaudeToIMException):
    """会话不存在异常"""
    pass

class PermissionDeniedError(ClaudeToIMException):
    """权限不足异常"""
    pass

class ClaudeSDKError(ClaudeToIMException):
    """Claude SDK 调用失败异常"""
    pass

class IMPlatformError(ClaudeToIMException):
    """IM 平台错误异常"""
    pass

class ResourceDownloadError(ClaudeToIMException):
    """资源下载失败异常"""

    def __init__(self, url: str, resource_key: str, message: str):
        self.url = url
        self.resource_key = resource_key
        super().__init__(message)

class CommandExecutionError(ClaudeToIMException):
    """命令执行错误异常"""
    pass
