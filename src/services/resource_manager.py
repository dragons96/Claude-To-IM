# src/services/resource_manager.py
import os
import uuid
import aiohttp
import aiofiles
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from src.services.models import ResourceCache
from src.core.exceptions import ResourceDownloadError


class ResourceManager:
    """资源管理器 - 负责下载和缓存远程资源文件"""

    def __init__(self, storage: Session, cache_dir: str):
        """
        初始化资源管理器

        Args:
            storage: SQLAlchemy 会话对象（用于缓存管理）
            cache_dir: 缓存目录路径
        """
        self.storage = storage
        self.cache_dir = cache_dir

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

    async def download_resource(
        self,
        url: str,
        resource_key: str,
        use_cache: bool = True
    ) -> bytes:
        """
        下载资源文件（支持缓存）

        Args:
            url: 资源 URL
            resource_key: 资源唯一标识（用于缓存）
            use_cache: 是否使用缓存

        Returns:
            资源内容（bytes）

        Raises:
            ResourceDownloadError: 下载失败时抛出
        """
        # 检查缓存
        if use_cache:
            cached = await self._check_cache(resource_key)
            if cached:
                # 从缓存读取
                return await self._read_from_cache(cached.local_path)

        # 从网络下载
        try:
            content = await self._download_from_url(url)

            # 保存到缓存
            await self._save_to_cache(resource_key, content, url)

            return content

        except Exception as e:
            raise ResourceDownloadError(
                url=url,
                resource_key=resource_key,
                message=f"下载资源失败: {str(e)}"
            ) from e

    async def save_resource(
        self,
        content: bytes,
        work_dir: str,
        subdir: Optional[str] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        保存资源到工作目录

        Args:
            content: 资源内容
            work_dir: 工作目录路径
            subdir: 子目录（可选）
            filename: 文件名（可选，不指定则自动生成）

        Returns:
            保存的完整文件路径
        """
        # 生成文件名
        if filename is None:
            filename = f"{uuid.uuid4()}"

        # 构建完整路径
        if subdir:
            full_dir = os.path.join(work_dir, subdir)
        else:
            full_dir = work_dir

        # 确保目录存在
        os.makedirs(full_dir, exist_ok=True)

        # 完整文件路径
        file_path = os.path.join(full_dir, filename)

        # 异步写入文件
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        return file_path

    async def _check_cache(self, resource_key: str) -> Optional[ResourceCache]:
        """
        检查资源缓存

        Args:
            resource_key: 资源标识

        Returns:
            ResourceCache 对象或 None
        """
        cached = self.storage.query(ResourceCache).filter_by(
            resource_key=resource_key
        ).first()

        if cached:
            # 检查是否过期
            if cached.expires_at and cached.expires_at < datetime.utcnow():
                # 缓存已过期，删除记录
                self.storage.delete(cached)
                self.storage.commit()
                return None

        return cached

    async def _read_from_cache(self, local_path: str) -> bytes:
        """
        从缓存文件读取内容

        Args:
            local_path: 本地缓存文件路径

        Returns:
            文件内容
        """
        async with aiofiles.open(local_path, 'rb') as f:
            return await f.read()

    async def _download_from_url(self, url: str) -> bytes:
        """
        从 URL 下载资源

        Args:
            url: 资源 URL

        Returns:
            下载的内容
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.read()

    async def _save_to_cache(
        self,
        resource_key: str,
        content: bytes,
        url: str
    ) -> None:
        """
        保存资源到缓存

        Args:
            resource_key: 资源标识
            content: 资源内容
            url: 资源 URL（用于获取 MIME 类型）
        """
        # 生成缓存文件路径
        cache_filename = f"{resource_key}.cache"
        cache_path = os.path.join(self.cache_dir, cache_filename)

        # 写入缓存文件
        async with aiofiles.open(cache_path, 'wb') as f:
            await f.write(content)

        # 获取 MIME 类型（简单处理）
        mime_type = "application/octet-stream"
        if url.endswith('.pdf'):
            mime_type = "application/pdf"
        elif url.endswith('.png'):
            mime_type = "image/png"
        elif url.endswith('.jpg') or url.endswith('.jpeg'):
            mime_type = "image/jpeg"

        # 保存缓存记录到数据库（默认缓存 7 天）
        from src.services.storage_service import StorageService
        storage_service = StorageService(self.storage)
        await storage_service.cache_resource(
            resource_key=resource_key,
            local_path=cache_path,
            mime_type=mime_type,
            size=len(content),
            expires_days=7
        )
