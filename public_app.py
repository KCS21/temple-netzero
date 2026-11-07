# -*- coding: utf-8 -*-
"""
불교탄소중립실천단 지수광풍 — 공개 홈페이지 (작업지시 10)

실행:  streamlit run public_app.py

**컨설턴트 앱(`app.py`)과 다른 앱입니다.** 사찰·종무소가 직접 씁니다.
쪽 넷 — 소개 · 자가진단 · 결과 · 컨설팅 요청.

계산은 컨설턴트 앱과 같은 모듈(`juso`·`bldengy`·`emissions`·`region`·`keys`)을
그대로 부릅니다. 두 앱이 같은 절에 다른 숫자를 내면 안 됩니다.

보여 주지 않는 것 — 원단위 배수, 면적당 값, 연면적, 지번 묶기, 엑셀 산정서.
면적 자료가 틀리기 쉬워 사찰이 오해할 수 있습니다.

**개인정보는 컨설팅 요청 양식에서만** 받고 구글 시트로 보내는 것 말고는
어디에도 남기지 않습니다. 화면·로그·파일에 찍지 마십시오.
"""
import datetime as dt
import io
import os
import threading

import streamlit as st
import streamlit.components.v1 as components

import bldengy
import bldrgst
import keys
import region
import search_ui
from public import content, report_pdf, selfcheck as sc, sheet

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))
NL = chr(10)

PAGES = ("소개", "자가진단", "결과", "컨설팅 요청")
QUERY_LIMIT = 5          # 한 세션의 자료 조회 횟수 (공공데이터포털 키를 컨설턴트 앱과 함께 씀)
BUSY_TEXT = "자료 서버가 바쁩니다. 잠시 뒤 다시 시도해 주세요."
LIMIT_TEXT = "조회를 여러 번 하셨습니다. 잠시 뒤 다시 시도해 주세요."

DARK, GREEN, PALE = "#1E5631", "#2F6B3F", "#E4F0E6"
MIST, GOLD = "#F4F9F5", "#F2C14E"     # 아주 옅은 바탕 · 숫자 강조에만 조금

st.set_page_config(page_title=content.SITE_TITLE, layout="centered",
                   initial_sidebar_state="collapsed")

# 색은 여기서만 입힙니다. `.streamlit/config.toml` 은 컨설턴트 앱과 함께 쓰므로
# 건드리지 않습니다(작업지시 10 0장 5번).
st.markdown(f"""
<style>
  html, body, .stApp, [class*="css"], .stMarkdown, p, li, label, input, textarea, button {{
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }}
  .stApp {{ background: #ffffff; color: #222; }}
  .stMarkdown p, .stMarkdown li {{ font-size: 18px; line-height: 1.75; }}
  h1, h2, h3, h4 {{ color: {DARK} !important; }}
  .stMarkdown h2 {{ font-size: 24px; margin-top: 1.4rem; padding-bottom: 0.3rem;
      border-bottom: 2px solid {PALE}; }}
  [data-testid="stHeader"] {{ background: transparent; }}
  .block-container {{ padding-top: 1.2rem; max-width: 980px; }}

  .jisu-head {{ background: {DARK}; color: #fff; border-radius: 12px;
      padding: 18px 20px 14px; margin-bottom: 10px; }}
  .jisu-head .t {{ font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
  .jisu-head .s {{ font-size: 16px; opacity: 0.9; margin-top: 2px; }}

  /* 쪽 이동 — 탭 모양. 휴대폰에서도 한 줄에 넷이 들어가게 */
  .st-key-nav {{ border-bottom: 3px solid {DARK}; margin-bottom: 14px; }}
  .st-key-nav [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important;
      gap: 4px !important; }}
  .st-key-nav [data-testid="stColumn"], .st-key-nav [data-testid="column"] {{
      min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
  .st-key-nav button {{ width: 100%; border-radius: 10px 10px 0 0 !important;
      border: none !important; padding: 0.55rem 0.2rem !important;
      background: {PALE} !important; color: {DARK} !important; }}
  .st-key-nav button[kind^="primary"] {{ background: {DARK} !important;
      color: #fff !important; }}
  .st-key-nav .stButton button p {{ font-size: 17px !important; white-space: nowrap; }}
  .st-key-nav [data-testid="stColumn"]:last-child {{ flex-grow: 1.4 !important; }}
  @media (max-width: 480px) {{
      .st-key-nav .stButton button p {{ font-size: 15px !important;
          letter-spacing: -0.5px; }} }}

  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
      font-size: 19px; font-weight: 700; padding: 0.65rem 1.4rem;
      border-radius: 10px; border: 2px solid {GREEN}; color: {DARK}; }}
  .stButton button p, .stDownloadButton button p, .stFormSubmitButton button p {{
      font-size: 19px !important; font-weight: 700; }}
  button[kind^="primary"] {{ background: {GREEN} !important; color: #fff !important;
      border-color: {GREEN} !important; }}
  button[kind^="primary"]:hover {{ background: {DARK} !important; }}
  button[kind^="secondary"]:hover, .stDownloadButton > button:hover {{
      border-color: {DARK} !important; color: {DARK} !important; background: {PALE}; }}
  /* 고른 동그라미·네모도 녹색으로 (테마 파일은 컨설턴트 앱과 함께 써서 못 바꿈) */
  [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child:not([data-testid]) {{
      background-color: {GREEN} !important; border-color: {GREEN} !important; }}
  div[role="radiogroup"] label:has(input:checked) > div:first-child {{
      background-color: {GREEN} !important; border-color: {GREEN} !important; }}
  [data-testid="stCheckbox"] label[data-selected="true"] > div:has(> svg) {{
      background-color: {GREEN} !important; border-color: {GREEN} !important; }}
  .stTextInput div[data-baseweb="input"]:focus-within,
  .stNumberInput div[data-baseweb="input"]:focus-within,
  .stTextArea div[data-baseweb="textarea"]:focus-within {{ border-color: {GREEN} !important; }}
  .stTextInput input, .stNumberInput input, .stTextArea textarea {{ font-size: 19px; }}
  label p, .stCheckbox p, div[role="radiogroup"] label p {{ font-size: 18px !important; }}

  .jisu-box {{ background: {PALE}; border-radius: 12px; padding: 14px 16px;
      margin: 6px 0 12px; }}
  .jisu-num {{ background: {PALE}; border-radius: 12px; padding: 14px 10px;
      text-align: center; margin-bottom: 8px; }}
  .jisu-num .l {{ color: {GREEN}; font-size: 16px; }}
  .jisu-num .v {{ color: {DARK}; font-size: 30px; font-weight: 800; }}
  .jisu-kind {{ font-size: 24px; font-weight: 800; color: {DARK}; }}
  .jisu-code {{ color: #888; font-size: 14px; margin-top: -0.4rem; }}
  .jisu-small {{ color: #555; font-size: 16px; }}
  .jisu-foot {{ margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #ddd;
      color: #555; font-size: 16px; }}

  /* ── 소개 화면 ── */
  .st-key-hero {{ background: {DARK}; border-radius: 16px; padding: 28px 24px 22px;
      margin-bottom: 18px; }}
  .st-key-hero .stMarkdown p, .st-key-hero h1 {{ color: #fff !important; }}
  .jisu-hero-t {{ font-size: 30px; font-weight: 800; line-height: 1.4;
      letter-spacing: -0.5px; color: #fff; margin: 4px 0 10px; }}
  .jisu-hero-s {{ font-size: 18px; color: #DDEBDF; line-height: 1.7; }}
  .st-key-hero button[kind^="secondary"] {{ background: #fff !important;
      color: {DARK} !important; border-color: #fff !important; }}
  .st-key-hero button[kind^="primary"] {{ background: {GOLD} !important;
      color: #1b1b1b !important; border-color: {GOLD} !important; }}
  .st-key-hero img {{ border-radius: 12px; }}
  .jisu-cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 18px; }}
  .jisu-card {{ flex: 1 1 200px; background: #fff; border: 1.5px solid {PALE};
      border-radius: 14px; padding: 16px 16px 14px;
      box-shadow: 0 1px 4px rgba(30, 86, 49, 0.07); }}
  .jisu-card .n {{ font-size: 34px; font-weight: 800; color: {GREEN}; line-height: 1; }}
  .jisu-card .t {{ font-size: 20px; font-weight: 800; color: {DARK}; margin: 6px 0 4px; }}
  .jisu-card .d {{ font-size: 17px; color: #333; line-height: 1.65; }}
  .jisu-stat {{ flex: 1 1 180px; background: {MIST}; border: 1.5px solid {PALE};
      border-radius: 14px; padding: 16px; text-align: center; }}
  .jisu-stat .v {{ font-size: 28px; font-weight: 800; color: {DARK}; }}
  .jisu-stat .v b {{ border-bottom: 4px solid {GOLD}; }}
  .jisu-stat .l {{ font-size: 16px; color: {GREEN}; margin-top: 2px; }}
  .st-key-band {{ background: {MIST}; border-radius: 16px; padding: 18px 18px 6px;
      margin: 10px 0 14px; }}
  .st-key-band img, .st-key-row1 img, .st-key-row2 img {{ border-radius: 12px; }}

  /* 접수 뒤 단추 둘 - 휴대폰에서도 나란히 */
  .st-key-done_btns [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; }}
  .st-key-done_btns [data-testid="stColumn"] {{ min-width: 0 !important; }}

  /* 자동 입력 막기용 칸. 사람에게는 보이지 않습니다 */
  .st-key-hp {{ position: absolute !important; left: -10000px !important;
      width: 1px !important; height: 1px !important; overflow: hidden !important; }}
</style>""", unsafe_allow_html=True)


# ── 판 표시 (CLAUDE.md 7장 — 올렸는데 옛 코드인 일을 바로 알아보려고) ──
def _kst(ts: float):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(KST)


def running_version() -> str:
    """`git` 을 부르지 않고 `.git` 을 직접 읽습니다. 시각은 한국 시각."""
    try:
        git = os.path.join(HERE, ".git")
        if os.path.isfile(git):          # 작업 폴더(worktree)면 진짜 위치를 따라갑니다
            git = io.open(git, encoding="utf-8").read().split(":", 1)[1].strip()
        head = io.open(os.path.join(git, "HEAD"), encoding="utf-8").read().strip()
        sha = head
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            common = os.path.join(git, "commondir")
            if not os.path.exists(os.path.join(git, ref)) and os.path.exists(common):
                git = os.path.join(git, io.open(common, encoding="utf-8").read().strip())
            sha = io.open(os.path.join(git, ref), encoding="utf-8").read().strip()
        when = _kst(os.path.getmtime(os.path.join(HERE, "public_app.py")))
        return f"{sha[:7]} · {when:%Y-%m-%d %H:%M}"
    except Exception:
        try:
            return f"{_kst(os.path.getmtime(os.path.join(HERE, 'public_app.py'))):%Y-%m-%d %H:%M}"
        except Exception:
            return ""


VERSION = running_version()


# ── 키 — 없으면 주소 찾기만 숨기고 고지서 입력은 그대로 ──
def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


try:
    CONFM_KEY, SERVICE_KEY = keys.load()
except Exception:
    CONFM_KEY, SERVICE_KEY = "", ""
LOOKUP_ON = bool(CONFM_KEY and SERVICE_KEY)
KAKAO_KEY = search_ui.kakao_key() if LOOKUP_ON else ""
SHEET_URL, SHEET_TOKEN = _secret("APPS_SCRIPT_URL"), _secret("APPS_SCRIPT_TOKEN")

BODY, SETTINGS = content.load()
CONTACT = content.contact_line(SETTINGS)

for k, v in [("nav", PAGES[0]), ("picked", None),
             ("result", None), ("queries", 0),
             ("diag_sent", None), ("pdf", None), ("pdf_sig", None),
             ("look_err", ""), ("no_data", ""), ("req_sent", 0),
             ("req_done", None),
             ("req_msg", None), ("mode", "find")]:
    st.session_state.setdefault(k, v)


def go(page: str, **extra):
    st.session_state.nav = page
    st.session_state.update(extra)


# ── 머리 · 쪽 이동 ──
st.markdown(f'<div class="jisu-head"><div class="t">{content.SITE_TITLE}</div>'
            '<div class="s">사찰 탄소중립 자가진단 · 무료 컨설팅</div></div>',
            unsafe_allow_html=True)
if st.session_state.get("goto"):
    st.session_state.nav = st.session_state.pop("goto")
with st.container(key="nav"):
    # 라디오는 빨간 점이 남아 홈페이지처럼 보이지 않았습니다(작업지시 11 ③).
    # 고른 쪽만 primary 로 그려 짙은 녹색 탭이 됩니다.
    for col, name in zip(st.columns(len(PAGES)), PAGES):
        col.button(name, key=f"tab_{name}", width="stretch",
                   type="primary" if st.session_state.nav == name else "secondary",
                   on_click=go, args=(name,))


# ═══════════ ① 소개 ═══════════
def _two_buttons(key: str):
    c1, c2 = st.columns(2)
    c1.button("우리 절 자가진단", key=f"{key}_check", type="primary",
              width="stretch", on_click=go, args=("자가진단",))
    c2.button("무료 컨설팅 요청", key=f"{key}_req", width="stretch",
              on_click=go, args=("컨설팅 요청",))


def _cards(items, numbered: bool = False) -> str:
    out = []
    for i, (t, d) in enumerate(items, 1):
        n = f'<div class="n">{i}</div>' if numbered else ""
        out.append(f'<div class="jisu-card">{n}<div class="t">{t}</div>'
                   f'<div class="d">{d}</div></div>')
    return '<div class="jisu-cards">' + "".join(out) + "</div>"


def _text_and_image(key: str, title: str, text: str, image: str,
                    image_left: bool = False):
    """글 + 그림 좌우. 휴대폰에서는 그림이 아래로 갑니다."""
    if not title:
        return
    with st.container(key=key):
        st.markdown(f"## {title}")
        if not image:
            st.markdown(text)
            return
        if image_left:
            c_img, c_txt = st.columns([2, 3], vertical_alignment="center")
        else:
            c_txt, c_img = st.columns([3, 2], vertical_alignment="center")
        c_txt.markdown(text)
        c_img.image(image, width="stretch")


# 소개글의 「지수광풍이 하는 일」을 세 칸으로. 문장은 소개글 그대로에서 땄습니다.
WORK_CARDS = (
    ("진단", "사찰과 불교계 기관을 찾아가 에너지 사용과 온실가스 배출을 진단합니다."),
    ("로드맵", "에너지 절약·그린리모델링·재생에너지로 가는 탄소중립 로드맵을 함께 세웁니다."),
    ("실행 지원", "실행한 뒤에도 꾸준히 살피고 돕습니다. 공사로 이익을 남기지 않고 "
                  "사찰의 입장에서 자문합니다."),
)
# 법문사 옥상 태양광 (소개글 「먼저 해 본 곳」)
STATS = (("42", "kW", "법문사 옥상 태양광"),
         ("48,313", "kWh", "한 해 생산"),
         ("22.18", "톤", "온실가스 감축"))


def _practice():
    """법문사 사례 — 컨설팅 요청 쪽 맨 위에 둡니다."""
    _b, secs = content.sections(BODY)
    title, done = content.find(secs, "먼저 해 본")
    st.markdown(f"## {title or '먼저 해 본 곳'}")
    st.markdown('<div class="jisu-cards">' + "".join(
        f'<div class="jisu-stat"><div class="v"><b>{v}</b> {u}</div>'
        f'<div class="l">{l}</div></div>' for v, u, l in STATS) + "</div>",
        unsafe_allow_html=True)
    if done:
        st.markdown(f'<p class="jisu-small">{done}</p>', unsafe_allow_html=True)


def page_intro():
    lead, secs = content.sections(BODY)
    tagline = lead.strip("* ").strip() or content.SITE_TITLE
    who_t, who = content.find(secs, "우리는")

    # 1. 히어로
    with st.container(key="hero"):
        c_txt, c_img = st.columns([3, 2], vertical_alignment="center")
        with c_txt:
            st.markdown(f'<div class="jisu-hero-t">{tagline}</div>'
                        '<div class="jisu-hero-s">불교에너지전문가들이 사찰을 찾아가 '
                        "에너지를 진단하고 탄소중립 로드맵을 함께 세웁니다. "
                        "사찰 컨설팅은 무료입니다.</div>", unsafe_allow_html=True)
        hero = content.img("temple_solar.png")
        if hero:
            c_img.image(hero, width="stretch")

    # 3. 우리는 / 하는 일
    if who:
        st.markdown(f"## {who_t}")
        st.markdown(who)
    work_t, work = content.find(secs, "하는 일")
    if work_t:
        st.markdown(f"## {work_t}")
        st.markdown(_cards(WORK_CARDS), unsafe_allow_html=True)
        st.markdown(work)

    # 4·5. 오래된 가르침 · 사찰의 현실
    t, x = content.find(secs, "가르침")
    _text_and_image("row1", t, x, content.img("cycle.png"))
    t, x = content.find(secs, "현실")
    _text_and_image("row2", t, x, content.img("meter_fuel.png"), image_left=True)

    # 6. 순서가 중요합니다
    t, x = content.find(secs, "순서")
    items = content.steps(x)
    if t and items:
        with st.container(key="band"):
            st.markdown(f"## {t}")
            st.markdown(_cards(items, numbered=True), unsafe_allow_html=True)
    elif t:
        st.markdown(f"## {t}")
        st.markdown(x)

    # 7. 단장 인사말 (설정 칸이 비면 숨김)
    g = content.greeting(SETTINGS)
    if g:
        title, text, photo = g
        st.markdown(f"## {title}")
        if photo:
            c1, c2 = st.columns([1, 2])
            c1.image(photo, width="stretch")
            c2.markdown(text)
        else:
            st.markdown(text)

    # 8. 함께하는 곳 · 시작하기
    with_t, with_x = content.find(secs, "함께")
    start_t, start_x = content.find(secs, "시작")
    lotus = content.img("lotus.png")
    if start_t or with_t:
        st.markdown(f"## {start_t or with_t}")
        c_img, c_txt = st.columns([1, 3], vertical_alignment="center")
        if lotus:
            c_img.image(lotus, width="stretch")
        with c_txt:
            if start_x:
                st.markdown(start_x)
            if with_x:
                st.markdown(f"**{with_t}** · {with_x}")
        _two_buttons("end")

    # md 에 새 칸을 더하면 여기서 그대로 보입니다(빠뜨리지 않도록)
    shown = ("우리는", "하는 일", "가르침", "현실", "순서", "먼저 해 본", "함께", "시작")
    for title, text in secs.items():
        if not any(k in title for k in shown):
            st.markdown(f"## {title}")
            st.markdown(text)


# ═══════════ ② 자가진단 ═══════════
@st.cache_data(ttl=86400, show_spinner=False)
def _purposes(sgg, bjd, bun, ji, plat):
    """그 지번 건물들의 주용도. 하루 동안 다시 씁니다."""
    dongs = bldrgst.fetch_dongs(sgg, bjd, bun, ji, SERVICE_KEY, plat)
    return [d.mainPurpsCdNm for d in dongs]


def _odd_place(j) -> bool:
    """절이 아닐 수 있는 주소인가. 조회가 안 되면 조용히 넘어갑니다."""
    p = j.building_params()
    try:
        ps = _purposes(p["sigunguCd"], p["bjdongCd"], p["bun"], p["ji"], p["platGbCd"])
    except Exception:
        return False
    return sc.not_temple(ps)


def _old_sgg(sgg: str) -> str:
    """컨설턴트 앱과 같은 까닭으로 감쌉니다 — 옛 모듈이 남아도 조회는 돕니다."""
    try:
        return region.old_sigungu(sgg)
    except Exception:
        return ""


def _place(addr: str) -> str:
    try:
        return region.place_token(addr)
    except Exception:
        return ""


@st.cache_data(ttl=86400, show_spinner=False)
def _year_data(sgg, bjd, bun, ji, plat, year, old_sgg, place):
    """같은 지번·같은 해는 24시간 다시 쓰기. 공공데이터포털 하루 한도를 지킵니다."""
    d = bldengy.fetch_year(sgg, bjd, bun, ji, year, SERVICE_KEY, plat_gb=plat,
                           old_sigungu=old_sgg, place_must=place,
                           timeout=10, retries=1)
    return {"elec": dict(d["elec"]), "gas": dict(d["gas"])}


def _months(series: dict) -> int:
    return sum(1 for v in series.values() if v and v > 0)


def _lookup(j):
    """지난해 하나. 12달이 안 되면 한 해 전으로 한 번 더 (작업지시 10 ②)."""
    p = j.building_params()
    args = (p["sigunguCd"], p["bjdongCd"], p["bun"], p["ji"], p["platGbCd"])
    extra = (_old_sgg(p["sigunguCd"]), _place(j.jibunAddr))
    year = dt.datetime.now(KST).year - 1
    data = _year_data(*args, year, *extra)
    if _months(data["elec"]) < 12:
        prev = _year_data(*args, year - 1, *extra)
        if _months(prev["elec"]) > _months(data["elec"]):
            data, year = prev, year - 1
    return data, year


def _heat_and_fuel():
    st.markdown("#### 난방은 무엇으로 하시나요? (여러 개 고르셔도 됩니다)")
    heat = [h for h in sc.HEAT_OPTIONS if st.checkbox(h, key=f"heat_{h}")]
    st.markdown("#### 연료 양 (모르시면 비워 두세요)")
    st.markdown('<p class="jisu-small">지난 1년 동안 쓴 양입니다.</p>',
                unsafe_allow_html=True)
    drums = st.number_input("등유 — 드럼 수 (1드럼 = 200 L)", min_value=0.0,
                            step=1.0, value=None, key="kero")
    c1, c2 = st.columns(2)
    small = c1.number_input("LPG 20kg 통 — 교체 횟수", min_value=0, step=1,
                            value=None, key="lpg20")
    big = c2.number_input("LPG 50kg 통 — 교체 횟수", min_value=0, step=1,
                          value=None, key="lpg50")
    st.markdown('<p class="jisu-small">화목(장작)은 양을 받지 않습니다. '
                "위에서 「화목」을 고르시면 사용하신다고 적어 둡니다.</p>",
                unsafe_allow_html=True)
    return heat, drums, small, big


def _show_result(r):
    # 쪽 이동 단추가 이미 그려진 뒤라 nav 를 바로 못 바꿉니다. 다음 그리기에서 옮깁니다.
    st.session_state.update(result=r, pdf=None, pdf_sig=None, goto="결과")


def page_check():
    st.markdown("## 우리 절 자가진단")
    modes = {"find": "주소나 절 이름으로 찾기", "bill": "고지서 숫자로 직접 넣기"}
    if not LOOKUP_ON:
        st.session_state.mode = "bill"
    else:
        st.radio("진단 방법", list(modes), format_func=modes.get, key="mode",
                 horizontal=True)

    if st.session_state.mode == "find":
        _find_block()
    else:
        _bill_block()


def _clear_after_pick():
    """고른 주소가 바뀌면 그 주소에 딸린 안내를 비웁니다."""
    st.session_state.update(look_err="", no_data="")


def _find_block():
    # 찾기 칸은 컨설턴트 앱과 **같은 것**을 씁니다(search_ui.py).
    search_ui.Finder(CONFM_KEY, KAKAO_KEY, on_pick=_clear_after_pick,
                     css="jisu-small",
                     other_way="위의 **「고지서 숫자로 직접 넣기」**"
                     ).show("#### 1. 주소 또는 절 이름으로 찾기")

    j = st.session_state.picked
    if j is None:
        return
    st.markdown("---")
    st.markdown(f"**고른 주소:** {j.jibunAddr}")
    if _odd_place(j):
        st.warning(sc.NOT_TEMPLE_TEXT)
    search_ui.name_warning(j)
    name = st.text_input("절 이름 (결과지에 찍힙니다)", value=j.bdNm or "",
                         key=f"name_{j.jibunAddr}")

    st.markdown("---")
    heat, drums, small, big = _heat_and_fuel()
    st.markdown('<p class="jisu-small">전기·가스 자료를 가져오는 데 30초쯤 걸립니다.</p>',
                unsafe_allow_html=True)
    if st.button("결과 보기", type="primary", width="stretch", key="go_find"):
        if st.session_state.queries >= QUERY_LIMIT:
            st.session_state.look_err = LIMIT_TEXT
        else:
            st.session_state.queries += 1
            try:
                with st.spinner("전기·가스 자료를 가져오고 있습니다. 30초쯤 걸립니다."):
                    data, year = _lookup(j)
            except Exception:
                # 503 과 「자료 없음」을 섞지 않습니다. 자료 없음은 아래에서 따로 말합니다.
                st.session_state.look_err = BUSY_TEXT
            else:
                elec, gas = sum(data["elec"].values()), sum(data["gas"].values())
                if elec <= 0 and gas <= 0:
                    st.session_state.no_data = (
                        f"이 주소에는 {year}년 공개된 전기·가스 자료가 없습니다. "
                        "전기가 다른 지번으로 잡혀 있을 수 있습니다.")
                else:
                    _show_result(sc.diagnose(
                        name.strip() or j.bdNm or j.jibunAddr, j.jibunAddr, year,
                        sc.MODE_LOOKUP, elec, gas, heat, drums, small, big,
                        monthly=data["elec"]))
                    st.rerun()
    if st.session_state.look_err:
        st.warning(st.session_state.look_err)
    if st.session_state.no_data:
        st.warning(st.session_state.no_data)
        st.button("고지서 숫자로 직접 넣기", width="stretch",
                  on_click=lambda: st.session_state.update(
                      mode="bill", bill_name=name.strip() or j.bdNm or "",
                      bill_addr=j.jibunAddr, no_data=""))


def _bill_block():
    st.markdown("#### 1. 고지서 숫자 넣기")
    if not LOOKUP_ON:
        st.info("지금은 주소 찾기를 쓸 수 없어 고지서 숫자로 진단합니다.")
    name = st.text_input("절 이름", key="bill_name")
    addr = st.text_input("주소", key="bill_addr", placeholder="예: 경기도 고양시 …")
    elec = st.number_input("지난 1년 전기 사용량 (kWh)", min_value=0.0, step=100.0,
                           value=None, key="bill_elec")
    monthly = {}
    with st.expander("월별로 넣기 (선택) — 12달을 다 넣으시면 난방 유형을 더 잘 봅니다"):
        cols = st.columns(3)
        for m in range(1, 13):
            v = cols[(m - 1) % 3].number_input(f"{m}월 (kWh)", min_value=0.0,
                                               step=10.0, value=None, key=f"m{m}")
            if v:
                monthly[f"{m:02d}"] = v
    gas = st.number_input("도시가스 사용량 (kWh, 선택)", min_value=0.0, step=100.0,
                          value=None, key="bill_gas")

    st.markdown("---")
    heat, drums, small, big = _heat_and_fuel()
    if st.button("결과 보기", type="primary", width="stretch", key="go_bill"):
        total = elec or sum(monthly.values())
        if not total:
            st.warning("지난 1년 전기 사용량을 넣어 주세요. 월별로 넣으셔도 됩니다.")
            return
        series = ({f"{m:02d}": monthly.get(f"{m:02d}", 0.0) for m in range(1, 13)}
                  if monthly else None)
        _show_result(sc.diagnose(name.strip() or "우리 절", addr.strip(), None,
                                 sc.MODE_BILL, total, gas or 0, heat, drums,
                                 small, big, monthly=series))
        st.rerun()


# ═══════════ ③ 결과 ═══════════
def _send_diag_once(r):
    """결과를 보여 줄 때 한 번. 같은 세션·같은 결과는 다시 보내지 않습니다."""
    data = sc.diag_payload(r, VERSION)
    sig = tuple(sorted((k, str(v)) for k, v in data.items()))
    if st.session_state.diag_sent == sig:
        return
    st.session_state.diag_sent = sig
    # 뒤에서 보냅니다. Apps Script 가 늦게 깨면 10초까지 걸려 결과가 그만큼 늦게
    # 뜹니다. 실패해도 사찰 화면은 그대로입니다.
    threading.Thread(target=sheet.post, daemon=True,
                     args=(SHEET_URL, SHEET_TOKEN, sheet.KIND_DIAG, data)).start()


def _solar_month_chart(r) -> None:
    """태양광 월 발전과 우리 절 월별 전기를 나란히.

    숫자 하나(연간 필요용량)만 보면 **여름에 남고 겨울에 모자라는** 사정이
    안 보입니다. 겨울 난방 전기는 태양광만으로 채우기 어려워 난방 전환을
    먼저 권하게 되는 까닭입니다(작업지시 14 ⑤).
    """
    if not r.solar_kw or not r.solar_month:
        return
    import altair as alt
    import pandas as pd

    months = [f"{m}월" for m in range(1, 13)]
    rows = [{"달": months[i], "구분": "태양광 발전(예상)", "kWh": r.solar_month[i]}
            for i in range(12)]
    use = []
    if r.monthly:
        # 조회는 「202501」, 고지서 입력은 「01」 — 둘 다 읽습니다.
        # `str(k)[4:]` 로 떼면 고지서 쪽이 빈 글자가 되어 결과 화면이 죽었습니다.
        by = {sc._month_of(k): float(v or 0) for k, v in r.monthly.items()}
        if len(by) == 12 and all(by.get(m) for m in range(1, 13)):
            use = [by[m] for m in range(1, 13)]
            rows += [{"달": months[i], "구분": "우리 절 전기", "kWh": use[i]}
                     for i in range(12)]
    st.markdown(f'<p class="jisu-small">{sc.solar.legend(r.solar_kw)}</p>',
                unsafe_allow_html=True)
    df = pd.DataFrame(rows)
    # 달 이름은 **가로로** 둡니다(labelAngle=0). 세로로 서면 읽기 어렵습니다.
    base = alt.Chart(df).encode(
        x=alt.X("달:N", sort=months, title=None,
                axis=alt.Axis(labelAngle=0)))
    line = base.transform_filter(
        alt.datum.구분 == "태양광 발전(예상)").mark_line(
        point=alt.OverlayMarkDef(color=sc.solar.LINE_COLOR),
        color=sc.solar.LINE_COLOR).encode(
        y=alt.Y("kWh:Q", title="kWh"), tooltip=["달", "구분", "kWh"])
    chart = line
    if use:
        bars = base.transform_filter(
            alt.datum.구분 == "우리 절 전기").mark_bar(
            color=sc.solar.BAR_COLOR).encode(
            y="kWh:Q", tooltip=["달", "구분", "kWh"])
        chart = bars + line
    st.altair_chart(chart.properties(height=sc.solar.CHART_HEIGHT), width="stretch")
    # 그림 바로 아래 해설 — 두 앱이 같은 문장(solar.explain)
    for line in sc.solar.explain(
            r.solar_kw, r.solar_place, r.solar_nation,
            r.year if r.mode == sc.MODE_LOOKUP else None, has_bars=bool(use)):
        st.markdown('<p class="jisu-small">'
                    + line.replace("**", "<b>", 1).replace("**", "</b>", 1)
                    + "</p>", unsafe_allow_html=True)

    if use:
        st.markdown(
            '<p class="jisu-small">여름에는 남고 겨울에는 모자랍니다. '
            "겨울 난방 전기는 태양광만으로 채우기 어려워, <b>난방 전환을 "
            "먼저</b> 권합니다. "
            + sc.solar.winter_text(r.solar_month, use)
            + "</p>", unsafe_allow_html=True)
    else:
        st.markdown('<p class="jisu-small">태양광은 겨울에 여름의 절반 정도만 '
                    "만듭니다.</p>", unsafe_allow_html=True)


def page_result():
    r = st.session_state.result
    if r is None:
        st.markdown("## 결과")
        st.info("아직 진단한 결과가 없습니다. 먼저 자가진단을 해 주세요.")
        st.button("자가진단 하러 가기", type="primary", width="stretch",
                  on_click=go, args=("자가진단",))
        return
    _send_diag_once(r)

    st.markdown(f"## {r.name}")
    where = f"{r.year}년 공개 자료" if r.mode == sc.MODE_LOOKUP else "입력하신 고지서 값"
    st.markdown(f'<p class="jisu-small">{r.addr or "주소 미입력"} · {where}</p>',
                unsafe_allow_html=True)

    cols = st.columns(3)
    for c, (lbl, val) in zip(cols, (("연간 배출량", f"{r.total_t:,.1f} t"),
                                     ("국민 환산", f"{r.people:,.1f}명분"),
                                     ("태양광 필요용량", f"{r.solar_kw:,.1f} kW"))):
        c.markdown(f'<div class="jisu-num"><div class="l">{lbl}</div>'
                   f'<div class="v">{val}</div></div>', unsafe_allow_html=True)
    parts = [f"전기 {r.elec_kwh:,.0f} kWh", f"도시가스 {r.gas_kwh:,.0f} kWh"]
    if r.kero_l:
        parts.append(f"등유 {r.kero_l:,.0f} L")
    if r.lpg_kg:
        parts.append(f"LPG {r.lpg_kg:,.0f} kg")
    st.markdown(f'<p class="jisu-small">{" · ".join(parts)}<br>'
                f"전기는 정부 공표 전력배출계수(소비단, 2023년 "
                f"{sc.em.ELEC_EF[sc.em.ELEC_DEFAULT]})로 계산했습니다. "
                f"국민 환산은 1인당 연 {r.per_capita_t} t"
                f"({r.per_capita_year}년 기준)입니다.</p>",
                unsafe_allow_html=True)

    # 태양광 — 어느 지역 값으로 셈했는지 밝히고 바로 아래 월별 그림.
    # **다른 칸은 움직이지 않습니다**(작업지시 14 ⑤).
    st.markdown(
        f'<p class="jisu-small">{sc.solar.label(r.solar_place)}'
        + (f" {sc.solar.NO_PLACE}" if r.solar_nation else "")
        + f" {sc.solar.CAVEAT}</p>", unsafe_allow_html=True)
    # 감축 한 줄. **공사비·보조금은 공개 앱에 내지 않습니다.**
    st.markdown(f'<p class="jisu-small">'
                + sc.solar.cut_text(r.total_t, r.elec_t).replace("**", "")
                + "</p>", unsafe_allow_html=True)

    st.markdown("## 우리 절 유형")
    ratio = sc.ratio_text(r.ratio)
    st.markdown(f'<div class="jisu-box"><div class="jisu-kind">{r.kind}</div>'
                + (f'<div class="jisu-small">{ratio}</div>' if ratio else "")
                + "</div>", unsafe_allow_html=True)

    st.markdown("## 먼저 해 볼 일")
    st.markdown(NL.join(f"{i}. {t}" for i, t in enumerate(r.todo, 1)))

    # 월별 전기와 태양광 발전을 **한 그림**에 둡니다(2026-11-03).
    # 전에는 태양광 칸 아래에 같은 막대가 한 번 더 나왔습니다.
    if (r.monthly and any(r.monthly.values())) or r.solar_kw:
        st.markdown("## 월별 전기 사용량과 태양광 발전 (kWh)")
        _solar_month_chart(r)

    st.markdown("## 지원사업")
    st.markdown(sc.SUPPORT_TEXT)
    st.markdown("## 이 진단의 한계")
    st.markdown(NL.join(f"- {t}" for t in r.notes))

    sig = id(r)
    if st.session_state.pdf_sig != sig:
        try:
            st.session_state.pdf = report_pdf.build(r, CONTACT)
        except Exception:
            st.session_state.pdf = None
        st.session_state.pdf_sig = sig
    c1, c2 = st.columns(2)
    if st.session_state.pdf:
        c1.download_button("인쇄용 PDF 내려받기", st.session_state.pdf,
                           file_name=report_pdf.file_name(r.name),
                           mime="application/pdf", width="stretch")
    else:
        c1.warning("PDF 를 만들지 못했습니다. 이 화면을 그대로 인쇄해 주세요.")
    c2.button("컨설팅 요청하기", type="primary", width="stretch",
              on_click=go, args=("컨설팅 요청",),
              kwargs={"req_name": r.name, "req_addr": r.addr})


# ═══════════ ④ 컨설팅 요청 ═══════════
def _md_plain(text: str) -> str:
    """접수 문구에 넣을 값. 이메일의 `_` 등이 글자 꾸밈으로 읽혀 빠지지 않게."""
    return "".join("\\" + c if c in "\\`*_~[]" else c for c in str(text or ""))


def _reset_request() -> None:
    """요청 양식만 처음으로. **진단 결과(`result`)는 건드리지 않습니다.**"""
    for k in ("req_name", "req_addr", "req_person", "req_contact",
              "req_text", "req_hp", "req_agree"):
        st.session_state.pop(k, None)
    st.session_state.req_msg = None
    st.session_state.req_done = None


def _to_home() -> None:
    _reset_request()
    go("소개", scroll_top=True)


def _request_done() -> None:
    """보낸 뒤 화면 — 보내기 단추가 있던 자리에 접수 메시지만."""
    done = st.session_state.get("req_done") or {}
    who = (done.get("name") or "").strip()
    whom = " · ".join(_md_plain(x) for x in (who, done.get("contact")) if x)
    st.success("요청이 접수되었습니다."
               + (f"  {whom} 로 지수광풍이 연락드리겠습니다."
                  if whom else "  지수광풍이 연락드리겠습니다.")
               + NL + NL + "연락처가 틀렸다면 「새 요청 쓰기」로 다시 보내 주세요.")
    # 화면을 이 자리로 내려 줍니다. 위에 그대로 두면 긴 폼에 가려
    # 접수됐는지 모르고 한 번 더 누르게 됩니다.
    st.markdown('<div id="jisu-done"></div>'
                '<script>document.getElementById("jisu-done")'
                '?.scrollIntoView({behavior:"smooth",block:"center"});</script>',
                unsafe_allow_html=True)
    with st.container(key="done_btns"):
        c1, c2 = st.columns(2)
        c1.button("새 요청 쓰기", key="req_new", width="stretch",
                  on_click=_reset_request)
        c2.button("처음으로", key="req_home", width="stretch", on_click=_to_home)


def page_request():
    _practice()
    st.markdown("## 컨설팅 요청")
    st.markdown("지수광풍은 사찰을 대상으로 **무료 컨설팅**을 하고 있습니다. "
                "아래를 적어 보내 주시면 연락드립니다.")
    # 보낸 뒤에는 **입력 칸을 잠그고 보내기 단추를 감춥니다.** 전에는 내용이
    # 그대로 살아 있어 한 번 더 누르면 **같은 요청이 두 번** 들어갔습니다.
    # 칸을 비우지 않고 잠그는 것은, 무엇을 보냈는지 보이게 하려는 것입니다.
    sent = st.session_state.req_msg == "sent"

    name = st.text_input("절 이름 (필수)", key="req_name", disabled=sent)
    addr = st.text_input("주소 (필수)", key="req_addr", disabled=sent)
    person = st.text_input("담당자 이름 (필수)", key="req_person", disabled=sent)
    contact = st.text_input("연락처 (필수) — 전화 또는 이메일", key="req_contact",
                            placeholder="예: 010-1234-5678", disabled=sent)
    text = st.text_area(f"요청 내용 ({sheet.REQ_MAX_TEXT:,}자 이내)", key="req_text",
                        max_chars=sheet.REQ_MAX_TEXT, height=140, disabled=sent)
    with st.container(key="hp"):
        hp = st.text_input("홈페이지", key="req_hp", label_visibility="collapsed",
                           autocomplete="off", disabled=sent)

    r = st.session_state.result
    summary = r.summary() if r is not None else ""
    if summary:
        st.markdown(f'<p class="jisu-small">자가진단 결과가 함께 갑니다: {summary}</p>',
                    unsafe_allow_html=True)

    st.markdown(f"**{sheet.CONSENT_TITLE}**" + NL + NL
                + NL.join(f"- {t}" for t in sheet.CONSENT_LINES))
    agree = st.checkbox(sheet.CONSENT_CHECK, key="req_agree", disabled=sent)

    # 보냈으면 **보내기 단추가 있던 자리**에 접수 메시지를 띄웁니다.
    if sent:
        _request_done()
        return

    used = st.session_state.req_sent >= sheet.SEND_LIMIT
    if used:
        st.info("이 화면에서는 더 보낼 수 없습니다. 지수광풍이 곧 연락드리겠습니다.")
    if st.button("보내기", type="primary", width="stretch",
                 disabled=not agree or used):
        form = {"절 이름": name, "주소": addr, "담당자 이름": person,
                "연락처": contact, "요청 내용": text, "동의": agree,
                "자가진단 요약": summary}
        errs = sheet.check_request(form)
        if errs:
            st.warning(NL.join(f"- {e}" for e in errs))
            return
        with st.spinner("보내는 중입니다. 20초까지 걸릴 수 있습니다."):
            status, code = sheet.send_request_detail(form, hp, SHEET_URL, SHEET_TOKEN)
        # 'off' (보낼 곳이 설정 안 됨)도 실패로 알립니다. 접수됐다고 하면 요청이 사라집니다.
        if status in ("sent", "blocked"):
            # 자동 입력은 성공처럼 보여 줍니다. 막혔다는 것을 알려 줄 까닭이 없습니다.
            st.session_state.req_sent += 1
            st.session_state.req_msg = "sent"
            # 접수 문구에 쓸 것만 남깁니다. 연락처는 **전체**를 보여 줍니다 -
            # 잘못 적었으면 알아보고 다시 보내게 하려는 것입니다.
            st.session_state.req_done = {"name": name,
                                         "contact": sheet.show_contact(contact)}
            st.rerun()
        # 실패하면 입력한 내용은 지우지 않습니다(위젯이 그대로 들고 있습니다).
        st.session_state.req_msg = None
        st.error(sheet.FAIL_TEXT)
        # 원인을 가릴 짧은 코드만. 이름·연락처는 어디에도 찍지 않습니다.
        st.markdown(f'<p class="jisu-code">(오류 코드: {code or status})</p>',
                    unsafe_allow_html=True)


def _check_block():
    """관리자 점검 — 주소 뒤에 `?check=1` 을 붙여 열 때만 보입니다(작업지시 11 ①)."""
    try:
        on = str(st.query_params.get("check", "")).strip() == "1"
    except Exception:
        on = False
    if not on:
        return
    st.markdown("---")
    st.markdown("#### 시트 연결 점검")
    st.markdown('<p class="jisu-small">개인정보 없이 점검 신호(ping)만 보냅니다.</p>',
                unsafe_allow_html=True)
    if st.button("시트 연결 점검", key="ping_go"):
        with st.spinner("점검 중입니다. 20초까지 걸릴 수 있습니다."):
            st.session_state.ping = sheet.ping(SHEET_URL, SHEET_TOKEN)
    res = st.session_state.get("ping")
    if res:
        (st.success if res["code"] in ("ok", "kind") else st.warning)(
            f"{res['verdict']} · 코드 {res['code']} · {res['seconds']}초")


def _scroll_top() -> None:
    """「처음으로」 뒤 맨 위로. 쪽을 바꿔도 스크롤은 그대로 남기 때문입니다.

    `st.markdown` 의 `<script>` 는 돌지 않아 iframe 에서 바깥 화면을 올립니다.
    못 올려도 쪽은 이미 옮겨졌으니 **어떤 오류든 삼킵니다.**
    """
    if not st.session_state.pop("scroll_top", False):
        return
    try:
        components.html(
            "<script>const d=window.parent.document;const up=()=>{"
            "for(const q of ['[data-testid=\"stMain\"]','section.main',"
            "'[data-testid=\"stAppViewContainer\"]']){const e=d.querySelector(q);"
            "if(e)e.scrollTop=0;}window.parent.scrollTo(0,0);};"
            "up();setTimeout(up,300);setTimeout(up,1000);</script>", height=0)
    except Exception:
        pass


{"소개": page_intro, "자가진단": page_check, "결과": page_result,
 "컨설팅 요청": page_request}[st.session_state.nav]()
_check_block()

# ── 바닥 ──
foot = [content.SITE_TITLE]
if CONTACT:
    foot.append(CONTACT)
st.markdown(f'<div class="jisu-foot">{"<br>".join(foot)}'
            + (f'<br><span style="font-size:13px;color:#999">판 {VERSION}</span>'
               if VERSION else "")
            + "</div>", unsafe_allow_html=True)
_scroll_top()
