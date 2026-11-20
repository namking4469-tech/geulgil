"""투고 관리: 공모전 응모·에이전시/출판사 투고 이력과 결과 추적."""
from datetime import date

import pandas as pd
import streamlit as st

from core.db import Submission, db, select
from core.ui import header, list_works, require_login

user = require_login()
header("📮 투고 관리", "어디에 무엇을 보냈고 결과가 어떤지 한눈에 봅니다.")
STATUS = ["준비 중", "발송", "검토 중", "수정 요청", "수락", "거절", "무응답", "철회"]
TYPES = ["공모전", "에이전시", "출판사", "플랫폼", "문예지", "기타"]

works = {w.id: w.title for w in list_works(user.id)}
with db() as s:
    subs = list(s.scalars(select(Submission).where(Submission.user_id == user.id).order_by(Submission.on.desc(), Submission.id.desc())))

if subs:
    m = st.columns(4)
    m[0].metric("전체", len(subs))
    m[1].metric("진행 중", sum(x.status in ("준비 중", "발송", "검토 중", "수정 요청") for x in subs))
    m[2].metric("수락", sum(x.status == "수락" for x in subs))
    m[3].metric("거절·무응답", sum(x.status in ("거절", "무응답") for x in subs))
    df = pd.DataFrame([{"id": x.id, "날짜": x.on, "종류": x.target_type, "보낸 곳": x.target_name,
                        "작품": works.get(x.work_id, ""), "상태": x.status, "받는 주소": x.sent_to, "메모": x.note,
                        "삭제": False} for x in subs])
    st.caption("표에서 상태·메모를 바로 고치고 '변경 저장'을 누르세요.")
    out = st.data_editor(df, hide_index=True, use_container_width=True, disabled=["id", "작품", "받는 주소"],
                         column_config={"id": None, "상태": st.column_config.SelectboxColumn(options=STATUS),
                                        "종류": st.column_config.SelectboxColumn(options=TYPES),
                                        "날짜": st.column_config.DateColumn()})
    c1, c2 = st.columns([1, 4])
    if c1.button("변경 저장", type="primary"):
        with db() as s:
            for _, r in out.iterrows():
                row = s.get(Submission, int(r["id"]))
                if r["삭제"]:
                    s.delete(row)
                else:
                    row.on, row.target_type, row.target_name = r["날짜"], r["종류"], r["보낸 곳"]
                    row.status, row.note = r["상태"], r["메모"] or ""
        st.rerun()
    c2.download_button("CSV 내려받기", df.drop(columns=["id", "삭제"]).to_csv(index=False).encode("utf-8-sig"),
                       "투고기록.csv", mime="text/csv")
    with st.expander("보낸 편지 다시 보기"):
        for x in subs:
            if x.body:
                st.markdown(f"**{x.on} · {x.target_name}**")
                st.text(x.body)
else:
    st.info("아직 기록이 없습니다. 공모전·에이전시 화면에서 기록하거나 아래에서 직접 추가하세요.")

st.divider()
st.markdown("##### 직접 추가")
with st.form("add", clear_on_submit=True):
    c = st.columns(4)
    on = c[0].date_input("날짜", date.today())
    typ = c[1].selectbox("종류", TYPES)
    name = c[2].text_input("보낸 곳")
    wid = c[3].selectbox("작품", [0] + list(works), format_func=lambda i: works.get(i, "(선택 안 함)"))
    c = st.columns([1, 3])
    status = c[0].selectbox("상태", STATUS)
    note = c[1].text_input("메모")
    if st.form_submit_button("추가") and name.strip():
        with db() as s:
            s.add(Submission(user_id=user.id, work_id=wid or None, target_type=typ, target_name=name.strip(),
                             status=status, note=note, on=on))
        st.rerun()
