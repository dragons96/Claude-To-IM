# src/cli/main.py
"""CLI 主入口模块

这是应用的启动入口,负责:
- 解析命令行参数
- 加载配置
- 初始化所有组件
- 启动飞书桥接
- 处理关闭信号
"""
import asyncio
import argparse
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import get_settings
from src.claude.sdk_adapter import ClaudeSDKAdapter
from src.services.storage_service import StorageService
from src.services.permission_manager import PermissionManager
from src.services.resource_manager import ResourceManager
from src.services.session_manager import SessionManager
from src.bridges.feishu.message_handler import FeishuMessageHandler
from src.bridges.feishu.command_handler import CommandHandler
from src.bridges.feishu import card_builder
from src.bridges.feishu.adapter import FeishuBridge


logger = logging.getLogger("claude-to-im")


def check_and_initialize() -> None:
    """检查并初始化项目环境

    检查:
    - 虚拟环境是否存在
    - .env 文件是否存在
    - 必要的目录是否存在

    如果缺少虚拟环境，会自动创建。
    如果缺少 .env 文件，会提示用户。
    """
    print("=" * 60)
    print("Claude to IM 服务 - 环境检查")
    print("=" * 60)
    print()

    project_root = Path(__file__).parent.parent.parent
    print(f"📁 项目目录: {project_root}")
    print()

    # 检查并创建虚拟环境
    venv_dir = project_root / ".venv"
    if not venv_dir.exists():
        print("❌ 虚拟环境不存在")
        print()
        print("🔧 正在创建虚拟环境...")

        try:
            import subprocess
            result = subprocess.run(
                ["uv", "venv"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ 虚拟环境创建成功")
            print(f"   输出: {result.stdout[:200]}")
        except subprocess.CalledProcessError as e:
            print(f"❌ 创建虚拟环境失败")
            print(f"   错误: {e.stderr}")
            print()
            print("请手动运行: uv venv")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ 未找到 uv 命令")
            print()
            print("请安装 uv:")
            print("  Windows: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
            print("  Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh")
            sys.exit(1)
        print()
    else:
        print("✅ 虚拟环境已存在")
    print()

    # 检查 .env 文件
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚠️  .env 文件不存在")
        print()
        print("请创建 .env 文件并配置必要的环境变量")
        print()
        print("示例 .env 文件内容:")
        print("-" * 40)
        print("# Application")
        print("APP_NAME=claude-to-im")
        print("DEBUG=false")
        print()
        print("# Database")
        print("DATABASE_URL=sqlite:///sessions/database.db")
        print()
        print("# Session")
        print("DEFAULT_SESSION_ROOT=./sessions")
        print("SESSION_TIMEOUT_HOURS=24")
        print("MAX_SESSIONS_PER_IM=10")
        print()
        print("# Permissions")
        print("ALLOWED_DIRECTORIES=D:/Codes,D:/Tools")
        print()
        print("# Claude SDK")
        print('ANTHROPIC_AUTH_TOKEN="your_token_here"')
        print('ANTHROPIC_BASE_URL="https://open.bigmodel.cn/api/anthropic"')
        print("ANTHROPIC_MODEL=claude-opus-4-6")
        print("MAX_TURNS=10")
        print()
        print("# Feishu")
        print('FEISHU_APP_ID="your_app_id"')
        print('FEISHU_APP_SECRET="your_app_secret"')
        print("-" * 40)
        print()

        # 询问用户是否继续
        response = input("是否继续启动? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ 启动已取消")
            sys.exit(1)
        print()
    else:
        print("✅ .env 文件已存在")
    print()

    # 创建必要的目录
    print("📁 创建必要的目录...")
    dirs_to_create = [
        project_root / "sessions",
        project_root / "logs",
        project_root / "sessions" / "database"
    ]

    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {dir_path.relative_to(project_root)}")

    print()
    print("=" * 60)
    print("✅ 环境检查完成")
    print("=" * 60)
    print()


def setup_logging(settings) -> logging.Logger:
    """设置日志

    配置日志系统,输出到文件和控制台

    Args:
        settings: 应用配置

    Returns:
        logging.Logger: 配置好的logger实例
    """
    # 创建日志目录
    log_file_path = settings.log_file_path
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # 清除现有handlers
    root_logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件handler (带轮转)
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger("claude-to-im")
    logger.info(f"日志初始化完成,级别: {settings.LOG_LEVEL}")
    logger.info(f"日志文件: {log_file_path}")

    return logger


async def create_components(settings) -> Dict[str, Any]:
    """创建所有组件

    初始化并配置所有应用组件

    Args:
        settings: 应用配置

    Returns:
        Dict[str, Any]: 组件字典
    """
    logger.info("初始化组件...")

    # 创建数据库引擎
    logger.info(f"连接数据库: {settings.DATABASE_URL}")
    db_engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True
    )

    # 创建会话工厂
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine,
        future=True
    )

    # 创建数据库会话
    db_session: Session = SessionLocal()

    # 初始化数据库表
    from src.services.models import Base
    Base.metadata.create_all(bind=db_engine)
    logger.info("数据库表初始化完成")

    # 创建存储服务
    storage_service = StorageService(db_session)
    logger.info("存储服务初始化完成")

    # 创建 Claude SDK 适配器
    from claude_agent_sdk import ClaudeAgentOptions

    claude_options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_AUTH_TOKEN": settings.ANTHROPIC_AUTH_TOKEN,
            "ANTHROPIC_BASE_URL": settings.ANTHROPIC_BASE_URL,
        },
        model=settings.ANTHROPIC_MODEL,
        max_turns=settings.MAX_TURNS,
        include_partial_messages=True,
        # 加载所有配置源：用户目录、项目目录、本地目录
        setting_sources=["user", "project", "local"],
        # 工具权限配置
        allowed_tools=settings.allowed_tools_list,
        disallowed_tools=settings.disallowed_tools_list,
    )
    claude_adapter = ClaudeSDKAdapter(claude_options)
    logger.info(f"Claude SDK 适配器初始化完成 (模型: {settings.ANTHROPIC_MODEL})")

    # 显示 Claude SDK 配置信息（MCP 服务器、技能、规则等）
    await claude_adapter.display_config_info(logger)

    # 创建权限管理器
    permission_manager = PermissionManager(
        settings.allowed_directory_list
    )
    logger.info(f"权限管理器初始化完成 (允许目录: {len(settings.allowed_directory_list)})")

    # 创建资源管理器
    cache_dir = str(settings.session_root_path / "cache")
    resource_manager = ResourceManager(
        db_session,
        cache_dir
    )
    logger.info(f"资源管理器初始化完成 (缓存目录: {cache_dir})")

    # 创建会话管理器
    session_manager = SessionManager(
        claude_adapter,
        storage_service,
        str(settings.session_root_path),
        permission_manager
    )
    logger.info(f"会话管理器初始化完成 (根目录: {settings.session_root_path})")

    # 创建飞书消息处理器
    message_handler = FeishuMessageHandler()
    logger.info("飞书消息处理器初始化完成")

    # 创建飞书命令处理器
    command_handler = CommandHandler(
        bridge=None  # 临时设置为None，稍后在创建FeishuBridge后更新
    )
    logger.info("飞书命令处理器初始化完成")

    # 创建飞书桥接适配器
    feishu_config = {
        "app_id": settings.FEISHU_APP_ID,
        "app_secret": settings.FEISHU_APP_SECRET,
        "encrypt_key": settings.FEISHU_ENCRYPT_KEY,
        "verification_token": settings.FEISHU_VERIFICATION_TOKEN,
        "bot_user_id": settings.FEISHU_BOT_USER_ID,
        "send_tool_messages": settings.FEISHU_SEND_TOOL_MESSAGES,
        "settings": settings,  # 传递 settings 对象用于工具权限检查
    }
    feishu_bridge = FeishuBridge(
        config=feishu_config,
        claude_adapter=claude_adapter,
        session_manager=session_manager,
        resource_manager=resource_manager,
        message_handler=message_handler,
        command_handler=command_handler,
        card_builder=card_builder,
        session_root_path=str(settings.session_root_path)
    )
    logger.info("飞书桥接适配器初始化完成")

    # 更新命令处理器的bridge引用
    command_handler.set_bridge(feishu_bridge)
    logger.info("命令处理器bridge引用已更新")

    components = {
        "db_engine": db_engine,
        "db_session": db_session,
        "claude_adapter": claude_adapter,
        "storage_service": storage_service,
        "permission_manager": permission_manager,
        "resource_manager": resource_manager,
        "session_manager": session_manager,
        "message_handler": message_handler,
        "command_handler": command_handler,
        "feishu_bridge": feishu_bridge,
    }

    components = {
        "db_engine": db_engine,
        "db_session": db_session,
        "claude_adapter": claude_adapter,
        "storage_service": storage_service,
        "permission_manager": permission_manager,
        "resource_manager": resource_manager,
        "session_manager": session_manager,
        "message_handler": message_handler,
        "command_handler": command_handler,
        "card_builder": card_builder,
        "feishu_bridge": feishu_bridge,
    }

    logger.info("所有组件初始化完成")

    # 恢复活跃会话（程序重启后根据数据库记录重新创建 SDK 客户端）
    logger.info("=" * 60)
    await session_manager.resume_active_sessions()
    logger.info("=" * 60)

    return components


def setup_signal_handlers(shutdown_event: asyncio.Event):
    """设置信号处理器

    设置 SIGINT 和 SIGTERM 信号处理器,实现优雅关闭

    Args:
        shutdown_event: 关闭事件
    """
    sigint_count = [0]  # 使用列表实现可变计数器

    def signal_handler(signum, frame):
        """信号处理函数"""
        if signum == signal.SIGINT:
            sigint_count[0] += 1
            if sigint_count[0] == 1:
                logger.info(f"收到信号 {signum}, 准备关闭...")
                shutdown_event.set()
            else:
                logger.warning("强制退出...")
                sys.exit(1)
        else:
            logger.info(f"收到信号 {signum}, 准备关闭...")
            shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("信号处理器设置完成")


async def _cleanup_components(components: dict, force: bool = False) -> None:
    """清理组件资源

    Args:
        components: 组件字典
        force: 是否强制清理（忽略错误）
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 1. 停止飞书桥接（设置超时）
        logger.info("停止飞书桥接...")
        try:
            feishu_bridge = components["feishu_bridge"]
            timeout = 2.0 if force else 5.0
            await asyncio.wait_for(feishu_bridge.stop(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("飞书桥接停止超时")
        except asyncio.CancelledError:
            if not force:
                raise
            logger.warning("飞书桥接停止时被取消")
        except Exception as e:
            if not force:
                logger.error(f"停止飞书桥接时出错: {e}")
            else:
                logger.debug(f"停止飞书桥接时出错（强制模式）: {e}")

        # 2. 关闭所有 Claude 会话（使用更robust的错误处理）
        logger.info("关闭 Claude 会话...")
        try:
            claude_adapter = components["claude_adapter"]
            sessions = await claude_adapter.list_sessions()

            for session in sessions:
                session_id = session.session_id
                try:
                    # 使用 shield 保护关闭操作，避免被外部取消
                    # 添加超时保护，避免无限等待
                    await asyncio.shield(
                        asyncio.wait_for(
                            claude_adapter.close_session(session_id),
                            timeout=3.0
                        )
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"关闭会话 {session_id} 超时")
                except asyncio.CancelledError:
                    if not force:
                        raise
                    logger.debug(f"关闭会话 {session_id} 时被取消")
                except RuntimeError as e:
                    # 忽略 cancel scope 错误（跨任务关闭）
                    if "cancel scope" in str(e):
                        logger.debug(f"关闭会话 {session_id} 时遇到 cancel scope 错误，已忽略")
                    else:
                        logger.warning(f"关闭会话 {session_id} 时遇到 RuntimeError: {e}")
                except Exception as e:
                    logger.warning(f"关闭会话 {session_id} 时出错: {e}")

        except asyncio.CancelledError:
            if not force:
                raise
            logger.debug("列出会话时被取消")
        except Exception as e:
            if not force:
                logger.error(f"关闭会话时出错: {e}")
            else:
                logger.debug(f"关闭会话时出错（强制模式）: {e}")

        # 3. 关闭数据库会话
        logger.info("关闭数据库连接...")
        try:
            db_session: Session = components["db_session"]
            db_session.close()
        except Exception as e:
            logger.warning(f"关闭数据库连接时出错: {e}")

        # 4. 关闭数据库引擎
        try:
            db_engine = components["db_engine"]
            db_engine.dispose()
        except Exception as e:
            logger.warning(f"关闭数据库引擎时出错: {e}")

        logger.info("应用已关闭")

    except Exception as e:
        if not force:
            logger.error(f"清理组件时出错: {e}", exc_info=True)
        else:
            logger.debug(f"清理组件时出错（强制模式）: {e}")


async def main_async(
    config_path: Optional[str] = None,
    debug: bool = False
) -> None:
    """主异步函数

    Args:
        config_path: 配置文件路径(可选)
        debug: 调试模式
    """
    try:
        # 加载配置
        logger.info("加载配置...")
        settings = get_settings(config_path)

        # 覆盖调试模式
        if debug:
            settings.DEBUG = True

        # 设置日志
        setup_logging(settings)
        logger.info(f"启动 {settings.APP_NAME}...")
        logger.info(f"调试模式: {'开启' if settings.DEBUG else '关闭'}")

        # 创建所有组件
        components = await create_components(settings)

        # 创建关闭事件
        shutdown_event = asyncio.Event()

        # 设置信号处理器
        setup_signal_handlers(shutdown_event)

        # 启动飞书桥接
        feishu_bridge: FeishuBridge = components["feishu_bridge"]
        logger.info("启动飞书桥接...")
        await feishu_bridge.start()

        # 等待关闭信号
        logger.info("应用运行中,按 Ctrl+C 退出...")
        await shutdown_event.wait()

        # 优雅关闭
        logger.info("正在关闭...")

        try:
            # 使用 shield 保护整个关闭流程，避免被外部取消
            await asyncio.shield(_cleanup_components(components))
        except asyncio.CancelledError:
            logger.info("关闭过程被取消，尝试强制清理...")
            # 即使被取消，也尝试强制清理
            await _cleanup_components(components, force=True)
        except Exception as e:
            logger.error(f"关闭过程中出错: {e}", exc_info=True)

    except asyncio.CancelledError:
        logger.info("应用被取消")
        # 尝试清理资源（忽略清理过程中的错误）
        try:
            if 'components' in locals():
                # 使用 gather 的 return_exceptions=True 来确保所有清理操作都被尝试
                cleanup_tasks = []
                try:
                    # 先尝试优雅关闭
                    cleanup_tasks.append(_cleanup_components(components, force=False))
                except Exception:
                    pass

                # 如果优雅关闭失败，强制关闭
                if cleanup_tasks:
                    results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                    if any(isinstance(r, Exception) for r in results):
                        logger.debug("优雅关闭失败，尝试强制清理")
                        await _cleanup_components(components, force=True)
                else:
                    await _cleanup_components(components, force=True)
        except asyncio.CancelledError:
            # 最后的防护：忽略所有取消错误
            logger.debug("强制清理也被取消，应用即将退出")
        except Exception as cleanup_error:
            logger.debug(f"清理过程中出现异常（将被忽略）: {cleanup_error}")

    except Exception as e:
        logger.error(f"应用运行错误: {e}", exc_info=True)

        # 尝试清理资源
        try:
            if 'components' in locals():
                await _cleanup_components(components, force=True)
        except asyncio.CancelledError:
            # 忽略取消错误
            logger.debug("清理过程被取消")
        except Exception as cleanup_error:
            logger.debug(f"清理资源时出错: {cleanup_error}")

        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """解析命令行参数

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="Claude Code CLI to IM bridge service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 使用默认配置
  %(prog)s --debug                  # 启用调试模式
  %(prog)s --config custom.env      # 使用自定义配置文件
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径 (默认: .env)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )

    return parser.parse_args()


def main() -> None:
    """主入口函数

    解析命令行参数并启动应用
    """
    # 先进行环境检查和初始化
    check_and_initialize()

    args = parse_args()

    # 运行异步主函数
    asyncio.run(main_async(args.config, args.debug))


if __name__ == "__main__":
    main()
