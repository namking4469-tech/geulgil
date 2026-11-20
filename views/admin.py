"""관리자: 회원 · 공모전 DB · 에이전시/출판사 DB."""
import secrets

import pandas as pd
import streamlit as st

from core import auth
from core.config import GENRES
from core.db import Contest, DirEntry, User, Work, db, func, select
from core.ui import fmt_dt, header, require_login

user = require_login()
if not user.is_admin:
    st.error("관리자만 볼 수 있습니다.")
    st.stop()
header("🛠️ 관리자", "회원과 공모전·주소록 데이터를 관리합니다. (처음 가입한 계정과 ADMIN_EMAILS 의 계정이 관리자입니다)")

t_users, t_contest, t_dir = st.tabs(["회원", "공모전 DB", "에이전시 · 출판사 DB"])

with t_users:
    with db() as s:
        users = list(s.scalars(select(User).order_by(User.created_at.desc())))
        counts = dict(s.execute(select(Work.user_id, func.count()).group_by(Work.user_id)).all())
    st.dataframe(pd.DataFrame([{
        "아이디": u.username, "이메일": u.email, "이름": u.name, "필명": u.pen_name, "유형": ", ".join(u.writer_types),
        "가입 경로": u.provider, "원고 수": counts.get(u.id, 0), "관리자": u.is_admin, "OTP": u.totp_enabled,
        "가입일": fmt_dt(u.created_at)} for u in users]), hide_index=True, use_container_width=True)
    by = {u.id: u for u in users}
    uid = st.selectbox("회원 선택", list(by), format_func=lambda i: f"{by[i].username} ({by[i].email})")
    u = by[uid]
    c = st.columns(3)
    if c[0].button("임시 비밀번호 발급"):
        tmp = secrets.token_urlsafe(9)
        auth.update_user(u.id, pw_hash=auth.hash_pw(tmp), failed_logins=0, locked_until=None)
        st.success("임시 비밀번호를 설정했습니다. 본인에게 안전하게 전달하고, 로그인 후 바꾸도록 안내하세요.")
        st.code(tmp, language=None)
    if c[1].button("잠금 해제"):
        auth.update_user(u.id, failed_logins=0, locked_until=None)
        st.success("해제했습니다.")
    if u.id != user.id and c[2].button("관리자 해제" if u.is_admin else "관리자로 지정"):
        auth.update_user(u.id, is_admin=not u.is_admin)
        st.rerun()


def csv_list(v) -> list[str]:
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


with t_contest:
    st.caption("행을 고치거나 맨 아래에 새 행을 추가한 뒤 저장하세요. 장르는 쉼표로 구분합니다. "
               f"마감일은 **공식 공고를 확인한 경우에만** 입력하세요. (장르 예: {', '.join(GENRES[:6])} …)")
    with db() as s:
        rows = list(s.scalars(select(Contest).order_by(Contest.name)))
    df = pd.DataFrame([{"id": r.id, "이름": r.name, "주최": r.organizer, "국가": r.country, "장르": ", ".join(r.genres),
                        "분량": r.length, "통상 시기": r.period, "마감일": r.deadline, "상금": r.prize,
                        "자격": r.eligibility, "URL": r.url, "메모": r.note} for r in rows])
    out = st.data_editor(df, hide_index=True, use_container_width=True, num_rows="dynamic", key="adm_contest",
                         column_config={"id": None, "마감일": st.column_config.DateColumn()})
    if st.button("공모전 저장", type="primary"):
        with db() as s:
            keep = set()
            for _, r in out.iterrows():
                if not str(r["이름"] or "").strip() or str(r["이름"]) == "nan":
                    continue
                row = s.get(Contest, int(r["id"])) if pd.notna(r["id"]) else None
                if not row:
                    row = Contest(name="")
                    s.add(row)
                row.name, row.organizer, row.country = r["이름"], r["주최"] or "", r["국가"] or ""
                row.genres, row.length, row.period = csv_list(r["장르"]), r["분량"] or "", r["통상 시기"] or ""
                row.deadline = r["마감일"] if pd.notna(r["마감일"]) else None
                row.prize, row.eligibility, row.url, row.note = r["상금"] or "", r["자격"] or "", r["URL"] or "", r["메모"] or ""
                s.flush()
                keep.add(row.id)
            for old in rows:
                if old.id not in keep:
                    s.delete(s.get(Contest, old.id))
        st.success("저장했습니다.")
        st.rerun()

with t_dir:
    st.caption("투고 이메일은 **공식 사이트에서 확인한 주소만** 넣어 주세요. 여기 넣은 주소는 모든 작가의 원터치 소개에 기본값으로 뜹니다.")
    with db() as s:
        rows = list(s.scalars(select(DirEntry).order_by(DirEntry.kind, DirEntry.name)))
    df = pd.DataFrame([{"id": r.id, "종류": r.kind, "이름": r.name, "국가": r.country, "장르": ", ".join(r.genres),
                        "접수 방식": r.accepts, "URL": r.url, "투고 이메일": r.email, "메모": r.note} for r in rows])
    out = st.data_editor(df, hide_index=True, use_container_width=True, num_rows="dynamic", key="adm_dir",
                         column_config={"id": None, "종류": st.column_config.SelectboxColumn(
                             options=["에이전시", "출판사", "플랫폼", "지원기관"], required=True)})
    if st.button("주소록 저장", type="primary"):
        with db() as s:
            keep = set()
            for _, r in out.iterrows():
                if not str(r["이름"] or "").strip() or str(r["이름"]) == "nan":
                    continue
                row = s.get(DirEntry, int(r["id"])) if pd.notna(r["id"]) else None
                if not row:
                    row = DirEntry(kind=r["종류"] or "출판사", name="")
                    s.add(row)
                row.kind, row.name, row.country = r["종류"], r["이름"], r["국가"] or ""
                row.genres, row.accepts, row.url = csv_list(r["장르"]), r["접수 방식"] or "", r["URL"] or ""
                row.email, row.note = r["투고 이메일"] or "", r["메모"] or ""
                s.flush()
                keep.add(row.id)
            for old in rows:
                if old.id not in keep:
                    s.delete(s.get(DirEntry, old.id))
        st.success("저장했습니다.")
        st.rerun()
