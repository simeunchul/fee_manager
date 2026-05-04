"""은행 거래내역 엑셀 업로드 → 자동 분류 → 저장 페이지."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src import matcher, parser
from src.storage import get_storage


st.set_page_config(page_title="거래내역 업로드", page_icon="📤", layout="wide")
st.title("거래내역 업로드")
st.caption("은행 인터넷뱅킹에서 받은 .xls / .xlsx 파일을 끌어다 놓으세요.")

storage = get_storage("local")
settings = storage.get_settings()
members = storage.list_members()

if not members:
    st.warning(
        "회원이 한 명도 등록되어 있지 않습니다. "
        "회원관리 페이지에서 먼저 등록한 뒤 업로드하면 자동 매칭이 됩니다."
    )

bank_options = [("auto", "자동 감지")] + parser.list_supported_banks()
bank_label_to_key = {label: key for key, label in bank_options}
bank_choice_label = st.selectbox(
    "은행 선택",
    [label for _, label in bank_options],
    index=0,
    help="자동 감지를 권장. 잘 안되면 직접 선택하세요.",
)
bank = bank_label_to_key[bank_choice_label]

uploaded = st.file_uploader(
    "은행 거래내역 파일",
    type=["xls", "xlsx"],
    accept_multiple_files=True,
    help="여러 파일을 한 번에 올릴 수 있습니다 (예: 1월~12월).",
)

if uploaded:
    all_new_txs = []
    parse_results = []

    for f in uploaded:
        suffix = Path(f.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(f.read())
            tmp_path = Path(tmp.name)

        try:
            detected = parser.detect_bank(tmp_path) if bank == "auto" else None
            actual_bank = detected if bank == "auto" else bank
            txs = parser.parse_bank_file(tmp_path, bank=bank)
            classified = matcher.classify(txs, members, settings)
            all_new_txs.extend(classified)
            parse_results.append({
                "파일": f.name,
                "감지된 은행": actual_bank or (bank if bank != "auto" else "generic"),
                "거래 건수": len(classified),
                "회비 매칭": sum(1 for t in classified if t.kind == "회비"),
                "기타입금": sum(1 for t in classified if t.kind == "기타입금"),
                "비용": sum(1 for t in classified if t.kind == "비용"),
            })
        except Exception as e:
            parse_results.append({
                "파일": f.name,
                "감지된 은행": "-",
                "거래 건수": f"오류: {e}",
                "회비 매칭": "-",
                "기타입금": "-",
                "비용": "-",
            })
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass

    st.subheader("파싱 결과")
    st.dataframe(pd.DataFrame(parse_results), use_container_width=True, hide_index=True)

    if all_new_txs:
        st.subheader("미리보기 (저장 전)")
        preview_df = pd.DataFrame([{
            "일시": t.txn_at.strftime("%Y-%m-%d %H:%M"),
            "구분": t.kind,
            "상대방": t.counterparty,
            "회원매칭": t.matched_member,
            "입금": t.deposit if t.deposit else "",
            "출금": t.withdraw if t.withdraw else "",
            "카테고리": t.category,
            "적요": t.memo,
        } for t in sorted(all_new_txs, key=lambda x: x.txn_at)])

        st.dataframe(preview_df, use_container_width=True, hide_index=True, height=400)

        unmatched = [t for t in all_new_txs if t.kind == "기타입금"]
        if unmatched:
            st.warning(
                f"매칭되지 않은 입금이 {len(unmatched)}건 있습니다. "
                "회원명단에 없는 사람이거나 이름이 다르게 송금된 경우입니다. "
                "저장 후 회원관리에서 이름을 추가/수정하고 다시 업로드하면 자동으로 갱신됩니다."
            )

        col1, col2 = st.columns([1, 5])
        if col1.button("저장", type="primary"):
            added = storage.add_transactions(all_new_txs)
            st.success(f"{added}건의 새 거래가 저장되었습니다. (중복 {len(all_new_txs) - added}건은 무시)")
            st.balloons()
    else:
        st.error("파싱된 거래가 없습니다. 은행 선택을 바꿔보거나 파일을 확인해주세요.")

st.divider()

with st.expander("저장된 거래내역 전체 보기 / 재분류"):
    existing = storage.list_transactions()
    st.write(f"현재 저장된 거래 수: **{len(existing)}건**")
    if existing:
        df = pd.DataFrame([{
            "일시": t.txn_at.strftime("%Y-%m-%d %H:%M"),
            "구분": t.kind,
            "상대방": t.counterparty,
            "회원매칭": t.matched_member,
            "입금": t.deposit,
            "출금": t.withdraw,
            "카테고리": t.category,
            "적요": t.memo,
        } for t in existing])
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)

        if st.button("회원명단으로 전체 재분류", help="회원 추가/수정 후 누르면 기존 거래도 매칭이 갱신됩니다."):
            reclassified = matcher.classify(existing, members, settings)
            storage.replace_transactions(reclassified)
            st.success("전체 거래를 재분류했습니다.")
            st.rerun()
