# tests/services/test_resource_manager.py
import pytest
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch
from src.services.resource_manager import ResourceManager
from src.services.models import ResourceCache
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


class TestResourceManager:
    """ResourceManager 测试套件"""

    @pytest.fixture
    def mock_storage(self):
        """Mock StorageService"""
        storage = Mock(spec=Session)
        return storage

    @pytest.fixture
    def temp_cache_dir(self):
        """临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def temp_work_dir(self):
        """临时工作目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_download_resource_new(self, mock_storage, temp_cache_dir):
        """测试下载新资源（从网络下载）"""
        # 准备测试数据
        url = "https://example.com/test.pdf"
        resource_key = "file_key_123"
        test_content = b"PDF test content here"

        # Mock aiohttp ClientSession
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_response.raise_for_status = Mock()

        # 创建一个正确的异步上下文管理器 mock
        async def mock_response_context():
            return mock_response

        mock_response.read = AsyncMock(return_value=test_content)

        # Mock session.get 返回一个异步上下文管理器
        mock_get_context = AsyncMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock()

        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        # Mock storage - 没有缓存
        mock_storage.query.return_value.filter_by.return_value.first.return_value = None

        # 创建 ResourceManager
        manager = ResourceManager(mock_storage, cache_dir=temp_cache_dir)

        # Patch aiohttp.ClientSession
        with patch('src.services.resource_manager.aiohttp.ClientSession', return_value=mock_session):
            content = await manager.download_resource(
                url=url,
                resource_key=resource_key,
                use_cache=True
            )

        # 验证下载内容
        assert content == test_content

        # 验证 HTTP 请求
        mock_session.get.assert_called_once_with(url)

    @pytest.mark.asyncio
    async def test_download_resource_from_cache(self, mock_storage, temp_cache_dir):
        """测试从缓存加载资源"""
        # 准备测试数据
        resource_key = "file_key_456"
        test_content = b"Cached content"

        # 创建缓存文件
        cache_file = os.path.join(temp_cache_dir, f"{resource_key}.cache")
        os.makedirs(temp_cache_dir, exist_ok=True)
        with open(cache_file, 'wb') as f:
            f.write(test_content)

        # Mock storage - 有未过期缓存
        cached_resource = ResourceCache(
            id="cache_123",
            resource_key=resource_key,
            local_path=cache_file,
            mime_type="application/pdf",
            size=len(test_content),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        mock_storage.query.return_value.filter_by.return_value.first.return_value = cached_resource

        # 创建 ResourceManager
        manager = ResourceManager(mock_storage, cache_dir=temp_cache_dir)

        # 下载资源（应该从缓存加载）
        with patch('src.services.resource_manager.aiofiles.open', create=True) as mock_open:
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=test_content)
            mock_open.return_value.__aenter__.return_value = mock_file

            content = await manager.download_resource(
                url="https://example.com/test.pdf",
                resource_key=resource_key,
                use_cache=True
            )

        # 验证返回缓存内容
        assert content == test_content

    @pytest.mark.asyncio
    async def test_save_resource_to_workdir(self, mock_storage, temp_work_dir):
        """测试保存资源到工作目录"""
        # 准备测试数据
        content = b"Test file content"
        subdir = "images"
        filename = "test_image.png"

        # 创建 ResourceManager
        manager = ResourceManager(mock_storage, cache_dir=temp_work_dir)

        # Patch aiofiles
        with patch('src.services.resource_manager.aiofiles.open', create=True) as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            # 保存资源
            file_path = await manager.save_resource(
                content=content,
                work_dir=temp_work_dir,
                subdir=subdir,
                filename=filename
            )

        # 验证文件路径
        expected_path = os.path.join(temp_work_dir, subdir, filename)
        assert file_path == expected_path

        # 验证写入操作
        mock_file.write.assert_called_once_with(content)
