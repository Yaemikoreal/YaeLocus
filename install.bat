@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    YaeLocus Installer
echo ========================================
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo Checking pip version...
python -m pip install --upgrade pip -q 2>nul

echo Installing...
pip install -e . --no-warn-script-location -q

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Installation failed
    echo Try: pip install --upgrade pip
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Usage:
echo   python -m geocode.cli --help
echo   python -m geocode.cli geocode "address"
echo   python -m geocode.cli doctor
echo.
echo Or run directly:
echo   python run.py -i data\addresses.xlsx
echo.
pause