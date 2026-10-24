# -*- coding: utf-8 -*-
"""
온실가스 배출량 계산 - 5단계 산정식
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

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


# CH4·N2O 는 **상업·공공** 열입니다 (2026-10-24 개정).
#
# 별표10 의 CH4 는 쓰임에 따라 네 열입니다.
#     [에너지산업] [제조업·건설업] [상업·공공] [가정·기타]
# 템플릿이 **제조업·건설업** 열을 골라 두었는데 사찰은 **상업·공공** 입니다.
# 별표10 원문에서 읽은 값입니다(000_data 의 PDF, 1~2쪽).
#
#   천연가스(LNG)   56,100   1  1  5  5   0.1 0.1   -> 상업·공공 CH4 5
#   액화석유가스 LPG 63,100   1  1  5  5   0.1 0.1   -> 상업·공공 CH4 5
#   기타등유 등유    71,900   3  3 10 10   0.6 0.6   -> 상업·공공 CH4 10
#   가스/디젤오일 경유 74,100  3  3 10 10   0.6 0.6   -> 상업·공공 CH4 10
#
# **N2O 는 네 연료 모두 바뀌지 않습니다.** 상업·공공도 같은 값입니다.
# CO2 와 발열량은 별표12(국가 고유)라 그대로입니다. 별표12 에는 CH4·N2O 가
# 아예 없어서 CH4·N2O 는 별표10 이 유일한 근거입니다(2026-10-24 확인).
#
# **경유·휘발유는 고치지 않았습니다.**
#   - 휘발유는 이동연소 전용입니다
#   - 경유는 별표10 상업·공공이 10 이지만, 이 도구는 경유를 **이동연소로만**
#     씁니다(default_scope). 그리고 엑셀 ②참조표는 연료당 한 줄이라 ③고정연소와
#     ④이동연소가 **같은 줄**을 봅니다. 경유를 10 으로 바꾸면 차량 계산까지
#     바뀌는데, 이동연소는 손대지 말라는 지시입니다.
#     경유를 보일러에 쓰는 사찰이 나오면 참조표에 줄을 따로 만들어야 합니다.
FUELS: Dict[str, Fuel] = {
    "도시가스/LNG":        Fuel("Nm3", 38.9, 56100, 5,   0.1, 0.995, "고정연소"),
    "경유(Diesel)":        Fuel("L",   35.2, 73200, 3,   0.6, 0.995, "이동연소"),
    "등유(Kerosene)":      Fuel("L",   34.2, 73200, 10,  0.6, 0.995, "고정연소"),
    "휘발유(Gasoline)":    Fuel("L",   30.4, 71600, 3,   0.6, 0.99,  "이동연소"),
    "LPG-프로판(LPG1호)":  Fuel("kg",  46.3, 64600, 5,   0.1, 0.99,  "고정연소"),
    "LPG-부탄(LPG3호)":    Fuel("kg",  45.7, 66300, 5,   0.1, 0.99,  "고정연소"),
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


# ── 면적당 에너지 — 그린투게더 원단위와 견주기 ────────────────
#
# **옛 방식(전기만 / 고정 200 kWh/m2)은 폐기되었습니다.**
# 「2025 건물에너지사용량통계」(국토교통부·한국부동산원, 국가승인통계
# 제408003호) 원문으로 원단위의 정의가 확인되었습니다. 14쪽.
#
#   분자  = 전기 + 도시가스 + 지역난방 **합**        (통계집 3쪽)
#   분모  = **주차장을 뺀** 연면적                   (3쪽·8쪽)
#   대표값 = **중간값(50%)**. 평균이 아닙니다        (3쪽)
#   지역  = 에너지절약설계기준 별표1.
#           중부1·2 -> 중부, 제주 -> 남부로 합침     (2쪽·8쪽)
#
# **갱신 시점이 배출계수와 다릅니다.**
#   전력 배출계수  매년 12월
#   원단위 EUI     매년 7월 말  -> 다음은 2027년 7월(2026년 사용량)
#
# 교회·성당도 함께 둡니다. 나중에 대상을 넓힐 때 바로 쓰입니다.
EUI_YEAR = 2025
EUI_SOURCE = "2025 건물에너지사용량통계 (국토교통부·한국부동산원)"
EUI: Dict[str, Dict[str, int]] = {
    "사찰": {"중부": 103, "남부": 79},
    "교회": {"중부": 73,  "남부": 56},
    "성당": {"중부": 71,  "남부": 57},
}
EUI_KIND_DEFAULT = "사찰"

# 원단위가 중간값이라는 것을 화면에 밝혀야 합니다. 전국 사찰의 절반이 그
# 아래라는 뜻이고, 작은 암자가 표본의 절반을 채우므로 큰 절이 중간값을
# 웃도는 것은 그 자체로 이상한 일이 아닙니다.
EUI_NOTE = (
    "원단위는 전국 사찰의 **중간값**입니다(평균이 아닙니다). "
    "절반이 이 아래라는 뜻이고, 작은 암자가 표본의 절반을 채웁니다. "
    "큰 절이 중간값을 웃도는 것은 그 자체로 이상한 일이 아닙니다."
)

# 건물에너지 API 에는 **지역난방 오퍼레이션이 없습니다.**
# getBeHeatUsgInfo 등 다섯 가지를 시험했는데 전부 NO_OPENAPI_SERVICE_ERROR
# 였습니다(2026-10-24 확인). 그래서 분자가 전기+도시가스뿐입니다.
# 지역난방을 쓰는 사찰이면 분자가 모자라 배수가 낮게 나옵니다.
EUI_NUMERATOR_NOTE = "전기 + 도시가스. 지역난방은 건물 단위 API 가 주지 않습니다."


def fuel_kwh(fuel: str, qty: float) -> float:
    """연료 사용량을 kWh 로 바꿉니다. 원단위 분자에 더하려고 씁니다.

    산중 사찰은 도시가스가 없고 LPG·등유로 난방합니다. 4단계에서 현장
    조사값을 넣으면 그때 분자에 더해 배수를 낼 수 있습니다.
    """
    f = FUELS.get(fuel)
    if not f or not qty:
        return 0.0
    return float(qty) * f.hv / MJ_PER_KWH


def eui_base(region2: str, kind: str = EUI_KIND_DEFAULT):
    """그 지역 원단위. 지역을 모르면 None 입니다."""
    return EUI.get(kind, {}).get(region2)


@dataclass
class AreaUse:
    """면적당 에너지 한 묶음. 화면과 CSV 가 이것만 보면 됩니다."""

    region: str = ""              # "중부" | "남부" | ""  (모르면 빈 문자열)
    area: float = 0.0             # 주차장을 뺀 연면적
    parking_area: float = 0.0     # 뺀 옥내 주차장 면적
    elec_kwh: float = 0.0
    gas_kwh: float = 0.0
    other_kwh: float = 0.0        # 현장 조사값(LPG·등유 등)을 kWh 로
    elec_per: float = 0.0         # 전기만 kWh/m2. **늘 보여 줍니다**
    per: float = 0.0              # 전체 kWh/m2. 낼 수 없으면 0
    base: int = 0                 # 그 지역 원단위
    ratio: float = 0.0            # 배수. **낼 수 없으면 0**
    note: str = ""                # 배수를 못 내는 까닭
    suspect: bool = False         # 면적 미등재 의심 (배수를 일부러 안 냄)

    @property
    def has_ratio(self) -> bool:
        return self.ratio > 0

    @property
    def total_kwh(self) -> float:
        """연간 총에너지. 난방을 모르면 0 입니다.

        배수(효율)만으로 줄 세우면 **작은 절부터 가게 됩니다.** 69곳에서
        한마음선원은 배수로 14위인데 총량으로는 2위였습니다(10,482m2).
        그래서 총량을 늘 배수 옆에 함께 둡니다.
        """
        heat = self.gas_kwh + self.other_kwh
        return (self.elec_kwh + heat) if heat > 0 else 0.0


# 도시가스가 0 이고 현장 조사값도 없으면 배수를 내지 않습니다.
#
# 산중 사찰은 도시가스가 안 들어가고 LPG·등유로 난방합니다. API 는 그
# 연료를 주지 않으므로 **분자에 난방이 통째로 빠집니다.** 그대로 배수를
# 내면 금산사가 1.34배로 「그럭저럭」처럼 보이는데, 실제 총에너지는 이보다
# 큽니다. 낮은 배수를 보여 주면 방문 순서에서 뒤로 밀리는데 정작 LPG 를
# 가장 많이 쓰는 절일 수 있습니다.
#
# 이것은 한계이지 버그가 아닙니다. 숨기지 않고 화면에 적습니다.
NO_HEAT_NOTE = "난방 연료 미확인, 현장 확인 필요"

# 전통 전각 0동 + 배수가 터무니없이 크면 「높다」가 아니라 「못 믿는다」입니다.
#
# 69곳에서 보현사가 16.04배였고 그다음(백양사)이 2.22배였습니다. 7배 차이입니다.
# 690m2 에 1,652 kWh/m2 는 전기가 많은 것이 아니라 **면적이 덜 잡힌** 것입니다.
# 3.0 은 그 분포에서 나온 값입니다(2.22 와 16.04 사이).
#
# **전통 전각 0동**을 함께 보는 까닭은, 목조 전각 미등재가 면적 누락의 주된
# 까닭이기 때문입니다(7장). 56곳 중 29곳이 전통 0동이었습니다.
SUSPECT_RATIO = 3.0
SUSPECT_NOTE = "면적미등재의심"
SUSPECT_TEXT = (
    "면적 일부만 잡힌 것으로 의심됩니다. 현장에서 전각 목록을 확인해 주세요."
)


def area_use(
    elec_kwh: float,
    gas_kwh: float,
    area: float,
    region2: str,
    parking_area: float = 0.0,
    other_kwh: float = 0.0,
    kind: str = EUI_KIND_DEFAULT,
    trad_count: int = -1,
) -> AreaUse:
    """면적당 에너지와 지역 원단위 대비 배수.

    area 는 **주차장을 뺀 뒤**의 연면적을 넣어 주십시오.
    parking_area 는 화면에 "얼마를 뺐는지" 밝히려고 함께 받습니다.

    **판정 문구는 붙이지 않습니다.** 구간을 그을 표본이 아직 없습니다.
    50곳을 돌려 분포를 본 뒤에 넣습니다.
    """
    u = AreaUse(
        region=region2 or "",
        area=float(area or 0),
        parking_area=float(parking_area or 0),
        elec_kwh=float(elec_kwh or 0),
        gas_kwh=float(gas_kwh or 0),
        other_kwh=float(other_kwh or 0),
    )
    if u.area <= 0:
        u.note = "연면적을 알 수 없어 면적당 값을 내지 못했습니다."
        return u

    u.elec_per = u.elec_kwh / u.area
    u.base = eui_base(u.region, kind) or 0

    heat = u.gas_kwh + u.other_kwh
    if heat <= 0:
        u.note = NO_HEAT_NOTE
        return u

    u.per = (u.elec_kwh + heat) / u.area
    if not u.base:
        u.note = "지역을 알 수 없어 원단위와 견주지 못했습니다."
        return u

    ratio = u.per / u.base

    # 면적이 덜 잡힌 것으로 보이면 배수를 내지 않습니다.
    # 「높다」가 아니라 「못 믿는다」로 갈라야 합니다.
    if trad_count == 0 and ratio > SUSPECT_RATIO:
        u.suspect = True
        u.note = SUSPECT_NOTE
        return u

    u.ratio = ratio
    return u


# ── 두 축 — 배수(효율)와 총량(규모) ──────────────────────────
#
# 처방이 다르므로 섞지 않는 것이 핵심입니다.
# 왼쪽 위는 **낭비를 줄이는** 일이고, 왼쪽 아래는 이미 효율적이지만
# 규모가 커서 **설비를 바꿀 값어치**가 있는 절입니다.
#
# 기준선을 임의로 정하지 않습니다.
#   배수 1.0  — 원단위 자체가 전국 사찰 중간값이므로
#   총량      — **그때그때 모은 절들의 중간값**. 절대 기준이 아닙니다
QUAD_RATIO = 1.0
QUAD = {
    (True, True): "효율 개선 후보",
    (True, False): "소규모 · 효율 점검",
    (False, True): "설비·태양광 후보",
    (False, False): "후순위",
}


def total_median(totals) -> float:
    """총량의 중간값. 0 이나 빈 값은 빼고 셈합니다."""
    vals = sorted(v for v in totals if v and v > 0)
    if not vals:
        return 0.0
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def quadrant(ratio: float, total_kwh: float, median: float) -> str:
    """네 칸 중 어디인지. 둘 중 하나라도 없으면 빈 문자열입니다.

    **단일 사찰 화면에서는 쓰지 마십시오.** 총량 기준선이 표본의 중간값이라
    한 곳만 보고는 정할 수 없습니다. 여러 절을 모아 보는 화면에서만 씁니다.
    """
    if not ratio or not total_kwh or not median:
        return ""
    return QUAD[(ratio >= QUAD_RATIO, total_kwh >= median)]
