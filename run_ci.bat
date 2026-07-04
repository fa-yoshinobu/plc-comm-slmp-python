@echo off
set PUBLISH_DIR=.\publish

echo ===================================================
echo [CI] Starting Python Quality Checks and CLI EXE Build...
echo ===================================================

echo [1/6] Running Ruff (Linting)...
python -m ruff check .
if %errorlevel% neq 0 (
    echo [ERROR] Ruff check failed.
    exit /b %errorlevel%
)

echo [2/6] Running Ruff (Formatting Check)...
python -m ruff format --check .
if %errorlevel% neq 0 (
    echo [ERROR] Code is not formatted.
    exit /b %errorlevel%
)

echo [3/6] Running Mypy (Type Checking core library)...
python -m mypy slmp
if %errorlevel% neq 0 (
    echo [ERROR] Mypy type check failed.
    exit /b %errorlevel%
)

echo [4/6] Validating public API docs coverage...
python scripts\check_public_api_docs.py
if %errorlevel% neq 0 (
    echo [ERROR] Public API docs coverage check failed.
    exit /b %errorlevel%
)

echo [5/6] Running Tests...
python -m unittest discover -s tests -v
if %errorlevel% neq 0 (
    echo [ERROR] Tests failed.
    exit /b %errorlevel%
)

echo [6/6] Building CLI Tool with PyInstaller...
python -m PyInstaller --onefile --noconfirm --distpath "%PUBLISH_DIR%" --name slmp slmp/cli.py
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    exit /b %errorlevel%
)

echo ===================================================
echo [SUCCESS] CI passed and CLI EXE published to:
echo %cd%\publish
echo ===================================================

