# Claude Code CLI 配置加载说明

> ⚠️ **注意**：本文档已过时，请查看 [claude_config_loading_fix.md](./claude_config_loading_fix.md) 获取最新的修复说明。

## 问题描述

启动服务时显示的配置信息为空：
- MCP 服务器: 无
- 斜杠命令: 无
- 系统命令: 无

即使你的 Claude Code CLI 已经配置了 MCP 服务器和 skills。

## 正确的解决方案

### 1. 明确指定 `setting_sources` 参数

**关键**：必须明确指定 `setting_sources=["user", "project", "local"]` 来加载所有配置层。

```python
claude_options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_AUTH_TOKEN": settings.ANTHROPIC_AUTH_TOKEN,
        "ANTHROPIC_BASE_URL": settings.ANTHROPIC_BASE_URL,
    },
    model=settings.ANTHROPIC_MODEL,
    max_turns=settings.MAX_TURNS,
    include_partial_messages=True,
    # ✅ 关键：加载所有配置源（用户、项目、本地）
    setting_sources=["user", "project", "local"]
)
```

### 2. 为每个会话设置独立的工作目录

在 `create_session` 方法中，为每个会话设置独立的工作目录：

```python
# 为这个会话创建独立的 options，设置工作目录
session_options = copy.copy(self.options)
session_options.cwd = work_directory

client = ClaudeSDKClient(session_options)
```

## 配置层级说明

Claude Code CLI 支持三个配置层：

1. **user（用户目录）** - `C:\Users\用户名\.claude\`
   - 包含：全局配置、MCP 服务器、skills、rules
   - 优先级：最低

2. **project（项目目录）** - 项目根目录的 `.claude/`
   - 包含：项目特定配置
   - 优先级：中等

3. **local（本地配置）** - 当前工作目录的 `.claude/`
   - 包含：本地会话配置
   - 优先级：最高

## 验证方法

启动服务后，应该能看到类似这样的输出：

```
============================================================
Claude SDK 配置信息
============================================================

📦 MCP 服务器 (3 个):
  ✅ github
     类型: github, 作用域: repository
     工具: 5 个

  ✅ filesystem
     类型: filesystem, 作用域: read
     工具: 3 个

  ❌ database
     错误: Connection failed

🔧 可用命令:
  斜杠命令 (15 个):
    /help
    /new
    /sessions
    /commit
    ...
  系统命令: 8 个

============================================================
```

## 常见问题

### Q: 为什么之前没有加载配置？

A: 之前的代码没有设置 `cwd` 参数，Claude Code CLI 无法知道从哪里查找配置文件。

### Q: `cwd` 应该设置为什么？

A: 通常设置为 `os.getcwd()`（当前工作目录）。如果你想在特定项目中使用特定配置，可以设置为项目路径。

### Q: 如何知道我的配置文件在哪里？

A: 在终端中运行：
```bash
# 查看用户主目录的配置
ls ~/.claude/

# 或在 Windows 上
dir %USERPROFILE%\.claude\

# 查看当前项目的配置
ls .claude/
```

### Q: 如何创建 MCP 服务器配置？

A: 参考 Claude Code CLI 文档，在 `~/.claude/mcp.json` 中配置：

```json
{
  "mcpServers": {
    "github": {
      "type": "github",
      "scope": "repository"
    },
    "filesystem": {
      "type": "filesystem",
      "scope": "read"
    }
  }
}
```

## 相关文件

- 配置加载: `src/cli/main.py` (第 136-145 行)
- 配置显示: `src/claude/sdk_adapter.py` (第 227-339 行)
- 示例代码: `examples/claude_code_sdk.py` (第 29 行)

## 关键要点

✅ **必须设置 `cwd` 参数** - 否则无法加载配置
✅ **使用 `os.getcwd()`** - 让 CLI 从当前目录查找配置
✅ **配置自动继承** - 会自动使用用户的 Claude Code 配置
✅ **支持项目级配置** - 可以在项目中覆盖全局配置
