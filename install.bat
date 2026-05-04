@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   회비관리 프로그램 설치 (최초 1회)
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo.
    echo Python 설치 방법:
    echo   1. https://www.python.org/downloads/ 접속
    echo   2. "Download Python 3.11.x" 클릭
    echo   3. 설치 시 "Add python.exe to PATH" 체크 필수
    echo   4. 설치 완료 후 이 파일을 다시 더블클릭
    echo.
    pause
    exit /b 1
)

echo [1/2] 가상환경 생성 중...
if not exist .venv (
    python -m venv .venv
)

echo [2/2] 필요한 패키지 설치 중... (약 2~3분 소요)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

echo.
echo ========================================
echo   설치 완료!
echo   이제 run.bat 을 더블클릭하세요.
echo ========================================
echo.
pause
