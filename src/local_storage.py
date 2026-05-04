from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pandas as pd

from .models import Member, Settings, Transaction
from .storage import Storage


def _resolve_data_dir() -> Path:
    """데이터 저장 폴더를 결정한다.

    기본은 사용자 홈의 ``.fee_manager`` 폴더. 환경변수
    ``FEE_MANAGER_DATA_DIR`` 로 위치를 강제할 수 있다 (테스트/이식 용).

    portable 배포 시 앱 폴더를 통째로 교체해도 데이터가 보존되도록
    프로젝트 디렉터리 바깥에 둔다.
    """
    override = os.environ.get("FEE_MANAGER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".fee_manager"


def _legacy_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def _migrate_legacy_if_needed(target: Path) -> None:
    """기존 프로젝트 내부 ``data/`` 폴더 사용자를 위한 1회성 이전.

    target 이 비어 있고 legacy 가 존재하면 파일들을 옮긴다.
    legacy 폴더 자체는 남겨두되 안에 있는 파일만 이동.
    """
    legacy = _legacy_data_dir()
    if not legacy.exists() or not legacy.is_dir():
        return
    # target 에 이미 데이터가 있으면 건드리지 않음
    if any(target.glob("*.csv")) or any(target.glob("*.json")):
        return
    target.mkdir(parents=True, exist_ok=True)
    moved = False
    for fname in ("members.csv", "transactions.csv", "settings.json"):
        src = legacy / fname
        dst = target / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            moved = True
    if moved:
        # 이전 완료 표시 — legacy 파일을 .migrated 로 rename 해서 두 번 옮기지 않게
        for fname in ("members.csv", "transactions.csv", "settings.json"):
            src = legacy / fname
            if src.exists():
                try:
                    src.rename(legacy / f"{fname}.migrated")
                except Exception:
                    pass


DATA_DIR = _resolve_data_dir()
MEMBERS_CSV = DATA_DIR / "members.csv"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"
SETTINGS_JSON = DATA_DIR / "settings.json"


class LocalStorage(Storage):
    """사용자 홈의 ``.fee_manager/`` 폴더에 CSV/JSON 으로 저장한다."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _migrate_legacy_if_needed(DATA_DIR)

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
            "memo", "kind", "matched_member", "category", "manual_match",
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
