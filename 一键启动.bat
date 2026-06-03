@echo off
chcp 65001 >nul
title Novel Forge - 小说引擎 v0.6.5
cd /d "%~dp0"

:check_python
python --version >nul 2>&1
if %errorlevel% equ 0 goto check_deps
echo   Python 未安装，请手动安装 Python 3.10+
echo   下载: https://www.python.org/downloads/
pause
exit /b 1

:check_deps
echo   安装 Python 依赖...
pip install -r requirements.txt -q 2>nul
if not exist config.json (
    if exist config.example.json copy config.example.json config.json >nul
)
python novel.py init 2>nul
echo   初始化完成！
echo.
echo   可用命令:
echo     python novel.py write         写作
echo     python novel.py status        状态检查
echo     python novel.py demo          运行演示
echo     python novel.py report        查看报告
echo.
pause
