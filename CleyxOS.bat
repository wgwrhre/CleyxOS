@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [CLEYXOS] Creating Python 3.14 environment...
    py -3.14 -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [ERROR] Python 3.14 was not found. Install Python 3.14 and try again.
        pause
        exit /b 1
    )
)

"%VENV_PY%" -c "import rich, psutil, requests, prompt_toolkit, pygments, dns, PIL, qrcode, pycaw, screen_brightness_control" >nul 2>&1
if errorlevel 1 (
    echo [CLEYXOS] Installing required packages...
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

"%VENV_PY%" main.py
if errorlevel 1 pause
endlocal