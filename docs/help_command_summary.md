# /help 命令响应说明

## 问题：/help 一直显示"思考中..."

可能的原因和解决方案：

### 原因分析

1. **SDK 返回了响应，但没有 TEXT_DELTA 事件**
   - 可能直接返回了完整内容
   - 需要在 END 事件时更新消息

2. **消息更新失败**
   - 飞书 API 调用失败
   - 卡片格式不正确

3. **响应内容为空**
   - /help 命令可能返回空内容
   - 或者返回了不可见字符

### 已修复

代码已在 END 事件中添加最终更新逻辑，确保无论什么情况都会显示响应。

## /help 命令的响应结构

### 示例 1: 分块响应（最常见）

```
事件 #1: TEXT_DELTA (55 字符)
  内容: "Cla Code v2.1.72  general   commands   custom-commands\n"

事件 #2: TEXT_DELTA (69 字符)
  内容: "\nClaude understands your codebase, makes edits with your permission,\n"

事件 #3: TEXT_DELTA (50 字符)
  内容: "and executes commands — right from your terminal.\n"

... (更多 TEXT_DELTA 事件)

事件 #10: END
  标志响应结束

总计: 10 个事件, 488 字符
```

### 示例 2: 单个大块（较少见）

```
事件 #1: TEXT_DELTA (488 字符)
  内容: "Cla Code v2.1.72 ..." (完整内容)

事件 #2: END
  标志响应结束

总计: 2 个事件, 488 字符
```

### 示例 3: 包含工具调用（极少见）

```
事件 #1: TEXT_DELTA
  内容: "Let me check the help..."

事件 #2: TOOL_USE
  工具: Bash
  输入: {"command": "claude --help"}

事件 #3: TOOL_RESULT
  内容: "帮助输出..."

事件 #4: TEXT_DELTA
  内容: "Here is what I found..."

事件 #5: END
```

## 当前处理逻辑

```
收到 TEXT_DELTA 事件
  ↓
累积到 accumulated_content
  ↓
立即调用 update_message(message_id, accumulated_content)
  ↓
飞书卡片实时刷新显示
  ↓
用户看到逐字显示的响应 ✅
```

## 验证方法

### 1. 查看日志

```bash
tail -f logs/app.log | grep -E "事件 #|TEXT_DELTA|END"
```

期望看到：
```
收到事件 #1: type=TEXT_DELTA, content长度=55
TEXT_DELTA: 累积内容长度: 55, 本次新增: 55
准备更新消息 msg_xxx...
消息更新结果: 成功

...

收到事件 #10: type=END, content长度=0
流式响应结束，共处理 10 个事件
最终响应长度: 488 字符
最终内容: Claude Code v2.1.72...
准备更新消息 msg_xxx...
最终消息更新结果: 成功
```

### 2. 运行示例脚本

```bash
cd D:\Codes\examples\claude-to-im
python examples/help_response_example.py
```

这个脚本会模拟 `/help` 命令的响应流程。

### 3. 测试实际调用

```bash
# 确保服务正在运行
python -m src.cli

# 然后在飞书中发送 /claude:help
```

## 完整的 /help 响应内容

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

## 关键要点

✅ **每个 TEXT_DELTA 都会更新消息** - 用户看到实时响应
✅ **END 事件会做最终更新** - 确保内容完整显示
✅ **支持长文本响应** - 无论是分块还是一次性返回
✅ **错误处理** - 如果出错会显示错误信息

## 如果还有问题

1. 检查日志文件 `logs/app.log`
2. 确认有活跃的 Claude 会话（使用 `/new` 创建）
3. 确认网络连接正常
4. 尝试其他命令（如 `/sessions`）看是否正常

## 相关文件

- 响应处理: `src/bridges/feishu/adapter.py` (第 729-831 行)
- 命令处理: `src/bridges/feishu/command_handler.py` (第 298-373 行)
- 示例代码: `examples/help_response_example.py`
- 详细文档: `docs/claude_help_response.md`
