# -*- coding: utf-8 -*-
"""
인증키 두 개가 살아 있는지 확인합니다.

실행:  python test_key.py
      python test_key.py "봉은사로 531"
"""
import sys

import bldrgst
import juso
import keys
import portal

# 인증키는 같은 폴더의 키.txt 에서 읽습니다. 코드에 키를 넣지 마십시오.

LINE = "-" * 64


def main() -> int:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "구산동 314"

    try:
        CONFM_KEY, SERVICE_KEY = keys.load()
    except keys.KeyError_ as e:
        print()
        print(e)
        print()
        return 1

    # ── 1. 도로명주소 ──
    print(f'\n[1] 주소 검색 - "{keyword}"')
    print(LINE)
    try:
        rows, total = juso.search(keyword, CONFM_KEY, per_page=5)
    except juso.JusoError as e:
        print(f"  실패 - {e}\n")
        return 1
    if not rows:
        print("  결과가 없습니다. 동 이름만 넣고 다시 해보세요.\n")
        return 1

    print(f"총 {total}건 중 {len(rows)}건\n")
    for i, j in enumerate(rows, 1):
        print(f"[{i}] {j.jibunAddr}" + ("  (산)" if j.is_mountain else ""))
        p = j.building_params()
        print(f"    조회값  시군구 {p['sigunguCd']} · 법정동 {p['bjdongCd']} · "
              f"번 {p['bun']} · 지 {p['ji']} · 대지구분 {p['platGbCd']}")
    print("\n  [OK] 도로명주소 승인키 정상")

    # ── 2. 건축물대장 ──
    first = rows[0]
    p = first.building_params()
    print(f"\n[2] 건축물대장 - {first.jibunAddr}")
    print(LINE)
    try:
        dongs = bldrgst.fetch_dongs(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                    p["ji"], SERVICE_KEY, p["platGbCd"])
    except portal.PortalError as e:
        print(f"  실패 - {e}\n")
        return 1

    if not dongs:
        print("  등록된 건물이 없습니다. (키는 정상. 이 지번에 자료가 없을 뿐입니다)")
    else:
        for d in dongs:
            print(f"  {d.kind}  {d.label()}")
        s = bldrgst.summarize(dongs)
        print(f"\n  {s['count']}동 / 연면적 {s['total_area']:,.1f} m²"
              f" / 전통 {s['trad_count']}동 · 신식 {s['modern_count']}동")
    print("\n  [OK] 공공데이터포털 인증키 정상")

    print(f"\n{LINE}\n두 키 모두 정상입니다.  streamlit run app.py 로 화면을 여세요.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
