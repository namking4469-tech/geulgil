"""공모전 정보: 검색 · 내 작품 맞춤 추천 · 일정/응모 기록 연결."""
from datetime import date

import streamlit as st

from core.db import Contest, Event, Submission, db, select
from core.ui import header, list_works, require_login

user = require_login()
header("🏆 공모전", "국내외 문학 공모전을 찾아보고, 내 작품에 맞는 곳을 추천받으세요.")
st.warning("공모전의 마감일·분량·자격·상금은 **해마다 바뀝니다.** 여기 정보는 길잡이이며, 응모 전에 반드시 "
           "주최 측 공식 공고를 확인해 주세요. '확인된 마감일'은 관리자가 공식 공고를 보고 입력한 경우에만 표시됩니다.", icon="⚠️")

with db() as s:
    contests = list(s.scalars(select(Contest).order_by(Contest.name)))
works = list_works(user.id)

c1, c2, c3, c4 = st.columns([1.4, 1, 1.2, 1.2])
by = {w.id: w for w in works}
wid = c1.selectbox("내 작품에 맞춰 추천", [0] + list(by), format_func=lambda i: "전체 보기" if not i else by[i].title)
region = c2.selectbox("지역", ["전체", "한국", "해외"])
genres = sorted({g for c in contests for g in c.genres})
f_genre = c3.multiselect("장르", genres)
q = c4.text_input("검색")


def score(c: Contest) -> int:
    if not wid:
        return 0
    w = by[wid]
    sc = 0
    if w.genre in c.genres:
        sc += 3
    if w.length_class and w.length_class[:2] in (c.length or ""):
        sc += 2
    if (w.lang == "ko") == (c.country == "한국"):
        sc += 1
    return sc


shown = []
for c in contests:
    if region == "한국" and c.country != "한국":
        continue
    if region == "해외" and c.country == "한국":
        continue
    if f_genre and not set(f_genre) & set(c.genres):
        continue
    if q and q.lower() not in (c.name + c.organizer + c.note).lower():
        continue
    if wid and score(c) < 3:
        continue
    shown.append(c)
shown.sort(key=lambda c: (-score(c), c.deadline or date.max, c.name))

if wid:
    w = by[wid]
    st.caption(f"《{w.title}》 ({w.genre or '장르 미분류'} · {w.length_class or '분량 미분류'}) 의 장르를 받는 공모전 {len(shown)}곳")
else:
    st.caption(f"{len(shown)}곳")

today = date.today()
for c in shown:
    dl = ""
    if c.deadline:
        d = (c.deadline - today).days
        dl = f" · 마감 {c.deadline} ({'D-' + str(d) if d >= 0 else '마감됨'})"
    with st.expander(f"**{c.name}** — {c.organizer} · {c.country}{dl}"):
        a, b = st.columns([2, 1], gap="large")
        with a:
            st.markdown(f"- **모집 분야**: {', '.join(c.genres)}\n- **분량**: {c.length}\n- **통상 접수 시기**: {c.period}\n"
                        f"- **상금·특전**: {c.prize}\n- **응모 자격**: {c.eligibility}"
                        + (f"\n- **확인된 마감일**: {c.deadline}" if c.deadline else "")
                        + (f"\n- **메모**: {c.note}" if c.note else ""))
            if c.url:
                st.link_button("공식 사이트에서 요강 확인", c.url)
        with b:
            when = st.date_input("내 일정에 넣을 날짜", c.deadline or today, key=f"cd{c.id}")
            if st.button("일정에 추가", key=f"ce{c.id}", use_container_width=True):
                with db() as s:
                    s.add(Event(user_id=user.id, on=when, title=f"{c.name} 마감", kind="공모전"))
                st.toast("일정에 추가했습니다.")
            if works:
                sw = st.selectbox("응모할 작품", list(by), format_func=lambda i: by[i].title, key=f"cw{c.id}",
                                  index=list(by).index(wid) if wid else 0)
                if st.button("응모 기록 남기기", key=f"cs{c.id}", use_container_width=True):
                    with db() as s:
                        s.add(Submission(user_id=user.id, work_id=sw, target_type="공모전", target_name=c.name,
                                         status="준비 중"))
                    st.toast("'투고 관리'에 기록했습니다.")
if not shown:
    st.info("조건에 맞는 공모전이 없습니다. 조건을 넓혀 보세요.")
