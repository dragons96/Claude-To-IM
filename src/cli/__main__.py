# src/cli/__main__.py
"""CLI 入口模块"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from src.cli.main import main

if __name__ == "__main__":
    main()
