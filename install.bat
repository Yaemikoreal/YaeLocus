@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo.
echo  ============================================
echo     YaeLocus v1.5.0 - 一键安装脚本 (Windows)
echo  ============================================
echo.

cd /d "%~dp0"

:: ── 1. 检查 Python ──
set PYTHON=
for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON=%%i
if "%PYTHON%"=="" (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 版本检查
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER%

if "%PYVER%" LSS "3.8" (
    echo [ERROR] Python 版本需要 >= 3.8，当前为 %PYVER%
    pause
    exit /b 1
)

:: ── 2. 创建虚拟环境 ──
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [*] 创建虚拟环境 .venv ...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
) else (
    echo [OK] 虚拟环境已存在
)

:: 激活
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [ERROR] 虚拟环境激活失败
    pause
    exit /b 1
)

:: ── 3. 升级 pip ──
echo.
echo [*] 升级 pip ...
python -m pip install --upgrade pip -q 2>nul

:: ── 4. 安装依赖 ──
echo [*] 安装 YaeLocus 及依赖 ...
pip install -e . -q 2>nul

if !errorlevel! neq 0 (
    echo.
    echo [WARN] 基础安装完成，但可能有非关键警告
)

:: 安装 AI 支持
echo [*] 安装 AI 支持依赖 ...
pip install "httpx>=0.27.0" -q 2>nul

:: 安装 Web GUI 支持
echo [*] 安装 Web GUI 支持 ...
pip install fastapi uvicorn python-multipart -q 2>nul

:: ── 5. 验证 ──
echo.
echo [*] 验证安装 ...
.venv\Scripts\python.exe -m geocode.cli --help >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] 安装验证失败
    pause
    exit /b 1
)
echo [OK] 安装验证成功

:: ── 6. 创建快捷方式 ──
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%" (
    echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\create_shortcut.vbs"
    echo sLinkFile = "%DESKTOP%\YaeLocus Web.lnk" >> "%TEMP%\create_shortcut.vbs"
    echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\create_shortcut.vbs"
    echo oLink.TargetPath = "%~dp0.venv\Scripts\python.exe" >> "%TEMP%\create_shortcut.vbs"
    echo oLink.Arguments = "-m geocode.cli serve" >> "%TEMP%\create_shortcut.vbs"
    echo oLink.WorkingDirectory = "%~dp0" >> "%TEMP%\create_shortcut.vbs"
    echo oLink.Description = "YaeLocus Web GUI" >> "%TEMP%\create_shortcut.vbs"
    echo oLink.Save >> "%TEMP%\create_shortcut.vbs"
    cscript //nologo "%TEMP%\create_shortcut.vbs" >nul 2>&1
    del "%TEMP%\create_shortcut.vbs" >nul 2>&1
    echo [OK] 桌面快捷方式已创建
)

:: ── 7. 运行诊断 ──
echo.
echo [*] 运行环境诊断 ...
.venv\Scripts\python.exe -m geocode.cli doctor 2>nul

:: ── 8. 完成 ──
echo.
echo  ============================================
echo     安装完成!
echo  ============================================
echo.
echo  快速开始:
echo    yaelocus serve         启动 Web 图形界面（推荐）
echo    yaelocus config         配置 API 密钥
echo    yaelocus geocode "地址" 单地址编码
echo    yaelocus run -i data\清单.xlsx  批量处理
echo.
echo  桌面快捷方式 "YaeLocus Web" 可一键启动 Web 界面
echo.

set /p START_NOW="是否现在启动 Web 界面? [y/N] "
if /i "%START_NOW%"=="y" (
    start .venv\Scripts\python.exe -m geocode.cli serve
)
pause
