@echo off
chcp 65001 >nul
echo ============================================
echo   Novel Pipeline - Write Engine v0.4.0
echo   Human-Grade Revision Suite
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 未安装或未加入 PATH.
    echo   请从 https://www.python.org/downloads/ 安装 Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python 已安装
python --version

:: Install pytest if needed
python -c "import pytest" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 安装 pytest...
    pip install pytest -q
)
echo [OK] pytest 可用

:: Copy config
if not exist config.json (
    echo [INFO] 创建 config.json...
    copy config.example.json config.json >nul
    echo [OK] config.json 已创建
) else (
    echo [OK] config.json 已存在
)

:: Init DB
echo [INFO] 初始化数据库...
python scripts/init_db.py --config config.json 2>nul
if %errorlevel% equ 0 (
    echo [OK] 数据库已初始化
) else (
    echo [WARN] 数据库初始化可能失败，跳过
)

:: Import demo skeleton
echo [INFO] 导入 Demo 标题骨架...
python scripts/import_outline_skeleton.py --config config.json --input examples/demo_novel/outline_skeleton.json 2>nul
echo [OK] Demo 骨架已导入

:: Run doctor
echo [INFO] 运行环境检查...
python scripts/doctor.py 2>nul
echo.

echo ============================================
echo   安装完成！
echo   运行: run_demo.bat    快速体验
echo   运行: run_tests.bat   跑全量测试
echo ============================================
pause
