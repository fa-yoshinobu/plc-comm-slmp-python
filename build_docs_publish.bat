@echo off
setlocal
set "DOCS_OUTPUT_DIR=docs"
echo [DOCS] Publishing SLMP Python Docs with MkDocs...
echo [DOCS] Output: %DOCS_OUTPUT_DIR%
set PYTHONPATH=.
python -m mkdocs build --site-dir "%DOCS_OUTPUT_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] mkdocs build failed.
    exit /b 1
)
echo [SUCCESS] Documentation published to %DOCS_OUTPUT_DIR%/
endlocal
