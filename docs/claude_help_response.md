# Claude SDK /help 命令响应说明

本文档说明 `claude-agent-sdk` 调用 `/help` 命令时的响应结构和处理方式。

## 响应事件类型

Claude SDK 返回的是流式响应（Stream），包含以下事件类型：

### 1. TEXT_DELTA - 文本增量事件

**说明**: 包含响应文本的一部分

**示例**:
```python
StreamEvent(
    event_type=StreamEventType.TEXT_DELTA,
    content="Cla Code v2.1.72"
)
```

**特点**:
- 内容是分块返回的
- 多个 TEXT_DELTA 事件组合成完整响应
- 每次事件包含部分文本

### 2. TOOL_USE - 工具调用事件

**说明**: 当 Claude 需要调用工具时触发

**示例**:
```python
StreamEvent(
    event_type=StreamEventType.TOOL_USE,
    tool_name="Bash",
    tool_input={"command": "ls -la"}
)
```

### 3. TOOL_RESULT - 工具结果事件

**说明**: 工具调用完成后返回结果

**示例**:
```python
StreamEvent(
    event_type=StreamEventType.TOOL_RESULT,
    content="total 24"
)
```

### 4. ERROR - 错误事件

**说明**: 发生错误时触发

**示例**:
```python
StreamEvent(
    event_type=StreamEventType.ERROR,
    content="Failed to execute command"
)
```

### 5. END - 结束事件

**说明**: 响应结束

**示例**:
```python
StreamEvent(
    event_type=StreamEventType.END,
    content=""
)
```

## /help 命令的典型响应流程

```
发送 /help
  ↓
事件 #1: TEXT_DELTA
  content: "Cla Code v2.1.72"
  ↓
事件 #2: TEXT_DELTA
  content: "\ngeneral   commands"
  ↓
事件 #3: TEXT_DELTA
  content: "\n  Claude understands..."
  ↓
... (更多 TEXT_DELTA 事件)
  ↓
事件 #N: END
  标志响应结束
```

## /help 命令的可能响应内容

### 情况 1: 短响应（单个事件）

```python
# 只有一个 TEXT_DELTA 事件
[
  TEXT_DELTA("Cla Code v2.1.72 general commands custom-commands"),
  END
]
```

### 情况 2: 多个增量事件

```python
# 多个 TEXT_DELTA 事件
[
  TEXT_DELTA("Cla Code v2.1.72\n"),
  TEXT_DELTA("general   commands   custom-commands\n"),
  TEXT_DELTA("\nClaude understands..."),
  ...
  END
]
```

### 情况 3: 带工具调用的响应

```python
# 如果 /help 触发了工具调用
[
  TEXT_DELTA("Let me check..."),
  TOOL_USE("Bash", {"command": "claude --help"}),
  TOOL_RESULT("..."),
  TEXT_DELTA("Here is the help..."),
  END
]
```

## 当前处理逻辑

### 流式处理流程

```python
async def _stream_claude_response(...):
    accumulated_content = ""
    event_count = 0

    async for event in claude_adapter.send_message(...):
        event_count += 1

        if event.event_type == StreamEventType.TEXT_DELTA:
            # 累积文本
            accumulated_content += event.content

            # 立即更新消息（实时显示）
            await update_message(message_id, accumulated_content)

        elif event.event_type == StreamEventType.TOOL_USE:
            # 处理工具调用
            ...

        elif event.event_type == StreamEventType.END:
            # 响应结束
            # 如果有内容，最终更新一次
            if accumulated_content:
                await update_message(message_id, accumulated_content)
            break
```

### 关键点

1. **实时更新**: 每个 TEXT_DELTA 都会立即更新消息
2. **累积内容**: 所有 TEXT_DELTA 的内容会累积
3. **END 事件**: 标志响应结束，做最终更新

## /help 一直显示"思考中..."的可能原因

### 原因 1: 没有收到 TEXT_DELTA 事件

**情况**: `/help` 可能只返回了 END 事件，没有 TEXT_DELTA

**修复**: 代码已在 END 事件中添加最终更新

### 原因 2: 消息更新失败

**情况**: `update_message` API 调用失败

**检查**: 查看日志中的 "消息更新结果"

### 原因 3: SDK 没有返回内容

**情况**: `/help` 命令可能不返回文本（只返回状态）

**解决方案**: 需要特殊处理无内容的情况

## 测试方法

### 方法 1: 运行测试脚本

```bash
python test_help_response.py
```

### 方法 2: 查看日志

启动服务后，发送 `/claude:help`，查看日志：

```
收到事件 #1: type=TEXT_DELTA, content长度=100
TEXT_DELTA: 累积内容长度: 100, 本次新增: 100
准备更新消息 xxx...
消息更新结果: 成功

收到事件 #2: type=END, content长度=0
流式响应结束，共处理 2 个事件
最终响应长度: 100
```

### 方法 3: 本地测试

```bash
# 在 Claude Code 中执行
claude --help

# 或在交互模式中
/help
```

## 预期的响应内容

### Claude Code CLI 的 /help 输出

```
Cla Code v2.1.72  general   commands   custom-commands

Claude understands your codebase, makes edits with your permission,
and executes commands — right from your terminal.

Shortcuts
! for bash mode           double tap esc to clear input
/ for commands            ctrl + o for verbose outputedits
& for background          \⏎ for newlineggle tasks
ctrl + shift + - to undo    meta + p to switch model
ctrl + g to edit in $EDITOR

For more help: https://code.claude.com/docs/en/overview
```

### 通过 SDK 的响应

相同的内容，但可能分成多个 TEXT_DELTA 事件返回。

## 建议

### 1. 检查日志

查看详细的日志输出，确认收到了哪些事件：

```bash
tail -f logs/app.log | grep "事件 #"
```

### 2. 添加调试信息

如果问题持续，可以添加更多日志：

```python
logger.info(f"事件详情: type={event.event_type}, "
           f"content={repr(event.content[:100]) if event.content else 'None'}")
```

### 3. 测试其他命令

尝试其他命令看看是否有同样问题：

- `/new` - 创建会话
- `/sessions` - 查看会话列表
- `/claude:commit` - 提交命令

## 总结

- `/help` 命令会返回流式响应
- 响应由多个事件组成（TEXT_DELTA + END）
- 代码已经处理了所有事件类型
- 如果一直显示"思考中..."，检查日志中的事件记录
