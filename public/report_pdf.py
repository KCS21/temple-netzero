# -*- coding: utf-8 -*-
"""
자가진단 결과 PDF — A4 세로 한 장 (작업지시 10 4장)
불교탄소중립실천단 지수광풍

글꼴은 같은 폴더 `fonts/` 의 나눔고딕(SIL OFL)입니다. 서버에 한글 글꼴이
없어도 찍히도록 저장소에 함께 둡니다.

**한 장을 넘기지 않습니다.** 자동 쪽 넘김을 끄고, 월별 막대는 자리가
남을 때만 그립니다.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from typing import Optional

from fpdf import FPDF

from public import selfcheck as sc

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_R = os.path.join(HERE, "fonts", "NanumGothic-Regular.ttf")
FONT_B = os.path.join(HERE, "fonts", "NanumGothic-Bold.ttf")

DARK = (0x1E, 0x56, 0x31)      # #1E5631
GREEN = (0x2F, 0x6B, 0x3F)     # #2F6B3F
PALE = (0xE4, 0xF0, 0xE6)      # #E4F0E6
INK = (0x22, 0x22, 0x22)
GREY = (0x66, 0x66, 0x66)

KST = dt.timezone(dt.timedelta(hours=9))
FOOT_REQUEST = "무료 컨설팅 요청: 홈페이지의 컨설팅 요청"


def today() -> dt.date:
    """배포 서버가 UTC 라 한국 날짜로 못박습니다(CLAUDE.md 7장 `_kst`)."""
    return dt.datetime.now(KST).date()


def file_name(name: str, day: Optional[dt.date] = None) -> str:
    """`지수광풍_자가진단_{절 이름}_{YYYYMMDD}.pdf`. 파일 이름에 못 쓰는 글자는 뺍니다."""
    safe = re.sub(r'[\\/:*?"<>|\s]+', "", name or "") or "사찰"
    return f"지수광풍_자가진단_{safe}_{(day or today()):%Y%m%d}.pdf"


class _Pdf(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("Nanum", "", FONT_R)
        self.add_font("Nanum", "B", FONT_B)
        self.set_auto_page_break(False)
        self.set_margins(16, 14, 16)
        self.add_page()

    @property
    def w_in(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def heading(self, text: str):
        self.ln(2.5)
        self.set_font("Nanum", "B", 12)
        self.set_text_color(*DARK)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        y = self.get_y()
        self.set_draw_color(*GREEN)
        self.set_line_width(0.3)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(1.5)
        self.set_text_color(*INK)

    def para(self, text: str, size: float = 10, h: float = 5.2, color=INK):
        self.set_font("Nanum", "", size)
        self.set_text_color(*color)
        self.multi_cell(0, h, text, new_x="LMARGIN", new_y="NEXT")


def build(r: sc.Result, contact: str = "", day: Optional[dt.date] = None) -> bytes:
    p = _Pdf()

    # ── 머리 ──
    p.set_fill_color(*DARK)
    p.rect(0, 0, p.w, 24, style="F")
    p.set_xy(p.l_margin, 6)
    p.set_text_color(255, 255, 255)
    p.set_font("Nanum", "B", 15)
    p.cell(0, 7, "불교탄소중립실천단 지수광풍", new_x="LMARGIN", new_y="NEXT")
    p.set_font("Nanum", "", 10.5)
    p.cell(0, 6, "사찰 탄소중립 자가진단 결과", new_x="LMARGIN", new_y="NEXT")
    p.set_y(28)

    # ── 절 이름·주소·조회연도·만든 날 ──
    p.set_text_color(*INK)
    p.set_font("Nanum", "B", 13)
    p.cell(0, 7, r.name or "사찰", new_x="LMARGIN", new_y="NEXT")
    p.set_font("Nanum", "", 9.5)
    p.set_text_color(*GREY)
    when = f"{r.year}년 공개 자료" if (r.mode == sc.MODE_LOOKUP and r.year) \
        else "입력하신 고지서 값"
    p.multi_cell(0, 5, f"{r.addr or '주소 미입력'}\n{when} · 만든 날 "
                       f"{(day or today()):%Y. %m. %d.}",
                 new_x="LMARGIN", new_y="NEXT")

    # ── 숫자 세 개 ──
    p.ln(3)
    gap = 4
    bw = (p.w_in - gap * 2) / 3
    y0 = p.get_y()
    boxes = (("연간 배출량", f"{r.total_t:,.1f} t"),
             ("국민 환산", f"{r.people:,.1f}명분"),
             ("태양광 필요용량", f"{r.solar_kw:,.0f} kW"))
    for i, (lbl, val) in enumerate(boxes):
        x = p.l_margin + i * (bw + gap)
        p.set_fill_color(*PALE)
        p.rect(x, y0, bw, 22, style="F")
        p.set_xy(x, y0 + 3)
        p.set_font("Nanum", "", 9.5)
        p.set_text_color(*GREEN)
        p.cell(bw, 5, lbl, align="C")
        p.set_xy(x, y0 + 10)
        p.set_font("Nanum", "B", 15)
        p.set_text_color(*DARK)
        p.cell(bw, 8, val, align="C")
    p.set_y(y0 + 24)
    p.para(f"전기 {r.elec_kwh:,.0f} kWh · 도시가스 {r.gas_kwh:,.0f} kWh"
           + (f" · 등유 {r.kero_l:,.0f} L" if r.kero_l else "")
           + (f" · LPG {r.lpg_kg:,.0f} kg" if r.lpg_kg else "")
           + f"  (국민 1인당 {sc.em.KOR_PER_CAPITA} t, 하루 {sc.em.SOLAR_HOURS}시간 발전 기준)",
           size=8.5, h=4.5, color=GREY)

    # ── 유형 ──
    p.heading("우리 절 유형")
    p.set_font("Nanum", "B", 11.5)
    p.set_text_color(*DARK)
    p.cell(0, 6, r.kind, new_x="LMARGIN", new_y="NEXT")
    if r.ratio is not None:
        p.para(sc.ratio_text(r.ratio), size=9.5, color=GREY)

    # ── 먼저 해 볼 일 ──
    p.heading("먼저 해 볼 일")
    for i, t in enumerate(r.todo, 1):
        p.para(f"{i}. {t}", size=10, h=5.2)
        p.ln(0.6)

    # ── 월별 전기 막대 (자료가 있고 자리가 남을 때만) ──
    if r.monthly and any(r.monthly.values()):
        p.heading("월별 전기 사용량 (kWh)")
        _bars(p, r.monthly, height=34)

    # ── 지원사업 · 한계 ──
    p.heading("지원사업")
    p.para(sc.SUPPORT_TEXT, size=9.5, h=5)
    p.heading("이 진단의 한계")
    for t in r.notes:
        p.para(f"- {t}", size=9, h=4.8, color=GREY)

    # ── 바닥 ──
    foot = FOOT_REQUEST + (f"   ·   {contact}" if contact else "")
    p.set_fill_color(*PALE)
    p.rect(0, p.h - 16, p.w, 16, style="F")
    p.set_xy(p.l_margin, p.h - 11.5)
    p.set_font("Nanum", "B", 10)
    p.set_text_color(*DARK)
    p.cell(0, 6, foot, align="C")
    return bytes(p.output())


def _bars(p: _Pdf, monthly: dict, height: float = 34):
    keys = sorted(monthly, key=sc._month_of)
    vals = [float(monthly[k] or 0) for k in keys]
    top = max(vals) or 1
    x0, y0 = p.l_margin, p.get_y() + 5      # 맨 높은 막대의 숫자 자리
    n = len(vals)
    slot = p.w_in / max(n, 1)
    bw = slot * 0.62
    base = y0 + height
    p.set_draw_color(*GREY)
    p.set_line_width(0.2)
    p.line(x0, base, x0 + p.w_in, base)
    for i, (k, v) in enumerate(zip(keys, vals)):
        h = height * v / top
        x = x0 + i * slot + (slot - bw) / 2
        if v > 0:
            p.set_fill_color(*GREEN)
            p.rect(x, base - h, bw, h, style="F")
        p.set_font("Nanum", "", 7)
        p.set_text_color(*GREY)
        p.set_xy(x0 + i * slot, base + 0.5)
        p.cell(slot, 4, f"{sc._month_of(k)}월", align="C")
        if v > 0:
            p.set_xy(x0 + i * slot, base - h - 4)
            p.cell(slot, 4, f"{v:,.0f}", align="C")
        else:
            p.set_xy(x0 + i * slot, base - 4.5)
            p.cell(slot, 4, "자료 없음", align="C")
    p.set_y(base + 5.5)
