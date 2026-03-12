# 会话创建改进 (2026-03-12 下午)

## 改进内容

### 1. 让 Claude SDK 自己生成会话ID

**之前的问题**:
- 手动使用 `uuid.uuid4()` 生成会话ID
- 然后传给 Claude SDK
- 这不符合 SDK 的设计初衷

**改进方案**:
- 不传入 `session_id` 参数，让 SDK 自己生成
- 先创建临时目录（`temp_{8位hex}`）
- SDK 返回 session_id 后，重命名目录为 `{session_id}`
- 这样确保目录名和实际的 session_id 一致

**代码示例**:
```python
# 创建临时目录
temp_session_id = f"temp_{uuid.uuid4().hex[:8]}"
temp_work_directory = self.default_session_root / temp_session_id
temp_work_directory.mkdir(parents=True, exist_ok=True)

# 让 SDK 自己生成 session_id
claude_session = await self.claude_adapter.create_session(
    work_directory=str(temp_work_directory)
)

# 重命名目录为实际的 session_id
actual_work_directory = self.default_session_root / claude_session.session_id
shutil.move(str(temp_work_directory), str(actual_work_directory))
```

### 2. 新会话自动自我介绍

**需求**: 创建新会话后，让 AI 自我介绍，让用户知道这个助手的功能

**实现**:
- `/new` 命令返回特殊类型 `new_session_created`
- 包含成功消息和自我介绍请求
- adapter 收到后先发送成功消息
- 然后自动发送"你好！请简单介绍一下你自己..."给 Claude

**代码示例**:
```python
return {
    "type": "new_session_created",
    "message": "✅ 成功创建新会话...",
    "intro_message": "你好！请简单介绍一下你自己..."
}
```

### 3. 会话恢复失败处理

**观察到的错误**:
```
Command failed with exit code 1 (exit code: 1)
```

**分析**:
- 会话恢复时 Claude CLI 返回错误
- 可能是会话数据损坏或不兼容
- 需要改进恢复逻辑或提供更好的错误处理

**当前状态**:
- 恢复失败时会创建新会话
- 旧会话被标记为非活跃
- 用户可以继续使用（但旧会话的上下文可能丢失）

## 文件修改

### 1. src/services/session_manager.py

**create_session 方法**:
- 移除手动 UUID 生成
- 使用临时目录 + 重命名策略
- 添加 `shutil` 导入用于目录重命名

**get_or_create_session 方法**:
- 同样的临时目录 + 重命名策略

### 2. src/bridges/feishu/command_handler.py

**_handle_new 方法**:
- 返回字典而不是字符串
- 类型: `new_session_created`
- 包含成功消息和自我介绍请求

### 3. src/bridges/feishu/adapter.py

**命令结果处理**:
- 添加 `uuid` 导入
- 添加 `new_session_created` 类型处理
- 先发送成功消息
- 再发送自我介绍请求给 Claude

## 使用示例

```bash
# 创建新会话
/new

# 系统响应：
# ✅ 成功创建新会话
# 📋 会话信息: ...
#
# （然后自动发送介绍请求）
# AI: 你好！我是 Claude Code...

# 查看会话列表（显示 SDK session_id）
/sessions

# 切换会话（使用显示的 session_id）
/switch abc123-def456-...
```

## 测试

```bash
# 测试会话管理
python -m pytest tests/test_services/test_session_manager.py -v

# 测试命令处理
python -m pytest tests/test_new_commands.py -v
```

## 已知问题

1. **会话恢复失败**: 某些会话无法恢复，会创建新会话
   - 需要进一步调查原因
   - 可能需要提供恢复失败时的更详细错误信息

2. **临时目录清理**: 如果重命名失败，临时目录可能会残留
   - 已有错误日志
   - 可以考虑添加清理逻辑

## 下一步改进

1. **会话恢复增强**:
   - 检测会话是否可恢复
   - 提供恢复失败的详细原因
   - 尝试修复损坏的会话

2. **自我介绍定制**:
   - 允许用户自定义介绍消息
   - 根据不同场景提供不同介绍

3. **错误处理改进**:
   - 更好的错误提示
   - 自动清理临时目录
   - 会话健康检查

## 日期

2026-03-12 下午
