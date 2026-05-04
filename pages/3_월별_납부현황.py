"""회원 × 월 납부 매트릭스 페이지."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import reporter
from src.storage import get_storage


st.set_page_config(page_title="월별 납부현황", page_icon="📅", layout="wide")
st.title("월별 납부현황")

storage = get_storage("local")
members = storage.list_members()
txs = storage.list_transactions()

if not members:
    st.info("회원이 등록되어 있지 않습니다.")
    st.stop()

if not txs:
    st.info("거래내역이 없습니다. 거래내역 업로드 페이지에서 은행 파일을 올려주세요.")
    st.stop()

months_all = reporter.month_keys(txs)
default_months = months_all[-6:] if len(months_all) > 6 else months_all
selected_months = st.multiselect(
    "표시할 월",
    options=months_all,
    default=default_months,
    help="기본은 최근 6개월. 전체 또는 특정 월만 선택 가능.",
)

if not selected_months:
    st.warning("최소 1개월을 선택하세요.")
    st.stop()

matrix = reporter.payment_matrix(txs, members, sorted(selected_months))

st.subheader("납부 매트릭스")
st.caption("✓ = 납부 / ✗ = 미납")


def _highlight(val):
    if val == "✓":
        return "background-color: #C8E6C9"
    if val == "✗":
        return "background-color: #FFCDD2"
    return ""


styled = matrix.style.applymap(_highlight)
st.dataframe(styled, use_container_width=True, height=min(700, 50 + len(matrix) * 35))

st.divider()

st.subheader("월별 미납자 상세")
target_month = st.selectbox("월 선택", sorted(selected_months, reverse=True))
unpaid = reporter.unpaid_members(txs, members, target_month)

c1, c2 = st.columns([1, 2])
c1.metric(f"{target_month} 미납자", f"{len(unpaid)}명")

if unpaid:
    c2.dataframe(
        pd.DataFrame([
            {"이름": m.name, "연락처": m.contact, "비고": m.note}
            for m in unpaid
        ]),
        use_container_width=True,
        hide_index=True,
    )
else:
    c2.success(f"{target_month} 에는 미납자가 없습니다.")

st.divider()

st.subheader("회원별 납부 이력")
member_names = [m.name for m in members]
target_member = st.selectbox("회원 선택", member_names, index=None, placeholder="이름 선택")

if target_member:
    history = reporter.member_payment_history(txs, target_member)
    if history.empty:
        st.warning(f"'{target_member}' 의 납부 기록이 없습니다.")
    else:
        st.dataframe(history, use_container_width=True, hide_index=True)
        total = history["금액"].sum()
        st.metric("누적 납부액", f"{int(total):,}원")
