@echo off
cd /d "%~dp0"

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo .env 파일을 새로 만들었습니다.
    echo 메모장이 열리면 텔레그램 봇 토큰과 chat_id를 채운 뒤 저장하고 닫으세요.
    notepad ".env"
    echo.
    echo 값을 다 채우셨다면 이 파일을 다시 더블클릭해서 실행하세요.
    pause
    exit /b
)

echo 필요한 패키지를 확인합니다...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo 패키지 설치에 실패했습니다. Python/pip가 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

python local_loop.py
pause
