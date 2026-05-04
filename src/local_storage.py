from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import Member, Settings, Transaction
from .storage import Storage


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MEMBERS_CSV = DATA_DIR / "members.csv"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"
SETTINGS_JSON = DATA_DIR / "settings.json"


class LocalStorage(Storage):
    """data/ 폴더의 CSV/JSON 파일에 모든 데이터를 저장한다."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # -------- members --------
    def list_members(self) -> list[Member]:
        if not MEMBERS_CSV.exists():
            return []
        df = pd.read_csv(MEMBERS_CSV, dtype=str).fillna("")
        if df.empty:
            return []
        members = []
        for _, row in df.iterrows():
            members.append(Member.from_dict({
                "name": row["name"],
                "joined_on": row["joined_on"],
                "active": row.get("active", "True") in ("True", "true", "1", "TRUE"),
                "contact": row.get("contact", ""),
                "note": row.get("note", ""),
            }))
        return sorted(members, key=lambda m: (not m.active, m.name))

    def upsert_member(self, member: Member) -> None:
        members = {m.name: m for m in self.list_members()}
        members[member.name] = member
        self._write_members(list(members.values()))

    def delete_member(self, name: str) -> None:
        members = [m for m in self.list_members() if m.name != name]
        self._write_members(members)

    def _write_members(self, members: list[Member]) -> None:
        rows = [m.to_dict() for m in members]
        df = pd.DataFrame(rows, columns=["name", "joined_on", "active", "contact", "note"])
        df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # -------- transactions --------
    def list_transactions(self) -> list[Transaction]:
        if not TRANSACTIONS_CSV.exists():
            return []
        df = pd.read_csv(TRANSACTIONS_CSV, dtype=str).fillna("")
        if df.empty:
            return []
        txs = []
        for _, row in df.iterrows():
            try:
                txs.append(Transaction.from_dict(row.to_dict()))
            except Exception:
                continue
        return sorted(txs, key=lambda t: t.txn_at)

    def add_transactions(self, txs: list[Transaction]) -> int:
        existing = self.list_transactions()
        seen = {self._tx_key(t) for t in existing}
        added = [t for t in txs if self._tx_key(t) not in seen]
        if not added:
            return 0
        self._write_transactions(existing + added)
        return len(added)

    def replace_transactions(self, txs: list[Transaction]) -> None:
        self._write_transactions(txs)

    def _write_transactions(self, txs: list[Transaction]) -> None:
        rows = [t.to_dict() for t in txs]
        df = pd.DataFrame(rows, columns=[
            "txn_at", "counterparty", "deposit", "withdraw", "balance",
            "memo", "kind", "matched_member", "category",
        ])
        df.to_csv(TRANSACTIONS_CSV, index=False, encoding="utf-8-sig")

    @staticmethod
    def _tx_key(t: Transaction) -> tuple:
        return (t.txn_at.isoformat(), t.counterparty, t.deposit, t.withdraw, t.memo)

    # -------- settings --------
    def get_settings(self) -> Settings:
        if not SETTINGS_JSON.exists():
            s = Settings()
            self.save_settings(s)
            return s
        with open(SETTINGS_JSON, "r", encoding="utf-8") as f:
            return Settings.from_dict(json.load(f))

    def save_settings(self, settings: Settings) -> None:
        with open(SETTINGS_JSON, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, ensure_ascii=False, indent=2)
