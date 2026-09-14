# -*- coding: utf-8 -*-
"""
건물에너지 대지/산 필터 확인

실행:  python test_bldengy.py

인터넷을 쓰지 않습니다. 가짜 응답을 넣어 bldengy.fetch_month 의
대지/산 거르기만 확인합니다. 인증키도 일부러 넣지 않았습니다.

왜 필요한가
-----------
건물에너지 API 는 요청에 대지구분(platGbCd)을 넣을 수 없습니다.
그런데 "162"(대지)와 "산162"(산)는 둘 다 bun=0162 로 변환되므로
한 응답에 남의 건물이 섞여 올 수 있습니다.

예전 코드는 `picked or rows` 로 되어 있어서, 산 지번 사찰을 조회했는데
대지 행만 오면 그 값을 사찰 것으로 합산했습니다. 없는 자료가 그럴듯한
숫자로 둔갑하고 신뢰도까지 "높음"으로 올라가던 문제입니다.
"""
import sys

import bldengy

LINE = "-" * 64
_fail = 0


def fake(rows):
    """(사용량, 대지구분) 목록으로 가짜 응답을 만듭니다.

    대지구분이 None 이면 응답에 그 항목 자체가 없는 경우입니다.
    """
    def _rows(op, params, service_key, timeout, retries):
        out = []
        for qty, gb in rows:
            raw = {} if gb is None else {"platGbCd": str(gb)}
            out.append(bldengy.MonthUse(
                useYm="202402", useQty=float(qty),
                platGbCd="0" if gb is None else str(gb),
                platPlc="(가짜)", raw=raw))
        return out
    return _rows


def check(name, rows, plat_gb, want, want_dropped=None):
    global _fail
    real, bldengy._rows = bldengy._rows, fake(rows)
    try:
        got, dropped = bldengy.fetch_month("elec", "41281", "10300", "0162", "0000",
                                           "202402", "DUMMY", plat_gb=plat_gb)
    finally:
        bldengy._rows = real

    ok = abs(got - want) < 0.001
    if want_dropped is not None and dropped != want_dropped:
        ok = False
    if not ok:
        _fail += 1
    gb = "None" if plat_gb is None else f'"{plat_gb}"'
    print(f"  [{'OK' if ok else 'FAIL'}]  {name}")
    tail = "" if want_dropped is None else f"  걸러냄 기대 {want_dropped} 실제 {dropped}"
    print(f"         plat_gb={gb}  기대 {want:,.0f}  실제 {got:,.0f}{tail}")


def main() -> int:
    print()
    print(LINE)
    print("  건물에너지 대지/산 필터 확인")
    print(LINE)
    print()
    print("  가정: 같은 번지에 사찰(산162)과 남의 건물(162)이 겹쳐 있음")
    print("        사찰 1,199 kWh / 남의 건물 28,000 kWh")
    print()

    SAN = (1199, "1")
    DAEJI = (28000, "0")

    print("  [1] 걸러내기")
    check("산 행만 있음 -> 그대로", [SAN], "1", 1199)
    check("산과 대지가 섞임 -> 산만", [SAN, DAEJI], "1", 1199)
    check("대지로 조회 -> 대지만", [SAN, DAEJI], "0", 28000)
    print()

    print("  [2] 이번에 고친 것 - 남의 건물을 사찰 것으로 세지 않는다")
    check("산 지번인데 대지 행만 옴 -> 0", [DAEJI], "1", 0, want_dropped=1)
    check("대지 지번인데 산 행만 옴 -> 0", [SAN], "0", 0, want_dropped=1)
    print("         (예전 코드는 각각 28,000 과 1,199 를 돌려주었습니다)")
    print()

    print("  [2-1] 걸러낸 건수를 세어 돌려준다 - 화면에 밝히기 위한 것")
    check("섞임 -> 대지 1건 걸러냄", [SAN, DAEJI], "1", 1199, want_dropped=1)
    check("대지 2건 걸러냄", [SAN, DAEJI, (900, "0")], "1", 1199, want_dropped=2)
    check("걸러낼 것 없음 -> 0건", [SAN], "1", 1199, want_dropped=0)
    print()

    print("  [3] 거를 수 없는 경우에는 손대지 않는다")
    check("응답에 대지구분이 없음 -> 전부", [(500, None)], "1", 500)
    check("일부에만 대지구분이 있음 -> 밝힌 것만", [SAN, (500, None)], "1", 1199)
    print()

    print("  [4] 그 밖")
    check("행이 아예 없음 -> 0", [], "1", 0)
    check("plat_gb 를 안 주면 전부", [SAN, DAEJI], None, 29199)
    print()

    print(LINE)
    if _fail:
        print(f"  {_fail}개 실패. bldengy.fetch_month 를 확인하세요.")
    else:
        print("  모두 통과했습니다.")
    print(LINE)
    print()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
