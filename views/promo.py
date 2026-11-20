"""홍보 스튜디오: SNS 문구·해시태그, 카드 이미지, 숏폼 영상."""
import streamlit as st

from core import ebook, promo
from core.ai import ai_ready
from core.config import LANGS
from core.db import Promo, db, select
from core.pipeline import edition, get_translations
from core.ui import copy_block, fmt_dt, header, require_login, work_picker

user = require_login()
ss = st.session_state
header("📣 홍보 스튜디오", "전자책을 알릴 문구·해시태그·이미지·영상을 만들어 드립니다. 복사해서 SNS 에 붙여 넣으세요.")

w = work_picker(user, "pr_pick", need_text=True)
if not w:
    st.stop()

trs = get_translations(w.id)
c1, c2 = st.columns([1, 2])
lang = c1.selectbox("홍보 언어", [w.lang] + list(trs), format_func=lambda c: LANGS.get(c, c))
title, text = edition(w, lang)
author = c2.text_input("작가 표기", user.display)
cover = w.cover if (w.cover and lang == w.lang) else None
an = w.analysis or {}
if not ebook.script_supported(title + text[:2000]):
    st.warning("서버에 이 언어의 글꼴이 없어 이미지·영상의 글자가 깨질 수 있습니다. (배포 시 packages.txt 의 Noto 글꼴이 설치되면 해결됩니다)")


def latest(kind: str):
    with db() as s:
        return s.scalar(select(Promo).where(Promo.work_id == w.id, Promo.kind == kind, Promo.lang == lang)
                        .order_by(Promo.created_at.desc()))


def store(kind: str, label: str, content: dict, blob: bytes | None = None):
    with db() as s:
        for old in s.scalars(select(Promo).where(Promo.work_id == w.id, Promo.kind == kind, Promo.lang == lang,
                                                 Promo.label == label)):
            s.delete(old)
        s.add(Promo(work_id=w.id, kind=kind, lang=lang, label=label, content=content, blob=blob))


copy_row = latest("copy")
copy = copy_row.content if copy_row else {}

t_copy, t_video, t_image = st.tabs(["소개글 · 해시태그", "영상", "이미지 카드"])

# ------------------------------------------------------------ 문구
with t_copy:
    if not ai_ready():
        st.info("AI 키가 없어 기본 서식으로 만듭니다. ANTHROPIC_API_KEY 를 설정하면 플랫폼별 맞춤 문구를 써 드립니다.")
    if st.button("문구 새로 만들기" if copy else "문구 만들기", type="primary"):
        with st.spinner("작성 중…"):
            out = promo.make_copy(title, author, w.genre, an.get("summary", ""), an.get("keywords", []), text, lang)
        store("copy", "copy", out)
        if out.get("error"):
            ss["pr_err"] = out["error"]
        st.rerun()
    if ss.get("pr_err"):
        st.error("AI 작성에 실패해 기본 서식을 썼습니다: " + ss.pop("pr_err"))
    if copy:
        st.caption(f"{copy.get('engine', '')} · {fmt_dt(copy_row.created_at)} (UTC) — 각 상자 오른쪽 위의 복사 버튼을 누르세요. "
                   "게시 전에 사실 관계와 표현을 꼭 확인해 주세요.")
        tags = copy.get("hashtags", [])
        a, b = st.columns(2, gap="large")
        with a:
            copy_block("해시태그 (전체)", " ".join(tags))
            copy_block("해시태그 (인스타그램용 상위 15개)", " ".join(tags[:15]))
            copy_block("한 줄 카피", "\n".join(copy.get("one_liners", [])))
            copy_block("Instagram 캡션", copy.get("instagram", "") + ("\n\n" + " ".join(tags[:15]) if tags else ""))
            copy_block("TikTok 캡션", copy.get("tiktok", "") + (" " + " ".join(tags[:6]) if tags else ""))
            copy_block("X(Twitter)", copy.get("x", ""))
        with b:
            copy_block("YouTube 제목", copy.get("youtube_title", ""))
            copy_block("YouTube 설명", copy.get("youtube_description", "") + ("\n\n" + " ".join(tags[:10]) if tags else ""))
            copy_block("Facebook", copy.get("facebook", ""))
            copy_block("블로그 소개글", copy.get("blog", ""))
            copy_block("온라인 서점 책 소개", copy.get("bookstore", ""))
            copy_block("보도자료", copy.get("press_release", ""))

# ------------------------------------------------------------ 영상
with t_video:
    st.caption("표지 → 강한 한 문장 → 책 속 문장 → 제목·작가·구매 안내 순서로 15~20초 영상을 만듭니다. (MP4 · H.264)")
    quotes0 = copy.get("quotes") or promo.pick_quotes(text)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        size_name = st.selectbox("화면 비율", list(promo.VIDEO_SIZES))
        hook = st.text_input("첫 화면 문구", copy.get("hook", title))
        q = [st.text_input(f"책 속 문장 {i + 1}", quotes0[i] if i < len(quotes0) else "", key=f"vq{i}_{w.id}_{lang}") for i in range(3)]
        cta = st.text_input("마지막 안내 문구", "지금 전자책으로 만나 보세요" if lang == "ko" else "Available now as an ebook")
    with c2:
        theme = st.selectbox("배경 분위기 (표지가 없을 때)", list(ebook.COVER_THEMES))
        use_cover = st.checkbox("표지 넣기", value=True)
        music = st.checkbox("잔잔한 배경음 넣기 (앱이 직접 합성 · 저작권 걱정 없음)", value=True)
        narr = st.checkbox("책 속 문장 낭독 음성 넣기 (Google TTS · 인터넷 필요)")
        if not cover and use_cover:
            st.caption("저장된 표지가 없어 자동 표지를 만들어 씁니다. ('전자책 · ISBN → ① 표지'에서 바꿀 수 있습니다)")
    if st.button("영상 만들기", type="primary"):
        cv = (cover or ebook.make_cover(title, author, theme=theme)) if use_cover else None
        voice = None
        if narr:
            voice, err = promo.tts(". ".join(x for x in [hook, *q] if x.strip()), lang)
            if err:
                st.warning(err + " — 음성 없이 만듭니다.")
        bar = st.progress(0.0, text="영상을 그리는 중…")
        try:
            data = promo.make_video(title, author, hook, [x for x in q if x.strip()], cta, cv,
                                    promo.VIDEO_SIZES[size_name], theme, music, voice,
                                    progress=lambda p: bar.progress(p, text=f"영상을 그리는 중… {p:.0%}"))
            store("video", size_name, {"hook": hook}, data)
        except Exception as e:
            st.error(f"영상 제작 실패: {type(e).__name__}: {e}")
        bar.empty()
        st.rerun()
    with db() as s:
        vids = list(s.scalars(select(Promo).where(Promo.work_id == w.id, Promo.kind == "video", Promo.lang == lang)
                              .order_by(Promo.created_at.desc())))
    if vids:
        st.divider()
        cols = st.columns(3)
        for i, v in enumerate(vids):
            with cols[i % 3]:
                st.markdown(f"**{v.label}**")
                st.video(v.blob)
                k1, k2 = st.columns(2)
                k1.download_button("MP4 받기", v.blob, f"{title}_{v.label.split()[0]}_{lang}.mp4", mime="video/mp4",
                                   key=f"vd{v.id}", use_container_width=True)
                if k2.button("삭제", key=f"vx{v.id}", use_container_width=True):
                    with db() as s:
                        s.delete(s.get(Promo, v.id))
                    st.rerun()
        st.caption("올릴 때: 위 '소개글 · 해시태그' 탭의 캡션을 복사해 함께 붙여 넣으세요.")

# ------------------------------------------------------------ 이미지
with t_image:
    kind = st.radio("종류", ["인용구 카드", "출간 알림 카드"], horizontal=True)
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        theme_i = st.selectbox("배경 분위기", list(ebook.COVER_THEMES), key="img_theme")
        if kind == "인용구 카드":
            quotes0 = copy.get("quotes") or promo.pick_quotes(text)
            quote = st.text_area("문장", quotes0[0] if quotes0 else "", height=110)
            shape = st.selectbox("크기", ["정사각 1080×1080", "세로 1080×1350", "스토리 1080×1920"])
            bg_cover = st.checkbox("표지를 흐린 배경으로 쓰기", value=bool(cover))
            size = {"정사각 1080×1080": (1080, 1080), "세로 1080×1350": (1080, 1350), "스토리 1080×1920": (1080, 1920)}[shape]
            img = promo.quote_card(quote or " ", title, author, cover if bg_cover else None, theme_i, size)
        else:
            tagline = st.text_input("한 줄 소개", (copy.get("one_liners") or [an.get("logline", "")])[0])
            badge = st.text_input("배지 문구", "전자책 출간" if lang == "ko" else "OUT NOW")
            img = promo.launch_card(title, author, tagline, cover or ebook.make_cover(title, author, theme=theme_i), badge)
    with c2:
        st.image(img, use_container_width=True)
        st.download_button("PNG 내려받기", img, f"{title}_{kind}_{lang}.png", mime="image/png", type="primary")
