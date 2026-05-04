"""은행 거래내역 .xls/.xlsx 파일을 표준 Transaction 리스트로 변환한다.

사용:
    txs = parse_bank_file("kb_202604.xlsx", bank="auto")
    txs = parse_bank_file("이상한파일.xlsx", bank="generic",
                          column_overrides={"counterparty": "보낸이름"})
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from .models import Transaction


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "bank_columns.yaml"


def load_bank_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["banks"]


def list_supported_banks() -> list[tuple[str, str]]:
    cfg = load_bank_config()
    return [(k, v["display_name"]) for k, v in cfg.items()]


def detect_bank(file_path: str | Path) -> Optional[str]:
    """파일 첫 몇 줄을 읽어 은행을 추정. 못 찾으면 None."""
    cfg = load_bank_config()
    try:
        df = _read_excel_raw(file_path, header=None, nrows=15)
    except Exception:
        return None
    blob = " ".join(df.astype(str).fillna("").to_numpy().ravel().tolist())
    for bank_key, bank_cfg in cfg.items():
        for kw in bank_cfg.get("auto_detect_keywords", []) or []:
            if kw and kw in blob:
                return bank_key
    return None


def parse_bank_file(
    file_path: str | Path,
    bank: str = "auto",
    column_overrides: Optional[dict[str, str]] = None,
) -> list[Transaction]:
    """은행 엑셀 파일을 읽어 Transaction 리스트로 변환.

    bank='auto' 면 자동 감지, 실패 시 'generic' 으로 폴백.
    column_overrides 로 특정 컬럼명만 강제 지정 가능.
    """
    file_path = Path(file_path)
    if bank == "auto":
        bank = detect_bank(file_path) or "generic"

    cfg = load_bank_config()
    if bank not in cfg:
        raise ValueError(f"지원하지 않는 은행 키: {bank}")

    df = _read_excel_with_header_detection(file_path, cfg[bank]["columns"])
    df = _normalize_columns(df, cfg[bank]["columns"], column_overrides or {})
    return _rows_to_transactions(df)


def _read_excel_raw(path: Path, header=None, nrows=None) -> pd.DataFrame:
    """xls/xlsx 모두 처리."""
    suffix = path.suffix.lower()
    if suffix == ".xls":
        return pd.read_excel(path, header=header, nrows=nrows, engine="xlrd")
    return pd.read_excel(path, header=header, nrows=nrows, engine="openpyxl")


def _read_excel_with_header_detection(path: Path, col_candidates: dict) -> pd.DataFrame:
    """엑셀 파일에서 헤더 행 위치를 자동으로 찾아 DataFrame 반환.

    은행 파일은 종종 상단 몇 행이 "조회기간/계좌번호" 같은 메타정보고
    실제 표는 5~10행쯤부터 시작. 후보 컬럼명이 가장 많이 일치하는 행을 헤더로 채택.
    """
    raw = _read_excel_raw(path, header=None)
    flat_candidates = set()
    for vs in col_candidates.values():
        flat_candidates.update(vs)

    best_row, best_hits = 0, -1
    for i in range(min(20, len(raw))):
        row_values = [str(v).strip() for v in raw.iloc[i].tolist()]
        hits = sum(1 for v in row_values if v in flat_candidates)
        if hits > best_hits:
            best_row, best_hits = i, hits

    if best_hits <= 0:
        return _read_excel_raw(path, header=0)

    df = _read_excel_raw(path, header=best_row)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def _normalize_columns(
    df: pd.DataFrame,
    col_candidates: dict[str, list[str]],
    overrides: dict[str, str],
) -> pd.DataFrame:
    """은행별 컬럼명 → 내부 표준 컬럼명으로 변환."""
    rename_map = {}
    for std_col, candidates in col_candidates.items():
        if std_col in overrides and overrides[std_col] in df.columns:
            rename_map[overrides[std_col]] = std_col
            continue
        for c in candidates:
            if c in df.columns:
                rename_map[c] = std_col
                break

    df = df.rename(columns=rename_map)

    for col in ("txn_at", "counterparty", "deposit", "withdraw", "balance", "memo"):
        if col not in df.columns:
            df[col] = None

    return df[["txn_at", "counterparty", "deposit", "withdraw", "balance", "memo"]]


def _rows_to_transactions(df: pd.DataFrame) -> list[Transaction]:
    txs: list[Transaction] = []
    for _, row in df.iterrows():
        txn_at = _coerce_datetime(row["txn_at"])
        if txn_at is None:
            continue
        deposit = _coerce_int(row["deposit"])
        withdraw = _coerce_int(row["withdraw"])
        if deposit == 0 and withdraw == 0:
            continue
        balance = _coerce_int(row["balance"], allow_none=True)
        txs.append(Transaction(
            txn_at=txn_at,
            counterparty=_clean_str(row["counterparty"]),
            deposit=deposit,
            withdraw=withdraw,
            balance=balance,
            memo=_clean_str(row["memo"]),
        ))
    return txs


def _coerce_datetime(v) -> Optional[datetime]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
        "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y.%m.%d",
        "%Y%m%d%H%M%S", "%Y%m%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None


_NUM_RE = re.compile(r"[^\d\-]")


def _coerce_int(v, allow_none: bool = False) -> Optional[int] | int:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None if allow_none else 0
    if isinstance(v, (int,)):
        return int(v)
    if isinstance(v, float):
        return int(v)
    s = _NUM_RE.sub("", str(v).strip())
    if not s or s == "-":
        return None if allow_none else 0
    try:
        return int(s)
    except ValueError:
        return None if allow_none else 0


def _clean_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()
