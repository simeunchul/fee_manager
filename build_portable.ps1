# Build a portable Streamlit app bundle.
#
# 출력: dist\fee_manager_portable_<VERSION>.zip
#
# 사용:
#   powershell -ExecutionPolicy Bypass -File build_portable.ps1
#   powershell -ExecutionPolicy Bypass -File build_portable.ps1 -Bump patch
#   powershell -ExecutionPolicy Bypass -File build_portable.ps1 -Bump minor
#   powershell -ExecutionPolicy Bypass -File build_portable.ps1 -Bump major
#
# 처음 실행 시 ~150MB 다운로드 + 의존성 설치로 5~10분 걸립니다.
# 두 번째부터는 캐시된 _runtime/ 을 재활용해 1분 안에 zip만 다시 만듭니다.

param(
    [ValidateSet("none", "patch", "minor", "major")]
    [string]$Bump = "none"
)

$ErrorActionPreference = "Stop"

$PythonVersion = "3.11.9"
$EmbedZipUrl   = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$GetPipUrl     = "https://bootstrap.pypa.io/get-pip.py"

$Root        = $PSScriptRoot
$RuntimeDir  = Join-Path $Root "_runtime"
$BuildCache  = Join-Path $Root ".build_cache"
$DistDir     = Join-Path $Root "dist"
$VersionFile = Join-Path $Root "VERSION"

if (-not (Test-Path $VersionFile)) {
    Write-Error "VERSION 파일이 없습니다."
    exit 1
}
$Version = (Get-Content $VersionFile -Raw).Trim()

if ($Bump -ne "none") {
    if ($Version -notmatch '^(\d+)\.(\d+)\.(\d+)$') {
        Write-Error "VERSION 형식이 X.Y.Z 가 아닙니다: $Version"
        exit 1
    }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    $patch = [int]$Matches[3]
    switch ($Bump) {
        "major" { $major++; $minor = 0; $patch = 0 }
        "minor" { $minor++; $patch = 0 }
        "patch" { $patch++ }
    }
    $newVersion = "$major.$minor.$patch"
    Set-Content -Path $VersionFile -Value $newVersion -NoNewline
    Write-Host "==> Bumped VERSION: $Version -> $newVersion"
    $Version = $newVersion
}

Write-Host "==> Building fee_manager portable v$Version"

New-Item -ItemType Directory -Force -Path $BuildCache, $DistDir | Out-Null

# 1) 임베드 파이썬 다운로드 + 추출
$EmbedZip = Join-Path $BuildCache "python-embed-$PythonVersion.zip"
if (-not (Test-Path $EmbedZip)) {
    Write-Host "    downloading embeddable Python $PythonVersion..."
    Invoke-WebRequest -Uri $EmbedZipUrl -OutFile $EmbedZip -UseBasicParsing
}

if (Test-Path $RuntimeDir) {
    # 이미 셋업되어 있으면 재사용. 새로 만들고 싶으면 _runtime 폴더를 삭제하고 다시 실행.
    Write-Host "    reusing existing _runtime/ (delete it to rebuild from scratch)"
} else {
    Write-Host "    extracting Python embed -> _runtime/"
    Expand-Archive -Path $EmbedZip -DestinationPath $RuntimeDir -Force

    # 2) ._pth 수정해서 site-packages 활성화
    $PthFile = Get-ChildItem -Path $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $PthFile) { Write-Error "python._pth not found in embed runtime"; exit 1 }
    $pth = Get-Content $PthFile.FullName
    $pth = $pth | ForEach-Object {
        if ($_ -match '^\s*#\s*import site\s*$') { 'import site' } else { $_ }
    }
    if (-not ($pth -contains 'Lib\site-packages')) { $pth += 'Lib\site-packages' }
    Set-Content -Path $PthFile.FullName -Value $pth -Encoding ASCII

    # 3) get-pip.py 로 pip 설치
    $GetPip = Join-Path $BuildCache "get-pip.py"
    if (-not (Test-Path $GetPip)) {
        Write-Host "    downloading get-pip.py..."
        Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPip -UseBasicParsing
    }
    Write-Host "    installing pip into runtime..."
    & "$RuntimeDir\python.exe" $GetPip --no-warn-script-location

    # 4) 의존성 설치
    Write-Host "    installing requirements..."
    & "$RuntimeDir\python.exe" -m pip install --no-warn-script-location -r (Join-Path $Root "requirements.txt")
}

# 5) zip 패키징 — Python 에 위임. PowerShell 의 Copy-Item / Compress-Archive 둘 다
#    Windows MAX_PATH(260) 제한에 걸려 깊은 site-packages 경로 파일을 누락시키므로,
#    Python zipfile (\\?\ prefix 자동 적용) 로 source 에서 zip 으로 직접 한방에 처리.
Write-Host "==> Packaging zip..."

$AppFolderName = "fee_manager_$Version"
$ZipPath = Join-Path $DistDir "fee_manager_portable_$Version.zip"
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

$ZipScript = @"
import os
import sys
import zipfile

# Windows MAX_PATH (260) 우회를 위해 모든 fs 호출에 \\?\ prefix 사용.
# 이게 없으면 os.walk / open 이 깊은 site-packages 폴더에서 파일을 빠뜨림.
LP = '\\\\?\\'

def lp(path: str) -> str:
    p = os.path.abspath(path)
    return p if p.startswith(LP) else LP + p

def strip_lp(path: str) -> str:
    return path[len(LP):] if path.startswith(LP) else path

ROOT = r'$Root'
DST  = r'$ZipPath'
APP  = r'$AppFolderName'

INCLUDE_DIRS  = ['_runtime', 'src', 'pages', 'config']
INCLUDE_FILES = ['app.py', 'run.bat', 'update.bat', 'VERSION',
                 'requirements.txt', 'README.md']
EXCLUDE_DIRS  = {
    # 빌드/VCS
    '__pycache__', '.git', '.venv', 'data', '.build_cache', 'dist',
    # streamlit 의 AI agent SDK 템플릿 (가장 깊은 경로의 주범, 우리 앱과 무관)
    '.agents',
    # 'hello', 'tests', 'examples' 같은 일반명은 streamlit/패키지 내부 서브모듈명과
    # 충돌해서 제외하면 import 가 깨진다 (예: from streamlit.hello import ...).
    # 그래서 '.agents' 만 유지.
}
EXCLUDE_FILES = {'.pending_update', '.update_check_cache.json'}

print(f'packaging {DST}')
count = 0
with zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in INCLUDE_FILES:
        full = os.path.join(ROOT, f)
        if not os.path.isfile(lp(full)):
            continue
        zf.write(lp(full), os.path.join(APP, f))
        count += 1

    for d in INCLUDE_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(lp(base)):
            continue
        # os.walk 에 \\?\ prefix 경로를 주면 자식 경로도 \\?\ 가 유지됨.
        for cur_root, dirs, files in os.walk(lp(base)):
            dirs[:] = [x for x in dirs if x not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(cur_root, f)
                rel  = os.path.relpath(strip_lp(full), ROOT)
                arcname = os.path.join(APP, rel)
                zf.write(full, arcname)
                count += 1
                if count % 1000 == 0:
                    print(f'  {count} files...')

print(f'done: {count} files')
"@
$TempScript = Join-Path $BuildCache "_zip.py"
Set-Content -Path $TempScript -Value $ZipScript -Encoding UTF8
& "$RuntimeDir\python.exe" $TempScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python zip 생성 실패"
    exit 1
}
Remove-Item -Force $TempScript

# 사용자용 install.bat 도 zip 옆에 복사. zip + install.bat 두 파일을 묶어 배포.
$InstallSrc = Join-Path $Root "install.bat"
$InstallDst = Join-Path $DistDir "install.bat"
if (Test-Path $InstallSrc) {
    Copy-Item -Force -Path $InstallSrc -Destination $InstallDst
}

$Size = (Get-Item $ZipPath).Length / 1MB
Write-Host ""
Write-Host "==> DONE: $ZipPath  ($([Math]::Round($Size,1)) MB)"
Write-Host "    함께 배포할 파일: $InstallDst"
Write-Host "    GitHub Releases 에 두 파일을 첨부하세요."
