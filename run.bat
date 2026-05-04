@echo off
cd /d "%~dp0"

set "PY=%~dp0_runtime\python.exe"
if not exist "%PY%" (
    echo.
    echo [오류] %PY% 를 찾을 수 없습니다.
    echo portable zip 을 다시 풀어 사용해주세요.
    echo.
    pause
    exit /b 1
)

echo.
echo ====== 회비관리 시작 ======
echo (이 검정 창은 사용 중 닫지 마세요. 종료하려면 Ctrl+C 두 번)
echo.

:LOOP
if exist ".pending_update" (
    echo.
    echo ====== 새 버전 적용 중 ======
    call update.bat
    if errorlevel 1 (
        echo.
        echo [경고] 업데이트 적용에 실패했습니다. 기존 버전으로 계속 진행합니다.
        echo.
    ) else (
        echo.
        echo 새 버전 적용 완료. streamlit 을 다시 시작합니다.
        echo 브라우저를 새로고침해주세요.
        echo.
    )
)

"%PY%" -m streamlit run app.py

rem streamlit 이 종료된 뒤에 마커가 있으면 (사용자가 in-app 업데이트 클릭한 경우)
rem 위로 돌아가 update.bat 적용 후 streamlit 재시작.
if exist ".pending_update" goto LOOP

rem 마커가 없으면 사용자가 정상 종료한 것이므로 창을 닫는다.
exit /b 0
