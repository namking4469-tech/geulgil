"""편집실: 형식별 온라인 편집기 (워드 · 한글 · PDF · 이미지 · 텍스트) + 버전 기록."""
import io

import streamlit as st
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from core import analysis, docs
from core.db import Version, db, select
from core.ebook import font
from core.ui import fmt_dt, header, require_login, save_version, update_work, work_picker

user = require_login()
ss = st.session_state
header("✍️ 편집실", "올린 형식에 맞는 편집기가 열립니다. 저장할 때마다 이전 상태가 버전 기록에 남습니다.")

w = work_picker(user, "ed_pick")
if not w:
    st.stop()
if ss.pop("ed_msg", None):
    st.toast("저장했습니다.", icon="✅")


def save_text(text: str, html: str, note: str, blob: bytes | None = None):
    save_version(w, note)
    stats = analysis.compute_stats(text) if text.strip() else {}
    kw = dict(text=text, html=html, stats=stats)
    if stats and not w.length_class:
        kw["length_class"] = analysis.length_class(stats, text)
    if stats:
        kw["length_class"] = analysis.length_class(stats, text)
    if blob is not None:
        kw["blob"] = blob
    update_work(w.id, **kw)
    ss["ed_msg"] = True
    st.rerun()


def export_buttons(text: str, html: str = ""):
    c = st.columns(3)
    c[0].download_button("워드(DOCX)로 받기", docs.html_to_docx(html, w.title) if html else docs.text_to_docx(text, w.title),
                         f"{w.title}.docx", use_container_width=True)
    c[1].download_button("텍스트(TXT)로 받기", text.encode("utf-8"), f"{w.title}.txt", use_container_width=True)
    if c[2].button("PDF 만들기", use_container_width=True, key="mkpdf"):
        ss["ed_pdf"] = (w.id, docs.text_to_pdf(text, w.title))
    if ss.get("ed_pdf", (0,))[0] == w.id:
        st.download_button("PDF 내려받기", ss["ed_pdf"][1], f"{w.title}.pdf", type="primary")


def live_count(text: str):
    s = analysis.compute_stats(text) if text.strip() else {}
    st.caption(f"글자 수 {s.get('chars', 0):,} (공백 제외 {s.get('chars_no_space', 0):,}) · "
               f"원고지 {s.get('manuscript_pages', 0):,}매 · 단어 {s.get('words', 0):,}")


tab_edit, tab_ver = st.tabs([f"{docs.KIND_LABEL[w.kind]} 편집", "버전 기록"])

with tab_edit:
    # ======================================================== 워드
    if w.kind == "docx":
        st.caption("제목·굵게·기울임·밑줄·목록·정렬을 지원합니다. 저장하면 DOCX 파일도 함께 갱신됩니다. "
                   "(표·그림·머리글 등 복잡한 서식은 편집기에서 유지되지 않습니다)")
        try:
            from streamlit_quill import st_quill
            toolbar = [[{"header": [1, 2, 3, False]}], ["bold", "italic", "underline", "strike"],
                       [{"list": "ordered"}, {"list": "bullet"}], [{"align": []}], ["blockquote"], ["clean"]]
            html = st_quill(value=w.html or "", html=True, toolbar=toolbar, key=f"quill_{w.id}_{ss.get('ed_rev', 0)}",
                            placeholder="여기에 글을 쓰세요…")
        except Exception:
            html = None
        if html is None:
            html = w.html or ""
        text = docs.html_to_text(html)
        live_count(text)
        if st.button("저장", type="primary"):
            save_text(text, html, "워드 편집", docs.html_to_docx(html, w.title))
        st.divider()
        export_buttons(text, html)

    # ======================================================== 한글 / 텍스트
    elif w.kind in ("hwp", "txt"):
        if w.kind == "hwp":
            st.info("한글(HWP/HWPX) 파일은 **글자만 꺼내어** 편집합니다. 글꼴·표·그림 같은 서식은 유지되지 않으며, "
                    "편집한 글은 워드(DOCX)·PDF·TXT 로 내려받을 수 있습니다. (한글 프로그램은 DOCX 를 그대로 엽니다) "
                    "원본 HWP 파일은 서재에 그대로 보관됩니다.")
        text = st.text_area("본문", w.text, height=520, key=f"ta_{w.id}_{ss.get('ed_rev', 0)}")
        live_count(text)
        if st.button("저장", type="primary"):
            save_text(text, docs.text_to_html(text), "본문 편집",
                      text.encode("utf-8") if w.kind == "txt" else None)
        st.divider()
        export_buttons(text)

    # ======================================================== PDF
    elif w.kind == "pdf":
        n = docs.pdf_page_count(w.blob)
        st.caption(f"총 {n}쪽")
        p_pages, p_stamp, p_merge, p_text = st.tabs(["페이지 정리", "글자·쪽번호·워터마크 넣기", "PDF 합치기", "본문 글 편집"])
        with p_pages:
            st.write("쪽마다 **남길지**, **회전**, **순서**를 정한 뒤 적용하세요.")
            show = st.slider("미리보기 범위", 1, n, (1, min(n, 8))) if n > 1 else (1, 1)
            cols = st.columns(4)
            for i in range(show[0] - 1, show[1]):
                cols[(i - show[0] + 1) % 4].image(docs.pdf_page_image(w.blob, i, 0.4), caption=f"{i + 1}쪽")
            import pandas as pd
            plan = st.data_editor(
                pd.DataFrame({"쪽": range(1, n + 1), "남기기": True, "회전": 0, "새 순서": range(1, n + 1)}),
                hide_index=True, use_container_width=True, key=f"plan_{w.id}_{ss.get('ed_rev', 0)}",
                column_config={"쪽": st.column_config.NumberColumn(disabled=True),
                               "회전": st.column_config.SelectboxColumn(options=[0, 90, 180, 270])})
            if st.button("페이지 정리 적용", type="primary"):
                keep = plan[plan["남기기"]].sort_values("새 순서", kind="stable")
                if keep.empty:
                    st.error("적어도 한 쪽은 남겨야 합니다.")
                else:
                    new = docs.pdf_rebuild(w.blob, [(int(r["쪽"]) - 1, int(r["회전"])) for _, r in keep.iterrows()])
                    text, html = docs.extract("pdf", new)
                    ss["ed_rev"] = ss.get("ed_rev", 0) + 1
                    save_text(text, html, "PDF 페이지 정리", new)
        with p_stamp:
            c1, c2 = st.columns([1, 1], gap="large")
            with c1:
                s_text = st.text_area("넣을 글 ( {n} 은 쪽 번호로 바뀝니다 )", "- {n} -", height=80)
                target = st.radio("대상", ["모든 쪽", "특정 쪽"], horizontal=True)
                pg = st.number_input("쪽", 1, n, 1) if target == "특정 쪽" else 1
                x = st.slider("가로 위치(%)", 0, 100, 46)
                y = st.slider("세로 위치(%)", 0, 100, 96)
                size = st.slider("글자 크기", 6, 96, 10)
                k1, k2, k3 = st.columns(3)
                color = k1.color_picker("색", "#000000")
                op = k2.slider("불투명도", 0.05, 1.0, 1.0)
                ang = k3.slider("기울기", -90, 90, 0)
                pages = list(range(n)) if target == "모든 쪽" else [pg - 1]
            with c2:
                prev = docs.pdf_stamp(w.blob, s_text, pages, x, y, size, color, op, ang)
                st.image(docs.pdf_page_image(prev, pages[0] if target == "특정 쪽" else 0, 0.9), caption="미리보기")
            if st.button("PDF 에 넣기", type="primary"):
                text, html = docs.extract("pdf", prev)
                save_text(w.text, w.html, "PDF 글자 넣기", prev)
        with p_merge:
            more = st.file_uploader("뒤에 이어 붙일 PDF", type=["pdf"], accept_multiple_files=True)
            if more and st.button("합치기", type="primary"):
                try:
                    new = docs.pdf_merge([w.blob] + [f.getvalue() for f in more])
                    text, html = docs.extract("pdf", new)
                    ss["ed_rev"] = ss.get("ed_rev", 0) + 1
                    save_text(text, html, "PDF 합치기", new)
                except Exception as e:
                    st.error(f"합치지 못했습니다: {e}")
        with p_text:
            st.info("PDF 는 완성된 지면이라 글을 직접 고치면 조판이 깨집니다. 여기서는 **꺼낸 본문 글**을 고치고, "
                    "그 글로 새 PDF·워드 파일을 만들 수 있습니다. 번역·전자책 제작에는 이 본문이 쓰입니다.")
            if not w.text.strip():
                st.warning("이 PDF 에서 글자를 찾지 못했습니다(스캔본일 수 있습니다). 직접 입력하거나 이미지로 올려 OCR 을 써 보세요.")
            text = st.text_area("본문", w.text, height=420, key=f"pt_{w.id}_{ss.get('ed_rev', 0)}")
            live_count(text)
            if st.button("본문 저장", type="primary"):
                save_text(text, docs.text_to_html(text), "PDF 본문 편집")
            export_buttons(text)
        st.divider()
        st.download_button("현재 PDF 내려받기", w.blob, w.filename or f"{w.title}.pdf")

    # ======================================================== 이미지
    elif w.kind == "image":
        src = ImageOps.exif_transpose(Image.open(io.BytesIO(w.blob))).convert("RGB")
        c1, c2 = st.columns([1, 1.3], gap="large")
        with c1:
            with st.expander("자르기 · 회전 · 크기", expanded=True):
                rot = st.select_slider("회전", [0, 90, 180, 270], 0)
                fl = st.checkbox("좌우 뒤집기")
                l, r = st.slider("가로 범위(%)", 0, 100, (0, 100))
                t, b = st.slider("세로 범위(%)", 0, 100, (0, 100))
                scale = st.slider("크기(%)", 10, 200, 100, 5)
            with st.expander("색 · 효과"):
                br = st.slider("밝기", 0.3, 2.0, 1.0, 0.05)
                ct = st.slider("대비", 0.3, 2.0, 1.0, 0.05)
                sa = st.slider("채도", 0.0, 2.0, 1.0, 0.05)
                sh = st.slider("선명도", 0.0, 3.0, 1.0, 0.1)
                fx = st.selectbox("필터", ["없음", "흑백", "세피아", "흐림", "윤곽 강조"])
            with st.expander("글자 넣기"):
                txt = st.text_input("글")
                tx = st.slider("가로(%)", 0, 100, 50, key="itx")
                ty = st.slider("세로(%)", 0, 100, 90, key="ity")
                ts = st.slider("크기(이미지 폭의 %)", 1, 20, 5)
                tc = st.color_picker("글자 색", "#FFFFFF")
                serif = st.checkbox("명조체")
        img = src.rotate(-rot, expand=True) if rot else src
        if fl:
            img = ImageOps.mirror(img)
        if r - l >= 1 and b - t >= 1:
            img = img.crop((int(img.width * l / 100), int(img.height * t / 100), int(img.width * r / 100),
                            int(img.height * b / 100)))
        if scale != 100:
            img = img.resize((max(1, img.width * scale // 100), max(1, img.height * scale // 100)))
        for enh, val in ((ImageEnhance.Brightness, br), (ImageEnhance.Contrast, ct), (ImageEnhance.Color, sa),
                         (ImageEnhance.Sharpness, sh)):
            if val != 1.0:
                img = enh(img).enhance(val)
        if fx == "흑백":
            img = ImageOps.grayscale(img).convert("RGB")
        elif fx == "세피아":
            img = ImageOps.colorize(ImageOps.grayscale(img), "#2b1a0e", "#f5e3c4")
        elif fx == "흐림":
            img = img.filter(ImageFilter.GaussianBlur(3))
        elif fx == "윤곽 강조":
            img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
        if txt:
            d = ImageDraw.Draw(img)
            fnt = font(max(8, img.width * ts // 100), bold=not serif, serif=serif)
            d.text((img.width * tx / 100, img.height * ty / 100), txt, font=fnt, fill=tc, anchor="mm",
                   stroke_width=max(1, fnt.size // 18), stroke_fill="#000000" if tc.upper() > "#888888" else "#FFFFFF")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        with c2:
            st.image(img, caption=f"미리보기 · {img.width}×{img.height}px", use_container_width=True)
            k1, k2 = st.columns(2)
            if k1.button("이 상태로 저장", type="primary", use_container_width=True):
                save_version(w, "이미지 편집")
                update_work(w.id, blob=buf.getvalue(), filename=w.title + ".png")
                ss["ed_msg"] = True
                st.rerun()
            k2.download_button("PNG 내려받기", buf.getvalue(), f"{w.title}.png", use_container_width=True)
        st.divider()
        st.markdown("##### 이미지 속 글자 읽기 (OCR)")
        st.caption("손글씨 원고나 스캔한 원고 사진에서 글자를 꺼내 본문으로 저장합니다. 번역·전자책에 쓸 수 있습니다.")
        if st.button("글자 읽기"):
            with st.spinner("읽는 중…"):
                text, err = docs.ocr_image(buf.getvalue(), "image/png")
            if err:
                st.error(err)
            else:
                ss["ocr"] = (w.id, text)
        if ss.get("ocr", (0,))[0] == w.id or w.text:
            text = st.text_area("읽은 글 (고칠 수 있습니다)", ss["ocr"][1] if ss.get("ocr", (0,))[0] == w.id else w.text,
                                height=260)
            if st.button("본문으로 저장"):
                ss.pop("ocr", None)
                save_text(text, docs.text_to_html(text), "OCR 본문")

# ------------------------------------------------------------ 버전 기록
with tab_ver:
    with db() as s:
        vers = list(s.scalars(select(Version).where(Version.work_id == w.id).order_by(Version.at.desc()).limit(30)))
    if not vers:
        st.info("아직 버전 기록이 없습니다. 저장할 때마다 직전 상태가 여기에 쌓입니다.")
    for v in vers:
        with st.expander(f"{fmt_dt(v.at)} (UTC) · {v.note} · {len(v.text):,}자"):
            if v.blob and w.kind == "image":
                st.image(v.blob, width=260)
            elif v.text:
                st.text(v.text[:1500] + ("…" if len(v.text) > 1500 else ""))
            if st.button("이 버전으로 되돌리기", key=f"rv{v.id}"):
                save_version(w, "되돌리기 직전 상태")
                kw = dict(text=v.text, html=v.html, stats=analysis.compute_stats(v.text) if v.text.strip() else {})
                if v.blob:
                    kw["blob"] = v.blob
                elif w.kind == "docx":
                    kw["blob"] = docs.html_to_docx(v.html, w.title)
                update_work(w.id, **kw)
                ss["ed_rev"] = ss.get("ed_rev", 0) + 1
                st.rerun()
