# -*- coding: utf-8 -*-
"""
온실가스 배출량 계산 - 5단계 산정식
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수화풍

    배출량(tCO2eq) = 활동량 x 발열량 x 배출계수 x 산화계수 x GWP

「온실가스 배출량 산정 실무용 템플릿」과 같은 방식입니다.
연료를 부피·무게(L·kg·Nm3)로 사면 발열량을 적용하고,
전기처럼 이미 에너지 단위(kWh)면 배출계수를 직접 적용합니다.

**이전 방식(활동량 x 통합배출계수)은 폐기되었습니다.** 발열량이 어디에
반영되었는지 추적할 수 없고 값의 출처를 구분할 수 없기 때문입니다.

연료명은 템플릿 ②시트와 글자 하나까지 같아야 합니다. 다르면 엑셀의
INDEX/MATCH 가 빈값을 돌려주고 계산이 통째로 0 이 됩니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

MJ_PER_KWH = 3.6


# ── 별표10·11·12 참조표 ──────────────────────────────────────
@dataclass(frozen=True)
class Fuel:
    unit: str
    hv: float          # 순발열량 MJ/단위
    co2: float         # kgCO2/TJ
    ch4: float         # kgCH4/TJ
    n2o: float         # kgN2O/TJ
    oxid: float        # 산화계수 (CO2 에만 적용)
    default_scope: str


FUELS: Dict[str, Fuel] = {
    "도시가스/LNG":        Fuel("Nm3", 38.9, 56100, 1,   0.1, 0.995, "고정연소"),
    "경유(Diesel)":        Fuel("L",   35.2, 73200, 3,   0.6, 0.995, "이동연소"),
    "등유(Kerosene)":      Fuel("L",   34.2, 73200, 3,   0.6, 0.995, "고정연소"),
    "휘발유(Gasoline)":    Fuel("L",   30.4, 71600, 3,   0.6, 0.99,  "이동연소"),
    "LPG-프로판(LPG1호)":  Fuel("kg",  46.3, 64600, 1,   0.1, 0.99,  "고정연소"),
    "LPG-부탄(LPG3호)":    Fuel("kg",  45.7, 66300, 1,   0.1, 0.99,  "고정연소"),
}

# 같은 연료도 쓰임에 따라 시트가 다릅니다. 계수는 같습니다.
# 경유를 보일러에 쓰면 고정연소(③), 차량에 쓰면 이동연소(④).
# 연료의 속성이 아니라 쓰임의 속성이므로 부르는 쪽이 지정할 수 있습니다.
SCOPES = ("고정연소", "이동연소")

# ── GWP ─────────────────────────────────────────────────────
GWP: Dict[str, Tuple[float, float]] = {
    "AR5": (28, 265),      # K-ETS 공식
    "AR6": (29.8, 273),    # CBAM·ISSB
}
GWP_DEFAULT = "AR5"

# ── 전력 배출계수 (kgCO2eq/kWh) ──────────────────────────────
ELEC_EF: Dict[str, float] = {
    "발전단(LB)": 0.3844,    # 기본값. 보고용 원칙
    "소비단(MB)": 0.4173,    # RE100 등 참고용
    "보고서2024": 0.4747,    # 기존 5개 사찰과 비교할 때만
}
ELEC_DEFAULT = "발전단(LB)"

# ── 도시가스 kWh -> Nm3 ────────────────────────────────────
# 2026-09-14 순발열량 38.9MJ 로 확정했습니다. 근거 둘.
#
# 1) 240320 보고서가 봉은사 도시가스를 2,630,415 kWh = 249,328 Nm3 으로
#    적었습니다. 나누면 10.550 kWh/Nm3 -> 37.98 MJ/Nm3.
#    순발열량 38.9 와 +2.4%, 총발열량 43.1 과는 +13.5% 차이입니다.
# 2) 더 결정적인 것은 왕복입니다. 총발열량으로 나누고 템플릿에서 순발열량을
#    곱하면 에너지가 9.7% 사라집니다(825,325 -> 744,899 MJ).
#    같은 발열량으로 나누고 곱해야 맞습니다.
#
# 고지서 실물로 최종 확인이 남아 있어 세 선택지는 남겨 둡니다.
GAS_BASIS: Dict[str, float] = {
    "순발열량 38.9MJ": 38.9 / MJ_PER_KWH,     # 10.8056 kWh/Nm3 (기본값)
    "총발열량 43.1MJ": 43.1 / MJ_PER_KWH,     # 11.9722
    "보고서 역산":      10.55,
}
GAS_BASIS_DEFAULT = "순발열량 38.9MJ"

# ── 개략 진단용 ──────────────────────────────────────────────
KOR_PER_CAPITA = 13.1        # 국민 1인당 연간 배출량 (tCO2eq)
SOLAR_HOURS = 3.5            # 일평균 발전시간. 법문사 42kW 실측
WATER_EF = 0.332             # kgCO2eq/톤. Scope 3 이라 템플릿에 없음

# 공개자료(전기+가스)가 총 배출량에서 차지하는 비율.
# 화면에서는 쓰지 않습니다(과잉 확신 방지). 표본이 쌓이면 다시 검토합니다.
COVERAGE = {"도심": 0.93, "산중": 0.88}


class EmissionError(Exception):
    """화면에 그대로 보여줄 수 있는 오류."""


# ── 연료 연소 ────────────────────────────────────────────────
@dataclass
class Burn:
    """연료 한 가지의 계산 내역. 5단계가 다 보이도록 중간값을 남깁니다."""

    fuel: str
    qty: float
    unit: str
    hv: float
    tj: float
    co2_kg: float
    ch4_kg: float        # GWP 적용 전 (kgCH4)
    n2o_kg: float        # GWP 적용 전 (kgN2O)
    raw: Fuel = field(repr=False, default=None)

    def total_kg(self, gwp: str = GWP_DEFAULT) -> float:
        if gwp not in GWP:
            raise EmissionError(f"모르는 GWP 기준입니다: {gwp}")
        g_ch4, g_n2o = GWP[gwp]
        return self.co2_kg + self.ch4_kg * g_ch4 + self.n2o_kg * g_n2o

    def total_t(self, gwp: str = GWP_DEFAULT) -> float:
        return self.total_kg(gwp) / 1000

    @property
    def ar5_t(self) -> float:
        return self.total_t("AR5")

    @property
    def ar6_t(self) -> float:
        return self.total_t("AR6")

    def formula(self, gwp: str = GWP_DEFAULT) -> str:
        """산식을 사람이 읽을 수 있게. 어디서 온 값인지 추적되도록."""
        g_ch4, g_n2o = GWP[gwp]
        f = self.raw
        return (
            f"{self.qty:,.1f} {self.unit} x {self.hv} MJ = {self.tj:.6f} TJ"
            f"  |  CO2 {f.co2:,.0f}x{f.oxid}"
            f" + CH4 {f.ch4}x{g_ch4}"
            f" + N2O {f.n2o}x{g_n2o}"
            f"  =  {self.total_kg(gwp):,.2f} kgCO2eq"
        )


def burn(fuel: str, qty: float) -> Burn:
    """연료 활동량으로 배출량을 냅니다. 산화계수는 CO2 에만 적용합니다."""
    if fuel not in FUELS:
        raise EmissionError(f"참조표에 없는 연료입니다: {fuel}")
    f = FUELS[fuel]
    qty = float(qty or 0)
    tj = qty * f.hv / 1_000_000          # MJ -> TJ
    return Burn(
        fuel=fuel, qty=qty, unit=f.unit, hv=f.hv, tj=tj,
        co2_kg=f.co2 * tj * f.oxid,
        ch4_kg=f.ch4 * tj,
        n2o_kg=f.n2o * tj,
        raw=f,
    )


# ── 전력 ─────────────────────────────────────────────────────
def power_t(kwh: float, basis: str = ELEC_DEFAULT) -> float:
    """구매전력. 이미 에너지 단위라 발열량을 쓰지 않습니다."""
    if basis not in ELEC_EF:
        raise EmissionError(f"모르는 전력 기준입니다: {basis}")
    return float(kwh or 0) * ELEC_EF[basis] / 1000


# ── 도시가스 단위 환산 ───────────────────────────────────────
def gas_kwh_to_nm3(kwh: float, basis: str = GAS_BASIS_DEFAULT) -> float:
    """건물에너지 API 는 kWh, 템플릿은 Nm3 을 요구합니다."""
    if basis not in GAS_BASIS:
        raise EmissionError(f"모르는 도시가스 기준입니다: {basis}")
    return float(kwh or 0) / GAS_BASIS[basis]


def gas_t(kwh: float, basis: str = GAS_BASIS_DEFAULT,
          gwp: str = GWP_DEFAULT) -> float:
    """도시가스 kWh 를 바로 배출량으로."""
    return burn("도시가스/LNG", gas_kwh_to_nm3(kwh, basis)).total_t(gwp)


def solar_capacity_kw(elec_kwh: float) -> float:
    """워크시트 산식: 전기사용량 / 365 / 3.5"""
    return float(elec_kwh or 0) / 365 / SOLAR_HOURS


# ── 개략 진단 (1~3단계 화면) ─────────────────────────────────
@dataclass
class Rough:
    """공개자료(전기+가스)만으로 하는 개략 진단.

    estimated_total_t 와 coverage 는 남겨 두었지만 화면에서는 쓰지 않습니다.
    커버리지 표본 4개 중 둘(실상사·금산사)에서 대장 누락이 확인되어
    전제가 흔들렸습니다. 표본이 쌓이면 다시 검토합니다.
    """

    elec_kwh: float = 0.0
    gas_kwh: float = 0.0
    gas_nm3: float = 0.0
    elec_t: float = 0.0
    gas_t: float = 0.0
    subtotal_t: float = 0.0
    people: float = 0.0
    solar_kw: float = 0.0
    elec_basis: str = ""
    elec_ef: float = 0.0
    gas_basis: str = ""
    gwp: str = ""
    coverage: float = 0.0
    estimated_total_t: float = 0.0


def diagnose(
    elec_kwh: float,
    gas_kwh: float,
    temple_type: str = "도심",
    elec_basis: str = ELEC_DEFAULT,
    gas_basis: str = GAS_BASIS_DEFAULT,
    gwp: str = GWP_DEFAULT,
) -> Rough:
    e = power_t(elec_kwh, elec_basis)
    nm3 = gas_kwh_to_nm3(gas_kwh, gas_basis)
    g = burn("도시가스/LNG", nm3).total_t(gwp)
    sub = e + g
    cov = COVERAGE.get(temple_type, 0.90)

    return Rough(
        elec_kwh=float(elec_kwh or 0),
        gas_kwh=float(gas_kwh or 0),
        gas_nm3=nm3,
        elec_t=e,
        gas_t=g,
        subtotal_t=sub,
        people=sub / KOR_PER_CAPITA,          # 공개자료 기준
        solar_kw=solar_capacity_kw(elec_kwh),
        elec_basis=elec_basis,
        elec_ef=ELEC_EF[elec_basis],
        gas_basis=gas_basis,
        gwp=gwp,
        coverage=cov,
        estimated_total_t=sub / cov if cov else sub,
    )


# 공개자료가 못 잡는 몫. 화면에 문장으로만 씁니다.
UNCOVERED_TEXT = ("여기에 LPG·등유·화목·차량·상수도가 더해집니다. "
                  "조사된 사찰 기준으로 전체의 6~14% 였습니다.")


def confidence(elec_kwh: float, gas_kwh: float) -> Tuple[str, str]:
    """진단을 어디까지 믿어도 되는지 스스로 밝힙니다."""
    if elec_kwh > 0 and gas_kwh > 0:
        return ("높음", "전기와 도시가스가 모두 조회되었습니다. 도심형 사찰로 보입니다.")
    if elec_kwh > 0:
        return (
            "보통",
            "전기만 조회되었습니다. 도시가스를 쓰지 않는 산중 사찰일 수 있습니다. "
            "LPG·등유·화목 난방은 공개자료에 없으므로 방문 때 확인해야 합니다.",
        )
    return ("낮음", "공개자료가 없습니다. 방문해서 고지서를 받아야 합니다.")


# ── 대장 누락 자동 탐지 ──────────────────────────────────────
# 면적당 전기. 조사된 사찰은 12~138 kWh/m2 이고 실상사만 672 로 튑니다.
# 518 m2 건물이 연간 348,369 kWh 를 쓸 수는 없습니다.
AREA_KWH_LIMIT = 200
AREA_SAMPLES = [("법문사", 12), ("수국사", 80), ("봉은사", 85),
                ("금산사", 138), ("실상사", 672)]


def area_check(elec_kwh: float, total_area: float) -> Tuple[float, str]:
    """면적당 전기 사용량으로 건축물대장 누락을 의심합니다.

    (kWh/m2, 경고문) 을 돌려줍니다. 이상이 없으면 경고문은 빈 문자열입니다.
    """
    if not total_area or total_area <= 0 or not elec_kwh:
        return (0.0, "")
    per = float(elec_kwh) / float(total_area)
    if per <= AREA_KWH_LIMIT:
        return (per, "")
    sample = " · ".join(f"{n} {v}" for n, v in AREA_SAMPLES[:4])
    return (per, (
        f"면적당 전기가 {per:,.0f} kWh/m²입니다. "
        f"조사된 사찰은 {sample} 수준이므로 {AREA_KWH_LIMIT}을 크게 넘습니다.\n\n"
        "건축물대장에 **빠진 건물이 있을 가능성**이 높습니다. 전기가 부풀려진 것이 "
        "아니라 면적이 모자란 쪽입니다. 현장에서 전각을 확인해 주세요."
    ))
