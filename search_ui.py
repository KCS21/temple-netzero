# -*- coding: utf-8 -*-
"""
사찰 찾기 화면 — 두 앱이 함께 씁니다
사찰 넷제로 진단 도구 · 불교탄소중립실천단 지수광풍

컨설턴트 앱(`app.py`) 1단계와 공개 앱(`public_app.py`) 자가진단의 찾기가
따로 자라 서로 달라졌습니다. 공개 앱 쪽이 더 나아서(지도 먼저 · 더 보기 ·
산 지번 · 지번 직접 · 주소 서버 재시도 뒤 자동 펼침) 그것을 여기로 옮기고
**두 앱이 같은 것을 부릅니다**(2026-11-07).

고른 주소는 `st.session_state.picked` 에 둡니다(두 앱이 원래 쓰던 이름).
고를 때마다 `on_pick()` 을 불러 각 앱이 **딸린 상태**(건물·진단·엑셀 등)를
비우게 합니다. 그 밖의 찾기 상태는 `srch_` 로 시작하는 이름만 씁니다.

지켜야 할 것(CLAUDE.md 2·7장)

- **누를 때만 찾습니다.** 실시간 자동완성 없음
- 지도(카카오) 결과는 **화면에만** 두고, 고른 주소를 도로명주소로 **다시**
  찾아 그 결과만 씁니다. 키가 없거나 어떤 오류가 나도 지도 칸에서 끝냅니다
- 주소 서버가 응답하지 않으면 **지번 직접 입력 칸을 펼쳐** 다음 행동을 줍니다
- 오류 문구는 `portal.hide_keys()` 를 거칩니다
"""
from __future__ import annotations

from typing import Callable, Optional

import streamlit as st

import juso
import kakao
import keys
import portal

PER_PAGE = 5
NAME_WARN = ("이름으로 찾은 주소입니다. **주소가 맞는지 확인해 주세요.** "
             "같은 이름의 다른 절이 흔합니다.")
BUSY = "주소 검색이 잠시 되지 않습니다. 잠시 뒤 다시 찾아 주세요."

_DEFAULTS = (("srch_rows", []), ("srch_total", 0), ("srch_page", 1),
             ("srch_kw", ""), ("srch_err", ""), ("srch_searched", False),
             ("srch_places", []), ("srch_places_err", ""),
             ("srch_open_direct", False), ("picked", None))


def kakao_key() -> str:
    """카카오 키. **무슨 오류든 삼키고 빈 문자열** — 키가 없는 것과 똑같이
    지도 칸만 숨습니다(7장 「옛 모듈이 남는다」·「없어도 되는 기능」)."""
    try:
        return keys.kakao()
    except Exception:
        return ""


def is_name(kw: str) -> bool:
    """숫자가 없으면 절 이름으로 찾는 것으로 봅니다. 「구산동 314」는 주소."""
    return not any(c.isdigit() for c in (kw or ""))


class Finder:
    """한 화면의 찾기 칸. 앱마다 하나 만들어 `.show()` 를 부릅니다.

    confm_key  도로명주소 승인키
    kakao      카카오 키(없으면 지도 칸을 숨김)
    on_pick    고른 주소가 바뀔 때(비워질 때 포함) 부를 함수
    css        안내 글에 붙일 클래스 — 두 앱의 작은 글씨 이름이 다릅니다
    other_way  못 찾았을 때 덧붙일 다른 길(공개 앱의 「고지서 숫자로 직접 넣기」)
    """

    def __init__(self, confm_key: str, kakao: str = "",
                 on_pick: Optional[Callable[[], None]] = None,
                 css: str = "hint", other_way: str = "",
                 per_page: int = PER_PAGE):
        self.confm_key = confm_key
        self.kakao = kakao
        self.on_pick = on_pick or (lambda: None)
        self.css = css
        self.other_way = other_way
        self.per_page = per_page
        for k, v in _DEFAULTS:
            st.session_state.setdefault(k, v)

    # ── 상태 바꾸기 (콜백 안에서도 부릅니다) ──
    def _set_picked(self, j):
        st.session_state.picked = j
        self.on_pick()

    def search(self, keyword: str, page: int = 1, keep_places: bool = False):
        """도로명주소 검색. 결과·오류를 상태에 두고 고른 주소를 비웁니다."""
        open_direct = False
        try:
            rows, total = juso.search(keyword, self.confm_key, page=page,
                                      per_page=self.per_page)
            err = ""
        except juso.JusoError as e:
            rows, total = [], 0
            err = portal.hide_keys(str(e))
            # 주소 서버가 응답하지 않으면 **지번 직접 입력 칸을 펼쳐** 둡니다.
            # 접힌 칸을 안내만 하면 시니어 회원은 거기서 멈춥니다(2장).
            open_direct = str(e) == juso.DOWN_TEXT
        except Exception:
            rows, total, err = [], 0, BUSY
        st.session_state.update(srch_rows=rows, srch_total=total, srch_page=page,
                                srch_kw=keyword, srch_err=err, srch_searched=True,
                                srch_addr_pick=None, srch_open_direct=open_direct)
        if not keep_places:
            st.session_state.update(srch_places=[], srch_places_err="",
                                    srch_place_pick=None)
        self._set_picked(None)

    def map_search(self, kw: str):
        """지도에서 절 이름 찾기. 이름으로 찾을 때만, 키가 있을 때만."""
        st.session_state.update(srch_places=[], srch_places_err="",
                                srch_place_pick=None)
        if not (self.kakao and is_name(kw)):
            return
        try:
            st.session_state.srch_places = kakao.search(kw, self.kakao)[0]
        except Exception:
            # 지도 칸은 어떤 오류가 나도 거기서 끝냅니다. 주소 검색은 그대로 돕니다.
            st.session_state.srch_places_err = ("지도 검색이 잠시 되지 않습니다. "
                                                "아래 주소 검색 결과를 봐 주세요.")

    def _pick_row(self):
        # **고르는 순간에만** 듣습니다(on_change). 옆 지번으로 바꾼 picked 를
        # 다음 그리기에서 목록의 줄로 되돌려 놓지 않도록(작업지시 08).
        i = st.session_state.get("srch_addr_pick")
        rows = st.session_state.srch_rows
        if i is not None and i < len(rows):
            self._set_picked(rows[i])

    def _pick_place(self):
        i = st.session_state.get("srch_place_pick")
        places = st.session_state.get("srch_places") or []
        if i is None or i >= len(places):
            return
        # 고른 곳을 도로명주소로 **다시** 찾습니다. 그 결과만 씁니다.
        self.search(places[i].search_key, keep_places=True)

    def _hint(self, html: str):
        st.markdown(f'<p class="{self.css}">{html}</p>', unsafe_allow_html=True)

    # ── 화면 ──
    def show(self, title: str = ""):
        if title:
            st.markdown(title)
        self._hint("<b>주소 또는 절 이름</b>을 넣어 주세요. 절 이름으로 찾은 것에는 "
                   "<b>(이름으로 찾음)</b> 표시가 붙습니다.<br>"
                   "같은 이름의 절이 많습니다. <b>시·군 이름을 함께</b> 넣으면 "
                   "잘 찾아집니다. 예: 원오사 양주")
        with st.form("search"):
            kw = st.text_input("주소 또는 절 이름", value=st.session_state.srch_kw,
                               placeholder="예: 구산동 314  또는  원오사 양주")
            go = st.form_submit_button("찾기", type="primary", width="stretch")
        if go:
            self.map_search(kw)
            self.search(kw, keep_places=True)

        # 지도 결과 — 이름으로 찾을 때 먼저
        places = st.session_state.get("srch_places") or []
        if st.session_state.get("srch_places_err"):
            st.info(st.session_state.srch_places_err)
        if places:
            st.markdown(f"**지도에서 {len(places)}곳**을 찾았습니다. 우리 절을 "
                        "고르시면 그 주소로 다시 찾습니다.")
            st.radio("지도 결과", list(range(len(places))), key="srch_place_pick",
                     format_func=lambda k: (f"{places[k].name}  ·  "
                                            f"{places[k].jibun or places[k].road or '주소 없음'}"),
                     index=None, label_visibility="collapsed",
                     on_change=self._pick_place)

        if st.session_state.srch_err:
            st.warning(st.session_state.srch_err)
        rows = st.session_state.srch_rows
        if st.session_state.srch_searched and not rows and not st.session_state.srch_err:
            st.warning("주소 검색에서는 찾지 못했습니다. 동 이름과 번지로 다시 "
                       "찾아 보세요. 예: 은평구 구산동 314")
            st.info("절 이름은 **건물 이름이 등록된 절만** 주소 검색에 나옵니다. "
                    "찾아지지 않으면 아래 「지번을 직접 넣기」"
                    + (f"나, {self.other_way}" if self.other_way else "")
                    + "를 써 주세요.")
        if rows:
            total, page = st.session_state.srch_total, st.session_state.srch_page
            last = max(1, (total + self.per_page - 1) // self.per_page)
            # 「1건」이 「유일」로 읽히면 안 됩니다 — 도로명주소 검색은 건물 이름이
            # 등록된 절만 찾습니다(원오사(계룡)가 그래서 안 나왔습니다).
            by_name = any(r.name_hit for r in rows)
            st.markdown(f"**주소 검색 {total:,}건** 중 {page}쪽입니다. 우리 절을 골라 주세요."
                        + (" 이름이 등록되지 않은 같은 이름의 절은 여기 나오지 않습니다."
                           if by_name else ""))
            st.radio("주소 고르기", list(range(len(rows))), key="srch_addr_pick",
                     format_func=lambda k: rows[k].label(), index=None,
                     label_visibility="collapsed", on_change=self._pick_row)
            c1, c2, c3 = st.columns(3)
            kw_now = (st.session_state.srch_kw or "").rstrip()
            if page > 1:
                c1.button("앞으로", key="pg_prev", width="stretch",
                          on_click=self.search, args=(kw_now, page - 1, True))
            if page < last:
                c2.button("더 보기", key="pg_next", width="stretch",
                          on_click=self.search, args=(kw_now, page + 1, True))
            if not any(r.is_mountain for r in rows) and not kw_now.endswith("산"):
                # 산중 사찰은 산 지번이 뒤쪽 쪽수에 묻히는 일이 많습니다.
                c3.button("산 지번만 찾기", key="mt_go", width="stretch",
                          on_click=self.search, args=(kw_now + " 산", 1, True))
        self.direct()

    def direct(self):
        """지번을 손으로 넣기 (작업지시 08 5번).

        **접어 둡니다.** 본번·부번을 묻는 것은 시니어에게 판단을 요구하는
        일이라(2장) 지번을 받아 온 회원만 펼칩니다. 다만 주소 서버가 응답하지
        않으면 **저절로 펼칩니다** — 그때는 이 칸이 유일한 다음 행동입니다.

        도로명이 없는 지번(강릉 삼산리 569)은 주소 검색에 무엇을 넣어도 안
        나옵니다. 그 동네를 찾아 행정구역코드만 빌리고 번·지는 갈아 끼웁니다.
        **건물명은 물려주지 않습니다**(`inherit_name=False`) — 아무 지번이나
        넣는 칸이라 남의 건물 이름(「계룡시 보훈회관」)이 붙어 나왔습니다.
        """
        with st.expander("지번을 직접 넣기 (주소 검색에 안 나올 때)",
                         expanded=bool(st.session_state.get("srch_open_direct"))):
            self._hint("고지서나 지도 앱에서 <b>지번을 확인하신 뒤</b> 넣어 주세요. "
                       "동·리는 그 동네를 찾는 데만 씁니다.")
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
                st.warning("동·리 이름과 번(숫자)을 넣어 주세요. "
                           "지(부번)가 없으면 비워 두세요.")
                return
            try:
                rows, _ = juso.search(dong.strip(), self.confm_key, per_page=1)
            except juso.JusoError as e:
                st.warning(portal.hide_keys(str(e)))
                return
            except Exception:
                st.warning(BUSY)
                return
            if not rows:
                st.warning("그 동네를 찾지 못했습니다. 시·군과 동·리 이름을 함께 "
                           "넣어 보세요. 예: 강릉시 연곡면 삼산리")
                return
            self._set_picked(juso.sibling(rows[0], int(bun_s), int(ji_s),
                                          inherit_name=False))
            st.rerun()


def name_warning(j) -> None:
    """이름으로 찾은 주소를 골랐으면 노란 안내 한 줄."""
    if j is not None and getattr(j, "name_hit", False):
        st.warning(NAME_WARN)
