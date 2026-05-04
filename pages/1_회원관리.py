"""회원 추가/수정/삭제 페이지."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.models import Member
from src.storage import get_storage


st.set_page_config(page_title="회원관리", page_icon="👥", layout="wide")
st.title("회원관리")

storage = get_storage("local")
members = storage.list_members()

st.subheader("회원 추가")

with st.form("add_member", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    name = c1.text_input("이름 *", placeholder="홍길동")
    contact = c2.text_input("연락처", placeholder="010-1234-5678")
    joined_on = c3.date_input("가입일", value=date.today())
    note = st.text_input("비고", placeholder="(선택) 메모")
    submitted = st.form_submit_button("추가", type="primary")
    if submitted:
        if not name.strip():
            st.error("이름을 입력해주세요.")
        elif any(m.name == name.strip() for m in members):
            st.error(f"'{name}' 회원이 이미 존재합니다.")
        else:
            storage.upsert_member(Member(
                name=name.strip(),
                joined_on=joined_on,
                active=True,
                contact=contact.strip(),
                note=note.strip(),
            ))
            st.success(f"'{name}' 회원이 추가되었습니다.")
            st.rerun()

st.divider()

st.subheader("회원 명단")

if not members:
    st.info("등록된 회원이 없습니다. 위 폼에서 추가해주세요.")
else:
    df = pd.DataFrame([{
        "이름": m.name,
        "가입일": m.joined_on.isoformat(),
        "활성": m.active,
        "연락처": m.contact,
        "비고": m.note,
    } for m in members])

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "활성": st.column_config.CheckboxColumn(
                help="체크 해제 시 회비 매칭 대상에서 제외 (탈퇴 처리)",
            ),
        },
        disabled=["이름", "가입일"],
        key="members_editor",
    )

    csave, cdel = st.columns([1, 1])
    if csave.button("변경사항 저장", type="primary"):
        for _, row in edited.iterrows():
            storage.upsert_member(Member(
                name=row["이름"],
                joined_on=date.fromisoformat(row["가입일"]),
                active=bool(row["활성"]),
                contact=str(row["연락처"] or ""),
                note=str(row["비고"] or ""),
            ))
        st.success("저장되었습니다.")
        st.rerun()

    with cdel.expander("회원 삭제"):
        names = [m.name for m in members]
        target = st.selectbox("삭제할 회원", names, index=None, placeholder="이름 선택")
        confirm = st.checkbox("정말 삭제합니다 (되돌릴 수 없음)")
        if st.button("삭제 실행", disabled=not (target and confirm)):
            storage.delete_member(target)
            st.success(f"'{target}' 회원이 삭제되었습니다.")
            st.rerun()

st.divider()
with st.expander("CSV 일괄 업로드 (대량 등록 시)"):
    st.caption("컬럼: name, joined_on, active, contact, note (헤더 필수)")
    up = st.file_uploader("회원 CSV 파일", type=["csv"], key="members_csv")
    if up is not None:
        try:
            new_df = pd.read_csv(up).fillna("")
            count = 0
            for _, row in new_df.iterrows():
                storage.upsert_member(Member.from_dict(row.to_dict()))
                count += 1
            st.success(f"{count}명을 추가/갱신했습니다.")
            st.rerun()
        except Exception as e:
            st.error(f"파일 읽기 실패: {e}")
