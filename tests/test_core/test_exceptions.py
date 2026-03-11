# tests/test_core/test_exceptions.py
import pytest
from src.core.exceptions import (
    ClaudeToIMException,
    SessionNotFoundError,
    PermissionDeniedError,
    ClaudeSDKError,
    IMPlatformError,
    ResourceDownloadError,
    CommandExecutionError
)

def test_exception_hierarchy():
    """Test all exception classes inherit from base class"""
    assert issubclass(SessionNotFoundError, ClaudeToIMException)
    assert issubclass(PermissionDeniedError, ClaudeToIMException)
    assert issubclass(ClaudeSDKError, ClaudeToIMException)
    assert issubclass(IMPlatformError, ClaudeToIMException)
    assert issubclass(ResourceDownloadError, ClaudeToIMException)
    assert issubclass(CommandExecutionError, ClaudeToIMException)

def test_exception_messages():
    """Test exception messages work correctly"""
    # Test SessionNotFoundError
    error = SessionNotFoundError("Session not found")
    assert str(error) == "Session not found"
    assert isinstance(error, ClaudeToIMException)

    # Test PermissionDeniedError
    perm_error = PermissionDeniedError("Access denied")
    assert str(perm_error) == "Access denied"
    assert isinstance(perm_error, ClaudeToIMException)

    # Test ClaudeSDKError
    sdk_error = ClaudeSDKError("SDK error")
    assert str(sdk_error) == "SDK error"
    assert isinstance(sdk_error, ClaudeToIMException)

    # Test IMPlatformError
    platform_error = IMPlatformError("Platform error")
    assert str(platform_error) == "Platform error"
    assert isinstance(platform_error, ClaudeToIMException)

    # Test ResourceDownloadError
    download_error = ResourceDownloadError("Download failed")
    assert str(download_error) == "Download failed"
    assert isinstance(download_error, ClaudeToIMException)

    # Test CommandExecutionError
    command_error = CommandExecutionError("Command failed")
    assert str(command_error) == "Command failed"
    assert isinstance(command_error, ClaudeToIMException)
