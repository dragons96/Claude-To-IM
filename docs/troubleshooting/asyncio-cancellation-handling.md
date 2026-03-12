# Ctrl+C 终止应用时的 asyncio 错误

## 问题描述

当用户通过 `Ctrl+C` 终止应用时，会出现以下错误：

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
AttributeError: 'TaskGroup' object has no attribute '_exceptions'
```

## 问题根源

这是一个经典的 **asyncio 与 anyio cancel scope 不兼容**问题：

1. 当用户按 `Ctrl+C` 时，`asyncio.run()` 会取消所有正在运行的任务
2. `ClaudeSDKClient` 内部使用 `anyio.TaskGroup`，它有自己的 cancel scope 管理
3. 当 `__aexit__` 在不同的任务中被调用时（因为任务被取消并重新调度），anyio 的 cancel scope 检测到它不是在创建它的同一个任务中被退出，因此抛出错误

## 解决方案

### 1. 在 `sdk_adapter.py` 中添加 `close_all_sessions` 方法

添加了一个安全关闭所有会话的方法，会：
- 尝试关闭所有会话，即使某个会话关闭失败
- 记录所有错误，但不会抛出异常
- 捕获并忽略 `RuntimeError` 中的 cancel scope 错误

### 2. 在 `main.py` 的 `_cleanup_components` 中改进错误处理

- 使用 `asyncio.shield` 保护关闭操作
- 使用 `asyncio.wait_for` 添加超时保护（3秒）
- 专门捕获 `RuntimeError` 并检查是否包含 "cancel scope"
- 忽略 cancel scope 错误，继续关闭其他会话

### 3. 在 `main_async` 中改进异常处理

- 使用 `asyncio.gather` 的 `return_exceptions=True` 确保所有清理操作都被尝试
- 添加多层防护，确保即使清理过程被取消也不会抛出未处理的异常

## 代码示例

### 安全关闭 SDK 客户端

```python
# sdk_adapter.py - close_session 方法

async def close_session(self, session_id: str) -> None:
    """关闭指定的会话"""
    if session_id in self.sessions:
        session_data = self.sessions[session_id]
        client = session_data["client"]

        # 退出异步上下文管理器
        if hasattr(client, '__aexit__'):
            try:
                # 使用 shield 保护关闭操作，避免被外部取消
                import asyncio
                try:
                    # 添加超时保护，避免无限等待
                    await asyncio.shield(
                        asyncio.wait_for(
                            client.__aexit__(None, None, None),
                            timeout=3.0
                        )
                    )
                except asyncio.CancelledError:
                    # 忽略取消错误，继续清理
                    logger.debug(f"关闭会话 {session_id} 时被取消，继续清理")
                except RuntimeError as e:
                    # 忽略 cancel scope 错误（跨任务关闭）
                    if "cancel scope" in str(e):
                        logger.debug(f"关闭会话 {session_id} 时遇到 cancel scope 错误，已忽略")
                    else:
                        raise
            except asyncio.TimeoutError:
                logger.warning(f"关闭会话 {session_id} 超时")
            except Exception as e:
                logger.warning(f"关闭会话 {session_id} 时出错: {e}")

        # 从会话字典中移除
        del self.sessions[session_id]
```

### 改进的清理函数

```python
# main.py - _cleanup_components 函数

async def _cleanup_components(components: dict, force: bool = False) -> None:
    """清理组件资源"""
    # ... 前面的代码 ...

    # 关闭所有 Claude 会话
    logger.info("关闭 Claude 会话...")
    try:
        claude_adapter = components["claude_adapter"]
        sessions = await claude_adapter.list_sessions()

        for session in sessions:
            session_id = session.session_id
            try:
                # 使用 shield 保护关闭操作，避免被外部取消
                # 添加超时保护，避免无限等待
                await asyncio.shield(
                    asyncio.wait_for(
                        claude_adapter.close_session(session_id),
                        timeout=3.0
                    )
                )
            except asyncio.TimeoutError:
                logger.warning(f"关闭会话 {session_id} 超时")
            except asyncio.CancelledError:
                if not force:
                    raise
                logger.debug(f"关闭会话 {session_id} 时被取消")
            except RuntimeError as e:
                # 忽略 cancel scope 错误（跨任务关闭）
                if "cancel scope" in str(e):
                    logger.debug(f"关闭会话 {session_id} 时遇到 cancel scope 错误，已忽略")
                else:
                    logger.warning(f"关闭会话 {session_id} 时遇到 RuntimeError: {e}")
            except Exception as e:
                logger.warning(f"关闭会话 {session_id} 时出错: {e}")

    except asyncio.CancelledError:
        if not force:
            raise
        logger.debug("列出会话时被取消")
    except Exception as e:
        if not force:
            logger.error(f"关闭会话时出错: {e}")
        else:
            logger.debug(f"关闭会话时出错（强制模式）: {e}")

    # ... 后面的代码 ...
```

## 最佳实践

1. **始终使用 `asyncio.shield` 保护清理操作**
   - 防止清理过程被外部取消

2. **添加超时保护**
   - 使用 `asyncio.wait_for` 避免无限等待
   - 推荐超时时间：3-5秒

3. **捕获特定错误类型**
   - `asyncio.CancelledError`：取消操作
   - `RuntimeError`：检查是否包含 "cancel scope"
   - `asyncio.TimeoutError`：超时操作

4. **记录但忽略清理错误**
   - 清理失败不应该阻止应用退出
   - 使用 `logger.debug` 或 `logger.warning` 记录错误

5. **多层防护**
   - 即使清理过程失败，也要确保不会抛出未处理的异常
   - 使用 `try-except` 包裹整个清理流程

## 测试

1. **正常关闭测试**
   ```bash
   # 启动应用后，按一次 Ctrl+C
   python -m src.cli.main
   # 应该看到优雅关闭日志，没有错误
   ```

2. **强制关闭测试**
   ```bash
   # 启动应用后，按两次 Ctrl+C
   python -m src.cli.main
   # 应该看到"强制退出"日志
   ```

3. **有活跃会话时关闭**
   ```bash
   # 创建一个会话后按 Ctrl+C
   # 应该看到"关闭 Claude 会话..."日志
   # 没有 RuntimeError 或 cancel scope 错误
   ```

## 参考资料

- [asyncio.shield](https://docs.python.org/3/library/asyncio-task.html#asyncio.shield)
- [asyncio.wait_for](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for)
- [anyio TaskGroup](https://anyio.readthedocs.io/en/stable/taskgroups.html)
- [Python asyncio: Handling CancelledError](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError)

## 相关文件

- `src/claude/sdk_adapter.py` - Claude SDK 适配器
- `src/cli/main.py` - 主入口和清理逻辑
- `src/services/session_manager.py` - 会话管理器

## 更新历史

- 2026-03-12: 初始版本，记录 Ctrl+C 终止时的 asyncio 错误及解决方案
