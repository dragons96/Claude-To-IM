# 飞书机器人信息获取功能

## 概述

本项目集成了飞书机器人信息 API，可以在应用启动时自动获取机器人的 `open_id`，无需手动配置。

## 功能特性

### 1. 自动获取机器人信息

在应用启动时，系统会自动通过飞书 API 获取以下信息：

- **open_id**: 机器人的唯一标识符
- **app_name**: 应用名称
- **activate_status**: 激活状态
- **avatar_url**: 头像URL

### 2. 多级回退机制

系统使用多级回退机制来获取机器人用户 ID（bot_user_id）：

1. **API 获取**（推荐）: 通过飞书 API `/open-apis/bot/v3/info` 自动获取
2. **配置文件**: 从 `.env` 文件中的 `FEISHU_BOT_USER_ID` 读取
3. **本地缓存**: 从 `sessions/robot_id.txt` 文件读取
4. **自动提取**: 从收到 `@机器人` 的消息中自动提取

### 3. 自动缓存

获取到的 `open_id` 会自动保存到 `sessions/robot_id.txt` 文件，下次启动时直接使用。

## API 参考

### 获取机器人信息

**端点**: `GET /open-apis/bot/v3/info`

**认证**: 使用 `tenant_access_token`

**响应示例**:

```json
{
    "code": 0,
    "msg": "ok",
    "bot": {
        "activate_status": 2,
        "app_name": "应用名称",
        "avatar_url": "https://...",
        "open_id": "ou_xxxxxxxxxxxxxxxx"
    }
}
```

**激活状态说明**:

- `0`: 初始化，租户待安装
- `1`: 租户停用
- `2`: 租户启用
- `3`: 安装后待启用
- `4`: 升级待启用
- `5`: license过期停用
- `6`: Lark套餐到期或降级停用

## 使用方法

### 1. 测试功能

运行测试脚本：

```bash
# Windows
bin\test_bot_info.bat

# 或直接运行 Python 脚本
python bin\test_bot_info.py
```

### 2. 在应用中使用

应用启动时会自动调用此功能，无需额外配置。查看启动日志：

```
🔍 正在通过飞书 API 获取机器人信息...
✅ 通过 API 获取到机器人信息:
   - Open ID: ou_xxxxxxxxxxxxxxxx
   - 应用名称: 金群龙的CC助手
   - 激活状态: 租户启用
✅ 使用API中的机器人用户ID: ou_xxxxxxxxxxxxxxxx
```

## 实现细节

### 核心模块

**文件**: `src/bridges/feishu/bot_info.py`

提供两个函数：

1. **`get_bot_info(http_client)`**: 同步获取机器人信息
2. **`get_bot_info_async(http_client)`**: 异步获取机器人信息

### 适配器集成

**文件**: `src/bridges/feishu/adapter.py`

在 `start()` 方法中自动调用：

```python
# 获取机器人用户ID（优先级：配置 > API > 文件 > 未设置）
bot_user_id = self.config.get("bot_user_id")

# 如果配置中没有，尝试通过 API 获取
if not bot_user_id:
    logger.info("🔍 正在通过飞书 API 获取机器人信息...")
    bot_info = get_bot_info(self._http_client)
    if bot_info and bot_info.get("open_id"):
        bot_user_id = bot_info["open_id"]
        # 保存到文件
        self._save_bot_user_id_to_file(bot_user_id)
```

## 依赖要求

- **lark-oapi**: 1.2.19+
- **应用权限**: 需要启用机器人能力并发布应用

## 故障排查

### 1. API 调用失败

**错误信息**: `❌ 获取机器人信息失败`

**可能原因**:
- App ID 或 App Secret 不正确
- 应用未启用机器人能力
- 应用未发布

**解决方案**:
1. 检查 `.env` 文件中的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`
2. 前往[飞书开放平台](https://open.feishu.cn/)
3. 选择应用 → 应用功能 → 机器人
4. 启用机器人能力并发布

### 2. 权限问题

确保应用有以下权限：
- 无需特殊权限（此 API 不需要额外权限）

### 3. 网络问题

如果无法连接到飞书 API：
- 检查网络连接
- 确认防火墙设置
- 验证代理配置（如果使用）

## 最佳实践

1. **推荐使用 API 获取**: 无需手动配置，自动获取最新信息
2. **保留本地缓存**: 作为备用方案，提高启动速度
3. **监控激活状态**: 定期检查 `activate_status`，确保应用正常运行
4. **日志记录**: 关注启动日志中的机器人信息获取状态

## 相关文档

- [飞书官方文档 - 获取机器人信息](https://open.feishu.cn/document/server-docs/bot-v3/bot-info)
- [飞书开放平台](https://open.feishu.cn/)
- [项目主文档](../README.md)
