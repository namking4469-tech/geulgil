"""인증: 비밀번호, 로그인 유지 쿠키, 이메일 인증코드, OTP, 소셜(OAuth2), 얼굴 인식, 패스키."""
import base64
import hashlib
import hmac
import json
import re
import secrets as pysecrets
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import requests
import streamlit as st

from .config import ROOT, app_secret, base_url, secret, APP_NAME
from .db import LoginLog, OneTimeCode, Passkey, SessionToken, User, db, func, select

COOKIE = "geulgil_session"
MAX_FAILS, LOCK_MIN = 5, 10


# ---------------------------------------------------------------- 기본 도구
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def check_pw(pw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def pw_problems(pw: str) -> list[str]:
    out = []
    if len(pw) < 8:
        out.append("8자 이상")
    if not re.search(r"[A-Za-z]", pw):
        out.append("영문 포함")
    if not re.search(r"\d", pw):
        out.append("숫자 포함")
    return out


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _sign(msg: str) -> str:
    return hmac.new(app_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()[:40]


def valid_email(e: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e or ""))


# ---------------------------------------------------------------- 사용자·세션
def find_user(ident: str) -> User | None:
    ident = (ident or "").strip()
    if not ident:
        return None
    with db() as s:
        return s.scalar(select(User).where((func.lower(User.username) == ident.lower())
                                           | (func.lower(User.email) == ident.lower())))


def get_user(uid: int) -> User | None:
    with db() as s:
        return s.get(User, uid)


def current_user() -> User | None:
    uid = st.session_state.get("uid")
    if uid:
        u = get_user(uid)
        if u:
            return u
        st.session_state.pop("uid", None)
    # 로그인 유지 쿠키
    if st.session_state.get("_logged_out"):
        return None
    try:
        tok = st.context.cookies.get(COOKIE)
    except Exception:
        tok = None
    if tok:
        with db() as s:
            row = s.get(SessionToken, _sha(tok))
            if row and row.expires > datetime.utcnow():
                st.session_state["uid"] = row.user_id
                return s.get(User, row.user_id)
    return None


def create_user(**kw) -> User:
    with db() as s:
        first = not s.scalar(select(func.count()).select_from(User))
        admins = [a.strip().lower() for a in str(secret("ADMIN_EMAILS", "")).split(",") if a.strip()]
        u = User(**kw)
        u.is_admin = first or u.email.lower() in admins
        s.add(u)
        s.flush()
        return u


def update_user(uid: int, **kw):
    with db() as s:
        u = s.get(User, uid)
        for k, v in kw.items():
            setattr(u, k, v)


def log_login(uid, method, ok):
    with db() as s:
        s.add(LoginLog(user_id=uid, method=method, ok=ok))


def is_locked(u: User) -> bool:
    return bool(u.locked_until and u.locked_until > datetime.utcnow())


def register_fail(u: User, method: str):
    fails = u.failed_logins + 1
    kw = {"failed_logins": fails}
    if fails >= MAX_FAILS:
        kw = {"failed_logins": 0, "locked_until": datetime.utcnow() + timedelta(minutes=LOCK_MIN)}
    update_user(u.id, **kw)
    log_login(u.id, method, False)


def login_user(u: User, method: str, remember: bool = True):
    update_user(u.id, failed_logins=0, locked_until=None)
    st.session_state["uid"] = u.id
    st.session_state.pop("_logged_out", None)
    st.session_state.pop("pending_2fa", None)
    log_login(u.id, method, True)
    if remember:
        tok = pysecrets.token_urlsafe(32)
        with db() as s:
            s.add(SessionToken(token_hash=_sha(tok), user_id=u.id,
                               expires=datetime.utcnow() + timedelta(days=14)))
        st.session_state["_cookie_op"] = ("set", tok)


def logout():
    try:
        tok = st.context.cookies.get(COOKIE)
    except Exception:
        tok = None
    if tok:
        with db() as s:
            row = s.get(SessionToken, _sha(tok))
            if row:
                s.delete(row)
    for k in ("uid", "pending_2fa"):
        st.session_state.pop(k, None)
    st.session_state["_logged_out"] = True
    st.session_state["_cookie_op"] = ("clear", "")


_COOKIE_JS = """
export default function(component) {
  const { data } = component;
  if (!data) return;
  const secure = location.protocol === 'https:' ? ';Secure' : '';
  if (data.op === 'set') document.cookie = data.name + '=' + data.value + ';path=/;max-age=1209600;SameSite=Lax' + secure;
  if (data.op === 'clear') document.cookie = data.name + '=;path=/;max-age=0';
}
"""


def flush_cookie_op():
    """app.py 가 매 실행 초기에 호출: 대기 중인 쿠키 쓰기를 브라우저에 반영."""
    op = st.session_state.pop("_cookie_op", None)
    if op:
        comp = st.components.v2.component("geulgil_cookie", js=_COOKIE_JS)
        comp(data={"op": op[0], "name": COOKIE, "value": op[1]}, key=f"ck_{time.time_ns()}")


# ---------------------------------------------------------------- 이메일 인증코드
def issue_code(email: str, purpose: str) -> str:
    code = f"{pysecrets.randbelow(10**6):06d}"
    with db() as s:
        for old in s.scalars(select(OneTimeCode).where(OneTimeCode.email == email.lower(),
                                                       OneTimeCode.purpose == purpose)):
            s.delete(old)
        s.add(OneTimeCode(email=email.lower(), code_hash=_sha(code + app_secret()), purpose=purpose,
                          expires=datetime.utcnow() + timedelta(minutes=10)))
    return code


def verify_code(email: str, purpose: str, code: str) -> bool:
    with db() as s:
        row = s.scalar(select(OneTimeCode).where(OneTimeCode.email == email.lower(),
                                                 OneTimeCode.purpose == purpose))
        if not row or row.expires < datetime.utcnow() or row.tries >= 5:
            return False
        if hmac.compare_digest(row.code_hash, _sha((code or "").strip() + app_secret())):
            s.delete(row)
            return True
        row.tries += 1
        return False


def send_code(email: str, purpose: str) -> tuple[bool, str]:
    """코드를 메일로 보낸다. SMTP 미설정이면 (False, code) 를 돌려 개발 모드로 화면에 표시한다."""
    from .mailer import send_mail, smtp_ready
    code = issue_code(email, purpose)
    if not smtp_ready():
        return False, code
    ok, err = send_mail(email, f"[{APP_NAME}] 인증코드 {code}",
                        f"{APP_NAME} 인증코드는 {code} 입니다. 10분 안에 입력해 주세요.")
    return ok, ("" if ok else err)


# ---------------------------------------------------------------- OTP (TOTP)
def totp_new_secret() -> str:
    import pyotp
    return pyotp.random_base32()


def totp_uri(u: User, sec: str) -> str:
    import pyotp
    return pyotp.TOTP(sec).provisioning_uri(name=u.email, issuer_name=APP_NAME)


def totp_check(sec: str, code: str) -> bool:
    import pyotp
    code = re.sub(r"\D", "", code or "")
    return bool(sec) and len(code) == 6 and pyotp.TOTP(sec).verify(code, valid_window=1)


def qr_png(data: str) -> bytes:
    import io
    import qrcode
    buf = io.BytesIO()
    qrcode.make(data).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- 소셜 로그인 (OAuth2)
PROVIDERS = {
    "google": dict(label="Google", color="#4285F4",
                   auth="https://accounts.google.com/o/oauth2/v2/auth",
                   token="https://oauth2.googleapis.com/token",
                   info="https://openidconnect.googleapis.com/v1/userinfo",
                   scope="openid email profile"),
    "facebook": dict(label="Facebook", color="#1877F2",
                     auth="https://www.facebook.com/dialog/oauth",
                     token="https://graph.facebook.com/oauth/access_token",
                     info="https://graph.facebook.com/me?fields=id,name,email",
                     scope="email,public_profile"),
    "naver": dict(label="네이버", color="#03C75A",
                  auth="https://nid.naver.com/oauth2.0/authorize",
                  token="https://nid.naver.com/oauth2.0/token",
                  info="https://openapi.naver.com/v1/nid/me", scope=""),
    "kakao": dict(label="카카오", color="#C9A700",
                  auth="https://kauth.kakao.com/oauth/authorize",
                  token="https://kauth.kakao.com/oauth/token",
                  info="https://kapi.kakao.com/v2/user/me", scope=""),
}


def provider_ready(p: str) -> bool:
    return bool(secret(f"{p.upper()}_CLIENT_ID") and secret(f"{p.upper()}_CLIENT_SECRET"))


def oauth_url(p: str) -> str:
    cfg = PROVIDERS[p]
    raw = f"{p}.{int(time.time())}.{pysecrets.token_hex(8)}"
    state = f"{raw}.{_sign(raw)}"
    q = {"client_id": secret(f"{p.upper()}_CLIENT_ID"), "redirect_uri": base_url(),
         "response_type": "code", "state": state}
    if cfg["scope"]:
        q["scope"] = cfg["scope"]
    return cfg["auth"] + "?" + urllib.parse.urlencode(q)


def _profile(p: str, data: dict) -> dict:
    if p == "google":
        return dict(pid=data.get("sub"), email=data.get("email"), name=data.get("name", ""),
                    verified=bool(data.get("email_verified")))
    if p == "facebook":
        return dict(pid=data.get("id"), email=data.get("email"), name=data.get("name", ""), verified=False)
    if p == "naver":
        r = data.get("response", {})
        return dict(pid=r.get("id"), email=r.get("email"), name=r.get("name") or r.get("nickname", ""),
                    verified=False)
    acc = data.get("kakao_account", {})
    return dict(pid=str(data.get("id") or ""), email=acc.get("email"),
                name=(data.get("properties") or {}).get("nickname", ""),
                verified=bool(acc.get("is_email_verified")))


def handle_oauth_callback() -> str | None:
    """리디렉션으로 돌아왔을 때(code, state 쿼리) 처리. 오류 메시지 또는 None 반환."""
    qp = st.query_params
    if "code" not in qp or "state" not in qp:
        return None
    code, state = qp["code"], qp["state"]
    st.query_params.clear()
    try:
        raw, sig = state.rsplit(".", 1)
        p, ts, _ = raw.split(".")
    except ValueError:
        return "소셜 로그인 상태값이 올바르지 않습니다."
    if p not in PROVIDERS or not hmac.compare_digest(sig, _sign(raw)) or time.time() - int(ts) > 600:
        return "소셜 로그인 요청이 만료되었거나 올바르지 않습니다. 다시 시도해 주세요."
    cfg = PROVIDERS[p]
    try:
        tok = requests.post(cfg["token"], data={
            "grant_type": "authorization_code", "code": code, "state": state, "redirect_uri": base_url(),
            "client_id": secret(f"{p.upper()}_CLIENT_ID"),
            "client_secret": secret(f"{p.upper()}_CLIENT_SECRET")},
            headers={"Accept": "application/json"}, timeout=15).json()
        access = tok.get("access_token")
        if not access:
            return f"{cfg['label']} 토큰 발급 실패: {tok.get('error_description') or tok.get('error') or tok}"
        info = requests.get(cfg["info"], headers={"Authorization": f"Bearer {access}"}, timeout=15).json()
    except Exception as e:  # 네트워크 오류
        return f"{cfg['label']} 서버와 통신하지 못했습니다: {e}"
    prof = _profile(p, info)
    if not prof["pid"]:
        return f"{cfg['label']} 에서 사용자 정보를 받지 못했습니다."
    with db() as s:
        u = s.scalar(select(User).where(User.provider == p, User.provider_id == str(prof["pid"])))
    if not u:
        email = prof["email"] or f"{p}_{prof['pid']}@no-email.local"
        if find_user(email):
            return ("이미 같은 이메일로 가입된 계정이 있습니다. 보안을 위해 자동 연결하지 않습니다. "
                    "기존 로그인 방법으로 로그인해 주세요.")
        base = re.sub(r"[^a-z0-9_]", "", email.split("@")[0].lower()) or p
        username = base
        while find_user(username):
            username = f"{base}{pysecrets.randbelow(10000)}"
        u = create_user(username=username, email=email, name=prof["name"] or "", provider=p,
                        provider_id=str(prof["pid"]), email_verified=prof["verified"])
        st.session_state["_welcome"] = True
    login_user(u, p)
    return None


# ---------------------------------------------------------------- 얼굴 인식
_MODEL_DIR = ROOT / "models"
_MODELS = {
    "yunet.onnx": "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "sface.onnx": "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
}
FACE_THRESHOLD = 0.45  # SFace 코사인 유사도. 공식 권장 0.363 보다 엄격하게.


@st.cache_resource(show_spinner="얼굴 인식 모델을 준비하는 중입니다(최초 1회, 약 40MB)…")
def _face_models():
    import cv2
    _MODEL_DIR.mkdir(exist_ok=True)
    for name, url in _MODELS.items():
        path = _MODEL_DIR / name
        if not path.exists() or path.stat().st_size < 100_000:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            path.write_bytes(r.content)
    det = cv2.FaceDetectorYN.create(str(_MODEL_DIR / "yunet.onnx"), "", (320, 320), 0.8)
    rec = cv2.FaceRecognizerSF.create(str(_MODEL_DIR / "sface.onnx"), "")
    return det, rec


def face_embedding(image_bytes: bytes):
    """사진에서 얼굴 특징 벡터를 뽑는다. (벡터, 오류메시지) 반환."""
    import cv2
    import numpy as np
    try:
        det, rec = _face_models()
    except Exception as e:
        return None, f"얼굴 인식 모델을 불러오지 못했습니다: {e}"
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None, "이미지를 읽을 수 없습니다."
    h, w = img.shape[:2]
    if max(h, w) > 1000:
        sc = 1000 / max(h, w)
        img = cv2.resize(img, (int(w * sc), int(h * sc)))
        h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    if faces is None or len(faces) == 0:
        return None, "얼굴을 찾지 못했습니다. 밝은 곳에서 정면을 보고 다시 촬영해 주세요."
    if len(faces) > 1:
        return None, "얼굴이 여러 개 보입니다. 혼자 촬영해 주세요."
    feat = rec.feature(rec.alignCrop(img, faces[0]))
    return np.asarray(feat, dtype=np.float32).flatten(), ""


def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("face:" + app_secret()).encode()).digest()))


def face_encrypt(vec) -> bytes:
    return _fernet().encrypt(vec.tobytes())


def face_similarity(u: User, vec) -> float:
    import numpy as np
    if not u.face_enc:
        return -1.0
    try:
        ref = np.frombuffer(_fernet().decrypt(u.face_enc), dtype=np.float32)
    except Exception:
        return -1.0  # 비밀키가 바뀌어 복호화 불가
    return float(np.dot(ref, vec) / (np.linalg.norm(ref) * np.linalg.norm(vec) + 1e-9))


# ---------------------------------------------------------------- 패스키 (WebAuthn: 지문·Face ID·Windows Hello)
def _rp():
    url = urllib.parse.urlparse(base_url())
    return url.hostname, base_url()


def passkey_reg_options(u: User) -> dict:
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                          ResidentKeyRequirement, UserVerificationRequirement)
    from webauthn.helpers import base64url_to_bytes
    rp_id, _ = _rp()
    with db() as s:
        existing = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(k.cred_id))
                    for k in s.scalars(select(Passkey).where(Passkey.user_id == u.id))]
    opts = generate_registration_options(
        rp_id=rp_id, rp_name=APP_NAME, user_id=str(u.id).encode(), user_name=u.email,
        user_display_name=u.display, exclude_credentials=existing,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED))
    st.session_state["_pk_chal"] = opts.challenge
    return json.loads(options_to_json(opts))


def passkey_reg_verify(u: User, resp: dict, label: str) -> str:
    from webauthn import verify_registration_response
    from webauthn.helpers import bytes_to_base64url
    rp_id, origin = _rp()
    try:
        v = verify_registration_response(credential=resp, expected_challenge=st.session_state.pop("_pk_chal"),
                                         expected_rp_id=rp_id, expected_origin=origin,
                                         require_user_verification=True)
    except Exception as e:
        return f"패스키 등록 검증 실패: {e}"
    with db() as s:
        s.add(Passkey(user_id=u.id, cred_id=bytes_to_base64url(v.credential_id),
                      public_key=v.credential_public_key, sign_count=v.sign_count, label=label or "내 기기"))
    return ""


def passkey_auth_options(u: User | None) -> dict:
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers import base64url_to_bytes
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
    rp_id, _ = _rp()
    allow = []
    if u:
        with db() as s:
            allow = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(k.cred_id))
                     for k in s.scalars(select(Passkey).where(Passkey.user_id == u.id))]
    opts = generate_authentication_options(rp_id=rp_id, allow_credentials=allow,
                                           user_verification=UserVerificationRequirement.REQUIRED)
    st.session_state["_pk_chal"] = opts.challenge
    return json.loads(options_to_json(opts))


def passkey_auth_verify(resp: dict) -> tuple[User | None, str]:
    from webauthn import verify_authentication_response
    rp_id, origin = _rp()
    chal = st.session_state.pop("_pk_chal", None)
    if not chal:
        return None, "요청이 만료되었습니다. 다시 시도해 주세요."
    with db() as s:
        key = s.scalar(select(Passkey).where(Passkey.cred_id == resp.get("id", "")))
        if not key:
            return None, "등록되지 않은 패스키입니다."
        try:
            v = verify_authentication_response(
                credential=resp, expected_challenge=chal, expected_rp_id=rp_id, expected_origin=origin,
                credential_public_key=key.public_key, credential_current_sign_count=key.sign_count,
                require_user_verification=True)
        except Exception as e:
            return None, f"패스키 검증 실패: {e}"
        key.sign_count = v.new_sign_count
        return s.get(User, key.user_id), ""


_PASSKEY_JS = """
const b2a = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
const a2b = (s) => Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')), c => c.charCodeAt(0));
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const root = parentElement.querySelector('.pk') || parentElement.appendChild(Object.assign(document.createElement('div'), {className:'pk'}));
  root.innerHTML = '';
  const btn = document.createElement('button');
  btn.textContent = data.label; btn.className = 'pkbtn';
  const msg = document.createElement('div'); msg.className = 'pkmsg';
  root.append(btn, msg);
  if (!window.PublicKeyCredential) { btn.disabled = true; msg.textContent = '이 브라우저는 패스키를 지원하지 않습니다.'; return; }
  btn.onclick = async () => {
    msg.textContent = '기기의 지문·얼굴·PIN 확인을 기다리는 중…';
    try {
      const o = JSON.parse(JSON.stringify(data.options));
      o.challenge = a2b(o.challenge);
      let out;
      if (data.mode === 'register') {
        o.user.id = a2b(o.user.id);
        (o.excludeCredentials || []).forEach(c => c.id = a2b(c.id));
        const c = await navigator.credentials.create({ publicKey: o });
        out = { id: c.id, rawId: b2a(c.rawId), type: c.type, response: {
          clientDataJSON: b2a(c.response.clientDataJSON), attestationObject: b2a(c.response.attestationObject) } };
      } else {
        (o.allowCredentials || []).forEach(c => c.id = a2b(c.id));
        const c = await navigator.credentials.get({ publicKey: o });
        out = { id: c.id, rawId: b2a(c.rawId), type: c.type, response: {
          clientDataJSON: b2a(c.response.clientDataJSON), authenticatorData: b2a(c.response.authenticatorData),
          signature: b2a(c.response.signature), userHandle: c.response.userHandle ? b2a(c.response.userHandle) : null } };
      }
      msg.textContent = '확인 완료';
      setTriggerValue('result', JSON.stringify(out));
    } catch (e) { msg.textContent = '취소되었거나 실패했습니다: ' + e.message; }
  };
}
"""
_PASSKEY_CSS = """
.pkbtn { padding: .5rem 1rem; border-radius: .5rem; border: 1px solid var(--st-primary-color);
  background: var(--st-primary-color); color: #fff; cursor: pointer; font-size: 1rem; }
.pkbtn:disabled { opacity: .5; cursor: not-allowed; }
.pkmsg { margin-top: .4rem; font-size: .85rem; color: var(--st-text-color); opacity: .8; }
"""


def passkey_button(mode: str, options: dict, label: str, key: str) -> dict | None:
    """브라우저의 패스키 창을 띄우는 버튼. 완료되면 응답(dict)을 돌려준다."""
    comp = st.components.v2.component("geulgil_passkey", js=_PASSKEY_JS, css=_PASSKEY_CSS)
    res = comp(data={"mode": mode, "options": options, "label": label}, key=key,
               on_result_change=lambda: None)
    if res.result:
        return json.loads(res.result)
    return None
