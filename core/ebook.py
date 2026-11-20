"""전자책 제작: 표지 생성, 장(章) 나누기, EPUB 3 / PDF 생성, ISBN 검증·바코드."""
import functools
import glob
import html as htmllib
import io
import re
import uuid
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from .config import FONT_DIR, RTL_LANGS


# ---------------------------------------------------------------- 글꼴·줄바꿈 (홍보 이미지와 공용)
_SYS_FONTS = {  # 나눔 글꼴에 없는 문자용(서버에 Noto 글꼴이 설치돼 있으면 사용; packages.txt 참고)
    "ar": (["NotoNaskhArabic-{w}.ttf", "NotoSansArabic-{w}.ttf"], 0),
    "hi": (["NotoSerifDevanagari-{w}.ttf", "NotoSansDevanagari-{w}.ttf"], 0),
    "ru": (["NotoSerif-{w}.ttf", "NotoSans-{w}.ttf"], 0),
    "ja": (["NotoSerifCJK-{w}.ttc", "NotoSansCJK-{w}.ttc"], 0),
    "zh": (["NotoSerifCJK-{w}.ttc", "NotoSansCJK-{w}.ttc"], 2),
}


def _script(text: str) -> str | None:
    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text) and not font_covers(text):
        return "zh"
    return None


@functools.lru_cache(maxsize=64)
def _sys_font(script: str, bold: bool) -> tuple[str, int] | None:
    names, index = _SYS_FONTS[script]
    for weight in (("Bold", "Regular") if bold else ("Regular",)):
        for n in names:
            hits = glob.glob(f"/usr/share/fonts/**/{n.format(w=weight)}", recursive=True)
            if hits:
                return hits[0], index
    return None


def script_supported(text: str) -> bool:
    """이 글을 이미지·영상에 제대로 그릴 글꼴이 있는가?"""
    sc = _script(text)
    return font_covers(text) if sc in (None, "ru") else _sys_font(sc, False) is not None


def font(size: int, bold: bool = False, serif: bool = False, text: str = "") -> ImageFont.FreeTypeFont:
    """text 를 주면 그 글의 문자(아랍·데바나가리·가나·간체)에 맞는 글꼴을 고른다."""
    sc = _script(text) if text else None
    if sc:
        hit = _sys_font(sc, bold)
        if hit:
            return ImageFont.truetype(hit[0], size, index=hit[1])
    name = ("NanumMyeongjoBold.ttf" if bold else "NanumMyeongjo.ttf") if serif else \
        ("NanumGothicBold.ttf" if bold else "NanumGothic.ttf")
    return ImageFont.truetype(str(FONT_DIR / name), size)


def font_covers(text: str) -> bool:
    """내장 글꼴(나눔)로 이 글을 그릴 수 있는가? 아랍어·힌디어·간체 한자 일부는 불가."""
    from reportlab.pdfbase.ttfonts import TTFont
    global _CMAP
    try:
        _CMAP
    except NameError:
        _CMAP = set(TTFont("_probe", str(FONT_DIR / "NanumMyeongjo.ttf")).face.charToGlyph)
    chars = {c for c in text[:20000] if not c.isspace()}
    if not chars:
        return True
    return sum(ord(c) not in _CMAP for c in chars) / len(chars) < 0.02


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    lines = []
    for para in text.split("\n"):
        cur = ""
        # 띄어쓰기가 있으면 단어 단위, 없으면 글자 단위로 줄바꿈
        tokens = re.findall(r"\S+\s*", para) if " " in para else list(para)
        for tok in tokens:
            if draw.textlength(cur + tok, font=fnt) <= max_w or not cur:
                cur += tok
            else:
                lines.append(cur.rstrip())
                cur = tok
            while draw.textlength(cur, font=fnt) > max_w and len(cur) > 1:  # 아주 긴 단어
                k = len(cur) - 1
                while k > 1 and draw.textlength(cur[:k], font=fnt) > max_w:
                    k -= 1
                lines.append(cur[:k])
                cur = cur[k:]
        lines.append(cur.rstrip())
    return lines


COVER_THEMES = {
    "밤하늘": ((18, 24, 54), (64, 42, 110), (255, 255, 255)),
    "노을": ((250, 112, 84), (120, 40, 110), (255, 255, 255)),
    "숲": ((20, 60, 50), (90, 140, 100), (255, 255, 255)),
    "바다": ((10, 70, 120), (60, 170, 190), (255, 255, 255)),
    "한지": ((244, 236, 220), (222, 205, 178), (50, 40, 30)),
    "먹": ((20, 20, 22), (70, 70, 76), (240, 240, 240)),
    "벚꽃": ((252, 228, 236), (244, 170, 190), (80, 30, 50)),
}


def gradient(size: tuple[int, int], c1, c2) -> Image.Image:
    w, h = size
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        col.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    return col.resize((w, h))


def make_cover(title: str, author: str, subtitle: str = "", theme: str = "밤하늘",
               size: tuple[int, int] = (1600, 2400)) -> bytes:
    c1, c2, fg = COVER_THEMES.get(theme, COVER_THEMES["밤하늘"])
    img = gradient(size, c1, c2)
    d = ImageDraw.Draw(img)
    w, h = size
    m = int(w * 0.11)
    d.rectangle([m // 2, m // 2, w - m // 2, h - m // 2], outline=fg, width=3)
    fs = int(w * 0.105)
    while True:
        ft = font(fs, bold=True, serif=True, text=title)
        lines = wrap(d, title, ft, w - 2 * m)
        if len(lines) <= 4 or fs < 60:
            break
        fs -= 10
    y = int(h * 0.24)
    for ln in lines:
        d.text((w / 2, y), ln, font=ft, fill=fg, anchor="ma")
        y += int(fs * 1.35)
    if subtitle:
        y += 20
        fsb = font(int(w * 0.036), serif=True, text=subtitle)
        for ln in wrap(d, subtitle, fsb, w - 2 * m):
            d.text((w / 2, y), ln, font=fsb, fill=fg, anchor="ma")
            y += int(w * 0.05)
    d.line([w / 2 - 90, h * 0.76, w / 2 + 90, h * 0.76], fill=fg, width=3)
    d.text((w / 2, h * 0.79), author, font=font(int(w * 0.05), serif=True, text=author), fill=fg, anchor="ma")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ---------------------------------------------------------------- 장 나누기
_CHAPTER = re.compile(
    r"^\s*(제\s*\d+\s*[장화부편회]|\d+\s*[장화부]|chapter\s+\w+|part\s+\w+|prologue|epilogue|프롤로그|에필로그|"
    r"capítulo\s+\w+|chapitre\s+\w+|kapitel\s+\w+|第\s*[\d一二三四五六七八九十百]+\s*[章話话回]|глава\s+\w+|#{1,3}\s+.+)"
    r"[\s.:：\-–—]*.{0,60}$", re.I)


def split_chapters(text: str) -> list[tuple[str, str]]:
    """[(장 제목, 본문)]. 장 표시가 없으면 한 덩어리로 돌려준다(제목은 빈 문자열)."""
    chapters, title, buf = [], "", []
    for line in text.split("\n"):
        if _CHAPTER.match(line) and len(line.strip()) <= 80:
            if title or any(b.strip() for b in buf):
                chapters.append((title, "\n".join(buf).strip("\n")))
            title, buf = line.strip().lstrip("#").strip(), []
        else:
            buf.append(line)
    if title or any(b.strip() for b in buf):
        chapters.append((title, "\n".join(buf).strip("\n")))
    return chapters or [("", text)]


_UI = {  # 전자책 속 고정 문구
    "ko": ("차례", "지은이", "판권", "본문", "지은이 소개", "발행일", "이 책의 저작권은 지은이에게 있습니다. 무단 전재와 복제를 금합니다."),
    "en": ("Contents", "Author", "Copyright", "Text", "About the Author", "Published", "All rights reserved. No part of this book may be reproduced without permission."),
    "ja": ("目次", "著者", "奥付", "本文", "著者紹介", "発行日", "本書の著作権は著者に帰属します。無断転載・複製を禁じます。"),
    "zh": ("目录", "作者", "版权", "正文", "作者简介", "出版日期", "版权所有，未经许可不得转载或复制。"),
    "es": ("Índice", "Autor", "Créditos", "Texto", "Sobre el autor", "Publicado", "Todos los derechos reservados."),
    "fr": ("Sommaire", "Auteur", "Mentions légales", "Texte", "À propos de l’auteur", "Publication", "Tous droits réservés."),
    "pt": ("Sumário", "Autor", "Créditos", "Texto", "Sobre o autor", "Publicação", "Todos os direitos reservados."),
    "de": ("Inhalt", "Autor", "Impressum", "Text", "Über den Autor", "Erschienen", "Alle Rechte vorbehalten."),
    "ru": ("Содержание", "Автор", "Выходные данные", "Текст", "Об авторе", "Дата издания", "Все права защищены."),
    "hi": ("विषय-सूची", "लेखक", "कॉपीराइट", "पाठ", "लेखक के बारे में", "प्रकाशन", "सर्वाधिकार सुरक्षित।"),
    "ar": ("المحتويات", "المؤلف", "حقوق النشر", "النص", "عن المؤلف", "تاريخ النشر", "جميع الحقوق محفوظة."),
}


def _paras_html(body: str, poem: bool) -> str:
    out = []
    for line in body.split("\n"):
        if line.strip():
            out.append(f'<p class="{"v" if poem else "p"}">{htmllib.escape(line.strip() if not poem else line)}</p>')
        else:
            out.append('<p class="gap">&#160;</p>')
    return "\n".join(out)


def build_epub(title: str, author: str, text: str, lang: str = "ko", cover: bytes | None = None,
               isbn: str = "", publisher: str = "", description: str = "", bio: str = "",
               poem: bool = False, subjects: list[str] | None = None) -> bytes:
    from ebooklib import epub
    ui = _UI.get(lang, _UI["en"])
    rtl = lang in RTL_LANGS
    book = epub.EpubBook()
    book.set_identifier(f"urn:isbn:{isbn_digits(isbn)}" if isbn else f"urn:uuid:{uuid.uuid4()}")
    book.set_title(title)
    book.set_language({"zh": "zh-Hans"}.get(lang, lang))
    book.add_author(author)
    if publisher:
        book.add_metadata("DC", "publisher", publisher)
    if description:
        book.add_metadata("DC", "description", description)
    book.add_metadata("DC", "date", date.today().isoformat())
    for sub in subjects or []:
        book.add_metadata("DC", "subject", sub)
    if rtl:
        book.set_direction("rtl")
    if cover:
        book.set_cover("cover.jpg", cover)
    css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=f"""
body {{ line-height: 1.8; margin: 5%; {"text-align: right;" if rtl else ""} }}
h1 {{ font-size: 1.5em; margin: 2.5em 0 1.5em; text-align: center; }}
p.p {{ margin: 0; text-indent: 1em; text-align: justify; }}
p.v {{ margin: 0; white-space: pre-wrap; }}
p.gap {{ margin: 0; }}
.title-page {{ text-align: center; margin-top: 30%; }}
.title-page h1 {{ font-size: 2em; margin-bottom: .6em; }}
.small {{ font-size: .85em; line-height: 1.6; }}
""")
    book.add_item(css)

    def page(name, heading, body_html):
        ch = epub.EpubHtml(title=heading, file_name=name, lang=lang, direction="rtl" if rtl else None)
        ch.content = body_html
        ch.add_item(css)
        book.add_item(ch)
        return ch

    e = htmllib.escape
    title_pg = page("title.xhtml", title, f'<div class="title-page"><h1>{e(title)}</h1><p>{e(author)}</p></div>')
    rights = [f"<h1>{e(ui[2])}</h1>", f'<p class="small"><b>{e(title)}</b></p>',
              f'<p class="small">{e(ui[1])}: {e(author)}</p>']
    if publisher:
        rights.append(f'<p class="small">{e(publisher)}</p>')
    rights.append(f'<p class="small">{e(ui[5])}: {date.today().isoformat()}</p>')
    if isbn:
        rights.append(f'<p class="small">ISBN {e(isbn)}</p>')
    rights.append(f'<p class="small">© {date.today().year} {e(author)}. {e(ui[6])}</p>')
    rights_pg = page("copyright.xhtml", ui[2], "\n".join(rights))

    chapters = []
    for i, (ctitle, body) in enumerate(split_chapters(text), 1):
        head = ctitle or (ui[3] if i == 1 else f"{i}")
        chapters.append(page(f"chap_{i:03d}.xhtml", head,
                             (f"<h1>{e(ctitle)}</h1>" if ctitle else "") + _paras_html(body, poem)))
    extra = []
    if bio.strip():
        extra.append(page("author.xhtml", ui[4], f"<h1>{e(ui[4])}</h1>" + _paras_html(bio, False)))
    book.toc = [title_pg, *chapters, *extra, rights_pg]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav(title=ui[0]))
    if cover:  # 표지 쪽을 본문 흐름에 포함(EPUBCheck OPF-096 방지)
        for item in book.get_items():
            if item.get_id() == "cover":
                item.is_linear = True
    book.spine = ([("cover", "yes")] if cover else []) + [title_pg, "nav", *chapters, *extra, rights_pg]
    buf = io.BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue()


def build_pdf_book(title: str, author: str, text: str, lang: str = "ko", cover: bytes | None = None,
                   isbn: str = "", publisher: str = "", bio: str = "", poem: bool = False) -> bytes:
    """판형 A5 PDF 전자책. 내장 글꼴이 지원하는 언어만 가능(font_covers 로 미리 확인)."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer
    from .docs import register_fonts
    register_fonts()
    ui = _UI.get(lang, _UI["en"])
    cjk = lang in ("ko", "ja", "zh")
    body = ParagraphStyle("b", fontName="Myeongjo", fontSize=10.5, leading=18.5,
                          wordWrap="CJK" if cjk else None, firstLineIndent=0 if poem else 10.5,
                          alignment=0 if poem else 4)
    h1 = ParagraphStyle("h1", fontName="MyeongjoB", fontSize=16, leading=24, alignment=TA_CENTER, spaceAfter=22,
                        spaceBefore=30)
    big = ParagraphStyle("big", fontName="MyeongjoB", fontSize=24, leading=34, alignment=TA_CENTER)
    mid = ParagraphStyle("mid", fontName="Myeongjo", fontSize=13, leading=20, alignment=TA_CENTER)
    small = ParagraphStyle("s", fontName="Nanum", fontSize=8.5, leading=14)
    e = htmllib.escape
    w, h = A5
    flow = []
    if cover:
        flow += [RLImage(io.BytesIO(cover), width=w, height=h), PageBreak()]
    flow += [Spacer(1, 55 * mm), Paragraph(e(title), big), Spacer(1, 10 * mm), Paragraph(e(author), mid), PageBreak()]
    for ctitle, btxt in split_chapters(text):
        if ctitle:
            flow.append(Paragraph(e(ctitle), h1))
        for line in btxt.split("\n"):
            flow.append(Paragraph(e(line).replace("  ", "&nbsp; ") if poem else e(line.strip()), body)
                        if line.strip() else Spacer(1, 9))
        flow.append(PageBreak())
    if bio.strip():
        flow.append(Paragraph(e(ui[4]), h1))
        flow += [Paragraph(e(ln), body) for ln in bio.split("\n") if ln.strip()]
        flow.append(PageBreak())
    flow += [Spacer(1, 110 * mm), Paragraph(f"<b>{e(title)}</b>", small), Paragraph(f"{e(ui[1])}: {e(author)}", small)]
    if publisher:
        flow.append(Paragraph(e(publisher), small))
    flow.append(Paragraph(f"{e(ui[5])}: {date.today().isoformat()}", small))
    if isbn:
        flow.append(Paragraph(f"ISBN {e(isbn)}", small))
    flow.append(Paragraph(f"© {date.today().year} {e(author)}. {e(ui[6])}", small))

    def number(canvas, doc):
        if doc.page > (2 if cover else 1):
            canvas.setFont("Nanum", 8)
            canvas.drawCentredString(w / 2, 10 * mm, str(doc.page))

    def first(canvas, doc):
        pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A5, leftMargin=0 if cover else 18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm, title=title, author=author)
    if cover:  # 표지는 여백 없이 전면에
        from reportlab.platypus import BaseDocTemplate, Frame, NextPageTemplate, PageTemplate
        doc = BaseDocTemplate(buf, pagesize=A5, title=title, author=author)
        doc.addPageTemplates([
            PageTemplate("cover", [Frame(0, 0, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]),
            PageTemplate("body", [Frame(18 * mm, 20 * mm, w - 36 * mm, h - 40 * mm)], onPage=number)])
        flow.insert(1, NextPageTemplate("body"))
        doc.build(flow)
    else:
        doc.build(flow, onFirstPage=first, onLaterPages=number)
    return buf.getvalue()


# ---------------------------------------------------------------- ISBN
def isbn_digits(isbn: str) -> str:
    return re.sub(r"[^0-9Xx]", "", isbn or "").upper()


def isbn_check(isbn: str) -> tuple[bool, str]:
    d = isbn_digits(isbn)
    if len(d) == 13 and d.isdigit():
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d[:12]))
        ok = (10 - total % 10) % 10 == int(d[12])
        if not ok:
            return False, "검증 숫자(마지막 자리)가 맞지 않습니다. 번호를 다시 확인해 주세요."
        if not d.startswith(("978", "979")):
            return False, "ISBN-13 은 978 또는 979 로 시작해야 합니다."
        return True, "올바른 ISBN-13 입니다."
    if len(d) == 10:
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(d) if c.isdigit() or c == "X")
        return (total % 11 == 0, "올바른 ISBN-10 입니다." if total % 11 == 0 else "ISBN-10 검증 숫자가 맞지 않습니다.")
    return False, "ISBN 은 13자리(또는 옛 10자리) 숫자여야 합니다."


def isbn_format(isbn: str) -> str:
    d = isbn_digits(isbn)
    if len(d) != 13:
        return isbn
    if d.startswith(("97889", "97911")):  # 한국
        return f"{d[:3]}-{d[3:5]}-{d[5:-1]}-{d[-1]}"
    return f"{d[:3]}-{d[3:-1]}-{d[-1]}"


def isbn_barcode(isbn: str) -> bytes:
    import barcode
    from barcode.writer import ImageWriter
    buf = io.BytesIO()
    barcode.get("ean13", isbn_digits(isbn), writer=ImageWriter()).write(
        buf, {"module_height": 16, "font_size": 9, "text_distance": 4, "quiet_zone": 4,
              "font_path": str(FONT_DIR / "NanumGothic.ttf")})
    return buf.getvalue()
