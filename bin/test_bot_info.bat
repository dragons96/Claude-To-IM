@echo off
REM 测试获取机器人信息功能

echo ========================================
echo 测试获取机器人信息功能
echo ========================================
echo.

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 运行测试脚本
python bin\test_bot_info.py

echo.
pause
