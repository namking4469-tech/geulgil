"""여러 화면이 함께 쓰는 작업 흐름: 번역 저장, 전자책 제작·저장."""
from datetime import datetime

from . import ebook
from .db import Ebook, Translation, User, Work, db, select


def get_translations(work_id: int) -> dict[str, Translation]:
    with db() as s:
        return {t.lang: t for t in s.scalars(select(Translation).where(Translation.work_id == work_id))}


def save_translation(work_id: int, lang: str, title: str, text: str, engine: str, reviewed: bool = False):
    with db() as s:
        t = s.scalar(select(Translation).where(Translation.work_id == work_id, Translation.lang == lang))
        if not t:
            t = Translation(work_id=work_id, lang=lang)
            s.add(t)
        t.title, t.text, t.engine, t.reviewed, t.updated_at = title, text, engine, reviewed, datetime.utcnow()


def edition(w: Work, lang: str) -> tuple[str, str] | None:
    """해당 언어판의 (제목, 본문). 원문 언어면 원고 자체, 아니면 저장된 번역."""
    if lang == w.lang:
        return w.title, w.text
    t = get_translations(w.id).get(lang)
    return (t.title or w.title, t.text) if t else None


def make_ebooks(w: Work, user: User, lang: str, fmts: list[str], publisher: str = "", theme: str = "밤하늘",
                author: str = "", cover: bytes | None = None) -> list[str]:
    """언어판 하나의 전자책을 만들어 저장한다. 결과 메시지 목록을 돌려준다."""
    ed = edition(w, lang)
    if not ed or not ed[1].strip():
        return [f"{lang}: 본문이 없어 만들지 못했습니다."]
    title, text = ed
    author = author or user.display
    poem = w.length_class == "시" or w.genre == "시"
    an = w.analysis or {}
    if cover is None:
        cover = w.cover if (w.cover and lang == w.lang) else ebook.make_cover(title, author, theme=theme)
    msgs = []
    for fmt in fmts:
        try:
            if fmt == "epub":
                data = ebook.build_epub(title, author, text, lang, cover, w.isbn, publisher,
                                        an.get("summary", "") if lang == w.lang else "", user.bio if lang == w.lang else "",
                                        poem, [w.genre] if w.genre else None)
            else:
                if not ebook.font_covers(title + text):
                    msgs.append(f"{lang} PDF: 내장 글꼴이 이 언어의 문자를 지원하지 않아 건너뜁니다(EPUB 은 제공).")
                    continue
                data = ebook.build_pdf_book(title, author, text, lang, cover, w.isbn, publisher,
                                            user.bio if lang == w.lang else "", poem)
        except Exception as e:
            msgs.append(f"{lang} {fmt.upper()}: 제작 실패 ({type(e).__name__}: {e})")
            continue
        with db() as s:
            for old in s.scalars(select(Ebook).where(Ebook.work_id == w.id, Ebook.lang == lang, Ebook.fmt == fmt)):
                s.delete(old)
            s.add(Ebook(work_id=w.id, lang=lang, fmt=fmt, title=title, blob=data))
        msgs.append(f"{lang} {fmt.upper()}: 완성")
    return msgs
