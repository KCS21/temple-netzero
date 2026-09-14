# -*- coding: utf-8 -*-
"""
사찰 기록 저장·불러오기
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수화풍

진단한 사찰을 같은 폴더의 `사찰기록.csv` 에 한 줄씩 쌓습니다.
50개 로드맵이 목표이므로 한 곳 보고 끝나면 안 됩니다.

왜 CSV 인가
-----------
시니어 회원이 **엑셀로 바로 열 수 있어야** 합니다(2장).
UTF-8 BOM 으로 저장해야 엑셀이 한글을 깨뜨리지 않습니다.

같은 지번·같은 해를 다시 진단하면 **덮어씁니다.** 줄이 쌓이면
어느 것이 최신인지 시니어가 판단해야 하는데, 그건 2장 위배입니다.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import shutil
from typing import Dict, List, Optional

FILE_NAME = "사찰기록.csv"

# 순서가 곧 엑셀 열 순서입니다. 앞쪽에 사람이 먼저 볼 것을 둡니다.
#
# 열 구성은 2026-09-14 에 바뀌었습니다(작업지시 03 Q7).
#  - 명단 열(번호·사찰명)을 앞에 붙였습니다.
#    **주지스님·연락처·종단은 넣지 않습니다**(작업지시 03 3장 개인정보 규칙).
#    2026-09-14 에 한 번 들어갔다가 뺐습니다. 다시 넣지 마십시오
#  - 방문 관리 열(상태·메모)을 넣었습니다. 사람이 채웁니다
#  - 화면 표시용 중간값(국민 환산, 가스 Nm3, 전기/가스 배출량 따로)은 뺐습니다.
#    Scope1·Scope2·소계만 있으면 로드맵을 쓸 수 있습니다
COLUMNS = [
    # ── 명단에서 ──
    "번호", "사찰",
    # ── 방문 관리 (사람이 채움) ──
    "방문 상태", "메모",
    # ── 조회 결과 ──
    "지번주소", "도로명주소", "조회연도",
    "Scope1(t)", "Scope2(t)", "공개자료 배출량(t)",
    "전기(kWh)", "가스(kWh)", "면적당 전기(kWh/m2)", "난방부담 지표",
    "동수", "연면적(m2)", "전통 동수", "신식 동수", "태양광 필요용량(kW)",
    "신뢰도", "대장누락 의심", "제외된 자료(건)", "실패사유",
    "전력 기준", "도시가스 기준", "GWP",
    "용도지역",
    # ── 다시 조회할 때 쓰는 값 ──
    "시군구", "법정동", "번", "지", "대지구분",
    "저장시각",
]

# 사람이 채우는 열은 다시 조회해도 덮어쓰지 않습니다.
KEEP_ON_UPDATE = ("방문 상태", "메모")

VISIT_STATES = ("미방문", "예정", "완료")

# 같은 곳인지 무엇으로 보는가.
#
# 명단 번호가 있으면 **번호**가 정체성입니다. 일괄 조회에서 첫 시도가 실패하면
# 지번주소 칸에 명단 주소가 들어가고, 다시 조회해 성공하면 실제 지번이
# 들어옵니다. 주소로 보면 같은 절이 두 줄이 됩니다. 실제로 그랬습니다.
#
# 화면에서 손으로 저장한 것은 번호가 없으므로 지번주소로 봅니다.
def _ident(row: Dict[str, str]) -> str:
    no = str(row.get("번호", "")).strip()
    return f"no:{no}" if no else "addr:" + str(row.get("지번주소", "")).strip()


class StoreError(Exception):
    """화면에 그대로 보여줄 수 있는 오류."""


def path(folder: str = "") -> str:
    here = folder or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, FILE_NAME)


def _key(row: Dict[str, str]) -> tuple:
    return (_ident(row), str(row.get("조회연도", "")).strip())


def load(folder: str = "") -> List[Dict[str, str]]:
    """저장된 기록을 전부 읽습니다. 파일이 없으면 빈 목록."""
    p = path(folder)
    if not os.path.exists(p):
        return []
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with io.open(p, encoding=enc, newline="") as f:
                return [dict(r) for r in csv.DictReader(f)]
        except UnicodeDecodeError:
            continue
    raise StoreError(
        f"`{FILE_NAME}` 을 읽지 못했습니다.\n\n"
        "엑셀에서 열어 두셨다면 닫고 다시 해주세요."
    )


def _write(rows: List[Dict[str, str]], folder: str = "") -> str:
    p = path(folder)
    # 엑셀에서 열어 둔 채로 저장하면 실패합니다. 있던 것을 잃지 않도록 백업 먼저.
    if os.path.exists(p):
        try:
            shutil.copyfile(p, p + ".bak")
        except OSError:
            pass
    try:
        with io.open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in COLUMNS})
    except PermissionError:
        raise StoreError(
            f"`{FILE_NAME}` 에 쓰지 못했습니다.\n\n"
            "엑셀에서 이 파일을 열어 두셨다면 **닫고 다시 눌러 주세요.**"
        )
    return p


def save(row: Dict, folder: str = "") -> tuple:
    """한 곳을 저장합니다. 같은 지번·같은 해가 있으면 덮어씁니다.

    (전체 기록, 덮어썼는지) 를 돌려줍니다.
    """
    rows = load(folder)
    row = {c: row.get(c, "") for c in COLUMNS}
    row["저장시각"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    k = _key(row)
    replaced = False
    for i, old in enumerate(rows):
        if _key(old) == k:
            # 사람이 채운 칸은 다시 조회해도 지키십시오.
            for c in KEEP_ON_UPDATE:
                if old.get(c) and not row.get(c):
                    row[c] = old[c]
            rows[i] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)

    # 기본값은 **병합한 뒤에** 넣습니다. 먼저 넣으면 "미방문" 이 채워진 값으로
    # 보여 사람이 적어 둔 "완료" 를 덮어씁니다. 실제로 그랬습니다.
    if not row.get("방문 상태"):
        row["방문 상태"] = VISIT_STATES[0]

    _write(rows, folder)
    return rows, replaced


def remove(jibun: str, year, folder: str = "") -> List[Dict[str, str]]:
    """한 줄을 지웁니다. 번호로도 지번주소로도 찾습니다."""
    rows = load(folder)
    want, yr = str(jibun).strip(), str(year).strip()
    left = [r for r in rows
            if not (str(r.get("조회연도", "")).strip() == yr
                    and want in (str(r.get("번호", "")).strip(),
                                 str(r.get("지번주소", "")).strip()))]
    if len(left) != len(rows):
        _write(left, folder)
    return left


def as_csv_bytes(folder: str = "") -> bytes:
    """내려받기용. 엑셀이 한글을 깨뜨리지 않도록 BOM 을 붙입니다."""
    rows = load(folder)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in COLUMNS})
    return buf.getvalue().encode("utf-8-sig")


def _num(v, default=None) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def benchmark(rows: List[Dict[str, str]]) -> dict:
    """쌓인 기록에서 비교 기준을 뽑습니다.

    표본이 적으면 평균이 흔들리므로 몇 곳으로 낸 값인지 함께 돌려줍니다.
    대장 누락이 의심되는 곳은 면적당 계산에서 빼야 합니다(7장).
    """
    tons = [t for t in (_num(r.get("공개자료 배출량(t)")) for r in rows) if t]
    clean = [r for r in rows if str(r.get("대장누락 의심", "")).strip() != "예"]
    per = [p for p in (_num(r.get("면적당 전기(kWh/m2)")) for r in clean) if p]

    def avg(xs):
        return sum(xs) / len(xs) if xs else None

    return {
        "count": len(rows),
        "ton_avg": avg(tons), "ton_n": len(tons),
        "ton_max": max(tons) if tons else None,
        "ton_min": min(tons) if tons else None,
        "per_avg": avg(per), "per_n": len(per),
        "suspect": len(rows) - len(clean),
    }


def priority(rows: List[Dict[str, str]]) -> tuple:
    """방문 우선순위. (판단 가능한 곳, 판단 보류한 곳) 을 돌려줍니다.

    **점수를 합산해 하나의 숫자로 만들지 않습니다**(2장). 세 지표를 나란히
    보이고 사람이 고릅니다. 정렬은 배출 규모 순입니다. 그게 가장 굵은 기준이라
    첫 줄로 삼을 뿐, 나머지 둘을 덮지 않습니다.

    신뢰도 "낮음" 이나 대장 누락 의심은 **"우선순위가 낮다" 가 아니라
    "자료가 부족해 판단을 보류한다"** 입니다. 섞으면 안 됩니다.
    """
    ready, hold = [], []
    for r in rows:
        lvl = (r.get("신뢰도") or "").strip()
        suspect = (r.get("대장누락 의심") or "").strip() == "예"
        why = (r.get("실패사유") or "").strip()
        if lvl == "낮음" or suspect or why:
            reason = why or ("대장 누락 의심" if suspect else "신뢰도 낮음")
            hold.append(dict(r, _보류사유=reason))
        else:
            ready.append(r)

    ready.sort(key=lambda r: -(_num(r.get("공개자료 배출량(t)")) or 0))
    hold.sort(key=lambda r: ((r.get("_보류사유") or ""), r.get("사찰") or ""))
    return ready, hold


def heating_flag(r: Dict[str, str]) -> str:
    """난방 부담 지표 읽기. 2.5 이상이면 개선 여지가 있다고 봅니다."""
    v = _num(r.get("난방부담 지표"))
    if v is None:
        return "—"
    return f"{v:.1f}배" + ("  ◀" if v >= 2.5 else "")


def solar_room(r: Dict[str, str]) -> str:
    """태양광을 올릴 데가 있는가. 신식 건물이 없으면 필요용량이 커도 소용없습니다."""
    kw = _num(r.get("태양광 필요용량(kW)")) or 0
    modern = _num(r.get("신식 동수")) or 0
    if not kw:
        return "—"
    if modern <= 0:
        return f"{kw:,.0f} kW (신식 0동)"
    return f"{kw:,.0f} kW / 신식 {modern:.0f}동"


# ── 여러 CSV 합치기 ──────────────────────────────────────────
# 69곳을 여러 분이 나눠 돌리면 파일이 갈라집니다. 원칙은 한 사람이 모으는
# 것이지만(2장), 나눠 돌린 것을 합칠 수단은 있어야 합니다.
# 같은 곳·같은 해가 겹치면 **저장시각이 늦은 것**만 남깁니다.

def read_bytes(blob: bytes) -> List[Dict[str, str]]:
    """올린 CSV 한 개를 읽습니다."""
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = bytes(blob).decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise StoreError("CSV 의 글자를 읽지 못했습니다. "
                         "엑셀에서 'CSV UTF-8' 로 다시 저장해 주세요.")
    rows = [dict(r) for r in csv.DictReader(io.StringIO(text))]
    if rows and "지번주소" not in rows[0] and "사찰" not in rows[0]:
        raise StoreError("사찰기록 CSV 가 아닌 것 같습니다. "
                         "머리글에 '사찰' 이나 '지번주소' 가 있어야 합니다.")
    return rows


def _stamp(row: Dict[str, str]) -> str:
    """저장시각. 비어 있으면 가장 오래된 것으로 봅니다."""
    return str(row.get("저장시각", "")).strip()


def merge(blobs: List[bytes], folder: str = "") -> dict:
    """올린 CSV 들을 지금 기록과 합칩니다.

    (더한 수, 새것으로 바꾼 수, 오래되어 버린 수, 읽은 줄 수) 를 돌려줍니다.
    """
    cur = {_key(r): r for r in load(folder)}
    added = updated = older = seen = 0

    for blob in blobs:
        for r in read_bytes(blob):
            row = {c: r.get(c, "") for c in COLUMNS}
            if not any(row.get(c) for c in ("사찰", "지번주소")):
                continue          # 빈 줄
            seen += 1
            k = _key(row)
            old = cur.get(k)
            if old is None:
                cur[k] = row
                added += 1
            elif _stamp(row) > _stamp(old):
                # 사람이 적어 둔 칸은 새 줄이 비어 있으면 지킵니다.
                for c in KEEP_ON_UPDATE:
                    if old.get(c) and not row.get(c):
                        row[c] = old[c]
                cur[k] = row
                updated += 1
            else:
                older += 1

    rows = list(cur.values())
    _write(rows, folder)
    return {"added": added, "updated": updated, "older": older,
            "seen": seen, "total": len(rows)}
