"""전 세계 문학 에이전시 · 출판사 · 플랫폼 · 지원기관 찾기 + 원터치 작품 소개."""
import streamlit as st

from core import docs
from core.ai import AIError, ai_ready, ask_json
from core.config import LANG_EN, LANGS
from core.db import DirEntry, Submission, db, select
from core.mailer import mailto_link, send_mail, smtp_ready
from core.pipeline import edition, get_translations
from core.ui import copy_block, get_work, header, list_works, require_login

user = require_login()
ss = st.session_state
header("🌍 에이전시 · 출판사 · 플랫폼", "작품을 세상에 내보낼 곳을 찾고, 준비된 소개 편지를 한 번에 보냅니다.")
st.caption("투고 방침과 연락처는 수시로 바뀝니다. 보내기 전에 각 곳의 공식 사이트에서 **투고 지침(submission guidelines)** 을 확인해 주세요. "
           "대형 출판사는 대부분 에이전트를 통해서만 원고를 받습니다.")

with db() as s:
    entries = list(s.scalars(select(DirEntry).order_by(DirEntry.kind, DirEntry.name)))

c1, c2, c3, c4 = st.columns([1.2, 1, 1.2, 1.2])
kinds = c1.multiselect("종류", sorted({e.kind for e in entries}))
countries = c2.multiselect("국가", sorted({e.country for e in entries}))
f_genre = c3.multiselect("장르", sorted({g for e in entries for g in e.genres}))
q = c4.text_input("검색")
shown = [e for e in entries if (not kinds or e.kind in kinds) and (not countries or e.country in countries)
         and (not f_genre or set(f_genre) & set(e.genres) or not e.genres)
         and (not q or q.lower() in (e.name + e.note + e.accepts).lower())]
st.caption(f"{len(shown)}곳")

ICON = {"에이전시": "🤝", "출판사": "🏢", "플랫폼": "💻", "지원기관": "🏛️"}
for e in shown:
    with st.expander(f"{ICON.get(e.kind, '')} **{e.name}** — {e.kind} · {e.country}"):
        a, b = st.columns([2.2, 1])
        with a:
            st.markdown((f"- **분야**: {', '.join(e.genres)}\n" if e.genres else "")
                        + f"- **접수 방식**: {e.accepts}" + (f"\n- {e.note}" if e.note else "")
                        + (f"\n- **투고 이메일**: `{e.email}`" if e.email else ""))
        with b:
            if e.url:
                st.link_button("공식 사이트", e.url, use_container_width=True)
            if e.kind in ("에이전시", "출판사"):
                if st.button("✉️ 원터치 작품 소개", key=f"p{e.id}", type="primary", use_container_width=True):
                    ss["pitch_to"] = e.id
                    ss.pop("pitch", None)
                    st.rerun()

# ------------------------------------------------------------ 원터치 소개
target = next((e for e in entries if e.id == ss.get("pitch_to")), None)
if target:
    st.divider()
    st.subheader(f"✉️ {target.name} 에 작품 소개하기")
    works = [w for w in list_works(user.id) if (w.stats or {}).get("chars")]
    if not works:
        st.info("소개할 원고가 없습니다. 먼저 원고 서재에 원고를 올려 주세요.")
        st.stop()
    by = {w.id: w for w in works}
    c1, c2 = st.columns(2)
    wid = c1.selectbox("소개할 작품", list(by), format_func=lambda i: by[i].title)
    w = get_work(wid, user.id)
    trs = get_translations(w.id)
    default_lang = "ko" if target.country == "한국" else "en"
    lang_opts = list(LANGS)
    lang = c2.selectbox("편지 언어", lang_opts, index=lang_opts.index(default_lang), format_func=LANGS.get)
    ed = edition(w, lang)
    if not ed and lang != w.lang:
        st.caption(f"이 작품의 {LANGS[lang]} 번역본이 없어 샘플 원고는 원문으로 첨부됩니다. (번역 화면에서 먼저 번역하면 번역본이 첨부됩니다)")
    title, text = ed or (w.title, w.text)
    an = w.analysis or {}

    if st.button("소개 편지 쓰기" if "pitch" not in ss else "다시 쓰기"):
        stt = w.stats or {}
        facts = (f"작품 제목: {title}\n장르: {w.genre}\n분량: {stt.get('chars', 0):,}자 / {stt.get('words', 0):,} 단어 ({w.length_class})\n"
                 f"로그라인: {an.get('logline', '')}\n요약: {an.get('summary', '')}\n주제: {', '.join(an.get('themes', []))}\n"
                 f"작가 이름: {user.display}\n등단·경력: {user.debut}\n작가 소개: {user.bio}\n대표작: {user.major_works}\n"
                 f"작가 이메일: {user.email}")
        if ai_ready():
            try:
                with st.spinner("작성 중…"):
                    out = ask_json(
                        f"당신은 문학 에이전트에게 보내는 투고 편지(query letter) 전문가입니다. 아래 사실만 사용해 "
                        f"{LANGS[lang]}({LANG_EN[lang]})로 편지를 쓰세요. 받는 곳: {target.name} ({target.kind}, {target.country}).\n"
                        f"주어지지 않은 수상 경력·판매량·추천사·비교 도서는 절대 지어내지 마세요. 비어 있는 항목은 언급하지 마세요.\n"
                        f"업계 관행(정중한 인사 → 작품 소개 훅 → 줄거리 요약 → 분량·장르 → 작가 약력 → 맺음)을 따르고 300단어 안팎으로.\n\n"
                        f"{facts}\n\nJSON 키: subject(메일 제목), body(편지 본문), synopsis(한 문단 시놉시스)", max_tokens=4000)
                ss["pitch"] = out
            except AIError as e:
                st.error(str(e))
        if "pitch" not in ss or not ai_ready():
            ss["pitch"] = {
                "subject": f"[투고] {w.genre} 《{title}》 — {user.display}" if lang == "ko" else f"Query: {title} ({w.genre}) by {user.display}",
                "body": (f"{target.name} 담당자님께,\n\n안녕하세요. {user.display}입니다.\n{w.length_class} {w.genre} 《{title}》을 소개드리고자 "
                         f"연락드립니다.\n\n{an.get('summary', '')}\n\n분량은 {(w.stats or {}).get('chars', 0):,}자"
                         f"(200자 원고지 {(w.stats or {}).get('manuscript_pages', 0):,}매)입니다.\n\n{user.bio}\n{user.debut}\n\n"
                         f"샘플 원고를 첨부합니다. 검토해 주시면 감사하겠습니다.\n\n{user.display} 드림\n{user.email}"),
                "synopsis": an.get("summary", "")}
            if lang != "ko" and not ai_ready():
                st.info("AI 키가 없어 한국어 기본 서식으로 작성했습니다. 직접 번역하거나 고쳐 써 주세요.")

    if "pitch" in ss:
        p = ss["pitch"]
        subject = st.text_input("메일 제목", p.get("subject", ""))
        body = st.text_area("편지 본문 (자유롭게 고치세요)", p.get("body", ""), height=340)
        c1, c2 = st.columns(2)
        to = c1.text_input("받는 이메일", target.email, placeholder="공식 사이트의 투고 주소를 확인해 입력",
                           help="이 주소록에는 확인되지 않은 이메일을 넣어 두지 않았습니다. 공식 사이트에서 투고 주소를 확인해 주세요.")
        n_sample = c2.select_slider("첨부할 샘플 원고 분량", [0, 3000, 5000, 10000, 20000], 5000,
                                    format_func=lambda n: "첨부 안 함" if not n else f"앞부분 {n:,}자")
        checked = st.checkbox(f"{target.name} 의 투고 지침을 확인했고, 이 방식의 투고를 받는 곳임을 확인했습니다.")
        atts = []
        if n_sample:
            atts.append((f"{title}_sample.docx", docs.text_to_docx(text[:n_sample], title),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        if p.get("synopsis"):
            atts.append((f"{title}_synopsis.docx", docs.text_to_docx(p["synopsis"], f"{title} — Synopsis"),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))

        def record(status: str):
            with db() as s:
                s.add(Submission(user_id=user.id, work_id=w.id, target_type=target.kind, target_name=target.name,
                                 sent_to=to, status=status, body=f"{subject}\n\n{body}"))

        k1, k2, k3 = st.columns(3)
        if smtp_ready():
            if k1.button("📨 지금 보내기", type="primary", disabled=not (checked and to.strip()), use_container_width=True):
                ok, err = send_mail(to.strip(), subject, body, reply_to=user.email, sender_name=user.display,
                                    attachments=atts)
                if ok:
                    record("발송")
                    ss.pop("pitch")
                    ss.pop("pitch_to")
                    st.success(f"{to} 로 보냈습니다. 답장은 {user.email} 로 옵니다. '투고 관리'에 기록했습니다.")
                else:
                    st.error(f"발송 실패: {err}")
        else:
            k1.link_button("📨 내 메일 앱으로 열기", mailto_link(to.strip() or "", subject, body),
                           disabled=not (checked and to.strip()), use_container_width=True)
            st.caption("앱에 메일 서버(SMTP)가 설정되지 않아 직접 발송은 꺼져 있습니다. 위 버튼은 내 메일 앱에 제목·본문을 채워 엽니다. "
                       "첨부 파일은 아래에서 내려받아 직접 붙여 주세요.")
        if k2.button("보낸 것으로 기록", disabled=not checked, use_container_width=True):
            record("발송")
            st.toast("'투고 관리'에 기록했습니다.")
        if k3.button("닫기", use_container_width=True):
            ss.pop("pitch", None)
            ss.pop("pitch_to", None)
            st.rerun()
        with st.expander("복사 · 첨부 파일 내려받기"):
            copy_block("제목", subject)
            copy_block("본문", body)
            for name, data, mime in atts:
                st.download_button(name, data, name, mime=mime, key=f"att_{name}")
