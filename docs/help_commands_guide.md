# 帮助命令使用指南

本文档介绍 Claude Code Bot 的帮助命令功能,包括如何查看 MCP 工具信息和可用命令列表。

## 命令列表

### `/help` - 基础帮助

显示所有可用命令的简要说明。

**用法:**
```
/help
```

**示例输出:**
```
📖 Claude Code Bot 命令帮助
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 会话管理命令:
/new [路径]          - 创建新会话
/sessions            - 列出所有会话
/switch <会话ID>      - 切换到指定会话
/delete <会话ID>      - 删除指定会话
/session:exec <会话ID> <内容> - 在指定会话中执行命令

...
```

---

### `/help:mcp` - MCP 工具详情

查看已加载的 MCP (Model Context Protocol) 工具信息,包括服务器状态、工具列表和详细描述。

**用法:**
```
/help:mcp
```

**功能:**
- ✅ 显示所有 MCP 服务器的连接状态
- 📦 列出每个服务器提供的工具
- 📝 显示工具的详细描述
- ❌ 显示失败服务器的错误信息

**示例输出:**
```
🔌 MCP 工具详情
==================================================

📦 已加载 2 个 MCP 服务器:

✅ **pencil**
   类型: stdio
   作用域: user
   版本: Pencil v1.0.0
   工具: 5 个
     • /batch_get
       Retrieve nodes by searching for matching patterns
     • /batch_design
       Use it when designing with .pen files
     • /get_editor_state
       Start with this tool if you are aware of the current editor state

✅ **playwright**
   类型: stdio
   作用域: user
   版本: Playwright v1.0.0
   工具: 8 个
     • /browser_navigate
       Navigate to a URL
     • /browser_click
       Perform click on a web page
     • /browser_snapshot
       Capture accessibility snapshot

==================================================
```

**状态图标说明:**
- ✅ **已连接** - MCP 服务器正常运行
- ⏳ **连接中** - 正在建立连接
- ❌ **连接失败** - 无法连接到服务器
- 🔒 **需要认证** - 需要提供认证信息
- ⚪ **已禁用** - 该服务器被禁用

---

### `/help:command` - 可用命令详情

查看 Claude Code CLI 中已加载的所有可用命令,包括斜杠命令和系统命令。

**用法:**
```
/help:command
```

**功能:**
- 📋 显示所有可用的斜杠命令
- 📝 显示命令的详细描述
- ⚙️ 显示系统命令列表
- 🔢 显示命令总数统计

**示例输出:**
```
🔧 可用命令详情
==================================================

📋 斜杠命令:

/plan
  Create implementation plan for complex features

/commit
  Create git commit with staged changes

/test
  Run tests and show results

/review
  Review code changes and provide feedback

/save-session
  Save current session state to a file

/resume-session
  Load and resume a previously saved session

⚙️  系统命令: 3 个
  • /clear
  • /exit
  • /help

==================================================

💡 提示:
• 使用 /claude:{命令名} 执行上述斜杠命令
• 使用 /help 查看所有可用命令
```

---

## 使用场景

### 场景 1: 查看 MCP 工具是否正常加载

当你需要确认某个 MCP 服务器的连接状态时:

```
用户: /help:mcp

机器人: 🔌 MCP 工具详情
...

✅ **godot**
   类型: stdio
   作用域: project
   工具: 10 个
```

### 场景 2: 查找可用的命令

当你想了解有哪些命令可用时:

```
用户: /help:command

机器人: 🔧 可用命令详情
...

📋 斜杠命令:
/plan
  Create implementation plan
...
```

### 场景 3: 查看命令详细描述

当你想知道某个命令的具体功能时,可以先查看命令列表:

```
用户: /help:command

机器人: 🔧 可用命令详情
...

/blueprint
  Turn a one-line objective into a step-by-step construction plan
```

---

## 技术实现

### 命令路由

这两个新命令在 `src/bridges/feishu/command_handler.py` 中实现:

```python
elif command == "/help:mcp":
    return await self._handle_help_mcp(message, args)
elif command == "/help:command":
    return await self._handle_help_command(message, args)
```

### 数据获取

通过 `ClaudeSDKAdapter` 获取 MCP 和命令信息:

```python
# 获取 MCP 工具信息
mcp_info = await claude_adapter.get_mcp_tools_info()

# 获取命令信息
commands_info = await claude_adapter.get_commands_info()
```

### 错误处理

如果获取信息失败,命令会返回友好的错误消息:

```
❌ 获取 MCP 工具信息失败: Connection timeout
```

---

## 注意事项

1. **需要活跃会话**: 这些命令需要在活跃的 Claude 会话中执行
2. **网络依赖**: 获取 MCP 和命令信息需要连接到 Claude CLI
3. **性能考虑**: 信息查询需要一定时间,请耐心等待
4. **信息缓存**: 当前实现每次都会重新查询,未来可能添加缓存机制

---

## 开发指南

### 添加新的帮助命令

如果需要添加更多帮助命令,可以按照以下步骤:

1. 在 `CommandHandler.handle()` 中添加路由
2. 实现对应的处理方法 `_handle_help_xxx()`
3. 在 `/help` 命令的帮助文本中添加说明
4. 编写测试用例

### 示例

```python
# 1. 添加路由
elif command == "/help:skills":
    return await self._handle_help_skills(message, args)

# 2. 实现处理方法
async def _handle_help_skills(self, message: IMMessage, args: str) -> str:
    """显示技能信息"""
    # 实现逻辑
    pass

# 3. 更新帮助文本
# 在 /help 命令中添加 /help:skills 的说明
```

---

## 相关文件

- `src/bridges/feishu/command_handler.py` - 命令处理器实现
- `src/claude/sdk_adapter.py` - SDK 适配器,提供数据获取接口
- `tests/test_help_commands.py` - 测试用例

---

## 更新日志

### 2026-03-12
- ✅ 添加 `/help:mcp` 命令
- ✅ 添加 `/help:command` 命令
- ✅ 更新 `/help` 命令,包含新命令说明
- ✅ 添加完整的测试用例
- ✅ 创建使用文档
