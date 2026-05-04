from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Member, Settings, Transaction


class Storage(ABC):
    """회원/거래/설정 데이터를 일관된 인터페이스로 다룬다.

    현재 구현체: ``LocalStorage`` (사용자 홈의 ``.fee_manager/`` 폴더에 CSV/JSON).
    """

    @abstractmethod
    def list_members(self) -> list[Member]: ...

    @abstractmethod
    def upsert_member(self, member: Member) -> None: ...

    @abstractmethod
    def delete_member(self, name: str) -> None: ...

    @abstractmethod
    def list_transactions(self) -> list[Transaction]: ...

    @abstractmethod
    def add_transactions(self, txs: list[Transaction]) -> int:
        """이미 있는(같은 일시+상대방+금액) 거래는 무시. 새로 추가된 건수 반환."""

    @abstractmethod
    def replace_transactions(self, txs: list[Transaction]) -> None:
        """전체 거래내역을 교체 (재분류 후 일괄 저장 등에 사용)."""

    @abstractmethod
    def get_settings(self) -> Settings: ...

    @abstractmethod
    def save_settings(self, settings: Settings) -> None: ...


def get_storage(backend: str = "local"):
    if backend == "local":
        from .local_storage import LocalStorage
        return LocalStorage()
    raise ValueError(f"알 수 없는 storage backend: {backend}")
