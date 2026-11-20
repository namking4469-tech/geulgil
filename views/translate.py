"""번역: 세계 주요 10개 언어로 자동 번역 → 검수 → (선택) 전자책 자동 제작."""
import streamlit as st

from core import docs
from core.ai import ai_ready
from core.config import LANGS
from core.pipeline import get_translations, make_ebooks, save_translation
from core.translate import engine_name, translate, translate_title
from core.ui import fmt_dt, header, require_login, update_work, work_picker

user = require_login()
ss = st.session_state
header("🌐 번역", "원고를 세계에서 가장 널리 쓰이는 언어들로 번역합니다. 번역이 끝나면 전자책까지 자동으로 만들 수 있습니다.")

w = work_picker(user, "tr_pick", need_text=True)
if not w:
    st.stop()

if ai_ready():
    st.caption(f"번역 엔진: **Claude** (문학 번역). 원고 내용이 Anthropic API 로 전송됩니다.")
else:
    st.info("AI 키가 없어 **무료 기계번역(Google)** 으로 동작합니다. 뜻은 통하지만 문학적 품질은 낮으니, "
            "출간용은 ANTHROPIC_API_KEY 설정 후 다시 번역하거나 전문 번역가의 감수를 받으세요.")

trs = get_translations(w.id)
targets_all = [c for c in LANGS if c != w.lang]
chars = (w.stats or {}).get("chars", len(w.text))

t_run, t_review = st.tabs(["자동 번역", f"검수 · 내려받기 ({len(trs)})"])

with t_run:
    st.write(f"원문: **{LANGS.get(w.lang, w.lang)}** · {chars:,}자")
    c1, c2 = st.columns([2, 1])
    picked = c1.multiselect("번역할 언어", targets_all, default=[c for c in targets_all if c not in trs],
                            format_func=LANGS.get)
    if c2.button("전체 선택", use_container_width=True):
        ss["tr_all"] = True
    if ss.pop("tr_all", False):
        picked = targets_all
    done = [LANGS[c] for c in picked if c in trs]
    if done:
        st.warning("이미 번역이 있는 언어는 덮어씁니다: " + ", ".join(done))
    glossary = st.text_area("용어집 (선택) — 인명·지명·고유명사를 어떻게 옮길지 한 줄에 하나씩",
                            (w.analysis or {}).get("glossary", ""), height=90,
                            placeholder="김서연 = Seoyeon Kim\n달동네 = hillside shantytown",
                            help="Claude 번역에서만 적용됩니다.")
    auto_book = st.checkbox("번역이 끝나면 언어별 전자책(EPUB)을 자동으로 만들기", value=True)
    if picked:
        st.caption(f"번역 분량: {chars:,}자 × {len(picked)}개 언어 = 약 {chars * len(picked):,}자. "
                   + ("분량에 비례해 API 비용과 시간이 듭니다. 긴 원고는 언어를 나눠 실행하세요." if ai_ready() else
                      "분량이 많으면 시간이 걸립니다."))
    if st.button(f"{len(picked)}개 언어로 번역 시작", type="primary", disabled=not picked):
        an = dict(w.analysis or {})
        an["glossary"] = glossary
        update_work(w.id, analysis=an)
        log = []
        for i, lang in enumerate(picked, 1):
            bar = st.progress(0.0, text=f"[{i}/{len(picked)}] {LANGS[lang]} 번역 중…")
            try:
                out, eng = translate(w.text, w.lang, lang, glossary, w.genre,
                                     progress=lambda p, b=bar, n=LANGS[lang]: b.progress(p, text=f"[{i}/{len(picked)}] {n} 번역 중… {p:.0%}"))
                title = translate_title(w.title, w.lang, lang)
                save_translation(w.id, lang, title, out, eng)
                log.append((True, f"{LANGS[lang]}: 번역 완료 ({len(out):,}자, {eng})"))
                if auto_book:
                    for m in make_ebooks(w, user, lang, ["epub"]):
                        log.append(("완성" in m, m.replace(lang, LANGS[lang], 1)))
            except RuntimeError as e:
                log.append((False, f"{LANGS[lang]}: 실패 — {e}"))
            bar.empty()
        ss["tr_log"] = log
        st.rerun()
    for ok, msg in ss.pop("tr_log", []):
        (st.success if ok else st.error)(msg)

with t_review:
    if not trs:
        st.info("아직 번역이 없습니다.")
    else:
        lang = st.radio("언어", list(trs), horizontal=True,
                        format_func=lambda c: LANGS.get(c, c) + (" ✓" if trs[c].reviewed else ""))
        t = trs[lang]
        st.caption(f"{t.engine} · 수정 {fmt_dt(t.updated_at)} (UTC) · {len(t.text):,}자"
                   + (" · 검수 완료" if t.reviewed else " · 검수 전"))
        st.warning("자동 번역은 오역·누락이 있을 수 있습니다. 출간 전에는 그 언어를 아는 사람의 검수를 권합니다.", icon="⚠️")
        title = st.text_input("번역 제목", t.title, key=f"tt_{lang}")
        c1, c2 = st.columns(2)
        c1.text_area("원문", w.text, height=480, disabled=True, key=f"src_{w.id}")
        text = c2.text_area("번역문 (직접 고칠 수 있습니다)", t.text, height=480, key=f"tx_{w.id}_{lang}")
        k = st.columns(4)
        if k[0].button("저장", type="primary", use_container_width=True):
            save_translation(w.id, lang, title, text, t.engine, t.reviewed)
            st.rerun()
        if k[1].button("검수 완료로 표시" if not t.reviewed else "검수 표시 해제", use_container_width=True):
            save_translation(w.id, lang, title, text, t.engine, not t.reviewed)
            st.rerun()
        k[2].download_button("TXT", text.encode("utf-8"), f"{title or w.title}_{lang}.txt", use_container_width=True)
        k[3].download_button("DOCX", docs.text_to_docx(text, title), f"{title or w.title}_{lang}.docx",
                             use_container_width=True)
