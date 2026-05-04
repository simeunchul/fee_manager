"""읽기/쓰기 시점에 거래 분류를 항상 최신 상태로 유지하기 위한 얇은 래퍼.

스토리지에 저장된 ``kind``/``matched_member``/``category`` 는 분류 시점
스냅샷이라, 회비 금액이나 회원 명단이 바뀌면 stale 해진다.
모든 화면이 이 모듈을 거쳐 거래를 가져오면 항상 일관된 결과가 나온다.
"""
from __future__ import annotations

from src import matcher
from src.models import Transaction
from src.storage import Storage


def load_classified_transactions(storage: Storage) -> list[Transaction]:
    """저장된 거래를 읽되, 항상 현재 settings/members 기준으로 재분류해 반환."""
    txs = storage.list_transactions()
    if not txs:
        return txs
    members = storage.list_members()
    settings = storage.get_settings()
    return matcher.classify(txs, members, settings)


def reclassify_and_save(storage: Storage) -> int:
    """저장소의 모든 거래를 재분류한 결과를 영구 저장한다.

    설정/회원 변경 직후 호출하면 외부 도구(예: CSV 직접 열기) 에서도
    최신 분류가 보인다. 변경된 건수를 리턴.
    """
    txs = storage.list_transactions()
    if not txs:
        return 0
    members = storage.list_members()
    settings = storage.get_settings()
    new = matcher.classify(txs, members, settings)
    changed = sum(
        1 for old, fresh in zip(txs, new)
        if (old.kind, old.matched_member, old.category)
        != (fresh.kind, fresh.matched_member, fresh.category)
    )
    if changed:
        storage.replace_transactions(new)
    return changed
