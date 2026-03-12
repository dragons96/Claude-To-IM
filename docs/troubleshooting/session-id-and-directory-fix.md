# 会话ID和目录命名修复

## 问题描述

### 问题1: 会话ID显示不一致

创建会话时显示的会话ID与会话列表中显示的ID不一致。

**原因**:
- 创建时显示的是 SDK 的 `session_id`
- 列表显示的是数据库的 `id` 字段

### 问题2: 目录命名使用平台会话ID

创建新会话时，工作目录使用的是平台会话ID（如飞书会话ID），而不是Claude会话ID。

**影响**:
- 同一个飞书会话下的多个Claude会话会共享同一个工作目录
- 不同用户在同一个飞书群聊中创建的会话会互相干扰

### 问题3: 命令参数不一致

`/sessions` 显示的ID无法直接用于 `/switch` 和 `/delete` 命令。

**原因**:
- `/sessions` 显示数据库 `id`
- `/switch` 和 `/delete` 也使用数据库 `id` 查找
- 但用户期望使用显示的ID来操作

## 解决方案

### 1. 统一显示SDK会话ID

修改 `/sessions` 命令，显示 SDK 的 `session_id` 而不是数据库 `id`：

```python
# src/bridges/feishu/command_handler.py 第192行
session_id = session.get("session_id", "unknown")  # 改为显示SDK会话ID
```

### 2. 使用Claude会话ID作为目录名

修改会话创建逻辑，使用 Claude SDK 的 `session_id` 作为目录名：

```python
# src/services/session_manager.py
# 生成 Claude 会话 ID
claude_session_id = str(uuid.uuid4())

# 如果没有指定工作目录，使用 Claude 会话ID作为目录名
if not work_directory:
    work_directory = str(self.default_session_root / claude_session_id)

# 创建 Claude SDK 会话时传入 session_id
claude_session = await self.claude_adapter.create_session(
    work_directory=work_directory,
    session_id=claude_session_id
)
```

### 3. 统一使用SDK会话ID查找

修改 `switch_session` 和 `delete_session` 方法，使用 SDK `session_id` 查找会话：

```python
# 使用 SDK session_id 查找
target_session = await self.storage.get_claude_session_by_sdk_id(claude_session_id)

# 设置活跃状态时使用数据库 id
await self.storage.set_claude_session_active(target_session.id, True)
```

### 4. 更新命令参数

所有命令 (`/switch`, `/delete`, `/session:exec`) 现在都接受并使用 SDK `session_id`。

## 修改文件

### 代码文件

1. **src/bridges/feishu/command_handler.py**
   - `_handle_sessions`: 显示 SDK `session_id`
   - `_handle_new`: 移除默认目录生成逻辑
   - `_handle_session_exec`: 使用 SDK `session_id` 查找

2. **src/services/session_manager.py**
   - `create_session`: 使用 Claude 会话ID作为目录名
   - `get_or_create_session`: 使用 Claude 会话ID作为目录名
   - `switch_session`: 使用 SDK `session_id` 查找
   - `delete_session`: 使用 SDK `session_id` 查找

### 测试文件

3. **tests/test_services/test_session_manager.py**
   - 添加缺失的 async mock 方法
   - 更新测试以使用 SDK `session_id`

4. **tests/test_new_commands.py**
   - 更新 `test_session_exec_success` 以使用 SDK `session_id`

## 验证

运行测试：

```bash
# 测试会话管理
python -m pytest tests/test_services/test_session_manager.py -v

# 测试命令处理
python -m pytest tests/test_new_commands.py::test_session_exec_success -v

# 测试所有会话相关功能（排除集成测试）
python -m pytest tests/ -v -k "session" --ignore=tests/integration
```

## 迁移说明

### 对现有用户的影响

1. **目录结构变化**
   - 旧目录：`sessions/oc_xxx/`（使用平台会话ID）
   - 新目录：`sessions/{claude-session-id}/`（使用Claude会话ID）
   - 现有会话不受影响，只有新创建的会话使用新结构

2. **命令使用**
   - `/sessions`: 现在显示 SDK session_id
   - `/switch <session_id>`: 使用显示的 SDK session_id
   - `/delete <session_id>`: 使用显示的 SDK session_id
   - `/session:exec <session_id> <content>`: 使用 SDK session_id

### 数据库兼容性

- 数据库 schema 无需变更
- 现有数据完全兼容
- `id` 字段仍用于内部关联
- `session_id` 字段用于用户操作

## 日期

2026-03-12 下午
