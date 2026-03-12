# 会话ID一致性修复

## 问题描述

用户反馈创建会话时显示的会话ID与 `/sessions` 列表中显示的会话ID不一致，导致在使用 `/switch`、`/delete`、`/session:exec` 等命令时产生困惑。

### 具体表现

1. **创建会话 (`/new`)**: 显示 SDK 生成的临时 `session_id`
2. **列表查看 (`/sessions`)**: 显示数据库中的 `session_id`（发送消息后可能已更新为真实ID）
3. **不一致的ID**: 用户不知道该使用哪个ID来操作会话

### 示例

```
# 创建会话
/new
✅ 成功创建新会话
📋 会话信息:
• 会话ID: 1d3cb3f9-3e55-4c24-b36c-50c33c23a21f  # SDK临时ID

# 查看会话列表
/sessions
📋 会话列表:
✨ 1. af8e12b0-89d1-488f-b92a-d3d84c44c051  # 数据库中的真实ID
```

## 根本原因

系统中有三种不同的ID：

1. **数据库 `id`**: 数据库记录的主键，UUID格式，稳定不变
2. **SDK `session_id`**: Claude SDK返回的会话ID，创建时是临时UUID，发送第一条消息后更新为真实ID
3. **目录名**: 工作目录的名称，使用UUID格式

之前的代码混合使用这些ID，导致显示不一致。

## 解决方案

**统一使用数据库 `id` 字段作为用户可见的会话ID**

### 设计原则

1. **用户可见ID**: 使用数据库 `id` 字段（稳定不变）
2. **内部交互**: 继续使用 SDK `session_id` 与 Claude SDK 交互
3. **清晰分离**: 用户看到的ID和内部使用的ID分开管理

### 实现细节

#### 1. 修改显示逻辑

**创建会话 (`_handle_new`)**:
```python
# 获取数据库记录，使用数据库 id 作为用户可见的会话ID
db_session = await self.session_manager.storage.get_claude_session_by_sdk_id(
    claude_session.session_id
)
display_session_id = db_session.id if db_session else claude_session.session_id
```

**列表显示 (`_handle_sessions`)**:
```python
# 使用数据库 id 作为用户可见的会话ID
session_id = session.get("id", "unknown")
```

#### 2. 新增数据库ID查询方法

**SessionManager**:
- `switch_session_by_db_id()`: 使用数据库ID切换会话
- `delete_session_by_db_id()`: 使用数据库ID删除会话

**命令处理器**:
- `/switch`: 现在使用数据库ID查询
- `/delete`: 现在使用数据库ID查询
- `/session:exec`: 现在使用数据库ID查询

#### 3. 内部映射

虽然用户使用数据库ID，但内部仍然使用SDK `session_id` 与 Claude SDK 交互：

```python
return {
    "type": "exec_in_session",
    "claude_session_id": target_session.session_id,  # SDK session_id（内部使用）
    "db_session_id": target_session.id,  # 数据库id（用户可见）
    "message": exec_message
}
```

## 修改文件

1. **src/bridges/feishu/command_handler.py**
   - 修改 `_handle_new`: 显示数据库ID
   - 修改 `_handle_sessions`: 显示数据库ID
   - 修改 `_handle_switch`: 使用 `switch_session_by_db_id`
   - 修改 `_handle_delete`: 使用 `delete_session_by_db_id`
   - 修改 `_handle_session_exec`: 使用数据库ID查询
   - 更新帮助文档中的示例

2. **src/services/session_manager.py**
   - 新增 `switch_session_by_db_id()` 方法
   - 新增 `delete_session_by_db_id()` 方法

3. **tests/test_new_commands.py**
   - 更新测试以匹配新的实现

## 用户体验改进

### 之前

```
/new
会话ID: 1d3cb3f9-3e55-4c24-b36c-50c33c23a21f  # SDK临时ID

/sessions
1. af8e12b0-89d1-488f-b92a-d3d84c44c051  # 数据库ID（不一致！）

/switch 1d3cb3f9-3e55-4c24-b36c-50c33c23a21f  # 哪个ID？❓
```

### 现在

```
/new
会话ID: abc123-def456-7890  # 数据库ID（稳定）

/sessions
✨ 1. abc123-def456-7890  # 相同的数据库ID ✅

/switch abc123-def456-7890  # 清晰明确！
```

## 技术优势

1. **ID稳定性**: 数据库ID永远不会改变
2. **一致性**: 所有地方显示的都是同一个ID
3. **向后兼容**: 内部仍然使用SDK session_id，不影响现有功能
4. **清晰分离**: 用户接口和内部实现明确分离

## 测试验证

所有相关测试已通过：

```bash
pytest tests/test_new_commands.py -v
# 5 passed ✅

pytest tests/test_services/test_session_manager.py -v -k "switch or delete"
# 4 passed ✅
```

## 相关文档

- `docs/session-management-final.md` - 会话管理最终方案
- `docs/troubleshooting/session-id-and-directory-fix.md` - 之前的会话ID修复

## 更新日期

2026-03-12
