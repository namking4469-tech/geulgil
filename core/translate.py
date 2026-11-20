"""자동 번역. Claude(문학 번역) 우선, 키가 없으면 무료 기계번역(deep-translator)으로 대체."""
from .ai import AIError, ai_ready, ask
from .config import LANG_EN

_GT_CODE = {"zh": "zh-CN"}


def split_chunks(text: str, limit: int) -> list[str]:
    """문단 경계를 지키며 limit 글자 이하로 나눈다."""
    chunks, cur = [], ""
    for para in text.split("\n"):
        while len(para) > limit:  # 한 문단이 너무 길면 강제로 자른다
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(para[:limit])
            para = para[limit:]
        if len(cur) + len(para) + 1 > limit and cur:
            chunks.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return chunks


def engine_name() -> str:
    return "Claude" if ai_ready() else "기계번역(Google)"


def _claude(chunk: str, src: str, dst: str, glossary: str, genre: str, prev_tail: str) -> str:
    system = (f"You are an award-winning literary translator from {LANG_EN.get(src, src)} into "
              f"{LANG_EN.get(dst, dst)}. Translate faithfully while preserving voice, rhythm, tone, imagery and "
              f"paragraph breaks. Keep line breaks exactly for poetry. Do not summarize, omit, censor or add "
              f"anything. Output only the translation.")
    prompt = ""
    if genre:
        prompt += f"Genre: {genre}\n"
    if glossary.strip():
        prompt += f"Glossary / fixed renderings (follow strictly):\n{glossary.strip()}\n"
    if prev_tail:
        prompt += f"End of the previous translated section, for continuity only (do not repeat it):\n{prev_tail}\n"
    prompt += f"\nTranslate the text between the tags.\n<text>\n{chunk}\n</text>"
    return ask(prompt, system=system, max_tokens=32000)


def _machine(chunk: str, src: str, dst: str) -> str:
    from deep_translator import GoogleTranslator
    tr = GoogleTranslator(source=_GT_CODE.get(src, src), target=_GT_CODE.get(dst, dst))
    return "\n".join(tr.translate(part) or "" for part in split_chunks(chunk, 4500))


def translate(text: str, src: str, dst: str, glossary: str = "", genre: str = "", progress=None) -> tuple[str, str]:
    """(번역문, 엔진명) 반환. 실패하면 RuntimeError."""
    use_ai = ai_ready()
    chunks = split_chunks(text, 6000 if use_ai else 4500)
    out = []
    for i, ch in enumerate(chunks):
        if progress:
            progress(i / len(chunks))
        if not ch.strip():
            out.append(ch)
            continue
        try:
            out.append(_claude(ch, src, dst, glossary, genre, out[-1][-400:] if out else "") if use_ai
                       else _machine(ch, src, dst))
        except AIError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            raise RuntimeError(f"번역 서버 오류: {type(e).__name__}: {e}")
    if progress:
        progress(1.0)
    return "\n".join(out), engine_name()


def translate_title(title: str, src: str, dst: str) -> str:
    try:
        if ai_ready():
            return ask(f"Translate this book title from {LANG_EN.get(src, src)} into {LANG_EN.get(dst, dst)}. "
                       f"Output only the translated title.\n\n{title}", max_tokens=200).strip().strip('"')
        return _machine(title, src, dst)
    except Exception:
        return title
