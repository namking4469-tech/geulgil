"""로그인 · 작가 등록 · 비밀번호 찾기."""
from datetime import date

import streamlit as st

from core import auth
from core.config import APP_NAME, APP_TAGLINE, WRITER_TYPES
from core.mailer import smtp_ready
from core.ui import square_jpeg

ss = st.session_state

st.markdown(f"# ✒️ {APP_NAME}")
st.caption(f"{APP_TAGLINE} — 원고 관리부터 번역, 전자책, 홍보, 투고까지 한곳에서.")

if ss.get("_oauth_error"):
    st.error(ss.pop("_oauth_error"))


def finish(u, method: str):
    """1차 인증 성공 뒤: OTP 를 켠 계정은 2단계로, 아니면 로그인 완료."""
    if u.totp_enabled and method in ("password", "face", "email_code"):
        ss["pending_2fa"] = (u.id, method)
    else:
        auth.login_user(u, method)
    st.rerun()


def show_code_notice(sent: bool, info: str, email: str):
    if sent:
        st.success(f"{email} 로 인증코드를 보냈습니다. 10분 안에 입력해 주세요.")
    elif smtp_ready():
        st.error(f"메일 발송 실패: {info}")
    else:
        st.warning(f"메일 서버(SMTP)가 아직 설정되지 않아 **개발 모드**로 코드를 화면에 표시합니다: `{info}`  \n"
                   "실제 운영 전에는 README 의 SMTP 설정을 꼭 해 주세요.")


# ------------------------------------------------------------ 2단계 인증
if ss.get("pending_2fa"):
    uid, method = ss["pending_2fa"]
    u = auth.get_user(uid)
    st.subheader("2단계 인증")
    st.write("인증 앱(Google Authenticator 등)에 표시된 6자리 코드를 입력해 주세요.")
    with st.form("otp"):
        code = st.text_input("OTP 코드", max_chars=6)
        ok = st.form_submit_button("확인", type="primary")
    if ok:
        if u and not auth.is_locked(u) and auth.totp_check(u.totp_secret, code):
            auth.login_user(u, method + "+otp")
            st.rerun()
        else:
            if u:
                auth.register_fail(u, "otp")
            st.error("코드가 맞지 않습니다.")
    if st.button("처음으로"):
        ss.pop("pending_2fa")
        st.rerun()
    st.stop()

tab_login, tab_join, tab_reset = st.tabs(["로그인", "작가 등록", "비밀번호 찾기"])

# ------------------------------------------------------------ 로그인
with tab_login:
    left, right = st.columns([1.2, 1], gap="large")
    with right:
        st.markdown("#### 간편 로그인 / 간편 가입")
        st.caption("처음이면 자동으로 작가 계정이 만들어집니다. 로그인 창은 새 탭에서 열리고, 로그인이 끝나면 그 탭에서 "
                   "앱이 이어집니다.")
        for p, cfg in auth.PROVIDERS.items():
            if auth.provider_ready(p):
                # Streamlit Cloud 는 앱을 제한된 틀(iframe) 안에 띄운다. 틀 안 이동은 로그인 제공사가 거부하고,
                # 창 전체 이동은 틀의 제한으로 막히므로, 새 탭으로 여는 기본 링크 버튼을 쓴다.
                st.link_button(f"{cfg['label']} 계정으로 계속하기", auth.oauth_url(p), type="primary",
                               use_container_width=True)
            else:
                st.button(f"{cfg['label']} 계정으로 계속하기", disabled=True, use_container_width=True, key=f"so_{p}",
                          help=f"관리자가 {p.upper()}_CLIENT_ID / {p.upper()}_CLIENT_SECRET 을 설정하면 켜집니다. (README 참고)")
    with left:
        m_pw, m_face, m_pk, m_mail = st.tabs(["비밀번호", "얼굴 인식", "패스키(지문·Face ID)", "이메일 코드"])
        with m_pw:
            with st.form("login_pw"):
                ident = st.text_input("아이디 또는 이메일")
                pw = st.text_input("비밀번호", type="password")
                ok = st.form_submit_button("로그인", type="primary", use_container_width=True)
            if ok:
                u = auth.find_user(ident)
                if u and auth.is_locked(u):
                    st.error(f"로그인 실패가 반복되어 계정이 잠겼습니다. {auth.LOCK_MIN}분 뒤 다시 시도해 주세요.")
                elif u and auth.check_pw(pw, u.pw_hash):
                    finish(u, "password")
                else:
                    if u:
                        auth.register_fail(u, "password")
                    st.error("아이디 또는 비밀번호가 맞지 않습니다.")
        with m_face:
            st.caption("프로필 · 보안에서 얼굴을 등록한 계정만 쓸 수 있습니다. 사진은 저장하지 않고 비교에만 씁니다.")
            f_ident = st.text_input("아이디 또는 이메일", key="face_ident")
            if st.toggle("카메라 켜기", key="face_cam_on"):
                shot = st.camera_input("정면을 보고 촬영해 주세요", key="face_shot")
                if shot and st.button("얼굴로 로그인", type="primary"):
                    u = auth.find_user(f_ident)
                    if not u or not u.face_login or not u.face_enc:
                        st.error("얼굴 로그인을 쓸 수 없는 계정입니다.")
                    elif auth.is_locked(u):
                        st.error("계정이 잠겨 있습니다. 잠시 후 다시 시도해 주세요.")
                    else:
                        vec, err = auth.face_embedding(shot.getvalue())
                        if err:
                            st.error(err)
                        elif auth.face_similarity(u, vec) >= auth.FACE_THRESHOLD:
                            finish(u, "face")
                        else:
                            auth.register_fail(u, "face")
                            st.error("등록된 얼굴과 일치하지 않습니다.")
        with m_pk:
            st.caption("기기에 등록한 지문 · Face ID · Windows Hello · 보안 키로 로그인합니다. "
                       "프로필 · 보안에서 패스키를 먼저 등록해야 합니다.")
            pk_ident = st.text_input("아이디 또는 이메일 (비워 두면 기기에 저장된 패스키에서 고릅니다)", key="pk_ident")
            if st.button("패스키 로그인 준비"):
                u = auth.find_user(pk_ident) if pk_ident.strip() else None
                ss["pk_login_opts"] = auth.passkey_auth_options(u)
            if ss.get("pk_login_opts"):
                resp = auth.passkey_button("login", ss["pk_login_opts"], "🔐 패스키로 로그인", key="pk_login")
                if resp:
                    ss.pop("pk_login_opts")
                    u, err = auth.passkey_auth_verify(resp)
                    if u:
                        auth.login_user(u, "passkey")
                        st.rerun()
                    st.error(err)
        with m_mail:
            st.caption("가입한 이메일로 1회용 코드를 받아 로그인합니다.")
            em = st.text_input("이메일", key="mail_login_email")
            if not smtp_ready():
                st.info("메일 서버(SMTP)를 설정해야 쓸 수 있는 기능입니다. (README 참고)")
            if st.button("코드 받기", disabled=not smtp_ready()):
                u = auth.find_user(em)
                if u:
                    ss["mail_login"] = (u.email, *auth.send_code(u.email, "login"))
                else:
                    st.error("가입되지 않은 이메일입니다.")
            if ss.get("mail_login"):
                email, sent, info = ss["mail_login"]
                show_code_notice(sent, info, email)
                code = st.text_input("인증코드 6자리", key="mail_login_code", max_chars=6)
                if st.button("코드로 로그인", type="primary"):
                    u = auth.find_user(email)
                    if u and auth.verify_code(email, "login", code):
                        ss.pop("mail_login")
                        auth.update_user(u.id, email_verified=True)
                        finish(u, "email_code")
                    else:
                        st.error("코드가 맞지 않거나 만료되었습니다.")

# ------------------------------------------------------------ 작가 등록
with tab_join:
    reg = ss.get("reg")
    if reg:  # 2단계: 이메일 인증
        st.subheader("이메일 인증")
        show_code_notice(reg["sent"], reg["info"], reg["data"]["email"])
        code = st.text_input("인증코드 6자리", max_chars=6, key="reg_code")
        c1, c2 = st.columns(2)
        if c1.button("등록 완료", type="primary", use_container_width=True):
            if auth.verify_code(reg["data"]["email"], "signup", code):
                u = auth.create_user(**reg["data"], email_verified=True)
                ss.pop("reg")
                ss["_welcome"] = True
                auth.login_user(u, "signup")
                st.rerun()
            else:
                st.error("코드가 맞지 않거나 만료되었습니다.")
        if c2.button("입력 화면으로 돌아가기", use_container_width=True):
            ss.pop("reg")
            st.rerun()
    else:
        st.caption("＊ 표시는 필수 항목입니다. 나머지는 가입 후 '내 프로필'에서 언제든 채울 수 있습니다.")
        st.markdown("##### 계정")
        c1, c2 = st.columns(2)
        username = c1.text_input("아이디＊", help="영문 소문자·숫자·밑줄 4~20자", key="r_username")
        email = c2.text_input("이메일＊", key="r_email")
        pw = c1.text_input("비밀번호＊", type="password", help="8자 이상, 영문과 숫자 포함", key="r_pw")
        pw2 = c2.text_input("비밀번호 확인＊", type="password", key="r_pw2")

        st.markdown("##### 기본 정보")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("이름(실명)＊", key="r_name")
        pen = c2.text_input("필명", key="r_pen")
        birth = c3.date_input("생년월일＊", value=None, min_value=date(1900, 1, 1), max_value=date.today(), key="r_birth")
        gender = c1.selectbox("성별", ["밝히지 않음", "여성", "남성", "기타"], key="r_gender")
        phone = c2.text_input("휴대전화", placeholder="010-0000-0000", key="r_phone")
        country = c3.text_input("국가", value="대한민국", key="r_country")
        address = st.text_input("주소", key="r_addr")

        st.markdown("##### 작가 정보")
        types = st.multiselect("작가 유형＊ (여러 개 선택 가능)", WRITER_TYPES, key="r_types")
        debut = st.text_input("등단·데뷔 정보", placeholder="예: 2020년 ○○일보 신춘문예 단편소설 당선 / 미등단", key="r_debut")
        bio = st.text_area("작가 소개", height=100, key="r_bio")
        works = st.text_area("대표작 (한 줄에 하나씩)", height=80, key="r_works")
        c1, c2 = st.columns(2)
        sns = {"instagram": c1.text_input("Instagram", key="r_ig"), "youtube": c2.text_input("YouTube", key="r_yt"),
               "x": c1.text_input("X(Twitter)", key="r_x"), "website": c2.text_input("블로그·홈페이지", key="r_web")}

        st.markdown("##### 작가 사진")
        how = st.radio("사진 넣는 방법", ["나중에", "카메라로 촬영", "이미지 파일 올리기"], horizontal=True, key="r_how")
        photo_raw = None
        if how == "카메라로 촬영":
            shot = st.camera_input("촬영", key="r_cam")
            photo_raw = shot.getvalue() if shot else None
        elif how == "이미지 파일 올리기":
            up = st.file_uploader("이미지 선택", type=["jpg", "jpeg", "png", "webp"], key="r_up")
            photo_raw = up.getvalue() if up else None
        photo = None
        if photo_raw:
            try:
                photo = square_jpeg(photo_raw)
                st.image(photo, width=160, caption="등록될 사진(프로필에서 다시 자를 수 있습니다)")
            except Exception:
                st.error("이미지를 읽을 수 없습니다. 다른 파일을 올려 주세요.")

        st.markdown("##### 약관 동의")
        with st.expander("이용약관 · 개인정보 수집 및 이용 안내 보기"):
            st.markdown(
                "- **수집 항목**: 아이디, 이메일, 이름, 생년월일, (선택) 필명·연락처·주소·사진·작가 정보\n"
                "- **이용 목적**: 회원 식별, 작가 서비스 제공(원고 보관·번역·전자책·투고 지원)\n"
                "- **보관 기간**: 회원 탈퇴 시 즉시 삭제\n"
                "- 올린 원고의 저작권은 전적으로 작가에게 있으며, 서비스는 작가가 요청한 처리에만 원고를 사용합니다.\n"
                "- AI 분석·번역 기능을 쓰면 해당 원고 내용이 AI 제공사(Anthropic) 또는 번역 서비스로 전송됩니다.\n\n"
                "※ 이 문구는 예시입니다. 실제 운영 시에는 운영자의 약관·개인정보처리방침으로 바꿔야 합니다.")
        a1 = st.checkbox("이용약관에 동의합니다＊", key="r_a1")
        a2 = st.checkbox("개인정보 수집·이용에 동의합니다＊", key="r_a2")
        a3 = st.checkbox("만 14세 이상입니다＊", key="r_a3")
        a4 = st.checkbox("새 소식·공모전 알림 메일 수신에 동의합니다 (선택)", key="r_a4")

        if st.button("작가 등록", type="primary", use_container_width=True):
            import re
            errs = []
            if not re.fullmatch(r"[a-z0-9_]{4,20}", username or ""):
                errs.append("아이디는 영문 소문자·숫자·밑줄 4~20자로 입력해 주세요.")
            elif auth.find_user(username):
                errs.append("이미 쓰이고 있는 아이디입니다.")
            if not auth.valid_email(email):
                errs.append("이메일 형식이 올바르지 않습니다.")
            elif auth.find_user(email):
                errs.append("이미 가입된 이메일입니다.")
            if auth.pw_problems(pw):
                errs.append("비밀번호 조건: " + ", ".join(auth.pw_problems(pw)))
            if pw != pw2:
                errs.append("비밀번호 확인이 일치하지 않습니다.")
            if not name.strip():
                errs.append("이름을 입력해 주세요.")
            if not birth:
                errs.append("생년월일을 입력해 주세요.")
            if not types:
                errs.append("작가 유형을 하나 이상 골라 주세요.")
            if not (a1 and a2 and a3):
                errs.append("필수 약관에 모두 동의해 주세요.")
            if errs:
                for e in errs:
                    st.error(e)
            else:
                data = dict(username=username, email=email.strip(), pw_hash=auth.hash_pw(pw), name=name.strip(),
                            pen_name=pen.strip(), birth=birth, gender=gender, phone=phone, country=country,
                            address=address, writer_types=types, debut=debut, bio=bio, major_works=works,
                            sns={k: v for k, v in sns.items() if v}, photo=photo, agree_marketing=a4)
                sent, info = auth.send_code(email.strip(), "signup")
                ss["reg"] = {"data": data, "sent": sent, "info": info}
                st.rerun()

# ------------------------------------------------------------ 비밀번호 찾기
with tab_reset:
    st.caption("가입한 이메일로 인증코드를 받아 새 비밀번호를 정합니다.")
    em = st.text_input("가입 이메일", key="reset_email")
    if not smtp_ready():
        st.info("메일 서버(SMTP)를 설정해야 쓸 수 있는 기능입니다. 그 전에는 관리자에게 비밀번호 초기화를 요청해 주세요.")
    if st.button("인증코드 받기", key="reset_send", disabled=not smtp_ready()):
        u = auth.find_user(em)
        if u:
            ss["reset"] = (u.email, *auth.send_code(u.email, "reset"))
        else:
            st.error("가입되지 않은 이메일입니다.")
    if ss.get("reset"):
        email, sent, info = ss["reset"]
        show_code_notice(sent, info, email)
        with st.form("reset_form"):
            code = st.text_input("인증코드 6자리", max_chars=6)
            npw = st.text_input("새 비밀번호", type="password")
            ok = st.form_submit_button("비밀번호 바꾸기", type="primary")
        if ok:
            if auth.pw_problems(npw):
                st.error("비밀번호 조건: " + ", ".join(auth.pw_problems(npw)))
            elif auth.verify_code(email, "reset", code):
                u = auth.find_user(email)
                auth.update_user(u.id, pw_hash=auth.hash_pw(npw), failed_logins=0, locked_until=None)
                ss.pop("reset")
                st.success("비밀번호를 바꿨습니다. 로그인 탭에서 로그인해 주세요.")
            else:
                st.error("코드가 맞지 않거나 만료되었습니다.")
