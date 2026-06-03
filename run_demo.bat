@echo off
chcp 65001 >nul
echo ============================================
for /f "delims=" %%v in ('type VERSION') do echo   Novel Forge - 小说引擎 %%v
echo   Demo Run
echo ============================================
echo.

:: Check config
if not exist config.json (
    echo [ERROR] config.json not found. Please run install.bat first.
    pause
    exit /b 1
)

:: Import voice profiles (if available)
echo [STEP 0] Importing character voice profiles...
if exist examples\demo_novel\voice_profiles.example.json (
    python scripts/import_voice_profiles.py --config config.json --novel-slug demo_novel --input examples\demo_novel\voice_profiles.example.json 2>nul
    echo [OK] Voice profiles imported
) else (
    echo [INFO] No voice_profiles.example.json found, skipping
)

:: Run demo
echo.
echo [STEP 1] Running demo pipeline...
python novel.py demo

:: Show reports
echo.
echo [STEP 2] Showing reports...
python novel.py report

echo.
echo ============================================
echo   Demo complete!
echo   Reports: exports\reports\
echo ============================================
pause
