from __future__ import annotations

from .models import Member, Settings, Transaction
from .storage import Storage


class GoogleSheetsStorage(Storage):
    """구글 스프레드시트에 모든 데이터를 저장하는 백엔드.

    TODO(인증):
      OAuth 클라이언트 ID 발급 후 src/auth.py 의 get_gspread_client() 가
      gspread.Client 를 반환하도록 구현되면 이 클래스가 동작합니다.
      자세한 발급 절차는 credentials/SETUP_OAUTH.md 참고.

    시트 구조 (프로그램이 첫 실행 시 자동 생성):
      - members        : name, joined_on, active, contact, note
      - transactions   : txn_at, counterparty, deposit, withdraw, balance,
                         memo, kind, matched_member, category
      - settings       : key, value (단일 행씩)
    """

    SHEET_MEMBERS = "members"
    SHEET_TRANSACTIONS = "transactions"
    SHEET_SETTINGS = "settings"

    def __init__(self) -> None:
        from .auth import get_gspread_client  # 지연 import (인증 없이도 패키지 import 가능)
        self._gc = get_gspread_client()
        self._sh = None  # 첫 호출 시 _open() 으로 시트 핸들 캐싱

    # 아래 메서드들은 인증이 활성화되면 즉시 동작하도록 시그니처를 맞춰둠.
    # 실제 구현은 OAuth 발급 완료 후 진행.

    def list_members(self) -> list[Member]:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def upsert_member(self, member: Member) -> None:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def delete_member(self, name: str) -> None:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def list_transactions(self) -> list[Transaction]:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def add_transactions(self, txs: list[Transaction]) -> int:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def replace_transactions(self, txs: list[Transaction]) -> None:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def get_settings(self) -> Settings:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")

    def save_settings(self, settings: Settings) -> None:
        raise NotImplementedError("OAuth 발급 후 활성화. credentials/SETUP_OAUTH.md 참고.")
