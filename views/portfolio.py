"""공개 작가 소개 페이지 ( ?author=아이디 ). 작가가 공개를 켠 경우에만 보인다."""
import streamlit as st

from core.auth import find_user
from core.config import APP_NAME


def render(username: str):
    u = find_user(username)
    if not u or not u.public_profile or "@" in username:
        st.error("공개된 작가 페이지가 없습니다.")
        return
    c1, c2 = st.columns([1, 3], gap="large")
    if u.photo:
        c1.image(u.photo, use_container_width=True)
    with c2:
        st.title(u.display)
        st.caption(" · ".join(u.writer_types))
        if u.debut:
            st.write(u.debut)
    if u.bio:
        st.markdown("#### 작가 소개")
        st.write(u.bio)
    if u.major_works.strip():
        st.markdown("#### 대표작")
        st.markdown("\n".join(f"- {ln.strip()}" for ln in u.major_works.split("\n") if ln.strip()))
    links = {"instagram": "Instagram", "youtube": "YouTube", "x": "X", "website": "홈페이지"}
    sns = [(links[k], v) for k, v in (u.sns or {}).items() if k in links and v]
    if sns:
        st.markdown("#### 링크")
        for label, v in sns:
            if v.startswith(("http://", "https://")):
                st.markdown(f"- [{label}]({v})")
            else:
                st.markdown(f"- {label}: {v}")
    st.divider()
    st.caption(f"✒️ {APP_NAME}")
