@echo off
setlocal

echo ===================================================
echo [RELEASE] SLMP Python release check
echo ===================================================

echo [1/4] Updating canonical SLMP profile JSON...
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\update_slmp_profile_jsons.ps1 -FailIfChanged
if %errorlevel% neq 0 (
    echo [ERROR] Canonical SLMP profile JSON check failed.
    exit /b %errorlevel%
)

echo [2/4] Checking package/runtime version sync...
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_version_sync.ps1
if %errorlevel% neq 0 (
    echo [ERROR] Version sync check failed.
    exit /b %errorlevel%
)

echo [3/4] Checking registry version...
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_registry_duplicate.ps1 -Registry pypi -Package plc-comm-slmp -VersionSource pyproject -ManifestPath pyproject.toml
if %errorlevel% neq 0 (
    echo [ERROR] Release version check failed.
    exit /b %errorlevel%
)

echo [4/4] Running CI...
call run_ci.bat
if %errorlevel% neq 0 (
    echo [ERROR] CI failed.
    exit /b %errorlevel%
)

echo ===================================================
echo [SUCCESS] Release check passed.
echo ===================================================
endlocal
