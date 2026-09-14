# -*- coding: utf-8 -*-
"""
실무용 템플릿 채우기
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수화풍

「온실가스 배출량 산정 실무용 템플릿」의 노란 셀(활동량)만 채웁니다.
수식·참조표·서식은 손대지 않으므로, 엑셀에서 열면 5단계 계산이 그대로 돕니다.

  ③Scope1_고정연소   B8:B15 연료명 / D8:D15 활동량
  ④Scope1_이동연소   B8:B14 연료명 / D8:D14 활동량
  ⑤Scope2_전력       D7 구매전력(kWh) / D10 재생에너지(kWh)
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from openpyxl import load_workbook

import emissions as em

TEMPLATE_NAME = "서식_온실가스_배출량_산정_템플릿.xlsx"

SH_FIXED = "③Scope1_고정연소"
SH_MOBILE = "④Scope1_이동연소"
SH_POWER = "⑤Scope2_전력"
SH_SUM = "⑥종합요약"

FIXED_ROWS = range(8, 16)     # 8칸
MOBILE_ROWS = range(8, 15)    # 7칸


class TemplateError(Exception):
    """화면에 그대로 보여줄 수 있는 오류."""


@dataclass
class Activity:
    """템플릿에 넣을 활동량 한 줄.

    같은 연료라도 보일러에 쓰면 고정연소, 차량에 쓰면 이동연소입니다.
    계수는 같지만 들어갈 시트가 다릅니다(템플릿 ④시트 주석 참조).
    scope 를 비워 두면 흔한 쓰임으로 정합니다.
    """

    fuel: str
    qty: float
    scope: str = ""
    note: str = ""

    def __post_init__(self):
        if self.fuel not in em.FUELS:
            raise TemplateError(f"참조표에 없는 연료입니다: {self.fuel}")
        if not self.scope:
            self.scope = em.FUELS[self.fuel].default_scope
        if self.scope not in ("고정연소", "이동연소"):
            raise TemplateError(f"고정연소 또는 이동연소여야 합니다: {self.scope}")

    @property
    def unit(self) -> str:
        return em.FUELS[self.fuel].unit


def find_template(folder: str = "") -> str:
    """서식 파일을 찾습니다."""
    here = folder or os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, TEMPLATE_NAME)
    if not os.path.exists(path):
        raise TemplateError(
            f"서식 파일이 없습니다: {TEMPLATE_NAME}\n"
            "진단 도구와 같은 폴더에 두어야 합니다."
        )
    return path


def _write_rows(ws, rows: Sequence[int], items: List[Activity], label: str) -> None:
    if len(items) > len(rows):
        raise TemplateError(
            f"{label} 칸이 {len(rows)}개인데 {len(items)}개를 넣으려 합니다. "
            "템플릿에서 행을 늘린 뒤 다시 해주세요."
        )
    for i, r in enumerate(rows):
        if i < len(items):
            ws.cell(row=r, column=2).value = items[i].fuel    # B 연료명
            ws.cell(row=r, column=4).value = items[i].qty     # D 활동량
        else:
            ws.cell(row=r, column=2).value = None
            ws.cell(row=r, column=4).value = None


def fill(
    out_path: str,
    temple: str,
    year: int,
    elec_kwh: float,
    activities: Sequence[Activity] = (),
    renewable_kwh: float = 0.0,
    template_path: Optional[str] = None,
    note: str = "",
) -> str:
    """템플릿 사본을 만들어 활동량을 채워 넣습니다. 만들어진 파일 경로를 돌려줍니다."""
    src = template_path or find_template()
    shutil.copyfile(src, out_path)

    wb = load_workbook(out_path)          # 수식 보존 (data_only=False 기본값)
    for need in (SH_FIXED, SH_MOBILE, SH_POWER):
        if need not in wb.sheetnames:
            raise TemplateError(f"서식에 '{need}' 시트가 없습니다. 서식 파일을 확인해 주세요.")

    fixed = [a for a in activities if a.scope == "고정연소"]
    mobile = [a for a in activities if a.scope == "이동연소"]

    _write_rows(wb[SH_FIXED], FIXED_ROWS, fixed, "고정연소")
    _write_rows(wb[SH_MOBILE], MOBILE_ROWS, mobile, "이동연소")

    ws = wb[SH_POWER]
    ws["D7"] = float(elec_kwh or 0)
    ws["D10"] = float(renewable_kwh or 0)

    stamp = dt.date.today().strftime("%Y. %m. %d.")
    tail = f"  |  {note}" if note else ""
    wb[SH_SUM]["B4"] = (
        f"대상: {temple}  |  기준연도: {year}년  |  작성일: {stamp}{tail}"
    )
    wb[SH_SUM]["B5"] = (
        "활동량은 사찰 넷제로 진단 도구가 채웠습니다. "
        "전기·도시가스는 건축HUB 건물에너지 공개자료, 나머지는 현장 조사값입니다."
    )

    wb.save(out_path)
    return out_path


def from_diagnosis(
    out_path: str,
    temple: str,
    year: int,
    elec_kwh: float,
    gas_kwh: float,
    gas_basis: str = em.GAS_BASIS_DEFAULT,
    extra: Sequence[Activity] = (),
    **kw,
) -> Tuple[str, List[Activity]]:
    """개략 진단 결과를 그대로 템플릿에 넣습니다.

    건물에너지 API 의 가스는 kWh 라서 Nm3 으로 바꿔 넣습니다.
    extra 에 현장에서 확인한 LPG·등유·차량연료를 넘기면 함께 들어갑니다.
    """
    acts: List[Activity] = []
    if gas_kwh:
        nm3 = em.gas_kwh_to_nm3(gas_kwh, gas_basis)
        acts.append(Activity("도시가스/LNG", round(nm3, 1), scope="고정연소",
                             note=f"{gas_kwh:,.0f} kWh 를 {gas_basis} 기준으로 환산"))
    acts.extend(extra)

    path = fill(out_path, temple, year, elec_kwh, acts,
                note=f"도시가스 환산기준 {gas_basis}", **kw)
    return path, acts


def preview(elec_kwh: float, activities: Sequence[Activity],
            elec_basis: str = em.ELEC_DEFAULT, gwp: str = em.GWP_DEFAULT) -> dict:
    """템플릿이 낼 값을 미리 계산해 화면에 보여줍니다. (엑셀 없이 확인용)"""
    rows = []
    s1 = 0.0
    for a in activities:
        b = em.burn(a.fuel, a.qty)
        t = b.ar5_t if gwp == "AR5" else b.ar6_t
        s1 += t
        rows.append({"연료": a.fuel, "구분": a.scope, "활동량": f"{a.qty:,.1f} {a.unit}",
                     "발열량": f"{b.hv} MJ/{b.unit}", "TJ": f"{b.tj:.6f}",
                     "배출량": f"{t:.3f} t", "산식": b.formula(gwp)})
    s2 = em.power_t(elec_kwh, elec_basis)
    return {"rows": rows, "scope1_t": s1, "scope2_t": s2, "total_t": s1 + s2,
            "elec_basis": elec_basis, "gwp": gwp}
