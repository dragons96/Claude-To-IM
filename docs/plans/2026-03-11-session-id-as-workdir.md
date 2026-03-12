# 会话ID作为工作目录名 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改用Claude session_id作为工作目录名，确保重启后能正确恢复到对应的Claude会话

**Architecture:**
1. 修改会话创建逻辑，使用Claude SDK的session_id作为工作目录名（而非飞书会话ID）
2. 保持现有的会话恢复机制，通过session_id匹配工作目录
3. 更新数据库记录以正确映射session_id到工作目录

**Tech Stack:**
- Python 3.11+
- SQLAlchemy (数据库ORM)
- Claude Agent SDK (会话管理)
- pytest (测试框架)

---

## Task 1: 修改 get_or_create_session 方法使用 session_id 作为工作目录

**Files:**
- Modify: `src/services/session_manager.py:84-190`
- Test: `tests/test_services/test_session_manager.py`

**Step 1: 理解当前逻辑**

当前代码（第159行）：
```python
work_directory = self.default_session_root / platform_session_id
```

这导致：
- 同一个飞书对话的所有Claude会话共享一个工作目录
- 重启后无法区分不同的Claude会话

**Step 2: 先创建Claude会话，再创建工作目录**

将第156-161行的逻辑调整为：
```python
# 没有活跃会话,创建新会话
# 先创建 Claude SDK 会话（生成 session_id）
logger.info("没有活跃会话，创建新会话...")
logger.info("调用 Claude SDK 创建会话...")
claude_session = await self.claude_adapter.create_session(
    work_directory=str(self.default_session_root)  # 临时目录，后面会移动
)

if not claude_session:
    raise RuntimeError(f"Claude SDK 创建会话失败，返回了 None")

logger.info(f"Claude SDK 会话已创建，ID: {claude_session.session_id}")

# 使用 session_id 作为工作目录名
work_directory = self.default_session_root / claude_session.session_id
work_directory.mkdir(parents=True, exist_ok=True)
logger.info(f"工作目录已创建: {work_directory}")

# 更新会话的工作目录（需要 SDK adapter 支持更新工作目录）
await self.claude_adapter.update_session_work_directory(
    claude_session.session_id,
    str(work_directory)
)
```

**Step 3: 添加数据库记录保存逻辑（保持不变）**

第174-184行的逻辑保持不变，但work_directory已经是session_id目录了。

**Step 4: 提交更改**

```bash
git add src/services/session_manager.py
git commit -m "refactor: 使用Claude session_id作为工作目录名"
```

---

## Task 2: 在 ClaudeSDKAdapter 中添加 update_session_work_directory 方法

**Files:**
- Modify: `src/claude/sdk_adapter.py`
- Test: `tests/test_claude/test_sdk_adapter.py`

**Step 1: 添加方法到 ClaudeSDKAdapter 类**

在 `sdk_adapter.py` 的 `close_session` 方法后添加：

```python
async def update_session_work_directory(
    self,
    session_id: str,
    new_work_directory: str
) -> None:
    """更新会话的工作目录

    Args:
        session_id: 会话 ID
        new_work_directory: 新的工作目录路径

    Raises:
        ValueError: 会话不存在
    """
    import logging
    logger = logging.getLogger(__name__)

    if session_id not in self.sessions:
        raise ValueError(f"Session {session_id} not found")

    session_data = self.sessions[session_id]
    client = session_data["client"]

    # 更新客户端的工作目录
    # 注意：这需要重新创建客户端连接，因为SDK可能不支持动态更改cwd
    # 临时方案：关闭旧客户端，创建新客户端

    # 关闭旧连接
    if hasattr(client, '__aexit__'):
        try:
            await asyncio.wait_for(
                client.__aexit__(None, None, None),
                timeout=3.0
            )
        except Exception as e:
            logger.warning(f"关闭旧连接时出错: {e}")

    # 创建新的客户端选项
    session_options = copy.copy(self.options)
    session_options.cwd = new_work_directory

    # 创建新客户端
    new_client = ClaudeSDKClient(session_options)

    # 建立新连接
    if hasattr(new_client, '__aenter__'):
        await new_client.__aenter__()

    # 更新会话数据
    self.sessions[session_id]["client"] = new_client
    self.sessions[session_id]["session"].work_directory = new_work_directory

    logger.info(f"会话 {session_id} 的工作目录已更新为: {new_work_directory}")
```

**Step 2: 提交更改**

```bash
git add src/claude/sdk_adapter.py
git commit -m "feat: 添加更新会话工作目录的方法"
```

---

## Task 3: 修改 create_session 方法支持自定义目录

**Files:**
- Modify: `src/services/session_manager.py:191-247`
- Test: `tests/test_services/test_session_manager.py`

**Step 1: 更新 create_session 方法**

当用户通过 `/new` 命令指定工作目录时，也需要使用session_id作为子目录：

```python
async def create_session(
    self,
    platform: str,
    platform_session_id: str,
    work_directory: str,
    summary: str
) ) -> ClaudeAdapterSession:
    """创建新的 Claude 会话

    Args:
        platform: 平台名称
        platform_session_id: 平台会话 ID
        work_directory: 工作目录路径（父目录）
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

    # 先创建 Claude SDK 会话（生成 session_id）
    claude_session = await self.claude_adapter.create_session(
        work_directory=work_directory  # 临时使用父目录
    )

    # 使用 session_id 作为最终的子目录
    work_path = Path(work_directory) / claude_session.session_id
    work_path.mkdir(parents=True, exist_ok=True)

    # 更新会话的工作目录
    await self.claude_adapter.update_session_work_directory(
        claude_session.session_id,
        str(work_path)
    )

    # 保存到数据库
    await self.storage.create_claude_session(
        id=str(uuid.uuid4()),
        im_session_id=im_session.id,
        session_id=claude_session.session_id,
        work_directory=str(work_path),  # 保存完整的路径（包含session_id）
        summary=summary[:10] if len(summary) > 10 else summary,
        is_active=True
    )

    return claude_session
```

**Step 2: 提交更改**

```bash
git add src/services/session_manager.py
git commit -m "refactor: create_session 也使用 session_id 作为子目录"
```

---

## Task 4: 确认 resume_active_sessions 逻辑正确

**Files:**
- Review: `src/services/session_manager.py:32-83`

**Step 1: 验证恢复逻辑**

检查第32-83行的 `resume_active_sessions` 方法：
- 第65行：`session_id=db_session_record.session_id` - 正确使用了数据库中的session_id
- 第64行：`work_directory=db_session_record.work_directory` - 正确使用了对应的工作目录

由于我们已经确保数据库中存储的是 session_id 对应的工作目录，恢复逻辑无需修改。

**Step 5: 无需提交（验证通过）**

---

## Task 5: 编写单元测试验证新逻辑

**Files:**
- Create: `tests/test_services/test_session_manager_workdir.py`

**Step 1: 编写测试用例**

```python
import pytest
import tempfile
from pathlib import Path
from src.services.session_manager import SessionManager
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.asyncio
async def test_session_id_used_as_work_directory():
    """测试使用 session_id 作为工作目录名"""
    # 准备测试数据
    platform = "feishu"
    platform_session_id = "feishu_chat_123"

    # 创建 mock 对象
    mock_adapter = Mock()
    mock_storage = Mock()
    mock_permission = Mock()

    # 创建临时目录作为会话根目录
    with tempfile.TemporaryDirectory() as temp_dir:
        session_root = Path(temp_dir)

        # Mock adapter.create_session 返回带 session_id 的会话
        expected_session_id = "test-session-uuid-456"
        mock_session = Mock()
        mock_session.session_id = expected_session_id
        mock_session.work_directory = str(session_root)

        mock_adapter.create_session = AsyncMock(return_value=mock_session)
        mock_adapter.update_session_work_directory = AsyncMock()

        # Mock storage 方法
        mock_storage.get_im_session_by_platform_id = AsyncMock(return_value=None)
        mock_storage.create_im_session = AsyncMock(
            return_value=Mock(id="im_session_123")
        )
        mock_storage.get_active_claude_sessions = AsyncMock(return_value=[])
        mock_storage.create_claude_session = AsyncMock()

        # 创建 SessionManager
        manager = SessionManager(
            claude_adapter=mock_adapter,
            storage=mock_storage,
            default_session_root=str(session_root),
            permission_manager=mock_permission
        )

        # 执行测试
        result = await manager.get_or_create_session(
            platform, platform_session_id
        )

        # 验证结果
        assert result.session_id == expected_session_id

        # 验证 create_session 被调用
        mock_adapter.create_session.assert_called_once()

        # 验证 update_session_work_directory 被调用
        mock_adapter.update_session_work_directory.assert_called_once()
        call_args = mock_adapter.update_session_work_directory.call_args
        assert call_args[0][0] == expected_session_id

        # 验证工作目录路径包含 session_id
        work_dir_arg = call_args[0][1]
        assert expected_session_id in work_dir_arg

        # 验证数据库保存的路径包含 session_id
        save_call = mock_storage.create_claude_session.call_args
        saved_work_dir = save_args[1]['work_directory']
        assert expected_session_id in saved_work_dir


@pytest.mark.asyncio
async def test_resume_restores_correct_work_directory():
    """测试恢复会话时使用正确的工作目录"""
    # 准备测试数据
    session_id = "test-session-uuid-789"
    work_directory = "/sessions/test-session-uuid-789"

    # 创建 mock 对象
    mock_adapter = Mock()
    mock_storage = Mock()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock 数据库查询返回活跃会话
        mock_db_session = Mock()
        mock_db_session.session_id = session_id
        mock_db_session.work_directory = work_directory
        mock_db_session.is_active = True

        mock_storage.db.query.return_value.filter_by.return_value.all.return_value = [
            mock_db_session
        ]

        # Mock adapter.create_session
        mock_session = Mock()
        mock_session.session_id = session_id
        mock_adapter.create_session = AsyncMock(return_value=mock_session)

        # 创建 SessionManager
        manager = SessionManager(
            claude_adapter=mock_adapter,
            storage=mock_storage,
            default_session_root=temp_dir,
            permission_manager=Mock()
        )

        # 执行恢复
        await manager.resume_active_sessions()

        # 验证使用正确的 session_id 和 work_directory
        mock_adapter.create_session.assert_called_once_with(
            work_directory=work_directory,
            session_id=session_id
        )
```

**Step 2: 运行测试**

```bash
pytest tests/test_services/test_session_manager_workdir.py -v
```

预期：所有测试通过

**Step 3: 提交测试**

```bash
git add tests/test_services/test_session_manager_workdir.py
git commit -m "test: 添加session_id作为工作目录的测试"
```

---

## Task 6: 更新现有测试以适应新逻辑

**Files:**
- Modify: `tests/test_services/test_session_manager.py`

**Step 1: 检查并更新现有测试**

查找所有涉及工作目录路径的测试断言，更新为预期session_id在路径中。

**Step 2: 运行所有测试**

```bash
pytest tests/test_services/test_session_manager.py -v
```

**Step 3: 提交更改**

```bash
git add tests/test_services/test_session_manager.py
git commit -m "test: 更新会话管理测试以适配新的目录结构"
```

---

## Task 7: 集成测试验证完整流程

**Files:**
- Create: `tests/integration/test_session_resume_integration.py`

**Step 1: 编写集成测试**

```python
import pytest
import tempfile
from pathlib import Path
from src.services.session_manager import SessionManager
from src.claude.sdk_adapter import ClaudeSDKAdapter
from src.services.storage_service import StorageService
from claude_agent_sdk import ClaudeAgentOptions


@pytest.mark.asyncio
async def test_full_session_lifecycle_with_resume():
    """测试完整的会话生命周期和恢复流程"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 初始化组件
        db_path = Path(temp_dir) / "test.db"
        storage = StorageService(f"sqlite:///{db_path}")
        await storage.initialize()

        options = ClaudeAgentOptions()
        adapter = ClaudeSDKAdapter(options)

        manager = SessionManager(
            claude_adapter=adapter,
            storage=storage,
            default_session_root=str(Path(temp_dir) / "sessions"),
            permission_manager=Mock()
        )

        # 1. 创建第一个会话
        session1 = await manager.get_or_create_session(
            "feishu", "chat_123"
        )

        # 验证工作目录包含 session_id
        work_dir = Path(session1.work_directory)
        assert session1.session_id in work_dir.name
        assert work_dir.exists()

        # 2. 创建第二个会话（同一飞书对话）
        # 将第一个会话标记为非活跃
        await storage.set_claude_session_active(
            session1.session_id, False
        )

        session2 = await manager.get_or_create_session(
            "feishu", "chat_123"
        )

        # 验证第二个会话有不同的工作目录
        work_dir2 = Path(session2.work_directory)
        assert session2.session_id in work_dir2.name
        assert work_dir != work_dir2

        # 3. 模拟重启 - 清空内存中的会话
        adapter.sessions.clear()

        # 4. 恢复会话
        await manager.resume_active_sessions()

        # 验证会话被正确恢复
        restored_session = await adapter.get_session_info(session2.session_id)
        assert restored_session is not None
        assert restored_session.work_directory == session2.work_directory
```

**Step 2: 运行集成测试**

```bash
pytest tests/integration/test_session_resume_integration.py -v
```

**Step 3: 提交集成测试**

```bash
git add tests/integration/test_session_resume_integration.py
git commit -m "test: 添加会话恢复集成测试"
```

---

## Task 8: 文档更新

**Files:**
- Create: `docs/architecture/session_management.md`

**Step 1: 创建会话管理架构文档**

```markdown
# 会话管理架构

## 目录结构

### 旧版本（基于飞书会话ID）
```
sessions/
└── feishu_chat_123/          # 飞书会话ID
    ├── .claude/
    └── ...
```

**问题：**
- 同一飞书对话的多个Claude会话共享目录
- 重启后无法区分不同的Claude会话

### 新版本（基于Claude session_id）
```
sessions/
├── abc123-def456-.../        # Claude会话1的session_id
│   ├── .claude/
│   └── ...
└── xyz789-uvw012-.../        # Claude会话2的session_id
    ├── .claude/
    └── ...
```

**优势：**
- 每个Claude会话独立目录
- 重启后通过session_id精确恢复
- 支持同一飞书对话的多个独立Claude会话

## 数据库映射

```
IMSession (飞书会话)
    ↓ 1:N
ClaudeSession (Claude会话)
    - session_id: UUID
    - work_directory: sessions/<session_id>
```

## 会话恢复流程

1. 程序启动时，查询数据库中所有 `is_active=True` 的会话
2. 对每个活跃会话：
   - 读取 `session_id` 和 `work_directory`
   - 调用 `claude_adapter.create_session(session_id=X, work_directory=Y)`
   - SDK恢复该会话的上下文
3. 恢复失败的会话被标记为 `is_active=False`
```

**Step 2: 提交文档**

```bash
git add docs/architecture/session_management.md
git commit -m "docs: 添加会话管理架构文档"
```

---

## Task 9: 手动验证

**Step 1: 启动服务并创建会话**

```bash
python -m src.cli.main
```

在飞书中发送消息创建会话。

**Step 2: 检查目录结构**

```bash
ls -la sessions/
```

验证目录名是UUID格式的session_id。

**Step 3: 重启服务**

```bash
# Ctrl+C 停止服务
python -m src.cli.main
```

**Step 4: 验证会话恢复**

在飞书中继续对话，验证：
- AI记得之前的对话历史
- 工作目录正确

---

## Task 10: 清理旧数据（可选）

**警告:** 仅在开发环境执行，生产环境需要备份！

**Step 1: 创建数据迁移脚本**

创建 `bin/migrate_to_session_id_dirs.sh`:

```bash
#!/bin/bash
# 将旧的基于飞书会话ID的目录迁移到新的基于session_id的结构

echo "此脚本将迁移旧的会话目录结构"
echo "建议先备份数据！"
read -p "继续? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# 实现迁移逻辑...
```

**Step 2: 提交脚本**

```bash
git add bin/migrate_to_session_id_dirs.sh
git commit -m "feat: 添加会话目录迁移脚本"
```

---

## 测试清单

完成所有任务后，验证：

- [ ] 单元测试全部通过
- [ ] 集成测试通过
- [ ] 手动测试：创建会话后目录名是session_id
- [ ] 手动测试：重启后会话正确恢复
- [ ] 手动测试：同一飞书对话的多个Claude会话有独立目录
- [ ] 文档完整且准确

## 回滚计划

如果出现问题，可以：
1. 回滚代码到修改前的commit
2. 数据库记录保持兼容（work_directory字段存储完整路径）
3. 使用数据迁移脚本恢复旧目录结构
