# /session:exec 命令行为说明

## 核心特性

✅ **支持对非活跃会话执行命令**
✅ **执行后不会改变活跃状态**

这是 `/session:exec` 命令的设计核心，与 `/switch` 命令有本质区别。

## 行为对比

### `/switch` 命令

```
/switch <会话ID>
```

**行为**:
- ✅ 修改活跃状态
- ✅ 将所有其他会话设为非活跃
- ✅ 将目标会话设为活跃
- ✅ 后续消息都发送到这个会话

**代码实现**:
```python
async def switch_session_by_db_id(...):
    # 1. 将所有其他会话设为非活跃
    await storage.set_all_claude_sessions_inactive(im_session.id)

    # 2. 将目标会话设为活跃
    await storage.set_claude_session_active(target_session.id, True)
```

**使用场景**: 永久切换工作会话

### `/session:exec` 命令

```
/session:exec <会话ID> <内容>
```

**行为**:
- ❌ **不修改活跃状态**
- ✅ 直接向指定会话发送消息
- ✅ 无论该会话是否活跃都可以执行
- ✅ 执行后当前活跃会话保持不变

**代码实现**:
```python
async def route_to_claude_with_session(message, claude_session_id):
    # 1. 查询会话记录（不检查 is_active）
    session_record = db_session.query(ClaudeSession).filter_by(
        session_id=claude_session_id
    ).first()

    # 2. 直接使用该会话发送消息
    await self._stream_claude_response(
        claude_session_id=session_record.session_id,
        message_content=message.content
    )

    # 3. 没有任何修改 session_record.is_active 的代码
```

**使用场景**: 临时在其他会话执行单个任务，不中断当前工作流

## 使用示例

### 场景：同时管理多个项目

假设你有三个项目会话：
- **项目A** (当前活跃) - `session-a-id`
- **项目B** (非活跃) - `session-b-id`
- **项目C** (非活跃) - `session-c-id`

#### 使用 `/switch` 的方式

```
# 当前在项目A工作
写代码

# 需要在项目B测试，切换会话
/switch session-b-id
运行测试

# 测试完成，需要切回项目A
/switch session-a-id
继续写代码

# 需要在项目C部署，再切换
/switch session-c-id
部署

# 再切回项目A
/switch session-a-id
继续工作
```

❌ 频繁切换，繁琐且容易忘记切回

#### 使用 `/session:exec` 的方式

```
# 在项目A工作（保持活跃）
写代码

# 在项目B测试（不切换活跃会话）
/session:exec session-b-id 运行测试

# 继续在项目A工作
写代码

# 在项目C部署（不切换活跃会话）
/session:exec session-c-id 部署

# 继续在项目A工作
写代码
```

✅ 从不切换活跃会话，工作流不被打断

## 实现细节

### 1. 不检查活跃状态

```python
# route_to_claude_with_session 中
session_record = db_session.query(ClaudeSession).filter_by(
    session_id=claude_session_id
).first()

# 没有这样的检查：
# if not session_record.is_active:
#     return error
```

### 2. 不修改活跃状态

```python
# route_to_claude_with_session 中
# 发送消息后，没有这样的代码：
# session_record.is_active = True
# db_session.commit()
```

### 3. 直接使用会话ID

```python
# 无论会话是否活跃，都直接使用
await self._stream_claude_response(
    claude_session_id=session_record.session_id,  # 直接使用
    message_content=message.content
)
```

## 测试验证

### 测试1：支持非活跃会话

```python
# 创建非活跃会话
inactive_session = Mock(
    session_id="inactive-id",
    is_active=False  # 非活跃
)

# 向非活跃会话发送消息
await adapter.route_to_claude_with_session(
    message,
    "inactive-id"
)

# ✅ 成功发送消息
# ✅ 会话仍然是非活跃状态
assert inactive_session.is_active == False
```

### 测试2：多个非活跃会话

```python
# 向三个不同的非活跃会话发送消息
for session in inactive_sessions:
    await adapter.route_to_claude_with_session(
        message,
        session.session_id
    )

# ✅ 所有消息都成功发送
# ✅ 所有会话仍然是非活跃状态
```

### 测试3：与 switch 的区别

```python
# /switch 会调用这些方法
await storage.set_all_claude_sessions_inactive(im_id)
await storage.set_claude_session_active(session_id, True)

# /session:exec 不会调用这些方法
# 它只是发送消息
```

## 常见问题

### Q: /session:exec 会修改活跃会话吗？
**A**: 不会。这是它和 `/switch` 的最大区别。

### Q: 可以向非活跃会话发送消息吗？
**A**: 可以。无论会话是否活跃都可以使用 `/session:exec`。

### Q: 执行 /session:exec 后，当前活跃会话会变化吗？
**A**: 不会。当前活跃会话保持不变。

### Q: 什么时候用 /switch，什么时候用 /session:exec？
**A**:
- **`/switch`**: 永久切换工作会话
- **`/session:exec`**: 临时在其他会话执行单个任务

### Q: 可以连续使用多个 /session:exec 吗？
**A**: 可以。你可以连续向多个不同的会话发送消息。

## 技术优势

1. **工作流不中断** - 在多个会话间切换时不会打断当前工作
2. **灵活性高** - 可以随时向任何会话发送消息
3. **状态清晰** - 活跃会话始终是你的"主工作区"
4. **多任务并行** - 可以同时监控多个会话的状态

## 相关文档

- `docs/new_commands_guide.md` - 新命令使用指南
- `docs/troubleshooting/session-exec-is-active-fix.md` - is_active 参数修复
- `tests/test_session_exec_inactive.py` - 非活跃会话测试

## 更新日期

2026-03-12
