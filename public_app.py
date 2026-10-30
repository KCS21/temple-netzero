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
import juso
import keys
import portal
import region
from public import content, report_pdf, selfcheck as sc, sheet

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))
NL = chr(10)

PAGES = ("소개", "자가진단", "결과", "컨설팅 요청")
QUERY_LIMIT = 5          # 한 세션의 자료 조회 횟수 (공공데이터포털 키를 컨설턴트 앱과 함께 씀)
PER_PAGE = 5
BUSY_TEXT = "자료 서버가 바쁩니다. 잠시 뒤 다시 시도해 주세요."
LIMIT_TEXT = "조회를 여러 번 하셨습니다. 잠시 뒤 다시 시도해 주세요."

DARK, GREEN, PALE = "#1E5631", "#2F6B3F", "#E4F0E6"

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
  .block-container {{ padding-top: 1.2rem; max-width: 760px; }}

  .jisu-head {{ background: {DARK}; color: #fff; border-radius: 12px;
      padding: 18px 20px 14px; margin-bottom: 10px; }}
  .jisu-head .t {{ font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
  .jisu-head .s {{ font-size: 16px; opacity: 0.9; margin-top: 2px; }}

  /* 쪽 이동 — 휴대폰에서 줄이 넘어가도 누르기 쉽게 */
  .st-key-nav div[role="radiogroup"] {{ gap: 6px; flex-wrap: wrap; }}
  .st-key-nav div[role="radiogroup"] > label {{ background: {PALE};
      border-radius: 999px; padding: 8px 16px; margin: 0; }}
  .st-key-nav label[data-selected="true"], .st-key-nav label:has(input:checked) {{
      background: {GREEN}; }}
  .st-key-nav label[data-selected="true"] p, .st-key-nav label:has(input:checked) p {{
      color: #fff !important; }}
  .st-key-nav label > div > div > div:first-child:not([data-testid]) {{ display: none; }}
  .st-key-nav div[role="radiogroup"] p {{ font-size: 18px; font-weight: 700;
      color: {DARK}; }}

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

for k, v in [("nav", PAGES[0]), ("rows", []), ("total", 0), ("kw", ""),
             ("search_err", ""), ("searched", False), ("picked", None),
             ("picked_i", None), ("result", None), ("queries", 0),
             ("diag_sent", None), ("pdf", None), ("pdf_sig", None),
             ("look_err", ""), ("no_data", ""), ("req_sent", 0),
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
st.radio("쪽", PAGES, key="nav", horizontal=True, label_visibility="collapsed")


# ═══════════ ① 소개 ═══════════
def page_intro():
    if BODY:
        st.markdown(BODY)
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
    st.write("")
    st.button("자가진단 해 보기", type="primary", width="stretch",
              on_click=go, args=("자가진단",))


# ═══════════ ② 자가진단 ═══════════
def _run_search(keyword: str):
    try:
        rows, total = juso.search(keyword, CONFM_KEY, per_page=PER_PAGE)
        err = ""
    except juso.JusoError as e:
        rows, total = [], 0
        err = portal.hide_keys(str(e))
    except Exception:
        rows, total, err = [], 0, "주소 검색이 잠시 되지 않습니다. 잠시 뒤 다시 찾아 주세요."
    st.session_state.update(rows=rows, total=total, kw=keyword, search_err=err,
                            searched=True, picked=None, picked_i=None,
                            look_err="", no_data="")


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


def _find_block():
    st.markdown("#### 1. 주소 또는 절 이름으로 찾기")
    with st.form("search"):
        kw = st.text_input("주소 또는 절 이름", value=st.session_state.kw,
                           placeholder="예: 구산동 314  또는  절 이름")
        go_search = st.form_submit_button("찾기", type="primary", width="stretch")
    if go_search:
        _run_search(kw)

    if st.session_state.search_err:
        st.warning(st.session_state.search_err)
    rows = st.session_state.rows
    if st.session_state.searched and not rows:
        if not st.session_state.search_err:
            st.warning("찾으시는 주소가 없습니다. 동 이름과 번지로 다시 찾아 보세요. "
                       "예: 은평구 구산동 314")
        st.info("절 이름은 **건물 이름이 등록된 절만** 찾아집니다. "
                "찾아지지 않으면 위에서 **「고지서 숫자로 직접 넣기」**를 골라 주세요.")
        return
    if not rows:
        return

    st.markdown(f"**{st.session_state.total:,}건** 중 앞의 {len(rows)}건입니다. "
                "우리 절을 골라 주세요.")
    i = st.radio("주소 고르기", list(range(len(rows))),
                 format_func=lambda k: rows[k].label(), index=None,
                 label_visibility="collapsed")
    st.markdown('<p class="jisu-small">우리 절이 없으면 동 이름과 번지로 다시 찾거나, '
                "「고지서 숫자로 직접 넣기」를 골라 주세요.</p>", unsafe_allow_html=True)
    if i is None:
        return
    if st.session_state.picked_i != i:
        st.session_state.update(picked=rows[i], picked_i=i, look_err="", no_data="")
    j = st.session_state.picked
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

    st.markdown("## 우리 절 유형")
    ratio = sc.ratio_text(r.ratio)
    st.markdown(f'<div class="jisu-box"><div class="jisu-kind">{r.kind}</div>'
                + (f'<div class="jisu-small">{ratio}</div>' if ratio else "")
                + "</div>", unsafe_allow_html=True)

    st.markdown("## 먼저 해 볼 일")
    st.markdown(NL.join(f"{i}. {t}" for i, t in enumerate(r.todo, 1)))

    if r.monthly and any(r.monthly.values()):
        st.markdown("## 월별 전기 사용량 (kWh)")
        st.bar_chart({f"{sc._month_of(k):02d}월": v for k, v in sorted(r.monthly.items())},
                     color=GREEN, x_label="", y_label="")

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
def page_request():
    st.markdown("## 컨설팅 요청")
    st.markdown("지수광풍은 사찰을 대상으로 **무료 컨설팅**을 하고 있습니다. "
                "아래를 적어 보내 주시면 연락드립니다.")
    msg = st.session_state.req_msg
    if msg == "sent":
        st.success(sheet.SENT_TEXT)

    name = st.text_input("절 이름 (필수)", key="req_name")
    addr = st.text_input("주소 (필수)", key="req_addr")
    person = st.text_input("담당자 이름 (필수)", key="req_person")
    contact = st.text_input("연락처 (필수) — 전화 또는 이메일", key="req_contact",
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

    st.markdown(f"**{sheet.CONSENT_TITLE}**" + NL + NL
                + NL.join(f"- {t}" for t in sheet.CONSENT_LINES))
    agree = st.checkbox(sheet.CONSENT_CHECK, key="req_agree")

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
