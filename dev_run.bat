@echo off
cd /d "%~dp0"

set "PY=%~dp0_runtime\python.exe"
if not exist "%PY%" (
    echo.
    echo [오류] %PY% 가 없습니다.
    echo build_portable.ps1 을 한 번 실행해 _runtime/ 을 빌드한 뒤 다시 시도해주세요.
    echo.
    pause
    exit /b 1
)

echo.
echo ====== dev streamlit 시작 (소스 직접 실행) ======
echo  - 소스 폴더 : %~dp0
echo  - 접속 주소 : http://localhost:8503
echo  - portable 과 포트 분리 (8503) 라 동시 실행 가능
echo  - 코드 수정 시 streamlit 이 자동 감지 -> 브라우저 새로고침
echo  (이 검정 창은 사용 중 닫지 마세요)
echo.

"%PY%" -m streamlit run app.py --server.port 8503

echo.
echo ====== streamlit 이 종료되었습니다 ======
echo 위에 에러 메시지가 있으면 그걸 보고 원인 파악 가능.
echo (정상 종료 시엔 그냥 Ctrl+C 누른 결과)
echo.
pause
