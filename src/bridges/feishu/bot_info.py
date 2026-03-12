# src/bridges/feishu/bot_info.py
"""飞书机器人信息工具模块

提供获取机器人信息的功能，特别是机器人的 open_id。
"""
import logging
from typing import Optional, Dict, Any

import lark_oapi as lark
from lark_oapi.core.model import BaseRequest, RequestOption
from lark_oapi.core import HttpMethod, AccessTokenType


logger = logging.getLogger(__name__)


def get_bot_info(http_client: lark.Client) -> Optional[Dict[str, Any]]:
    """获取机器人信息

    通过飞书 API 获取机器人的基本信息，包括 open_id。

    Args:
        http_client: 飞书 HTTP 客户端实例

    Returns:
        Optional[Dict[str, Any]]: 机器人信息字典，包含：
            - open_id: 机器人的 open_id
            - app_name: 应用名称
            - activate_status: 激活状态
            - avatar_url: 头像URL
            如果获取失败则返回 None
    """
    try:
        # 构造请求
        request = BaseRequest.builder() \
            .http_method(HttpMethod.GET) \
            .uri("/open-apis/bot/v3/info") \
            .token_types({AccessTokenType.TENANT}) \
            .build()

        # 发起请求
        response = http_client.request(request)

        # 检查响应
        if response.code == 0:
            # 从 raw.content 中解析 JSON
            import json
            from lark_oapi.core.const import UTF_8
            response_data = json.loads(str(response.raw.content, UTF_8))

            bot_info = response_data.get("bot", {})
            open_id = bot_info.get("open_id")

            if open_id:
                logger.info(f"✅ 成功获取机器人信息: open_id={open_id}, app_name={bot_info.get('app_name')}")
                return {
                    "open_id": open_id,
                    "app_name": bot_info.get("app_name"),
                    "activate_status": bot_info.get("activate_status"),
                    "avatar_url": bot_info.get("avatar_url"),
                }
            else:
                logger.warning("API 响应中未找到 open_id")
                return None
        else:
            logger.error(f"获取机器人信息失败: code={response.code}, msg={response.msg}")
            return None

    except Exception as e:
        logger.error(f"获取机器人信息时发生异常: {e}")
        return None


async def get_bot_info_async(http_client: lark.Client) -> Optional[Dict[str, Any]]:
    """异步获取机器人信息

    通过飞书 API 获取机器人的基本信息，包括 open_id。

    Args:
        http_client: 飞书 HTTP 客户端实例

    Returns:
        Optional[Dict[str, Any]]: 机器人信息字典，包含：
            - open_id: 机器人的 open_id
            - app_name: 应用名称
            - activate_status: 激活状态
            - avatar_url: 头像URL
            如果获取失败则返回 None
    """
    try:
        # 构造请求
        request = BaseRequest.builder() \
            .http_method(HttpMethod.GET) \
            .uri("/open-apis/bot/v3/info") \
            .token_types({AccessTokenType.TENANT}) \
            .build()

        # 发起异步请求
        response = await http_client.arequest(request)

        # 检查响应
        if response.code == 0:
            # 从 raw.content 中解析 JSON
            import json
            from lark_oapi.core.const import UTF_8
            response_data = json.loads(str(response.raw.content, UTF_8))

            bot_info = response_data.get("bot", {})
            open_id = bot_info.get("open_id")

            if open_id:
                logger.info(f"✅ 成功获取机器人信息: open_id={open_id}, app_name={bot_info.get('app_name')}")
                return {
                    "open_id": open_id,
                    "app_name": bot_info.get("app_name"),
                    "activate_status": bot_info.get("activate_status"),
                    "avatar_url": bot_info.get("avatar_url"),
                }
            else:
                logger.warning("API 响应中未找到 open_id")
                return None
        else:
            logger.error(f"获取机器人信息失败: code={response.code}, msg={response.msg}")
            return None

    except Exception as e:
        logger.error(f"获取机器人信息时发生异常: {e}")
        return None
