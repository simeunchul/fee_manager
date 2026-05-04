from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional, Literal


TxKind = Literal["회비", "기타입금", "비용", "미분류"]


@dataclass
class Member:
    name: str
    joined_on: date
    active: bool = True
    contact: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["joined_on"] = self.joined_on.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Member":
        return cls(
            name=str(d["name"]).strip(),
            joined_on=_parse_date(d["joined_on"]),
            active=bool(d.get("active", True)),
            contact=str(d.get("contact", "")),
            note=str(d.get("note", "")),
        )


@dataclass
class Transaction:
    txn_at: datetime
    counterparty: str
    deposit: int
    withdraw: int
    balance: Optional[int]
    memo: str
    kind: TxKind = "미분류"
    matched_member: str = ""
    category: str = ""
    # 사용자가 회원매칭을 수동으로 변경한 거래는 자동 재매칭 대상에서 제외.
    # (counterparty 가 정규 회원명과 안 맞아도 사용자가 "이 송금은 누구"라고
    # 지정한 결과를 보존하기 위함.)
    manual_match: bool = False

    @property
    def is_deposit(self) -> bool:
        return self.deposit > 0

    @property
    def is_withdraw(self) -> bool:
        return self.withdraw > 0

    @property
    def amount(self) -> int:
        return self.deposit if self.is_deposit else -self.withdraw

    @property
    def month_key(self) -> str:
        return self.txn_at.strftime("%Y-%m")

    def to_dict(self) -> dict:
        return {
            "txn_at": self.txn_at.isoformat(),
            "counterparty": self.counterparty,
            "deposit": self.deposit,
            "withdraw": self.withdraw,
            "balance": self.balance,
            "memo": self.memo,
            "kind": self.kind,
            "matched_member": self.matched_member,
            "category": self.category,
            "manual_match": self.manual_match,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        manual = d.get("manual_match", False)
        if isinstance(manual, str):
            manual = manual.strip().lower() in ("true", "1", "yes", "y")
        return cls(
            txn_at=_parse_datetime(d["txn_at"]),
            counterparty=str(d.get("counterparty", "")),
            deposit=int(d.get("deposit") or 0),
            withdraw=int(d.get("withdraw") or 0),
            balance=int(d["balance"]) if d.get("balance") not in (None, "") else None,
            memo=str(d.get("memo", "")),
            kind=str(d.get("kind", "미분류")),  # type: ignore[arg-type]
            matched_member=str(d.get("matched_member", "")),
            category=str(d.get("category", "")),
            manual_match=bool(manual),
        )


@dataclass
class Settings:
    monthly_fee: int = 50000
    fee_due_day: int = 10
    expense_categories: list[str] = field(
        default_factory=lambda: ["식대", "임대료", "소모품", "회식", "기타"]
    )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        return cls(
            monthly_fee=int(d.get("monthly_fee", 50000)),
            fee_due_day=int(d.get("fee_due_day", 10)),
            expense_categories=list(d.get("expense_categories")
                                    or ["식대", "임대료", "소모품", "회식", "기타"]),
        )


def _parse_date(v) -> date:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"날짜 형식을 알 수 없습니다: {v!r}")


def _parse_datetime(v) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime.combine(v, datetime.min.time())
    s = str(v).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y.%m.%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"날짜시간 형식을 알 수 없습니다: {v!r}")
