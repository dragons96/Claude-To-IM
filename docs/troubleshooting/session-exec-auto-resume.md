# /session:exec 自动恢复非活跃会话

## 问题描述

使用 `/session:exec` 命令访问非活跃会话时出现错误：

```
Session d68d36ce-0e71-4a0b-aa9f-e05a25bd8d7d not found
```

### 复现步骤

1. 创建会话A并使用
2. 创建会话B（会话A变为非活跃）
3. 程序重启
4. 尝试使用 `/session:exec` 访问会话A
5. 出现错误：`Session xxx not found`

### 错误信息对比

- **用户输入**: `/session:exec c77e153b-4c73-45c0-9333-b4c89acc24d6 今天星期几？`
- **错误显示**: `Session d68d36ce-0e71-4a0b-aa9f-e05a25bd8d7d not found`

两个ID不一致说明：
- `c77e153b...` 是数据库 `id`（用户可见）
- `d68d36ce...` 是 SDK `session_id`（内部使用）

## 根本原因

### 1. 会话恢复机制

程序启动时，`SessionManager.resume_active_sessions()` 只恢复**活跃会话**：

```python
# src/services/session_manager.py
active_sessions = db_session.query(ClaudeSession).filter_by(
    is_active=True  # 只恢复活跃会话
).all()
```

### 2. 非活跃会话的状态

- **数据库**: 存在记录（包含 `session_id`, `work_directory` 等）
- **SDK 内存**: 不存在（程序重启后未加载）
- **结果**: 无法通过 SDK 发送消息

### 3. 错误发生位置

`sdk_adapter.py:146-148`:

```python
if session_id not in self.sessions:
    logger.error(f"会话不存在: {session_id}")
    raise ValueError(f"Session {session_id} not found")
```

## 解决方案

在 `route_to_claude_with_session` 中添加自动恢复逻辑：

### 修复代码

```python
# src/bridges/feishu/adapter.py
async def route_to_claude_with_session(...):
    # ... 查询会话记录 ...

    # 检查会话是否在 SDK 内存中，如果不在则尝试恢复
    if session_record.session_id not in self.claude_adapter.sessions:
        logger.warning(f"会话 {session_record.session_id} 不在内存中，尝试恢复...")
        try:
            # 使用数据库中的 session_id 和 work_directory 恢复会话
            restored_session = await self.claude_adapter.create_session(
                work_directory=session_record.work_directory,
                session_id=session_record.session_id
            )
            logger.info(f"✅ 会话已恢复到内存: {restored_session.session_id}")
        except Exception as e:
            error_msg = f"无法恢复会话 {session_record.session_id}: {str(e)}"
            logger.error(error_msg)
            await self.send_message(
                session_id=message.session_id,
                content=f"❌ {error_msg}\n\n💡 提示：该会话可能已失效，请使用 /new 创建新会话",
                message_type=MessageType.TEXT,
                receive_id_type="chat_id",
            )
            return

    # ... 继续发送消息 ...
```

## 实现细节

### 1. 检测会话是否在内存

```python
if session_record.session_id not in self.claude_adapter.sessions:
    # 会话不在内存中，需要恢复
```

### 2. 恢复会话

```python
restored_session = await self.claude_adapter.create_session(
    work_directory=session_record.work_directory,
    session_id=session_record.session_id  # 使用相同的 session_id
)
```

### 3. 错误处理

如果恢复失败：
- 记录错误日志
- 向用户发送友好的错误消息
- 提示创建新会话

## 行为说明

### 修复前

```
1. 用户：/session:exec c77e153b... 今天星期几？
2. 系统：❌ Session d68d36ce... not found
3. 用户：😕 为什么会失败？
```

### 修复后

```
1. 用户：/session:exec c77e153b... 今天星期几？
2. 系统：⚠️ 会话 d68d36ce... 不在内存中，尝试恢复...
3. 系统：✅ 会话已恢复到内存
4. 系统：今天是星期三
```

## 适用场景

### ✅ 可以自动恢复

- 程序重启后的非活跃会话
- 尚未被加载到内存的会话
- 会话文件仍然存在于磁盘上

### ❌ 无法恢复

- 会话文件被删除
- 工作目录被移动或删除
- 会话数据损坏

## 测试验证

```bash
pytest tests/test_session_exec_resume.py -v
```

### 测试用例

1. ✅ `test_session_exec_auto_resume_inactive_session` - 自动恢复非活跃会话
2. ✅ `test_session_exec_resume_fails_gracefully` - 恢复失败时优雅处理
3. ✅ `test_session_exec_session_already_in_memory` - 会话已在内存中（不需要恢复）

## 优势

1. **用户体验提升** - 无需手动切换会话
2. **透明恢复** - 自动在后台恢复会话
3. **错误处理完善** - 恢复失败时给出友好提示
4. **向后兼容** - 不影响现有功能

## 注意事项

1. **性能考虑**: 首次访问非活跃会话会有额外恢复开销
2. **并发问题**: 同一会话被多次访问时，恢复逻辑是幂等的
3. **资源管理**: 恢复的会话会占用内存，直到程序关闭

## 相关文档

- `docs/session-exec-behavior.md` - /session:exec 行为说明
- `docs/troubleshooting/session-exec-is-active-fix.md` - is_active 参数修复
- `tests/test_session_exec_resume.py` - 自动恢复测试

## 更新日期

2026-03-12
