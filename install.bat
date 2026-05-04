@echo off
setlocal

cd /d "%~dp0"

set "ZIP="
for /f "delims=" %%i in ('dir /b /o-n "fee_manager_portable_*.zip" 2^>nul') do (
    if not defined ZIP set "ZIP=%%i"
)

if not defined ZIP (
    echo [오류] 같은 폴더에 fee_manager_portable_*.zip 가 없습니다.
    echo zip 파일과 install.bat 을 같은 폴더에 두고 실행해주세요.
    echo.
    pause
    exit /b 1
)

set "DEST=%USERPROFILE%\fee_manager"

echo.
echo ============================================
echo   회비관리 프로그램 설치
echo ============================================
echo   사용할 zip: %ZIP%
echo   설치 위치 : %DEST%
echo ============================================
echo.

if exist "%DEST%" (
    echo 이미 설치된 폴더가 있습니다: %DEST%
    set /p answer="기존 설치를 덮어쓸까요? (y/n): "
    if /i not "%answer%"=="y" (
        echo 설치를 취소했습니다.
        pause
        exit /b 0
    )
    echo 기존 폴더 삭제 중...
    rd /s /q "%DEST%"
)

echo.
echo [1/3] 압축 풀기...
powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0%ZIP%', '%USERPROFILE%')"
if errorlevel 1 (
    echo [오류] 압축 풀기 실패.
    echo Windows 의 Long Path Support 가 꺼져 있거나 백신이 차단했을 수 있습니다.
    pause
    exit /b 1
)

rem zip 안엔 fee_manager_<버전>\ 폴더가 들어있어 %USERPROFILE%\fee_manager_X.Y.Z 로 풀림
rem -> %USERPROFILE%\fee_manager 로 rename
for /d %%d in ("%USERPROFILE%\fee_manager_*") do (
    ren "%%d" "fee_manager"
    goto :renamed
)
:renamed

if not exist "%DEST%\run.bat" (
    echo [오류] 압축 풀기는 됐는데 %DEST%\run.bat 이 없습니다.
    echo 폴더 구조를 확인해주세요: %DEST%
    pause
    exit /b 1
)

echo.
echo [2/3] 바탕화면 바로가기 생성...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$([Environment]::GetFolderPath('Desktop'))\회비관리.lnk\"); $s.TargetPath='%DEST%\run.bat'; $s.WorkingDirectory='%DEST%'; $s.IconLocation='%DEST%\_runtime\python.exe,0'; $s.Save()"

echo.
echo [3/3] 완료!
echo.
echo ============================================
echo   설치 완료 - 바탕화면의 "회비관리" 더블클릭
echo ============================================
echo   설치 위치: %DEST%
echo ============================================
echo.
pause
