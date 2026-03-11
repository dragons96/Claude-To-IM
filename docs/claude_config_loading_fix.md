# Claude Code CLI 配置加载修复说明

## 问题分析

用户反馈启动服务后显示的配置信息为空：
- MCP 服务器: 无
- 斜杠命令: 无
- 系统命令: 无

## 根本原因

### 1. 缺少 `setting_sources` 参数

在创建 `ClaudeAgentOptions` 时，没有指定 `setting_sources` 参数，导致默认传递空字符串给 CLI，不会加载用户配置。

### 2. 每个会话的工作目录未正确设置

虽然 `create_session` 方法接受 `work_directory` 参数，但所有会话共享同一个 `options` 对象，没有为每个会话设置独立的工作目录。

## 配置层级说明

Claude Code CLI 支持三个配置层：

1. **user（用户目录）**
   - 位置：`C:\Users\用户名\.claude\`
   - 包含：用户的全局配置、MCP 服务器、skills、rules
   - 优先级：最低（可被其他层级覆盖）

2. **project（项目目录）**
   - 位置：项目根目录的 `.claude/` 或父目录
   - 包含：项目特定的配置
   - 优先级：中等（覆盖 user，被 local 覆盖）

3. **local（本地配置）**
   - 位置：当前工作目录的 `.claude/`
   - 包含：本地会话的配置
   - 优先级：最高（覆盖所有）

## 修复方案

### 1. 明确指定 `setting_sources`

在 `src/cli/main.py` 中：

```python
claude_options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_AUTH_TOKEN": settings.ANTHROPIC_AUTH_TOKEN,
        "ANTHROPIC_BASE_URL": settings.ANTHROPIC_BASE_URL,
    },
    model=settings.ANTHROPIC_MODEL,
    max_turns=settings.MAX_TURNS,
    include_partial_messages=True,
    # ✅ 明确指定加载所有配置源
    setting_sources=["user", "project", "local"]
)
```

这样 CLI 会按优先级加载三个层级的配置。

### 2. 为每个会话设置独立的工作目录

在 `src/claude/sdk_adapter.py` 的 `create_session` 方法中：

```python
async def create_session(
    self,
    work_directory: str,
    session_id: Optional[str] = None
) -> ClaudeSession:
    if session_id is None:
        session_id = str(uuid.uuid4())

    # ✅ 为这个会话创建独立的 options，设置工作目录
    session_options = copy.copy(self.options)
    session_options.cwd = work_directory

    # 创建 SDK 客户端并建立连接
    client = ClaudeSDKClient(session_options)
    ...
```

这样：
- 每个会话有独立的工作目录（用于代码操作）
- 所有会话共享用户配置（MCP、skills、rules）
- 符合"一个飞书会话对应多个 Claude 会话"的设计

## 验证方法

启动服务后，应该能看到：

```
============================================================
Claude SDK 配置信息
============================================================

📦 MCP 服务器 (X 个):
  ✅ [用户配置的 MCP 服务器]
     类型: xxx, 作用域: user
     工具: X 个

🔧 可用命令:
  斜杠命令 (XX 个):
    /help
    /new
    /sessions
    /superpowers:write-plans
    ...
  系统命令: X 个

============================================================
```

## 关键要点

✅ **setting_sources 必须明确指定** - 否则不会加载用户配置
✅ **每个会话有独立的工作目录** - 但共享用户配置
✅ **配置按优先级加载** - local > project > user
✅ **MCP 和 skills 来自 user 层级** - 工作目录在 cwd

## 架构说明

```
用户配置（user）
├── ~/.claude/config.json       ← 全局配置
├── ~/.claude/mcp.json          ← MCP 服务器配置
├── ~/.claude/skills/           ← 用户 skills
└── ~/.claude/rules/            ← 用户规则

项目配置（project）
└── .claude/config.json         ← 项目特定配置

会话配置（local）
└── .claude/config.json         ← 会话特定配置（如有）

每个 Claude 会话
├── cwd: 独立的工作目录          ← 用于文件操作
├── MCP 服务器: 从 user 加载     ← 共享用户配置
├── skills: 从 user 加载         ← 共享用户配置
└── rules: 从 user 加载          ← 共享用户配置
```

## 相关文件

- 配置加载: `src/cli/main.py` (第 136-146 行)
- 会话创建: `src/claude/sdk_adapter.py` (第 30-68 行)
- 类型定义: `.venv/Lib/site-packages/claude_agent_sdk/types.py` (第 976-1045 行)
- CLI 参数: `.venv/Lib/site-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py` (第 276-281 行)
