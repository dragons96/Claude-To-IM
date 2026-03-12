# src/services/session_manager.py
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.core.claude_adapter import ClaudeSession as ClaudeAdapterSession
from src.core.exceptions import SessionNotFoundError, PermissionDeniedError


class SessionManager:
    """会话管理器 - 处理 Claude 会话生命周期"""

    def __init__(
        self,
        claude_adapter,
        storage,
        default_session_root: str,
        permission_manager
    ):
        """初始化会话管理器

        Args:
            claude_adapter: Claude 适配器实例
            storage: 存储服务实例
            default_session_root: 默认会话根目录
            permission_manager: 权限管理器实例
        """
        self.claude_adapter = claude_adapter
        self.storage = storage
        self.default_session_root = Path(default_session_root)
        self.permission_manager = permission_manager

    async def resume_active_sessions(self):
        """恢复活跃会话

        程序重启后，根据数据库中的活跃会话记录，重新创建 SDK 客户端。
        这样可以保持会话的连续性，使用相同的 session_id 和 work_directory。
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 获取所有活跃的 Claude 会话
            from src.services.models import ClaudeSession

            db_session = self.storage.db
            active_sessions = db_session.query(ClaudeSession).filter_by(
                is_active=True
            ).all()

            if not active_sessions:
                logger.info("没有需要恢复的活跃会话")
                return

            logger.info(f"发现 {len(active_sessions)} 个活跃会话，正在恢复...")

            restored_count = 0
            for db_session_record in active_sessions:
                try:
                    logger.info(f"  - 恢复会话: {db_session_record.session_id}")
                    logger.info(f"    工作目录: {db_session_record.work_directory}")

                    # 使用数据库中的 session_id 和 work_directory 重新创建会话
                    restored_session = await self.claude_adapter.create_session(
                        work_directory=db_session_record.work_directory,
                        session_id=db_session_record.session_id  # 使用相同的 session_id
                    )

                    logger.info(f"    ✅ 会话已恢复: {restored_session.session_id}")
                    restored_count += 1

                except Exception as e:
                    # 捕获所有异常，避免单个会话失败导致整个恢复过程失败
                    logger.error(f"    ❌ 恢复会话 {db_session_record.session_id} 失败: {e}", exc_info=True)
                    # 标记该会话为非活跃状态
                    try:
                        db_session_record.is_active = False
                        db_session.commit()
                        logger.info(f"    ⚠️  会话 {db_session_record.session_id} 已标记为非活跃")
                    except Exception as commit_error:
                        logger.error(f"    ❌ 更新会话状态失败: {commit_error}")
                    # 恢复失败，将此会话标记为非活跃
                    db_session_record.is_active = False

            # 提交可能的状态变更
            db_session.commit()

            logger.info(f"✅ 活跃会话恢复完成: {restored_count}/{len(active_sessions)}")

        except Exception as e:
            logger.error(f"恢复活跃会话失败: {e}", exc_info=True)

    async def get_or_create_session(
        self,
        platform: str,
        platform_session_id: str
    ) -> ClaudeAdapterSession:
        """获取或创建 Claude 会话

        如果平台会话不存在且有活跃的 Claude 会话,返回第一个活跃会话。
        否则自动在默认目录创建新会话。

        Args:
            platform: 平台名称 (feishu, dingtalk, etc.)
            platform_session_id: 平台会话 ID

        Returns:
            ClaudeAdapterSession: Claude 会话对象

        Raises:
            RuntimeError: 当会话创建失败时抛出异常
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"获取或创建会话 - platform: {platform}, platform_session_id: {platform_session_id}")

        try:
            # 获取或创建 IM 会话
            im_session = await self.storage.get_im_session_by_platform_id(
                platform, platform_session_id
            )

            if not im_session:
                # 创建新的 IM 会话
                logger.info("IM 会话不存在，创建新的...")
                im_session = await self.storage.create_im_session(
                    id=str(uuid.uuid4()),
                    platform=platform,
                    platform_session_id=platform_session_id
                )
                logger.info(f"IM 会话已创建，ID: {im_session.id}")
            else:
                logger.info(f"找到现有 IM 会话，ID: {im_session.id}")

            # 检查是否有活跃的 Claude 会话
            active_sessions = await self.storage.get_active_claude_sessions(im_session.id)
            logger.info(f"活跃会话数量: {len(active_sessions)}")

            if active_sessions:
                # 返回第一个活跃会话的 SDK 会话对象
                db_session = active_sessions[0]
                logger.info(f"找到现有活跃会话记录: {db_session.session_id}")

                # 尝试从内存中获取会话
                claude_session = await self.claude_adapter.get_session_info(
                    db_session.session_id
                )

                if claude_session:
                    logger.info(f"活跃会话在内存中有效，返回: {claude_session.session_id}")
                    return claude_session
                else:
                    # 会话不在内存中且恢复失败，需要创建新会话
                    logger.warning(f"活跃会话不在内存中（恢复可能失败），将创建新会话")
                    logger.info(f"旧会话信息: session_id={db_session.session_id}, work_directory={db_session.work_directory}")

                    # 将旧会话标记为非活跃
                    await self.storage.set_claude_session_active(db_session.id, False)
                    logger.info(f"已将旧会话 {db_session.session_id} 标记为非活跃")

                    # 继续下面的逻辑创建新会话
                    pass

            # 没有活跃会话,创建新会话
            # 创建默认工作目录
            logger.info("没有活跃会话，创建新会话...")
            work_directory = self.default_session_root / platform_session_id
            work_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"工作目录已创建: {work_directory}")

            # 创建 Claude SDK 会话
            logger.info("调用 Claude SDK 创建会话...")
            claude_session = await self.claude_adapter.create_session(
                work_directory=str(work_directory)
            )

            if not claude_session:
                raise RuntimeError(f"Claude SDK 创建会话失败，返回了 None")

            logger.info(f"Claude SDK 会话已创建，ID: {claude_session.session_id}")

            # 保存到数据库
            await self.storage.create_claude_session(
                id=str(uuid.uuid4()),
                im_session_id=im_session.id,
                session_id=claude_session.session_id,
                work_directory=str(work_directory),
                summary=f"自动创建于 {platform_session_id}",
                is_active=True
            )

            logger.info(f"✅ 新会话创建成功: {claude_session.session_id}")
            return claude_session

        except Exception as e:
            logger.error(f"获取或创建会话失败: {e}", exc_info=True)
            raise RuntimeError(f"无法获取或创建会话: {str(e)}") from e

    async def create_session(
        self,
        platform: str,
        platform_session_id: str,
        work_directory: str,
        summary: str
    ) -> ClaudeAdapterSession:
        """创建新的 Claude 会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID
            work_directory: 工作目录路径
            summary: 会话摘要

        Returns:
            ClaudeAdapterSession: 创建的 Claude 会话对象

        Raises:
            PermissionDeniedError: 没有权限访问指定目录
        """
        # 检查目录权限
        self.permission_manager.check_permission(work_directory)

        # 获取或创建 IM 会话
        im_session = await self.storage.get_im_session_by_platform_id(
            platform, platform_session_id
        )

        if not im_session:
            im_session = await self.storage.create_im_session(
                id=str(uuid.uuid4()),
                platform=platform,
                platform_session_id=platform_session_id
            )

        # 创建工作目录
        work_path = Path(work_directory)
        work_path.mkdir(parents=True, exist_ok=True)

        # 创建 Claude SDK 会话
        claude_session = await self.claude_adapter.create_session(
            work_directory=work_directory
        )

        # 保存到数据库
        await self.storage.create_claude_session(
            id=str(uuid.uuid4()),
            im_session_id=im_session.id,
            session_id=claude_session.session_id,
            work_directory=work_directory,
            summary=summary[:10] if len(summary) > 10 else summary,
            is_active=True
        )

        return claude_session

    async def list_sessions(
        self,
        platform: str,
        platform_session_id: str
    ) -> List[Dict[str, Any]]:
        """列出平台会话的所有 Claude 会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID

        Returns:
            List[Dict[str, Any]]: 会话信息列表

        Raises:
            SessionNotFoundError: 平台会话不存在
        """
        # 获取 IM 会话
        im_session = await self.storage.get_im_session_by_platform_id(
            platform, platform_session_id
        )

        if not im_session:
            raise SessionNotFoundError(
                f"平台会话不存在: {platform}/{platform_session_id}"
            )

        # 获取所有活跃会话
        active_sessions = await self.storage.get_active_claude_sessions(im_session.id)

        # 格式化返回
        sessions_info = []
        for session in active_sessions:
            sessions_info.append({
                "id": session.id,
                "session_id": session.session_id,
                "work_directory": session.work_directory,
                "is_active": session.is_active,
                "summary": session.summary,
                "created_at": session.created_at.isoformat() if session.created_at else None
            })

        return sessions_info

    async def switch_session(
        self,
        platform: str,
        platform_session_id: str,
        claude_session_id: str
    ) -> Dict[str, Any]:
        """切换到指定的 Claude 会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID
            claude_session_id: Claude 会话 ID

        Returns:
            Dict[str, Any]: 切换后的会话信息

        Raises:
            SessionNotFoundError: 会话不存在
        """
        # 获取 IM 会话
        im_session = await self.storage.get_im_session_by_platform_id(
            platform, platform_session_id
        )

        if not im_session:
            raise SessionNotFoundError(
                f"平台会话不存在: {platform}/{platform_session_id}"
            )

        # 获取目标 Claude 会话
        target_session = await self.storage.get_claude_session(claude_session_id)

        if not target_session or target_session.im_session_id != im_session.id:
            raise SessionNotFoundError(
                f"Claude 会话不存在或不属于此平台会话: {claude_session_id}"
            )

        # 设置为活跃状态
        await self.storage.set_claude_session_active(claude_session_id, True)

        # 返回会话信息
        return {
            "id": target_session.id,
            "session_id": target_session.session_id,
            "work_directory": target_session.work_directory,
            "is_active": True,
            "summary": target_session.summary,
            "created_at": target_session.created_at.isoformat() if target_session.created_at else None
        }

    async def delete_session(
        self,
        platform: str,
        platform_session_id: str,
        claude_session_id: str
    ) -> Dict[str, Any]:
        """删除指定的 Claude 会话

        Args:
            platform: 平台名称
            platform_session_id: 平台会话 ID
            claude_session_id: Claude 会话 ID (数据库中的 id 字段)

        Returns:
            Dict[str, Any]: 被删除的会话信息

        Raises:
            SessionNotFoundError: 会话不存在
        """
        import logging
        logger = logging.getLogger(__name__)

        # 获取 IM 会话
        im_session = await self.storage.get_im_session_by_platform_id(
            platform, platform_session_id
        )

        if not im_session:
            raise SessionNotFoundError(
                f"平台会话不存在: {platform}/{platform_session_id}"
            )

        # 获取目标 Claude 会话
        target_session = await self.storage.get_claude_session(claude_session_id)

        if not target_session or target_session.im_session_id != im_session.id:
            raise SessionNotFoundError(
                f"Claude 会话不存在或不属于此平台会话: {claude_session_id}"
            )

        # 记录会话信息用于返回
        session_info = {
            "id": target_session.id,
            "session_id": target_session.session_id,
            "work_directory": target_session.work_directory,
            "summary": target_session.summary,
        }

        # 尝试关闭 Claude SDK 会话
        try:
            await self.claude_adapter.close_session(target_session.session_id)
            logger.info(f"Claude SDK 会话已关闭: {target_session.session_id}")
        except Exception as e:
            logger.warning(f"关闭 Claude SDK 会话失败（继续删除数据库记录）: {e}")

        # 删除数据库记录
        success = await self.storage.delete_claude_session(claude_session_id)

        if not success:
            raise SessionNotFoundError(
                f"删除会话失败: {claude_session_id}"
            )

        logger.info(f"会话已删除: {claude_session_id}")

        return session_info
