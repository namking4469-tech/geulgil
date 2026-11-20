"""내 프로필 · 보안 설정."""
from datetime import date

import streamlit as st

from core import auth
from core.config import WRITER_TYPES, base_url
from core.db import (Contract, Ebook, Event, Finance, LoginLog, Passkey, Promo, SessionToken, Setting, Submission,
                     Translation, User, Version, Work, WritingLog, db, select)
from core.ui import fmt_dt, header, require_login, square_jpeg

user = require_login()
ss = st.session_state
header("👤 내 프로필 · 보안", "작가 정보와 로그인 수단을 관리합니다.")

t_info, t_photo, t_sec, t_log, t_out = st.tabs(["작가 정보", "작가 사진", "로그인 수단", "접속 기록", "탈퇴"])

# ------------------------------------------------------------ 작가 정보
with t_info:
    with st.form("profile"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("이름(실명)", user.name)
        pen = c2.text_input("필명", user.pen_name)
        birth = c3.date_input("생년월일", user.birth, min_value=date(1900, 1, 1), max_value=date.today())
        genders = ["밝히지 않음", "여성", "남성", "기타"]
        gender = c1.selectbox("성별", genders, index=genders.index(user.gender) if user.gender in genders else 0)
        phone = c2.text_input("휴대전화", user.phone)
        country = c3.text_input("국가", user.country)
        address = st.text_input("주소", user.address)
        types = st.multiselect("작가 유형", WRITER_TYPES, [t for t in user.writer_types if t in WRITER_TYPES])
        debut = st.text_input("등단·데뷔 정보", user.debut)
        bio = st.text_area("작가 소개 (전자책 '지은이 소개'와 투고 편지에 쓰입니다)", user.bio, height=130)
        works = st.text_area("대표작 (한 줄에 하나씩)", user.major_works, height=90)
        c1, c2 = st.columns(2)
        sns = dict(user.sns or {})
        sns_new = {"instagram": c1.text_input("Instagram", sns.get("instagram", "")),
                   "youtube": c2.text_input("YouTube", sns.get("youtube", "")),
                   "x": c1.text_input("X(Twitter)", sns.get("x", "")),
                   "website": c2.text_input("블로그·홈페이지", sns.get("website", ""))}
        public = st.checkbox("공개 작가 소개 페이지 켜기 (이름·필명·소개·대표작·사진·SNS 만 공개)", user.public_profile)
        marketing = st.checkbox("새 소식·공모전 알림 메일 수신", user.agree_marketing)
        if st.form_submit_button("저장", type="primary"):
            auth.update_user(user.id, name=name, pen_name=pen, birth=birth, gender=gender, phone=phone,
                             country=country, address=address, writer_types=types, debut=debut, bio=bio,
                             major_works=works, sns={k: v for k, v in sns_new.items() if v},
                             public_profile=public, agree_marketing=marketing)
            st.success("저장했습니다.")
            st.rerun()
    st.caption(f"아이디 `{user.username}` · 이메일 `{user.email}` · 가입 {fmt_dt(user.created_at)} · "
               f"가입 경로 {auth.PROVIDERS.get(user.provider, {}).get('label', '일반')}")
    if user.public_profile:
        st.markdown("**내 공개 페이지 주소** (복사해서 SNS 프로필에 넣으세요)")
        st.code(f"{base_url()}/?author={user.username}", language=None)

# ------------------------------------------------------------ 사진
with t_photo:
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        st.markdown("**현재 사진**")
        if user.photo:
            st.image(user.photo, width=220)
            if st.button("사진 지우기"):
                auth.update_user(user.id, photo=None)
                st.rerun()
        else:
            st.info("등록된 사진이 없습니다.")
    with c2:
        how = st.radio("새 사진", ["카메라로 촬영", "이미지 파일 올리기"], horizontal=True)
        raw = None
        if how == "카메라로 촬영":
            if st.toggle("카메라 켜기"):
                shot = st.camera_input("촬영")
                raw = shot.getvalue() if shot else None
        else:
            up = st.file_uploader("이미지 선택", type=["jpg", "jpeg", "png", "webp"])
            raw = up.getvalue() if up else None
        if raw:
            st.markdown("**자르기**")
            k1, k2, k3 = st.columns(3)
            zoom = k1.slider("확대(%)", 100, 300, 100, 10)
            cx = k2.slider("가로 위치", 0, 100, 50)
            cy = k3.slider("세로 위치", 0, 100, 50)
            try:
                out = square_jpeg(raw, box=(cx, cy, zoom))
                st.image(out, width=220, caption="미리보기")
                if st.button("이 사진으로 저장", type="primary"):
                    auth.update_user(user.id, photo=out)
                    st.rerun()
            except Exception:
                st.error("이미지를 읽을 수 없습니다.")

# ------------------------------------------------------------ 로그인 수단
with t_sec:
    st.markdown("#### 🔑 비밀번호")
    with st.form("pw"):
        cur = st.text_input("현재 비밀번호", type="password") if user.pw_hash else ""
        if not user.pw_hash:
            st.caption("소셜 계정으로 가입해 아직 비밀번호가 없습니다. 새로 정하면 아이디/비밀번호로도 로그인할 수 있습니다.")
        n1 = st.text_input("새 비밀번호", type="password")
        n2 = st.text_input("새 비밀번호 확인", type="password")
        if st.form_submit_button("비밀번호 바꾸기"):
            if user.pw_hash and not auth.check_pw(cur, user.pw_hash):
                st.error("현재 비밀번호가 맞지 않습니다.")
            elif auth.pw_problems(n1):
                st.error("비밀번호 조건: " + ", ".join(auth.pw_problems(n1)))
            elif n1 != n2:
                st.error("새 비밀번호 확인이 일치하지 않습니다.")
            else:
                auth.update_user(user.id, pw_hash=auth.hash_pw(n1))
                st.success("비밀번호를 바꿨습니다.")

    st.divider()
    st.markdown("#### 📱 OTP 2단계 인증")
    if user.totp_enabled:
        st.success("켜져 있습니다. 비밀번호·얼굴·이메일 코드 로그인 뒤 OTP 코드를 한 번 더 확인합니다.")
        with st.form("otp_off"):
            code = st.text_input("끄려면 현재 OTP 코드 입력", max_chars=6)
            if st.form_submit_button("OTP 끄기"):
                if auth.totp_check(user.totp_secret, code):
                    auth.update_user(user.id, totp_enabled=False, totp_secret="")
                    st.rerun()
                else:
                    st.error("코드가 맞지 않습니다.")
    else:
        st.caption("Google Authenticator, Microsoft Authenticator, Authy 같은 인증 앱을 씁니다.")
        if st.button("OTP 설정 시작"):
            ss["otp_setup"] = auth.totp_new_secret()
        if ss.get("otp_setup"):
            c1, c2 = st.columns([1, 2])
            c1.image(auth.qr_png(auth.totp_uri(user, ss["otp_setup"])), width=200)
            with c2:
                st.write("① 인증 앱에서 QR 코드를 스캔하고 ② 앱에 뜬 6자리 코드를 입력하세요.")
                st.code(ss["otp_setup"], language=None)
                with st.form("otp_on"):
                    code = st.text_input("OTP 코드", max_chars=6)
                    if st.form_submit_button("확인하고 켜기", type="primary"):
                        if auth.totp_check(ss["otp_setup"], code):
                            auth.update_user(user.id, totp_secret=ss.pop("otp_setup"), totp_enabled=True)
                            st.rerun()
                        else:
                            st.error("코드가 맞지 않습니다. 휴대전화 시간이 자동 설정인지 확인해 주세요.")

    st.divider()
    st.markdown("#### 🙂 얼굴 인식 로그인")
    st.caption("사진은 저장하지 않습니다. 얼굴에서 뽑은 숫자 벡터(128차원)만 암호화해 보관하며, 언제든 삭제할 수 있습니다. "
               "사진·영상으로 속이는 것을 막는 '실물 감지'는 없으므로 OTP 와 함께 쓰는 것을 권합니다.")
    if user.face_enc:
        st.success("얼굴이 등록되어 있습니다." + (" 얼굴 로그인 사용 중." if user.face_login else ""))
        c1, c2 = st.columns(2)
        if c1.button("얼굴 로그인 끄기" if user.face_login else "얼굴 로그인 켜기"):
            auth.update_user(user.id, face_login=not user.face_login)
            st.rerun()
        if c2.button("얼굴 정보 삭제"):
            auth.update_user(user.id, face_enc=None, face_login=False)
            st.rerun()
    consent = st.checkbox("얼굴 특징 정보(생체 인식 정보)를 로그인 목적으로 수집·이용하는 데 동의합니다.", key="face_consent")
    if consent and st.toggle("카메라 켜기", key="face_reg_cam"):
        shot = st.camera_input("밝은 곳에서 정면을 보고 촬영해 주세요", key="face_reg_shot")
        if shot and st.button("이 얼굴로 등록", type="primary"):
            vec, err = auth.face_embedding(shot.getvalue())
            if err:
                st.error(err)
            else:
                auth.update_user(user.id, face_enc=auth.face_encrypt(vec), face_login=True)
                st.success("얼굴을 등록했습니다.")
                st.rerun()

    st.divider()
    st.markdown("#### 🔐 패스키 (지문 · Face ID · Windows Hello · 보안 키)")
    st.caption("웹은 지문을 직접 읽지 않습니다. 기기가 지문·얼굴을 확인하고 서버에는 공개키만 저장되는 국제 표준(WebAuthn) 방식입니다. "
               "패스키는 등록한 주소(도메인)에서만 동작합니다.")
    with db() as s:
        keys = list(s.scalars(select(Passkey).where(Passkey.user_id == user.id)))
    for k in keys:
        c1, c2 = st.columns([4, 1])
        c1.write(f"• **{k.label}** — 등록 {fmt_dt(k.created_at)}")
        if c2.button("삭제", key=f"pkdel{k.id}"):
            with db() as s:
                s.delete(s.get(Passkey, k.id))
            st.rerun()
    label = st.text_input("기기 이름", placeholder="예: 내 아이폰, 회사 노트북", key="pk_label")
    if st.button("패스키 등록 준비"):
        ss["pk_reg_opts"] = auth.passkey_reg_options(user)
    if ss.get("pk_reg_opts"):
        resp = auth.passkey_button("register", ss["pk_reg_opts"], "🔐 이 기기를 패스키로 등록", key="pk_reg")
        if resp:
            ss.pop("pk_reg_opts")
            err = auth.passkey_reg_verify(user, resp, label)
            if err:
                st.error(err)
            else:
                st.success("패스키를 등록했습니다.")
                st.rerun()

# ------------------------------------------------------------ 접속 기록
with t_log:
    with db() as s:
        logs = list(s.scalars(select(LoginLog).where(LoginLog.user_id == user.id).order_by(LoginLog.at.desc()).limit(30)))
    if logs:
        st.dataframe([{"일시(UTC)": fmt_dt(g.at), "방법": g.method, "결과": "성공" if g.ok else "실패"} for g in logs],
                     hide_index=True, use_container_width=True)
    if st.button("다른 기기에서 모두 로그아웃"):
        with db() as s:
            for t in s.scalars(select(SessionToken).where(SessionToken.user_id == user.id)):
                s.delete(t)
        st.success("저장된 로그인 유지 정보를 모두 지웠습니다.")

# ------------------------------------------------------------ 탈퇴
with t_out:
    st.warning("탈퇴하면 계정, 원고, 번역, 전자책, 홍보물, 기록이 모두 **즉시 삭제**되며 되돌릴 수 없습니다. "
               "필요한 파일은 먼저 내려받아 주세요.")
    confirm = st.text_input(f"확인을 위해 아이디 `{user.username}` 를 입력하세요")
    if st.button("회원 탈퇴", type="primary", disabled=confirm != user.username):
        with db() as s:
            wids = list(s.scalars(select(Work.id).where(Work.user_id == user.id)))
            for model in (Version, Translation, Ebook, Promo):
                for row in s.scalars(select(model).where(model.work_id.in_(wids))):
                    s.delete(row)
            for model in (Work, Passkey, SessionToken, Submission, WritingLog, Event, Finance, Contract, LoginLog):
                for row in s.scalars(select(model).where(model.user_id == user.id)):
                    s.delete(row)
            st_row = s.get(Setting, user.id)
            if st_row:
                s.delete(st_row)
            s.delete(s.get(User, user.id))
        auth.logout()
        st.rerun()
