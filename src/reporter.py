"""분류된 거래내역을 집계해 리포트(미납자/수입지출/월별현황)를 만든다."""
from __future__ import annotations

import io
from datetime import date
from typing import Iterable

import pandas as pd

from .models import Member, Transaction


def month_keys(txs: Iterable[Transaction]) -> list[str]:
    months = sorted({t.month_key for t in txs})
    return months


def payment_matrix(
    txs: list[Transaction],
    members: list[Member],
    months: list[str] | None = None,
) -> pd.DataFrame:
    """행=회원, 열=월, 값='✓'/'✗' 의 매트릭스. 비활성 회원 제외."""
    active_members = [m.name for m in members if m.active]
    months = months or month_keys(txs)

    paid: dict[tuple[str, str], int] = {}
    for t in txs:
        if t.kind != "회비" or not t.matched_member:
            continue
        key = (t.matched_member, t.month_key)
        paid[key] = paid.get(key, 0) + t.deposit

    df = pd.DataFrame(index=active_members, columns=months, dtype=object)
    df.index.name = "회원"
    for name in active_members:
        for m in months:
            df.loc[name, m] = "✓" if paid.get((name, m), 0) > 0 else "✗"
    return df


def unpaid_members(
    txs: list[Transaction],
    members: list[Member],
    month_key: str,
) -> list[Member]:
    """특정 월에 회비를 안 낸 활성 회원 리스트."""
    paid_names = {
        t.matched_member for t in txs
        if t.kind == "회비" and t.month_key == month_key and t.matched_member
    }
    return [m for m in members if m.active and m.name not in paid_names]


def monthly_summary(txs: list[Transaction]) -> pd.DataFrame:
    """월별 수입/지출/순합계."""
    if not txs:
        return pd.DataFrame(columns=["월", "회비수입", "기타입금", "비용지출", "순합계"])
    rows = []
    for m in month_keys(txs):
        month_txs = [t for t in txs if t.month_key == m]
        fee_in = sum(t.deposit for t in month_txs if t.kind == "회비")
        other_in = sum(t.deposit for t in month_txs if t.kind == "기타입금")
        out = sum(t.withdraw for t in month_txs if t.kind == "비용")
        rows.append({
            "월": m,
            "회비수입": fee_in,
            "기타입금": other_in,
            "비용지출": out,
            "순합계": fee_in + other_in - out,
        })
    return pd.DataFrame(rows)


def expense_breakdown(txs: list[Transaction], month_key: str | None = None) -> pd.DataFrame:
    """비용을 카테고리별로 합산."""
    pool = [t for t in txs if t.kind == "비용"]
    if month_key:
        pool = [t for t in pool if t.month_key == month_key]
    if not pool:
        return pd.DataFrame(columns=["카테고리", "금액", "건수"])
    df = pd.DataFrame([
        {"카테고리": t.category or "기타", "금액": t.withdraw}
        for t in pool
    ])
    grouped = df.groupby("카테고리").agg(
        금액=("금액", "sum"),
        건수=("금액", "count"),
    ).reset_index().sort_values("금액", ascending=False)
    return grouped


def member_payment_history(
    txs: list[Transaction],
    member_name: str,
) -> pd.DataFrame:
    """특정 회원의 납부 이력."""
    rows = [
        {
            "월": t.month_key,
            "납부일": t.txn_at.strftime("%Y-%m-%d"),
            "금액": t.deposit,
            "적요": t.memo,
        }
        for t in txs if t.kind == "회비" and t.matched_member == member_name
    ]
    if not rows:
        return pd.DataFrame(columns=["월", "납부일", "금액", "적요"])
    return pd.DataFrame(rows).sort_values("월")


def current_month_key(today: date | None = None) -> str:
    today = today or date.today()
    return today.strftime("%Y-%m")


def to_xlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    """여러 DataFrame 을 한 .xlsx 의 여러 시트로 묶어 바이트로 반환.

    streamlit ``st.download_button`` 의 ``data`` 인자로 그대로 전달 가능.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for sheet_name, df in sheets.items():
            # Excel 시트명 길이 제한 31자
            safe = sheet_name[:31] if len(sheet_name) > 31 else sheet_name
            df.to_excel(w, sheet_name=safe, index=False)
    return buf.getvalue()


def to_csv(df: pd.DataFrame) -> bytes:
    """엑셀 한국어 호환을 위해 BOM 포함 UTF-8 으로 직렬화."""
    return df.to_csv(index=False).encode("utf-8-sig")


def unpaid_report_df(
    members: list[Member],
    unpaid: list[Member],
    month_key: str,
) -> pd.DataFrame:
    """카톡/이메일 첨부용 미납자 보고서 DataFrame."""
    rows = [{
        "이름": m.name,
        "연락처": m.contact,
        "비고": m.note,
    } for m in unpaid]
    df = pd.DataFrame(rows, columns=["이름", "연락처", "비고"])
    return df
