@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title JIEZI - View on Phone

set "PY1=C:\Users\Serein\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

echo.
echo   Starting local server for phone...
echo.

if exist "%PY1%" (
    "%PY1%" serve.py
    goto done
)

python serve.py
if errorlevel 1 (
    echo.
    echo   [X] Python not found. Please install Python 3 once.
)

:done
echo.
pause