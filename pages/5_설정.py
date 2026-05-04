"""회비액, 마감일, 비용 카테고리, 저장소 백엔드 설정."""
from __future__ import annotations

import streamlit as st

from src.models import Settings
from src.storage import get_storage


st.set_page_config(page_title="설정", page_icon="⚙️", layout="centered")
st.title("설정")

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

st.subheader("저장소 백엔드")
backend = st.radio(
    "데이터 저장 위치",
    options=["local", "google_sheets"],
    format_func=lambda x: {"local": "로컬 (data/ 폴더 CSV)", "google_sheets": "구글 스프레드시트"}[x],
    index=0 if settings.storage_backend == "local" else 1,
    horizontal=True,
)

spreadsheet_id = ""
if backend == "google_sheets":
    spreadsheet_id = st.text_input(
        "스프레드시트 ID",
        value=settings.spreadsheet_id,
        help="구글 시트 URL 의 /d/ 다음 부분 (예: 1AbCdEf...)",
    )
    st.warning(
        "구글 시트 백엔드를 사용하려면 OAuth 인증이 필요합니다. "
        "현재 인증 코드가 비활성화되어 있으니 `credentials/SETUP_OAUTH.md` 가이드에 따라 "
        "발급한 뒤 `src/auth.py` 의 `get_gspread_client()` 를 활성화하세요."
    )

if st.button("저장", type="primary"):
    new_settings = Settings(
        monthly_fee=int(fee),
        fee_due_day=int(due_day),
        expense_categories=new_categories or ["기타"],
        storage_backend=backend,  # type: ignore[arg-type]
        spreadsheet_id=spreadsheet_id.strip(),
    )
    storage.save_settings(new_settings)
    st.success("설정이 저장되었습니다.")
    st.cache_resource.clear()
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
