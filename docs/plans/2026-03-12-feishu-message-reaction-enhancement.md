# 飞书消息表情反应增强实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 在飞书消息处理中添加表情反应功能，实现"敲键盘"和"完成"状态反馈，并使AI回复引用用户消息以提升消息链可追溯性。

**架构:** 创建独立的FeishuReactionManager服务类封装所有表情API操作，在FeishuAdapter中集成表情管理并维护会话状态字典，表情操作失败不影响主流程。

**技术栈:** Python 3.10+, lark_oapi SDK, structlog, pytest, asyncio

---

## 前置准备

### Task 0: 环境验证

**目标:** 确保开发环境已准备就绪

**文件:** 无

**Step 1: 检查Python版本**

```bash
python --version
```

Expected: `Python 3.10.0` 或更高

**Step 2: 检查lark_oapi SDK已安装**

```bash
pip show lark-oapi
```

Expected: 显示包信息（包含版本号），如果未安装则运行：
```bash
uv pip install lark-oapi
```

**Step 3: 检查测试依赖**

```bash
pip show pytest pytest-asyncio
```

Expected: 显示包信息，如果未安装则运行：
```bash
uv pip install pytest pytest-asyncio
```

**Step 4: 运行现有测试确保基础功能正常**

```bash
pytest tests/ -v --tb=short
```

Expected: 所有现有测试通过

---

## Phase 1: 创建FeishuReactionManager类

### Task 1: 创建reaction_manager.py文件骨架

**文件:**
- Create: `src/bridges/feishu/reaction_manager.py`

**Step 1: 创建文件和基础类结构**

```python
# src/bridges/feishu/reaction_manager.py

"""
飞书消息表情反应管理器

负责处理飞书消息的表情反应操作，包括添加、删除和替换表情。
"""

from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class FeishuReactionManager:
    """飞书消息表情反应管理器"""

    # 表情类型常量
    EMOJI_TYPING = "Typing"
    EMOJI_DONE = "DONE"

    def __init__(self, http_client, bot_user_id: str):
        """
        初始化表情管理器

        Args:
            http_client: 飞书HTTP客户端
            bot_user_id: 机器人的user_id，用于指定操作者
        """
        self._http_client = http_client
        self._bot_user_id = bot_user_id
```

**Step 2: 运行语法检查**

```bash
python -m py_compile src/bridges/feishu/reaction_manager.py
```

Expected: 无语法错误

**Step 3: 提交**

```bash
git add src/bridges/feishu/reaction_manager.py
git commit -m "feat: 创建FeishuReactionManager类骨架"
```

---

### Task 2: 实现add_reaction方法（添加表情的通用方法）

**文件:**
- Modify: `src/bridges/feishu/reaction_manager.py`
- Test: Create: `tests/bridges/feishu/test_reaction_manager.py`

**Step 1: 先编写失败的测试**

创建测试文件：

```python
# tests/bridges/feishu/test_reaction_manager.py

"""
FeishuReactionManager单元测试
"""

import pytest
from unittest.mock import AsyncMock, Mock
from src.bridges.feishu.reaction_manager import FeishuReactionManager


class TestFeishuReactionManager:

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        """测试成功添加表情"""
        # 准备mock
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 0
        mock_response.data = Mock()
        mock_response.data.reaction_id = "test_reaction_123"
        mock_http_client.im.v1.message_reaction.create.return_value = mock_response

        # 执行
        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_reaction("msg_456", "Typing")

        # 验证
        assert reaction_id == "test_reaction_123"
        mock_http_client.im.v1.message_reaction.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_api_error(self):
        """测试API返回错误码"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 231003  # 消息不存在
        mock_response.msg = "message not found"
        mock_http_client.im.v1.message_reaction.create.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_reaction("msg_456", "Typing")

        assert reaction_id is None

    @pytest.mark.asyncio
    async def test_add_reaction_exception(self):
        """测试网络异常"""
        mock_http_client = AsyncMock()
        mock_http_client.im.v1.message_reaction.create.side_effect = Exception("Network error")

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_reaction("msg_456", "Typing")

        assert reaction_id is None
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_add_reaction_success -v
```

Expected: FAIL - `AttributeError: 'FeishuReactionManager' object has no attribute 'add_reaction'`

**Step 3: 实现add_reaction方法**

在`src/bridges/feishu/reaction_manager.py`中添加方法：

```python
from lark_oapi.api.im.v1 import (
    CreateMessageReactionRequest,
    DeleteMessageReactionRequest
)

class FeishuReactionManager:
    # ... 现有代码 ...

    async def add_reaction(self, message_id: str, emoji_type: str) -> Optional[str]:
        """
        通用方法：添加表情反应

        Args:
            message_id: 消息ID
            emoji_type: 表情类型（如"Typing", "DONE"）

        Returns:
            reaction_id: 表情反应ID，失败返回None
        """
        try:
            # 导入ReactionType（在方法内部导入避免循环依赖）
            from lark_oapi.api.im.v1.model.reaction_type import ReactionType

            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    ReactionType.builder()
                        .emoji_type(emoji_type)
                        .build()
                ) \
                .operator_id(self._bot_user_id) \
                .operator_type("user") \
                .build()

            response = await self._http_client.im.v1.message_reaction.create(request)

            if response.code == 0 and response.data:
                reaction_id = response.data.reaction_id
                logger.info(
                    f"成功添加表情 {emoji_type} 到消息 {message_id}",
                    reaction_id=reaction_id
                )
                return reaction_id
            else:
                logger.error(
                    f"添加表情失败: code={response.code}, msg={response.msg}",
                    message_id=message_id,
                    emoji_type=emoji_type
                )
                return None

        except Exception as e:
            logger.error(
                f"添加表情异常: {e}",
                exc_info=True,
                message_id=message_id,
                emoji_type=emoji_type
            )
            return None
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_add_reaction_success -v
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_add_reaction_api_error -v
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_add_reaction_exception -v
```

Expected: 所有三个测试都PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/reaction_manager.py tests/bridges/feishu/test_reaction_manager.py
git commit -m "feat: 实现add_reaction方法并添加单元测试"
```

---

### Task 3: 实现delete_reaction方法

**文件:**
- Modify: `src/bridges/feishu/reaction_manager.py`
- Modify: `tests/bridges/feishu/test_reaction_manager.py`

**Step 1: 编写失败的测试**

在测试文件中添加：

```python
class TestFeishuReactionManager:
    # ... 现有测试 ...

    @pytest.mark.asyncio
    async def test_delete_reaction_success(self):
        """测试成功删除表情"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 0
        mock_http_client.im.v1.message_reaction.delete.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        success = await manager.delete_reaction("msg_456", "reaction_123")

        assert success is True
        mock_http_client.im.v1.message_reaction.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_reaction_failure(self):
        """测试删除失败"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 231003
        mock_response.msg = "reaction not found"
        mock_http_client.im.v1.message_reaction.delete.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        success = await manager.delete_reaction("msg_456", "reaction_123")

        assert success is False
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_delete_reaction_success -v
```

Expected: FAIL - 方法不存在

**Step 3: 实现delete_reaction方法**

在`src/bridges/feishu/reaction_manager.py`中添加：

```python
class FeishuReactionManager:
    # ... 现有代码 ...

    async def delete_reaction(self, message_id: str, reaction_id: str) -> bool:
        """
        通用方法：删除表情反应

        Args:
            message_id: 消息ID
            reaction_id: 表情反应ID

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            request = DeleteMessageReactionRequest.builder() \
                .message_id(message_id) \
                .reaction_id(reaction_id) \
                .operator_id(self._bot_user_id) \
                .operator_type("user") \
                .build()

            response = await self._http_client.im.v1.message_reaction.delete(request)

            if response.code == 0:
                logger.info(
                    f"成功删除表情 reaction_id: {reaction_id}",
                    reaction_id=reaction_id,
                    message_id=message_id
                )
                return True
            else:
                logger.error(
                    f"删除表情失败: code={response.code}, msg={response.msg}",
                    reaction_id=reaction_id,
                    message_id=message_id
                )
                return False

        except Exception as e:
            logger.error(
                f"删除表情异常: {e}",
                exc_info=True,
                reaction_id=reaction_id,
                message_id=message_id
            )
            return False
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_delete_reaction_success -v
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_delete_reaction_failure -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/reaction_manager.py tests/bridges/feishu/test_reaction_manager.py
git commit -m "feat: 实现delete_reaction方法并添加测试"
```

---

### Task 4: 实现高级方法add_typing和replace_with_done

**文件:**
- Modify: `src/bridges/feishu/reaction_manager.py`
- Modify: `tests/bridges/feishu/test_reaction_manager.py`

**Step 1: 编写失败的测试**

在测试文件中添加：

```python
class TestFeishuReactionManager:
    # ... 现有测试 ...

    @pytest.mark.asyncio
    async def test_add_typing(self):
        """测试添加敲键盘表情"""
        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.code = 0
        mock_response.data = Mock()
        mock_response.data.reaction_id = "typing_reaction_123"
        mock_http_client.im.v1.message_reaction.create.return_value = mock_response

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        reaction_id = await manager.add_typing("msg_456")

        assert reaction_id == "typing_reaction_123"

    @pytest.mark.asyncio
    async def test_replace_with_done_success(self):
        """测试成功替换表情为完成"""
        mock_http_client = AsyncMock()
        mock_http_client.im.v1.message_reaction.delete.return_value = Mock(code=0)
        mock_http_client.im.v1.message_reaction.create.return_value = Mock(code=0)

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        success = await manager.replace_with_done("msg_456", "reaction_123")

        assert success is True

    @pytest.mark.asyncio
    async def test_replace_with_done_delete_fails(self):
        """测试删除失败时整体返回False"""
        mock_http_client = AsyncMock()
        mock_http_client.im.v1.message_reaction.delete.return_value = Mock(code=231003)

        manager = FeishuReactionManager(mock_http_client, "bot_123")
        success = await manager.replace_with_done("msg_456", "reaction_123")

        assert success is False
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/bridges/feishu/test_reaction_manager.py::TestFeishuReactionManager::test_add_typing -v
```

Expected: FAIL

**Step 3: 实现高级方法**

在`src/bridges/feishu/reaction_manager.py`中添加：

```python
class FeishuReactionManager:
    # ... 现有代码 ...

    async def add_typing(self, message_id: str) -> Optional[str]:
        """
        为消息添加"敲键盘"表情反应

        Args:
            message_id: 消息ID

        Returns:
            reaction_id: 表情反应ID，失败返回None
        """
        return await self.add_reaction(message_id, self.EMOJI_TYPING)

    async def replace_with_done(self, message_id: str, reaction_id: str) -> bool:
        """
        将"敲键盘"表情替换为"完成"表情

        Args:
            message_id: 消息ID
            reaction_id: 要删除的"敲键盘"表情ID

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            # 先删除Typing表情
            await self.delete_reaction(message_id, reaction_id)
            # 添加Done表情
            await self.add_reaction(message_id, self.EMOJI_DONE)
            return True
        except Exception as e:
            logger.error(
                f"替换表情失败: {e}",
                exc_info=True,
                message_id=message_id,
                reaction_id=reaction_id
            )
            return False
```

**Step 4: 运行所有测试确认通过**

```bash
pytest tests/bridges/feishu/test_reaction_manager.py -v
```

Expected: 所有测试PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/reaction_manager.py tests/bridges/feishu/test_reaction_manager.py
git commit -m "feat: 实现add_typing和replace_with_done高级方法"
```

---

## Phase 2: 集成到FeishuAdapter

### Task 5: 在FeishuAdapter中初始化reaction_manager

**文件:**
- Modify: `src/bridges/feishu/adapter.py`
- Test: Create: `tests/bridges/feishu/test_adapter_reaction_integration.py`

**Step 1: 先编写测试验证初始化**

创建集成测试文件：

```python
# tests/bridges/feishu/test_adapter_reaction_integration.py

"""
FeishuAdapter表情管理集成测试
"""

import pytest
from unittest.mock import Mock
from src.bridges.feishu.adapter import FeishuAdapter
from src.bridges.feishu.reaction_manager import FeishuReactionManager


class TestFeishuAdapterReactionIntegration:
    """测试FeishuAdapter与ReactionManager的集成"""

    def test_adapter_has_reaction_manager(self):
        """测试Adapter初始化时创建reaction_manager"""
        # 创建mock依赖
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        # 创建adapter
        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        # 验证
        assert hasattr(adapter, 'reaction_manager')
        assert isinstance(adapter.reaction_manager, FeishuReactionManager)
        assert adapter.reaction_manager._bot_user_id == "bot_123"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration::test_adapter_has_reaction_manager -v
```

Expected: FAIL - `reaction_manager`属性不存在

**Step 3: 修改FeishuAdapter添加初始化**

找到`src/bridges/feishu/adapter.py`的`__init__`方法，添加导入和初始化：

在文件顶部添加导入：
```python
from .reaction_manager import FeishuReactionManager
```

在`__init__`方法中添加（在现有初始化代码之后）：
```python
# 表情管理器
self.reaction_manager = FeishuReactionManager(
    http_client=self._http_client,
    bot_user_id=self.bot_user_id
)
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration::test_adapter_has_reaction_manager -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/adapter.py tests/bridges/feishu/test_adapter_reaction_integration.py
git commit -m "feat: 在FeishuAdapter中初始化reaction_manager"
```

---

### Task 6: 添加状态管理_pending_reactions

**文件:**
- Modify: `src/bridges/feishu/adapter.py`
- Modify: `tests/bridges/feishu/test_adapter_reaction_integration.py`

**Step 1: 编写测试验证状态存储**

在测试文件中添加：

```python
class TestFeishuAdapterReactionIntegration:
    # ... 现有测试 ...

    def test_adapter_has_pending_reactions_state(self):
        """测试Adapter有pending_reactions状态管理"""
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        # 验证状态字典存在
        assert hasattr(adapter, '_pending_reactions')
        assert isinstance(adapter._pending_reactions, dict)

        # 验证可以存储和读取状态
        adapter._pending_reactions["session_123"] = {
            "user_message_id": "msg_456",
            "reaction_id": "reaction_789"
        }

        assert adapter._pending_reactions["session_123"]["user_message_id"] == "msg_456"
        assert adapter._pending_reactions["session_123"]["reaction_id"] == "reaction_789"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration::test_adapter_has_pending_reactions_state -v
```

Expected: FAIL - `_pending_reactions`不存在

**Step 3: 在__init__中添加状态管理**

在`src/bridges/feishu/adapter.py`的`__init__`方法中添加（在reaction_manager初始化之后）：

```python
# 状态管理 - 存储每个会话的表情信息
# 结构: {session_id: {"user_message_id": str, "reaction_id": str}}
self._pending_reactions: Dict[str, Dict[str, str]] = {}
```

确保文件顶部有：
```python
from typing import Dict
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration::test_adapter_has_pending_reactions_state -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/adapter.py tests/bridges/feishu/test_adapter_reaction_integration.py
git commit -m "feat: 添加_pending_reactions状态管理"
```

---

### Task 7: 实现_finalize_reaction辅助方法

**文件:**
- Modify: `src/bridges/feishu/adapter.py`
- Modify: `tests/bridges/feishu/test_adapter_reaction_integration.py`

**Step 1: 编写测试**

在测试文件中添加：

```python
import asyncio
from unittest.mock import AsyncMock

class TestFeishuAdapterReactionIntegration:
    # ... 现有测试 ...

    @pytest.mark.asyncio
    async def test_finalize_reaction_success(self):
        """测试成功完成表情处理"""
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        # 设置状态
        adapter._pending_reactions["session_123"] = {
            "user_message_id": "msg_456",
            "reaction_id": "reaction_789"
        }

        # Mock reaction_manager
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        # 执行
        await adapter._finalize_reaction("session_123")

        # 验证
        adapter.reaction_manager.replace_with_done.assert_called_once_with("msg_456", "reaction_789")
        assert "session_123" not in adapter._pending_reactions

    @pytest.mark.asyncio
    async def test_finalize_reaction_no_state(self):
        """测试没有对应状态时不应报错"""
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        # Mock reaction_manager
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        # 执行 - 不应抛出异常
        await adapter._finalize_reaction("nonexistent_session")

        # 验证没有调用replace_with_done
        adapter.reaction_manager.replace_with_done.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_reaction_exception_handling(self):
        """测试异常时仍然清理状态"""
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        # 设置状态
        adapter._pending_reactions["session_123"] = {
            "user_message_id": "msg_456",
            "reaction_id": "reaction_789"
        }

        # Mock抛出异常
        adapter.reaction_manager.replace_with_done = AsyncMock(side_effect=Exception("API error"))

        # 执行 - 不应抛出异常
        await adapter._finalize_reaction("session_123")

        # 验证状态仍然被清理
        assert "session_123" not in adapter._pending_reactions
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration::test_finalize_reaction_success -v
```

Expected: FAIL - 方法不存在

**Step 3: 实现_finalize_reaction方法**

在`src/bridges/feishu/adapter.py`的`FeishuAdapter`类中添加：

```python
async def _finalize_reaction(self, session_id: str) -> None:
    """
    完成会话时的表情处理：移除Typing，添加Done

    Args:
        session_id: 会话ID
    """
    reaction_info = self._pending_reactions.get(session_id)

    if not reaction_info:
        logger.warning(f"未找到会话 {session_id} 的表情信息")
        return

    try:
        user_message_id = reaction_info["user_message_id"]
        reaction_id = reaction_info["reaction_id"]

        # 替换表情：Typing -> Done
        success = await self.reaction_manager.replace_with_done(
            user_message_id,
            reaction_id
        )

        if success:
            logger.info(
                f"会话 {session_id} 表情替换成功",
                session_id=session_id
            )
        else:
            logger.warning(
                f"会话 {session_id} 表情替换失败",
                session_id=session_id
            )

    except Exception as e:
        logger.error(
            f"完成表情处理失败: {e}",
            exc_info=True,
            session_id=session_id
        )
    finally:
        # 清理状态
        self._pending_reactions.pop(session_id, None)
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration -k finalize -v
```

Expected: 所有finalize相关测试PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/adapter.py tests/bridges/feishu/test_adapter_reaction_integration.py
git commit -m "feat: 实现_finalize_reaction辅助方法"
```

---

### Task 8: 集成到handle_message_for_claude方法

**文件:**
- Modify: `src/bridges/feishu/adapter.py`

**Step 1: 定位handle_message_for_claude方法**

```bash
grep -n "async def handle_message_for_claude" src/bridges/feishu/adapter.py
```

记下行号，假设是1234行

**Step 2: 阅读方法了解当前结构**

```bash
sed -n '1234,1400p' src/bridges/feishu/adapter.py
```

**Step 3: 添加表情处理逻辑**

在`handle_message_for_claude`方法中找到以下位置并修改：

**位置1：方法开始处保存user_message_id**
```python
async def handle_message_for_claude(self, message: IMMessage) -> None:
    """将消息路由到Claude会话并处理响应"""

    session_id = message.session_id
    user_message_id = message.message_id  # 新增：保存用户消息ID
```

**位置2：在创建Claude会话之后、发送初始卡片之前**
```python
    # ... 现有的会话创建/获取逻辑 ...

    # ===== 新增：表情处理开始 =====
    # 步骤1: 添加"敲键盘"表情
    reaction_id = await self.reaction_manager.add_typing(user_message_id)

    # 步骤2: 存储状态
    if reaction_id:
        self._pending_reactions[session_id] = {
            "user_message_id": user_message_id,
            "reaction_id": reaction_id
        }
        logger.info(
            f"已添加敲键盘表情",
            session_id=session_id,
            user_message_id=user_message_id,
            reaction_id=reaction_id
        )
    else:
        logger.warning(
            f"添加敲键盘表情失败，继续处理消息",
            session_id=session_id,
            user_message_id=user_message_id
        )
    # ===== 表情处理结束 =====
```

**位置3：发送初始卡片时添加parent_id参数**
```python
    # 创建初始卡片（飞书只能更新卡片消息，不能更新文本消息）
    initial_card = self.card_builder.create_message_card("思考中...")
    logger.info(f"发送初始卡片: 思考中...")
    card_message_id = await self.send_message(
        session_id=session_id,
        content=initial_card,
        message_type=MessageType.CARD,  # 必须使用 CARD 类型才能更新
        receive_id_type="chat_id",
        parent_id=user_message_id  # 新增：引用用户消息
    )
```

**位置4：流式处理结束时调用finalize**
找到流式处理的结束位置（通常在流式循环之后），添加：

```python
    # 流式接收响应
    accumulated_content = ""
    event_count = 0

    logger.info(f"开始向 Claude 发送消息并接收响应...")
    try:
        async for event in self.claude_adapter.send_message(
            session_id=claude_session_id,
            message=message_content
        ):
            # ... 现有的事件处理逻辑 ...

    finally:
        # ===== 新增：确保完成表情处理 =====
        await self._finalize_reaction(session_id)
        # ===== 结束 =====
```

**Step 4: 运行所有测试确保没有破坏现有功能**

```bash
pytest tests/bridges/feishu/ -v
```

Expected: 所有测试PASS

**Step 5: 提交**

```bash
git add src/bridges/feishu/adapter.py
git commit -m "feat: 集成表情管理到handle_message_for_claude流程

- 在开始处理时添加Typing表情
- 发送思考卡片时引用用户消息(parent_id)
- 流式响应结束时替换为Done表情
- 确保异常时也能清理表情状态"
```

---

## Phase 3: 端到端测试

### Task 9: 编写完整的端到端集成测试

**文件:**
- Modify: `tests/bridges/feishu/test_adapter_reaction_integration.py`

**Step 1: 添加完整的消息流测试**

```python
class TestFeishuAdapterReactionIntegration:
    # ... 现有测试 ...

    @pytest.mark.asyncio
    async def test_full_message_flow_with_reactions(self):
        """测试完整的消息处理流程（包含表情）"""
        # 准备adapter
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        # 准备测试消息
        from src.bridges.feishu.message_handler import IMMessage, MessageType
        test_message = IMMessage(
            session_id="chat_test_123",
            message_id="user_msg_456",
            content="Hello",
            message_type=MessageType.TEXT,
            sender_id="user_789"
        )

        # Mock reaction_manager
        adapter.reaction_manager.add_typing = AsyncMock(return_value="reaction_abc")
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        # Mock send_message（用于发送卡片）
        adapter.send_message = AsyncMock(return_value="card_msg_id")

        # Mock claude_adapter和session_manager
        mock_claude_session = Mock()
        mock_claude_session.session_id = "claude_session_xyz"

        adapter.session_manager.get_or_create_session = AsyncMock(return_value=mock_claude_session)

        # Mock流式响应
        async def mock_send_message(*args, **kwargs):
            yield Mock(type="content_delta", delta="Hi")
            yield Mock(type="stop")

        adapter.claude_adapter.send_message = mock_send_message
        adapter.card_builder.create_message_card = Mock(return_value="{}")
        adapter.card_builder.create_text_card = Mock(return_value="{}")

        # 执行
        await adapter.handle_message_for_claude(test_message)

        # 验证完整流程
        # 1. 添加了Typing表情
        adapter.reaction_manager.add_typing.assert_called_once_with("user_msg_456")

        # 2. 状态被保存
        assert "chat_test_123" in adapter._pending_reactions
        assert adapter._pending_reactions["chat_test_123"]["user_message_id"] == "user_msg_456"
        assert adapter._pending_reactions["chat_test_123"]["reaction_id"] == "reaction_abc"

        # 3. 发送卡片时传入了parent_id
        adapter.send_message.assert_called()
        call_kwargs = adapter.send_message.call_args[1]
        assert call_kwargs.get("parent_id") == "user_msg_456"

        # 4. 表情被替换为Done
        adapter.reaction_manager.replace_with_done.assert_called_once_with("user_msg_456", "reaction_abc")

        # 5. 状态被清理
        assert "chat_test_123" not in adapter._pending_reactions
```

**Step 2: 运行测试**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py::TestFeishuAdapterReactionIntegration::test_full_message_flow_with_reactions -v
```

Expected: PASS

**Step 3: 提交**

```bash
git add tests/bridges/feishu/test_adapter_reaction_integration.py
git commit -m "test: 添加完整的端到端集成测试"
```

---

### Task 10: 添加边界情况和错误场景测试

**文件:**
- Modify: `tests/bridges/feishu/test_adapter_reaction_integration.py`

**Step 1: 添加边界测试**

```python
class TestFeishuAdapterReactionIntegration:
    # ... 现有测试 ...

    @pytest.mark.asyncio
    async def test_reaction_add_failure_does_not_break_flow(self):
        """测试表情添加失败不影响主流程"""
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        from src.bridges.feishu.message_handler import IMMessage, MessageType
        test_message = IMMessage(
            session_id="chat_test",
            message_id="user_msg",
            content="Hello",
            message_type=MessageType.TEXT,
            sender_id="user_789"
        )

        # Mock表情添加失败
        adapter.reaction_manager.add_typing = AsyncMock(return_value=None)
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)

        adapter.send_message = AsyncMock(return_value="card_msg_id")

        mock_claude_session = Mock()
        mock_claude_session.session_id = "claude_session"
        adapter.session_manager.get_or_create_session = AsyncMock(return_value=mock_claude_session)

        async def mock_send_message(*args, **kwargs):
            yield Mock(type="content_delta", delta="Hi")
            yield Mock(type="stop")

        adapter.claude_adapter.send_message = mock_send_message
        adapter.card_builder.create_message_card = Mock(return_value="{}")
        adapter.card_builder.create_text_card = Mock(return_value="{}")

        # 执行 - 不应抛出异常
        await adapter.handle_message_for_claude(test_message)

        # 验证
        # 1. 尝试添加表情
        adapter.reaction_manager.add_typing.assert_called_once()

        # 2. Claude仍被调用
        adapter.claude_adapter.send_message.assert_called_once()

        # 3. 没有尝试替换表情（因为没有reaction_id）
        adapter.reaction_manager.replace_with_done.assert_not_called()

        # 4. 没有保存状态
        assert "chat_test" not in adapter._pending_reactions

    @pytest.mark.asyncio
    async def test_exception_in_streaming_still_finalizes_reaction(self):
        """测试流式响应异常时仍然完成表情处理"""
        mock_http_client = Mock()
        mock_settings = Mock()
        mock_settings.feishu.app_id = "test_app"
        mock_settings.feishu.app_secret = "test_secret"
        mock_settings.feishu.bot_user_id = "bot_123"
        mock_settings.feishu.encrypt_key = "test_key"
        mock_settings.feishu.verify_token = "test_token"

        adapter = FeishuAdapter(
            http_client=mock_http_client,
            settings=mock_settings.feishu
        )

        from src.bridges/feishu/message_handler import IMMessage, MessageType
        test_message = IMMessage(
            session_id="chat_test",
            message_id="user_msg",
            content="Hello",
            message_type=MessageType.TEXT,
            sender_id="user_789"
        )

        adapter.reaction_manager.add_typing = AsyncMock(return_value="reaction_123")
        adapter.reaction_manager.replace_with_done = AsyncMock(return_value=True)
        adapter.send_message = AsyncMock(return_value="card_msg_id")

        mock_claude_session = Mock()
        mock_claude_session.session_id = "claude_session"
        adapter.session_manager.get_or_create_session = AsyncMock(return_value=mock_claude_session)

        # Mock流式响应抛出异常
        async def mock_send_message_error(*args, **kwargs):
            yield Mock(type="content_delta", delta="Hi")
            raise Exception("Claude API error")

        adapter.claude_adapter.send_message = mock_send_message_error
        adapter.card_builder.create_message_card = Mock(return_value="{}")
        adapter.card_builder.create_text_card = Mock(return_value="{}")

        # 执行 - 应该捕获异常并完成表情处理
        try:
            await adapter.handle_message_for_claude(test_message)
        except Exception:
            pass  # 预期会抛出异常

        # 验证表情仍被完成
        adapter.reaction_manager.replace_with_done.assert_called_once()
        assert "chat_test" not in adapter._pending_reactions
```

**Step 2: 运行所有测试**

```bash
pytest tests/bridges/feishu/test_adapter_reaction_integration.py -v
```

Expected: 所有测试PASS

**Step 3: 提交**

```bash
git add tests/bridges/feishu/test_adapter_reaction_integration.py
git commit -m "test: 添加边界情况和错误场景测试"
```

---

## Phase 4: 文档和收尾

### Task 11: 更新文档

**文件:**
- Modify: `docs/feishu_message_handling.md`

**Step 1: 阅读现有文档**

```bash
cat docs/feishu_message_handling.md
```

**Step 2: 在文档中添加表情反应说明**

找到合适的位置，添加以下内容：

```markdown
## 表情反应

当AI处理用户消息时，系统会自动添加表情反应以提供状态反馈：

1. **敲键盘表情** (Typing): AI开始处理消息时自动添加
2. **完成表情** (DONE): AI完成所有响应后替换

### 消息引用

AI回复的"思考中..."卡片会引用用户消息（通过`parent_id`），便于在飞书中追踪完整的消息链。

### 容错处理

表情操作失败不会影响AI的主流程。如果无法添加表情，系统会记录日志并继续处理消息。
```

**Step 3: 运行文档检查**

如果有文档检查工具，运行检查。如果没有，跳过此步。

**Step 4: 提交**

```bash
git add docs/feishu_message_handling.md
git commit -m "docs: 更新文档说明表情反应功能"
```

---

### Task 12: 运行完整测试套件

**Step 1: 运行所有测试**

```bash
pytest tests/ -v --tb=short
```

Expected: 所有测试通过

**Step 2: 检查代码覆盖率**

```bash
pytest tests/bridges/feishu/ --cov=src/bridges/feishu --cov-report=term-missing
```

Expected: 覆盖率报告显示新代码有良好覆盖

**Step 3: 代码格式检查**

如果有格式化工具（如black、ruff），运行检查：

```bash
ruff check src/bridges/feishu/reaction_manager.py
ruff check src/bridges/feishu/adapter.py
```

Expected: 无格式错误

**Step 4: 提交任何修复**

如果有需要修复的问题，修复后提交：

```bash
git add src/ tests/
git commit -m "fix: 修复测试和代码检查发现的问题"
```

---

### Task 13: 创建手动测试清单

**文件:**
- Create: `docs/manual-testing-checklist.md`

**Step 1: 创建手动测试清单**

```markdown
# 手动测试清单 - 飞书表情反应功能

## 测试前准备

- [ ] 确保飞书应用已开启表情权限
- [ ] 确保机器人已添加到测试群组
- [ ] 确保配置正确（app_id, app_secret等）

## 基础功能测试

- [ ] 发送消息后，用户消息上出现"敲键盘"表情
- [ ] AI回复的"思考中..."卡片正确引用了用户消息
  - 在飞书中可以看到回复的引用关系
  - 点击引用可以跳转到原始用户消息
- [ ] AI回复完成后，"敲键盘"表情消失
- [ ] AI回复完成后，用户消息上出现"完成"表情

## 多消息场景

- [ ] 快速连续发送3条消息
  - 每条消息都正确添加了"敲键盘"表情
  - 每条消息都正确引用了对应的用户消息
  - 所有消息都正确显示"完成"表情

## 错误场景测试

- [ ] 机器人不在群组中
  - 表情添加失败不影响AI回复
  - 查看日志确认有相关错误记录
- [ ] 用户消息被撤回
  - 表情操作优雅降级
  - AI仍能正常回复
- [ ] 网络不稳定
  - 表情操作失败时AI仍能完成回复
  - 日志中有详细的错误信息

## 性能测试

- [ ] 发送长消息（1000+字符）
  - 表情添加正常
  - 引用关系正确
- [ ] AI响应时间较长（30秒+）
  - "敲键盘"表情在整个响应期间保持
  - 响应完成后正确替换为"完成"

## 日志验证

- [ ] 检查日志确认以下信息都被记录：
  - 表情添加成功
  - 表情替换成功
  - 任何表情操作失败的错误

## 回归测试

- [ ] 确认现有的功能未受影响：
  - /help 命令正常工作
  - /sessions 命令正常工作
  - /new 命令正常工作
  - 普通对话正常工作

## 发现的问题

记录测试中发现的问题：

1.
2.
3.
```

**Step 2: 提交**

```bash
git add docs/manual-testing-checklist.md
git commit -m "docs: 添加手动测试清单"
```

---

### Task 14: 最终检查和推送

**Step 1: 检查git状态**

```bash
git status
```

Expected: 没有未提交的更改（除了测试产生的临时文件）

**Step 2: 查看提交历史**

```bash
git log --oneline -10
```

Expected: 看到所有相关提交，提交信息清晰

**Step 3: 创建feature分支（如果需要）**

如果项目使用feature分支：

```bash
git checkout -b feat/feishu-message-reaction
git push -u origin feat/feishu-message-reaction
```

**Step 4: 创建Pull Request（如果需要）**

如果项目使用PR流程：

```bash
gh pr create --title "feat: 添加飞书消息表情反应功能" --body "实现了以下功能：
- 创建FeishuReactionManager服务类管理表情操作
- 在消息处理时自动添加Typing表情
- AI回复卡片引用用户消息
- 完成时替换为Done表情
- 完善的错误处理和测试

详见设计文档: docs/plans/2026-03-12-feishu-message-reaction-enhancement-design.md"
```

**Step 5: 标记计划完成**

在实施计划文档顶部添加完成标记：

```markdown
# 飞书消息表情反应增强实施计划

> **状态:** ✅ 已完成
> **完成日期:** 2026-03-12
>
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
```

**Step 6: 最终提交**

```bash
git add docs/plans/2026-03-12-feishu-message-reaction-enhancement.md
git commit -m "docs: 标记实施计划为已完成"
```

---

## 总结

这个实施计划通过TDD方法，分阶段实现了飞书消息表情反应功能：

1. **Phase 1**: 创建FeishuReactionManager类并完成单元测试
2. **Phase 2**: 集成到FeishuAdapter并添加状态管理
3. **Phase 3**: 编写端到端测试和边界测试
4. **Phase 4**: 完善文档和手动测试清单

每个任务都是独立的、可验证的，遵循了DRY、YAGNI、TDD和频繁提交的原则。
