"""설정·비밀값 읽기. Streamlit Secrets → 환경변수 → 기본값 순서로 찾는다."""
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
DATA_DIR = ROOT / "data"
APP_NAME = "글길"
APP_TAGLINE = "작가를 위한 올인원 플랫폼"

DEV_SECRET = "dev-only-secret-change-me"


def secret(key: str, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


def app_secret() -> str:
    return str(secret("APP_SECRET", DEV_SECRET))


def using_dev_secret() -> bool:
    return app_secret() == DEV_SECRET


def base_url() -> str:
    """OAuth 리디렉션·패스키에 쓰는 앱 주소."""
    url = secret("APP_BASE_URL")
    if url:
        return str(url).rstrip("/")
    try:
        host = st.context.headers.get("host", "localhost:8501")
    except Exception:
        host = "localhost:8501"
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    return f"{scheme}://{host}"


# 작가 유형
WRITER_TYPES = [
    "소설가", "시인", "수필가", "극작가", "시나리오 작가", "아동문학가", "웹소설 작가",
    "평론가", "논픽션 작가", "번역가", "동화작가", "방송작가", "기타",
]

# 번역 대상 언어 (사용 인구 상위 대표 언어)
LANGS = {
    "ko": "한국어", "en": "영어", "zh": "중국어(간체)", "es": "스페인어", "hi": "힌디어",
    "ar": "아랍어", "fr": "프랑스어", "pt": "포르투갈어", "ja": "일본어", "ru": "러시아어",
    "de": "독일어",
}
LANG_EN = {
    "ko": "Korean", "en": "English", "zh": "Simplified Chinese", "es": "Spanish", "hi": "Hindi",
    "ar": "Arabic", "fr": "French", "pt": "Portuguese", "ja": "Japanese", "ru": "Russian",
    "de": "German",
}
RTL_LANGS = {"ar"}

GENRES = [
    "순문학", "로맨스", "판타지", "SF", "미스터리/스릴러", "호러", "역사", "무협", "청소년",
    "아동/동화", "시", "수필/에세이", "희곡/시나리오", "논픽션", "자기계발", "평론", "기타",
]
