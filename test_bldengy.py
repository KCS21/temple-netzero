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


def gcheck(name, months, want_holes, want_ends):
    """bldengy.gaps - 빠진 달을 두 갈래로 가르는 규칙.

    months 는 1~12월 값 열두 개. 0 이면 그달 자료가 없다는 뜻입니다.
    """
    global _fail
    series = {f"2021{i:02d}": float(v) for i, v in enumerate(months, 1)}
    holes, ends = bldengy.gaps(series)
    gh = [int(y[4:]) for y in holes]
    ge = [int(y[4:]) for y in ends]
    ok = gh == list(want_holes) and ge == list(want_ends)
    if not ok:
        _fail += 1
    print(f"  [{'OK' if ok else 'FAIL'}]  {name}")
    print(f"         구멍 기대 {list(want_holes)} 실제 {gh}"
          f"  /  끝 기대 {list(want_ends)} 실제 {ge}")


def mcheck(name, fake, want, notwant=""):
    """오류 문구가 맞는 갈래로 나오는지. 인터넷을 쓰지 않습니다."""
    global _fail
    import requests
    import portal as _p
    real = requests.get
    requests.get = fake
    try:
        _p.request("http://b", "op", {"x": 1}, "KEY", timeout=1, retries=0)
        msg = "(오류가 안 났습니다)"
    except _p.PortalError as e:
        msg = str(e)
    finally:
        requests.get = real
    ok = want in msg and (not notwant or notwant not in msg)
    if not ok:
        _fail += 1
    print(f"  [{'OK' if ok else 'FAIL'}]  {name}")
    print(f"         기대 「{want}」 / 실제 「{msg.splitlines()[0]}」")


def ycheck(name, want_code, want_total, place_must="", old_sgg="46730",
           new_plc="전라남도 구례군 마산면 황전리 12번지",
           old_qty=100.0, new_qty=0.0, old_plc=None):
    """fetch_year 가 옛 시군구코드로 되묻는 규칙. 인터넷을 쓰지 않습니다.

    새 코드로 열두 달이 **모두 0** 일 때만 되묻고, 받은 자료의 주소에
    그 동네 이름이 든 것만 씁니다.
    """
    global _fail
    calls = {"새": 0, "옛": 0}

    def _rows(op, params, service_key, timeout, retries):
        sgg = params["sigunguCd"]
        is_old = sgg == old_sgg
        calls["옛" if is_old else "새"] += 1
        qty = old_qty if is_old else new_qty
        plc = (old_plc if is_old and old_plc is not None
               else new_plc)
        if not qty:
            return []
        return [bldengy.MonthUse(useYm=params["useYm"], useQty=float(qty),
                                 platGbCd="0", platPlc=plc,
                                 raw={"platGbCd": "0"})]

    real, bldengy._rows = bldengy._rows, _rows
    try:
        out = bldengy.fetch_year("12730", "34024", "0012", "0000", 2025,
                                 "DUMMY", plat_gb="0", pause=0,
                                 old_sigungu=old_sgg, place_must=place_must)
    finally:
        bldengy._rows = real

    tot = sum(out["elec"].values()) + sum(out["gas"].values())
    ok = out.get("code") == want_code and abs(tot - want_total) < 0.001
    if not ok:
        _fail += 1
    print(f"  [{'OK' if ok else 'FAIL'}]  {name}")
    print(f"         코드 기대 {want_code} 실제 {out.get('code')}"
          f" · 합계 기대 {want_total:,.0f} 실제 {tot:,.0f}"
          f" · 호출 새 {calls['새']} / 옛 {calls['옛']}")


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

    # 빠진 달은 **가운데 구멍**과 **앞뒤 끝**이 다릅니다. 가운데 구멍은
    # 자료 출처에 그 달이 없는 것이라 해를 바꿔도 그대로이고, 앞뒤 끝은
    # 아직 안 들어온 해라 최근 해로 바꾸면 채워집니다. 다음 행동이
    # 정반대라 화면이 두 문구로 나눠 알립니다(2026-10-24).
    print("  [5] 빠진 달 가르기 (gaps)")
    F = 100
    gcheck("열두 달 꽉 참", [F] * 12, [], [])
    gcheck("10월만 구멍 (2021년 전기 실제)",
           [F] * 9 + [0] + [F] * 2, [10], [])
    gcheck("구멍 둘", [F, F, F, 0, F, F, F, F, F, 0, F, F], [4, 10], [])
    gcheck("뒤쪽 끝이 비었음", [F] * 9 + [0] * 3, [], [10, 11, 12])
    gcheck("앞쪽 끝이 비었음 (원오사 2020년)",
           [0] * 3 + [F] * 9, [], [1, 2, 3])
    gcheck("앞 끝과 가운데 구멍이 같이",
           [0, 0, 0] + [F] * 6 + [0] + [F, F], [10], [1, 2, 3])
    gcheck("한 달만 있음 -> 나머지는 전부 끝",
           [0] * 5 + [F] + [0] * 6, [], [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12])
    gcheck("통째로 없음 -> 구멍 아님",
           [0] * 12, [], list(range(1, 13)))
    print()

    # 제공기관이 503 을 내는 날에 **회원 인터넷을 탓하면 안 됩니다.**
    # 시니어가 공유기를 보러 가십니다(2026-10-25).
    print("  [6] 오류 문구가 맞는 갈래로 나오나")
    import requests as _rq

    class _R503:
        text = "<html>503</html>"

        def raise_for_status(self):
            raise _rq.HTTPError("503 Server Error for url: http://x")

        def json(self):
            raise AssertionError

    class _RHtml:
        text = "<html>잠시 후</html>"

        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("no json")

    def _down(*a, **k):
        raise _rq.ConnectionError("getaddrinfo failed")

    mcheck("서버가 5xx -> 공공기관 서버 문구", lambda *a, **k: _R503(),
           "공공기관 서버가 잠시 응답하지 않습니다", "인터넷 연결을 확인")
    mcheck("연결 자체 실패 -> 인터넷 문구", _down,
           "인터넷 연결을 확인", "공공기관 서버가 잠시")
    mcheck("JSON 대신 HTML -> 불안정 문구", lambda *a, **k: _RHtml(),
           "제공기관 서버가 잠시 불안정합니다")
    print()

    print()
    print("  [5] 옛 시군구코드로 되묻기 (행정구역 통합)")
    # 새 코드가 전부 0 이고 옛 코드에 자료가 있으면 -> 옛 코드 값
    ycheck("새 코드 전부 0 -> 옛 코드로 받음", "옛", 100.0 * 24,
           place_must="마산면")
    # 새 코드에 자료가 있으면 되묻지 않습니다
    ycheck("새 코드에 자료가 있으면 그대로", "새", 50.0 * 24,
           place_must="마산면", new_qty=50.0, old_qty=100.0)
    # 옛 코드에도 없으면 새 코드 결과(0)를 그대로
    ycheck("옛 코드에도 없으면 0", "새", 0.0,
           place_must="마산면", old_qty=0.0)
    # **남의 동네가 오면 버립니다** — 지명이 안 맞는 경우
    ycheck("옛 코드가 남의 동네를 주면 쓰지 않음", "새", 0.0,
           place_must="마산면", old_plc="전라남도 순천시 조례동 1589-1")
    # 옛 코드를 안 주면(통합 지역이 아니면) 되묻지 않습니다
    ycheck("통합 지역이 아니면 되묻지 않음", "새", 0.0,
           place_must="", old_sgg="")

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
