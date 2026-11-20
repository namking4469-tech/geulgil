"""화면 공통 도구."""
import io
from datetime import datetime

import streamlit as st
from PIL import Image, ImageOps
from sqlalchemy.orm import defer

from .auth import current_user
from .config import APP_NAME, LANGS
from .db import User, Version, Work, db, select
from .docs import KIND_LABEL

KIND_ICON = {"docx": "📝", "hwp": "📄", "pdf": "📕", "image": "🖼️", "txt": "📃"}
STATUSES = ["구상 중", "집필 중", "퇴고 중", "완성", "투고 중", "계약", "출간"]


def require_login() -> User:
    u = current_user()
    if not u:
        st.warning("로그인이 필요한 화면입니다.")
        st.stop()
    return u


def header(title: str, desc: str = ""):
    st.title(title)
    if desc:
        st.caption(desc)


def list_works(uid: int, kinds: list[str] | None = None) -> list[Work]:
    """목록용(파일 바이너리·본문 제외)."""
    with db() as s:
        q = select(Work).where(Work.user_id == uid).options(
            defer(Work.blob), defer(Work.text), defer(Work.html), defer(Work.cover)).order_by(Work.updated_at.desc())
        if kinds:
            q = q.where(Work.kind.in_(kinds))
        return list(s.scalars(q))


def get_work(wid: int, uid: int) -> Work | None:
    with db() as s:
        w = s.get(Work, wid)
        return w if w and w.user_id == uid else None


def update_work(wid: int, **kw):
    with db() as s:
        w = s.get(Work, wid)
        for k, v in kw.items():
            setattr(w, k, v)
        w.updated_at = datetime.utcnow()


def save_version(w: Work, note: str):
    """현재 상태를 버전 기록에 남긴다(편집 내용을 덮어쓰기 전에 호출)."""
    with db() as s:
        s.add(Version(work_id=w.id, text=w.text, html=w.html, blob=w.blob if w.kind in ("pdf", "image") else None,
                      note=note))


def work_picker(user: User, key: str, kinds: list[str] | None = None, need_text: bool = False,
                label: str = "작품 선택") -> Work | None:
    works = list_works(user.id, kinds)
    if need_text:
        works = [w for w in works if (w.stats or {}).get("chars", 0) > 0]
    if not works:
        st.info("먼저 **원고 서재**에서 원고를 올려 주세요." + (" (글자가 들어 있는 원고가 필요합니다)" if need_text else ""))
        return None
    ids = [w.id for w in works]
    by = {w.id: w for w in works}
    default = st.session_state.get("cur_work")
    idx = ids.index(default) if default in ids else 0
    wid = st.selectbox(label, ids, index=idx, key=key,
                       format_func=lambda i: f"{KIND_ICON.get(by[i].kind, '')} {by[i].title}  ·  {by[i].genre or '미분류'}"
                                             f"  ·  {LANGS.get(by[i].lang, by[i].lang)}")
    st.session_state["cur_work"] = wid
    return get_work(wid, user.id)


def copy_block(label: str, text: str):
    """오른쪽 위 복사 버튼이 달린 글 상자."""
    if not text:
        return
    st.markdown(f"**{label}**")
    st.code(text, language=None, wrap_lines=True)


def square_jpeg(data: bytes, size: int = 600, box: tuple[float, float, float] | None = None) -> bytes:
    """프로필 사진: 정사각형으로 잘라 JPEG 로. box=(가로중심%, 세로중심%, 확대%)"""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    side = min(img.size)
    cx, cy, zoom = box or (50, 50, 100)
    side = int(side * 100 / max(100, zoom))
    x = int((img.width - side) * cx / 100)
    y = int((img.height - side) * cy / 100)
    img = img.crop((x, y, x + side, y + side)).resize((size, size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def app_caption():
    st.caption(f"✒️ {APP_NAME}")
