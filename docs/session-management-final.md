# 会话管理实现方案 (2026-03-12 最终版)

## 需求

1. **目录命名**：
   - `/new` 指定路径：使用用户指定的路径
   - `/new` 未指定路径：生成 UUID 作为目录名
   - 首次发送消息：生成 UUID 作为目录名

2. **Claude Session ID**：
   - 从 SDK 的 `ResultMessage.session_id` 中获取真实的 session_id
   - 不使用自己生成的 UUID 作为 session_id

3. **三者关联**：
   - 飞书会话 ID (`platform_session_id`)
   - Claude session_id (从 SDK 获取的真实 ID)
   - 工作目录 (`work_directory`)

## 实现方案

### 核心流程

```
创建会话
  ↓
生成目录名 (UUID 或用户指定)
  ↓
创建目录
  ↓
调用 SDK 创建会话 (不传 session_id)
  ↓
发送第一条消息
  ↓
从 ResultMessage 获取 real_session_id
  ↓
更新数据库 session_id 字段
```

### 关键技术点

#### 1. 目录命名

**指定路径** (`/new D:/Projects/myproject`):
```python
work_directory = "D:/Projects/myproject"
```

**未指定路径** (`/new` 或首次发送消息):
```python
temp_session_id = str(uuid.uuid4())  # 生成 UUID
work_directory = self.default_session_root / temp_session_id
```

#### 2. SDK 会话创建

```python
# 不传 session_id，让 SDK 自己生成
claude_session = await self.claude_adapter.create_session(
    work_directory=str(work_directory)
)
```

#### 3. 提取真实 Session ID

**sdk_adapter.py** - 在处理 ResultMessage 时：
```python
elif isinstance(sdk_message, ResultMessage):
    real_session_id = sdk_message.session_id  # 真实的 session_id
    yield StreamEvent(
        event_type=StreamEventType.END,
        content="",
        metadata={
            "session_id": session_id,
            "real_session_id": real_session_id  # ← 包含在 metadata 中
        }
    )
```

**adapter.py** - 在处理 END 事件时：
```python
elif event.event_type == StreamEventType.END:
    # 检查是否有真实的 session_id
    real_session_id = event.metadata.get("real_session_id")
    if real_session_id and real_session_id != claude_session_id:
        # 更新数据库
        await self.session_manager.storage.update_claude_session_id(
            old_session_id=claude_session_id,
            new_session_id=real_session_id
        )
```

#### 4. 数据库更新

**storage_service.py** - 添加更新方法：
```python
async def update_claude_session_id(
    self,
    old_session_id: str,
    new_session_id: str
) -> bool:
    """更新 Claude 会话的 session_id"""
    session = self.db.query(ClaudeSession).filter_by(
        session_id=old_session_id
    ).first()
    if session:
        session.session_id = new_session_id
        self.db.commit()
        return True
    return False
```

## 数据结构

### 数据库表结构

**im_sessions** 表：
```sql
id                  VARCHAR(64) PRIMARY KEY
platform            VARCHAR(32)
platform_session_id VARCHAR(128) UNIQUE
```

**claude_sessions** 表：
```sql
id                VARCHAR(64) PRIMARY KEY
im_session_id     VARCHAR(64)
session_id        VARCHAR(128) UNIQUE  -- Claude SDK 的真实 session_id
work_directory    VARCHAR(512)
is_active         BOOLEAN
summary           VARCHAR(10)
```

### 文件系统结构

```
sessions/
├── 37bb3160-a5d0-47d0-b72d-6c16041a5d7a/  ← UUID 作为目录名
│   └── (Claude SDK 会话数据)
├── df4832d4-53b7-4918-b237-404d85af52f0/
│   └── (Claude SDK 会话数据)
└── D:/Projects/myproject/  ← 用户指定的路径
    └── (Claude SDK 会话数据)
```

## 使用场景

### 场景1: /new 命令（未指定目录）

```bash
用户: /new

系统:
1. 生成 UUID: 37bb3160-a5d0-47d0-b72d-6c16041a5d7a
2. 创建目录: sessions/37bb3160-a5d0-47d0-b72d-6c16041a5d7a
3. 创建 SDK 会话
4. 发送"介绍自己"消息
5. 从 ResultMessage 获取 real_session_id
6. 更新数据库
7. 返回成功消息
```

### 场景2: /new 命令（指定目录）

```bash
用户: /new D:/Projects/myproject

系统:
1. 使用指定目录: D:/Projects/myproject
2. 创建目录（如果不存在）
3. 创建 SDK 会话
4. 发送"介绍自己"消息
5. 从 ResultMessage 获取 real_session_id
6. 更新数据库
7. 返回成功消息
```

### 场景3: 首次发送消息（无活跃会话）

```bash
用户: 你好，帮我写个函数

系统:
1. 生成 UUID: df4832d4-53b7-4918-b237-404d85af52f0
2. 创建目录: sessions/df4832d4-53b7-4918-b237-404d85af52f0
3. 创建 SDK 会话
4. 发送用户消息
5. 从 ResultMessage 获取 real_session_id
6. 更新数据库
7. 返回 Claude 的响应
```

### 场景4: Resume 会话

```bash
用户: /switch abc123-def456

系统:
1. 从数据库获取会话记录
2. 使用 resume 参数恢复会话
   await self.claude_adapter.create_session(
       work_directory=session.work_directory,
       resume_session_id=session.session_id  # 使用真实 session_id
   )
3. 切换成功，拥有该会话的上下文
```

## 文件修改清单

### 1. src/services/session_manager.py
- `create_session()`: 处理指定/未指定目录的情况
- `get_or_create_session()`: 自动创建会话逻辑

### 2. src/claude/sdk_adapter.py
- `send_message()`: 在 ResultMessage 处理时添加 real_session_id 到 metadata

### 3. src/bridges/feishu/adapter.py
- `_stream_claude_response()`: 在 END 事件处理中更新数据库 session_id
- 修复 IMMessage 字段名错误（`sender_id` → `user_id`）

### 4. src/services/storage_service.py
- 添加 `update_claude_session_id()` 方法

## 注意事项

1. **Windows 目录锁定**：CLI 启动后锁定目录，无法重命名，所以使用 UUID 作为最终目录名
2. **Session ID 更新时机**：只在第一次发送消息后更新，避免重复更新
3. **Resume 功能**：使用数据库中保存的真实 session_id 进行恢复
4. **三者关联**：通过数据库表的外键关联飞书会话和 Claude 会话

## 测试验证

```bash
# 测试会话创建
python -m pytest tests/test_services/test_session_manager.py -v

# 测试命令处理
python -m pytest tests/test_new_commands.py -v

# 完整测试
python -m pytest tests/ -v --ignore=tests/integration
```

## 日期

2026-03-12 晚上
