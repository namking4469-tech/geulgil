"""문서 처리: 형식 판별, 텍스트 추출(DOCX·HWP·HWPX·PDF·TXT), 형식 변환, PDF 페이지 편집, OCR."""
import html as htmllib
import io
import re
import struct
import zipfile
import zlib

from .config import FONT_DIR

KIND_LABEL = {"docx": "워드(DOCX)", "hwp": "한글(HWP/HWPX)", "pdf": "PDF", "image": "이미지", "txt": "텍스트"}
EXT_KIND = {"docx": "docx", "hwp": "hwp", "hwpx": "hwp", "pdf": "pdf", "txt": "txt", "md": "txt",
            "jpg": "image", "jpeg": "image", "png": "image", "webp": "image", "gif": "image", "bmp": "image"}
UPLOAD_TYPES = list(EXT_KIND)


def detect_kind(filename: str) -> str | None:
    return EXT_KIND.get(filename.rsplit(".", 1)[-1].lower()) if "." in filename else None


# ---------------------------------------------------------------- 텍스트 ↔ HTML
def text_to_html(text: str) -> str:
    return "".join(f"<p>{htmllib.escape(p) or '<br>'}</p>" for p in text.split("\n"))


def html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    out = []
    blocks = soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote"])
    if not blocks:
        return soup.get_text()
    for el in blocks:
        if el.find_parent(["li", "blockquote"]) and el.name == "p":
            continue
        out.append(el.get_text().strip("\n"))
    return "\n".join(out)


# ---------------------------------------------------------------- 추출
def _decode_txt(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _hwp5_text(data: bytes) -> str:
    """HWP 5.x(OLE) 본문 텍스트 추출. BodyText/Section* 스트림의 PARA_TEXT 레코드를 읽는다."""
    import olefile
    ole = olefile.OleFileIO(io.BytesIO(data))
    header = ole.openstream("FileHeader").read()
    compressed = bool(header[36] & 1)
    if header[36] & 2:
        raise ValueError("암호가 걸린 HWP 문서는 열 수 없습니다.")
    sections = sorted((e for e in ole.listdir() if e[0] == "BodyText"),
                      key=lambda e: int(re.sub(r"\D", "", e[1]) or 0))
    paras = []
    for entry in sections:
        raw = ole.openstream(entry).read()
        if compressed:
            raw = zlib.decompress(raw, -15)
        i = 0
        while i + 4 <= len(raw):
            (h,) = struct.unpack_from("<I", raw, i)
            tag, size = h & 0x3FF, (h >> 20) & 0xFFF
            i += 4
            if size == 0xFFF:
                (size,) = struct.unpack_from("<I", raw, i)
                i += 4
            if tag == 67:  # HWPTAG_PARA_TEXT
                chunk, out, j = raw[i:i + size], [], 0
                while j + 2 <= len(chunk):
                    (c,) = struct.unpack_from("<H", chunk, j)
                    if c in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23) or c in (4, 5, 6, 7, 8, 9, 19, 20):
                        if c == 9:
                            out.append("\t")
                        j += 16  # 확장/인라인 컨트롤: 8 WCHAR
                        continue
                    if c in (10, 13):
                        out.append("\n" if c == 10 else "")
                    elif c >= 32:
                        out.append(chr(c))
                    j += 2
                paras.append("".join(out).encode("utf-16", "surrogatepass").decode("utf-16", "replace"))
            i += size
    return "\n".join(paras)


def _hwpx_text(data: bytes) -> str:
    import xml.etree.ElementTree as ET
    paras = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml", n))
        for n in names:
            root = ET.fromstring(z.read(n))
            for p in root.iter():
                if p.tag.endswith("}p"):
                    paras.append("".join(t.text or "" for t in p.iter() if t.tag.endswith("}t")))
    return "\n".join(paras)


def extract(kind: str, data: bytes, filename: str = "") -> tuple[str, str]:
    """(텍스트, HTML) 을 돌려준다. 실패하면 ValueError."""
    try:
        if kind == "docx":
            import mammoth
            html = mammoth.convert_to_html(io.BytesIO(data)).value
            html = re.sub(r'<img[^>]*>', "", html)  # 내장 이미지는 편집기에서 제외
            return html_to_text(html), html
        if kind == "hwp":
            text = _hwpx_text(data) if data[:2] == b"PK" else _hwp5_text(data)
            return text, text_to_html(text)
        if kind == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("암호가 걸린 PDF 는 열 수 없습니다.")
            text = "\n\n".join((p.extract_text() or "").strip() for p in reader.pages)
            return text, text_to_html(text)
        if kind == "txt":
            text = _decode_txt(data)
            return text, text_to_html(text)
        return "", ""
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"파일을 읽지 못했습니다({type(e).__name__}: {e}). 파일이 손상되었거나 지원하지 않는 형식일 수 있습니다.")


# ---------------------------------------------------------------- 내보내기
def html_to_docx(html: str, title: str = "") -> bytes:
    """편집기 HTML(제목·문단·굵게·기울임·밑줄·목록·정렬)을 DOCX 로 변환."""
    from bs4 import BeautifulSoup, NavigableString
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    doc = Document()
    st_ = doc.styles["Normal"]
    st_.font.name = "맑은 고딕"
    st_.element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
    if title:
        doc.core_properties.title = title
    align = {"ql-align-center": WD_ALIGN_PARAGRAPH.CENTER, "ql-align-right": WD_ALIGN_PARAGRAPH.RIGHT,
             "ql-align-justify": WD_ALIGN_PARAGRAPH.JUSTIFY}

    def runs(par, node, b=False, i=False, u=False, s=False):
        for ch in node.children:
            if isinstance(ch, NavigableString):
                if str(ch):
                    r = par.add_run(str(ch))
                    r.bold, r.italic, r.underline, r.font.strike = b or None, i or None, u or None, s or None
            elif ch.name == "br":
                par.add_run().add_break()
            else:
                runs(par, ch, b or ch.name in ("strong", "b"), i or ch.name in ("em", "i"),
                     u or ch.name == "u", s or ch.name in ("s", "strike", "del"))

    soup = BeautifulSoup(html or "", "html.parser")
    for el in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote"]):
        if el.name == "p" and el.find_parent(["li", "blockquote"]):
            continue
        if el.name[0] == "h":
            par = doc.add_heading(level=int(el.name[1]))
        elif el.name == "li":
            par = doc.add_paragraph(style="List Number" if el.find_parent("ol") else "List Bullet")
        elif el.name == "blockquote":
            par = doc.add_paragraph(style="Intense Quote")
        else:
            par = doc.add_paragraph()
        for cls in el.get("class", []):
            if cls in align:
                par.alignment = align[cls]
        runs(par, el)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def text_to_docx(text: str, title: str = "") -> bytes:
    return html_to_docx((f"<h1>{htmllib.escape(title)}</h1>" if title else "") + text_to_html(text), title)


def register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for name, file in (("Nanum", "NanumGothic.ttf"), ("NanumB", "NanumGothicBold.ttf"),
                       ("Myeongjo", "NanumMyeongjo.ttf"), ("MyeongjoB", "NanumMyeongjoBold.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))


def text_to_pdf(text: str, title: str = "") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    register_fonts()
    body = ParagraphStyle("b", fontName="Myeongjo", fontSize=11, leading=19, wordWrap="CJK", firstLineIndent=11)
    head = ParagraphStyle("h", fontName="NanumB", fontSize=18, leading=26, spaceAfter=14)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm, topMargin=25 * mm,
                            bottomMargin=25 * mm, title=title)
    flow = [Paragraph(htmllib.escape(title), head)] if title else []
    for line in text.split("\n"):
        flow.append(Paragraph(htmllib.escape(line), body) if line.strip() else Spacer(1, 10))
    doc.build(flow)
    return buf.getvalue()


# ---------------------------------------------------------------- PDF 페이지 편집
def pdf_page_count(data: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(data)).pages)


def pdf_page_image(data: bytes, index: int, scale: float = 1.0):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    try:
        return pdf[index].render(scale=scale).to_pil()
    finally:
        pdf.close()


def pdf_rebuild(data: bytes, pages: list[tuple[int, int]]) -> bytes:
    """pages: [(원본 페이지 번호(0부터), 회전각)] 순서대로 새 PDF 를 만든다(순서 변경·삭제·회전)."""
    from pypdf import PdfReader, PdfWriter
    reader, writer = PdfReader(io.BytesIO(data)), PdfWriter()
    for idx, rot in pages:
        page = writer.add_page(reader.pages[idx])
        if rot:
            page.rotate(rot)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def pdf_merge(files: list[bytes]) -> bytes:
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for f in files:
        for page in PdfReader(io.BytesIO(f)).pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def pdf_stamp(data: bytes, text: str, pages: list[int], x_pct: float, y_pct: float, size: int,
              color: str = "#000000", opacity: float = 1.0, angle: int = 0) -> bytes:
    """지정한 페이지 위에 글자(주석·워터마크·쪽번호 등)를 얹는다. 좌표는 페이지 왼쪽 위 기준 %."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    register_fonts()
    reader, writer = PdfReader(io.BytesIO(data)), PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in pages:
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            c.setFont("Nanum", size)
            c.setFillColor(HexColor(color), alpha=opacity)
            c.saveState()
            c.translate(w * x_pct / 100, h * (1 - y_pct / 100))
            c.rotate(angle)
            for n, line in enumerate(text.replace("{n}", str(i + 1)).split("\n")):
                c.drawString(0, -n * size * 1.4, line)
            c.restoreState()
            c.save()
            page.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ---------------------------------------------------------------- OCR
def ocr_image(data: bytes, mime: str = "image/png") -> tuple[str, str]:
    """이미지 속 글자를 읽는다. (텍스트, 오류) 반환. Claude 비전 → Tesseract 순으로 시도."""
    from .ai import AIError, ai_ready, ask
    if ai_ready():
        try:
            return ask("이 이미지에 보이는 글자를 줄바꿈을 살려 그대로 옮겨 적어 주세요. "
                       "글자 외의 설명은 덧붙이지 마세요. 글자가 없으면 빈 문자열만 답하세요.",
                       images=[(data, mime)], max_tokens=8000), ""
        except AIError as e:
            return "", str(e)
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang="kor+eng"), ""
    except Exception as e:
        return "", f"OCR 을 쓰려면 ANTHROPIC_API_KEY 또는 Tesseract 가 필요합니다. ({type(e).__name__})"
