"""홍보물 제작: SNS 문구·해시태그, 인용구 카드 이미지, 숏폼/가로 홍보 영상(MP4)."""
import io
import math
import os
import re
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .ai import AIError, ai_ready, ask_json
from .config import LANG_EN, LANGS
from .ebook import COVER_THEMES, font, gradient, wrap

VIDEO_SIZES = {
    "세로 9:16 (릴스 · 틱톡 · 쇼츠)": (720, 1280),
    "가로 16:9 (유튜브)": (1280, 720),
    "정사각 1:1 (피드)": (720, 720),
}
FPS = 24


# ---------------------------------------------------------------- 문구
def pick_quotes(text: str, n: int = 3) -> list[str]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?。！？…])\s+|\n+", text) if 14 <= len(s.strip()) <= 70]
    if not sents:
        return []
    step = max(1, len(sents) // n)
    return [sents[min(len(sents) - 1, i * step + step // 2)] for i in range(n)][:n]


def _fallback_copy(title, author, genre, summary, keywords, quotes) -> dict:
    tags = ["#" + re.sub(r"\s+", "", k) for k in [title, author, genre, *keywords, "신간", "전자책", "책추천", "북스타그램",
                                                   "독서", "책스타그램", "ebook", "booktok", "bookstagram"] if k]
    tags = list(dict.fromkeys(tags))[:25]
    q = quotes[0] if quotes else ""
    base = f"《{title}》 — {author}\n\n{summary}".strip()
    return {
        "one_liners": [f"{author} 작가의 신작 《{title}》 출간!", f"지금, 《{title}》을 만나 보세요."],
        "instagram": f"📖 {base}\n\n“{q}”\n\n전자책으로 만나 보세요. 프로필 링크 확인 ✨",
        "tiktok": f"《{title}》 한 문장 미리보기 👀 “{q}”",
        "youtube_title": f"《{title}》 북트레일러 | {author} {genre}",
        "youtube_description": f"{base}\n\n▶ 전자책 구매: (링크)\n▶ 작가: {author}",
        "x": f"《{title}》 전자책 출간. {summary[:80]}",
        "facebook": f"{base}\n\n전자책으로 출간되었습니다. 많은 관심 부탁드립니다.",
        "blog": f"{base}\n\n책 속 한 문장\n“{q}”",
        "bookstore": summary,
        "press_release": f"[보도자료] {author} 작가, {genre} 《{title}》 전자책 출간\n\n{summary}",
        "hashtags": tags, "hook": f"《{title}》", "quotes": quotes, "engine": "기본 서식(AI 키 없음)",
    }


def make_copy(title: str, author: str, genre: str, summary: str, keywords: list[str], text: str,
              lang: str = "ko") -> dict:
    quotes = pick_quotes(text)
    if not ai_ready():
        return _fallback_copy(title, author, genre, summary, keywords, quotes)
    excerpt = text[:8000]
    prompt = f"""당신은 출판 마케터입니다. 아래 전자책의 SNS 홍보 문구를 {LANGS.get(lang, lang)}({LANG_EN.get(lang, lang)})로 작성하세요.
과장·허위(수상, 판매량, 추천사 등 주어지지 않은 사실)는 절대 지어내지 마세요.

제목: {title}
작가: {author}
장르: {genre}
소개: {summary}
키워드: {', '.join(keywords)}
<본문 발췌>
{excerpt}
</본문 발췌>

다음 키의 JSON 으로 답하세요.
- one_liners: 한 줄 카피 5개(배열)
- instagram: 인스타그램 캡션(줄바꿈·이모지 포함, 해시태그 제외)
- tiktok: 틱톡 캡션(짧고 강한 한두 문장)
- youtube_title: 유튜브 영상 제목(60자 이내)
- youtube_description: 유튜브 설명란(구매 링크 자리는 "(링크)" 로 표시)
- x: X(트위터) 게시글(공백 포함 140자 이내)
- facebook: 페이스북 게시글
- blog: 블로그 소개글(3~4문단)
- bookstore: 온라인 서점 책 소개(2~3문단)
- press_release: 보도자료(제목 한 줄 + 본문)
- hashtags: 해시태그 25개(배열, 각 항목은 # 로 시작, 공백 없음, 널리 쓰이는 태그와 작품 고유 태그를 섞어서)
- hook: 영상 첫 화면에 띄울 12자 안팎의 강한 문구
- quotes: 본문 발췌에서 그대로 가져온 인상적인 문장 3개(배열, 각 60자 이내, 발췌에 없는 문장은 금지)"""
    try:
        out = ask_json(prompt, max_tokens=8000)
    except AIError as e:
        out = _fallback_copy(title, author, genre, summary, keywords, quotes)
        out["error"] = str(e)
        return out
    out.setdefault("quotes", quotes)
    out["hashtags"] = ["#" + re.sub(r"[\s#]+", "", str(t)) for t in out.get("hashtags", []) if str(t).strip("# ")]
    out["engine"] = "Claude"
    return out


# ---------------------------------------------------------------- 이미지 카드
def _fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    r = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * r), math.ceil(img.height * r)))
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _background(size, cover: bytes | None, theme: str, dark: float = 0.55) -> Image.Image:
    if cover:
        bg = _fit_cover(Image.open(io.BytesIO(cover)).convert("RGB"), size).filter(ImageFilter.GaussianBlur(22))
        return Image.blend(bg, Image.new("RGB", size, (0, 0, 0)), dark)
    c1, c2, _ = COVER_THEMES.get(theme, COVER_THEMES["밤하늘"])
    return gradient(size, c1, c2)


def _fg(cover, theme):
    return (255, 255, 255) if cover else COVER_THEMES.get(theme, COVER_THEMES["밤하늘"])[2]


def _draw_block(d, text, fnt, box_w, cx, y, fill, gap=1.45):
    lines = wrap(d, text, fnt, box_w)
    for ln in lines:
        d.text((cx, y), ln, font=fnt, fill=fill, anchor="ma")
        y += int(fnt.size * gap)
    return y


def quote_card(quote: str, title: str, author: str, cover: bytes | None = None, theme: str = "밤하늘",
               size: tuple[int, int] = (1080, 1080)) -> bytes:
    img = _background(size, cover, theme)
    d = ImageDraw.Draw(img)
    w, h = size
    fg = _fg(cover, theme)
    fs = int(w * 0.062)
    while True:
        fq = font(fs, serif=True, text=quote)
        lines = wrap(d, quote, fq, int(w * 0.76))
        if len(lines) * fs * 1.6 < h * 0.5 or fs < 30:
            break
        fs -= 4
    y = int(h / 2 - len(lines) * fs * 1.6 / 2)
    d.text((w / 2, y - fs * 2.0), "“", font=font(int(fs * 2.4), serif=True, bold=True), fill=fg, anchor="ma")
    for ln in lines:
        d.text((w / 2, y), ln, font=fq, fill=fg, anchor="ma")
        y += int(fs * 1.6)
    d.line([w / 2 - 50, h * 0.84, w / 2 + 50, h * 0.84], fill=fg, width=2)
    d.text((w / 2, h * 0.865), f"《{title}》  {author}", font=font(int(w * 0.032), text=title + author), fill=fg, anchor="ma")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def launch_card(title: str, author: str, tagline: str, cover: bytes, badge: str = "전자책 출간",
                size: tuple[int, int] = (1080, 1350)) -> bytes:
    img = _background(size, cover, "밤하늘", 0.6)
    w, h = size
    cv = Image.open(io.BytesIO(cover)).convert("RGB")
    ch = int(h * 0.52)
    cv = cv.resize((int(cv.width * ch / cv.height), ch))
    shadow = Image.new("RGBA", (cv.width + 80, cv.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([40, 40, cv.width + 40, cv.height + 40], fill=(0, 0, 0, 170))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(20)), ((w - shadow.width) // 2, int(h * 0.11) - 25), shadow.filter(ImageFilter.GaussianBlur(20)))
    img.paste(cv, ((w - cv.width) // 2, int(h * 0.11)))
    d = ImageDraw.Draw(img)
    fb = font(int(w * 0.034), bold=True, text=badge)
    bw = d.textlength(badge, font=fb) + 44
    d.rounded_rectangle([w / 2 - bw / 2, h * 0.045, w / 2 + bw / 2, h * 0.045 + fb.size + 22], 30, fill=(255, 255, 255))
    d.text((w / 2, h * 0.045 + 10), badge, font=fb, fill=(20, 20, 30), anchor="ma")
    y = _draw_block(d, title, font(int(w * 0.06), bold=True, serif=True, text=title), int(w * 0.84), w / 2, int(h * 0.67), (255, 255, 255))
    y = _draw_block(d, author, font(int(w * 0.036), text=author), int(w * 0.84), w / 2, y + 6, (230, 230, 230))
    if tagline:
        _draw_block(d, tagline, font(int(w * 0.034), serif=True, text=tagline), int(w * 0.8), w / 2, y + 24, (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- 영상
def _text_layer(size, lines_spec, fg) -> np.ndarray:
    """lines_spec: [(text, font, y비율)] → RGBA 배열"""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = size
    for text, fnt, ypct in lines_spec:
        lines = wrap(d, text, fnt, int(w * 0.82))
        y = int(h * ypct - len(lines) * fnt.size * 1.5 / 2)
        for ln in lines:
            d.text((w / 2 + 2, y + 2), ln, font=fnt, fill=(0, 0, 0, 150), anchor="ma")
            d.text((w / 2, y), ln, font=fnt, fill=(*fg, 255), anchor="ma")
            y += int(fnt.size * 1.5)
    return np.asarray(layer, dtype=np.float32)


def _ease(t):
    return t * t * (3 - 2 * t)


def _ambient_wav(seconds: float, path: str, sr: int = 22050):
    """저작권 걱정 없는 잔잔한 배경음을 직접 합성한다(느린 화음 패드)."""
    t = np.arange(int(seconds * sr)) / sr
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 329.63)]
    seg = 4.0
    out = np.zeros_like(t)
    for i in range(int(math.ceil(seconds / seg))):
        ch = chords[i % len(chords)]
        m = (t >= i * seg - 0.5) & (t < (i + 1) * seg + 0.5)
        local = t[m] - i * seg
        env = np.clip((local + 0.5) / 1.2, 0, 1) * np.clip((seg + 0.5 - local) / 1.2, 0, 1)
        out[m] += sum(np.sin(2 * np.pi * f * t[m]) + 0.4 * np.sin(2 * np.pi * f * 2.002 * t[m]) for f in ch) * env
    out *= np.clip(t / 1.5, 0, 1) * np.clip((seconds - t) / 2.0, 0, 1)
    out = (out / (np.abs(out).max() + 1e-9) * 0.28 * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(out.tobytes())


def make_video(title: str, author: str, hook: str, quotes: list[str], cta: str, cover: bytes | None,
               size: tuple[int, int] = (720, 1280), theme: str = "밤하늘", music: bool = True,
               narration: bytes | None = None, progress=None) -> bytes:
    """표지 → 훅 문구 → 책 속 문장들 → 제목/작가/구매 안내 순서의 홍보 영상(MP4, H.264)."""
    import imageio
    import imageio_ffmpeg
    w, h = size
    fg = _fg(cover, theme)
    big = (int(w * 1.12), int(h * 1.12))
    bg_big = np.asarray(_background(big, cover, theme, 0.62), dtype=np.float32)
    unit = min(w, h * 0.7)

    scenes = []  # (길이초, 종류, 레이어)
    if cover:
        cv = Image.open(io.BytesIO(cover)).convert("RGB")
        chh = int(h * (0.62 if h >= w else 0.78))
        cv = cv.resize((int(cv.width * chh / cv.height), chh))
        card = Image.new("RGBA", size, (0, 0, 0, 0))
        sh = Image.new("RGBA", size, (0, 0, 0, 0))
        x0, y0 = (w - cv.width) // 2, (h - cv.height) // 2
        ImageDraw.Draw(sh).rectangle([x0 + 10, y0 + 16, x0 + cv.width + 10, y0 + cv.height + 16], fill=(0, 0, 0, 190))
        card.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
        card.paste(cv, (x0, y0))
        scenes.append((3.0, "cover", np.asarray(card, dtype=np.float32)))
    if hook:
        scenes.append((2.6, "text", _text_layer(size, [(hook, font(int(unit * 0.105), bold=True, text=hook), 0.5)], fg)))
    for q in quotes[:3]:
        if q.strip():
            scenes.append((max(3.0, min(5.5, len(q) * 0.11)), "text",
                           _text_layer(size, [("“", font(int(unit * 0.16), serif=True, bold=True), 0.27),
                                              (q, font(int(unit * 0.066), serif=True, text=q), 0.5)], fg)))
    scenes.append((3.4, "text", _text_layer(size, [
        (title, font(int(unit * 0.095), bold=True, serif=True, text=title), 0.4),
        (author, font(int(unit * 0.052), text=author), 0.56),
        (cta, font(int(unit * 0.046), bold=True, text=cta), 0.72)], fg)))

    total = sum(s[0] for s in scenes)
    n_total = int(total * FPS)
    tmp = tempfile.mkdtemp()
    silent = os.path.join(tmp, "v.mp4")
    writer = imageio.get_writer(silent, fps=FPS, codec="libx264", quality=7, pixelformat="yuv420p",
                                macro_block_size=8)
    dx, dy = big[0] - w, big[1] - h
    k = 0
    for dur, kind, layer in scenes:
        n = int(dur * FPS)
        for i in range(n):
            g = k / max(1, n_total - 1)
            ox, oy = int(dx * g), int(dy * (1 - g))
            frame = bg_big[oy:oy + h, ox:ox + w].copy()
            t = i / n
            fade = min(1.0, t / 0.18, (1 - t) / 0.14) if kind == "text" else min(1.0, t / 0.25, (1 - t) / 0.12)
            fade = _ease(max(0.0, fade))
            lay = layer
            if kind == "cover":  # 살짝 떠오르는 효과
                shift = int((1 - _ease(min(1, t / 0.4))) * h * 0.03)
                if shift:
                    lay = np.roll(layer, shift, axis=0)
                    lay[:shift] = 0
            a = lay[..., 3:4] / 255.0 * fade
            frame += (lay[..., :3] - frame) * a
            if k < FPS * 0.4:  # 처음엔 검은 화면에서 밝아진다
                frame *= k / (FPS * 0.4)
            writer.append_data(frame.clip(0, 255).astype(np.uint8))
            k += 1
            if progress and k % 12 == 0:
                progress(min(0.95, k / n_total))
    writer.close()

    final = silent
    if music or narration:
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        final = os.path.join(tmp, "out.mp4")
        cmd = [ff, "-y", "-loglevel", "error", "-i", silent]
        filters, maps = [], 0
        if music:
            wav = os.path.join(tmp, "m.wav")
            _ambient_wav(total, wav)
            cmd += ["-i", wav]
            maps += 1
        if narration:
            nar = os.path.join(tmp, "n.mp3")
            with open(nar, "wb") as f:
                f.write(narration)
            cmd += ["-i", nar]
            maps += 1
        if maps == 2:
            filters = ["-filter_complex", "[1:a]volume=0.5[a1];[2:a]adelay=600|600[a2];[a1][a2]amix=inputs=2:duration=first[a]",
                       "-map", "0:v", "-map", "[a]"]
        else:
            filters = ["-map", "0:v", "-map", "1:a"]
        cmd += [*filters, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}", final]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            final = silent  # 소리 합성 실패 시 무음 영상이라도 돌려준다
    with open(final, "rb") as f:
        data = f.read()
    if progress:
        progress(1.0)
    return data


def tts(text: str, lang: str = "ko") -> tuple[bytes | None, str]:
    """낭독 음성(MP3). 인터넷의 Google TTS 를 쓰므로 실패할 수 있다."""
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang={"zh": "zh-CN"}.get(lang, lang)).write_to_fp(buf)
        return buf.getvalue(), ""
    except Exception as e:
        return None, f"음성 합성 실패: {type(e).__name__}: {e}"
