"""원고 서재: 업로드 → 자동 분석·분류 → 목록·상세 → Excel 내보내기."""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from core import analysis, docs
from core.ai import ai_ready
from core.config import GENRES, LANGS
from core.db import Ebook, Promo, Translation, Version, Work, db, select
from core.ui import KIND_ICON, STATUSES, fmt_dt, get_work, header, list_works, require_login, update_work

user = require_login()
ss = st.session_state
header("📚 원고 서재", "원고를 올리면 분량·장르·주제를 자동으로 분석해 분류하고 보관합니다.")
if not ai_ready():
    st.info("AI 키(ANTHROPIC_API_KEY)가 없어 장르 분석은 **키워드 기반 간이 분석**으로 동작합니다. 결과는 직접 고칠 수 있습니다.")

LENGTHS = ["시", "엽편(콩트)", "플래시 픽션", "단편", "중편", "장편", ""]


def ingest(name: str, data: bytes, do_ai: bool) -> tuple[bool, str]:
    kind = docs.detect_kind(name)
    if not kind:
        return False, f"{name}: 지원하지 않는 형식입니다."
    try:
        text, html = docs.extract(kind, data, name)
    except ValueError as e:
        return False, f"{name}: {e}"
    title = name.rsplit(".", 1)[0]
    stats = analysis.compute_stats(text) if text.strip() else {}
    an = (analysis.analyze(text, title) if do_ai else analysis.heuristic_analysis(text)) if text.strip() else {}
    with db() as s:
        s.add(Work(user_id=user.id, title=title, filename=name, kind=kind, blob=data, text=text, html=html,
                   lang=stats.get("lang", "ko"), genre=an.get("genre", ""),
                   length_class=analysis.length_class(stats, text) if stats else "", stats=stats, analysis=an))
    note = ""
    if kind == "pdf" and not text.strip():
        note = " (글자를 찾지 못했습니다. 스캔한 PDF 로 보입니다.)"
    if an.get("error"):
        note += f" (AI 분석 실패로 간이 분석 사용: {an['error']})"
    return True, f"{name}: 저장했습니다.{note}"


t_list, t_up, t_export = st.tabs(["내 원고", "올리기 · 새로 쓰기", "데이터 내보내기"])

# ------------------------------------------------------------ 올리기
with t_up:
    st.markdown("##### 파일 올리기")
    files = st.file_uploader("워드(DOCX) · 한글(HWP, HWPX) · PDF · 텍스트(TXT) · 이미지(JPG, PNG…)",
                             type=docs.UPLOAD_TYPES, accept_multiple_files=True, key=f"up_{ss.get('up_n', 0)}")
    do_ai = st.checkbox("AI 로 장르·주제 정밀 분석 (원고 내용이 Anthropic API 로 전송됩니다)", value=ai_ready(),
                        disabled=not ai_ready())
    st.caption("옛 워드 형식(.doc)은 지원하지 않습니다. 워드에서 .docx 로 다시 저장해 올려 주세요.")
    if files and st.button(f"{len(files)}개 파일 저장 · 분석", type="primary"):
        results = []
        bar = st.progress(0.0)
        for i, f in enumerate(files):
            with st.spinner(f"{f.name} 분석 중…"):
                results.append(ingest(f.name, f.getvalue(), do_ai))
            bar.progress((i + 1) / len(files))
        ss["up_msgs"] = results
        ss["up_n"] = ss.get("up_n", 0) + 1
        st.rerun()
    for ok, msg in ss.pop("up_msgs", []):
        (st.success if ok else st.error)(msg)

    st.divider()
    st.markdown("##### 빈 원고로 새로 쓰기")
    with st.form("new"):
        title = st.text_input("제목")
        if st.form_submit_button("새 원고 만들기") and title.strip():
            with db() as s:
                w = Work(user_id=user.id, title=title.strip(), filename=f"{title.strip()}.docx", kind="docx",
                         blob=docs.text_to_docx("", title.strip()), text="", html="", stats={}, analysis={})
                s.add(w)
                s.flush()
                ss["cur_work"] = w.id
            st.success("만들었습니다. **편집실**에서 바로 쓸 수 있습니다.")

# ------------------------------------------------------------ 목록
with t_list:
    works = list_works(user.id)
    if not works:
        st.info("아직 원고가 없습니다. '올리기 · 새로 쓰기' 탭에서 시작해 보세요.")
    else:
        c1, c2, c3 = st.columns(3)
        f_kind = c1.multiselect("형식", list(docs.KIND_LABEL), format_func=docs.KIND_LABEL.get)
        f_genre = c2.multiselect("장르", sorted({w.genre for w in works if w.genre}))
        f_q = c3.text_input("제목 검색")
        shown = [w for w in works if (not f_kind or w.kind in f_kind) and (not f_genre or w.genre in f_genre)
                 and (f_q.lower() in w.title.lower())]
        st.caption(f"{len(shown)}편 / 전체 {len(works)}편 — 행을 누르면 아래에 상세가 열립니다.")
        df = pd.DataFrame([{
            "형식": KIND_ICON.get(w.kind, "") + " " + docs.KIND_LABEL[w.kind], "제목": w.title, "장르": w.genre,
            "분량": w.length_class, "글자 수": (w.stats or {}).get("chars", 0),
            "원고지(매)": (w.stats or {}).get("manuscript_pages", 0), "언어": LANGS.get(w.lang, w.lang),
            "상태": w.status, "ISBN": w.isbn, "수정": fmt_dt(w.updated_at)} for w in shown])
        ev = st.dataframe(df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row")
        sel = ev.selection.rows
        if sel:
            ss["cur_work"] = shown[sel[0]].id
        cur = get_work(ss.get("cur_work", 0), user.id) if ss.get("cur_work") else None
        if cur:
            st.divider()
            st.subheader(f"{KIND_ICON.get(cur.kind, '')} {cur.title}")
            stt, an = cur.stats or {}, cur.analysis or {}
            if stt:
                m = st.columns(5)
                m[0].metric("글자 수(공백 포함)", f"{stt.get('chars', 0):,}")
                m[1].metric("공백 제외", f"{stt.get('chars_no_space', 0):,}")
                m[2].metric("200자 원고지", f"{stt.get('manuscript_pages', 0):,}매")
                m[3].metric("단어 · 문단", f"{stt.get('words', 0):,} · {stt.get('paragraphs', 0):,}")
                m[4].metric("예상 독서 시간", f"{stt.get('reading_minutes', 0)}분")
            a, b = st.columns([1.3, 1], gap="large")
            with a:
                st.markdown("**분석 결과**" + (f" · {an.get('engine')}" if an.get("engine") else ""))
                if an.get("sampled"):
                    st.caption("원고가 길어 앞·중간·끝 부분을 발췌해 분석했습니다.")
                if an.get("logline"):
                    st.markdown(f"> {an['logline']}")
                if an.get("summary"):
                    st.write(an["summary"])
                for label, key in (("세부 장르", "sub_genres"), ("주제", "themes"), ("키워드", "keywords")):
                    if an.get(key):
                        st.markdown(f"**{label}** " + " ".join(f"`{x}`" for x in an[key]))
                for label, key in (("분위기·문체", "mood"), ("대상 독자", "audience")):
                    if an.get(key):
                        st.markdown(f"**{label}** {an[key]}")
                for label, key in (("강점", "strengths"), ("다듬으면 좋을 점", "suggestions")):
                    if an.get(key):
                        st.markdown(f"**{label}**\n" + "\n".join(f"- {x}" for x in an[key]))
                if cur.text.strip() and st.button("다시 분석", help="현재 본문으로 분량·장르를 새로 분석합니다."):
                    with st.spinner("분석 중…"):
                        stats = analysis.compute_stats(cur.text)
                        an2 = analysis.analyze(cur.text, cur.title)
                        update_work(cur.id, stats=stats, analysis=an2, genre=an2.get("genre", cur.genre),
                                    length_class=analysis.length_class(stats, cur.text), lang=stats["lang"])
                    if an2.get("error"):
                        ss["up_msgs"] = [(False, f"AI 분석 실패로 간이 분석을 썼습니다: {an2['error']}")]
                    st.rerun()
            with b:
                with st.form("meta"):
                    st.markdown("**분류 고치기**")
                    title = st.text_input("제목", cur.title)
                    genre = st.selectbox("장르", GENRES, index=GENRES.index(cur.genre) if cur.genre in GENRES else len(GENRES) - 1)
                    lc = st.selectbox("분량", LENGTHS, index=LENGTHS.index(cur.length_class) if cur.length_class in LENGTHS else len(LENGTHS) - 1)
                    lang = st.selectbox("원문 언어", list(LANGS), index=list(LANGS).index(cur.lang) if cur.lang in LANGS else 0,
                                        format_func=LANGS.get)
                    status = st.selectbox("상태", STATUSES, index=STATUSES.index(cur.status) if cur.status in STATUSES else 1)
                    if st.form_submit_button("저장"):
                        update_work(cur.id, title=title.strip() or cur.title, genre=genre, length_class=lc, lang=lang,
                                    status=status)
                        st.rerun()
                if cur.blob:
                    st.download_button("현재 파일 내려받기", cur.blob, file_name=cur.filename or cur.title,
                                       use_container_width=True)
                with st.popover("원고 삭제", use_container_width=True):
                    st.write("번역·전자책·홍보물·버전 기록까지 함께 지워지며 되돌릴 수 없습니다.")
                    if st.button("정말 삭제", type="primary"):
                        with db() as s:
                            for model in (Version, Translation, Ebook, Promo):
                                for row in s.scalars(select(model).where(model.work_id == cur.id)):
                                    s.delete(row)
                            s.delete(s.get(Work, cur.id))
                        ss.pop("cur_work", None)
                        st.rerun()

# ------------------------------------------------------------ 내보내기
with t_export:
    works = list_works(user.id)
    st.write("원고 목록과 분석 결과를 표 데이터로 내려받습니다. (본문·파일 자체는 포함하지 않습니다)")
    if works:
        with db() as s:
            wids = [w.id for w in works]
            trs = list(s.execute(select(Translation.work_id, Translation.lang).where(Translation.work_id.in_(wids))))
            ebs = list(s.execute(select(Ebook.work_id, Ebook.lang, Ebook.fmt).where(Ebook.work_id.in_(wids))))
        rows = []
        for w in works:
            stt, an = w.stats or {}, w.analysis or {}
            rows.append({
                "번호": w.id, "제목": w.title, "파일명": w.filename, "형식": docs.KIND_LABEL[w.kind], "장르": w.genre,
                "세부 장르": ", ".join(an.get("sub_genres", [])), "분량 분류": w.length_class,
                "언어": LANGS.get(w.lang, w.lang), "상태": w.status, "글자 수": stt.get("chars", 0),
                "공백 제외 글자 수": stt.get("chars_no_space", 0), "단어 수": stt.get("words", 0),
                "문단 수": stt.get("paragraphs", 0), "원고지(200자) 매수": stt.get("manuscript_pages", 0),
                "예상 독서 시간(분)": stt.get("reading_minutes", 0), "주제": ", ".join(an.get("themes", [])),
                "키워드": ", ".join(an.get("keywords", [])), "로그라인": an.get("logline", ""),
                "요약": an.get("summary", ""), "ISBN": w.isbn,
                "번역 언어": ", ".join(sorted({LANGS.get(l, l) for i, l in trs if i == w.id})),
                "전자책": ", ".join(sorted({f"{LANGS.get(l, l)}({f.upper()})" for i, l, f in ebs if i == w.id})),
                "등록일": fmt_dt(w.created_at), "수정일": fmt_dt(w.updated_at)})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True, height=260)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="원고 목록")
            ws = xw.sheets["원고 목록"]
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:50])
                ws.column_dimensions[col[0].column_letter].width = min(50, max(10, width * 1.6))
            ws.freeze_panes = "C2"
        stamp = datetime.now().strftime("%Y%m%d")
        c1, c2 = st.columns(2)
        c1.download_button("Excel(.xlsx) 내려받기", buf.getvalue(), f"원고목록_{stamp}.xlsx", type="primary",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        c2.download_button("CSV 내려받기", df.to_csv(index=False).encode("utf-8-sig"), f"원고목록_{stamp}.csv",
                           mime="text/csv", use_container_width=True)
    else:
        st.info("내보낼 원고가 없습니다.")
