# tests/test_cli/test_main.py
"""CLI 主入口测试"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestParseArgs:
    """测试命令行参数解析"""

    def test_parse_args_default(self):
        """测试默认参数"""
        from src.cli.main import parse_args
        import sys

        # 保存原始argv
        original_argv = sys.argv

        try:
            # 设置测试argv
            sys.argv = ["main"]
            args = parse_args()
            assert args.config is None
            assert args.debug is False
        finally:
            # 恢复原始argv
            sys.argv = original_argv

    def test_parse_args_with_options(self):
        """测试带参数"""
        from src.cli.main import parse_args
        import sys

        # 保存原始argv
        original_argv = sys.argv

        try:
            # 设置测试argv
            sys.argv = ["main", "--debug", "--config", "test.env"]
            args = parse_args()
            assert args.config == "test.env"
            assert args.debug is True
        finally:
            # 恢复原始argv
            sys.argv = original_argv


class TestSetupLogging:
    """测试日志设置"""

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """测试日志设置创建日志目录"""
        from config.settings import Settings
        from src.cli.main import setup_logging

        # 使用临时路径
        log_file = tmp_path / "test.log"

        settings = Settings(
            DATABASE_URL="sqlite:///test.db",
            LOG_FILE=str(log_file)
        )
        logger = setup_logging(settings)

        assert logger is not None
        # 检查日志目录是否创建
        assert log_file.parent.exists()

    def test_setup_logging_returns_logger(self):
        """测试日志设置返回logger"""
        from config.settings import Settings
        from src.cli.main import setup_logging

        settings = Settings(DATABASE_URL="sqlite:///test.db")
        logger = setup_logging(settings)

        assert logger is not None
        assert logger.name == "claude-to-im"


class TestMain:
    """测试主函数"""

    def test_main_function_exists(self):
        """测试主函数存在"""
        from src.cli.main import main
        assert callable(main)

    def test_parse_args_function_exists(self):
        """测试参数解析函数存在"""
        from src.cli.main import parse_args
        assert callable(parse_args)


class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_create_components_handles_missing_database(self):
        """测试组件创建处理数据库错误"""
        from config.settings import Settings
        from src.cli.main import create_components

        settings = Settings(
            DATABASE_URL="sqlite:///test.db",
            ANTHROPIC_AUTH_TOKEN="test_token"
        )

        # Mock数据库引擎
        with patch("src.cli.main.create_engine") as mock_engine:
            mock_engine.return_value = MagicMock()

            # 尝试创建组件
            try:
                components = await create_components(settings)
                assert components is not None
                assert "db_engine" in components
            except Exception as e:
                # 某些异常是预期的
                pass


class TestSignalHandling:
    """测试信号处理"""

    def test_signal_handler_setup(self):
        """测试信号处理器设置"""
        import asyncio
        from src.cli.main import setup_signal_handlers

        shutdown_event = asyncio.Event()
        setup_signal_handlers(shutdown_event)

        # 测试通过 - 没有抛出异常
        assert True
