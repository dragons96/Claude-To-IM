# src/services/models.py
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class IMSession(Base):
    """IM 平台会话映射表"""
    __tablename__ = 'im_sessions'

    id = Column(String(64), primary_key=True)
    platform = Column(String(32), nullable=False)  # 'feishu', 'dingtalk', etc.
    platform_session_id = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ClaudeSession(Base):
    """Claude Code 会话表"""
    __tablename__ = 'claude_sessions'

    id = Column(String(64), primary_key=True)
    im_session_id = Column(String(64), ForeignKey('im_sessions.id'))
    session_id = Column(String(128), nullable=False, unique=True)  # Claude SDK session_id
    work_directory = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    summary = Column(String(10))  # 第一条消息前10字符
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    im_session = relationship("IMSession", backref="claude_sessions")

class MessageHistory(Base):
    """消息历史表"""
    __tablename__ = 'message_history'

    id = Column(String(64), primary_key=True)
    claude_session_id = Column(String(64), ForeignKey('claude_sessions.id'))
    role = Column(String(16), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PermissionConfig(Base):
    """权限配置表"""
    __tablename__ = 'permission_config'

    id = Column(String(64), primary_key=True)
    path = Column(String(512), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ResourceCache(Base):
    """资源缓存表(飞书文件下载缓存)"""
    __tablename__ = 'resource_cache'

    id = Column(String(64), primary_key=True)
    resource_key = Column(String(256), nullable=False, unique=True)  # 飞书文件key
    local_path = Column(String(512), nullable=False)
    mime_type = Column(String(128))
    size = Column(BigInteger)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # 过期时间,可定期清理
