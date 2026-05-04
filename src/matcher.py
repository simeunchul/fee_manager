"""거래내역을 회비/기타입금/비용으로 자동 분류한다.

규칙:
  - 출금              → "비용" (카테고리는 적요/메모로 추천)
  - 입금 + 회원명 매칭 + 회비액 일치 → "회비"
  - 입금 + 회원명만 매칭             → "회비" (단, 금액 != 회비액 이면 미분류 표시 옵션)
  - 입금 + 매칭 실패                 → "기타입금"
"""
from __future__ import annotations

import re
from typing import Optional

from .models import Member, Settings, Transaction


_SPACES = re.compile(r"\s+")
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def normalize_name(name: str) -> str:
    """공백/괄호/특수문자 제거 후 소문자로. '김 철수' / '김철수(B조)' / '  김철수 ' → '김철수'."""
    if not name:
        return ""
    n = _PAREN.sub("", name)
    n = _SPACES.sub("", n)
    return n.strip().lower()


def classify(
    txs: list[Transaction],
    members: list[Member],
    settings: Settings,
) -> list[Transaction]:
    """거래 리스트를 받아 kind/matched_member/category 를 채운 새 리스트 반환.

    ``manual_match=True`` 인 거래는 ``matched_member`` 를 사용자가 지정한 값으로
    유지하고, ``kind`` 만 회비액 기준으로 다시 계산한다.
    """
    member_index = _build_member_index(members)
    fee = settings.monthly_fee
    out: list[Transaction] = []
    for t in txs:
        new_t = Transaction(
            txn_at=t.txn_at,
            counterparty=t.counterparty,
            deposit=t.deposit,
            withdraw=t.withdraw,
            balance=t.balance,
            memo=t.memo,
            kind=t.kind,
            matched_member=t.matched_member,
            category=t.category,
            manual_match=t.manual_match,
        )
        if new_t.is_withdraw:
            new_t.kind = "비용"
            # 자동 분류 결과는 매칭 클리어. 사용자가 수동 매칭한 출금
            # (예: "이 카카오페이 비용은 누가 결제") 은 그대로 보존.
            if not new_t.manual_match:
                new_t.matched_member = ""
            if not new_t.category:
                new_t.category = _guess_expense_category(new_t.memo, settings.expense_categories)
            out.append(new_t)
            continue

        # 입금 처리
        if new_t.manual_match:
            # 사용자가 지정한 매칭 보존. 단 그 회원이 활성 멤버인지만 가볍게 검증.
            member = member_index.get(normalize_name(new_t.matched_member))
        else:
            member = _match_member(new_t.counterparty, member_index)

        if member is None:
            new_t.kind = "기타입금"
            if not new_t.manual_match:
                new_t.matched_member = ""
        else:
            new_t.matched_member = member.name
            if fee == 0 or new_t.deposit == fee:
                new_t.kind = "회비"
            else:
                new_t.kind = "회비" if abs(new_t.deposit - fee) <= max(1000, fee * 0.1) else "기타입금"
        out.append(new_t)
    return out


def _build_member_index(members: list[Member]) -> dict[str, Member]:
    idx: dict[str, Member] = {}
    for m in members:
        if not m.active:
            continue
        idx[normalize_name(m.name)] = m
    return idx


def _match_member(counterparty: str, member_index: dict[str, Member]) -> Optional[Member]:
    if not counterparty:
        return None
    norm = normalize_name(counterparty)
    if not norm:
        return None
    if norm in member_index:
        return member_index[norm]
    # 부분 일치 (회원명이 보낸이 문자열 안에 포함된 경우)
    candidates = [m for k, m in member_index.items() if k and (k in norm or norm in k)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _guess_expense_category(memo: str, categories: list[str]) -> str:
    if not memo:
        return "기타"
    lowered = memo.lower()
    keyword_map = {
        "식대": ["식당", "음식", "밥", "점심", "저녁", "배달", "치킨", "피자", "카페", "스타벅스"],
        "임대료": ["임대", "월세", "전세", "관리비"],
        "소모품": ["문구", "마트", "다이소", "이마트", "쿠팡", "11번가"],
        "회식": ["회식", "주점", "호프", "노래방"],
    }
    for cat in categories:
        if cat in memo:
            return cat
        for kw in keyword_map.get(cat, []):
            if kw in lowered:
                return cat
    return "기타"
