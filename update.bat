@echo off
cd /d "%~dp0"

set "PY=%~dp0_runtime\python.exe"
if not exist "%PY%" set "PY=python"

rem 보류 zip 경로 가져오기 + 마커 삭제
set "ZIP_PATH="
for /f "usebackq delims=" %%i in (`"%PY%" -m src.updater pending-zip 2>nul`) do set "ZIP_PATH=%%i"

if not defined ZIP_PATH (
    echo 보류 업데이트 정보가 없습니다.
    exit /b 1
)
if not exist "%ZIP_PATH%" (
    echo 업데이트 zip 을 찾을 수 없음: %ZIP_PATH%
    exit /b 1
)

set "TMPDIR=%TEMP%\fee_manager_update_%RANDOM%"
mkdir "%TMPDIR%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%TMPDIR%' -Force"
if errorlevel 1 (
    echo zip 추출 실패
    rd /s /q "%TMPDIR%" 2>nul
    exit /b 1
)

rem zip 안에 fee_manager_X.Y.Z\ 폴더가 들어있다고 가정 - 첫 폴더를 소스로 사용
set "SRC_DIR="
for /d %%d in ("%TMPDIR%\*") do (
    if not defined SRC_DIR set "SRC_DIR=%%d"
)
if not defined SRC_DIR (
    echo zip 구조가 예상과 다릅니다.
    rd /s /q "%TMPDIR%" 2>nul
    exit /b 1
)

rem robocopy: 현재 폴더로 동기화. run.bat / update.bat 은 자기 자신이라 잠금 가능 - 제외.
rem __pycache__, .git 같은 것도 제외.
robocopy "%SRC_DIR%" "%~dp0" /E /R:1 /W:1 /XF run.bat update.bat /XD __pycache__ .git .venv >nul
set "RC=%ERRORLEVEL%"

rem robocopy 종료코드 0~7 은 정상 (8 이상이 실제 에러)
if %RC% GEQ 8 (
    echo robocopy 실패 (코드 %RC%)
    rd /s /q "%TMPDIR%" 2>nul
    exit /b 1
)

rd /s /q "%TMPDIR%" 2>nul
del /q "%ZIP_PATH%" 2>nul

echo 업데이트 완료.
exit /b 0
