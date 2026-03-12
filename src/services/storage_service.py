# src/services/storage_service.py
import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.services.models import (
    IMSession,
    ClaudeSession,
    MessageHistory,
    PermissionConfig,
    ResourceCache
)


class StorageService:
    """存储服务 - 封装所有数据库操作"""

    def __init__(self, db: Session):
        """
        初始化存储服务

        Args:
            db: SQLAlchemy 会话对象
        """
        self.db = db

    # ==================== IM Session Operations ====================

    async def create_im_session(
        self,
        id: str,
        platform: str,
        platform_session_id: str
    ) -> IMSession:
        """
        创建 IM 平台会话

        Args:
            id: 会话唯一标识
            platform: 平台名称 (feishu, dingtalk, etc.)
            platform_session_id: 平台会话 ID

        Returns:
            创建的 IMSession 对象
        """
        session = IMSession(
            id=id,
            platform=platform,
            platform_session_id=platform_session_id
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def get_im_session(self, session_id: str) -> Optional[IMSession]:
        """
        根据 ID 获取 IM 会话

        Args:
            session_id: 会话 ID

        Returns:
            IMSession 对象或 None
        """
        return self.db.query(IMSession).filter_by(id=session_id).first()

    async def get_im_session_by_platform_id(
        self,
        platform: str,
        platform_session_id: str
    ) -> Optional[IMSession]:
        """
        根据平台 ID 获取 IM 会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID

        Returns:
            IMSession 对象或 None
        """
        return self.db.query(IMSession).filter_by(
            platform=platform,
            platform_session_id=platform_session_id
        ).first()

    async def update_im_session_last_active(self, session_id: str) -> None:
        """
        更新 IM 会话的最后活跃时间

        Args:
            session_id: 会话 ID
        """
        session = self.db.query(IMSession).filter_by(id=session_id).first()
        if session:
            session.last_active = datetime.utcnow()
            self.db.commit()

    # ==================== Claude Session Operations ====================

    async def create_claude_session(
        self,
        id: str,
        im_session_id: str,
        session_id: str,
        work_directory: str,
        summary: str,
        is_active: bool
    ) -> ClaudeSession:
        """
        创建 Claude Code 会话

        Args:
            id: 会话唯一标识
            im_session_id: 关联的 IM 会话 ID
            session_id: Claude SDK session_id
            work_directory: 工作目录路径
            summary: 会话摘要(第一条消息前10字符)
            is_active: 是否活跃

        Returns:
            创建的 ClaudeSession 对象
        """
        claude_session = ClaudeSession(
            id=id,
            im_session_id=im_session_id,
            session_id=session_id,
            work_directory=work_directory,
            summary=summary,
            is_active=is_active
        )
        self.db.add(claude_session)
        self.db.commit()
        self.db.refresh(claude_session)
        return claude_session

    async def get_claude_session(self, session_id: str) -> Optional[ClaudeSession]:
        """
        根据 ID 获取 Claude 会话

        Args:
            session_id: 会话 ID

        Returns:
            ClaudeSession 对象或 None
        """
        return self.db.query(ClaudeSession).filter_by(id=session_id).first()

    async def get_claude_session_by_sdk_id(
        self,
        sdk_session_id: str
    ) -> Optional[ClaudeSession]:
        """
        根据 Claude SDK session_id 获取会话

        Args:
            sdk_session_id: Claude SDK session_id

        Returns:
            ClaudeSession 对象或 None
        """
        return self.db.query(ClaudeSession).filter_by(
            session_id=sdk_session_id
        ).first()

    async def get_active_claude_sessions(
        self,
        im_session_id: str
    ) -> List[ClaudeSession]:
        """
        获取指定 IM 会话的所有活跃 Claude 会话

        Args:
            im_session_id: IM 会话 ID

        Returns:
            ClaudeSession 对象列表
        """
        return self.db.query(ClaudeSession).filter_by(
            im_session_id=im_session_id,
            is_active=True
        ).all()

    async def set_claude_session_active(
        self,
        session_id: str,
        is_active: bool
    ) -> None:
        """
        设置 Claude 会话的活跃状态

        Args:
            session_id: 会话 ID
            is_active: 是否活跃
        """
        session = self.db.query(ClaudeSession).filter_by(id=session_id).first()
        if session:
            session.is_active = is_active
            self.db.commit()

    async def delete_claude_session(self, session_id: str) -> bool:
        """
        删除 Claude 会话

        Args:
            session_id: 会话 ID (数据库中的 id 字段)

        Returns:
            bool: 是否删除成功
        """
        session = self.db.query(ClaudeSession).filter_by(id=session_id).first()
        if session:
            # 删除关联的消息历史
            self.db.query(MessageHistory).filter_by(claude_session_id=session_id).delete()
            # 删除会话
            self.db.delete(session)
            self.db.commit()
            return True
        return False

    # ==================== Message Operations ====================

    async def save_message(
        self,
        claude_session_id: str,
        role: str,
        content: str
    ) -> MessageHistory:
        """
        保存消息到历史记录

        Args:
            claude_session_id: Claude 会话 ID
            role: 角色 (user/assistant)
            content: 消息内容

        Returns:
            创建的 MessageHistory 对象
        """
        message = MessageHistory(
            id=str(uuid.uuid4()),
            claude_session_id=claude_session_id,
            role=role,
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    # ==================== Permission Operations ====================

    async def get_permission_configs(self) -> List[PermissionConfig]:
        """
        获取所有权限配置

        Returns:
            PermissionConfig 对象列表
        """
        return self.db.query(PermissionConfig).filter_by(is_active=True).all()

    async def create_permission_config(self, path: str) -> PermissionConfig:
        """
        创建权限配置

        Args:
            path: 允许访问的路径

        Returns:
            创建的 PermissionConfig 对象
        """
        config = PermissionConfig(
            id=str(uuid.uuid4()),
            path=path
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    # ==================== Resource Operations ====================

    async def cache_resource(
        self,
        resource_key: str,
        local_path: str,
        mime_type: str,
        size: int,
        expires_days: int
    ) -> ResourceCache:
        """
        缓存资源文件

        Args:
            resource_key: 资源唯一标识
            local_path: 本地文件路径
            mime_type: MIME 类型
            size: 文件大小(字节)
            expires_days: 过期天数

        Returns:
            创建的 ResourceCache 对象
        """
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

        cache = ResourceCache(
            id=str(uuid.uuid4()),
            resource_key=resource_key,
            local_path=local_path,
            mime_type=mime_type,
            size=size,
            expires_at=expires_at
        )
        self.db.add(cache)
        self.db.commit()
        self.db.refresh(cache)
        return cache

    async def get_cached_resource(
        self,
        resource_key: str
    ) -> Optional[ResourceCache]:
        """
        获取缓存资源

        Args:
            resource_key: 资源唯一标识

        Returns:
            ResourceCache 对象或 None
        """
        return self.db.query(ResourceCache).filter_by(
            resource_key=resource_key
        ).first()
