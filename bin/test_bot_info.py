#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试获取机器人信息功能"""
import lark_oapi as lark
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    print("=" * 40)
    print("测试获取机器人信息功能")
    print("=" * 40)
    print()

    # 加载环境变量
    env_file = project_root / ".env"
    if not env_file.exists():
        print("❌ 错误: .env 文件不存在")
        print("   请在项目根目录创建 .env 文件并配置以下变量:")
        print("   - FEISHU_APP_ID")
        print("   - FEISHU_APP_SECRET")
        return 1

    load_dotenv(env_file)

    app_id = os.getenv('FEISHU_APP_ID')
    app_secret = os.getenv('FEISHU_APP_SECRET')

    if not app_id or not app_secret:
        print("❌ 错误: 请在 .env 文件中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return 1

    print(f"App ID: {app_id}")
    print(f"App Secret: {app_secret[:10]}..." if len(app_secret) > 10 else f"App Secret: {app_secret}")
    print()

    try:
        # 创建客户端
        print("正在创建飞书客户端...")
        client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

        print("✅ 飞书客户端创建成功")
        print()

        # 获取机器人信息
        from src.bridges.feishu.bot_info import get_bot_info

        print("🔍 正在获取机器人信息...")
        bot_info = get_bot_info(client)

        if bot_info:
            print()
            print("🎉 成功获取机器人信息:")
            print(f"   Open ID: {bot_info.get('open_id')}")
            print(f"   应用名称: {bot_info.get('app_name')}")

            # 解析激活状态
            activate_status = bot_info.get('activate_status')
            status_map = {
                0: "初始化",
                1: "租户停用",
                2: "租户启用",
                3: "安装后待启用",
                4: "升级待启用",
                5: "license过期停用",
                6: "Lark套餐到期或降级停用"
            }
            status_text = status_map.get(activate_status, activate_status)
            print(f"   激活状态: {status_text}")

            if bot_info.get('avatar_url'):
                print(f"   头像URL: {bot_info.get('avatar_url')}")
            print()
            print("✅ 测试通过!")
            return 0
        else:
            print()
            print("❌ 获取机器人信息失败")
            print("请检查:")
            print("  1. App ID 和 App Secret 是否正确")
            print("  2. 应用是否已启用机器人能力")
            print("  3. 应用是否已发布")
            return 1

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
