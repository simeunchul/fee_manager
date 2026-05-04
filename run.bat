@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   회비관리 프로그램 실행 중...
echo ========================================
echo.

if not exist .venv (
    echo [오류] 설치가 안 되어 있습니다.
    echo install.bat 을 먼저 더블클릭하세요.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo 잠시 후 브라우저가 자동으로 열립니다.
echo (이 검정 창은 사용 중 닫지 마세요)
echo.
streamlit run app.py
