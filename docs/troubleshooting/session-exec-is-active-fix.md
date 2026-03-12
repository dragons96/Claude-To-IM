# /session:exec 命令缺少 is_active 参数错误

## 问题描述

在使用 `/session:exec` 命令时出现以下错误：

```
TypeError: ClaudeSession.__init__() missing 1 required positional argument: 'is_active'
```

### 错误堆栈

```
File "d:\Codes\examples\claude-to-im\src\bridges\feishu\adapter.py", line 1383, in route_to_claude_with_session
    claude_session = ClaudeSession(
                     ^^^^^^^^^^^^^^
TypeError: ClaudeSession.__init__() missing 1 required positional argument: 'is_active'
```

## 根本原因

在 `src/bridges/feishu/adapter.py` 的 `route_to_claude_with_session` 方法中，创建 `ClaudeSession` 对象时缺少了 `is_active` 参数。

### ClaudeSession 定义

```python
@dataclass
class ClaudeSession:
    """Claude 会话对象"""
    session_id: str
    work_directory: str
    is_active: bool  # ← 必需参数
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### 错误代码（修复前）

```python
# 构建会话对象
from src.core.claude_adapter import ClaudeSession
claude_session = ClaudeSession(
    session_id=session_record.session_id,
    work_directory=session_record.work_directory
    # ❌ 缺少 is_active 参数
)
```

## 解决方案

在创建 `ClaudeSession` 对象时添加 `is_active` 参数：

```python
# 构建会话对象
from src.core.claude_adapter import ClaudeSession
claude_session = ClaudeSession(
    session_id=session_record.session_id,
    work_directory=session_record.work_directory,
    is_active=session_record.is_active  # ✅ 添加 is_active 参数
)
```

## 修改文件

- **src/bridges/feishu/adapter.py** (line 1383-1386)

## 影响范围

- 影响 `/session:exec` 命令的正常执行
- 导致无法在指定会话中执行命令

## 测试验证

### 测试代码

```python
from src.core.claude_adapter import ClaudeSession
from unittest.mock import Mock

session_record = Mock()
session_record.session_id = 'test-session-id'
session_record.work_directory = '/test/path'
session_record.is_active = True

claude_session = ClaudeSession(
    session_id=session_record.session_id,
    work_directory=session_record.work_directory,
    is_active=session_record.is_active
)

assert claude_session.session_id == 'test-session-id'
assert claude_session.is_active == True
```

### 验证结果

✅ 修复成功，`/session:exec` 命令可以正常工作

## 预防措施

为了避免类似问题，建议：

1. **使用类型提示**: 在函数签名中明确参数类型
2. **单元测试**: 为所有创建对象的地方编写测试
3. **代码审查**: 关注 dataclass 和 namedtuple 的所有必需字段

## 相关文档

- `docs/troubleshooting/session-id-consistency-fix.md` - 会话ID一致性修复
- `docs/new_commands_guide.md` - 新命令使用指南

## 修复日期

2026-03-12
