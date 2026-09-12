@echo off
cd /d "%~dp0"

python setup_env.py
if errorlevel 1 (
    pause
    exit /b
)

python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo Package install failed. Make sure Python and pip are installed correctly.
    pause
    exit /b 1
)

python local_loop.py
pause
