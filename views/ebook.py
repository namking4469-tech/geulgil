"""전자책 제작(EPUB 3 · PDF)과 ISBN 지원."""
import io
import zipfile

import streamlit as st

from core import ebook
from core.config import LANGS
from core.db import Ebook, Setting, db, select
from core.pipeline import get_translations, make_ebooks
from core.ui import copy_block, fmt_dt, header, require_login, update_work, work_picker

user = require_login()
ss = st.session_state
header("📖 전자책 · ISBN", "원고와 번역본을 표준 전자책(EPUB 3)과 PDF 로 만들고, ISBN 신청을 준비합니다.")

w = work_picker(user, "eb_pick", need_text=True)
if not w:
    st.stop()

with db() as s:
    setting = s.get(Setting, user.id)
    prefs = dict(setting.data) if setting else {}

t_cover, t_make, t_isbn = st.tabs(["① 표지", "② 전자책 만들기", "③ ISBN"])

# ------------------------------------------------------------ 표지
with t_cover:
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        mode = st.radio("표지", ["자동 생성", "이미지 올리기"], horizontal=True)
        if mode == "자동 생성":
            title = st.text_input("표지 제목", w.title)
            author = st.text_input("작가 이름", user.display)
            sub = st.text_input("부제·장르 표기 (선택)", w.genre and f"{w.length_class} {w.genre}".strip())
            theme = st.selectbox("분위기", list(ebook.COVER_THEMES))
            new = ebook.make_cover(title, author, sub, theme)
        else:
            up = st.file_uploader("표지 이미지 (세로형 권장 1600×2400)", type=["jpg", "jpeg", "png"])
            new = None
            if up:
                from PIL import Image
                im = Image.open(up).convert("RGB")
                im.thumbnail((1600, 2560))
                b = io.BytesIO()
                im.save(b, format="JPEG", quality=90)
                new = b.getvalue()
        if new and st.button("이 표지로 저장", type="primary"):
            update_work(w.id, cover=new)
            st.rerun()
        st.caption("저장한 표지는 원문 언어판 전자책과 홍보물에 쓰입니다. 번역판 표지는 번역된 제목으로 자동 생성됩니다.")
    with c2:
        a, b = st.columns(2)
        if new:
            a.image(new, caption="미리보기")
        if w.cover:
            b.image(w.cover, caption="저장된 표지")
            b.download_button("표지 내려받기", w.cover, f"{w.title}_cover.jpg")

# ------------------------------------------------------------ 만들기
with t_make:
    trs = get_translations(w.id)
    langs = [w.lang] + list(trs)
    chapters = ebook.split_chapters(w.text)
    st.caption(f"자동으로 찾은 장(章): {len(chapters)}개"
               + (" — " + ", ".join(c[0] for c in chapters[:6] if c[0]) + (" …" if len(chapters) > 6 else "")
                  if chapters[0][0] or len(chapters) > 1 else " (장 구분 없음: '제1장', 'Chapter 1', '# 제목' 같은 줄이 있으면 장으로 나눕니다)"))
    c1, c2, c3 = st.columns(3)
    picked = c1.multiselect("언어판", langs, default=langs, format_func=lambda c: LANGS.get(c, c))
    fmts = c2.multiselect("포맷", ["epub", "pdf"], default=["epub"],
                          format_func={"epub": "EPUB 3 (표준 · 서점 유통용)", "pdf": "PDF (A5 고정 지면)"}.get)
    publisher = c3.text_input("출판사·발행처 이름 (선택)", prefs.get("publisher", ""))
    theme = st.selectbox("번역판 자동 표지 분위기", list(ebook.COVER_THEMES), key="eb_theme")
    st.caption("EPUB 은 Amazon KDP, Kobo, Apple Books, Google Play Books, 리디, 교보문고 등 대부분의 서점이 받는 표준 포맷입니다. "
               "PDF 는 한국어·영어 등 내장 글꼴이 지원하는 언어만 만들 수 있습니다(아랍어·힌디어·일본어·중국어는 EPUB 만).")
    if not trs:
        st.info("번역본이 없어 원문 언어판만 만듭니다. **번역** 화면에서 번역하면 언어별로 함께 만들 수 있습니다.")
    if st.button("전자책 만들기", type="primary", disabled=not (picked and fmts)):
        with db() as s:
            row = s.get(Setting, user.id)
            if row:
                row.data = {**row.data, "publisher": publisher}
            else:
                s.add(Setting(user_id=user.id, data={"publisher": publisher}))
        log = []
        bar = st.progress(0.0)
        for i, lang in enumerate(picked):
            for m in make_ebooks(w, user, lang, fmts, publisher, theme):
                log.append(("완성" in m, m.replace(lang, LANGS.get(lang, lang), 1)))
            bar.progress((i + 1) / len(picked))
        ss["eb_log"] = log
        st.rerun()
    for ok, msg in ss.pop("eb_log", []):
        (st.success if ok else st.warning)(msg)

    with db() as s:
        books = list(s.scalars(select(Ebook).where(Ebook.work_id == w.id).order_by(Ebook.lang, Ebook.fmt)))
    if books:
        st.divider()
        st.markdown("##### 만들어진 전자책")
        for bk in books:
            c = st.columns([3, 1.2, 1.4, 0.8])
            c[0].write(f"**{LANGS.get(bk.lang, bk.lang)}** · {bk.title}")
            c[1].write(f"{bk.fmt.upper()} · {len(bk.blob) / 1024:,.0f} KB")
            c[2].download_button("내려받기", bk.blob, f"{bk.title}_{bk.lang}.{bk.fmt}", key=f"dl{bk.id}",
                                 mime="application/epub+zip" if bk.fmt == "epub" else "application/pdf",
                                 use_container_width=True)
            if c[3].button("삭제", key=f"rm{bk.id}", use_container_width=True):
                with db() as s:
                    s.delete(s.get(Ebook, bk.id))
                st.rerun()
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            for bk in books:
                z.writestr(f"{bk.lang}/{bk.title}.{bk.fmt}", bk.blob)
        st.download_button("전체 ZIP 으로 내려받기", zbuf.getvalue(), f"{w.title}_ebooks.zip", mime="application/zip")

# ------------------------------------------------------------ ISBN
with t_isbn:
    st.info("**ISBN 은 이 앱이 발급할 수 없습니다.** 한국에서는 출판사 신고를 한 발행자가 "
            "국립중앙도서관 ISBN·ISSN·납본시스템에서 직접 신청해 받습니다. "
            "이 화면은 신청 준비 → 받은 번호 등록 → 전자책·바코드 반영을 돕습니다.")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("##### 발급 받는 길")
        st.markdown(
            "**1. 직접 발급 (1인 출판사)**\n"
            "1. 관할 시·군·구청에 **출판사 신고** (신고확인증 발급)\n"
            "2. 세무서 **사업자 등록** (업종: 출판업)\n"
            "3. 국립중앙도서관 서지정보유통지원시스템에서 **발행자번호 신청** (교육 이수 필요)\n"
            "4. 책마다 **ISBN 신청** → 승인 후 번호 부여\n"
            "5. 발간 후 **납본**\n\n"
            "**2. 대행 이용** — 부크크·유페이퍼 같은 자가출판 플랫폼이나 계약한 출판사가 자기 발행자번호로 ISBN 을 붙여 줍니다.\n\n"
            "**3. 해외 유통만** — Amazon KDP 는 전자책에 ISBN 이 필수가 아니며, 자체 식별번호(ASIN)를 부여합니다.\n\n"
            "※ 절차·요건은 바뀔 수 있으니 공식 안내를 확인하세요. 같은 책이라도 **포맷(EPUB/PDF)·언어판마다 ISBN 이 따로** 필요합니다.")
        st.link_button("국립중앙도서관 ISBN·ISSN·납본시스템 열기", "https://www.nl.go.kr/seoji/")
    with b:
        st.markdown("##### 신청서에 옮겨 적을 내용")
        an = w.analysis or {}
        stt = w.stats or {}
        sheet = (f"서명(제목): {w.title}\n저자: {user.name or user.display}"
                 + (f" (필명 {user.pen_name})" if user.pen_name and user.pen_name != user.name else "")
                 + f"\n발행처: {prefs.get('publisher') or '(출판사 이름)'}\n형태: 전자책(EPUB)\n언어: {LANGS.get(w.lang, w.lang)}"
                 f"\n분야: {w.genre or '(장르)'}\n분량: {stt.get('chars', 0):,}자 (200자 원고지 {stt.get('manuscript_pages', 0):,}매)"
                 f"\n주제어: {', '.join(an.get('keywords', []))}\n책 소개: {an.get('summary', '')}")
        copy_block("복사해서 쓰세요", sheet)

    st.divider()
    st.markdown("##### 받은 ISBN 등록")
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        isbn = st.text_input("ISBN", w.isbn, placeholder="979-11-0000-000-0")
        if isbn:
            ok, msg = ebook.isbn_check(isbn)
            (st.success if ok else st.error)(msg)
            if ok and st.button("이 작품의 ISBN 으로 저장", type="primary"):
                update_work(w.id, isbn=ebook.isbn_format(isbn))
                st.success("저장했습니다. '② 전자책 만들기'를 다시 실행하면 판권 면과 책 정보에 들어갑니다.")
                st.rerun()
        if w.isbn and st.button("ISBN 지우기"):
            update_work(w.id, isbn="")
            st.rerun()
    with c2:
        if w.isbn and len(ebook.isbn_digits(w.isbn)) == 13:
            png = ebook.isbn_barcode(w.isbn)
            st.image(png, caption=f"ISBN {w.isbn} 바코드(EAN-13)", width=280)
            st.download_button("바코드 PNG 내려받기", png, f"isbn_{ebook.isbn_digits(w.isbn)}.png")
