# -*- coding: utf-8 -*-
"""
사찰 넷제로 진단 도구 — 개략 진단
불교탄소중립실천단 지수광풍

실행:  streamlit run app.py
"""
import datetime as dt
import io
import os
import tempfile
import time

_NL = chr(10)

import streamlit as st

import bldengy
import bldrgst
import emissions as em
import juso
import kakao
import keys
import batch
import portal
import region
import store
import template_out as tpl

# 인증키는 같은 폴더의 키.txt 에서 읽습니다. 코드에 키를 넣지 마십시오.

PER_PAGE = 5

st.set_page_config(page_title="사찰 넷제로 진단", page_icon="🪷", layout="centered")
st.markdown("""
<style>
  html, body, [class*="css"] { font-size: 18px; }
  .stButton > button { font-size: 20px; font-weight: 700;
      padding: 0.7rem 1.6rem; border-radius: 10px; }
  .stTextInput input { font-size: 20px; padding: 0.7rem; }
  div[role="radiogroup"] label { font-size: 19px; padding: 6px 0; }
  .hint { color: #6b6a64; font-size: 16px; }
</style>""", unsafe_allow_html=True)

def _share_mode() -> bool:
    """의견을 받으려고 남에게 보여주는 판인가.

    남들이 보는 판에서는 1~4단계(주소 -> 엑셀)만 보입니다. 사찰 기록·일괄
    조회·방문 우선순위는 감춥니다. 까닭 둘.

    1. 조사한 사찰 목록은 모임 안의 자료입니다. 남에게 보일 것이 아닙니다
    2. 웹에 올리면 여러 사람이 같은 파일에 쓰게 되어 서로의 기록이 섞이고,
       서버가 다시 뜨면 사라집니다. 기록은 교수님 컴퓨터에서만 쌓습니다
    """
    if os.environ.get("JISU_SHARE", "").strip():
        return True
    try:
        return bool(st.secrets.get("share_mode", False))
    except Exception:
        return False


SHARE = _share_mode()

def _old_sgg(sigungu_cd: str) -> str:
    """통합 지역의 옛 시군구코드. **없으면 빈 문자열** (되묻지 않음).

    `_kakao_key()` 와 같은 까닭으로 감쌉니다 — Streamlit 은 `app.py` 만
    다시 돌리고 **불러온 모듈은 메모리에 그대로 둡니다.** 새 판을 올리면
    `app.py` 는 새것인데 `region` 은 옛것이 남아, 아직 없는
    `region.old_sigungu` 를 부르다 **3단계가 통째로 죽었습니다**
    (2026-10-25, 광주의 한 절). 서버를 다시 띄우면 풀리지만 그때까지
    아무도 조회를 못 합니다.

    여기서 삼키면 **되묻기만 쉬고** 나머지 조회는 그대로 돕니다.
    """
    try:
        return region.old_sigungu(sigungu_cd)
    except Exception:
        return ""


def _place(addr: str) -> str:
    """옛 코드로 받을 때 견줄 읍면동·리. 모르면 빈 문자열 (위와 같은 까닭)."""
    try:
        return region.place_token(addr)
    except Exception:
        return ""


def _kakao_key() -> str:
    """카카오 키. **무슨 일이 있어도 도구를 멈추지 않습니다.**

    지도 검색은 있으면 좋은 것이지 없으면 안 되는 것이 아닙니다(작업지시 07 ①).
    그런데 이 한 줄 때문에 **배포판이 통째로 멈춘 적이 있습니다**(2026-10-24).

    까닭은 Streamlit 이 `app.py` 만 다시 돌리고 **불러온 모듈은 그대로 두기**
    때문입니다. 새 판을 올리면 `app.py` 는 새것인데 `keys` 는 옛것이 메모리에
    남아, 아직 없는 `keys.kakao` 를 부르다 AttributeError 로 첫 화면조차
    못 떴습니다. 서버를 다시 띄우면 풀리지만, 그때까지 아무도 못 씁니다.

    그래서 여기서는 **어떤 오류든 삼키고 빈 문자열**을 돌려줍니다.
    키가 없는 것과 똑같이 취급되어 단추만 숨습니다.
    """
    try:
        return keys.kakao()
    except Exception:
        return ""


try:
    CONFM_KEY, SERVICE_KEY = keys.load()
    KAKAO_KEY = _kakao_key()      # 없어도 됩니다. 단추만 숨깁니다
except keys.KeyError_ as e:
    st.title("사찰 넷제로 진단")
    st.error(str(e))
    st.stop()

for k, v in [("rows", []), ("total", 0), ("page", 1), ("kw", ""),
             ("picked", None), ("error", None), ("bld", None), ("diag", None),
             # 1단계 라디오에서 **방금 고른 줄**. 이것이 없으면 아래 라디오가
             # 다시 그려질 때마다 picked 를 제 값으로 되돌려 놓습니다.
             ("addr_applied", None), ("temple_name", ""),
             ("xlsx", None),
             # 지도 검색(작업지시 07 ①) · 옆 지번(②) · 묶기(③)
             ("places", []), ("places_err", ""), ("kakao_done", ""),
             ("sibs", None), ("sibs_err", ""), ("merged", []),
             ("bill_ok", False)]:
    st.session_state.setdefault(k, v)


# ═══════════ 1단계 — 주소 찾기 ═══════════
st.title("사찰 주소 찾기")
st.markdown('<p class="hint"><b>주소 또는 절 이름</b>을 넣어 주세요. '
            "예: 구산동 314 · 절 이름<br>"
            "절 이름으로 찾은 것에는 <b>(이름으로 찾음)</b> 표시가 붙습니다. "
            "<b>주소가 맞는지 꼭 확인해 주세요.</b> 같은 이름의 다른 절이 흔합니다."
            "</p>", unsafe_allow_html=True)


def run_search(keyword, page):
    try:
        rows, total = juso.search(keyword, CONFM_KEY, page=page, per_page=PER_PAGE)
    except juso.JusoError as e:
        st.session_state.update(rows=[], total=0, error=str(e), searched=True)
        return
    st.session_state.update(rows=rows, total=total, page=page, kw=keyword,
                            picked=None, error=None, bld=None, diag=None,
                            addr_applied=None, sibs=None, merge_state=None,
                            temple_name='',
                            searched=True)


def _kakao_block():
    """지도에서 절 이름 찾기 (작업지시 07 ①).

    **키가 없으면 아무것도 보이지 않습니다.** 지도 검색은 있으면 좋은
    것이지 없으면 안 되는 것이 아닙니다. 오류 화면이 나와선 안 됩니다.

    결과는 **저장하지 않습니다.** 고른 주소를 도로명주소 API 로 다시
    조회해서 그 결과만 저장합니다(kakao.py 머리말).
    """
    if not KAKAO_KEY:
        return
    kw = (st.session_state.kw or "").strip()
    if not kw:
        return
    with st.expander(f"지도에서 「{kw}」 찾아보기", expanded=False):
        st.markdown('<p class="hint">도로명주소 검색은 <b>건물 이름이 등록된 절만</b> '
                    "찾습니다. 지도에는 더 많이 있습니다.<br>"
                    "<b>누르실 때만</b> 지도를 찾습니다.</p>",
                    unsafe_allow_html=True)
        if st.button("지도에서 찾기", key="kakao_go", width="stretch"):
            try:
                st.session_state.places = kakao.search(kw, KAKAO_KEY)[0]
                st.session_state.places_err = ""
            except Exception as e:
                # **어떤 오류가 나도 지도 칸에서 끝냅니다.** 지도 검색은
                # 있으면 좋은 것이지 없으면 안 되는 것이 아닙니다. 예전에
                # 키에 한글이 섞여 UnicodeEncodeError 가 났을 때 **화면
                # 전체가 죽었습니다**(2026-10-24). 주소 검색은 그대로
                # 돌아야 합니다.
                st.session_state.places = []
                st.session_state.places_err = (
                    str(e) if isinstance(e, kakao.KakaoError) else
                    "지도 검색이 되지 않습니다." + _NL + _NL +
                    "**주소로 찾기는 그대로 쓸 수 있습니다.** "
                    f"({portal.hide_keys(e)})")

        if st.session_state.get("places_err"):
            st.warning(st.session_state.places_err)
        places = st.session_state.get("places") or []
        if places:
            st.markdown(f"**지도에서 {len(places)}곳**을 찾았습니다. "
                        "고르시면 그 주소로 다시 찾습니다.")
            pick = st.radio("지도 결과", options=list(range(len(places))),
                            format_func=lambda i: places[i].label(),
                            index=None, label_visibility="collapsed",
                            key="kakao_pick")
            if pick is not None:
                key = places[pick].search_key
                if key and st.session_state.get("kakao_done") != key:
                    st.session_state.kakao_done = key
                    run_search(key, 1)
                    st.rerun()


with st.form("search"):
    c1, c2 = st.columns([4, 1])
    keyword = c1.text_input("주소", value=st.session_state.kw,
                            placeholder="예: 구산동 314  또는  절 이름",
                            label_visibility="collapsed")
    submitted = c2.form_submit_button("찾기", width="stretch")

if submitted:
    run_search(keyword, 1)
if st.session_state.error:
    st.error(st.session_state.error)
    # 0건일 때도 「없다」가 아니라 「이름이 등록 안 됐다」일 수 있습니다.
    # 원오사(계룡)가 그랬습니다.
    if st.session_state.get("searched"):
        st.warning(
            "**절 이름으로 찾으셨다면, 이름이 등록되지 않은 절은 "
            "여기 나오지 않습니다.**"
            + _NL + _NL +
            "지도 앱에서 주소를 확인해 **주소로** 찾아 주세요."
        )
    _kakao_block()

rows = st.session_state.rows
if rows:
    total, page = st.session_state.total, st.session_state.page
    last = (total + PER_PAGE - 1) // PER_PAGE
    # 「1건」이 「유일」로 읽히면 안 됩니다. 도로명주소 검색은 **건물 이름이
    # 등록된 절만** 찾습니다. 원오사(계룡)는 이름이 등록되지 않아 부산 것 한 건만
    # 나왔고, 교수님이 지도 앱으로 직접 찾아야 했습니다.
    _by_name = any(r.name_hit for r in rows)
    if _by_name:
        st.markdown(f"**건물 이름이 등록된 {total}곳**을 찾았습니다. 아래에서 고르세요.")
        st.warning(
            "**이름이 등록되지 않은 같은 이름의 절은 여기 나오지 않습니다.**"
            + _NL + _NL +
            "찾는 절이 아니면 지도 앱에서 주소를 확인해 **주소로** 찾아 주세요."
        )
    else:
        st.markdown(f"**{total}건**을 찾았습니다. 아래에서 고르세요.")
    choice = st.radio("주소 선택", options=list(range(len(rows))),
                      format_func=lambda i: rows[i].label(),
                      index=None, label_visibility="collapsed")
    # **고르는 순간에만** 듣습니다. 예전에는 `picked is not rows[choice]` 로
    # 보았는데, 옆 지번으로 바꾸면 picked 가 목록에 없는 객체가 되어 조건이
    # 늘 참이 됩니다. 그래서 569 로 들어가도 **다음 그리기에서 569-1 로
    # 되돌아왔습니다**(작업지시 08 에서 찾음).
    if choice is not None and st.session_state.get("addr_applied") != choice:
        st.session_state.update(picked=rows[choice], bld=None, diag=None,
                                addr_applied=choice, sibs=None,
                                merge_state=None, temple_name='')

    _kakao_block()

    # 산중 사찰은 산 지번이 뒤쪽 쪽수에 묻혀 있는 일이 많습니다.
    # 검색어 끝에 "산"을 붙이면 산 지번만 올라옵니다.
    kw_now = (st.session_state.kw or "").rstrip()
    if not any(r.is_mountain for r in rows) and not kw_now.endswith("산"):
        st.markdown('<p class="hint">산중 사찰인데 목록에 <b>(산)</b> 표시가 없으면, '
                    "아래 단추를 눌러 보세요.</p>", unsafe_allow_html=True)
        if st.button("산 지번만 찾기", width="stretch"):
            run_search(kw_now + " 산", 1); st.rerun()
    if last > 1:
        a, b, c = st.columns([1, 2, 1])
        if page > 1 and a.button("← 앞으로", width="stretch"):
            run_search(st.session_state.kw, page - 1); st.rerun()
        b.markdown(f"<p style='text-align:center;padding-top:0.8rem'>{page} / {last} 쪽</p>",
                   unsafe_allow_html=True)
        if page < last and c.button("더 보기 →", width="stretch"):
            run_search(st.session_state.kw, page + 1); st.rerun()
elif submitted and not st.session_state.error:
    st.warning("찾으시는 주소가 없습니다. 동 이름만 넣고 다시 해보세요. 예: 은평구 구산동")


KST = dt.timezone(dt.timedelta(hours=9))


def _kst(ts: float):
    """시각을 한국 시각으로. 배포 서버가 UTC 라 그냥 쓰면 9시간 어긋납니다."""
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).astimezone(KST)


def running_version() -> str:
    """지금 돌고 있는 판. 커밋 번호와 날짜를 짧게.

    **왜 보여 주는가** — 올렸는데 사이트가 옛 코드인 일이 하루에 세 번
    있었습니다(2026-10-24). Streamlit 은 `app.py` 만 다시 돌리고 불러온
    모듈은 그대로 두기 때문에, 겉보기로는 새 판인지 알 수 없습니다.
    이 줄이 있으면 **열어 보는 즉시** 알 수 있습니다.

    `git` 명령을 부르지 않습니다. 배포 서버에 git 이 없을 수 있어
    `.git` 파일을 직접 읽고, 그것도 없으면 코드 파일의 시각을 씁니다.

    **시각은 한국 시각으로 못박습니다.** 배포 서버가 UTC 라 그냥 찍으면
    9시간 이르게 나옵니다(22:08 이 13:08 로). 교수님 컴퓨터에서는 맞고
    웹에서만 틀려서 더 헷갈립니다.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        head = io.open(os.path.join(here, ".git", "HEAD"),
                       encoding="utf-8").read().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            sha = io.open(os.path.join(here, ".git", ref),
                          encoding="utf-8").read().strip()
        else:
            sha = head
        when = _kst(os.path.getmtime(os.path.join(here, "app.py")))
        return f"{sha[:7]} · {when:%Y-%m-%d %H:%M} KST"
    except Exception:
        pass
    try:
        newest = max(os.path.getmtime(os.path.join(here, f))
                     for f in os.listdir(here) if f.endswith(".py"))
        return f"{_kst(newest):%Y-%m-%d %H:%M} KST 판"
    except Exception:
        return "판 알 수 없음"


def _xlsx_sig(j, year, elec_basis, gas_basis):
    """만든 엑셀이 어느 조건의 것인지. 하나라도 바뀌면 다시 만들게 합니다."""
    return (j.jibunAddr, str(year), temple_name(j), elec_basis, gas_basis,
            str(st.session_state.get("merge_state") or ""))


def _xlsx_name(j, temple, year) -> str:
    """내려받을 파일 이름에 **사찰명과 지번**을 함께 넣습니다.

    이름만 있으면 같은 절의 다른 지번을 받았을 때 파일이 겹칩니다.
    원오사는 375 와 375-3 이 다른 건물입니다.
    """
    lot = juso.jibun_text(j.lnbrMnnm, j.lnbrSlno,
                          str(j.mtYn).strip() == "1").replace(" ", "")
    bad = chr(92) + '/:*?"<>|'          # 파일 이름에 못 쓰는 글자
    safe = "".join(("_" if c in bad else c) for c in f"{temple}_{lot}")
    return f"{safe}_{year}_온실가스산정.xlsx"


def auto_temple_name(j) -> str:
    """조회한 지번에서 자동으로 뽑은 사찰명.

    건축물대장·도로명주소에 **건물명이 없는 절이 흔합니다.** 그때는
    주소가 이름 자리에 들어갑니다. 회원이 4단계에서 고쳐 넣을 수 있게
    했고, 이 함수는 그 **첫 값**입니다.
    """
    return region.named((j.bdNm or j.jibunAddr).strip(), j.jibunAddr)


def temple_name(j) -> str:
    """회원이 고쳐 넣은 이름이 있으면 그것, 없으면 자동 이름."""
    typed = (st.session_state.get("temple_name") or "").strip()
    return typed or auto_temple_name(j)


def _direct_block():
    """지번을 손으로 넣어 바로 조회 (작업지시 08 5번).

    **접어 둡니다.** 대부분은 주소로 찾으면 되고, 본번·부번을 묻는 것은
    시니어에게 판단을 요구하는 일입니다(2장). 현장에서 지번을 받아 온
    회원만 펼쳐 씁니다.

    **왜 필요한가** — 도로명주소 API 는 도로명이 붙은 지번만 들고 있어서,
    도로명이 없는 지번은 **무엇을 넣어도 안 걸립니다.** 옆 지번으로 들어갈
    수 있으면 그 길이 낫지만, 명단 69곳에서 건물이 안 잡힌 13곳 중 6곳은
    **옆 지번조차 없었습니다.** 본번이 많아 목록을 막는 곳도 있습니다.
    """
    with st.expander("자세히 — 지번을 직접 넣어 조회하기", expanded=False):
        st.markdown(
            '<p class="hint">주소로 찾아지지 않는 지번이 있습니다. '
            "도로명주소가 붙지 않은 땅은 <b>무엇을 넣어도 검색에 안 나옵니다.</b><br>"
            "<b>고지서나 지도 앱에서 지번을 확인하신 뒤</b>에 쓰십시오. "
            "지번을 모르시면 위 주소 검색을 쓰시는 편이 낫습니다.</p>",
            unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        dong = c1.text_input("법정동까지의 주소", key="dj_dong",
                             placeholder="예: 강릉시 연곡면 삼산리")
        st.caption("같은 법정동의 **아무 지번이나** 넣으시면 됩니다. "
                   "그 동네를 찾는 데만 씁니다.")
        c3, c4 = st.columns(2)
        bun = c3.text_input("번 (본번)", key="dj_bun", placeholder="예: 569")
        ji = c4.text_input("지 (부번) — 없으면 비워 두세요", key="dj_ji",
                           placeholder="예: 3")
        if not c2.button("조회", key="dj_go", width="stretch"):
            return
        if not (dong or "").strip() or not str(bun or "").strip().isdigit():
            st.warning("**법정동 주소와 번(본번)을 넣어 주세요.** "
                       "번은 숫자만 넣으시면 됩니다.")
            return
        jj = str(ji or "").strip() or "0"
        if not jj.isdigit():
            st.warning("**지(부번)는 숫자만 넣어 주세요.** 없으면 비워 두십시오.")
            return
        try:
            rows, _ = juso.search(dong.strip(), CONFM_KEY, per_page=1)
        except juso.JusoError as e:
            st.error(str(e)); return
        if not rows:
            st.warning("**그 동네를 찾지 못했습니다.** 시군구와 동·리 이름을 "
                       "넣어 보세요. 예: 강릉시 연곡면 삼산리")
            return
        st.session_state.update(
            picked=juso.sibling(rows[0], int(bun), int(jj),
                                inherit_name=False),
            bld=None, diag=None, sibs=None, merge_state=None,
            temple_name='')
        st.rerun()


_direct_block()


# ═══════════ 2단계 — 건물 정보 ═══════════

def _sibling_block(j, year):
    """같은 본번의 다른 지번 찾기 (작업지시 07 ②).

    **누를 때만** 찾고, **회원이 고릅니다.** 화면이 알아서 다른 지번으로
    넘어가지 않습니다. 지번이 너무 많으면 목록을 만들지 않고 다음 행동을
    알려 줍니다 — 청정사 본번 0001 에 89개가 있었고, 훑어 보니 남의 건물
    전기가 20여 건 잡혔습니다.
    """
    p = j.building_params()
    st.markdown('<p class="hint">절이 <b>여러 지번에 걸쳐</b> 있고 전기가 '
                "그중 <b>한 지번으로만</b> 들어오는 일이 있습니다.<br>"
                "<b>전기 자료가 없는 지번이 있으면</b> 같은 번지의 다른 "
                "지번도 찾아보세요.</p>",
                unsafe_allow_html=True)
    if st.button(f"같은 번지({int(p['bun'])})의 다른 지번도 찾아보기",
                 key="sib_go", width="stretch"):
        try:
            st.session_state.sibs = bldrgst.siblings(
                p["sigunguCd"], p["bjdongCd"], p["bun"], SERVICE_KEY,
                p["platGbCd"], p["ji"])
            st.session_state.sibs_err = ""
        except portal.PortalError as e:
            st.session_state.sibs = None
            st.session_state.sibs_err = str(e)

    if st.session_state.get("sibs_err"):
        st.error(st.session_state.sibs_err)
        return
    sibs = st.session_state.get("sibs")
    if sibs is None:
        return
    if not sibs:
        st.info("이 본번에는 건물이 있는 다른 지번이 없습니다. "
                "**고지서에 적힌 주소**로 찾아 보십시오.")
        return
    if len(sibs) > bldrgst.SIBLING_MAX:
        st.warning(
            f"같은 번지({int(p['bun'])})에 다른 지번이 **{len(sibs)}개** 있어 "
            "자동 목록을 만들지 않습니다. **남의 건물이 섞일 수 있기 "
            "때문입니다.**" + _NL + _NL +
            "**고지서에 적힌 주소나 지도 앱에서 지번을 확인해 직접 넣어 주세요.**"
        )
        return

    st.markdown(f"**건물이 있는 지번 {len(sibs)}곳**을 찾았습니다. "
                "어느 것이 이 절인지 골라 주세요.")
    keys_ = sorted(sibs)
    st.table({
        "지번": [sibs[k].get("표시") or sibs[k]["지번"] for k in keys_],
        "연면적": [f'{sibs[k]["연면적"]:,.1f} m²' for k in keys_],
        "주용도": [sibs[k]["주용도"] or "-" for k in keys_],
        "사용승인일": [sibs[k]["사용승인일"] or "-" for k in keys_],
        "동수": [f'{sibs[k]["동수"]}동' for k in keys_],
    })
    st.caption("주용도는 **건축물대장 기준**입니다. 절의 건물이 "
               "단독주택이나 근린생활시설로 올라가 있기도 합니다. "
               "주용도를 보고 전각 이름을 짐작하지 마십시오.")
    pick = st.radio("지번 선택", options=keys_,
                    format_func=lambda k: f'{sibs[k].get("표시") or sibs[k]["지번"]}'
                                          f'  ·  {sibs[k]["연면적"]:,.1f} m²',
                    index=None, label_visibility="collapsed", key="sib_pick")
    if pick is not None:
        name = sibs[pick].get("표시") or sibs[pick]["지번"]
        # **주소 검색으로 되돌아가지 않습니다**(작업지시 08 ①).
        # 강릉 삼산리 569 는 도로명주소 API 에 아예 없어서, 다시 찾으면
        # 569-1 만 돌아오고 영영 못 들어갑니다. 이미 가진 행정구역코드에
        # 번·지만 갈아 끼워 건축물대장·건물에너지를 바로 부릅니다.
        if st.button(f"**{name}** 이 지번으로 조회",
                     key="sib_apply", width="stretch"):
            st.session_state.update(
                picked=juso.sibling(j, int(p["bun"]), int(pick)),
                bld=None, diag=None, sibs=None, merge_state=None,
                temple_name='')
            st.rerun()


picked = st.session_state.picked
if picked:
    st.divider()
    st.subheader(picked.jibunAddr + ("  ·  산 지번" if picked.is_mountain else ""))
    # 옆 지번으로 들어온 것은 **도로명이 없습니다.** 지어내지 않고
    # 어디서 왔는지를 밝힙니다(작업지시 08 ②).
    _src = (picked.raw or {}).get("출처", "")
    if picked.roadAddr:
        st.markdown(f'<p class="hint">도로명 {picked.roadAddr}</p>',
                    unsafe_allow_html=True)
    elif _src:
        st.markdown(
            f'<p class="hint"><b>{_src}</b> — 기준 '
            f'{(picked.raw or {}).get("기준지번", "")}<br>'
            "이 지번에는 도로명주소가 없어 주소 검색으로는 찾을 수 없습니다. "
            "건축물대장·건물에너지는 지번으로 바로 조회합니다.</p>",
            unsafe_allow_html=True)
    if picked.name_hit:
        st.warning("""**절 이름으로 찾은 주소입니다.** 같은 이름의 다른 절일 수 있으니 위 주소가 맞는지 확인해 주세요.

명단이나 고지서에 주소가 있으면 그 주소로 찾으시는 편이 확실합니다.""")
    for w in picked.check():
        st.warning(w)

    p = picked.building_params()
    if st.session_state.bld is None:
        with st.spinner("건축물대장을 가져오는 중입니다"):
            try:
                dongs = bldrgst.fetch_dongs(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                            p["ji"], SERVICE_KEY, p["platGbCd"])
                recap = bldrgst.fetch_recap(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                            p["ji"], SERVICE_KEY, p["platGbCd"])
                jjg = bldrgst.fetch_jijigu(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                           p["ji"], SERVICE_KEY, p["platGbCd"])
                st.session_state.bld = (dongs, recap, jjg)
            except portal.PortalError as e:
                st.error(str(e)); st.stop()

    dongs, recap, jjg = st.session_state.bld
    if not dongs:
        st.warning("건축물대장에 등록된 건물이 없습니다. 미등재 전각일 수 있으니 방문해서 확인해야 합니다.")
        # **여기가 회원이 막히는 자리입니다.** 예전에는 에너지 조회를
        # 끝까지 돌려야 옆 지번 단추가 나왔는데, 건물이 없으면 조회할
        # 것도 없습니다. 현덕사가 그랬습니다 - 569-1 에는 건물이 없고
        # 바로 옆 569 에 8동 636㎡ 가 있었습니다(작업지시 08).
        st.markdown("**같은 번지의 다른 지번에 건물이 있을 수 있습니다.**")
        _sibling_block(picked, None)
    else:
        s = bldrgst.summarize(dongs)
        zones = bldrgst.restricted(jjg)
        st.markdown("#### 건물 정보")
        c1, c2, c3 = st.columns(3)
        c1.metric("동 수", f"{s['count']}동")
        c2.metric("연면적", f"{s['total_area']:,.0f} m²")
        c3.metric("대지면적", f"{recap['platArea']:,.0f} m²" if recap else "—")

        st.table({
            "동": [d.name(i) for i, d in enumerate(dongs, 1)],
            "연면적": [f"{d.totArea:,.1f} m²" for d in dongs],
            "주용도": [d.mainPurpsCdNm or "-" for d in dongs],
            "구조": [d.strctCdNm or "-" for d in dongs],
            "지붕": [d.roofCdNm or "-" for d in dongs],
            "구분": [d.kind for d in dongs],
            "태양광": [bldrgst.solar_label(d, bool(zones)) for d in dongs],
        })
        bits = [f'전통 {s["trad_count"]}동 {s["trad_area"]:,.0f} m²']
        if s["check_count"]:
            bits.append(f'확인 필요 {s["check_count"]}동 {s["check_area"]:,.0f} m²')
        bits.append(f'신식 {s["modern_count"]}동 {s["modern_area"]:,.0f} m²')
        if s["parking_area"]:
            bits.append(f'옥내 주차장 {s["parking_area"]:,.0f} m²')
        if recap and recap["totPkngCnt"]:
            bits.append(f'주차 {recap["totPkngCnt"]}대')
        st.markdown('<p class="hint">' + " · ".join(bits) + "</p>",
                    unsafe_allow_html=True)

        # 참고 정보는 파란색, 손봐야 할 것은 노란색으로 나눕니다.
        # 둘 다 노란색이면 모든 상자가 문제로 읽힙니다.
        if s["trad_count"]:
            st.info("목조 전각은 태양광 설치 대상에서 빠집니다. 구조와 지붕은 "
                    "건축물대장 기준이므로 현장에서 확인해 주세요.")
        if s["check_count"]:
            st.info(
                "**구조는 목재가 아닌데 지붕만 기와·초가인 동이 "
                f"{s['check_count']}동** 있습니다." "  지붕에 판을 올릴 수 "
                "있는 경우가 많아 「확인 필요」로 두었습니다. "
                "현장에서 보고 정해 주세요."
            )
        if s["parking_area"]:
            st.info(
                f"연면적에 **옥내 주차장 {s['parking_area']:,.0f} m²** 가 "
                "들어 있습니다. 면적당 에너지를 낼 때는 이것을 뺀 "
                f"**{s['area_excl_parking']:,.0f} m²** 로 나눕니다. "
                "통계의 원단위가 주차장을 뺀 연면적 기준이기 때문입니다."
            )

        for m in bldrgst.checks(dongs, recap):
            st.warning(m)
        if jjg:
            msg = "용도지역·구역: " + " / ".join(jjg)
            if zones:
                st.warning(
                    msg + "\n\n**" + " · ".join(zones) + "** 이 걸려 있어 태양광은 "
                    "「협의 필요」로 표시했습니다. **못 하는 것이 아니라 절차가 "
                    "있는 것**입니다. 규제 해당 여부는 관할 지자체 질의로만 "
                    "확정됩니다."
                )
            else:
                st.info(msg + "\n\n규제 해당 여부는 관할 지자체 질의로만 확정됩니다.")




def _merge_cols() -> dict:
    """묶기 결과를 사찰기록 열 셋으로. 안 묶었으면 빈칸입니다."""
    ms = st.session_state.get("merge_state")
    if not ms or len(ms["rows"]) < 2:
        return {}
    return {
        "묶은 지번": ", ".join(r["지번"] for r in ms["rows"]),
        "묶음 근거": ms["basis"],
        "묶은 연면적(m2)": f'{ms["area"]:.1f}',
    }


def _merge_rows(picked, es, gs):
    """지금 지번 한 줄. 묶기의 첫 줄이 됩니다."""
    bld = st.session_state.bld
    d = bldrgst.summarize(bld[0]) if (bld and bld[0]) else {}
    return {"지번": picked.jibunAddr, "연면적": d.get("total_area", 0.0),
            "주차장제외": d.get("area_excl_parking", 0.0),
            "전기": es["total"], "가스": gs["total"],
            "동수": d.get("count", 0), "전통": d.get("trad_count", 0)}


def _merge_block(picked, year, es, gs, use):
    """한 절을 여러 지번으로 묶기 (작업지시 07 ③).

    판정은 **도구가 정합니다.** 회원이 고르는 것은 「고지서로 확인했다」
    하나뿐입니다.

      모든 지번에 전기 기록       -> 공개자료_전지번  (합친 값 낸다)
      전기 0 인 지번 + 고지서 확인 -> 고지서확인      (낸다)
      전기 0 인 지번 + 확인 안 됨  -> 모름           (내지 않는다)
    """
    with st.expander("이 절에 지번 더하기 (여러 지번에 걸친 절)"):
        st.markdown('<p class="hint">절이 여러 지번에 걸쳐 있으면 더해 주세요. '
                    "<b>전기가 잡히는 지번과 건물이 있는 지번이 다를 수 있습니다.</b><br>"
                    "더한 지번의 전기는 <b>잰 값의 합</b>이라 늘 맞습니다. "
                    "다만 <b>면적당 값</b>은 한전 계약이 하나여야 뜻이 있습니다.</p>",
                    unsafe_allow_html=True)

        extra = st.session_state.get("merged") or []
        c1, c2 = st.columns([3, 1])
        add = c1.text_input("더할 지번", placeholder="예: 충청남도 계룡시 엄사면 엄사리 375",
                            label_visibility="collapsed", key="merge_add")
        if c2.button("더하기", key="merge_go", width="stretch") and add.strip():
            try:
                rows_, _ = juso.search(add.strip(), CONFM_KEY)
                j2 = rows_[0]
                p2 = j2.building_params()
                dongs2 = bldrgst.fetch_dongs(p2["sigunguCd"], p2["bjdongCd"],
                                             p2["bun"], p2["ji"], SERVICE_KEY,
                                             p2["platGbCd"])
                d2 = bldrgst.summarize(dongs2)
                e2 = bldengy.fetch_year(p2["sigunguCd"], p2["bjdongCd"], p2["bun"],
                                        p2["ji"], year, SERVICE_KEY,
                                        plat_gb=p2["platGbCd"],
                                        old_sigungu=_old_sgg(p2["sigunguCd"]),
                                        place_must=_place(j2.jibunAddr))
                extra.append({
                    "지번": j2.jibunAddr,
                    "연면적": d2["total_area"],
                    "주차장제외": d2["area_excl_parking"],
                    "전기": sum(e2["elec"].values()),
                    "가스": sum(e2["gas"].values()),
                    "동수": d2["count"], "전통": d2["trad_count"]})
                st.session_state.merged = extra
                st.rerun()
            except (juso.JusoError, portal.PortalError) as ex:
                st.error(str(ex))
            except IndexError:
                st.error("그 지번을 찾지 못했습니다. 지번을 다시 확인해 주세요.")

        if not extra:
            return

        rows_all = [_merge_rows(picked, es, gs)] + extra
        st.table({
            "지번": [r["지번"] for r in rows_all],
            "연면적": [f'{r["연면적"]:,.1f} m²' for r in rows_all],
            "전기(kWh)": [f'{r["전기"]:,.0f}' for r in rows_all],
            "가스(kWh)": [f'{r["가스"]:,.0f}' for r in rows_all],
        })
        if st.button("묶기 지우기", key="merge_clear"):
            st.session_state.merged = []
            st.rerun()

        bill = st.checkbox(
            "고지서로 **한전 계약이 하나**임을 확인했습니다",
            key="bill_ok",
            help="통합청구로 고지서가 한 장이어도 계약이 둘일 수 있습니다. "
                 "고지서 안에 계약별로 따로 적혀 있습니다. "
                 "외벽 계량기 개수로는 알 수 없습니다.")
        basis = store.merge_basis([r["전기"] for r in rows_all], bill)
        area = sum(r["주차장제외"] for r in rows_all)
        elec = sum(r["전기"] for r in rows_all)
        gas = sum(r["가스"] for r in rows_all)

        st.markdown(f"**합계 — 연면적 {sum(r['연면적'] for r in rows_all):,.1f} m² · "
                    f"전기 {elec:,.0f} kWh · 가스 {gas:,.0f} kWh**")
        st.caption(f"묶음 판정: **{basis}**")

        if not store.merged_ratio_ok(basis):
            st.warning(
                "**합친 면적당 값을 내지 않았습니다.**" + _NL + _NL +
                "전기가 0 인 지번이 끼어 있어, 한전 계약이 하나인지 "
                "공개자료로는 가릴 수 없습니다. 계약이 둘인데 면적만 합치면 "
                "값이 실제보다 **낮게** 나옵니다." + _NL + _NL +
                "**고지서의 고객번호가 몇 개인지, 각각의 사용 장소 주소가 "
                "어디인지** 확인해 주세요. 확인되면 위 칸을 체크하십시오."
            )
        else:
            u2 = em.area_use(elec, gas, area, region.of(picked.jibunAddr))
            if u2.has_ratio:
                st.success(
                    f"묶은 면적당 에너지 **{u2.per:,.0f} kWh/m²** — "
                    f"{region.label(picked.jibunAddr)} 사찰 원단위 {u2.base} 대비 "
                    f"**{u2.ratio:.2f}배**  ({basis})")
            else:
                st.info(f"묶은 전기만 **{u2.elec_per:,.0f} kWh/m²** — {u2.note}")

        st.session_state.merge_state = {
            "basis": basis, "rows": rows_all, "area": area,
            "elec": elec, "gas": gas}


# ═══════════ 3단계 — 개략 진단 ═══════════
if picked:
    st.divider()
    st.markdown("#### 에너지 진단")
    this_year = dt.date.today().year
    # 건물에너지 API 는 **2020년부터** 줍니다(2026-10-24 봉은사로 확인,
    # 2015~2019 전부 0). 다만 지역·건물마다 들어온 시점이 다릅니다 —
    # 서울 두 곳은 2020년부터 12달이 차 있는데 금산사·실상사는 2023년까지
    # 사실상 비어 있었습니다. 그래서 해를 넓게 열되, 받아 본 뒤 12달이
    # 안 되면 그 자리에서 밝힙니다(아래 months 경고).
    ENERGY_FIRST_YEAR = 2020
    years = list(range(this_year - 1, ENERGY_FIRST_YEAR - 1, -1))
    c1, c2 = st.columns(2)
    year = c1.selectbox("조회할 해", years)
    ttype = c2.selectbox("사찰 유형", ["도심", "산중"], index=1 if picked.is_mountain else 0)

    st.markdown('<p class="hint">전기와 가스는 <b>지번 한 곳</b>을 기준으로 찾습니다. '
                "전기요금은 전각마다 따로 나오지 않고 <b>특정 건물로 묶여</b> 나오기 때문에, "
                "사찰 전체가 이 지번 하나에 잡히지 않을 수 있습니다.<br>"
                "<b>고지서가 있으시면, 고지서에 적힌 주소로 찾으시는 편이 가장 정확합니다.</b>"
                "</p>", unsafe_allow_html=True)

    if st.button("자료 가져오기  (30초쯤 걸립니다)", width="stretch"):
        bar = st.progress(0.0, text="시작합니다")
        p = picked.building_params()
        try:
            data = bldengy.fetch_year(
                p["sigunguCd"], p["bjdongCd"], p["bun"], p["ji"], year, SERVICE_KEY,
                plat_gb=p["platGbCd"],
                # 통합된 광주·전남은 건물에너지가 옛 시군구코드에만 있습니다.
                old_sigungu=_old_sgg(p["sigunguCd"]),
                place_must=_place(picked.jibunAddr),
                progress=lambda d, t, lbl: bar.progress(d / t, text=f"{lbl} ({d}/{t})"))
        except portal.PortalError as e:
            bar.empty(); st.error(str(e)); st.stop()
        bar.empty()
        st.session_state.diag = (data, ttype, year)

    d = st.session_state.diag
    if d:
        data, ttype, year = d
        es, gs = bldengy.summarize(data["elec"]), bldengy.summarize(data["gas"])
        r = em.diagnose(es["total"], gs["total"], ttype)
        lvl, msg = em.confidence(es["total"], gs["total"])

        if es["total"] == 0 and gs["total"] == 0:
            _sibling_block(picked, year)
            st.error(f"""**{picked.jibunAddr}** 의 {year}년 자료가 없습니다.

이 지번에 없을 뿐, 전기가 **다른 지번으로 잡혀 있을 수 있습니다.**
고지서에 적힌 주소로 다시 찾아 보세요. 해를 바꿔 보셔도 됩니다.

그래도 없으면 공개자료가 없는 사찰입니다. 방문해서 고지서를 받아야 합니다.""")
        else:
            st.markdown(f"##### {year}년 개략 진단")
            k1, k2, k3 = st.columns(3)
            k1.metric("공개자료 배출량", f"{r.subtotal_t:,.1f} t")
            k2.metric("국민 환산", f"{r.people:,.1f}명분")
            k3.metric("태양광 필요용량", f"{r.solar_kw:,.0f} kW")
            st.caption("전기와 도시가스만 더한 값입니다. " + em.UNCOVERED_TEXT)

            st.info(f"이 값은 **{picked.jibunAddr}** 한 지번에 잡힌 것만 더한 것입니다. "
                    "사찰 전체가 아닐 수 있습니다. "
                    "고지서에 적힌 주소가 이와 다르면 그 주소로 다시 찾아 주세요.")

            # 옛 시군구코드로 받아 왔으면 밝힙니다. 참고이지 문제가 아니라
            # 파란 상자입니다(7장 「참고는 파란색」).
            if data.get("code") == bldengy.OLD_CODE:
                st.info(f"""이 지역은 행정구역이 통합되어 **건물에너지 자료가
통합 전 코드에 남아 있습니다.** 새 코드로는 열두 달이 모두 0 이어서,
**통합 전 시군구코드({data.get('sigungu', '')})로 다시 받은 값**입니다.

받은 자료의 주소에 **{_place(picked.jibunAddr)}** 가 들어 있는 것만 썼습니다.
건물 정보(동수·연면적)는 지금 코드로 받은 것입니다.""")

            dropped = data.get("dropped", 0)
            if dropped:
                st.warning(f"""같은 번지에서 대지구분이 다른 자료 **{dropped}건을 제외**했습니다.

이 사찰의 전기가 그쪽에 물려 있을 수 있습니다. 현장에서 고지서 주소를 확인해 주세요.""")

            # ── 면적당 에너지 — 그 지역 사찰 원단위와 견줍니다 ──
            #
            # 옛 방식(전기만 / 고정 200)은 폐기되었습니다. 통계의 원단위는
            # 전기+가스 합을 **주차장 뺀 연면적**으로 나눈 **중간값**입니다.
            bld = st.session_state.bld
            area = area_gross = 0.0
            use = em.AreaUse()
            if bld and bld[0]:
                ds0 = bldrgst.summarize(bld[0])
                area_gross = ds0["total_area"]
                area = ds0["area_excl_parking"]
                use = em.area_use(
                    es["total"], gs["total"], area,
                    region.of(picked.jibunAddr),
                    parking_area=ds0["parking_area"],
                    trad_count=ds0["trad_count"],
                )
            if use.area:
                reg = region.label(picked.jibunAddr)
                if use.suspect:
                    # 「높다」가 아니라 「못 믿는다」입니다. 배수를 내지 않습니다.
                    st.warning(
                        f"**배수를 내지 않았습니다 — {em.SUSPECT_NOTE}**"
                        + _NL + _NL +
                        f"전통 전각이 한 동도 없는데 면적당 에너지가 "
                        f"{use.per:,.0f} kWh/m² 로 지역 원단위({use.base})의 "
                        f"{use.per / use.base:.1f}배입니다. "
                        + em.SUSPECT_TEXT
                    )
                elif use.has_ratio:
                    # 배수(효율)와 총량(규모)을 **나란히** 둡니다.
                    # 배수만 보면 작은 절부터 가게 됩니다.
                    q1, q2 = st.columns(2)
                    q1.metric(f"면적당 에너지 ({reg} 원단위 {use.base} 대비)",
                              f"{use.per:,.0f} kWh/m²", f"{use.ratio:.2f}배",
                              delta_color="off")
                    q2.metric("연간 총에너지", f"{use.total_kwh:,.0f} kWh")
                    st.caption(em.EUI_NOTE + "  출처: " + em.EUI_SOURCE)
                else:
                    st.markdown(
                        f"**전기만 {use.elec_per:,.0f} kWh/m²** · "
                        f"연간 전기 **{use.elec_kwh:,.0f} kWh** — "
                        f"배수와 총에너지는 내지 않았습니다. {use.note}"
                    )
                    if use.note == em.NO_HEAT_NOTE:
                        st.warning(
                            "**도시가스가 0 입니다.** 산중 사찰은 LPG·등유·화목으로 "
                            "난방하는데 공개자료에는 그 연료가 없습니다. 분자에 난방이 "
                            "통째로 빠지므로 배수를 내면 실제보다 낮게 나옵니다."
                            + _NL + _NL +
                            "위 전기 사용량은 **실제로 잰 값**입니다. 4단계에 LPG·등유를 "
                            "넣으시면 그때 합산해 배수를 냅니다."
                        )
                st.caption(
                    f"분모 {use.area:,.0f} m²"
                    + (f" (연면적 {area_gross:,.0f} - 옥내 주차장 {use.parking_area:,.0f})"
                       if use.parking_area else " (옥내 주차장 없음)")
                    + " · 분자 " + em.EUI_NUMERATOR_NOTE
                )

            if es["ratio"]:
                st.markdown(
                    f"**난방 부담 지표 {es['ratio']:.2f}배** — 전기를 가장 많이 쓴 달"
                    f"({int(es['max_ym'][4:])}월)이 가장 적게 쓴 달({int(es['min_ym'][4:])}월)의 "
                    f"{es['ratio']:.1f}배입니다. "
                    + ("난방 개선 여지가 큽니다." if es["ratio"] >= 2.5 else "난방 부담은 크지 않습니다."))

            # 해에 따라 자료가 덜 들어와 있습니다. 2020~2022 는 지역마다
            # 편차가 큽니다(금산사·실상사는 2023년까지 사실상 비어 있었음).
            #
            # **빠진 달을 두 갈래로 나눠 알립니다**(bldengy.gaps).
            # 둘은 다음 행동이 **정반대**라 한 문구로 묶으면 틀린 안내가
            # 됩니다. 2021년 10월 전기처럼 출처에 빠진 달은 해를 바꿔도
            # 그대로인데, 예전 문구는 「최근 해로 바꿔 보십시오」였습니다.
            if es["total"] and es["months"] < 12:
                def _months(yms):
                    return ", ".join(f"{int(y[4:])}월" for y in yms)

                if es.get("holes"):
                    st.warning(
                        f"**{year}년 {_months(es['holes'])} 전기 자료가 "
                        "출처에 빠져 있습니다.**"
                        + _NL + _NL +
                        "앞뒤 달은 차 있는데 그 달만 비었습니다. "
                        "**그 절이 전기를 안 쓴 것이 아닙니다.** "
                        f"연간 합계({es['total']:,.0f} kWh)가 그만큼 적게 "
                        "잡혀 있습니다."
                        + _NL + _NL +
                        "**해를 바꿔도 이 달은 채워지지 않습니다.** "
                        "그대로 쓰시되, 다른 해와 견주실 때만 한 달이 빈 것을 "
                        "염두에 두십시오."
                    )
                if es.get("ends"):
                    st.warning(
                        f"**{year}년은 전기 자료가 {es['months']}달치뿐입니다.**"
                        f" ({_months(es['ends'])}이 비어 있습니다)"
                        + _NL + _NL +
                        "그 해에 자료가 덜 들어온 것이지 전기를 안 쓴 것이 "
                        "아닙니다. **연간 값으로 보면 적게 나옵니다.** "
                        "최근 해로 바꿔 보십시오."
                    )

            if es["total"]:
                st.caption("월별 전기 사용량 (kWh)")
                st.bar_chart({f"{k[4:]}월": v for k, v in sorted(data["elec"].items())})

            with st.expander("자세히 보기"):
                st.table({
                    "항목": ["전기 사용량", "가스 사용량", "가스 환산",
                             "전기 배출량", "가스 배출량", "공개자료 소계",
                             "전력 기준", "도시가스 기준", "GWP"],
                    "값": [f"{es['total']:,.0f} kWh ({es['months']}개월)",
                           f"{gs['total']:,.0f} kWh ({gs['months']}개월)",
                           f"{r.gas_nm3:,.1f} Nm³",
                           f"{r.elec_t:,.2f} t", f"{r.gas_t:,.2f} t",
                           f"{r.subtotal_t:,.2f} t",
                           f"{r.elec_ef} kgCO2eq/kWh ({r.elec_basis})",
                           r.gas_basis, r.gwp]})

            (st.success if lvl == "높음" else st.warning)(f"신뢰도 {lvl} — {msg}")

            if not SHARE and st.button("이 사찰 기록에 저장하기", width="stretch"):
                pp = picked.building_params()
                dongs = bld[0] if bld else []
                jjg = bld[2] if bld else []
                ds = bldrgst.summarize(dongs) if dongs else {}
                try:
                    rows, replaced = store.save({
                        "사찰": temple_name(picked),
                        "지번주소": picked.jibunAddr,
                        "도로명주소": picked.roadAddr,
                        "조회연도": str(year),
                        "Scope1(t)": f"{r.gas_t:.2f}",
                        "Scope2(t)": f"{r.elec_t:.2f}",
                        "공개자료 배출량(t)": f"{r.subtotal_t:.2f}",
                        "전기(kWh)": f"{es['total']:.0f}",
                        "가스(kWh)": f"{gs['total']:.0f}",
                        "면적당 전기(kWh/m2)": (f"{use.per:,.0f}" if use.per
                                                else (f"{use.elec_per:,.0f}"
                                                      if use.elec_per else "")),
                        "난방부담 지표": f"{es['ratio']:.2f}" if es.get("ratio") else "",
                        "동수": str(ds.get("count", "")),
                        "연면적(m2)": f"{area:.1f}" if area else "",
                        "전통 동수": str(ds.get("trad_count", "")),
                        "신식 동수": str(ds.get("modern_count", "")),
                        "태양광 필요용량(kW)": f"{r.solar_kw:.0f}",
                        "신뢰도": lvl,
                        # 되살렸습니다(지시 05 6번).
                        # 전통 0동 + 배수 3.0 초과일 때만 붙습니다.
                        "대장누락 의심": "예" if use.suspect else "",
                        "제외된 자료(건)": str(data.get("dropped", 0)),
                        "전력 기준": r.elec_basis,
                        "도시가스 기준": r.gas_basis,
                        "GWP": r.gwp,
                        "용도지역": " / ".join(jjg),
                        "시군구": pp["sigunguCd"], "법정동": pp["bjdongCd"],
                        "번": pp["bun"], "지": pp["ji"], "대지구분": pp["platGbCd"],
                        # 옆 지번에서 들어왔으면 그 사실을 남깁니다. 이 지번은
                        # 도로명주소가 없어 **주소로는 다시 못 찾습니다**.
                        "조회경로": (picked.raw or {}).get("출처", ""),
                        **_merge_cols(),
                    })
                except store.StoreError as e:
                    st.error(str(e)); st.stop()
                st.success(
                    ("같은 지번·같은 해 기록을 **새것으로 바꿨습니다.**"
                     if replaced else "기록에 **더했습니다.**")
                    + f" 지금까지 {len(rows)}곳입니다.")
            _merge_block(picked, year, es, gs, use)

            st.markdown('<p class="hint"><b>아직 모르는 것</b> — 계약전력, LPG·등유·화목, '
                        "차량, 상수도. 모두 방문해서 확인해야 합니다.</p>", unsafe_allow_html=True)

# ═══════════ 4단계 — 정식 산정 (엑셀 서식) ═══════════
if picked and st.session_state.diag:
    data, ttype, year = st.session_state.diag
    es = bldengy.summarize(data["elec"])
    gs = bldengy.summarize(data["gas"])

    st.divider()
    st.markdown("#### 정식 산정 — 엑셀 서식 만들기")
    st.markdown('<p class="hint">「온실가스 배출량 산정 실무용 템플릿」의 활동량 칸을 '
                "채워 드립니다. 엑셀에서 열면 <b>활동량 x 발열량 x 배출계수 x 산화계수 "
                "x GWP</b> 5단계가 그대로 계산됩니다.</p>", unsafe_allow_html=True)

    # 건물명이 없는 절이 흔합니다. 그때는 주소가 이름 자리에 들어가
    # 엑셀 표지에 「충청남도 계룡시 …」처럼 찍힙니다. 고쳐 넣을 수 있게
    # 했습니다. **비워 두면 자동 이름을 그대로 씁니다**(2장 - 판단을
    # 요구하지 않는다). 기록에 저장할 때도 같은 이름이 들어갑니다.
    _auto = auto_temple_name(picked)
    st.text_input("사찰명 — 문서에 적힐 이름", key="temple_name",
                  placeholder=_auto)
    if not (st.session_state.get("temple_name") or "").strip():
        if picked.bdNm:
            st.caption(f"비워 두시면 **{_auto}** 로 적습니다.")
        else:
            st.caption(f"이 지번에는 **건물명이 없어** 주소로 적힙니다 "
                       f"— {_auto}. 절 이름을 넣어 주시면 그것으로 바뀝니다.")

    # 계수 고르기는 접어 둡니다. 기본값이 옳고 대부분 손댈 일이 없는데
    # 눈에 띄는 자리에 두면 시니어에게 판단을 요구하는 셈이 됩니다(2장).
    with st.expander("자세한 설정 — 배출계수 고르기", icon=":material/tune:"):
        st.caption(f"그냥 두셔도 됩니다. 기본값은 전력 {em.ELEC_DEFAULT}, "
                   f"도시가스 {em.GAS_BASIS_DEFAULT} 입니다.")
        b1, b2 = st.columns(2)
        elec_basis = b1.selectbox("전력 배출계수", list(em.ELEC_EF),
                                  index=list(em.ELEC_EF).index(em.ELEC_DEFAULT))
        gas_basis = b2.selectbox("도시가스 환산기준", list(em.GAS_BASIS),
                                 index=list(em.GAS_BASIS).index(em.GAS_BASIS_DEFAULT))

        if elec_basis != em.ELEC_DEFAULT:
            st.warning(
                f"**이 선택은 화면에만 적용됩니다.** 내려받으실 엑셀은 서식에 박힌 "
                f"{em.ELEC_EF[em.ELEC_DEFAULT]}({em.ELEC_DEFAULT})로 계산합니다. "
                "서식의 수식은 고칠 수 없기 때문입니다. "
                "기존 다섯 사찰과 견주어 보실 때만 쓰시고, 엑셀로 내실 때는 "
                f"{em.ELEC_DEFAULT}로 되돌려 주세요."
            )
        if gas_basis != em.GAS_BASIS_DEFAULT:
            st.caption("도시가스 환산기준은 고지서로 최종 확인이 남아 있습니다. "
                       "고지서에 kWh 와 Nm³ 이 함께 찍혀 있으면 나눠 보아 확정됩니다. "
                       "이 선택은 엑셀에도 그대로 반영됩니다.")

    st.markdown('<p class="hint"><b>현장 조사값</b> — 방문해서 확인한 값만 넣으세요. '
                "모르면 비워 두시면 됩니다(0).</p>", unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns(5)
    lpg = f1.number_input("LPG-프로판 (kg)", min_value=0.0, value=0.0, step=10.0)
    kero = f2.number_input("등유 (L)", min_value=0.0, value=0.0, step=10.0)
    wood = f3.number_input("화목·장작 (kg)", min_value=0.0, value=0.0, step=50.0)
    gaso = f4.number_input("휘발유 (L)", min_value=0.0, value=0.0, step=10.0)
    dies = f5.number_input("경유 (L)", min_value=0.0, value=0.0, step=10.0)
    if wood > 0:
        b = em.burn("화목(장작)", wood)
        st.caption(
            f"화목 {wood:,.0f} kg — 생물기원 CO₂ {b.bio_co2_kg:,.0f} kg 은 "
            f"**합계에서 뺍니다**(고시 제18조). CH₄·N₂O {b.ar5_t * 1000:,.0f} kg "
            "만 합계에 들어갑니다. 엑셀에도 따로 적힙니다."
        )

    st.markdown('<p class="hint"><b>자가 태양광</b> — 있으면 넣어 주세요. '
                "회피 배출량이 참고로 계산되고 합계에는 넣지 않습니다.</p>",
                unsafe_allow_html=True)
    s1, s2 = st.columns(2)
    solar = s1.number_input("발전량 (kWh)", min_value=0.0, value=0.0, step=100.0)
    solar_self = s2.number_input("그중 자가소비량 (kWh)", min_value=0.0,
                                 value=0.0, step=100.0)

    # 도시가스가 0 이라 3단계에서 배수를 못 냈던 사찰도, 여기에 난방 연료를
    # 넣으면 그때 배수를 냅니다(지시 04 3번).
    # **휘발유·경유는 더하지 않습니다.** 차량 연료라 건물 에너지가 아닙니다.
    _bld = st.session_state.bld
    if _bld and _bld[0] and gs["total"] <= 0 and (lpg > 0 or kero > 0 or wood > 0):
        _ds = bldrgst.summarize(_bld[0])
        _heat = (em.fuel_kwh("LPG-프로판(LPG1호)", lpg)
                 + em.fuel_kwh("등유(Kerosene)", kero)
                 + em.fuel_kwh("화목(장작)", wood))
        _u = em.area_use(
            es["total"], 0.0, _ds["area_excl_parking"],
            region.of(picked.jibunAddr),
            parking_area=_ds["parking_area"], other_kwh=_heat,
        )
        if _u.has_ratio:
            st.success(
                f"현장 조사값을 더해 배수를 냈습니다 — 면적당 에너지 "
                f"**{_u.per:,.0f} kWh/m²**, {region.label(picked.jibunAddr)} 사찰 "
                f"원단위 {_u.base} 대비 **{_u.ratio:.2f}배**"
                + _NL + _NL +
                f"난방 연료 {_heat:,.0f} kWh 를 전기 {es['total']:,.0f} kWh 에 "
                "더한 값입니다. 차량 연료(휘발유·경유)는 건물 에너지가 아니라 "
                "빼고 셈했습니다."
            )

    if st.button("엑셀 서식 만들기", width="stretch"):
        extra = []
        for fuel, qty, scope in (("LPG-프로판(LPG1호)", lpg, "고정연소"),
                                 ("등유(Kerosene)", kero, "고정연소"),
                                 ("화목(장작)", wood, "고정연소"),
                                 ("휘발유(Gasoline)", gaso, "이동연소"),
                                 ("경유(Diesel)", dies, "이동연소")):
            if qty > 0:
                extra.append(tpl.Activity(fuel, float(qty), scope=scope))

        # 묶었으면 **지번별 전기 합계**로 나갑니다. 잰 값의 합이라
        # 한전 계약 수와 상관없이 맞습니다(작업지시 07 ③).
        _ms = st.session_state.get("merge_state")
        _elec = _ms["elec"] if _ms and len(_ms["rows"]) > 1 else es["total"]
        _gas = _ms["gas"] if _ms and len(_ms["rows"]) > 1 else gs["total"]
        # **묶지 않았어도 한 줄은 냅니다.** 예전에는 묶었을 때만 채워서,
        # 지번 하나만 조회하면 ⑧조회근거 14행에 지번만 찍히고 연면적·전기·
        # 동수가 통째로 비었습니다(2026-10-24 발견). 묶기는 드문 일이라
        # **보통의 조회가 늘 빈 줄을 내고 있었습니다.**
        _rows = (_ms["rows"] if _ms and len(_ms["rows"]) > 1
                 else [_merge_rows(picked, es, gs)])
        _srcs = [{"지번": r["지번"], "연면적": round(r["연면적"], 1),
                  "주차장제외": round(r["주차장제외"], 1),
                  "전기": round(r["전기"]), "가스": round(r["가스"]),
                  "동수": r["동수"], "전통": r["전통"]}
                 for r in _rows]
        _basis = _ms["basis"] if _ms and len(_ms["rows"]) > 1 else ""

        temple = temple_name(picked)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, f"{temple}_{year}_온실가스산정.xlsx")
                path, acts = tpl.from_diagnosis(
                    out, temple, year, _elec, _gas,
                    gas_basis=gas_basis, extra=extra,
                    road_addr=picked.roadAddr, jibun_addr=picked.jibunAddr,
                    route=(picked.raw or {}).get("출처", ""),
                    solar_kwh=solar, solar_self_kwh=solar_self,
                    sources=_srcs, merge_basis=_basis,
                    energy_code=(st.session_state.diag[0].get("code", "")
                                 if st.session_state.get("diag") else ""))
                blob = io.open(path, "rb").read()
        except tpl.TemplateError as e:
            st.error(str(e)); st.stop()

        pv = tpl.preview(_elec, acts, elec_basis=elec_basis)
        st.session_state.xlsx = (blob, _xlsx_name(picked, temple, year),
                                 pv, acts, _xlsx_sig(picked, year,
                                                     elec_basis, gas_basis))

    # **만든 뒤에 다른 절로 넘어갔으면 보여 주지 않습니다.**
    #
    # 예전에는 `picked` 가 바뀌어도 `xlsx` 가 세션에 그대로 남아,
    # **다른 절을 조회해도 앞 절의 엑셀이 계속 내려왔습니다**
    # (2026-10-24, 배포판에서 교수님이 겪으심). 서버를 다시 띄우면
    # 세션이 지워져 없어지는 탓에 「옛 코드」처럼 보였습니다.
    #
    # 지우는 자리를 일일이 기억하는 대신, **만들 때의 조건을 함께
    # 적어 두고 지금 조건과 다르면 버립니다.** 조건이 하나라도
    # 바뀌면 저절로 맞습니다.
    x = st.session_state.xlsx
    if x and (len(x) < 5 or x[4] != _xlsx_sig(picked, year,
                                              elec_basis, gas_basis)):
        st.session_state.xlsx = None
        x = None
    if x:
        blob, fname, pv, acts, _ = x
        st.markdown("##### 미리보기")
        if pv["rows"]:
            st.table({
                "연료": [r["연료"] for r in pv["rows"]],
                "구분": [r["구분"] for r in pv["rows"]],
                "활동량": [r["활동량"] for r in pv["rows"]],
                "발열량": [r["발열량"] for r in pv["rows"]],
                "배출량": [r["배출량"] for r in pv["rows"]],
            })
        else:
            st.caption("연료 활동량이 없습니다. 전력만 들어갑니다.")

        s1, s2, s3 = st.columns(3)
        s1.metric("Scope 1 (연료)", f"{pv['scope1_t']:,.2f} t")
        s2.metric("Scope 2 (전력)", f"{pv['scope2_t']:,.2f} t")
        s3.metric("합계", f"{pv['total_t']:,.2f} t")
        st.caption(f"전력 {pv['elec_basis']} · GWP {pv['gwp']} 기준. "
                   "상수도는 Scope 3 이라 이 서식에 들어가지 않습니다.")

        with st.expander("산식 보기 (5단계가 어떻게 계산되는지)"):
            for r in pv["rows"]:
                st.markdown(f"**{r['연료']}**")
                st.code(r["산식"], language=None)
            st.markdown("**전력**")
            st.code(f"{es['total']:,.0f} kWh x {em.ELEC_EF[pv['elec_basis']]}"
                    f" = {pv['scope2_t']:,.2f} t", language=None)

        st.download_button("엑셀 내려받기", data=blob, file_name=fname,
                           mime="application/vnd.openxmlformats-officedocument."
                                "spreadsheetml.sheet",
                           width="stretch")
        st.caption("내려받은 파일을 엑셀에서 열면 ⑥종합요약에 합계가 나옵니다. "
                   "합계가 0 이면 연료명이 서식과 다른 것이니 알려 주세요.")


# ═══════════ 5·6·7단계 — 모임 안에서만 보는 부분 ═══════════
# 남에게 보여주는 판에서는 통째로 감춥니다. 까닭은 _share_mode() 를 보십시오.
saved = []
if not SHARE:
    # ═══════════ 5단계 — 사찰 목록 (쌓아서 비교) ═══════════
    st.divider()
    try:
        saved = store.load()
    except store.StoreError as e:
        st.error(str(e))
        saved = []

    st.markdown(f"#### 저장된 사찰 — {len(saved)}곳")

    if not saved:
        st.markdown('<p class="hint">아직 저장된 사찰이 없습니다. 위에서 진단한 뒤 '
                    "<b>[이 사찰 기록에 저장하기]</b> 를 누르시면 여기에 쌓입니다.<br>"
                    "여러 곳이 쌓이면 서로 견주어 볼 수 있습니다.</p>",
                    unsafe_allow_html=True)
    else:
        b = store.benchmark(saved)
        m1, m2, m3 = st.columns(3)
        m1.metric("사찰 수", f"{b['count']}곳")
        m2.metric("배출량 평균", f"{b['ton_avg']:,.1f} t" if b["ton_avg"] else "—")
        m3.metric("면적당 전기 평균",
                  f"{b['per_avg']:,.0f} kWh/m²" if b["per_avg"] else "—")

        bits = []
        if b["ton_n"]:
            bits.append(f"배출량은 {b['ton_n']}곳 평균이고 "
                        f"{b['ton_min']:,.1f} ~ {b['ton_max']:,.1f} t 사이입니다")
        if b["suspect"]:
            bits.append(f"대장 누락이 의심되는 {b['suspect']}곳은 면적당 평균에서 뺐습니다")
        if b["count"] < 5:
            bits.append("아직 표본이 적어 평균은 참고만 하십시오")
        if bits:
            st.caption(" · ".join(bits) + ".")

        st.table({
            "사찰": [region.named(r.get("사찰", ""), r.get("지번주소", ""))
                     for r in saved],
            "연도": [r.get("조회연도", "") for r in saved],
            "배출량(t)": [r.get("공개자료 배출량(t)", "") for r in saved],
            "면적당(kWh/m²)": [r.get("면적당 전기(kWh/m2)", "") or "—" for r in saved],
            "연면적(m²)": [r.get("연면적(m2)", "") or "—" for r in saved],
            "신뢰도": [r.get("신뢰도", "") for r in saved],
            "누락 의심": [r.get("대장누락 의심", "") for r in saved],
        })

        # ── 두 축 — 배수(효율) x 총량(규모) ──
        #
        # **여러 절을 모아 볼 때만** 네 칸으로 나눕니다. 총량 기준선이
        # 표본의 중간값이라 한 곳만 보고는 정할 수 없습니다.
        # 단일 사찰 화면에는 판정 문구를 붙이지 않습니다.
        _rr = batch.ratio_rows()
        _med, _usable = batch.classify(_rr)      # CSV 와 같은 함수를 씁니다
        # 같은 이름 절 구별 — 원오사(부산 해운대구) / 원오사(계룡시)
        _pts = [(r.get("표시이름") or r.get("사찰", ""), q, t)
                for q, t, r in _usable]

        if len(_pts) >= 3:
            st.markdown("##### 두 축으로 보기 — 효율과 규모")
            st.markdown(
                '<p class="hint">처방이 다르므로 섞지 않습니다. '
                "<b>효율 개선 후보</b>는 낭비를 줄이는 일이고, "
                "<b>설비·태양광 후보</b>는 이미 효율적이지만 규모가 커서 "
                "설비를 바꿀 값어치가 있는 절입니다.</p>",
                unsafe_allow_html=True)

            import altair as alt
            import pandas as pd
            df = pd.DataFrame(
                [{"사찰": n, "배수": q, "총에너지(kWh)": t,
                  "분류": em.quadrant(q, t, _med)} for n, q, t in _pts])
            base = alt.Chart(df)
            pts = base.mark_circle(size=120, opacity=0.8).encode(
                x=alt.X("배수:Q", title="지역 원단위 대비 배수"),
                y=alt.Y("총에너지(kWh):Q", title="연간 총에너지 (kWh, 로그)",
                        scale=alt.Scale(type="log")),
                color=alt.Color("분류:N", title=""),
                tooltip=["사찰", "배수", "총에너지(kWh)", "분류"],
            )
            vline = base.mark_rule(strokeDash=[6, 4]).encode(
                x=alt.datum(em.QUAD_RATIO))
            hline = base.mark_rule(strokeDash=[6, 4]).encode(
                y=alt.datum(_med))
            st.altair_chart((pts + vline + hline).properties(height=360),
                            width="stretch")
            st.caption(
                f"세로 점선 = 배수 {em.QUAD_RATIO:.1f} (원단위 자체가 전국 중간값) · "
                f"가로 점선 = 이 {len(_pts)}곳의 총에너지 중간값 "
                f"{_med:,.0f} kWh. **가로선은 절대 기준이 아니라 "
                "모인 절들 안에서의 상대적인 선입니다.**")

            # 상가 건물 한 호만 쓰는 절은 빼 두었습니다. 숨기지 않고
            # 몇 곳을 왜 뺐는지 밝힙니다(CLAUDE.md 7장).
            _inb = [(r.get("표시이름") or r.get("사찰", ""))
                    for r in _rr if batch.is_yes(r.get(batch.COL_INBLD))]
            if _inb:
                st.caption(
                    f"**{len(_inb)}곳은 이 그림에서 뺐습니다** — "
                    f"{' · '.join(_inb)}. 상가 건물 한 호만 쓰는 절이라 "
                    "건물에너지가 **건물 전체 값**으로 잡힙니다. "
                    "전기와 면적은 위 표에 그대로 있습니다.")

            _cnt = df["분류"].value_counts().to_dict()
            st.table({
                "분류": list(em.QUAD.values()),
                "곳": [_cnt.get(v, 0) for v in em.QUAD.values()],
                "사찰": [" · ".join(df[df["분류"] == v]["사찰"].tolist()) or "—"
                         for v in em.QUAD.values()],
            })
        elif _rr:
            st.caption("배수와 총에너지가 함께 나온 곳이 3곳을 넘으면 "
                       "두 축 그림이 나옵니다.")

        with st.expander("나눠 돌린 기록 합치기"):
            st.markdown('<p class="hint">여러 분이 나눠 조회하셨다면 각자의 '
                        "<b>사찰기록.csv</b> 를 여기에 올리십시오. 같은 사찰·같은 해가 "
                        "겹치면 <b>나중에 저장한 것</b>만 남습니다.<br>"
                        "적어 두신 <b>방문 상태와 메모는 지워지지 않습니다.</b></p>",
                        unsafe_allow_html=True)
            ups = st.file_uploader("합칠 CSV", type="csv", accept_multiple_files=True,
                                   label_visibility="collapsed")
            if ups and st.button("합치기", width="stretch"):
                try:
                    res = store.merge([u.getvalue() for u in ups])
                except store.StoreError as e:
                    st.error(str(e)); st.stop()
                st.success(
                    f"**{len(ups)}개 파일에서 {res['seen']}줄**을 읽어 "
                    f"새로 {res['added']}곳을 더하고 {res['updated']}곳을 새것으로 "
                    f"바꿨습니다. 오래되어 넘긴 것 {res['older']}줄. "
                    f"이제 모두 {res['total']}곳입니다.")
                st.rerun()

        d1, d2 = st.columns([3, 2])
        with d1:
            st.download_button("표 내려받기 (엑셀에서 열림)",
                               data=store.as_csv_bytes(),
                               file_name="사찰기록.csv", mime="text/csv",
                               width="stretch")
            st.caption(f"파일은 이 폴더의 {store.FILE_NAME} 에도 그대로 있습니다.")
        with d2:
            labels = [f"{r.get('사찰','')} · {r.get('조회연도','')}" for r in saved]
            pick = st.selectbox("지울 기록", options=list(range(len(saved))),
                                format_func=lambda i: labels[i], index=None,
                                placeholder="고르세요")
            if pick is not None and st.button("이 기록 지우기", width="stretch"):
                try:
                    store.remove(saved[pick].get("지번주소", ""),
                                 saved[pick].get("조회연도", ""))
                except store.StoreError as e:
                    st.error(str(e)); st.stop()
                st.rerun()


    # ═══════════ 6단계 — 명단 일괄 조회 ═══════════
    st.divider()
    st.markdown("#### 명단으로 한꺼번에 조회")

    _here = os.path.dirname(os.path.abspath(__file__))
    _list_path = os.path.join(_here, batch.LIST_NAME)

    try:
        targets = batch.read_list(_list_path) if os.path.exists(_list_path) else []
        list_err = ""
    except batch.BatchError as e:
        targets, list_err = [], str(e)

    if list_err:
        st.error(list_err)
    elif not targets:
        st.markdown(f'<p class="hint">같은 폴더에 <b>{batch.LIST_NAME}</b> 이 있으면 '
                    "여기서 한꺼번에 조회할 수 있습니다.</p>", unsafe_allow_html=True)
    else:
        have = batch.done_map()
        left = [t for t in targets if (t.no or t.name) not in have]
        bad = [t for t in targets if have.get(t.no or t.name)]

        c1, c2, c3 = st.columns(3)
        c1.metric("명단", f"{len(targets)}곳")
        c2.metric("조회함", f"{len(targets) - len(left)}곳")
        c3.metric("남음", f"{len(left)}곳")

        st.markdown('<p class="hint">한 번에 <b>10곳씩</b> 합니다. 한 곳이 끝날 때마다 '
                    "바로 저장하므로 <b>중간에 멈춰도 이어집니다.</b> "
                    "이미 조회한 곳은 건너뜁니다.<br>"
                    "한 곳에 10~20초 걸립니다. 제공기관 서버가 느리면 더 걸리는데, "
                    "3분을 넘기면 그 곳은 건너뛰고 다음으로 갑니다.</p>",
                    unsafe_allow_html=True)

        b1, b2, b3 = st.columns([2, 2, 1])
        year_b = b3.selectbox("해", [dt.date.today().year - 1,
                                     dt.date.today().year - 2,
                                     dt.date.today().year - 3], key="batch_year")
        go = b1.button(f"10곳 조회하기  (남은 {len(left)}곳 중)",
                       width="stretch", disabled=not left)
        again = b2.button(f"실패한 {len(bad)}곳만 다시",
                          width="stretch", disabled=not bad)

        if go or again:
            bar = st.progress(0.0, text="시작합니다")
            log = st.empty()
            t0 = time.time()
            lines = []

            def prog(done, total, t, why):
                gone = time.time() - t0
                eta = (gone / done) * (total - done) if done else 0
                bar.progress(done / total,
                             text=f"{done}/{total}  {t.label()}  ·  "
                                  f"남은 시간 약 {eta/60:.0f}분")
                lines.append(f"{'OK ' if why == '성공' else '-- '} {t.label()}  {why}")
                log.code(_NL.join(lines[-10:]), language=None)

            try:
                res = batch.run(targets, year_b, CONFM_KEY, SERVICE_KEY,
                                limit=10, retry_failed=bool(again), progress=prog)
            except Exception as e:
                bar.empty(); st.error(f"조회 중 멈췄습니다: {portal.hide_keys(e)}"); st.stop()
            bar.empty()

            st.success(f"**성공 {res['ok']}곳 · 실패 {len(res['failed'])}곳** "
                       f"({(time.time()-t0)/60:.0f}분). "
                       f"아직 {res['remaining']}곳 남았습니다.")
            if res["failed"]:
                st.warning("**실패한 곳**" + _NL + _NL +
                           _NL.join(f"- {t.label()} — {why}" for t, why in res["failed"]))
            st.rerun()


    # ═══════════ 7단계 — 방문 우선순위 ═══════════
    if saved:
        st.divider()
        ready, hold = store.priority(saved)
        st.markdown(f"#### 방문 우선순위 — {len(ready)}곳")
        st.markdown('<p class="hint">세 가지를 <b>나란히</b> 보여 드립니다. '
                    "점수를 합쳐 하나로 만들지 않습니다. 어느 것을 중히 볼지는 "
                    "사람이 정할 일입니다.<br>"
                    "배출 규모가 큰 순으로 줄을 세웠을 뿐입니다. "
                    "난방 부담은 2.5배 이상이면 <b>◀</b> 를 붙였습니다.</p>",
                    unsafe_allow_html=True)

        if ready:
            st.table({
                "번호": [r.get("번호", "") for r in ready],
                "사찰": [region.named(r.get("사찰", ""), r.get("지번주소", ""))
                         for r in ready],
                "배출 규모(t)": [r.get("공개자료 배출량(t)", "") for r in ready],
                "난방 부담": [store.heating_flag(r) for r in ready],
                "태양광 여지": [store.solar_room(r) for r in ready],
                "방문 상태": [r.get("방문 상태", "") for r in ready],
            })
        else:
            st.caption("아직 판단할 수 있는 곳이 없습니다.")

        if hold:
            st.markdown(f"##### 판단 보류 — {len(hold)}곳")
            st.markdown('<p class="hint">우선순위가 <b>낮은</b> 것이 아니라 '
                        "<b>자료가 부족해 판단을 미룬</b> 곳입니다. 섞어 보지 마십시오. "
                        "현장에서 확인해야 합니다.</p>", unsafe_allow_html=True)
            st.table({
                "번호": [r.get("번호", "") for r in hold],
                "사찰": [region.named(r.get("사찰", ""), r.get("지번주소", ""))
                         for r in hold],
                "보류 사유": [r.get("_보류사유", "") for r in hold],
                "전기(kWh)": [r.get("전기(kWh)", "") or "—" for r in hold],
                "연면적(m²)": [r.get("연면적(m2)", "") or "—" for r in hold],
            })


# ═══════════ 맨 아래 — 지금 돌고 있는 판 ═══════════
#
# 올린 뒤 사이트가 최신인지 **열어 보는 즉시** 알 수 있게 합니다.
st.divider()
st.caption(f"사찰 넷제로 진단 도구 · 돌고 있는 판 {running_version()}")
