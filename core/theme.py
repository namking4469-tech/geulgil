"""화면 디자인: 컨셉(5종) × 밝게/어둡게 × 흑백 모드. 사용자별로 저장된다."""
import streamlit as st

from .db import Setting, db

UI_COOKIE = "geulgil_ui"
DEFAULT = {"concept": "aurora", "mode": "light", "mono": False}

# 각 컨셉: 이름, 설명, 모서리 둥글기, 제목 글꼴, 기본 강조색의 색상각(hue), 밝게/어둡게 팔레트
# 팔레트 키: bg 배경, sf 카드, sd 사이드바, inp 입력칸, tx 글자, mu 흐린 글자, bd 테두리, ac 강조1, ac2 강조2, on 강조 위 글자
CONCEPTS = {
    "aurora": {
        "name": "오로라", "desc": "유리 질감과 보랏빛 그라데이션. 가장 현대적인 기본 디자인", "radius": "14px",
        "head": "'Pretendard Variable', Pretendard, sans-serif", "hue": 255,
        "light": dict(bg="#f6f5ff", sf="rgba(255,255,255,.72)", sd="rgba(255,255,255,.62)", inp="rgba(255,255,255,.9)",
                      tx="#1b1836", mu="#6b6889", bd="rgba(99,82,255,.16)", ac="#6352ff", ac2="#19b8e6", on="#ffffff",
                      art="radial-gradient(900px 500px at 8% -5%, rgba(124,92,255,.22), transparent 60%),"
                          "radial-gradient(800px 480px at 100% 0%, rgba(25,184,230,.18), transparent 60%),"
                          "radial-gradient(700px 500px at 60% 110%, rgba(255,120,200,.14), transparent 60%)"),
        "dark": dict(bg="#0c0b1d", sf="rgba(30,27,62,.66)", sd="rgba(18,16,40,.78)", inp="rgba(12,11,29,.7)",
                     tx="#ecebff", mu="#9d9ac4", bd="rgba(150,135,255,.22)", ac="#8f82ff", ac2="#3fd5ff", on="#0c0b1d",
                     art="radial-gradient(900px 520px at 5% -8%, rgba(110,80,255,.38), transparent 60%),"
                         "radial-gradient(800px 500px at 105% 0%, rgba(20,170,230,.26), transparent 60%),"
                         "radial-gradient(700px 520px at 55% 115%, rgba(230,70,170,.18), transparent 60%)"),
    },
    "ink": {
        "name": "잉크", "desc": "종이와 먹. 명조 제목의 차분한 문예지 느낌", "radius": "4px",
        "head": "'Noto Serif KR', 'Nanum Myeongjo', serif", "hue": 215,
        "light": dict(bg="#f7f3ea", sf="#fffdf8", sd="#f0eadc", inp="#fffdf8", tx="#22201c", mu="#7a7468",
                      bd="#ddd3bf", ac="#1f3a5f", ac2="#8a5a2b", on="#fffdf8", art="none"),
        "dark": dict(bg="#151412", sf="#1f1d1a", sd="#1a1816", inp="#141311", tx="#ece6d8", mu="#9c9484",
                     bd="#3a362f", ac="#d9b97a", ac2="#9db7d8", on="#151412", art="none"),
    },
    "neon": {
        "name": "네온", "desc": "선명한 형광빛과 발광 효과. 미래적인 분위기", "radius": "10px",
        "head": "'Pretendard Variable', Pretendard, sans-serif", "hue": 315,
        "light": dict(bg="#fbf7ff", sf="rgba(255,255,255,.82)", sd="rgba(255,255,255,.7)", inp="#ffffff", tx="#17102b",
                      mu="#6f6788", bd="rgba(214,36,180,.2)", ac="#d624b4", ac2="#00b3c7", on="#ffffff",
                      art="linear-gradient(120deg, rgba(214,36,180,.10), transparent 40%),"
                          "linear-gradient(300deg, rgba(0,179,199,.12), transparent 45%)"),
        "dark": dict(bg="#07060f", sf="rgba(22,16,40,.72)", sd="rgba(10,8,22,.86)", inp="rgba(7,6,15,.8)", tx="#f3eaff",
                     mu="#a093c2", bd="rgba(255,60,220,.3)", ac="#ff4fd8", ac2="#22e6ff", on="#07060f",
                     art="linear-gradient(120deg, rgba(255,60,220,.20), transparent 42%),"
                         "linear-gradient(300deg, rgba(34,230,255,.18), transparent 46%)"),
    },
    "forest": {
        "name": "숲", "desc": "초록과 흙빛. 눈이 편안한 자연의 색", "radius": "18px",
        "head": "'Pretendard Variable', Pretendard, sans-serif", "hue": 150,
        "light": dict(bg="#f3f7f1", sf="rgba(255,255,255,.8)", sd="rgba(232,241,229,.85)", inp="#ffffff", tx="#172118",
                      mu="#627064", bd="rgba(34,120,74,.18)", ac="#1f8a55", ac2="#7aa33a", on="#ffffff",
                      art="radial-gradient(900px 520px at 0% 0%, rgba(60,160,100,.16), transparent 60%),"
                          "radial-gradient(800px 500px at 100% 100%, rgba(170,190,80,.14), transparent 60%)"),
        "dark": dict(bg="#0d1410", sf="rgba(24,38,29,.74)", sd="rgba(14,22,17,.86)", inp="rgba(10,16,12,.8)", tx="#e4efe4",
                     mu="#93a896", bd="rgba(90,200,140,.22)", ac="#4fd08e", ac2="#b6d95c", on="#0d1410",
                     art="radial-gradient(900px 520px at 0% 0%, rgba(40,150,90,.26), transparent 60%),"
                         "radial-gradient(800px 500px at 100% 100%, rgba(150,180,60,.14), transparent 60%)"),
    },
    "sunset": {
        "name": "노을", "desc": "산호색과 호박색. 따뜻하고 감성적인 색", "radius": "16px",
        "head": "'Pretendard Variable', Pretendard, sans-serif", "hue": 15,
        "light": dict(bg="#fff7f2", sf="rgba(255,255,255,.8)", sd="rgba(255,240,231,.86)", inp="#ffffff", tx="#2a1712",
                      mu="#84685f", bd="rgba(235,94,60,.18)", ac="#e8553a", ac2="#f2a03d", on="#ffffff",
                      art="radial-gradient(900px 520px at 100% -5%, rgba(255,150,90,.24), transparent 60%),"
                          "radial-gradient(800px 500px at 0% 100%, rgba(240,90,130,.14), transparent 60%)"),
        "dark": dict(bg="#170e0c", sf="rgba(44,26,21,.74)", sd="rgba(26,15,13,.86)", inp="rgba(18,10,9,.8)", tx="#ffece4",
                     mu="#bd9d92", bd="rgba(255,130,90,.24)", ac="#ff7d5c", ac2="#ffc15e", on="#170e0c",
                     art="radial-gradient(900px 520px at 100% -5%, rgba(255,110,60,.28), transparent 60%),"
                         "radial-gradient(800px 500px at 0% 100%, rgba(220,60,110,.18), transparent 60%)"),
    },
}

# 흑백 모드: 어떤 컨셉이든 색을 빼고 흑·백·회색만 쓴다(모서리·글꼴은 컨셉을 따른다)
MONO = {
    "light": dict(bg="#ffffff", sf="#ffffff", sd="#f4f4f4", inp="#ffffff", tx="#0a0a0a", mu="#666666", bd="#d0d0d0",
                  ac="#0a0a0a", ac2="#444444", on="#ffffff", art="none"),
    "dark": dict(bg="#000000", sf="#101010", sd="#0a0a0a", inp="#000000", tx="#f5f5f5", mu="#9a9a9a", bd="#333333",
                 ac="#f5f5f5", ac2="#bbbbbb", on="#000000", art="none"),
}

_FONTS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@500;700&display=swap');
"""

_CSS = """
.stApp { background: var(--g-bg); background-image: var(--g-art); background-attachment: fixed; color: var(--g-tx);
  font-family: 'Pretendard Variable', Pretendard, -apple-system, 'Noto Sans KR', sans-serif; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMainBlockContainer"] { padding-top: 3.2rem; max-width: 1280px; }

/* ── 글자 ── */
.stApp :is(p, li, label, small, summary, td, th, h1, h2, h3, h4, h5, h6),
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"] *,
.stApp [data-testid="stMetricValue"] *, .stApp [data-testid="stExpander"] summary * { color: var(--g-tx); }
.stApp [data-testid="stCaptionContainer"] *, .stApp [data-testid="stMetricLabel"] *,
.stApp small { color: var(--g-mu) !important; }
.stApp :is(h1, h2, h3, h4) { font-family: var(--g-head); letter-spacing: -.02em; }
.stApp h1 { font-weight: 800; font-size: 2.3rem; padding-bottom: .9rem; position: relative; }
.stApp h1::after { content: ""; position: absolute; left: 0; bottom: .2rem; width: 56px; height: 5px;
  border-radius: 99px; background: linear-gradient(90deg, var(--g-ac), var(--g-ac2)); }
.stApp a:not([data-testid]) { color: var(--g-ac); }
.stApp hr { border-color: var(--g-bd) !important; }
.stApp blockquote { border-left: 3px solid var(--g-ac); color: var(--g-tx); }
.stApp code:not(pre code) { background: var(--g-tint); color: var(--g-ac); border-radius: 6px; }

/* ── 사이드바 ── */
[data-testid="stSidebar"] { background: var(--g-sd) !important; border-right: 1px solid var(--g-bd);
  backdrop-filter: blur(22px) saturate(1.3); -webkit-backdrop-filter: blur(22px) saturate(1.3); }
[data-testid="stSidebar"] :is(p, span, label) { color: var(--g-tx); }
[data-testid="stSidebarNavLink"] { border-radius: var(--g-r); margin: 1px 0; transition: all .15s ease; }
[data-testid="stSidebarNavLink"]:hover { background: var(--g-tint) !important; transform: translateX(2px); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--g-tint2) !important;
  box-shadow: inset 3px 0 0 var(--g-ac); }
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: var(--g-ac) !important; font-weight: 700; }
[data-testid="stNavSectionHeader"] *, [data-testid="stSidebarNavSeparator"] { color: var(--g-mu) !important; }

/* ── 카드류 ── */
[data-testid="stExpander"] details, [data-testid="stForm"], [data-testid="stMetric"],
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stFileUploaderDropzone"],
div[data-testid="stVerticalBlock"] > div[style*="border"] {
  background: var(--g-sf) !important; border: 1px solid var(--g-bd) !important; border-radius: var(--g-r) !important;
  box-shadow: var(--g-shadow); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
[data-testid="stMetric"] { padding: 1rem 1.1rem; transition: transform .18s ease, box-shadow .18s ease; }
[data-testid="stMetric"]:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover { transform: translateY(-2px);
  box-shadow: var(--g-shadow2); }
[data-testid="stMetricValue"] { font-family: var(--g-head); font-weight: 800; }
[data-testid="stExpander"] summary:hover * { color: var(--g-ac) !important; }
[data-testid="stFileUploaderDropzone"] { border-style: dashed !important; }
[data-testid="stFileUploaderDropzone"] * { color: var(--g-mu); }

/* ── 버튼 ── */
.stApp :is(button[data-testid^="stBaseButton-secondary"], a[data-testid^="stBaseLinkButton-secondary"],
  button[data-testid="stPopoverButton"], [data-testid="stFileUploaderDropzone"] button) {
  background: var(--g-sf) !important; color: var(--g-tx) !important; border: 1px solid var(--g-bd) !important;
  border-radius: var(--g-r) !important; transition: all .16s ease; }
.stApp :is(button[data-testid^="stBaseButton-secondary"], a[data-testid^="stBaseLinkButton-secondary"],
  button[data-testid="stPopoverButton"]) * { color: inherit !important; }
.stApp :is(button[data-testid^="stBaseButton-secondary"], a[data-testid^="stBaseLinkButton-secondary"],
  button[data-testid="stPopoverButton"]):hover:not(:disabled) { border-color: var(--g-ac) !important;
  color: var(--g-ac) !important; transform: translateY(-1px); box-shadow: var(--g-shadow); }
.stApp :is(button[data-testid^="stBaseButton-primary"], a[data-testid^="stBaseLinkButton-primary"]) {
  background: linear-gradient(135deg, var(--g-ac), var(--g-ac2)) !important; border: 0 !important;
  border-radius: var(--g-r) !important; box-shadow: 0 8px 22px var(--g-glow); font-weight: 700;
  transition: all .16s ease; }
.stApp :is(button[data-testid^="stBaseButton-primary"], a[data-testid^="stBaseLinkButton-primary"]),
.stApp :is(button[data-testid^="stBaseButton-primary"], a[data-testid^="stBaseLinkButton-primary"]) * {
  color: var(--g-on) !important; }
.stApp :is(button[data-testid^="stBaseButton-primary"], a[data-testid^="stBaseLinkButton-primary"]):hover:not(:disabled) {
  transform: translateY(-2px); box-shadow: 0 12px 30px var(--g-glow); filter: brightness(1.06); }
.stApp button:disabled { opacity: .45; }

/* ── 입력칸 ── */
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
  [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
  [data-testid="stNumberInputContainer"], [data-testid="stDateInputField"], [data-testid="stChatInput"] > div) {
  background: var(--g-inp) !important; border-color: var(--g-bd) !important; border-radius: var(--g-r) !important;
  transition: border-color .15s, box-shadow .15s; }
.stApp [data-testid="stDateInputField"] [role="group"] { background: transparent !important; }
.stApp :is(input, textarea, [role="spinbutton"]) { color: var(--g-tx) !important; caret-color: var(--g-ac);
  background: transparent !important; }
.stApp :is([data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stDateInput"],
  [data-testid="stNumberInputContainer"]) :is(svg, button) { color: var(--g-mu) !important; }
.stApp [data-testid="stNumberInputContainer"] button { background: transparent !important; }
.stApp :is(input, textarea)::placeholder { color: var(--g-mu) !important; opacity: .8; }
.stApp :is([data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
  [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
  [data-testid="stNumberInputContainer"], [data-testid="stDateInputField"]):focus-within {
  border-color: var(--g-ac) !important; box-shadow: 0 0 0 3px var(--g-tint2) !important; }
.stApp :is(input, textarea):disabled { -webkit-text-fill-color: var(--g-mu) !important; }

/* 펼침 목록 · 팝오버 (본문 바깥에 그려진다) */
:is([data-rac][data-trigger], [data-testid="stPopoverBody"],
  [data-testid="stTooltipContent"], [data-testid="stDateInputPopover"], [data-testid="stDateInputCalendar"]) {
  background: var(--g-pop) !important; color: var(--g-tx) !important; border-radius: var(--g-r) !important;
  outline: 1px solid var(--g-bd); }
[role="option"], [role="option"] *, [data-testid="stPopoverBody"] :is(p, label, span, h1, h2, h3, h4) {
  color: var(--g-tx) !important; }
[role="option"]:is([data-hovered], [data-focused], [aria-selected="true"]) { background: var(--g-tint2) !important; }

/* ── 탭 ── */
.stApp [role="tablist"] { gap: .25rem; border-bottom-color: var(--g-bd) !important; }
.stApp [data-testid="stTab"] { border-radius: var(--g-r) var(--g-r) 0 0; padding-left: .9rem; padding-right: .9rem;
  transition: background .15s; }
.stApp [data-testid="stTab"] p { color: var(--g-mu) !important; }
.stApp [data-testid="stTab"]:hover { background: var(--g-tint); }
.stApp [data-testid="stTab"][aria-selected="true"] p { color: var(--g-ac) !important; font-weight: 700; }
.stApp [data-testid="stTab"] > div[data-rac] { background: linear-gradient(90deg, var(--g-ac), var(--g-ac2)) !important;
  height: 3px !important; border-radius: 3px; }

/* ── 알림 · 코드 · 표 ── */
[data-testid="stAlertContainer"] { background: var(--g-sf) !important; border: 1px solid var(--g-bd);
  border-left: 4px solid var(--g-ac); border-radius: var(--g-r) !important; backdrop-filter: blur(12px); }
[data-testid="stAlertContainer"] * { color: var(--g-tx) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { border-left-color: var(--g-ok); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { border-left-color: var(--g-warn); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { border-left-color: var(--g-err); }
[data-testid="stCode"] pre, [data-testid="stCode"] { background: var(--g-inp) !important; border-radius: var(--g-r) !important; }
[data-testid="stCode"] pre { border: 1px solid var(--g-bd); }
[data-testid="stCode"] code, [data-testid="stCode"] code * { color: var(--g-tx) !important; }
[data-testid="stDataFrame"], [data-testid="stImage"] img, [data-testid="stVideo"] { border-radius: var(--g-r);
  overflow: hidden; }
[data-testid="stDataFrame"] { border: 1px solid var(--g-bd); box-shadow: var(--g-shadow); }
[data-testid="stImage"] img { box-shadow: var(--g-shadow); }
[data-testid="stToast"] { background: var(--g-pop) !important; border: 1px solid var(--g-bd); border-radius: var(--g-r); }
[data-testid="stToast"] * { color: var(--g-tx) !important; }

/* ── 작은 조작 요소(슬라이더·체크박스·스위치·진행 막대·선택 태그): 기본 보라색을 컨셉 색으로 돌린다 ── */
.stApp :is([data-testid="stSlider"] [data-rac], [data-testid="stCheckbox"] label > div:not([data-testid]),
  [data-testid="stCheckbox"] label > span, [data-testid="stRadio"] label > div:first-child,
  [data-testid="stMultiSelectTagsContainer"] > :not(input)) {
  filter: var(--g-ctl); }
[data-testid="stProgressBarTrack"] { background: var(--g-tint2) !important; border-radius: 99px; overflow: hidden; }
[data-testid="stProgressBarTrack"] > div { background: linear-gradient(90deg, var(--g-ac), var(--g-ac2)) !important;
  border-radius: 99px; }
[data-testid="stMetricDelta"] { background: var(--g-tint2) !important; border-radius: 99px; }
[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * { color: var(--g-ac) !important; }
[data-testid="stCheckbox"] label:has(input[role="switch"]:not(:checked)) > div:not([data-testid]) {
  background: var(--g-mu) !important; opacity: .55; }
/* 구간 선택 버튼(밝게/어둡게 등) */
[data-testid="stButtonGroup"] button[data-variant] { background: var(--g-sf) !important; border-color: var(--g-bd) !important; }
[data-testid="stButtonGroup"] button[data-variant] p { color: var(--g-tx) !important; }
[data-testid="stButtonGroup"] button[data-variant][aria-checked="true"] { background: var(--g-tint2) !important;
  border-color: var(--g-ac) !important; }
[data-testid="stButtonGroup"] button[data-variant][aria-checked="true"] p { color: var(--g-ac) !important; font-weight: 700; }

/* ── 로그인 화면 머리 ── */
.g-hero { padding: 2.2rem 2.4rem; border-radius: calc(var(--g-r) * 1.6); margin-bottom: 1.4rem; position: relative;
  overflow: hidden; background: linear-gradient(135deg, var(--g-ac), var(--g-ac2)); box-shadow: 0 20px 50px var(--g-glow); }
.g-hero::before { content: ""; position: absolute; inset: -40% -10% auto auto; width: 420px; height: 420px;
  border-radius: 50%; background: radial-gradient(circle, rgba(255,255,255,.28), transparent 65%); }
.g-hero h1, .g-hero p, .g-hero span { color: var(--g-on) !important; position: relative; }
.g-hero h1 { font-size: 2.9rem !important; margin: 0; padding: 0 !important; }
.g-hero h1::after { display: none; }
.g-hero p { font-size: 1.08rem; opacity: .92; margin: .5rem 0 1rem; }
.g-chip { display: inline-block; padding: .28rem .8rem; margin: .15rem .3rem .15rem 0; border-radius: 99px;
  font-size: .85rem; font-weight: 600; background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.35);
  backdrop-filter: blur(6px); }
.g-mono .g-chip { background: transparent; border-color: currentColor; }
"""

# 어둡게: 색을 직접 바꿀 수 없는 요소(표 캔버스, 차트, 서식 편집기 틀)는 색을 뒤집어 맞춘다
_DARK_EXTRA = """
[data-testid="stDataFrame"] canvas, [data-testid="stVegaLiteChart"], [data-testid="stCustomComponentV1"],
.stApp iframe[title*="quill"] { filter: invert(.92) hue-rotate(180deg); }
[data-testid="stDataFrame"] { background: #000; }
"""
_MONO_EXTRA = """
[data-testid="stVegaLiteChart"] { filter: grayscale(1); }
.stApp h1::after { background: var(--g-tx); }
"""


def _hex_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def build_css(prefs: dict) -> str:
    concept = CONCEPTS.get(prefs.get("concept"), CONCEPTS["aurora"])
    mode = "dark" if prefs.get("mode") == "dark" else "light"
    mono = bool(prefs.get("mono"))
    p = MONO[mode] if mono else concept[mode]
    r, g, b = _hex_rgb(p["ac"])
    dark = mode == "dark"
    ctl = "grayscale(1) contrast(1.4)" + (" invert(1)" if dark else "") if mono else \
        f"hue-rotate({(concept['hue'] - 248) % 360}deg)"
    pop = {"light": "#ffffff", "dark": "#17162b"}[mode] if not mono else p["sf"]
    if not mono and concept is CONCEPTS["ink"]:
        pop = p["sf"]
    v = {
        "bg": p["bg"], "art": p["art"], "sf": p["sf"], "sd": p["sd"], "inp": p["inp"], "tx": p["tx"], "mu": p["mu"],
        "bd": p["bd"], "ac": p["ac"], "ac2": p["ac2"], "on": p["on"], "pop": pop, "r": concept["radius"],
        "head": concept["head"], "ctl": ctl,
        "tint": f"rgba({r},{g},{b},{.10 if dark else .07})", "tint2": f"rgba({r},{g},{b},{.20 if dark else .13})",
        "glow": "transparent" if mono else f"rgba({r},{g},{b},{.45 if dark else .30})",
        "shadow": "none" if mono else ("0 6px 24px rgba(0,0,0,.35)" if dark else "0 6px 24px rgba(30,20,90,.07)"),
        "shadow2": "none" if mono else ("0 12px 34px rgba(0,0,0,.5)" if dark else "0 14px 34px rgba(30,20,90,.13)"),
        "ok": p["tx"] if mono else "#22c55e", "warn": p["mu"] if mono else "#f59e0b",
        "err": p["tx"] if mono else "#ef4444",
    }
    root = ":root {" + "".join(f"--g-{k}: {val};" for k, val in v.items()) + "}"
    return _FONTS + root + _CSS + (_DARK_EXTRA if dark else "") + (_MONO_EXTRA if mono else "")


# ---------------------------------------------------------------- 설정 읽기·쓰기
def _decode(raw: str | None) -> dict | None:
    try:
        concept, mode, mono = (raw or "").split(".")
        if concept in CONCEPTS and mode in ("light", "dark"):
            return {"concept": concept, "mode": mode, "mono": mono == "1"}
    except ValueError:
        pass
    return None


def current(user=None) -> dict:
    ss = st.session_state
    if "ui" in ss:
        return ss["ui"]
    prefs = None
    if user:
        with db() as s:
            row = s.get(Setting, user.id)
            if row and isinstance(row.data.get("ui"), dict):
                prefs = {**DEFAULT, **row.data["ui"]}
    if not prefs:
        try:
            prefs = _decode(st.context.cookies.get(UI_COOKIE))
        except Exception:
            prefs = None
    ss["ui"] = prefs or dict(DEFAULT)
    return ss["ui"]


def save(prefs: dict, user=None):
    st.session_state["ui"] = prefs
    st.session_state["_ui_cookie"] = f"{prefs['concept']}.{prefs['mode']}.{int(bool(prefs['mono']))}"
    if user:
        with db() as s:
            row = s.get(Setting, user.id)
            if row:
                row.data = {**row.data, "ui": prefs}
            else:
                s.add(Setting(user_id=user.id, data={"ui": prefs}))


def apply(user=None) -> dict:
    """매 실행마다 호출: 현재 설정의 CSS 를 넣는다."""
    prefs = current(user)
    st.html(f"<style>{build_css(prefs)}</style>")
    return prefs


def picker(user=None, key: str = "ui"):
    """디자인 설정 상자(사이드바·로그인 화면 공용)."""
    prefs = current(user)
    with st.popover("🎨 화면 디자인", use_container_width=True):
        ids = list(CONCEPTS)
        concept = st.radio("디자인 컨셉", ids, index=ids.index(prefs["concept"]), key=f"{key}_c",
                           format_func=lambda c: CONCEPTS[c]["name"],
                           captions=[CONCEPTS[c]["desc"] for c in ids])
        mode = st.segmented_control("밝기", ["light", "dark"], default=prefs["mode"], key=f"{key}_m",
                                    format_func={"light": "☀️ 밝게", "dark": "🌙 어둡게"}.get) or prefs["mode"]
        mono = st.toggle("흑백 모드", value=prefs["mono"], key=f"{key}_b",
                         help="색을 빼고 흑·백·회색만 씁니다. 밝게/어둡게와 함께 쓸 수 있습니다.")
        new = {"concept": concept, "mode": mode, "mono": mono}
        if new != prefs:
            save(new, user)
            st.rerun()
