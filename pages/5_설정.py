"""회비액, 마감일, 비용 카테고리 설정."""
from __future__ import annotations

import streamlit as st

from src import pipeline
from src.models import Settings
from src.storage import get_storage


st.set_page_config(page_title="설정", page_icon="⚙️", layout="centered")
st.title("설정")

# rerun 직후 사용자가 저장 결과를 명확히 볼 수 있도록 상단에 메시지 노출
if _saved_msg := st.session_state.pop("_settings_saved_msg", None):
    st.success(_saved_msg)

storage = get_storage("local")
settings = storage.get_settings()

st.subheader("회비")
fee = st.number_input(
    "월 회비액 (원)",
    min_value=0,
    step=1000,
    value=int(settings.monthly_fee),
)
due_day = st.slider(
    "납부 마감일 (매월)",
    min_value=1,
    max_value=31,
    value=int(settings.fee_due_day),
    help="현재는 표시용. 추후 알림 기능에 사용 예정.",
)

st.subheader("비용 카테고리")
categories_text = st.text_area(
    "쉼표 또는 줄바꿈으로 구분",
    value=", ".join(settings.expense_categories),
    height=100,
)
new_categories = [
    c.strip() for c in categories_text.replace("\n", ",").split(",")
    if c.strip()
]

if st.button("저장", type="primary"):
    new_settings = Settings(
        monthly_fee=int(fee),
        fee_due_day=int(due_day),
        expense_categories=new_categories or ["기타"],
    )
    storage.save_settings(new_settings)
    changed = pipeline.reclassify_and_save(storage)
    msg = "✅ 설정이 저장되었습니다."
    if changed:
        msg += f" 회비액 변경에 따라 거래 {changed}건의 분류를 자동 갱신했습니다."
    st.toast(msg, icon="✅")
    st.session_state["_settings_saved_msg"] = msg
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()

st.divider()

with st.expander("저장된 데이터 위치"):
    from src.local_storage import DATA_DIR, MEMBERS_CSV, TRANSACTIONS_CSV, SETTINGS_JSON
    st.code(
        f"폴더:        {DATA_DIR}\n"
        f"회원명단:    {MEMBERS_CSV.name}\n"
        f"거래내역:    {TRANSACTIONS_CSV.name}\n"
        f"설정:        {SETTINGS_JSON.name}",
        language="text",
    )
    st.caption("백업은 위 폴더 전체를 복사해두면 됩니다.")
