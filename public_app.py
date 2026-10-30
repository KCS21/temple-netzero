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

import bldengy
import bldrgst
import juso
import kakao
import keys
import portal
import region
from public import content, report_pdf, selfcheck as sc, sheet

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))
NL = chr(10)

QUERY_LIMIT = 5          # 한 세션의 자료 조회 횟수 (공공데이터포털 키를 컨설턴트 앱과 함께 씀)
PER_PAGE = 5
BUSY_TEXT = "자료 서버가 바쁩니다. 잠시 뒤 다시 시도해 주세요."
LIMIT_TEXT = "조회를 여러 번 하셨습니다. 잠시 뒤 다시 시도해 주세요."

# 작업지시 12 — 차분한 미색 바탕, 얇은 선, 각진 모서리. 짙은 녹색 하나가 주인공.
BG, CARD, LINE = "#F7F4EE", "#FCFAF6", "#DDD5C6"
INK, SUB = "#1B1B1B", "#6B6B6B"
DARK, GREEN, GOLD = "#1E4D2B", "#2F6B3F", "#B8893B"
FOOT = "#EFEAE0"

st.set_page_config(page_title=content.SITE_TITLE, layout="wide",
                   initial_sidebar_state="collapsed")

# 색은 여기서만 입힙니다. `.streamlit/config.toml` 은 컨설턴트 앱과 함께 쓰므로
# 건드리지 않습니다(작업지시 10 0장 5번).
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=Nanum+Brush+Script&display=swap');
  html, body, .stApp, [class*="css"], .stMarkdown, p, li, label, input, textarea, button {{
      font-family: "Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif; }}
  .stApp {{ background: {BG}; color: {INK}; }}
  .stMarkdown p, .stMarkdown li {{ font-size: 17.5px; line-height: 1.7; color: {INK}; }}
  h1, h2, h3, h4 {{ color: {INK} !important; letter-spacing: -0.02em; }}
  .stMarkdown h4 {{ font-size: 20px; font-weight: 700; margin-top: 0.6rem; }}

  /* Streamlit 틀 감추기 */
  header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
  [data-testid="stDecoration"], .stDeployButton, [data-testid="stAppDeployButton"] {{
      display: none !important; }}
  .block-container {{ max-width: 1120px; padding: 0 24px 0 !important; margin: 0 auto; }}
  @media (max-width: 640px) {{ .block-container {{ padding: 0 16px !important; }} }}

  /* ── 머리 ── */
  .st-key-topbar {{ border-bottom: 1px solid {LINE}; padding: 18px 0 12px;
      margin-bottom: 8px; }}
  .jisu-logo {{ font-size: 18px; font-weight: 500; color: {INK}; letter-spacing: -0.02em;
      white-space: nowrap; }}
  .jisu-logo b {{ color: {DARK}; font-weight: 900; }}
  .jisu-slogan {{ font-family: "Nanum Brush Script", cursive; font-size: 30px;
      color: {DARK}; text-align: center; line-height: 1; }}
  .st-key-menu {{ flex-direction: row !important; flex-wrap: wrap; align-items: center;
      justify-content: flex-end; gap: 4px 20px !important; }}
  .st-key-menu > div {{ width: auto !important; }}
  .st-key-menu a {{ padding: 4px 0 !important; border-radius: 0 !important;
      background: transparent !important; }}
  .st-key-menu a p {{ font-size: 15px !important; color: {SUB} !important; }}
  .st-key-menu [class*="st-key-m_"][class*="_on"] a {{ border-bottom: 2px solid {GREEN}; }}
  .st-key-menu [class*="st-key-m_"][class*="_on"] a p {{ color: {GREEN} !important;
      font-weight: 700 !important; }}
  .st-key-m_cta a {{ border: 1px solid {DARK} !important; border-radius: 2px !important;
      padding: 4px 12px !important; }}
  .st-key-m_cta a p {{ color: {DARK} !important; font-weight: 700 !important; }}
  @media (max-width: 640px) {{
      .jisu-slogan {{ display: none; }}
      .st-key-menu {{ justify-content: flex-start; gap: 4px 14px !important; }}
  }}

  /* ── 단추 · 입력 칸 ── */
  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
      border-radius: 2px !important; border: 1px solid {DARK} !important;
      background: {CARD} !important; color: {DARK} !important;
      padding: 0.6rem 1.2rem; box-shadow: none !important; }}
  .stButton button p, .stDownloadButton button p, .stFormSubmitButton button p {{
      font-size: 15px !important; font-weight: 700 !important; }}
  button[kind^="primary"] {{ background: {DARK} !important; color: #fff !important;
      border-color: {DARK} !important; }}
  button[kind^="primary"] p {{ color: #fff !important; }}
  button[kind^="primary"]:hover {{ background: {GREEN} !important; }}
  button[kind^="secondary"]:hover, .stDownloadButton > button:hover {{
      background: {FOOT} !important; }}
  .stTextInput div[data-baseweb="input"], .stNumberInput div[data-baseweb="input"],
  .stTextArea div[data-baseweb="textarea"] {{ background: #fff !important;
      border: 1px solid {LINE} !important; border-radius: 2px !important; }}
  .stTextInput input, .stNumberInput input, .stTextArea textarea,
  [data-baseweb="base-input"] {{ background: #fff !important; font-size: 17px; }}
  .stTextInput div[data-baseweb="input"]:focus-within,
  .stNumberInput div[data-baseweb="input"]:focus-within,
  .stTextArea div[data-baseweb="textarea"]:focus-within {{ border-color: {GREEN} !important; }}
  label p, .stCheckbox p, div[role="radiogroup"] label p {{ font-size: 17px !important; }}
  /* 라디오·체크 상자에 빨간색이 남지 않게 (테마 파일은 컨설턴트 앱과 함께 씀) */
  [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child:not([data-testid]),
  div[role="radiogroup"] label:has(input:checked) > div:first-child {{
      background-color: {GREEN} !important; border-color: {GREEN} !important; }}
  [data-testid="stCheckbox"] label[data-selected="true"] > div:has(> svg),
  [data-testid="stCheckbox"] label:has(input:checked) > span:first-of-type {{
      background-color: {GREEN} !important; border-color: {GREEN} !important; }}
  [data-testid="stExpander"] details {{ border: 1px solid {LINE} !important;
      border-radius: 2px !important; background: {CARD}; }}

  /* ── 칸 머리 ── */
  .jisu-kicker {{ color: {GOLD}; font-size: 13px; font-weight: 700;
      letter-spacing: 0.18em; text-transform: uppercase; margin: 80px 0 6px; }}
  .jisu-kicker.first {{ margin-top: 48px; }}
  .jisu-h {{ font-size: 30px; font-weight: 900; letter-spacing: -0.02em;
      color: {INK}; line-height: 1.35; margin: 0 0 18px; }}
  .jisu-small {{ color: {SUB}; font-size: 15.5px; line-height: 1.7; }}
  .jisu-code {{ color: #888; font-size: 14px; margin-top: -0.4rem; }}

  /* ── 첫 화면 ── */
  .jisu-hero-k {{ text-align: center; margin-top: 56px; }}
  .jisu-hero-t {{ text-align: center; font-size: 40px; font-weight: 900;
      letter-spacing: -0.03em; line-height: 1.35; color: {INK};
      max-width: 860px; margin: 0 auto 40px; }}
  @media (max-width: 640px) {{ .jisu-hero-t {{ font-size: 28px; }}
      .jisu-h {{ font-size: 24px; }} }}
  .st-key-card_l, .st-key-card_r {{ border: 1px solid {LINE}; border-radius: 2px;
      padding: 28px 28px 24px; min-height: 300px; justify-content: space-between; }}
  .st-key-card_l {{ background: {CARD}; }}
  .st-key-card_r {{ background: {DARK}; border-color: {DARK};
      box-shadow: 0 2px 10px rgba(30, 77, 43, 0.12); }}
  .st-key-card_r .stMarkdown p, .st-key-card_r .jisu-ct, .st-key-card_r .jisu-cl {{
      color: #fff !important; }}
  .st-key-card_r .jisu-cs, .st-key-card_r .jisu-ctag {{ color: #C9D8CC !important; }}
  .st-key-card_r button {{ background: {CARD} !important; color: {DARK} !important;
      border-color: {CARD} !important; }}
  .st-key-card_r button p {{ color: {DARK} !important; }}
  .jisu-ctop {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .jisu-icon {{ width: 44px; height: 44px; border: 1px solid {LINE}; display: flex;
      align-items: center; justify-content: center; background: #fff; }}
  .st-key-card_r .jisu-icon {{ background: transparent; border-color: #5E8467; }}
  .jisu-ctag {{ font-size: 13px; color: {SUB}; letter-spacing: 0.04em; }}
  .jisu-ct {{ font-size: 26px; font-weight: 900; color: {INK}; margin: 26px 0 8px;
      letter-spacing: -0.02em; }}
  .jisu-cl {{ font-size: 17px; color: {INK}; line-height: 1.6; }}
  .jisu-cs {{ font-size: 14px; color: {SUB}; margin: 14px 0 18px; }}
  .st-key-hero_img {{ max-width: 760px; margin: 24px auto 0; }}
  .st-key-hero_img img {{ border-radius: 0; }}

  .jisu-cards {{ display: flex; flex-wrap: wrap; gap: 16px; margin: 8px 0 18px; }}
  .jisu-card {{ flex: 1 1 220px; background: {CARD}; border: 1px solid {LINE};
      border-radius: 2px; padding: 22px 20px 18px; }}
  .jisu-card .n {{ font-size: 36px; font-weight: 900; color: {GOLD}; line-height: 1; }}
  .jisu-card .t {{ font-size: 20px; font-weight: 900; color: {DARK}; margin: 10px 0 6px; }}
  .jisu-card .d {{ font-size: 16px; color: #333; line-height: 1.65; }}
  .jisu-stat {{ flex: 1 1 200px; background: {CARD}; border: 1px solid {LINE};
      border-radius: 2px; padding: 22px 16px; text-align: center; }}
  .jisu-stat .v {{ font-size: 32px; font-weight: 900; color: {DARK}; }}
  .jisu-stat .v b {{ color: {GOLD}; }}
  .jisu-stat .l {{ font-size: 15px; color: {SUB}; margin-top: 4px; }}

  /* ── 안쪽 쪽 ── */
  .jisu-pk {{ color: {GREEN}; font-size: 13px; font-weight: 700; letter-spacing: 0.08em;
      margin-top: 40px; }}
  .jisu-pt {{ font-size: 34px; font-weight: 900; letter-spacing: -0.02em; color: {INK};
      line-height: 1.35; margin: 6px 0 10px; }}
  @media (max-width: 640px) {{ .jisu-pt {{ font-size: 26px; }} }}
  .jisu-pd {{ color: {SUB}; font-size: 16px; line-height: 1.7; margin-bottom: 18px; }}
  [class*="st-key-box"] {{ border: 1px solid {DARK}; background: {CARD};
      border-radius: 2px; padding: 24px 24px 20px; margin-bottom: 14px; }}
  @media (max-width: 640px) {{ [class*="st-key-box"] {{ padding: 16px 14px; }} }}
  .jisu-num {{ background: #fff; border: 1px solid {LINE}; border-radius: 2px;
      padding: 20px 12px; text-align: center; margin-bottom: 8px; }}
  .jisu-num .l {{ color: {SUB}; font-size: 15px; }}
  .jisu-num .v {{ color: {DARK}; font-size: 34px; font-weight: 900; }}
  .jisu-band {{ background: {DARK}; color: #fff; border-radius: 2px;
      padding: 18px 22px; margin: 6px 0 12px; }}
  .jisu-band .k {{ font-size: 13px; color: #C9D8CC; letter-spacing: 0.08em; }}
  .jisu-band .v {{ font-size: 26px; font-weight: 900; margin-top: 2px; }}
  .jisu-band .s {{ font-size: 15px; color: #DCE6DE; }}
  .jisu-h3 {{ font-size: 22px; font-weight: 900; color: {INK}; margin: 34px 0 8px; }}
  ol.jisu-ol {{ padding-left: 1.4rem; }}
  ol.jisu-ol li {{ font-size: 17px; line-height: 1.7; margin-bottom: 8px; }}
  ol.jisu-ol li::marker {{ color: {DARK}; font-weight: 900; }}

  /* ── 바닥 ── */
  .st-key-footer {{ background: {FOOT}; margin-top: 90px; padding: 34px 28px 22px;
      border-top: 1px solid {LINE}; }}
  .st-key-footer a {{ padding: 2px 0 !important; background: transparent !important; }}
  .st-key-footer a p {{ font-size: 15px !important; color: {INK} !important; }}
  .jisu-fh {{ font-size: 13px; font-weight: 700; color: {GOLD}; letter-spacing: 0.12em;
      margin-bottom: 8px; }}
  .jisu-ft {{ font-size: 15px; color: {INK}; line-height: 1.8; }}
  .jisu-fb {{ border-top: 1px solid {LINE}; margin-top: 18px; padding-top: 12px;
      font-size: 13px; color: {SUB}; }}

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
SHEET_URL, SHEET_TOKEN = _secret("APPS_SCRIPT_URL"), _secret("APPS_SCRIPT_TOKEN")

BODY, SETTINGS = content.load()
CONTACT = content.contact_line(SETTINGS)

for k, v in [("rows", []), ("total", 0), ("kw", ""),
             ("search_err", ""), ("searched", False), ("picked", None),
             ("result", None), ("queries", 0),
             ("diag_sent", None), ("pdf", None), ("pdf_sig", None),
             ("look_err", ""), ("no_data", ""), ("req_sent", 0),
             ("req_msg", None), ("mode", "find"), ("page", 1),
             ("places", []), ("places_err", "")]:
    st.session_state.setdefault(k, v)

# 쪽을 옮기면 Streamlit 이 **안 보이는 쪽의 입력 칸 값을 버립니다.** 요청서를 쓰다
# 결과를 보러 갔다 오면 다 지워져 있었습니다. 위젯이 그려지기 전에 같은 값을 다시
# 넣어 두면 남습니다. 숨은 칸(req_hp)은 일부러 붙잡지 않습니다.
_KEEP = ("req_name", "req_addr", "req_person", "req_contact", "req_text", "req_agree",
         "mode", "bill_name", "bill_addr", "bill_elec", "bill_gas", "kero", "lpg20",
         "lpg50", "dj_dong", "dj_bun", "dj_ji")
for _k in list(st.session_state.keys()):
    if _k in _KEEP or _k.startswith("heat_") or (_k[:1] == "m" and _k[1:].isdigit()):
        st.session_state[_k] = st.session_state[_k]

# 쪽 — 맨 아래에서 `st.navigation` 에 넘깁니다. 주소: / · /check · /result · /request
PAGE = {}


def _go(key: str, **extra):
    """다른 쪽으로. **단추를 누른 그 자리에서** 부릅니다(콜백 안에서는 못 옮김).

    결과·고른 주소는 위젯이 아닌 세션 값이라 쪽을 옮겨도 남습니다.
    """
    st.session_state.update(extra)
    st.switch_page(PAGE[key])


def _kicker(text: str, first: bool = False):
    return f'<div class="jisu-kicker{" first" if first else ""}">{text}</div>'


def _sec(kicker: str, title: str, first: bool = False):
    """칸 머리 — 작은 금색 머리글 + 큰 제목."""
    st.markdown(_kicker(kicker, first) + f'<div class="jisu-h">{title}</div>',
                unsafe_allow_html=True)


def _page_head(kicker: str, title: str, desc: str = ""):
    """안쪽 쪽 머리 — 녹색 작은 머리글 · 큰 제목 · 회색 설명."""
    st.markdown(f'<div class="jisu-pk">{kicker}</div><div class="jisu-pt">{title}</div>'
                + (f'<div class="jisu-pd">{desc}</div>' if desc else ""),
                unsafe_allow_html=True)


# ═══════════ ① 소개 ═══════════
def _two_buttons(key: str):
    c1, c2 = st.columns(2)
    if c1.button("자가진단 시작하기 →", key=f"{key}_check", type="primary",
                 width="stretch"):
        _go("check")
    if c2.button("컨설팅 요청하기 →", key=f"{key}_req", width="stretch"):
        _go("request")


# 카드 왼쪽 위 작은 네모 안의 선 그림 (직접 그린 단순한 선. 아이콘 글꼴을 쓰지 않음)
ICON_GAUGE = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
              'stroke="{c}" stroke-width="1.6" stroke-linecap="round">'
              '<path d="M4 16a8 8 0 0 1 16 0"/><path d="M12 16l4-5"/>'
              '<path d="M4 19h16"/></svg>')
ICON_TALK = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
             'stroke="{c}" stroke-width="1.6" stroke-linejoin="round">'
             '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>')

CARD_L = ("공개 자료 · 5분", "우리 절 자가진단",
          "우리 절의 에너지와 온실가스를 먼저 살펴보세요",
          "전기 · 도시가스 · 난방 연료 · 태양광")
CARD_R = ("사찰 대상 · 무료", "무료 컨설팅 요청",
          "현장 진단과 탄소중립 로드맵을 함께 세웁니다",
          "진단 · 감축 · 재생에너지 · 지원사업")


def _big_card(key: str, icon: str, color: str, data, label: str, target: str,
              primary: bool):
    tag, title, line, small = data
    with st.container(key=key):
        st.markdown(f'<div class="jisu-ctop"><div class="jisu-icon">'
                    f'{icon.format(c=color)}</div><div class="jisu-ctag">{tag}</div></div>'
                    f'<div class="jisu-ct">{title}</div><div class="jisu-cl">{line}</div>'
                    f'<div class="jisu-cs">{small}</div>', unsafe_allow_html=True)
        if st.button(label, key=f"{key}_go", type="primary" if primary else "secondary"):
            _go(target)


def _cards(items, numbered: bool = False) -> str:
    out = []
    for i, (t, d) in enumerate(items, 1):
        n = f'<div class="n">{i}</div>' if numbered else ""
        out.append(f'<div class="jisu-card">{n}<div class="t">{t}</div>'
                   f'<div class="d">{d}</div></div>')
    return '<div class="jisu-cards">' + "".join(out) + "</div>"


def _text_and_image(key: str, kicker: str, title: str, text: str, image: str,
                    image_left: bool = False):
    """글 + 그림 좌우. 휴대폰에서는 그림이 아래로 갑니다."""
    if not title:
        return
    with st.container(key=key):
        _sec(kicker, title)
        if not image:
            st.markdown(text)
            return
        if image_left:
            c_img, c_txt = st.columns([2, 3], vertical_alignment="center", gap="large")
        else:
            c_txt, c_img = st.columns([3, 2], vertical_alignment="center", gap="large")
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


def page_intro():
    lead, secs = content.sections(BODY)
    tagline = lead.strip("* ").strip() or content.SITE_TITLE
    who_t, who = content.find(secs, "우리는")

    # 1. 첫 화면 — 머리글 · 큰 제목 · 큰 카드 두 장
    st.markdown('<div class="jisu-hero-k">' + _kicker("Buddhist Carbon Neutral Action", True)
                + f'</div><div class="jisu-hero-t">{tagline}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _big_card("card_l", ICON_GAUGE, DARK, CARD_L, "자가진단 시작하기 →",
                  "check", True)
    with c2:
        _big_card("card_r", ICON_TALK, "#FFFFFF", CARD_R, "컨설팅 요청하기 →",
                  "request", False)
    hero = content.img("temple_solar.png")
    if hero:
        with st.container(key="hero_img"):
            st.write("")
            st.image(hero, width="stretch")

    # 2. 숫자 카드
    _sec("Practice", "먼저 해 본 곳")
    st.markdown('<div class="jisu-cards">' + "".join(
        f'<div class="jisu-stat"><div class="v"><b>{v}</b> {u}</div>'
        f'<div class="l">{l}</div></div>' for v, u, l in STATS) + "</div>",
        unsafe_allow_html=True)
    _t, done = content.find(secs, "먼저 해 본")
    if done:
        st.markdown(f'<p class="jisu-small">{done}</p>', unsafe_allow_html=True)

    # 3. 우리는 / 하는 일
    if who:
        _sec("About", who_t)
        st.markdown(who)
    work_t, work = content.find(secs, "하는 일")
    if work_t:
        _sec("What we do", work_t)
        st.markdown(_cards(WORK_CARDS), unsafe_allow_html=True)
        st.markdown(work)

    # 4·5. 오래된 가르침 · 사찰의 현실
    t, x = content.find(secs, "가르침")
    _text_and_image("row1", "Teaching", t, x, content.img("cycle.png"))
    t, x = content.find(secs, "현실")
    _text_and_image("row2", "Reality", t, x, content.img("meter_fuel.png"), image_left=True)

    # 6. 순서가 중요합니다
    t, x = content.find(secs, "순서")
    items = content.steps(x)
    if t and items:
        _sec("Roadmap", t)
        st.markdown(_cards(items, numbered=True), unsafe_allow_html=True)
        hp = content.img("heatpump.png")
        if hp:
            c1, c2 = st.columns([2, 3], vertical_alignment="center", gap="large")
            c1.image(hp, width="stretch")
            c2.markdown("**감축**의 중심은 히트펌프입니다. 전기판넬·등유 보일러를 "
                        "바꾸면 난방 에너지가 크게 줍니다. 그다음에 남은 전기를 "
                        "태양광으로 채웁니다.")
    elif t:
        _sec("Roadmap", t)
        st.markdown(x)

    # 7. 단장 인사말 (설정 칸이 비면 숨김)
    g = content.greeting(SETTINGS)
    if g:
        title, text, photo = g
        _sec("Greeting", title)
        if photo:
            c1, c2 = st.columns([1, 2], gap="large")
            c1.image(photo, width="stretch")
            c2.markdown(text)
        else:
            st.markdown(text)

    # 8. 함께하는 곳 · 시작하기
    with_t, with_x = content.find(secs, "함께")
    start_t, start_x = content.find(secs, "시작")
    lotus = content.img("lotus.png")
    if start_t or with_t:
        _sec("Start", start_t or with_t)
        c_img, c_txt = st.columns([1, 3], vertical_alignment="center", gap="large")
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
            _sec("More", title)
            st.markdown(text)


# ═══════════ ② 자가진단 ═══════════
def _run_search(keyword: str, page: int = 1, keep_places: bool = False):
    try:
        rows, total = juso.search(keyword, CONFM_KEY, page=page, per_page=PER_PAGE)
        err = ""
    except juso.JusoError as e:
        rows, total = [], 0
        err = portal.hide_keys(str(e))
    except Exception:
        rows, total, err = [], 0, "주소 검색이 잠시 되지 않습니다. 잠시 뒤 다시 찾아 주세요."
    st.session_state.update(rows=rows, total=total, page=page, kw=keyword,
                            search_err=err, searched=True, picked=None,
                            addr_pick=None, look_err="", no_data="")
    if not keep_places:
        st.session_state.update(places=[], places_err="", place_pick=None)


def _direct_block():
    """지번을 손으로 넣기 — 컨설턴트 앱 「자세히 — 지번을 직접 넣어 조회하기」와 같은 흐름.

    **접어 둡니다.** 도로명이 없는 지번은 주소 검색에 무엇을 넣어도 안 나옵니다.
    그 동네를 찾아 행정구역코드만 빌리고 번·지는 갈아 끼웁니다(`juso.sibling`).
    """
    with st.expander("지번을 직접 넣기 (주소 검색에 안 나올 때)", expanded=False):
        st.markdown('<p class="jisu-small">고지서나 지도 앱에서 <b>지번을 확인하신 뒤</b> '
                    "넣어 주세요.</p>", unsafe_allow_html=True)
        dong = st.text_input("시·군·구와 동·리 이름", key="dj_dong",
                             placeholder="예: 강릉시 연곡면 삼산리")
        c1, c2 = st.columns(2)
        bun = c1.text_input("번 (본번)", key="dj_bun", placeholder="예: 569")
        ji = c2.text_input("지 (부번) - 없으면 비워 두세요", key="dj_ji",
                           placeholder="예: 3")
        if not st.button("이 지번으로 찾기", key="dj_go", width="stretch"):
            return
        bun_s, ji_s = str(bun or "").strip(), str(ji or "").strip() or "0"
        if not (dong or "").strip() or not bun_s.isdigit() or not ji_s.isdigit():
            st.warning("동·리 이름과 번(숫자)을 넣어 주세요. 지(부번)가 없으면 비워 두세요.")
            return
        try:
            rows, _ = juso.search(dong.strip(), CONFM_KEY, per_page=1)
        except Exception:
            rows = []
        if not rows:
            st.warning("그 동네를 찾지 못했습니다. 시·군과 동·리 이름을 함께 넣어 보세요. "
                       "예: 강릉시 연곡면 삼산리")
            return
        j = juso.sibling(rows[0], int(bun_s), int(ji_s), inherit_name=False)
        st.session_state.update(picked=j, look_err="", no_data="")
        st.rerun()


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
    _go("result", result=r, pdf=None, pdf_sig=None)


CHECK_NOTES = (
    "전기·가스는 공개된 건물에너지 자료에서 **지번 한 곳**에 잡힌 값입니다. "
    "사찰 전체가 아닐 수 있습니다.",
    "등유·LPG 는 넣으신 양만 셈합니다. 화목(장작)은 배출 합계에 넣지 않습니다.",
    "결과는 개략 진단입니다. 정확한 진단은 현장 확인이 필요합니다.",
)


def page_check():
    _page_head("자가진단", "우리 절의 에너지를 먼저 살펴보세요",
               "이 진단은 공개 자료와 입력하신 값으로 계산합니다. "
               "입력하신 숫자 외의 개인 정보는 받지 않습니다.")
    modes = {"find": "주소나 절 이름으로 찾기", "bill": "고지서 숫자로 직접 넣기"}
    with st.container(key="box_check"):
        if not LOOKUP_ON:
            st.session_state.mode = "bill"
        else:
            st.radio("진단 방법", list(modes), format_func=modes.get, key="mode",
                     horizontal=True)

        if st.session_state.mode == "find":
            _find_block()
        else:
            _bill_block()
    with st.expander("유의사항"):
        st.markdown(NL.join(f"- {t}" for t in CHECK_NOTES))


def _kakao_key() -> str:
    """카카오 키. **어떤 오류든 삼키고 빈 문자열**(컨설턴트 앱 `_kakao_key` 와 같은 까닭)."""
    try:
        return keys.kakao()
    except Exception:
        return ""


KAKAO_KEY = _kakao_key() if LOOKUP_ON else ""


def _is_name(kw: str) -> bool:
    """숫자가 없으면 절 이름으로 찾는 것으로 봅니다. 「구산동 314」는 주소."""
    return not any(c.isdigit() for c in (kw or ""))


def _map_search(kw: str):
    """지도에서 절 이름 찾기. 결과는 **화면에만** 두고 저장하지 않습니다(CLAUDE.md 7장)."""
    st.session_state.update(places=[], places_err="", place_pick=None)
    if not (KAKAO_KEY and _is_name(kw)):
        return
    try:
        st.session_state.places = kakao.search(kw, KAKAO_KEY)[0]
    except Exception:
        # 지도 칸은 어떤 오류가 나도 거기서 끝냅니다. 주소 검색은 그대로 돕니다.
        st.session_state.places_err = ("지도 검색이 잠시 되지 않습니다. "
                                       "아래 주소 검색 결과를 봐 주세요.")


def _pick_row():
    i = st.session_state.get("addr_pick")
    rows = st.session_state.rows
    if i is not None and i < len(rows):
        st.session_state.update(picked=rows[i], look_err="", no_data="")


def _pick_place():
    i = st.session_state.get("place_pick")
    places = st.session_state.get("places") or []
    if i is None or i >= len(places):
        return
    # 고른 곳을 도로명주소로 **다시** 찾습니다. 그 결과만 씁니다.
    _run_search(places[i].search_key, keep_places=True)


def _place_label(pl) -> str:
    return f"{pl.name}  ·  {pl.jibun or pl.road or '주소 없음'}"


def _find_block():
    st.markdown("#### 1. 주소 또는 절 이름으로 찾기")
    st.markdown('<p class="jisu-small">같은 이름의 절이 많습니다. <b>시·군 이름을 함께</b> '
                "넣으면 잘 찾아집니다. 예: 원오사 양주</p>", unsafe_allow_html=True)
    with st.form("search"):
        kw = st.text_input("주소 또는 절 이름", value=st.session_state.kw,
                           placeholder="예: 구산동 314  또는  원오사 양주")
        go_search = st.form_submit_button("찾기", type="primary", width="stretch")
    if go_search:
        _map_search(kw)
        _run_search(kw, keep_places=True)

    # ── 지도 결과 (이름으로 찾을 때 먼저) ──
    places = st.session_state.get("places") or []
    if st.session_state.get("places_err"):
        st.info(st.session_state.places_err)
    if places:
        st.markdown(f"**지도에서 {len(places)}곳**을 찾았습니다. 우리 절을 고르시면 "
                    "그 주소로 다시 찾습니다.")
        st.radio("지도 결과", list(range(len(places))), key="place_pick",
                 format_func=lambda k: _place_label(places[k]), index=None,
                 label_visibility="collapsed", on_change=_pick_place)

    if st.session_state.search_err:
        st.warning(st.session_state.search_err)
    rows = st.session_state.rows
    if st.session_state.searched and not rows and not st.session_state.search_err:
        st.warning("주소 검색에서는 찾지 못했습니다. 동 이름과 번지로 다시 찾아 보세요. "
                   "예: 은평구 구산동 314")
        st.info("절 이름은 **건물 이름이 등록된 절만** 주소 검색에 나옵니다. "
                "찾아지지 않으면 아래 「지번을 직접 넣기」나, 위의 "
                "**「고지서 숫자로 직접 넣기」**를 골라 주세요.")
    if rows:
        total, page = st.session_state.total, st.session_state.page
        last = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        st.markdown(f"**주소 검색 {total:,}건** 중 {page}쪽입니다. 우리 절을 골라 주세요.")
        st.radio("주소 고르기", list(range(len(rows))), key="addr_pick",
                 format_func=lambda k: rows[k].label(), index=None,
                 label_visibility="collapsed", on_change=_pick_row)
        c1, c2, c3 = st.columns(3)
        if page > 1:
            c1.button("앞으로", key="pg_prev", width="stretch",
                      on_click=_run_search, args=(st.session_state.kw, page - 1, True))
        if page < last:
            c2.button("더 보기", key="pg_next", width="stretch",
                      on_click=_run_search, args=(st.session_state.kw, page + 1, True))
        kw_now = (st.session_state.kw or "").rstrip()
        if not any(r.is_mountain for r in rows) and not kw_now.endswith("산"):
            # 산중 사찰은 산 지번이 뒤쪽 쪽수에 묻히는 일이 많습니다.
            c3.button("산 지번만 찾기", key="mt_go", width="stretch",
                      on_click=_run_search, args=(kw_now + " 산", 1, True))
    _direct_block()

    j = st.session_state.picked
    if j is None:
        return
    st.markdown("---")
    st.markdown(f"**고른 주소:** {j.jibunAddr}")
    if _odd_place(j):
        st.warning(sc.NOT_TEMPLE_TEXT)
    if j.name_hit:
        st.warning("이름으로 찾은 주소입니다. **주소가 맞는지 확인해 주세요.** "
                   "같은 이름의 다른 절이 흔합니다.")
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
    if st.session_state.look_err:
        st.warning(st.session_state.look_err)
    if st.session_state.no_data:
        st.warning(st.session_state.no_data)
        st.button("고지서 숫자로 직접 넣기",
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


def page_result():
    r = st.session_state.result
    if r is None:
        _page_head("결과", "아직 진단한 결과가 없습니다",
                   "먼저 자가진단을 해 주세요. 5분이면 됩니다.")
        if st.button("자가진단 하러 가기 →", type="primary"):
            _go("check")
        return
    _send_diag_once(r)

    where = f"{r.year}년 공개 자료" if r.mode == sc.MODE_LOOKUP else "입력하신 고지서 값"
    _page_head("자가진단 결과", r.name, f"{r.addr or '주소 미입력'} · {where}")

    cols = st.columns(3)
    for c, (lbl, val) in zip(cols, (("연간 배출량", f"{r.total_t:,.1f} t"),
                                     ("국민 환산", f"{r.people:,.1f}명분"),
                                     ("태양광 필요용량", f"{r.solar_kw:,.0f} kW"))):
        c.markdown(f'<div class="jisu-num"><div class="l">{lbl}</div>'
                   f'<div class="v">{val}</div></div>', unsafe_allow_html=True)
    parts = [f"전기 {r.elec_kwh:,.0f} kWh", f"도시가스 {r.gas_kwh:,.0f} kWh"]
    if r.kero_l:
        parts.append(f"등유 {r.kero_l:,.0f} L")
    if r.lpg_kg:
        parts.append(f"LPG {r.lpg_kg:,.0f} kg")
    st.markdown(f'<p class="jisu-small">{" · ".join(parts)}<br>'
                f"국민 환산은 1인당 연 {sc.em.KOR_PER_CAPITA} t, 태양광은 하루 "
                f"{sc.em.SOLAR_HOURS}시간 발전으로 셈했습니다.</p>",
                unsafe_allow_html=True)

    ratio = sc.ratio_text(r.ratio)
    st.markdown('<div class="jisu-band"><div class="k">우리 절 유형</div>'
                f'<div class="v">{r.kind}</div>'
                + (f'<div class="s">{ratio}</div>' if ratio else "")
                + "</div>", unsafe_allow_html=True)

    st.markdown('<div class="jisu-h3">먼저 해 볼 일</div><ol class="jisu-ol">'
                + "".join(f"<li>{t}</li>" for t in r.todo) + "</ol>",
                unsafe_allow_html=True)

    if r.monthly and any(r.monthly.values()):
        st.markdown('<div class="jisu-h3">월별 전기 사용량 (kWh)</div>',
                    unsafe_allow_html=True)
        st.bar_chart({f"{sc._month_of(k):02d}월": v for k, v in sorted(r.monthly.items())},
                     color=GREEN, x_label="", y_label="")

    st.markdown('<div class="jisu-h3">지원사업</div>', unsafe_allow_html=True)
    st.markdown(sc.SUPPORT_TEXT)
    with st.expander("이 진단의 한계", expanded=True):
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
    if c2.button("컨설팅 요청하기 →", type="primary", width="stretch"):
        _go("request", req_name=r.name, req_addr=r.addr)


# ═══════════ ④ 컨설팅 요청 ═══════════
def page_request():
    _page_head("컨설팅 요청", "무료 컨설팅을 요청해 주세요",
               "지수광풍은 사찰을 대상으로 무료 컨설팅을 하고 있습니다. "
               "아래를 적어 보내 주시면 연락드립니다.")
    msg = st.session_state.req_msg
    if msg == "sent":
        st.success(sheet.SENT_TEXT)

    with st.container(key="box_req"):
        c1, c2 = st.columns(2)
        name = c1.text_input("절 이름 (필수)", key="req_name")
        addr = c2.text_input("주소 (필수)", key="req_addr")
        c3, c4 = st.columns(2)
        person = c3.text_input("담당자 이름 (필수)", key="req_person")
        contact = c4.text_input("연락처 (필수) — 전화 또는 이메일", key="req_contact",
                                placeholder="예: 010-1234-5678")
        text = st.text_area(f"요청 내용 ({sheet.REQ_MAX_TEXT:,}자 이내)", key="req_text",
                            max_chars=sheet.REQ_MAX_TEXT, height=140)
        with st.container(key="hp"):
            hp = st.text_input("홈페이지", key="req_hp", label_visibility="collapsed",
                               autocomplete="off")

        r = st.session_state.result
        summary = r.summary() if r is not None else ""
        if summary:
            st.markdown(f'<p class="jisu-small">자가진단 결과가 함께 갑니다: {summary}</p>',
                        unsafe_allow_html=True)

    # 동의 문안은 테두리 상자 안에, 체크와 [보내기] 는 그 아래에 (문안 글자는 그대로)
    with st.container(key="box_consent"):
        st.markdown(f"**{sheet.CONSENT_TITLE}**" + NL + NL
                    + NL.join(f"- {t}" for t in sheet.CONSENT_LINES))
    agree = st.checkbox(sheet.CONSENT_CHECK, key="req_agree")

    used = st.session_state.req_sent >= sheet.SEND_LIMIT
    if used:
        st.info("이 화면에서는 더 보낼 수 없습니다. 지수광풍이 곧 연락드리겠습니다.")
    if st.button("보내기 →", type="primary", disabled=not agree or used):
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


# ═══════════ 머리 · 바닥 ═══════════
MENU = (("intro", "소개"), ("check", "자가진단"), ("result", "결과"),
        ("request", "컨설팅 요청"))


def _header(cur: str):
    """로고 · 표어 · 메뉴 네 개 + 「무료 상담」. 휴대폰에서는 표어를 감춥니다."""
    with st.container(key="topbar"):
        c1, c2, c3 = st.columns([3, 3, 6], vertical_alignment="center")
        logo = content.logo(SETTINGS)
        if logo:
            c1.image(logo, width=220)
        else:
            c1.markdown('<div class="jisu-logo">불교탄소중립실천단 <b>지수광풍</b></div>',
                        unsafe_allow_html=True)
        slogan_img = content.slogan_img(SETTINGS)
        if slogan_img:
            with c2.container(key="slogan_img"):
                st.image(slogan_img, width=200)
        else:
            c2.markdown(f'<div class="jisu-slogan">{content.slogan(SETTINGS)}</div>',
                        unsafe_allow_html=True)
        with c3.container(key="menu"):
            for k, label in MENU:
                with st.container(key=f"m_{k}{'_on' if k == cur else ''}"):
                    st.page_link(PAGE[k], label=label)
            with st.container(key="m_cta"):
                st.page_link(PAGE["request"], label="무료 상담")


def _footer():
    with st.container(key="footer"):
        c1, c2, c3 = st.columns(3, gap="large")
        with c1:
            st.markdown('<div class="jisu-fh">바로가기</div>', unsafe_allow_html=True)
            for k, label in (("intro", "소개"), ("check", "자가진단"),
                             ("request", "컨설팅 요청")):
                st.page_link(PAGE[k], label=label)
        tel = (SETTINGS.get("문의_전화") or "").strip()
        org = (SETTINGS.get("문의_기관") or "").strip() or "불교환경연대 사무실"
        c2.markdown('<div class="jisu-fh">문의</div><div class="jisu-ft">'
                    f'{org}' + (f'<br>☎ {tel}' if tel else "") + "</div>",
                    unsafe_allow_html=True)
        c3.markdown('<div class="jisu-fh">함께하는 곳</div><div class="jisu-ft">'
                    "불교환경연대<br>비로자나자연에너지협동조합</div>",
                    unsafe_allow_html=True)
        st.markdown(f'<div class="jisu-fb">© {content.SITE_TITLE} · 이 진단은 개략 '
                    "진단이며 현장 확인을 대신하지 않습니다"
                    + (f" · 판 {VERSION}" if VERSION else "") + "</div>",
                    unsafe_allow_html=True)


PAGE.update(
    intro=st.Page(page_intro, title="소개", url_path="intro", default=True),
    check=st.Page(page_check, title="자가진단", url_path="check"),
    result=st.Page(page_result, title="결과", url_path="result"),
    request=st.Page(page_request, title="컨설팅 요청", url_path="request"),
)
_current = st.navigation(list(PAGE.values()), position="hidden")
# 시험(AppTest)은 주소로 쪽을 고를 수 없어 이 값으로 고릅니다. 화면에서는 쓰지 않습니다.
_cur_key = st.session_state.get("_test_page") or next(
    (k for k, pg in PAGE.items() if pg.url_path == _current.url_path), "intro")
_header(_cur_key)
if st.session_state.get("_test_page"):
    # 고른 쪽이 아닌 `st.Page` 는 .run() 을 못 부릅니다. 함수를 바로 부릅니다.
    {"intro": page_intro, "check": page_check, "result": page_result,
     "request": page_request}[_cur_key]()
else:
    _current.run()
_check_block()
_footer()
