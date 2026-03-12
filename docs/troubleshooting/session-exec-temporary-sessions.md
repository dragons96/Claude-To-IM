# /session:exec 临时会话实现（不污染活跃列表）

## 问题描述

之前的实现存在严重问题：
- 使用 `/session:exec` 访问非活跃会话时，会将会话恢复到 `self.claude_adapter.sessions` 中
- 这会**污染活跃会话列表**
- 非活跃会话不应该持久化在内存中

## 正确的设计

`/session:exec` 的核心原则：**临时使用，用完即销毁**

### 设计要求

1. ✅ **不污染活跃会话列表** - 临时会话不添加到 `self.claude_adapter.sessions`
2. ✅ **用完即销毁** - 执行完成后立即清理临时会话
3. ✅ **活跃会话保持流式响应** - 对于活跃会话，使用完整的流式响应
4. ✅ **不影响 `is_active` 状态** - 无论活跃还是非活跃，执行后不改变状态

## 实现方案

### 分支处理逻辑

```python
async def route_to_claude_with_session(message, claude_session_id):
    # 1. 查询数据库中的会话记录
    session_record = db_session.query(ClaudeSession).filter_by(
        session_id=claude_session_id
    ).first()

    # 2. 检查会话是否在主会话列表中（活跃会话）
    if session_record.session_id in self.claude_adapter.sessions:
        # 活跃会话：使用标准流程（流式响应）
        await self._stream_claude_response(
            session_id=message.session_id,
            claude_session_id=session_record.session_id,
            message_content=message.content,
            user_message_id=message.message_id,
        )
        return

    # 3. 非活跃会话：临时创建并使用
    temp_client = None
    try:
        # 临时创建会话
        temp_client = ClaudeSDKClient(session_options)
        await temp_client.__aenter__()

        # 发送消息并获取响应（简化版，不流式更新）
        await temp_client.query(message_content, session_id)

        response_text = ""
        async for sdk_message in temp_client.receive_messages():
            # 解析响应...
            response_text += text_content

        # 发送完整响应
        await self.send_message(
            session_id=message.session_id,
            content=response_text,
            message_type=MessageType.TEXT,
        )

    finally:
        # 4. 清理临时会话
        if temp_client:
            await temp_client.__aexit__(None, None, None)
```

## 关键特性

### 1. 双路径处理

| 会话状态 | 处理方式 | 响应类型 |
|---------|---------|---------|
| **活跃会话** | 使用 `_stream_claude_response` | 流式响应（实时更新） |
| **非活跃会话** | 临时创建 client | 完整响应（一次性返回） |

### 2. 内存管理

**活跃会话**:
```python
# 存储在 self.claude_adapter.sessions 中
self.claude_adapter.sessions = {
    "session-id": {
        "session": ClaudeSession(...),
        "client": SDKClient
    }
}
```

**非活跃会话**（临时）:
```python
# 不存储在 self.claude_adapter.sessions 中
# 使用局部变量 temp_client
# finally 块中清理
```

### 3. 清理保证

```python
try:
    # 使用临时会话
    ...
finally:
    # 无论如何都会清理
    if temp_client:
        await temp_client.__aexit__(None, None, None)
```

## 优势

### 1. 不污染活跃会话列表

```
# 执行前
self.claude_adapter.sessions = {
    "active-session-1": {...},
    "active-session-2": {...}
}

# 执行 /session:exec inactive-session
# 临时创建，使用后销毁

# 执行后
self.claude_adapter.sessions = {
    "active-session-1": {...},
    "active-session-2": {...}
}
# ✅ 没有变化，inactive-session 不在其中
```

### 2. 自动资源管理

- 临时会话用完即销毁
- 不占用内存
- 不需要手动管理

### 3. 向后兼容

- 活跃会话保持原有的流式响应体验
- 不改变现有的会话管理逻辑

## 测试验证

```bash
pytest tests/test_session_exec_temporary.py -v
```

### 测试用例

1. ✅ `test_session_exec_temporary_session_not_pollute_active_list` - 临时会话不污染活跃列表
2. ✅ `test_session_exec_active_session_uses_standard_flow` - 活跃会话使用标准流程
3. ✅ `test_session_exec_cleanup_on_error` - 即使出错也清理临时会话

## 使用示例

### 场景：同时管理多个项目

```
# 会话列表（project-a 活跃）
/sessions
✨ 1. project-a (active)
   2. project-b (inactive)
   3. project-c (inactive)

# 在 project-b 执行测试（非活跃，临时创建）
/session:exec project-b 运行测试
[临时创建 client → 发送消息 → 接收响应 → 清理 client]
✅ 测试结果：通过

# 在 project-c 执行部署（非活跃，临时创建）
/session:exec project-c 部署
[临时创建 client → 发送消息 → 接收响应 → 清理 client]
✅ 部署成功

# 验证活跃会话列表没有被污染
/sessions
✨ 1. project-a (active) ← 仍然是活跃
   2. project-b (inactive)
   3. project-c (inactive)
```

## 错误处理

### 临时会话创建失败

```python
try:
    temp_client = ClaudeSDKClient(session_options)
    await temp_client.__aenter__()
except Exception as e:
    # 发送错误消息给用户
    await self.send_message(
        content=f"❌ 无法创建临时会话: {e}"
    )
```

### 临时会话执行失败

```python
try:
    # 执行逻辑
    ...
except Exception as e:
    # finally 块确保清理
    ...
    # 发送错误消息
    await self.send_message(
        content=f"❌ 执行失败: {e}"
    )
```

## 性能考虑

### 活跃会话（流式响应）
- 响应速度快
- 实时更新卡片
- 用户体验好

### 非活跃会话（完整响应）
- 首次创建 client 有开销（约 100-200ms）
- 一次性返回完整响应
- 不支持流式更新

### 优化建议

如果需要频繁访问某个非活跃会话：
1. 使用 `/switch` 将其切换为活跃会话
2. 享受流式响应和更好的用户体验

## 对比其他方案

### 方案1：恢复并持久化（之前的实现）

```python
# ❌ 错误的做法
if session_id not in self.sessions:
    # 恢复会话
    restored_session = await self.claude_adapter.create_session(...)
    # 问题：会话被添加到 self.sessions 中，不会被清理
```

**问题**：
- 污染活跃会话列表
- 内存泄漏（非活跃会话永久占用内存）
- 不符合 `/session:exec` 的设计初衷

### 方案2：临时创建并销毁（当前实现）

```python
# ✅ 正确的做法
temp_client = None
try:
    # 临时创建
    temp_client = ClaudeSDKClient(...)
    await temp_client.__aenter__()
    # 使用
    ...
finally:
    # 清理
    if temp_client:
        await temp_client.__aexit__(...)
```

**优势**：
- 不污染活跃会话列表
- 自动资源管理
- 符合 `/session:exec` 的设计初衷

## 相关文档

- `docs/session-exec-behavior.md` - /session:exec 行为说明
- `docs/troubleshooting/session-exec-auto-resume.md` - 之前的自动恢复方案（已废弃）
- `tests/test_session_exec_temporary.py` - 临时会话测试

## 更新历史

- **2026-03-12** - 初始实现（自动恢复并持久化）❌
- **2026-03-12** - 重新设计（临时创建，用完即销毁）✅

## 注意事项

1. **非活跃会话不支持流式响应** - 这是设计决策，避免复杂度
2. **临时会话每次都重新创建** - 如果需要频繁访问，建议使用 `/switch`
3. **错误会自动清理** - finally 块确保资源释放
