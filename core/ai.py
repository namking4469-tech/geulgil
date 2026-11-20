"""Claude API 래퍼. ANTHROPIC_API_KEY 가 없으면 ai_ready() 가 False 이고, 각 기능은 간이 방식으로 대체된다."""
import base64
import json
import re

import streamlit as st

from .config import secret

DEFAULT_MODEL = "claude-opus-5-5"


def ai_ready() -> bool:
    return bool(secret("ANTHROPIC_API_KEY"))


def model_name() -> str:
    return str(secret("ANTHROPIC_MODEL", DEFAULT_MODEL))


@st.cache_resource(show_spinner=False)
def _client(key: str):
    import anthropic
    return anthropic.Anthropic(api_key=key)


class AIError(Exception):
    pass


def ask(prompt: str, system: str = "", max_tokens: int = 16000, images: list[tuple[bytes, str]] | None = None) -> str:
    """Claude 에게 한 번 묻고 텍스트를 돌려준다. 긴 출력에 대비해 스트리밍으로 받는다."""
    import anthropic
    if not ai_ready():
        raise AIError("ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
    content = []
    for data, mime in images or []:
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime,
                                                    "data": base64.b64encode(data).decode()}})
    content.append({"type": "text", "text": prompt})
    kw = dict(model=model_name(), max_tokens=max_tokens, messages=[{"role": "user", "content": content}],
              # 안전 분류기가 요청을 거절하면 서버가 다른 모델로 자동 재시도한다.
              betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if system:
        kw["system"] = system
    try:
        with _client(str(secret("ANTHROPIC_API_KEY"))).beta.messages.stream(**kw) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise AIError("API 키가 올바르지 않습니다. Secrets 의 ANTHROPIC_API_KEY 를 확인해 주세요.")
    except anthropic.RateLimitError:
        raise AIError("API 사용량 한도에 걸렸습니다. 잠시 후 다시 시도해 주세요.")
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API 오류({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        raise AIError("Claude API 에 연결하지 못했습니다.")
    if msg.stop_reason == "refusal":
        raise AIError("AI 가 이 요청을 처리하지 않았습니다(안전 정책).")
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if msg.stop_reason == "max_tokens":
        text += "\n\n[…출력이 길어 여기서 끊겼습니다]"
    return text


def ask_json(prompt: str, system: str = "", max_tokens: int = 8000) -> dict:
    """JSON 객체 하나만 답하도록 요청하고 파싱한다."""
    text = ask(prompt + "\n\n반드시 JSON 객체 하나만 출력하세요. 설명이나 코드펜스는 쓰지 마세요.",
               system=system, max_tokens=max_tokens)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise AIError("AI 응답에서 JSON 을 찾지 못했습니다.")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise AIError(f"AI 응답 JSON 해석 실패: {e}")
