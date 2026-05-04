"""비용(출금) 관리 페이지 - 카테고리별 집계 및 수동 분류."""
from __future__ import annotations

import pandas as pd
import streamlit as st
import altair as alt

from src import reporter
from src.storage import get_storage


st.set_page_config(page_title="비용관리", page_icon="💸", layout="wide")
st.title("비용관리")

storage = get_storage("local")
settings = storage.get_settings()
txs = storage.list_transactions()

expense_txs = [t for t in txs if t.kind == "비용"]
if not expense_txs:
    st.info("출금(비용) 내역이 없습니다.")
    st.stop()

months_all = reporter.month_keys(expense_txs)
target = st.selectbox(
    "월 선택",
    options=["전체"] + sorted(months_all, reverse=True),
    index=0,
)
target_month = None if target == "전체" else target

st.subheader("카테고리별 합계")
breakdown = reporter.expense_breakdown(expense_txs, target_month)

c1, c2 = st.columns([1, 1])
c1.dataframe(
    breakdown.assign(금액=lambda d: d["금액"].map(lambda x: f"{int(x):,}원")),
    use_container_width=True,
    hide_index=True,
)

if not breakdown.empty:
    chart = (
        alt.Chart(breakdown)
        .mark_arc(innerRadius=60)
        .encode(
            theta="금액:Q",
            color=alt.Color("카테고리:N"),
            tooltip=["카테고리", "금액", "건수"],
        )
        .properties(height=300)
    )
    c2.altair_chart(chart, use_container_width=True)

total = breakdown["금액"].sum()
st.metric(
    f"{'전체' if target_month is None else target_month} 비용 총합",
    f"{int(total):,}원",
)

st.divider()

st.subheader("개별 거래 - 카테고리 수정")
st.caption("자동 추천된 카테고리가 틀렸으면 직접 수정 후 저장하세요.")

filtered = expense_txs if target_month is None else [t for t in expense_txs if t.month_key == target_month]

if filtered:
    df = pd.DataFrame([{
        "_idx": i,
        "일시": t.txn_at.strftime("%Y-%m-%d %H:%M"),
        "상대방": t.counterparty,
        "출금액": t.withdraw,
        "카테고리": t.category or "기타",
        "적요": t.memo,
    } for i, t in enumerate(filtered)])

    edited = st.data_editor(
        df.drop(columns=["_idx"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "카테고리": st.column_config.SelectboxColumn(
                options=settings.expense_categories,
                required=True,
            ),
        },
        disabled=["일시", "상대방", "출금액", "적요"],
        key="expense_editor",
    )

    if st.button("카테고리 수정 저장", type="primary"):
        # 인덱스 기준으로 카테고리만 갱신
        for i, row in edited.iterrows():
            filtered[i].category = str(row["카테고리"])
        # 전체 거래 리스트에서도 동기화
        edited_keys = {(t.txn_at.isoformat(), t.counterparty, t.withdraw): t.category for t in filtered}
        for t in txs:
            k = (t.txn_at.isoformat(), t.counterparty, t.withdraw)
            if k in edited_keys:
                t.category = edited_keys[k]
        storage.replace_transactions(txs)
        st.success("저장되었습니다.")
        st.rerun()
