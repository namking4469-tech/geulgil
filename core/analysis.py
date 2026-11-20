"""원고 분석: 분량 통계, 언어 감지, 분량 분류, 장르·주제 분석(Claude 또는 키워드 간이 분석)."""
import math
import re
from collections import Counter

from .ai import AIError, ai_ready, ask_json
from .config import GENRES, LANGS


def detect_lang(text: str) -> str:
    s = text[:5000]
    n = {"ko": len(re.findall(r"[가-힣]", s)), "ja": len(re.findall(r"[ぁ-んァ-ヶ]", s)),
         "zh": len(re.findall(r"[一-鿿]", s)), "ru": len(re.findall(r"[а-яА-Я]", s)),
         "ar": len(re.findall(r"[؀-ۿ]", s)), "hi": len(re.findall(r"[ऀ-ॿ]", s)),
         "lat": len(re.findall(r"[A-Za-z]", s))}
    if n["ja"] > 10 and n["ja"] >= n["ko"]:
        return "ja"
    top = max(n, key=n.get)
    if n[top] == 0:
        return "ko"
    if top != "lat":
        return top
    low = " " + s.lower() + " "
    marks = {"en": (" the ", " and ", " of ", " was "), "es": (" el ", " los ", " que ", " una "),
             "fr": (" le ", " les ", " est ", " une "), "pt": (" não ", " uma ", " que ", " os "),
             "de": (" der ", " und ", " nicht ", " ist ")}
    return max(marks, key=lambda k: sum(low.count(w) for w in marks[k]))


def compute_stats(text: str, lang: str | None = None) -> dict:
    lang = lang or detect_lang(text)
    chars = len(text.replace("\n", ""))
    no_space = len(re.sub(r"\s", "", text))
    words = len(text.split())
    paras = len([p for p in text.split("\n") if p.strip()])
    sents = len(re.findall(r"[.!?。！？…]+(?:\s|$)", text)) or (1 if text.strip() else 0)
    if lang in ("ko", "ja", "zh"):
        minutes = no_space / 500
    else:
        minutes = words / 230
    return {"chars": chars, "chars_no_space": no_space, "words": words, "paragraphs": paras, "sentences": sents,
            "manuscript_pages": math.ceil(chars / 200) if chars else 0,  # 200자 원고지 환산
            "reading_minutes": max(1, round(minutes)) if chars else 0, "lang": lang}


def is_poem(text: str) -> bool:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < 6 or len(text) > 6000:
        return False
    closed = sum(ln[-1] in ".!?。”\"’'" for ln in lines) / len(lines)  # 산문은 대개 문장부호로 끝난다
    return sum(len(ln) for ln in lines) / len(lines) < 28 and closed < 0.6


def length_class(stats: dict, text: str = "") -> str:
    if text and is_poem(text):
        return "시"
    if stats.get("lang") in ("ko", "ja", "zh"):
        p = stats["manuscript_pages"]
        return "엽편(콩트)" if p < 30 else "단편" if p < 200 else "중편" if p < 500 else "장편"
    w = stats["words"]  # 영미권 기준
    return "플래시 픽션" if w < 1500 else "단편" if w < 7500 else "중편" if w < 40000 else "장편"


_KEYWORDS = {
    "로맨스": "사랑 연애 키스 설렘 고백 연인 결혼 첫사랑 이별 love kiss romance",
    "판타지": "마법 용 마왕 검 기사 엘프 왕국 마나 소환 던전 회귀 magic dragon wizard",
    "SF": "우주 로봇 인공지능 행성 외계 미래 우주선 복제 시간여행 robot galaxy spaceship",
    "미스터리/스릴러": "살인 형사 범인 시체 수사 탐정 용의자 단서 추적 사건 murder detective",
    "호러": "귀신 유령 저주 악령 비명 공포 피 ghost haunted",
    "역사": "조선 임금 전하 왕조 장군 궁궐 양반 고려 일제 전쟁",
    "무협": "무림 강호 내공 검법 사부 문파 무공 협객",
    "아동/동화": "옛날 토끼 곰 친구들 마을 숲속 요정 엄마 아빠 동생",
    "수필/에세이": "나는 생각한다 일상 어머니 기억 삶 여행 산책 문득",
    "자기계발": "성공 습관 목표 실천 방법 성장 리더 동기",
}


def heuristic_analysis(text: str) -> dict:
    if is_poem(text):
        genre = "시"
    else:
        scores = {g: sum(text.count(w) for w in kw.split()) for g, kw in _KEYWORDS.items()}
        best = max(scores, key=scores.get)
        genre = best if scores[best] >= max(3, len(text) / 3000) else "순문학"
    words = [w for w in re.findall(r"[가-힣A-Za-z]{2,}", text)]
    stop = set("그리고 그러나 하지만 그는 그녀는 그것 있는 있었다 없는 것이 했다 하는 한다 이런 그런 저런 the and that with was for".split())
    kws = [w for w, _ in Counter(w for w in words if w not in stop).most_common(40) if len(w) >= 2][:10]
    first = next((p.strip() for p in text.split("\n") if len(p.strip()) > 20), text[:200])
    return {"genre": genre, "sub_genres": [], "themes": [], "mood": "", "keywords": kws,
            "summary": first[:200], "logline": "", "audience": "", "engine": "간이 분석(키워드)"}


def _sample(text: str, limit: int = 24000) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    part = limit // 3
    mid = len(text) // 2
    return (text[:part] + "\n\n[…중략…]\n\n" + text[mid - part // 2: mid + part // 2]
            + "\n\n[…중략…]\n\n" + text[-part:]), True


def analyze(text: str, title: str = "") -> dict:
    """장르·주제 등 분석. 긴 원고는 앞·중간·끝을 발췌해 분석한다(결과의 sampled 로 표시)."""
    if not text.strip():
        return {"genre": "기타", "engine": "내용 없음"}
    if not ai_ready():
        return heuristic_analysis(text)
    sample, sampled = _sample(text)
    prompt = f"""다음은 작가가 올린 원고입니다. 문학 편집자의 눈으로 분석해 주세요.

제목: {title or '(없음)'}
<원고>
{sample}
</원고>

다음 키를 가진 JSON 으로 답하세요.
- genre: 다음 중 하나 {GENRES}
- sub_genres: 세부 장르 1~3개(문자열 배열)
- themes: 핵심 주제 2~4개(배열)
- mood: 분위기·문체를 한 문장으로
- keywords: 검색·홍보용 키워드 8~12개(배열)
- summary: 3~4문장 줄거리/내용 요약(결말 누설 없이)
- logline: 한 문장 로그라인
- audience: 주 대상 독자
- strengths: 강점 2~3개(배열)
- suggestions: 다듬으면 좋을 점 2~3개(배열)
값은 모두 원고의 언어와 관계없이 한국어로 쓰세요."""
    try:
        out = ask_json(prompt)
    except AIError as e:
        out = heuristic_analysis(text)
        out["error"] = str(e)
        return out
    if out.get("genre") not in GENRES:
        out["genre"] = "기타"
    out["engine"] = "Claude"
    out["sampled"] = sampled
    return out


def lang_label(code: str) -> str:
    return LANGS.get(code, code)
