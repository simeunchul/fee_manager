"""회비관리 프로그램 - 홈(대시보드).

실행:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import altair as alt

from src.storage import get_storage
from src import reporter


st.set_page_config(
    page_title="회비관리",
    page_icon="💰",
    layout="wide",
)


@st.cache_resource
def _storage(backend: str):
    return get_storage(backend)


def _get_storage_safely():
    """설정에서 backend 를 읽되, sheets 가 인증 안 됐으면 local 로 폴백."""
    local = _storage("local")
    settings = local.get_settings()
    if settings.storage_backend == "google_sheets":
        try:
            return _storage("google_sheets"), settings
        except Exception:
            st.warning(
                "구글 시트 백엔드가 설정되어 있지만 인증이 완료되지 않아 "
                "로컬 저장소로 동작 중입니다. (설정 페이지에서 변경 가능)"
            )
    return local, settings


def main():
    st.title("회비관리")
    st.caption("팀/모임 회비 입금·출금을 자동 매칭하고 미납자를 추적합니다.")

    storage, settings = _get_storage_safely()
    members = storage.list_members()
    txs = storage.list_transactions()

    this_month = reporter.current_month_key()
    st.subheader(f"이번 달 ({this_month}) 요약")

    col1, col2, col3, col4 = st.columns(4)
    active = [m for m in members if m.active]
    unpaid = reporter.unpaid_members(txs, members, this_month)
    fee_in = sum(t.deposit for t in txs if t.kind == "회비" and t.month_key == this_month)
    out = sum(t.withdraw for t in txs if t.kind == "비용" and t.month_key == this_month)

    col1.metric("활성 회원", f"{len(active)}명")
    col2.metric("이번 달 납부", f"{len(active) - len(unpaid)} / {len(active)}명")
    col3.metric("회비 수입", f"{fee_in:,}원")
    col4.metric("비용 지출", f"{out:,}원")

    st.divider()

    left, right = st.columns([1, 1])

    with left:
        st.subheader("이번 달 미납자")
        if not active:
            st.info("회원이 등록되어 있지 않습니다. 좌측 메뉴 **회원관리** 에서 추가하세요.")
        elif not unpaid:
            st.success("이번 달 미납자가 없습니다.")
        else:
            st.dataframe(
                pd.DataFrame([
                    {"이름": m.name, "연락처": m.contact, "비고": m.note}
                    for m in unpaid
                ]),
                use_container_width=True,
                hide_index=True,
            )

    with right:
        st.subheader("월별 수입·지출")
        summary = reporter.monthly_summary(txs)
        if summary.empty:
            st.info("거래내역이 없습니다. 좌측 메뉴 **거래내역 업로드** 에서 은행 파일을 올려주세요.")
        else:
            chart_df = summary.melt(
                id_vars="월",
                value_vars=["회비수입", "기타입금", "비용지출"],
                var_name="구분",
                value_name="금액",
            )
            chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X("월:N", title="월"),
                    y=alt.Y("금액:Q", title="금액 (원)"),
                    color=alt.Color("구분:N", scale=alt.Scale(
                        domain=["회비수입", "기타입금", "비용지출"],
                        range=["#2E7D32", "#1565C0", "#C62828"],
                    )),
                    xOffset="구분:N",
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)

    st.divider()
    st.subheader("최근 거래 (최신 10건)")
    if not txs:
        st.info("거래내역이 없습니다.")
    else:
        recent = sorted(txs, key=lambda t: t.txn_at, reverse=True)[:10]
        st.dataframe(
            pd.DataFrame([{
                "일시": t.txn_at.strftime("%Y-%m-%d %H:%M"),
                "구분": t.kind,
                "상대방": t.counterparty,
                "회원매칭": t.matched_member,
                "입금": t.deposit if t.deposit else "",
                "출금": t.withdraw if t.withdraw else "",
                "카테고리": t.category,
                "적요": t.memo,
            } for t in recent]),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    with st.expander("사용 가이드 (처음이라면 클릭)"):
        st.markdown(
            """
            1. 좌측 사이드바의 **회원관리** 페이지에서 회원 명단을 입력하세요.
            2. **설정** 페이지에서 회비액(기본 50,000원)과 납부 마감일을 조정하세요.
            3. 매월 은행 인터넷뱅킹에서 거래내역을 엑셀로 다운로드한 뒤,
               **거래내역 업로드** 페이지에 끌어다 놓으세요.
            4. **월별 납부현황** 에서 누가 안 냈는지, **비용관리** 에서 지출 내역을 확인할 수 있습니다.

            > 데이터는 모두 본 컴퓨터의 `data/` 폴더에 저장됩니다 (CSV 파일).
            > 구글 시트와 연동하려면 OAuth 설정 후 **설정** 페이지에서 백엔드를 변경하세요.
            """
        )


if __name__ == "__main__":
    main()
