# -*- coding: utf-8 -*-
"""
명단 일괄 조회
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

`녹색사찰_명단.csv` 를 읽어 한 곳씩 조회하고 `사찰기록.csv` 에 쌓습니다.

규모
----
한 곳당 주소 1 + 건축물대장 3 + 건물에너지 24 = **약 28회**.
69곳이면 약 1,900회이고 하루 한도 10,000건 안쪽입니다.
곳당 30~40초라 전체 40분 안팎입니다.

그래서 지켜야 할 것
-------------------
- **끊어서 돌립니다.** 한 묶음이 끝날 때마다 저장하므로 중간에 멈춰도
  처음부터 다시 하지 않습니다
- 이미 기록에 있는 곳은 **건너뜁니다**
- 한 곳이 실패해도 **멈추지 않고** 사유를 적고 넘어갑니다
"""
from __future__ import annotations

import csv
import io
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import bldengy
import bldrgst
import emissions as em
import juso
import portal
import store

LIST_NAME = "녹색사찰_명단.csv"

# 명단 열 이름. 원본 엑셀을 정리한 것이라 이름이 고정되어 있습니다.
COL_NO, COL_NAME, COL_ADDR = "번호", "사찰명", "주소"
# 주지스님·연락처·종단은 읽지 않습니다. 도구 어디에도 개인정보를 두지
# 않는다는 규칙입니다(작업지시 03 3장). 명단에 그런 열이 있어도 무시합니다.


class BatchError(Exception):
    """화면에 그대로 보여줄 수 있는 오류."""


@dataclass
class Target:
    """명단 한 줄."""

    no: str = ""
    name: str = ""
    addr: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    def label(self) -> str:
        return f"{self.no}. {self.name}"


def read_list(path_or_bytes) -> List[Target]:
    """명단을 읽습니다. 파일 경로나 올린 파일의 바이트를 받습니다."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        text = None
        for enc in ("utf-8-sig", "utf-8", "cp949"):
            try:
                text = bytes(path_or_bytes).decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise BatchError("명단 파일의 글자를 읽지 못했습니다. 엑셀에서 "
                             "CSV UTF-8 로 다시 저장해 주세요.")
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        p = str(path_or_bytes)
        if not os.path.exists(p):
            raise BatchError(f"명단 파일이 없습니다: {os.path.basename(p)}")
        rows = None
        for enc in ("utf-8-sig", "utf-8", "cp949"):
            try:
                with io.open(p, encoding=enc, newline="") as f:
                    rows = list(csv.DictReader(f))
                break
            except UnicodeDecodeError:
                continue
        if rows is None:
            raise BatchError("명단 파일의 글자를 읽지 못했습니다.")

    if not rows:
        raise BatchError("명단이 비어 있습니다.")
    need = {COL_NAME, COL_ADDR}
    missing = need - set(rows[0].keys())
    if missing:
        raise BatchError(
            f"명단에 필요한 열이 없습니다: {', '.join(sorted(missing))}\n\n"
            f"열 이름은 {COL_NO} · {COL_NAME} · {COL_ADDR} 이어야 합니다."
        )

    out = []
    for r in rows:
        if not (r.get(COL_NAME) or "").strip():
            continue
        out.append(Target(
            no=(r.get(COL_NO) or "").strip(),
            name=(r.get(COL_NAME) or "").strip(),
            addr=(r.get(COL_ADDR) or "").strip(),
            raw=r,
        ))
    return out


def done_map(folder: str = "") -> Dict[str, str]:
    """이미 조회한 곳 -> 실패사유(성공이면 빈 문자열).

    명단 번호로 봅니다. 번호가 없으면 사찰명으로 봅니다.
    """
    out = {}
    for r in store.load(folder):
        no = str(r.get("번호", "")).strip()
        key = no if no else str(r.get("사찰", "")).strip()
        out[key] = (r.get("실패사유") or "").strip()
    return out


def done_keys(folder: str = "") -> set:
    return set(done_map(folder))


# 명단 주소에 괄호가 붙은 곳이 10곳 있습니다.
#   "고창군 아산면 도솔길 194-77 (삼인리, 참당암)"
# 괄호 안이 검색어에 섞이면 0건이 됩니다. 떼면 정상으로 찾습니다.
_PAREN = re.compile("[(][^)]*[)]")


def address_tries(addr: str, name: str = "") -> List[str]:
    """조회에 써 볼 검색어를 순서대로 돌려줍니다.

    괄호를 뗀 것을 먼저 쓰고, 안 되면 원본, 그래도 안 되면 절 이름입니다.
    이름으로 찾는 것은 마지막입니다. 같은 이름의 다른 절이 흔하기 때문입니다.
    """
    out, seen = [], set()
    for cand in (_PAREN.sub(" ", addr), addr, name):
        c = " ".join((cand or "").split())
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def pick_best(rows: List, name: str):
    """후보 중 명단 사찰명과 건물명이 맞는 것을 고릅니다.

    없으면 첫 번째를 씁니다. 주소로 찾은 것이라 대개 첫 번째가 맞습니다.
    """
    key = (name or "").replace(" ", "")
    if key:
        for j in rows:
            if (j.bdNm or "").replace(" ", "") == key:
                return j
        for j in rows:
            if key in (j.bdNm or "").replace(" ", ""):
                return j
    return rows[0]


def _fail_row(t: Target, year: int, why: str) -> Dict[str, str]:
    """실패해도 명단 정보는 남겨 둡니다. 나중에 손으로 채울 수 있게."""
    return {
        "번호": t.no, "사찰": t.name,
        "지번주소": t.addr, "조회연도": str(year),
        "신뢰도": "낮음", "실패사유": why,
    }


# 한 곳에 쓸 수 있는 시간 상한(초). 정상이면 10~20초면 끝납니다.
# 제공기관 서버가 아플 때 한 곳에서 34분을 쓴 일이 있어 상한을 둡니다.
BUDGET = 180


def run_one(t: Target, year: int, confm_key: str, service_key: str,
            budget: int = BUDGET) -> Dict[str, str]:
    """한 곳을 조회해 기록 한 줄을 만듭니다. 실패해도 예외를 내지 않습니다."""
    deadline = time.time() + budget
    # ── 1. 주소 ──
    rows, last = [], ""
    for kw in address_tries(t.addr, t.name):
        try:
            rows, _ = juso.search(kw, confm_key, per_page=5)
        except juso.JusoError as e:
            last = str(e)
            continue
        if rows:
            break
    if not rows:
        return _fail_row(t, year, f"주소 못 찾음 ({last or '결과 없음'})")

    j = pick_best(rows, t.name)
    p = j.building_params()

    # ── 2. 건축물대장 ──
    dongs, recap, jjg = [], None, []
    try:
        dongs = bldrgst.fetch_dongs(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                    p["ji"], service_key, p["platGbCd"])
        jjg = bldrgst.fetch_jijigu(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                   p["ji"], service_key, p["platGbCd"])
    except portal.PortalError as e:
        return _fail_row(t, year, f"건축물대장 실패 ({e})")

    s = bldrgst.summarize(dongs) if dongs else {}
    area = s.get("total_area", 0.0)

    # ── 3. 건물에너지 ──
    try:
        data = bldengy.fetch_year(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                  p["ji"], year, service_key,
                                  plat_gb=p["platGbCd"],
                                  timeout=8, retries=1, deadline=deadline)
    except portal.PortalError as e:
        return _fail_row(t, year, f"건물에너지 실패 ({e})")

    es = bldengy.summarize(data["elec"])
    gs = bldengy.summarize(data["gas"])
    r = em.diagnose(es["total"], gs["total"],
                    "산중" if j.is_mountain else "도심")
    lvl, _ = em.confidence(es["total"], gs["total"])
    per, warn = em.area_check(es["total"], area)

    why = ""
    if not dongs:
        why = "건물 없음"
    if es["total"] == 0 and gs["total"] == 0:
        why = (why + " · " if why else "") + "에너지 자료 없음"

    return {
        "번호": t.no, "사찰": t.name,
        "지번주소": j.jibunAddr, "도로명주소": j.roadAddr, "조회연도": str(year),
        "Scope1(t)": f"{r.gas_t:.2f}", "Scope2(t)": f"{r.elec_t:.2f}",
        "공개자료 배출량(t)": f"{r.subtotal_t:.2f}",
        "전기(kWh)": f"{es['total']:.0f}", "가스(kWh)": f"{gs['total']:.0f}",
        "면적당 전기(kWh/m2)": f"{per:.0f}" if per else "",
        "난방부담 지표": f"{es['ratio']:.2f}" if es.get("ratio") else "",
        "동수": str(s.get("count", 0)),
        "연면적(m2)": f"{area:.1f}" if area else "",
        "전통 동수": str(s.get("trad_count", 0)),
        "신식 동수": str(s.get("modern_count", 0)),
        "태양광 필요용량(kW)": f"{r.solar_kw:.0f}",
        "신뢰도": lvl,
        "대장누락 의심": "예" if warn else "아니오",
        "제외된 자료(건)": str(data.get("dropped", 0)),
        "실패사유": why,
        "전력 기준": r.elec_basis, "도시가스 기준": r.gas_basis, "GWP": r.gwp,
        "용도지역": " / ".join(jjg),
        "시군구": p["sigunguCd"], "법정동": p["bjdongCd"],
        "번": p["bun"], "지": p["ji"], "대지구분": p["platGbCd"],
    }


def run(
    targets: List[Target],
    year: int,
    confm_key: str,
    service_key: str,
    limit: int = 10,
    skip_done: bool = True,
    retry_failed: bool = False,
    folder: str = "",
    progress: Optional[Callable[[int, int, Target, str], None]] = None,
) -> dict:
    """명단을 차례로 조회합니다.

    한 번에 `limit` 곳까지만 합니다. 69곳을 한 번에 돌리지 않기 위해서입니다.
    **한 곳이 끝날 때마다 바로 저장**하므로 중간에 멈춰도 이어집니다.

    progress(지금까지, 이번에 할 수, 조회 중인 곳, 결과) 로 진행을 알립니다.
    """
    todo = list(targets)
    have = done_map(folder)
    if retry_failed:
        # 실패로 남은 곳만 다시 합니다. 성공한 곳은 건드리지 않습니다.
        todo = [t for t in todo if have.get(t.no or t.name, "_none_")]
    elif skip_done:
        todo = [t for t in todo if (t.no or t.name) not in have]

    left = len(todo)                     # 이번 묶음 뒤에도 남는 수를 세려고
    if limit and limit > 0:
        todo = todo[:limit]

    ok, failed = 0, []
    total = len(todo)
    for i, t in enumerate(todo, 1):
        row = run_one(t, year, confm_key, service_key)
        why = (row.get("실패사유") or "").strip()
        store.save(row, folder)          # 한 곳씩 바로 저장 = 끊겨도 이어짐
        if why:
            failed.append((t, why))
        else:
            ok += 1
        if progress:
            progress(i, total, t, why or "성공")

    return {
        "total": total,                  # 이번에 실제로 돌린 수
        "ok": ok,
        "failed": failed,
        "done_before": len(targets) - left,   # 이미 있어서 건너뛴 수
        "remaining": left - total,            # 이번 묶음 뒤에도 남은 수
    }
