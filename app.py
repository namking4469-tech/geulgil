"""글길 — 작가를 위한 올인원 플랫폼 (Streamlit 진입점).
실행:  streamlit run app.py
"""
import streamlit as st

from core import theme
from core.auth import current_user, flush_cookie_op, handle_oauth_callback, logout
from core.config import APP_NAME, APP_TAGLINE, using_dev_secret
from core.db import is_persistent

st.set_page_config(page_title=f"{APP_NAME} · {APP_TAGLINE}", page_icon="✒️", layout="wide")

flush_cookie_op()
oauth_error = handle_oauth_callback()
if oauth_error:
    st.session_state["_oauth_error"] = oauth_error

# 공개 작가 소개 페이지:  ?author=아이디
if "author" in st.query_params:
    theme.apply(None)
    from views.portfolio import render
    render(st.query_params["author"])
    st.stop()

user = current_user()
theme.apply(user)

if not user:
    pg = st.navigation([st.Page("views/login.py", title="로그인 · 작가 등록", icon="🔑")], position="hidden")
    pg.run()
    st.stop()

pages = {
    "": [st.Page("views/home.py", title="대시보드", icon="🏠", default=True)],
    "원고": [
        st.Page("views/library.py", title="원고 서재", icon="📚"),
        st.Page("views/editor.py", title="편집실", icon="✍️"),
        st.Page("views/translate.py", title="번역", icon="🌐"),
    ],
    "출간": [
        st.Page("views/ebook.py", title="전자책 · ISBN", icon="📖"),
        st.Page("views/promo.py", title="홍보 스튜디오", icon="📣"),
    ],
    "세상으로": [
        st.Page("views/contests.py", title="공모전", icon="🏆"),
        st.Page("views/directory.py", title="에이전시 · 출판사", icon="🌍"),
        st.Page("views/submissions.py", title="투고 관리", icon="📮"),
    ],
    "작가 생활": [
        st.Page("views/planner.py", title="집필 목표 · 일정", icon="🗓️"),
        st.Page("views/finance.py", title="수익 · 계약", icon="💰"),
        st.Page("views/profile.py", title="내 프로필 · 보안", icon="👤"),
    ],
}
if user.is_admin:
    pages["관리"] = [st.Page("views/admin.py", title="관리자", icon="🛠️")]

pg = st.navigation(pages, expanded=True)

with st.sidebar:
    c1, c2 = st.columns([1, 2.4], vertical_alignment="center")
    if user.photo:
        c1.image(user.photo, width=56)
    else:
        c1.markdown("## ✒️")
    c2.markdown(f"**{user.display}**  \n{' · '.join(user.writer_types[:2]) or '작가'}")
    theme.picker(user)
    if st.button("로그아웃", use_container_width=True):
        logout()
        st.rerun()
    if not is_persistent():
        st.caption("⚠️ 임시 저장소 사용 중: 서버가 재시작되면 데이터가 지워집니다. (README의 DATABASE_URL 설정 참고)")
    if using_dev_secret():
        st.caption("⚠️ APP_SECRET 미설정: 개발용 기본 키를 쓰고 있습니다.")

if st.session_state.pop("_welcome", False):
    st.toast("가입을 환영합니다! '내 프로필'에서 작가 정보를 채워 주세요.", icon="🎉")

pg.run()
