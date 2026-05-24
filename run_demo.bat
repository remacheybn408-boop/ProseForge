@echo off
chcp 65001 >nul
echo ============================================
echo   Novel Pipeline - Write Engine v0.4.0
echo   Demo Run
echo ============================================
echo.

:: Check config
if not exist config.json (
    echo [ERROR] config.json 不存在，请先运行 install.bat
    pause
    exit /b 1
)

:: Run pre for chapter 1
echo [STEP 1] 写作前准备 (pre)...
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel --volume-no 1

:: Try post if chapter exists
echo.
echo [STEP 2] 检查是否有 demo 章节...
set CHAPTER_FILE=novels\demo_novel\第01卷\第1章_测试章节.txt
if exist "%CHAPTER_FILE%" (
    python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel --chapter-type normal
) else (
    echo [INFO] 未找到 demo 章节 TXT，跳过 post.
    echo   创建文件后运行:
    echo     python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel
)

:: Run tests
echo.
echo [STEP 3] 运行测试...
python -m pytest tests/ -q

echo.
echo ============================================
echo   Demo 运行完成！
echo   查看报告: exports\reports\
echo ============================================
pause
