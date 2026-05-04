"""회원 × 월 납부 매트릭스 페이지."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import reporter, pipeline
from src.storage import get_storage


st.set_page_config(page_title="월별 납부현황", page_icon="📅", layout="wide")
st.title("월별 납부현황")

storage = get_storage("local")
members = storage.list_members()
txs = pipeline.load_classified_transactions(storage)

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


_styler_map = getattr(matrix.style, "map", None) or matrix.style.applymap
styled = _styler_map(_highlight)
st.dataframe(styled, use_container_width=True, height=min(700, 50 + len(matrix) * 35))

# 매트릭스 + 월별요약 한 파일로 다운로드 (팀원 공유용)
summary_df = reporter.monthly_summary(txs)
matrix_for_export = matrix.reset_index()  # 회원 컬럼이 index 라 reset
xlsx_bytes = reporter.to_xlsx({
    "납부매트릭스": matrix_for_export,
    "월별요약": summary_df,
})
st.download_button(
    "📥 전체 현황 엑셀 다운로드 (팀 공유용)",
    data=xlsx_bytes,
    file_name=f"회비현황_{sorted(selected_months)[-1]}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="secondary",
)

st.divider()

st.subheader("월별 미납자 상세")
target_month = st.selectbox("월 선택", sorted(selected_months, reverse=True))
unpaid = reporter.unpaid_members(txs, members, target_month)

c1, c2 = st.columns([1, 2])
c1.metric(f"{target_month} 미납자", f"{len(unpaid)}명")

if unpaid:
    unpaid_df = reporter.unpaid_report_df(members, unpaid, target_month)
    c2.dataframe(unpaid_df, use_container_width=True, hide_index=True)

    # 미납자 명단 단독 다운로드 - 카톡/이메일 첨부에 가장 자주 쓰는 형태
    d1, d2 = st.columns(2)
    d1.download_button(
        f"📥 {target_month} 미납자 엑셀",
        data=reporter.to_xlsx({f"{target_month} 미납자": unpaid_df}),
        file_name=f"미납자_{target_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"_dl_unpaid_xlsx_{target_month}",
    )
    d2.download_button(
        f"📥 {target_month} 미납자 CSV",
        data=reporter.to_csv(unpaid_df),
        file_name=f"미납자_{target_month}.csv",
        mime="text/csv",
        key=f"_dl_unpaid_csv_{target_month}",
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
