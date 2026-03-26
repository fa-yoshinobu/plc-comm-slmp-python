@echo off
setlocal

echo ===================================================
echo [RELEASE] SLMP Python release check
echo ===================================================

echo [1/2] Running CI...
call run_ci.bat
if %errorlevel% neq 0 (
    echo [ERROR] CI failed.
    exit /b %errorlevel%
)

echo [2/2] Building docs...
call build_docs.bat
if %errorlevel% neq 0 (
    echo [ERROR] Docs build failed.
    exit /b %errorlevel%
)

echo ===================================================
echo [SUCCESS] Release check passed.
echo ===================================================
endlocal
