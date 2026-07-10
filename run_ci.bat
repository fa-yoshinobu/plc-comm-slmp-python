@echo off
echo ===================================================
echo [CI] Starting Python quality checks...
echo ===================================================

echo [1/5] Running Ruff (Linting)...
python -m ruff check .
if %errorlevel% neq 0 (
    echo [ERROR] Ruff check failed.
    exit /b %errorlevel%
)

echo [2/5] Running Ruff (Formatting Check)...
python -m ruff format --check .
if %errorlevel% neq 0 (
    echo [ERROR] Code is not formatted.
    exit /b %errorlevel%
)

echo [3/5] Running Mypy (Type Checking core library)...
python -m mypy slmp
if %errorlevel% neq 0 (
    echo [ERROR] Mypy type check failed.
    exit /b %errorlevel%
)

echo [4/5] Validating public API docs coverage...
python scripts\check_public_api_docs.py
if %errorlevel% neq 0 (
    echo [ERROR] Public API docs coverage check failed.
    exit /b %errorlevel%
)

echo [5/5] Running Tests...
python -m unittest discover -s tests -v
if %errorlevel% neq 0 (
    echo [ERROR] Tests failed.
    exit /b %errorlevel%
)

echo ===================================================
echo [SUCCESS] CI checks passed. CLI tools are distributed as wheel console entry points.
echo ===================================================

