@echo off
echo [DOCS] Building SLMP Python Docs with MkDocs...
set PYTHONPATH=.
python -m mkdocs build
if %errorlevel% neq 0 (
    echo [ERROR] mkdocs build failed.
    exit /b 1
)
echo [SUCCESS] Documentation built to docs/



