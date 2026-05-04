"""구글 OAuth 인증.

TODO(배포 전 구현):
    1. credentials/SETUP_OAUTH.md 가이드대로 OAuth 클라이언트 ID 발급
    2. 다운받은 client_secret_*.json 을 credentials/client_secret.json 으로 저장
    3. 아래 get_gspread_client() 의 NotImplementedError 를 제거하고 주석 코드 활성화
    4. 첫 실행 시 브라우저가 열려 사용자가 본인 구글 계정으로 로그인
       → credentials/token.json 에 토큰이 저장되어 다음부턴 로그인 불필요
"""
from __future__ import annotations

from pathlib import Path

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent / "credentials"
CLIENT_SECRET_FILE = CREDENTIALS_DIR / "client_secret.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def get_gspread_client():
    """gspread.Client 를 반환. OAuth 발급 완료 후 활성화.

    참고 구현 (활성화 시 사용):

        import gspread
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRET_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return gspread.authorize(creds)
    """
    raise NotImplementedError(
        "OAuth 클라이언트가 발급되지 않았습니다. "
        "credentials/SETUP_OAUTH.md 가이드를 따라 발급한 뒤 "
        "src/auth.py 의 get_gspread_client() 를 활성화해주세요."
    )


def is_authenticated() -> bool:
    return CLIENT_SECRET_FILE.exists() and TOKEN_FILE.exists()
