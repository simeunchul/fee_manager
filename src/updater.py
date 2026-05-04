"""GitHub Releases 기반 자동 업데이트 모듈.

흐름:
1. 앱 시작 시 ``check_for_update()`` 로 최신 release 조회 (캐시: 1시간)
2. 신버전 있으면 사이드바 배너 노출
3. 사용자가 "업데이트 받기" 클릭 → ``download_update()`` 가 zip 을
   ``%TEMP%`` 에 받고 프로젝트 루트에 ``.pending_update`` 마커 생성
4. 사용자가 streamlit 종료 후 ``run.bat`` 재실행
5. ``run.bat`` 이 마커를 보면 ``update.bat`` 호출해 zip 풀어 덮어쓰기
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


REPO_OWNER = "simeunchul"
REPO_NAME = "fee_manager"
RELEASE_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
PENDING_MARKER = PROJECT_ROOT / ".pending_update"
CHECK_CACHE = PROJECT_ROOT / ".update_check_cache.json"
CHECK_INTERVAL_SEC = 3600  # 1 hour


@dataclass
class UpdateInfo:
    current: str
    latest: str
    download_url: str
    notes: str = ""

    @property
    def is_newer(self) -> bool:
        return _semver_tuple(self.latest) > _semver_tuple(self.current)


def current_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except FileNotFoundError:
        return "0.0.0"


def _semver_tuple(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v)
    return tuple(int(n) for n in nums[:3]) or (0,)


def _read_cache() -> Optional[dict]:
    if not CHECK_CACHE.exists():
        return None
    try:
        with open(CHECK_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if time.time() - data.get("ts", 0) > CHECK_INTERVAL_SEC:
        return None
    return data


def _write_cache(latest: str, url: str, notes: str) -> None:
    try:
        with open(CHECK_CACHE, "w", encoding="utf-8") as f:
            json.dump({
                "ts": time.time(),
                "latest": latest,
                "url": url,
                "notes": notes,
            }, f, ensure_ascii=False)
    except Exception:
        pass


def check_for_update(force: bool = False) -> Optional[UpdateInfo]:
    """최신 릴리스를 조회한다. 네트워크 실패는 조용히 None 리턴."""
    cur = current_version()

    if not force:
        cache = _read_cache()
        if cache:
            return UpdateInfo(
                current=cur,
                latest=cache["latest"],
                download_url=cache["url"],
                notes=cache.get("notes", ""),
            )

    try:
        req = urllib.request.Request(
            RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "fee-manager"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    tag = (data.get("tag_name") or "").lstrip("v").strip()
    if not tag:
        return None

    asset_url = ""
    for asset in data.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(".zip") and "portable" in name:
            asset_url = asset.get("browser_download_url") or ""
            break
    if not asset_url:
        return None

    notes = data.get("body") or ""
    _write_cache(tag, asset_url, notes)
    return UpdateInfo(current=cur, latest=tag, download_url=asset_url, notes=notes)


def download_update(info: UpdateInfo, dest_dir: Optional[Path] = None) -> Path:
    """새 zip 을 다운로드하고 ``.pending_update`` 마커를 만든다.

    반환값: 다운로드된 zip 의 경로.
    """
    dest_dir = dest_dir or Path(os.environ.get("TEMP", str(PROJECT_ROOT)))
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / f"fee_manager_portable_{info.latest}.zip"

    req = urllib.request.Request(
        info.download_url,
        headers={"User-Agent": "fee-manager"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as f:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)

    PENDING_MARKER.write_text(
        json.dumps({
            "zip": str(zip_path),
            "from": info.current,
            "to": info.latest,
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return zip_path


def has_pending_update() -> bool:
    return PENDING_MARKER.exists()


def schedule_self_terminate(delay_sec: float = 3.0) -> None:
    """현재 프로세스(streamlit)를 잠시 뒤 강제 종료한다.

    run.bat 의 :LOOP 구조가 streamlit 종료를 감지해 .pending_update 마커를
    보고 update.bat 을 호출, 새 zip 적용 후 streamlit 을 재시작한다.
    UI 메시지를 사용자가 볼 시간을 위해 ``delay_sec`` 만큼 대기 후 죽인다.
    """
    import threading
    import time
    import os

    def _kill() -> None:
        time.sleep(delay_sec)
        os._exit(0)

    threading.Thread(target=_kill, daemon=True).start()


def consume_pending() -> Optional[dict]:
    """run.bat 이 호출하는 함수. 마커 내용을 읽어 반환하고 마커 삭제."""
    if not PENDING_MARKER.exists():
        return None
    try:
        data = json.loads(PENDING_MARKER.read_text(encoding="utf-8"))
    except Exception:
        data = None
    try:
        PENDING_MARKER.unlink()
    except Exception:
        pass
    return data


if __name__ == "__main__":
    # CLI: run.bat 이 ``python -m src.updater <command>`` 형태로 부른다.
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pending-zip":
        data = consume_pending()
        if data and data.get("zip"):
            sys.stdout.write(data["zip"])
            sys.exit(0)
        sys.exit(1)
    elif cmd == "version":
        sys.stdout.write(current_version())
        sys.exit(0)
    else:
        sys.stderr.write(f"unknown command: {cmd}\n")
        sys.exit(2)
