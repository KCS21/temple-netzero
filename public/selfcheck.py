# -*- coding: utf-8 -*-
"""
사찰 자가진단 계산 — 공개 홈페이지 (작업지시 10)
불교탄소중립실천단 지수광풍

화면(`public_app.py`)과 떼어 두었습니다. 테스트(`test_public.py`)가 이것을 봅니다.

**계산은 컨설턴트 앱과 같은 함수를 씁니다** — `emissions.power_t`·`gas_t`·`burn`.
두 앱이 같은 절에 다른 숫자를 내면 안 됩니다(작업지시 10 0장 3번).

보여 주지 않는 것 — 원단위 배수, 면적당 값, 연면적. 대장 면적이 틀리기 쉬워
사찰이 오해할 수 있습니다(CLAUDE.md 7장, 실상사 518 m2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import bldrgst
import emissions as em

# ── 난방 수단 (여러 개 고르기) ──
HEAT_ELEC = "전기판넬·전기보일러·심야전기"
HEAT_GAS = "도시가스"
HEAT_KERO = "등유"
HEAT_LPG = "LPG"
HEAT_WOOD = "화목"
HEAT_UNKNOWN = "잘 모름"
HEAT_OPTIONS = (HEAT_ELEC, HEAT_GAS, HEAT_KERO, HEAT_LPG, HEAT_WOOD, HEAT_UNKNOWN)
FUEL_HEATS = (HEAT_KERO, HEAT_LPG, HEAT_WOOD)

# ── 연료 양 — 사찰이 아는 단위로 받습니다 ──
DRUM_L = 200          # 등유 1드럼
LPG_SMALL_KG = 20     # 20kg 통
LPG_BIG_KG = 50       # 50kg 통
KEROSENE = "등유(Kerosene)"
LPG = "LPG-프로판(LPG1호)"   # 가정·상업용 통은 프로판입니다

# ── 유형 ──
TYPE_FUEL = "연료 난방형"
TYPE_ELEC = "전기 난방형"
TYPE_GAS = "도시가스 난방형"
TYPE_ELEC_EST = "전기 난방형 (자료로 추정)"
TYPE_FUEL_EST = "연료 난방 추정형"
TYPE_HOLD = "판정 보류"

SEASON_CUT = 2.5      # 겨울 최대 달 / 여름 최소 달
WINTER = (12, 1, 2)
SUMMER = (6, 7, 8, 9)

MODE_LOOKUP = "조회"
MODE_BILL = "고지서"

SUPPORT_TEXT = ("태양광 건물지원·자가설비 인증서(REGO)·난방전기화 사업이 "
                "2027년 공고 예정입니다. 대상 여부는 컨설팅에서 함께 확인해 드립니다.")
LIMIT_TEXT = ("공개 자료와 입력하신 값으로 계산한 개략 진단입니다. "
              "정확한 진단은 현장 확인이 필요합니다.")
WOOD_TEXT = "장작은 배출 합계에 넣지 않았습니다(바이오매스)."

ACTION_FIRST = ("전기 고지서의 계약전력을 확인해 보세요. 실제 쓰는 만큼으로 낮추면 "
                "기본요금이 줄어듭니다(돈이 들지 않습니다).")
ACTION_BY_TYPE = {
    TYPE_ELEC: ("전기판넬·전기보일러를 공기열 히트펌프로 바꾸면 난방 전기를 "
                "크게 줄일 수 있습니다."),
    TYPE_FUEL: ("등유·LPG 보일러를 히트펌프로 바꾸는 것을 검토해 보세요. "
                "연료비와 배출이 함께 줍니다."),
    TYPE_GAS: "창호·단열과 고효율 보일러 또는 히트펌프를 살펴보세요.",
    TYPE_HOLD: "1년치 고지서로 다시 진단해 보세요.",
}
ACTION_BY_TYPE[TYPE_ELEC_EST] = ACTION_BY_TYPE[TYPE_ELEC]
ACTION_BY_TYPE[TYPE_FUEL_EST] = ACTION_BY_TYPE[TYPE_FUEL]
ACTION_LAST = ("줄이고 남은 전기는 태양광으로. 부속건물 지붕은 전기요금을 아끼는 "
               "자가소비형, 넓은 주차장·유휴부지는 투자 부담 없이 임대료를 받는 "
               "부지임대형이 있습니다.")


def _month_of(key) -> int:
    """'202501' · '01' · 1 을 모두 달(1~12)로."""
    s = str(key).strip()
    return int(s[-2:]) if len(s) >= 2 else int(s)


def season_ratio(monthly: Optional[Dict]) -> Optional[float]:
    """겨울(12·1·2월) 최대 달 / 여름(6~9월) 최소 달.

    **12달이 모두 있어야** 냅니다. 한 달이라도 0 이거나 비면 None —
    빈 달이 여름에 끼면 계절비가 하늘로 솟습니다.
    """
    if not monthly:
        return None
    by_m = {}
    for k, v in monthly.items():
        try:
            by_m[_month_of(k)] = float(v or 0)
        except (TypeError, ValueError):
            return None
    if len(by_m) != 12 or any(by_m.get(m, 0) <= 0 for m in range(1, 13)):
        return None
    return max(by_m[m] for m in WINTER) / min(by_m[m] for m in SUMMER)


def classify(heat, gas_kwh: float = 0.0, monthly: Optional[Dict] = None) -> str:
    """우리 절 유형. **위에서부터 먼저 맞는 것** (작업지시 10 ③ 판정표).

    사람이 고른 것을 자료보다 먼저 믿습니다. 자료로 추정하는 것은
    아무것도 고르지 않았거나 「잘 모름」일 때뿐입니다.
    """
    heat = set(heat or ())
    if heat & set(FUEL_HEATS) and HEAT_ELEC not in heat:
        return TYPE_FUEL
    if HEAT_ELEC in heat:
        return TYPE_ELEC
    if HEAT_GAS in heat or float(gas_kwh or 0) > 0:
        return TYPE_GAS
    r = season_ratio(monthly)
    if r is not None:
        return TYPE_ELEC_EST if r >= SEASON_CUT else TYPE_FUEL_EST
    return TYPE_HOLD


def kerosene_l(drums) -> float:
    return float(drums or 0) * DRUM_L


def lpg_kg(small, big) -> float:
    return float(small or 0) * LPG_SMALL_KG + float(big or 0) * LPG_BIG_KG


def actions(kind: str) -> List[str]:
    return [ACTION_FIRST, ACTION_BY_TYPE.get(kind, ACTION_BY_TYPE[TYPE_HOLD]),
            ACTION_LAST]


def ratio_text(r: Optional[float]) -> str:
    """화면에는 「겨울 전기가 여름의 ○.○배」로 풀어 씁니다."""
    return f"겨울 전기가 여름의 {r:.1f}배" if r is not None else ""


@dataclass
class Result:
    name: str
    addr: str
    year: Optional[int]
    mode: str                         # 조회 | 고지서
    elec_kwh: float
    gas_kwh: float
    kero_l: float
    lpg_kg: float
    wood: bool
    heat: List[str]
    monthly: Optional[Dict[str, float]] = None
    months: int = 0                   # 자료가 있는 달 수 (조회일 때)
    elec_t: float = 0.0
    gas_t: float = 0.0
    kero_t: float = 0.0
    lpg_t: float = 0.0
    total_t: float = 0.0
    people: float = 0.0
    solar_kw: float = 0.0
    ratio: Optional[float] = None
    kind: str = TYPE_HOLD
    todo: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """컨설팅 요청에 붙이는 한 줄."""
        return (f"전기 {self.elec_kwh:,.0f} kWh · 배출 {self.total_t:,.1f} t · "
                f"유형 {self.kind}")


def diagnose(name: str, addr: str, year: Optional[int], mode: str,
             elec_kwh: float, gas_kwh: float = 0.0, heat=(),
             kero_drums=None, lpg_small=None, lpg_big=None,
             monthly: Optional[Dict] = None) -> Result:
    """숫자 세 개 + 유형 + 먼저 해 볼 일 + 한계 문구."""
    heat = [h for h in HEAT_OPTIONS if h in set(heat or ())]
    kero, lpg = kerosene_l(kero_drums), lpg_kg(lpg_small, lpg_big)
    elec_kwh, gas_kwh = float(elec_kwh or 0), float(gas_kwh or 0)
    r = Result(name=name, addr=addr, year=year, mode=mode,
               elec_kwh=elec_kwh, gas_kwh=gas_kwh, kero_l=kero, lpg_kg=lpg,
               wood=HEAT_WOOD in heat, heat=heat, monthly=monthly or None)
    if monthly:
        r.months = sum(1 for v in monthly.values() if v and float(v) > 0)

    # 기본값 그대로: 전력 발전단(LB) · 도시가스 순발열량 · AR5 (CLAUDE.md 6장)
    r.elec_t = em.power_t(elec_kwh)
    r.gas_t = em.gas_t(gas_kwh)
    r.kero_t = em.burn(KEROSENE, kero).ar5_t if kero else 0.0
    r.lpg_t = em.burn(LPG, lpg).ar5_t if lpg else 0.0
    r.total_t = r.elec_t + r.gas_t + r.kero_t + r.lpg_t
    r.people = r.total_t / em.KOR_PER_CAPITA
    r.solar_kw = em.solar_capacity_kw(elec_kwh)

    r.ratio = season_ratio(monthly)
    r.kind = classify(heat, gas_kwh, monthly)
    r.todo = actions(r.kind)

    r.notes = [LIMIT_TEXT]
    if r.wood:
        r.notes.append(WOOD_TEXT)
    if mode == MODE_LOOKUP and monthly and r.months < 12:
        r.notes.append(f"공개 자료에 {r.months}달 치만 있어 1년치보다 적게 "
                       "잡혔을 수 있습니다.")
    if mode == MODE_LOOKUP:
        r.notes.append("전기·가스는 이 주소의 지번 한 곳에 잡힌 값입니다. "
                       "사찰 전체가 아닐 수 있습니다.")
    unasked = [h for h in (HEAT_KERO, HEAT_LPG) if h in heat]
    if (HEAT_KERO in unasked and not kero) or (HEAT_LPG in unasked and not lpg):
        r.notes.append("양을 넣지 않은 난방 연료는 배출량에 들어가지 않았습니다.")
    return r


def diag_payload(r: Result, version: str = "") -> dict:
    """구글 시트 「자가진단기록」 한 줄. 열쇠는 `.gs` 의 DIAG_COLS 와 같습니다.

    **이름·연락처는 없습니다.** 자가진단은 누가 했는지 받지 않습니다.
    """
    return {
        "절 이름": r.name,
        "지번주소": r.addr,
        "조회연도": r.year or "",
        "입력 방식": r.mode,
        "연간 전기(kWh)": round(r.elec_kwh),
        "도시가스(kWh)": round(r.gas_kwh),
        "등유(L)": round(r.kero_l),
        "LPG(kg)": round(r.lpg_kg),
        "화목 사용": "사용함" if r.wood else "",
        "난방 수단": ", ".join(r.heat),
        "배출량(t)": round(r.total_t, 2),
        "계절비": round(r.ratio, 2) if r.ratio is not None else "",
        "유형": r.kind,
        "앱 버전": version,
    }


# ── 고른 주소가 절이 맞는지 (작업지시 11 ②) ──
# **종교시설이 없다고 바로 경고하지 않습니다**(CLAUDE.md 7장). 종교집회장은
# 500m2 미만이면 제2종근린생활시설이고 요사채는 단독주택으로 잡힙니다.
# 그래서 종교시설도 없고, **절에 흔한 용도(근린생활·주택)도 아닌 것**이
# 있을 때만 안내합니다 — 학교·숙박·업무시설 같은 것. 컨설턴트 앱의
# `bldrgst.ODD_PURPOSES` 에 걸리면 종교시설이 있어도 안내합니다.
TEMPLE_OK = ("종교", "근린생활", "단독주택", "주택", "노유자")
NOT_TEMPLE_TEXT = "이 주소의 건물이 절이 아닐 수 있습니다. 주소를 확인해 주세요."


def not_temple(purposes) -> bool:
    ps = [str(p or "").strip() for p in (purposes or ()) if str(p or "").strip()]
    if not ps:
        return False                    # 건물이 없으면 이 안내가 아니라 자료 없음으로
    if any(any(k in p for k in bldrgst.ODD_PURPOSES) for p in ps):
        return True
    if any("종교" in p for p in ps):
        return False
    return any(not any(k in p for k in TEMPLE_OK) for p in ps)
