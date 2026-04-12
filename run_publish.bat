@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -m ai_digest --publish
) else (
    python -m ai_digest --publish
)

echo.
pause
