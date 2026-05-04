"""회비관리 프로그램 - 홈(대시보드).

실행:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import altair as alt

from src.storage import get_storage
from src import reporter, updater, pipeline


st.set_page_config(
    page_title="회비관리",
    page_icon="💰",
    layout="wide",
)


@st.cache_resource
def _storage():
    return get_storage("local")


@st.cache_data(ttl=3600)
def _check_update_cached(_nonce: int = 0):
    """앱 시작 시 1시간 캐시. 강제 재확인 시 _nonce 를 바꿔 캐시 우회."""
    return updater.check_for_update(force=(_nonce > 0))


def _render_update_banner():
    nonce = st.session_state.get("_update_check_nonce", 0)
    info = _check_update_cached(nonce)
    with st.sidebar:
        if info and info.is_newer:
            st.warning(
                f"새 버전 **{info.latest}** 이 있습니다.\n\n현재: {info.current}",
                icon="⬆️",
            )
            if info.notes:
                with st.sidebar.expander("변경사항"):
                    st.markdown(info.notes)
            if st.button("업데이트 받기", use_container_width=True, key="_update_btn"):
                progress_bar = st.progress(0, text="다운로드 준비 중...")

                def _on_progress(downloaded: int, total: int):
                    if total > 0:
                        pct = min(downloaded / total, 1.0)
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total / (1024 * 1024)
                        progress_bar.progress(
                            pct,
                            text=f"다운로드 중... {mb_done:.1f} / {mb_total:.1f} MB ({int(pct*100)}%)",
                        )
                    else:
                        mb_done = downloaded / (1024 * 1024)
                        progress_bar.progress(
                            0,
                            text=f"다운로드 중... {mb_done:.1f} MB",
                        )

                try:
                    updater.download_update(info, progress_cb=_on_progress)
                except Exception as e:
                    progress_bar.empty()
                    st.error(f"다운로드 실패:\n\n{e}")
                    st.markdown(
                        f"[GitHub Releases 페이지에서 직접 받기]({info.download_url})"
                    )
                    return
                progress_bar.progress(1.0, text="다운로드 완료")
                st.success(
                    "✅ 다운로드 완료. 잠시 후 자동으로 재시작됩니다.\n\n"
                    "재시작 후엔 **브라우저를 새로고침** 해주세요."
                )
                updater.schedule_self_terminate(delay_sec=3.0)
                st.stop()
        # 강제 재확인 버튼 — 새 release 직후 캐시 우회용
        if st.button("↻ 업데이트 다시 확인", use_container_width=True, key="_force_check_btn"):
            st.session_state["_update_check_nonce"] = nonce + 1
            st.cache_data.clear()
            st.rerun()


def main():
    st.title("회비관리")
    st.caption("팀/모임 회비 입금·출금을 자동 매칭하고 미납자를 추적합니다.")
    _render_update_banner()

    storage = _storage()
    settings = storage.get_settings()
    members = storage.list_members()
    txs = pipeline.load_classified_transactions(storage)

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

    st.subheader("누적 요약")
    total_fee = sum(t.deposit for t in txs if t.kind == "회비")
    total_other = sum(t.deposit for t in txs if t.kind == "기타입금")
    total_out = sum(t.withdraw for t in txs if t.kind == "비용")
    balance = total_fee + total_other - total_out

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("누적 회비수입", f"{total_fee:,}원")
    a2.metric("누적 기타입금", f"{total_other:,}원")
    a3.metric("누적 비용지출", f"{total_out:,}원")
    a4.metric(
        "잔여금액",
        f"{balance:,}원",
        help="누적 회비수입 + 누적 기타입금 - 누적 비용지출. 거래내역에 기록된 범위 기준이라 시작 시점 이전 잔고는 반영되지 않습니다.",
    )

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
                "입금": f"{t.deposit:,}" if t.deposit else "",
                "출금": f"{t.withdraw:,}" if t.withdraw else "",
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

            > 데이터는 본 컴퓨터의 `%USERPROFILE%\\.fee_manager\\` 폴더에 저장됩니다 (CSV 파일).
            > 앱을 업데이트(폴더 교체)해도 데이터는 보존됩니다.
            > 팀원과 공유는 **월별 납부현황 → 엑셀 다운로드** 로 한 번에.
            """
        )


if __name__ == "__main__":
    main()
