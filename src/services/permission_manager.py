# src/services/permission_manager.py
from typing import List
import os
from src.core.exceptions import PermissionDeniedError


class PermissionManager:
    """目录权限管理器"""

    def __init__(self, allowed_directories: List[str] = None):
        """初始化权限管理器

        Args:
            allowed_directories: 允许访问的目录列表
        """
        # 标准化所有允许的目录
        if allowed_directories:
            self.allowed_directories = [self._normalize_path(d) for d in allowed_directories]
        else:
            self.allowed_directories = []

    def add_allowed_directory(self, path: str) -> None:
        """添加允许的目录"""
        normalized = self._normalize_path(path)
        if normalized not in self.allowed_directories:
            self.allowed_directories.append(normalized)

    def remove_allowed_directory(self, path: str) -> None:
        """移除允许的目录"""
        normalized = self._normalize_path(path)
        if normalized in self.allowed_directories:
            self.allowed_directories.remove(normalized)

    def is_allowed(self, path: str) -> bool:
        """检查路径是否允许访问"""
        if not self.allowed_directories:
            return False

        normalized = self._normalize_path(path)

        # 检查是否在允许的目录或其子目录中
        for allowed_dir in self.allowed_directories:
            if normalized == allowed_dir or normalized.startswith(allowed_dir + "/"):
                return True

        return False

    def check_permission(self, path: str) -> None:
        """检查权限,无权限时抛出异常"""
        if not self.is_allowed(path):
            raise PermissionDeniedError(f"没有权限访问目录: {path}")

    def _normalize_path(self, path: str) -> str:
        """标准化路径(处理 Windows 路径分隔符)"""
        # 转换为绝对路径并标准化分隔符
        normalized = os.path.normpath(os.path.abspath(path))
        # 统一使用正斜线
        return normalized.replace("\\", "/")
