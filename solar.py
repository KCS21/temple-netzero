# -*- coding: utf-8 -*-
"""
태양광 발전시간 — 시도·월별 실측값
사찰 넷제로 진단 도구 · 불교탄소중립실천단 지수광풍

작업지시 14(2026-11-03). 그 전에는 **전국 한 값 3.5시간**을 썼습니다.
실측으로 보니 시도 차이가 20%(대전 3.00 ~ 전북 3.61 h/일),
달 차이는 **두 배가 넘습니다**(12월 1.8 ~ 5월 4.9).

    1 kW 연간 발전[시도] = Σ(하루 발전시간[월] x 그 달 날수)
    필요용량(kW)        = 연간 전기 / 1 kW 연간 발전[시도]

자료는 `data/태양광_발전시간_시도월_2022_2024.csv`
(전력거래소 EPSIS 신재생에너지 이용률, 공공데이터포털 15142242).
**갱신은 `scripts/태양광표_만들기.py`** 로 하고, 기간이 바뀌면 아래
`PERIOD`·`FILE` 두 줄만 고치면 화면 문구까지 따라갑니다.

**이 값에 없는 것** — 지붕 방향·그늘·경사. 계통에 판매된 발전량 기준
이용률이라 지붕형은 조금 낮게 나옵니다. 설치 가능 여부와 실제 발전량은
현장 확인이 필요합니다(CLAUDE.md 7장).
"""
from __future__ import annotations

import calendar
import csv
import io
import os
from typing import Dict, List, Optional

import region

PERIOD = "2022~2024"
FILE = "태양광_발전시간_시도월_2022_2024.csv"
SOURCE = f"전력거래소 EPSIS 실측 이용률, {PERIOD} 평균"

# 평년 날수. 표를 만들 때와 같은 잣대로 연간값을 냅니다.
_DAYS = [calendar.monthrange(2023, m)[1] for m in range(1, 13)]

# 표의 시도 이름 <- 주소에서 뽑은 짧은 이름(region._SIDO 가 정규화한 것).
# **옛 이름도 맞아야 합니다** - 강원도/강원특별자치도, 전라북도/전북특별자치도
# 둘 다 들어옵니다(region 이 이미 짧은 이름으로 모읍니다).
_TO_TABLE = {
    "서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천",
    "광주": "광주", "대전": "대전", "울산": "울산", "세종": "세종",
    "경기": "경기도", "강원": "강원도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전라북도", "전남": "전라남도", "경북": "경상북도",
    "경남": "경상남도", "제주": "제주도",
}


class SolarError(Exception):
    pass


def _path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", FILE)


def _load():
    p = _path()
    if not os.path.exists(p):
        raise SolarError(f"태양광 표가 없습니다: data/{FILE}")
    hours: Dict[str, List[float]] = {}
    with io.open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = (r.get("시도") or "").strip()
            if not name:
                continue
            hours[name] = [float(r[f"{m}월 발전시간(h/일)"]) for m in range(1, 13)]
    if not hours:
        raise SolarError("태양광 표가 비어 있습니다.")
    return hours


HOURS: Dict[str, List[float]] = _load()

# 전국 평균 — **17개 시도 단순 평균**입니다(설비 용량 가중이 아닙니다).
# 시도를 못 찾았을 때만 씁니다.
NATION = "전국 평균"
HOURS[NATION] = [sum(v[i] for v in HOURS.values()) / len(HOURS)
                 for i in range(12)]


def annual_kwh_per_kw(place: str = NATION) -> float:
    """1 kW 가 한 해에 만드는 전기(kWh). 달마다 날수가 달라 가중해 더합니다."""
    hs = HOURS.get(place) or HOURS[NATION]
    return sum(h * d for h, d in zip(hs, _DAYS))


ANNUAL: Dict[str, float] = {k: annual_kwh_per_kw(k) for k in HOURS}


def place_of(addr: str) -> str:
    """주소 -> 표의 시도 이름. 못 찾으면 빈 문자열.

    통합된 광주·전남은 시군구 이름으로 가릅니다(`region.old_sido`).
    """
    sido, _ = region.split(addr or "")
    if not sido:
        return ""
    if sido == "전남광주":
        sido = region.old_sido(addr) or ""
    return _TO_TABLE.get(sido, "")


def hours_of(place: str = NATION) -> List[float]:
    """그 시도의 12달 하루 발전시간."""
    return list(HOURS.get(place) or HOURS[NATION])


def day_hours(place: str = NATION) -> float:
    """연평균 하루 발전시간 (연간 발전량 / 365)."""
    return annual_kwh_per_kw(place) / 365


def capacity_kw(elec_kwh: float, place: str = NATION) -> float:
    """연간 전기를 메우는 데 드는 태양광 용량(kW)."""
    per = annual_kwh_per_kw(place)
    return float(elec_kwh or 0) / per if per else 0.0


def monthly_gen(kw: float, place: str = NATION) -> List[float]:
    """그 용량이 달마다 만드는 전기(kWh)."""
    return [float(kw or 0) * h * d for h, d in zip(hours_of(place), _DAYS)]


def label(place: str) -> str:
    """화면·엑셀에 적을 한 줄. 시도·출처·기간·시간을 함께 밝힙니다."""
    name = place or NATION
    return (f"{name} 실측 이용률({SOURCE}) 기준 "
            f"하루 평균 {day_hours(name):.1f}시간으로 계산했습니다.")


CAVEAT = ("지붕 방향·그늘·경사는 반영되지 않았습니다. "
          "설치 가능 여부와 실제 발전량은 현장 확인이 필요합니다.")
NO_PLACE = "지역을 찾지 못해 전국 평균을 썼습니다."


def resolve(addr: str) -> tuple:
    """(표의 시도 이름, 전국 평균을 썼는가)."""
    p = place_of(addr)
    return (p or NATION, not p)
