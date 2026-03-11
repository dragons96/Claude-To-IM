# tests/test_services/test_permission_manager.py
import pytest
from src.services.permission_manager import PermissionManager
from src.core.exceptions import PermissionDeniedError


@pytest.mark.asyncio
async def test_default_no_permissions():
    manager = PermissionManager([])
    assert manager.is_allowed("/tmp/test") is False
    assert manager.is_allowed("D:/Codes") is False


@pytest.mark.asyncio
async def test_add_allowed_directory():
    manager = PermissionManager([])
    manager.add_allowed_directory("D:/Codes")
    assert manager.is_allowed("D:/Codes") is True
    assert manager.is_allowed("D:/Codes/project") is True
    assert manager.is_allowed("D:/xxx") is False


@pytest.mark.asyncio
async def test_multiple_allowed_directories():
    manager = PermissionManager(["D:/Codes", "C:/Projects"])
    assert manager.is_allowed("D:/Codes/project") is True
    assert manager.is_allowed("C:/Projects/app") is True
    assert manager.is_allowed("E:/Data") is False


@pytest.mark.asyncio
async def test_windows_path_handling():
    manager = PermissionManager(["D:\\Codes"])
    assert manager.is_allowed("D:/Codes/project") is True
    assert manager.is_allowed("D:\\Codes\\project") is True


@pytest.mark.asyncio
async def test_remove_allowed_directory():
    manager = PermissionManager(["D:/Codes", "C:/Projects"])
    manager.remove_allowed_directory("D:/Codes")
    assert manager.is_allowed("D:/Codes") is False
    assert manager.is_allowed("C:/Projects") is True


@pytest.mark.asyncio
async def test_check_with_exception():
    manager = PermissionManager(["D:/Codes"])
    # 不应该抛出异常
    manager.check_permission("D:/Codes/project")

    # 应该抛出异常
    with pytest.raises(PermissionDeniedError):
        manager.check_permission("E:/Data")
