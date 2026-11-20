"""대시보드."""
import html
from datetime import date, timedelta

import streamlit as st

from core.ai import ai_ready
from core.auth import PROVIDERS, provider_ready
from core.config import LANGS
from core.db import Ebook, Event, Submission, Translation, WritingLog, db, func, is_persistent, select
from core.docs import KIND_LABEL
from core.mailer import smtp_ready
from core.ui import KIND_ICON, fmt_dt, list_works, require_login

user = require_login()
st.title(f"안녕하세요, {user.display} 작가님 ✒️")

works = list_works(user.id)
wids = [w.id for w in works]
today = date.today()
with db() as s:
    n_tr = s.scalar(select(func.count()).select_from(Translation).where(Translation.work_id.in_(wids))) if wids else 0
    n_eb = s.scalar(select(func.count()).select_from(Ebook).where(Ebook.work_id.in_(wids))) if wids else 0
    subs = list(s.scalars(select(Submission).where(Submission.user_id == user.id)))
    events = list(s.scalars(select(Event).where(Event.user_id == user.id, Event.done == False,  # noqa: E712
                                                Event.on <= today + timedelta(days=30)).order_by(Event.on)))
    wrote = s.scalar(select(func.coalesce(func.sum(WritingLog.chars), 0)).where(
        WritingLog.user_id == user.id, WritingLog.on == today))

m = st.columns(5)
m[0].metric("원고", f"{len(works)}편")
m[1].metric("총 분량", f"{sum((w.stats or {}).get('chars', 0) for w in works):,}자")
m[2].metric("번역본", f"{n_tr}개")
m[3].metric("전자책", f"{n_eb}권")
m[4].metric("진행 중인 투고", f"{sum(x.status in ('준비 중', '발송', '검토 중', '수정 요청') for x in subs)}건")

if not works:
    st.info("처음이시군요! 아래 순서대로 따라 하면 원고가 전자책과 홍보물이 됩니다.")
st.markdown("#### 작업 흐름")
steps = [("views/library.py", "① 올리기", "📚", "자동 분석·분류"), ("views/editor.py", "② 편집", "✍️", "형식별 온라인 편집"),
         ("views/translate.py", "③ 번역", "🌐", "10개 언어"), ("views/ebook.py", "④ 전자책", "📖", "EPUB · PDF"),
         ("views/promo.py", "⑤ 홍보", "📣", "영상·문구·태그"), ("views/directory.py", "⑥ 투고", "🌍", "에이전시·출판사")]
for col, (page, label, icon, desc) in zip(st.columns(6), steps):
    with col.container(border=True):
        st.page_link(page, label=label, icon=icon)
        st.caption(desc)

a, b = st.columns([1.4, 1], gap="large")
with a:
    st.markdown("#### 최근 원고")
    if works:
        for w in works[:6]:
            st.markdown(f"{KIND_ICON.get(w.kind, '')} **{html.escape(w.title)}** · {w.genre or '미분류'} · {w.length_class or KIND_LABEL[w.kind]} · "
                        f"{(w.stats or {}).get('chars', 0):,}자 · {LANGS.get(w.lang, w.lang)} · {w.status}  \n"
                        f"<small>수정 {fmt_dt(w.updated_at)}</small>", unsafe_allow_html=True)
    else:
        st.caption("아직 원고가 없습니다.")
with b:
    st.markdown("#### 다가오는 일정 (30일)")
    if events:
        for e in events[:8]:
            d = (e.on - today).days
            tag = f"D-{d}" if d > 0 else "오늘" if d == 0 else f"{-d}일 지남"
            st.markdown(f"**{tag}** · {e.on} · {e.kind} · {e.title}")
    else:
        st.caption("예정된 일정이 없습니다.")
    st.markdown("#### 오늘의 집필")
    st.write(f"{wrote:,}자 기록됨")
    st.page_link("views/planner.py", label="집필 기록하러 가기", icon="🗓️")

with st.expander("연결 상태 (어떤 기능이 켜져 있나요?)"):
    def row(ok, name, off_msg):
        st.markdown(f"{'🟢' if ok else '⚪'} **{name}** — {'사용 중' if ok else off_msg}")
    row(ai_ready(), "AI (Claude)", "꺼짐 · 장르 분석·번역·홍보 문구가 간이 방식으로 동작합니다 (ANTHROPIC_API_KEY)")
    row(is_persistent(), "영구 저장소", "꺼짐 · 서버 재시작 시 데이터가 지워집니다 (DATABASE_URL)")
    row(smtp_ready(), "메일 발송", "꺼짐 · 인증 메일·원터치 투고 직접 발송을 쓸 수 없습니다 (SMTP_*)")
    for p, cfg in PROVIDERS.items():
        row(provider_ready(p), f"{cfg['label']} 로그인", f"꺼짐 ({p.upper()}_CLIENT_ID / _SECRET)")
    st.caption("설정 방법은 저장소의 README.md 를 참고하세요.")
