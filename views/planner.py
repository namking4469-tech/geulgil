"""집필 목표 · 기록 · 일정."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core.db import Event, Setting, WritingLog, db, select
from core.ui import header, require_login

user = require_login()
header("🗓️ 집필 목표 · 일정", "매일 쓴 분량을 기록하고, 마감과 일정을 관리합니다.")

with db() as s:
    row = s.get(Setting, user.id)
    prefs = dict(row.data) if row else {}
    logs = list(s.scalars(select(WritingLog).where(WritingLog.user_id == user.id).order_by(WritingLog.on)))
    events = list(s.scalars(select(Event).where(Event.user_id == user.id).order_by(Event.on)))
goal = int(prefs.get("daily_goal", 2000))
today = date.today()
by_day = {}
for g in logs:
    by_day[g.on] = by_day.get(g.on, 0) + g.chars

streak, d = 0, today
if by_day.get(today, 0) < goal:
    d = today - timedelta(days=1)  # 오늘은 아직 쓰는 중일 수 있다
while by_day.get(d, 0) >= goal:
    streak += 1
    d -= timedelta(days=1)

t_write, t_cal = st.tabs(["집필 기록", "일정"])

with t_write:
    m = st.columns(4)
    m[0].metric("오늘", f"{by_day.get(today, 0):,}자", f"목표 {goal:,}자")
    m[1].metric("최근 7일", f"{sum(v for k, v in by_day.items() if k > today - timedelta(days=7)):,}자")
    m[2].metric("이번 달", f"{sum(v for k, v in by_day.items() if (k.year, k.month) == (today.year, today.month)):,}자")
    m[3].metric("목표 달성 연속", f"{streak}일")
    st.progress(min(1.0, by_day.get(today, 0) / goal) if goal else 0.0)

    c1, c2 = st.columns([2, 1], gap="large")
    with c1:
        with st.form("log", clear_on_submit=True):
            k = st.columns([1, 1, 2])
            on = k[0].date_input("날짜", today, max_value=today)
            chars = k[1].number_input("쓴 글자 수", 0, 200000, 0, 100)
            memo = k[2].text_input("메모 (작품·장면 등)")
            if st.form_submit_button("기록", type="primary") and chars > 0:
                with db() as s:
                    s.add(WritingLog(user_id=user.id, on=on, chars=int(chars), memo=memo))
                st.rerun()
    with c2:
        with st.form("goal"):
            g = st.number_input("하루 목표(자)", 100, 50000, goal, 100)
            if st.form_submit_button("목표 저장"):
                with db() as s:
                    row = s.get(Setting, user.id)
                    if row:
                        row.data = {**row.data, "daily_goal": int(g)}
                    else:
                        s.add(Setting(user_id=user.id, data={"daily_goal": int(g)}))
                st.rerun()

    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    chart = pd.DataFrame({"날짜": [d.strftime("%m-%d") for d in days], "글자 수": [by_day.get(d, 0) for d in days]})
    st.bar_chart(chart, x="날짜", y="글자 수", height=240)
    if logs:
        with st.expander("기록 목록 · 삭제"):
            for g in reversed(logs[-40:]):
                k = st.columns([1.2, 1, 3, 0.8])
                k[0].write(str(g.on))
                k[1].write(f"{g.chars:,}자")
                k[2].write(g.memo)
                if k[3].button("삭제", key=f"lg{g.id}"):
                    with db() as s:
                        s.delete(s.get(WritingLog, g.id))
                    st.rerun()

with t_cal:
    with st.form("ev", clear_on_submit=True):
        k = st.columns([1, 1, 3])
        on = k[0].date_input("날짜", today)
        kind = k[1].selectbox("종류", ["마감", "공모전", "출간", "행사·강연", "미팅", "기타"])
        title = k[2].text_input("내용")
        if st.form_submit_button("일정 추가", type="primary") and title.strip():
            with db() as s:
                s.add(Event(user_id=user.id, on=on, title=title.strip(), kind=kind))
            st.rerun()
    upcoming = [e for e in events if not e.done and e.on >= today]
    overdue = [e for e in events if not e.done and e.on < today]
    past = [e for e in events if e.done]

    def show(items, label):
        if not items:
            return
        st.markdown(f"##### {label}")
        for e in items:
            dd = (e.on - today).days
            tag = f"D-{dd}" if dd > 0 else "오늘" if dd == 0 else f"{-dd}일 지남"
            k = st.columns([1.2, 0.9, 0.9, 3.5, 0.8, 0.8])
            k[0].write(str(e.on))
            k[1].write(f"**{tag}**" if not e.done else "완료")
            k[2].write(e.kind)
            k[3].write(e.title)
            if k[4].button("완료" if not e.done else "되돌림", key=f"ed{e.id}"):
                with db() as s:
                    s.get(Event, e.id).done = not e.done
                st.rerun()
            if k[5].button("삭제", key=f"ex{e.id}"):
                with db() as s:
                    s.delete(s.get(Event, e.id))
                st.rerun()

    show(overdue, "⏰ 날짜가 지난 일정")
    show(upcoming, "다가오는 일정")
    if not (upcoming or overdue):
        st.info("예정된 일정이 없습니다.")
    with st.expander(f"완료한 일정 ({len(past)})"):
        show(past, "완료")
