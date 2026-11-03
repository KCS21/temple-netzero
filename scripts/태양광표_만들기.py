# -*- coding: utf-8 -*-
"""EPSIS 신재생에너지 이용률(태양광)을 받아 「시도 x 월」 발전시간 표를 만듭니다.

    python scripts/태양광표_만들기.py              # 최근 3년 (기본)
    python scripts/태양광표_만들기.py --from 2023 --to 2025

**해마다 자료가 늘어납니다.** 다음 해에는 기간만 바꿔 다시 돌리면 됩니다.
표 파일 이름과 기간은 `solar.py` 가 읽어 화면 문구에까지 그대로 씁니다.

자료: 공공데이터포털 15142242 「한국전력거래소_신재생에너지 이용률」.
포털은 파일을 직접 주지 않고 EPSIS 로 보냅니다(제공형태: 기관자체 다운로드).
EPSIS 화면이 쓰는 그리드 조회를 그대로 부릅니다 - 로그인은 필요 없습니다.

**빈칸은 「이용률 5% 미만 미표기」입니다**(자료 설명에 명시). 결측이 아니라
「5% 아래」라는 정보이므로 **상한 5% 로 채웁니다.** 빼고 평균을 내면 그 달이
부풀어 오릅니다 - 2022년 12월 호남·충청 폭설로 11곳이 비었는데, 그것도
날씨의 일부라 3년 평균에 그대로 넣습니다.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import io
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

URL = "https://epsis.kpx.or.kr/epsisnew/selectKnreUtilRtoGridAjax.ajax"
REFERER = "https://epsis.kpx.or.kr/epsisnew/selectKnreUtilRtoChart.do?menuId=010100"
BLANK_FILL = 5.0            # 「5% 미만 미표기」의 상한
MONTHS = [f"{m:02d}" for m in range(1, 13)]

# 응답은 JS 코드입니다. 값·지역·연월이 한 덩어리로 나옵니다.
_BLOCK = re.compile(
    r'textFormmat\("([^"]*)",1\);\s*localnm="([^"]+)";.*?year = "(\d{4}/\d{2})";',
    re.S)


def fetch(y0: int, y1: int) -> str:
    r = requests.post(
        URL,
        data={"selDate": "month", "beginDate": str(y0), "endDate": str(y1),
              "beginMonth": "01", "endMonth": "12",
              "mapCd": "0", "dataType": "U", "genType": "1"},   # 1 = 태양광
        headers={"User-Agent": "Mozilla/5.0", "Referer": REFERER,
                 "X-Requested-With": "XMLHttpRequest"},
        timeout=60,
    )
    r.raise_for_status()
    return r.text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", type=int, default=2022, dest="y0")
    ap.add_argument("--to", type=int, default=2024, dest="y1")
    a = ap.parse_args()
    years = list(range(a.y0, a.y1 + 1))

    os.makedirs(DATA, exist_ok=True)
    raw = fetch(a.y0, a.y1)
    raw_path = os.path.join(
        DATA, f"EPSIS_신재생이용률_태양광_월별_{a.y0}_{a.y1}_원본.js")
    io.open(raw_path, "w", encoding="utf-8").write(raw)

    got = {(reg, ym): float(v) for v, reg, ym in _BLOCK.findall(raw) if v.strip()}
    regions = sorted({r for r, _ in got})
    if not regions:
        print("** 자료를 읽지 못했습니다. EPSIS 응답 꼴이 바뀌었을 수 있습니다.")
        return 1

    # 달마다 날수가 다릅니다. 연간 발전량은 월 평균을 12로 나누지 않고
    # **월 발전시간 x 그 달 날수**를 더해 냅니다.
    days = {m: sum(calendar.monthrange(y, int(m))[1] for y in years) / len(years)
            for m in MONTHS}

    out = os.path.join(DATA, f"태양광_발전시간_시도월_{a.y0}_{a.y1}.csv")
    filled_all = []
    with io.open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["시도"]
                   + [f"{int(m)}월 이용률(%)" for m in MONTHS]
                   + [f"{int(m)}월 발전시간(h/일)" for m in MONTHS]
                   + ["연평균 발전시간(h/일)", "연간 발전량(kWh/kW·년)",
                      "채움", "채운 칸 수"])
        for reg in regions:
            rates, filled = [], []
            for m in MONTHS:
                vals = []
                for y in years:
                    v = got.get((reg, f"{y}/{m}"))
                    if v is None:
                        v = BLANK_FILL
                        filled.append(f"{y}/{m}")
                    vals.append(v)
                rates.append(sum(vals) / len(vals))
            hours = [x * 24 / 100 for x in rates]
            annual = sum(h * days[m] for h, m in zip(hours, MONTHS))
            filled_all += [(reg, x) for x in filled]
            w.writerow([reg]
                       + [f"{x:.1f}" for x in rates]
                       + [f"{h:.2f}" for h in hours]
                       + [f"{annual / 365:.2f}", f"{annual:.0f}",
                          " ".join(filled), len(filled)])

    print(f"받은 칸 {len(got)} / {len(regions) * 12 * len(years)}"
          f" · 5%로 채운 칸 {len(filled_all)}")
    for reg, ym in filled_all:
        print(f"   {reg} {ym}")
    print(f"원본: {os.path.basename(raw_path)}")
    print(f"표  : {os.path.basename(out)}")
    print()
    print("※ solar.py 의 PERIOD 와 파일 이름을 새 기간으로 맞추십시오.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
