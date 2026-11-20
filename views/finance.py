"""수익 · 계약 관리."""
import io
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core.db import Contract, Finance, db, select
from core.ui import header, list_works, require_login

user = require_login()
header("💰 수익 · 계약", "인세·원고료·상금과 출판 계약을 기록합니다. (개인 장부용이며 세무 신고 자료를 대신하지 않습니다)")
KINDS = ["인세", "원고료", "상금", "계약금(선인세)", "강연료", "지원금", "기타 수입", "지출"]
titles = [""] + [w.title for w in list_works(user.id)]

with db() as s:
    rows = list(s.scalars(select(Finance).where(Finance.user_id == user.id).order_by(Finance.on.desc())))
    contracts = list(s.scalars(select(Contract).where(Contract.user_id == user.id).order_by(Contract.end)))

t_money, t_contract = st.tabs(["수입 · 지출", "계약"])

with t_money:
    years = sorted({r.on.year for r in rows} | {date.today().year}, reverse=True)
    year = st.selectbox("연도", years)
    yr = [r for r in rows if r.on.year == year]
    income = sum(r.amount for r in yr if r.kind != "지출")
    spend = sum(r.amount for r in yr if r.kind == "지출")
    m = st.columns(3)
    m[0].metric(f"{year}년 수입", f"{income:,.0f}원")
    m[1].metric("지출", f"{spend:,.0f}원")
    m[2].metric("순수입", f"{income - spend:,.0f}원")
    if yr:
        monthly = pd.DataFrame({"월": [f"{i}월" for i in range(1, 13)],
                                "수입": [sum(r.amount for r in yr if r.on.month == i and r.kind != "지출") for i in range(1, 13)]})
        st.bar_chart(monthly, x="월", y="수입", height=220)
    with st.form("fin", clear_on_submit=True):
        k = st.columns([1, 1, 1.4, 1.4, 1])
        on = k[0].date_input("날짜", date.today())
        kind = k[1].selectbox("구분", KINDS)
        wt = k[2].selectbox("작품", titles)
        cp = k[3].text_input("거래처 (출판사·플랫폼 등)")
        amt = k[4].number_input("금액(원)", 0, 10**10, 0, 10000)
        memo = st.text_input("메모")
        if st.form_submit_button("기록", type="primary") and amt > 0:
            with db() as s:
                s.add(Finance(user_id=user.id, on=on, kind=kind, work_title=wt, counterparty=cp, amount=float(amt), memo=memo))
            st.rerun()
    if rows:
        df = pd.DataFrame([{"id": r.id, "날짜": r.on, "구분": r.kind, "작품": r.work_title, "거래처": r.counterparty,
                            "금액": r.amount, "메모": r.memo, "삭제": False} for r in rows])
        out = st.data_editor(df, hide_index=True, use_container_width=True, disabled=[c for c in df.columns if c != "삭제"],
                             column_config={"id": None, "금액": st.column_config.NumberColumn(format="%,.0f")})
        c1, c2 = st.columns([1, 4])
        if c1.button("선택 삭제"):
            with db() as s:
                for i in out[out["삭제"]]["id"]:
                    s.delete(s.get(Finance, int(i)))
            st.rerun()
        buf = io.BytesIO()
        df.drop(columns=["id", "삭제"]).to_excel(buf, index=False, sheet_name="수입지출")
        c2.download_button("Excel 내려받기", buf.getvalue(), "수입지출.xlsx")

with t_contract:
    soon = [c for c in contracts if c.end and date.today() <= c.end <= date.today() + timedelta(days=90)]
    for c in soon:
        st.warning(f"《{c.work_title}》 — {c.counterparty} {c.kind} 계약이 {c.end} 에 끝납니다. (D-{(c.end - date.today()).days})")
    with st.form("ct", clear_on_submit=True):
        k = st.columns(3)
        wt = k[0].selectbox("작품", titles, key="ctw")
        cp = k[1].text_input("상대방 (출판사·플랫폼·에이전시)")
        kind = k[2].selectbox("계약 종류", ["출판권(종이책)", "전자책 배타적발행권", "전자책 비독점", "2차적저작물(영상·웹툰 등)", "해외 판권", "에이전시 계약", "연재", "기타"])
        k = st.columns(3)
        start = k[0].date_input("시작일", date.today())
        end = k[1].date_input("종료일", None)
        royalty = k[2].text_input("인세율·조건", placeholder="예: 정가의 10% / 순매출의 70%")
        memo = st.text_area("메모 (자동 연장, 해지 통보 기한 등)", height=70)
        if st.form_submit_button("계약 추가", type="primary") and cp.strip():
            with db() as s:
                s.add(Contract(user_id=user.id, work_title=wt, counterparty=cp.strip(), kind=kind, start=start, end=end,
                               royalty=royalty, memo=memo))
            st.rerun()
    if not contracts:
        st.info("기록된 계약이 없습니다.")
    for c in contracts:
        with st.expander(f"《{c.work_title or '작품 미지정'}》 — {c.counterparty} · {c.kind} · {c.start or ''} ~ {c.end or '기한 없음'}"):
            st.write(f"**조건**: {c.royalty or '-'}")
            if c.memo:
                st.write(c.memo)
            if st.button("삭제", key=f"cx{c.id}"):
                with db() as s:
                    s.delete(s.get(Contract, c.id))
                st.rerun()
