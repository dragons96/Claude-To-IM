# 会话 Resume 参数修复

**日期**: 2026-03-12
**影响**: `/session:exec` 和 `/switch` 命令

## 问题描述

### 问题 1：`/session:exec` 命令无法恢复会话历史

**现象**：
- 使用 `/session:exec [会话ID] xxx` 向非活跃会话发送消息
- Claude 无法记住之前的对话内容
- 问"我们刚刚聊了什么"时，描述的内容不对

**原因**：
在 `src/bridges/feishu/adapter.py` 的 `route_to_claude_with_session()` 方法中，当处理非活跃会话时，创建了临时会话但**没有传递 `resume_session_id` 参数**，导致创建了一个新的空会话，无法恢复之前的对话历史。

```python
# 修复前的代码（第1417行）
logger.info(f"  是否设置 resume: False (临时会话不使用 resume)")
temp_client = ClaudeSDKClient(session_options)  # ❌ 没有 resume
```

### 问题 2：`/switch` 命令切换后无法恢复会话历史

**现象**：
- 使用 `/switch [会话ID]` 切换到非活跃会话
- 切换成功，但问"我们刚刚聊了什么"时，描述的内容不对
- 会话虽然在数据库中标记为活跃，但不在内存中

**原因**：
在 `src/services/session_manager.py` 的 `switch_session_by_db_id()` 方法中，只是将数据库中的会话标记为活跃，但**没有实际恢复会话到内存中**。

```python
# 修复前的代码（第359行）
await self.storage.set_claude_session_active(target_session.id, True)
logger.info(f"已将会话 {target_session.session_id} 设置为活跃")
# ❌ 没有检查或恢复会话到内存
```

## 解决方案

### 修复 1：`route_to_claude_with_session()` - 添加 resume 参数

**文件**: `src/bridges/feishu/adapter.py`
**位置**: 第1398-1419行

**修改内容**：
```python
# 修复后的代码
# 创建独立的 options，设置工作目录
session_options = copy.copy(self.claude_adapter.options)
session_options.cwd = session_record.work_directory

# ✅ 设置 resume 参数以恢复会话历史
session_options.resume = session_record.session_id

logger.info(f"🔧 临时会话创建参数:")
logger.info(f"  数据库 session_id: {session_record.session_id}")
logger.info(f"  work_directory: {session_record.work_directory}")
logger.info(f"  session_options.cwd: {session_options.cwd}")
logger.info(f"  ✅ 已设置 session_options.resume: {session_options.resume}")

temp_client = ClaudeSDKClient(session_options)
```

**效果**：
- 临时会话创建时会恢复目标会话的历史记录
- Claude 可以访问之前的对话内容

### 修复 2：`switch_session_by_db_id()` - 检查并恢复会话到内存

**文件**: `src/services/session_manager.py`
**位置**: 第314-370行

**修改内容**：
```python
# 检查会话是否已在内存中
logger.info(f"检查会话 {target_session.session_id} 是否在内存中...")
existing_session = await self.claude_adapter.get_session_info(
    target_session.session_id
)

if existing_session:
    # 会话已在内存中，检查是否是同一个会话
    logger.info(f"✅ 会话 {target_session.session_id} 已在内存中")
    if existing_session.session_id == target_session.session_id:
        logger.info(f"✅ 内存中的会话ID与目标会话ID一致，无需恢复")
    else:
        logger.warning(f"⚠️  内存中的会话ID ({existing_session.session_id}) 与目标会话ID ({target_session.session_id}) 不一致，需要恢复")
        # 关闭旧会话
        await self.claude_adapter.close_session(existing_session.session_id)
        # 恢复目标会话
        restored_session = await self.claude_adapter.create_session(
            work_directory=target_session.work_directory,
            session_id=target_session.session_id,
            resume_session_id=target_session.session_id  # ✅ 使用 resume
        )
else:
    # 会话不在内存中，需要恢复
    logger.info(f"会话 {target_session.session_id} 不在内存中，开始恢复...")
    # 使用 resume 参数恢复会话
    restored_session = await self.claude_adapter.create_session(
        work_directory=target_session.work_directory,
        session_id=target_session.session_id,
        resume_session_id=target_session.session_id  # ✅ 使用 resume
    )
```

**效果**：
- 切换会话时会检查会话是否在内存中
- 如果不在内存中，会使用 `resume_session_id` 参数恢复会话
- 如果内存中的会话ID与目标会话ID不同，会先关闭旧会话，再恢复目标会话
- Claude 可以访问之前的对话内容

## 测试建议

### 测试场景 1：`/session:exec` 恢复会话历史

1. 创建新会话并发送一些消息
2. 创建第二个会话并设为活跃
3. 使用 `/session:exec [第一个会话ID] 我们刚刚聊了什么`
4. 验证 Claude 能正确描述之前的对话内容

### 测试场景 2：`/switch` 恢复会话历史

1. 创建新会话并发送一些消息
2. 创建第二个会话并设为活跃
3. 使用 `/switch [第一个会话ID]`
4. 发送消息"我们刚刚聊了什么"
5. 验证 Claude 能正确描述之前的对话内容

### 测试场景 3：多个会话切换

1. 创建三个会话，每个会话都发送不同的内容
2. 在三个会话之间切换
3. 验证每个会话都能正确恢复其历史记录

## 相关文件

- `src/bridges/feishu/adapter.py` - 飞书桥接适配器
- `src/services/session_manager.py` - 会话管理器
- `src/claude/sdk_adapter.py` - Claude SDK 适配器（包含 resume 参数实现）

## 技术细节

### resume 参数的作用

Claude Agent SDK 的 `resume` 参数用于恢复之前的会话上下文：

```python
# sdk_adapter.py 中的实现
if resume_session_id is not None:
    session_options.resume = resume_session_id
    logger.info(f"  ✅ 已设置 session_options.resume: {session_options.resume}")
```

当设置 `session_options.resume` 时，SDK 会：
1. 查找指定 session_id 的历史记录
2. 加载之前的对话上下文
3. 恢复会话的状态（包括工具调用、文件访问等）

### 会话ID的一致性

系统中有两种会话ID：
- **数据库 id**：用户可见的会话ID（自增主键），用于用户操作
- **SDK session_id**：内部使用的会话ID（UUID），与 Claude SDK 交互

恢复会话时使用 **SDK session_id**：
```python
resume_session_id=target_session.session_id  # 使用 SDK session_id
```

## 参考文档

- `docs/troubleshooting/session-id-consistency-fix.md` - 会话ID一致性修复
- `docs/troubleshooting/session-exec-is-active-fix.md` - is_active参数错误修复
- `docs/session-management-final.md` - 会话管理最终方案
