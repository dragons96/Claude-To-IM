"""配置管理模块测试"""
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config.settings import Settings, get_settings, _reset_settings


@pytest.fixture(autouse=True)
def reset_settings():
    """每个测试前重置配置"""
    _reset_settings()
    yield
    _reset_settings()


@pytest.fixture
def temp_env_file():
    """创建临时环境变量文件并备份现有的.env文件"""
    env_path = Path(__file__).parent.parent / ".env"
    backup_path = None

    if env_path.exists():
        backup_path = env_path.with_suffix(".env.backup")
        shutil.copy(env_path, backup_path)
        env_path.unlink()

    yield

    # 恢复原始.env文件
    if backup_path and backup_path.exists():
        shutil.copy(backup_path, env_path)
        backup_path.unlink()


class TestSettingsLoading:
    """测试配置加载"""

    def test_settings_loading_from_env(self):
        """测试从环境变量加载配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
APP_NAME=test-app
DEBUG=true
DATABASE_URL=sqlite:///test.db
DEFAULT_SESSION_ROOT=/tmp/sessions
SESSION_TIMEOUT_HOURS=12
MAX_SESSIONS_PER_IM=5
ALLOWED_DIRECTORIES=/tmp,/home
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://test.api.com
ANTHROPIC_MODEL=claude-test
MAX_TURNS=20
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
RESOURCE_CACHE_DAYS=14
MAX_FILE_SIZE_MB=50
""")
            env_file = f.name

        try:
            # 模拟从指定文件加载
            settings = Settings(_env_file=env_file)

            # 验证配置对象创建成功
            assert isinstance(settings, Settings)
            assert settings.APP_NAME == "test-app"
            assert settings.DEBUG is True
            assert settings.DATABASE_URL == "sqlite:///test.db"
            assert settings.DEFAULT_SESSION_ROOT == "/tmp/sessions"
            assert settings.SESSION_TIMEOUT_HOURS == 12
            assert settings.MAX_SESSIONS_PER_IM == 5
            assert settings.ALLOWED_DIRECTORIES == "/tmp,/home"
            assert settings.allowed_directory_list == ["/tmp", "/home"]
            assert settings.ANTHROPIC_MODEL == "claude-test"
            assert settings.MAX_TURNS == 20
            assert settings.FEISHU_APP_ID == "test_app_id"
            assert settings.FEISHU_APP_SECRET == "test_secret"
            assert settings.RESOURCE_CACHE_DAYS == 14
            assert settings.MAX_FILE_SIZE_MB == 50
        finally:
            os.unlink(env_file)

    def test_settings_parsing_comma_separated_list(self, temp_env_file):
        """测试逗号分隔列表解析"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
ALLOWED_DIRECTORIES=/path1,/path2,/path3
""")
            env_file = f.name

        try:
            settings = Settings(_env_file=env_file)
            assert settings.allowed_directory_list == ["/path1", "/path2", "/path3"]
        finally:
            os.unlink(env_file)


class TestDefaultValues:
    """测试默认值"""

    def test_default_app_name(self, temp_env_file):
        """测试默认应用名称"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
""")
            env_file = f.name

        try:
            settings = Settings(_env_file=env_file)
            assert settings.APP_NAME == "claude-to-im"
        finally:
            os.unlink(env_file)

    def test_default_debug_false(self, temp_env_file):
        """测试默认DEBUG为False"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
""")
            env_file = f.name

        try:
            settings = Settings(_env_file=env_file)
            assert settings.DEBUG is False
        finally:
            os.unlink(env_file)


class TestValidation:
    """测试验证"""

    def test_missing_required_field(self, temp_env_file):
        """测试缺少必填字段"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
# 缺少 DATABASE_URL (必填字段)
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
""")
            env_file = f.name

        try:
            with pytest.raises(ValidationError) as exc_info:
                Settings(_env_file=env_file)

            errors = exc_info.value.errors()
            error_fields = {e['loc'][0] for e in errors}
            assert 'DATABASE_URL' in error_fields
        finally:
            os.unlink(env_file)

    def test_invalid_type_conversion(self, temp_env_file):
        """测试无效类型转换"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
SESSION_TIMEOUT_HOURS=not_a_number
""")
            env_file = f.name

        try:
            with pytest.raises(ValidationError):
                Settings(_env_file=env_file)
        finally:
            os.unlink(env_file)

    def test_invalid_boolean_value(self, temp_env_file):
        """测试无效布尔值"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
DEBUG=not_a_boolean
""")
            env_file = f.name

        try:
            with pytest.raises(ValidationError):
                Settings(_env_file=env_file)
        finally:
            os.unlink(env_file)


class TestGetSettings:
    """测试全局配置实例"""

    def test_get_settings_singleton(self, temp_env_file):
        """测试获取全局配置实例（单例）"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
""")
            env_file = f.name

        try:
            settings1 = get_settings(config_path=env_file)
            settings2 = get_settings(config_path=env_file)

            # 验证返回的是同一个实例
            assert settings1 is settings2
        finally:
            os.unlink(env_file)

    def test_get_settings_type(self, temp_env_file):
        """测试get_settings返回正确的类型"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
DATABASE_URL=sqlite:///test.db
ANTHROPIC_AUTH_TOKEN=test_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-test
FEISHU_APP_ID=test_app_id
FEISHU_APP_SECRET=test_secret
""")
            env_file = f.name

        try:
            settings = get_settings(config_path=env_file)
            assert isinstance(settings, Settings)
        finally:
            os.unlink(env_file)
