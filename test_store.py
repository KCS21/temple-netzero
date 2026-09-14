# -*- coding: utf-8 -*-
"""
사찰 기록 저장 확인

실행:  python test_store.py

인터넷도 인증키도 쓰지 않습니다. 임시 폴더에서만 돌므로
실제 사찰기록.csv 는 건드리지 않습니다.

기록이 날아가면 되돌릴 수 없어서 따로 확인합니다.
"""
import io
import os
import shutil
import tempfile

import store

LINE = "-" * 64
_fail = 0


def ok(name, cond, detail=""):
    global _fail
    if not cond:
        _fail += 1
    print(f"  [{'OK' if cond else 'FAIL'}]  {name}")
    if detail:
        print(f"         {detail}")


def row(temple, jibun, year, ton, per="", suspect=""):
    return {"사찰": temple, "지번주소": jibun, "조회연도": str(year),
            "공개자료 배출량(t)": str(ton), "면적당 전기(kWh/m2)": str(per),
            "대장누락 의심": suspect}


def main() -> int:
    print()
    print(LINE)
    print("  사찰 기록 저장 확인")
    print(LINE)
    print()

    tmp = tempfile.mkdtemp()
    try:
        print("  [1] 비어 있을 때")
        ok("파일이 없으면 빈 목록", store.load(tmp) == [])

        print()
        print("  [2] 저장과 다시 읽기")
        rows, replaced = store.save(row("수국사", "은평구 구산동 314", 2022, 117.0, 80), tmp)
        ok("한 곳 저장", len(rows) == 1 and not replaced)
        back = store.load(tmp)
        ok("다시 읽으면 그대로", len(back) == 1 and back[0]["사찰"] == "수국사",
           f"읽은 값: {back[0]['사찰']} / {back[0]['공개자료 배출량(t)']}")
        ok("저장시각이 찍힘", bool(back[0]["저장시각"]), back[0]["저장시각"])

        print()
        print("  [3] 같은 지번·같은 해는 덮어쓴다 (줄이 쌓이지 않아야 함)")
        rows, replaced = store.save(row("수국사", "은평구 구산동 314", 2022, 131.7, 85), tmp)
        ok("덮어썼다고 알려줌", replaced)
        ok("줄이 늘지 않음", len(rows) == 1, f"{len(rows)}줄")
        ok("값이 새것으로", store.load(tmp)[0]["공개자료 배출량(t)"] == "131.7")

        print()
        print("  [4] 해가 다르면 따로 쌓인다")
        store.save(row("수국사", "은평구 구산동 314", 2023, 120.0, 82), tmp)
        ok("두 줄이 됨", len(store.load(tmp)) == 2)

        print()
        print("  [5] 다른 사찰 추가")
        store.save(row("봉은사", "강남구 삼성동 73", 2023, 1096.9, 85), tmp)
        store.save(row("실상사", "남원시 산내면 입석리 50-1", 2024, 136.4, 685, "예"), tmp)
        rows = store.load(tmp)
        ok("네 줄", len(rows) == 4, f"{len(rows)}줄")

        print()
        print("  [6] 한글이 안 깨진다 (엑셀에서 여는 형식)")
        raw = open(store.path(tmp), "rb").read()
        ok("UTF-8 BOM 으로 저장됨", raw.startswith(b"\xef\xbb\xbf"))
        ok("한글이 그대로", "실상사".encode("utf-8") in raw)

        print()
        print("  [7] 지우기")
        left = store.remove("강남구 삼성동 73", 2023, tmp)
        ok("한 줄 줄어듦", len(left) == 3)
        ok("없는 것을 지워도 안전", len(store.remove("없는 지번", 1999, tmp)) == 3)

        print()
        print("  [7-1] 다시 조회해도 사람이 채운 칸은 지킨다")
        store.save(row("현덕사", "강릉시 연곡면 100", 2024, 30.0, 60), tmp)
        cur = store.load(tmp)
        me = [r for r in cur if r["사찰"] == "현덕사"][0]
        me["방문 상태"], me["메모"] = "완료", "주지스님 면담 마침"
        store._write(cur, tmp)
        # 같은 지번·같은 해로 다시 조회한 셈
        store.save(row("현덕사", "강릉시 연곡면 100", 2024, 31.5, 62), tmp)
        me = [r for r in store.load(tmp) if r["사찰"] == "현덕사"][0]
        ok("방문 상태가 남음", me["방문 상태"] == "완료", me["방문 상태"])
        ok("메모가 남음", me["메모"] == "주지스님 면담 마침", me["메모"])
        ok("조회값은 새것으로", me["공개자료 배출량(t)"] == "31.5",
           me["공개자료 배출량(t)"])
        store.remove("강릉시 연곡면 100", 2024, tmp)

        print()
        print("  [7-2] 방문 상태 기본값")
        store.save(row("새절", "어디 1", 2024, 10.0), tmp)
        me = [r for r in store.load(tmp) if r["사찰"] == "새절"][0]
        ok("비우면 미방문", me["방문 상태"] == "미방문", me["방문 상태"])
        store.remove("어디 1", 2024, tmp)

        print()
        print("  [8] 벤치마크")
        b = store.benchmark(store.load(tmp))
        ok("기록 수를 셈", b["count"] == 3, f"count={b['count']}")
        ok("누락 의심은 면적당 평균에서 뺌", b["per_n"] == 2 and b["suspect"] == 1,
           f"면적당 표본 {b['per_n']}곳 / 누락 의심 {b['suspect']}곳")
        ok("배출량 평균이 나옴", b["ton_avg"] is not None,
           f"평균 {b['ton_avg']:.1f} t / 최대 {b['ton_max']:.1f} / 최소 {b['ton_min']:.1f}")

        print()
        print("  [9] 내려받기용 바이트")
        blob = store.as_csv_bytes(tmp)
        ok("BOM 포함", blob.startswith(b"\xef\xbb\xbf"))
        ok("머리글이 들어 있음", "지번주소".encode("utf-8") in blob)

        print()
        print("  [9-1] 여러 CSV 합치기")
        import store as _s
        a = tempfile.mkdtemp()
        b = tempfile.mkdtemp()
        try:
            # 갑: 1번·2번을 돌림
            _s.save(dict(row("갑절", "갑 1", 2024, 10.0), 번호="1"), a)
            _s.save(dict(row("을절", "을 2", 2024, 20.0), 번호="2"), a)
            # 을: 2번을 더 늦게 다시 돌리고 3번을 새로 돌림
            _s.save(dict(row("을절", "을 2", 2024, 22.2), 번호="2"), b)
            _s.save(dict(row("병절", "병 3", 2024, 30.0), 번호="3"), b)
            # 을쪽 2번의 저장시각을 늦춰 둡니다
            rb = _s.load(b)
            for r in rb:
                if r["번호"] == "2":
                    r["저장시각"] = "2099-01-01 00:00"
            _s._write(rb, b)

            blob = io.open(_s.path(b), "rb").read()
            res = _s.merge([blob], a)
            got = {r["번호"]: r for r in _s.load(a)}
            ok("세 곳이 됨", len(got) == 3, f"{len(got)}곳 / {res}")
            ok("새 곳은 더해짐", res["added"] == 1 and "3" in got)
            ok("늦은 것이 이김", got["2"]["공개자료 배출량(t)"] == "22.2",
               got["2"]["공개자료 배출량(t)"])
            ok("건드리지 않은 곳은 그대로", got["1"]["공개자료 배출량(t)"] == "10.0")

            # 같은 것을 또 합치면 아무것도 안 바뀌어야 합니다
            res2 = _s.merge([blob], a)
            ok("두 번 합쳐도 안 늘어남", len(_s.load(a)) == 3 and res2["added"] == 0,
               f"{res2}")

            # 사람이 적은 메모는 지켜야 합니다
            ra = _s.load(a)
            for r in ra:
                if r["번호"] == "2":
                    r["메모"] = "면담 예정"
                    r["저장시각"] = "2000-01-01 00:00"
            _s._write(ra, a)
            _s.merge([blob], a)
            got = {r["번호"]: r for r in _s.load(a)}
            ok("합칠 때도 메모가 남음", got["2"]["메모"] == "면담 예정", got["2"]["메모"])
        finally:
            shutil.rmtree(a, ignore_errors=True)
            shutil.rmtree(b, ignore_errors=True)

        print()
        print("  [10] 덮어쓰기 전에 백업이 남는다")
        ok("사찰기록.csv.bak 생김", os.path.exists(store.path(tmp) + ".bak"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(LINE)
    if _fail:
        print(f"  {_fail}개 실패. store.py 를 확인하세요.")
    else:
        print("  모두 통과했습니다.")
    print(LINE)
    print()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
