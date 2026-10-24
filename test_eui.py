# -*- coding: utf-8 -*-
"""
원단위 기준 확인 (작업지시 04)

실행:  python test_eui.py

인터넷도 인증키도 쓰지 않습니다. 가짜 값으로만 돌립니다.

확인하는 것
  - 지역 구분 별표1 (전북이 중부2 인지가 핵심)
  - 면적당 에너지와 배수 (도시가스 0 이면 배수를 내지 않는지)
  - 주차장은 옥내 두 항목만 빼는지
  - 전통/확인 필요/신식 세 갈래
  - 종교시설이 없다고 경고하지 않는지
"""
import bldrgst
import emissions as em
import region

LINE = "-" * 68
_fail = 0


def ok(name, cond, detail=""):
    global _fail
    if not cond:
        _fail += 1
    print(f"  [{'OK' if cond else 'FAIL'}]  {name}")
    if detail:
        print(f"         {detail}")


def dong(strct="", roof="", area=100.0, purps="종교시설", **raw):
    return bldrgst.Dong(
        dongNm="테스트", totArea=area, strctCdNm=strct, roofCdNm=roof,
        mainPurpsCdNm=purps, raw=raw,
    )


def main() -> int:
    print()
    print(LINE)
    print("  원단위 기준 확인 (작업지시 04)")
    print(LINE)

    # ── 1. 지역 구분 ──
    print()
    print("  [1] 지역 구분 - 에너지절약설계기준 별표1")
    cases = [
        ("전북특별자치도 김제시 금산면 금산리 39", "중부2", "중부"),
        ("전북특별자치도 남원시 산내면 입석리 50-1", "중부2", "중부"),
        ("전라북도 전주시 완산구", "중부2", "중부"),
        ("서울특별시 강남구 삼성동 73", "중부2", "중부"),
        ("경기도 고양시 덕양구 대자동 산162", "중부2", "중부"),
        ("경기도 남양주시 와부읍", "중부1", "중부"),
        ("경기도 양주시 백석읍", "중부1", "중부"),
        ("강원특별자치도 속초시 교동", "중부2", "중부"),
        ("강원특별자치도 원주시 명륜동", "중부1", "중부"),
        ("충청북도 제천시 의림동", "중부1", "중부"),
        ("충청북도 청주시 상당구", "중부2", "중부"),
        ("경상북도 봉화군 춘양면", "중부1", "중부"),
        ("경상북도 경주시 진현동", "남부", "남부"),
        ("경상북도 안동시 풍천면", "중부2", "중부"),
        ("경상남도 거창군 가조면", "중부2", "중부"),
        ("경상남도 통영시 광도면", "남부", "남부"),
        ("부산광역시 금정구 청룡동", "남부", "남부"),
        ("제주특별자치도 서귀포시 안덕면", "제주", "남부"),
    ]
    bad = []
    for addr, want4, want2 in cases:
        got4 = region.region4(addr)
        got2 = region.region2(got4)
        if (got4, got2) != (want4, want2):
            bad.append(f"{addr} -> {got4}/{got2} (기대 {want4}/{want2})")
    ok(f"{len(cases)}곳 전부 맞음", not bad, " / ".join(bad))

    ok("전북은 남부가 아니라 중부",
       region.of("전북특별자치도 김제시 금산면 금산리 39") == "중부",
       "지도상 남쪽이지만 별표1은 중부2 입니다")
    ok("모르는 주소는 빈 문자열", region.region4("어디인지 모를 곳 123") == "")
    ok("빈 주소도 안전", region.region4("") == "" and region.of("") == "")
    ok("label 이 네 구분을 함께 밝힘",
       region.label("서울특별시 강남구") == "중부 (중부2)",
       region.label("서울특별시 강남구"))

    # ── 2. 면적당 에너지 ──
    print()
    print("  [2] 면적당 에너지와 배수")

    # 수국사 - 옥내 주차장이 없어 분모가 그대로입니다.
    u = em.area_use(208412, 229257, 2658.3, "중부")
    ok("수국사 165 kWh/m2", round(u.per) == 165, f"{u.per:.1f}")
    ok("수국사 배수 1.60", round(u.ratio, 2) == 1.60, f"{u.ratio:.2f}")
    ok("수국사 원단위 103", u.base == 103)

    # 봉은사 - 옥내 자주식 7,497.5 m2 를 뺀 분모입니다.
    u = em.area_use(2310661, 2630415, 27271.1 - 7497.5, "중부",
                    parking_area=7497.5)
    ok("봉은사 250 kWh/m2 (주차장 제외)", round(u.per) == 250, f"{u.per:.1f}")
    ok("봉은사 배수 2.43", round(u.ratio, 2) == 2.43, f"{u.ratio:.2f}")

    # 주차장을 안 뺐을 때와 견줍니다. 빼면 배수가 커집니다.
    g = em.area_use(2310661, 2630415, 27271.1, "중부")
    ok("주차장을 빼면 배수가 커진다", u.ratio > g.ratio,
       f"제외 {u.ratio:.2f} > 포함 {g.ratio:.2f}")

    print()
    print("  [3] 도시가스가 0 이면 배수를 내지 않는다")
    u = em.area_use(1037930, 0, 7545.2, "중부")
    ok("배수가 없음", not u.has_ratio and u.ratio == 0)
    ok("전체 kWh/m2 도 안 냄", u.per == 0)
    ok("전기 kWh/m2 는 그대로 보여 줌", round(u.elec_per) == 138,
       f"{u.elec_per:.0f} kWh/m2")
    ok("까닭을 밝힘", u.note == em.NO_HEAT_NOTE, u.note)

    print()
    print("  [3-1] 현장 조사값을 넣으면 그때 배수를 낸다")
    heat = em.fuel_kwh("LPG-프로판(LPG1호)", 20000)
    u = em.area_use(1037930, 0, 7545.2, "중부", other_kwh=heat)
    ok("LPG 20,000 kg = 257,222 kWh", round(heat) == 257222, f"{heat:,.0f}")
    ok("배수가 나옴", u.has_ratio, f"{u.ratio:.2f}배")
    ok("가스 0 인데도 분자에 더해짐", u.per > u.elec_per,
       f"전체 {u.per:.0f} > 전기만 {u.elec_per:.0f}")

    print()
    print("  [3-2] 낼 수 없는 경우")
    u = em.area_use(1000, 1000, 0, "중부")
    ok("연면적 0 이면 아무것도 안 냄", u.per == 0 and u.elec_per == 0 and not u.has_ratio)
    u = em.area_use(1000, 1000, 100, "")
    ok("지역을 모르면 배수 없음", not u.has_ratio and "지역" in u.note, u.note)
    ok("그래도 전기 kWh/m2 는 냄", u.elec_per == 10)

    print()
    print("  [3-3] 상수")
    ok("사찰 중부 103 / 남부 79",
       em.EUI["사찰"] == {"중부": 103, "남부": 79})
    ok("교회·성당도 함께 둠",
       em.EUI["교회"] == {"중부": 73, "남부": 56}
       and em.EUI["성당"] == {"중부": 71, "남부": 57})
    ok("옛 고정 기준이 사라짐", not hasattr(em, "AREA_KWH_LIMIT"))
    ok("옛 area_check 가 사라짐", not hasattr(em, "area_check"))
    ok("중간값이라는 것을 문구로 들고 있음", "중간값" in em.EUI_NOTE)

    # ── 4. 주차장 ──
    print()
    print("  [4] 주차장은 옥내 두 항목만 뺀다")
    d = dong(area=18730.9, indrMechArea="0", indrAutoArea="7497.5",
             oudrMechArea="0", oudrAutoArea="0")
    ok("옥내 자주식이 잡힘", d.indr_parking == 7497.5, f"{d.indr_parking}")
    d2 = dong(area=2658.3, indrMechArea="0", indrAutoArea="0",
              oudrMechArea="0", oudrAutoArea="184.0")
    ok("옥외는 빼지 않음 (수국사 184 m2)", d2.indr_parking == 0.0,
       "옥외 주차장은 애초에 연면적에 없습니다")
    s = bldrgst.summarize([d, d2])
    ok("summarize 가 분모를 따로 냄",
       round(s["area_excl_parking"], 1) == round(18730.9 + 2658.3 - 7497.5, 1),
       f"{s['area_excl_parking']:,.1f} m2")
    ok("뺀 면적을 밝힘", s["parking_area"] == 7497.5)

    # ── 5. 전통 / 확인 필요 / 신식 ──
    print()
    print("  [5] 전통 / 확인 필요 / 신식 세 갈래")
    wood = dong("일반목구조", "기와")
    mixed = dong("철근콘크리트구조", "기와")
    plain = dong("철근콘크리트구조", "(철근)콘크리트")
    ok("목구조는 전통", wood.kind == "전통")
    ok("콘크리트인데 지붕만 기와는 확인 필요", mixed.kind == "확인 필요",
       f"{mixed.strctCdNm} + {mixed.roofCdNm} -> {mixed.kind}")
    ok("둘 다 아니면 신식", plain.kind == "신식")
    ok("전통만 태양광에서 뺌",
       not wood.solar_ok and mixed.solar_ok and plain.solar_ok)
    ok("표에 적을 말", (bldrgst.solar_label(wood), bldrgst.solar_label(mixed),
                        bldrgst.solar_label(plain)) == ("제외", "확인 필요", "후보"))
    ok("규제 구역이면 협의 필요", bldrgst.solar_label(plain, True) == "협의 필요")
    ok("규제여도 전통은 그대로 제외", bldrgst.solar_label(wood, True) == "제외")

    print()
    print("  [5-1] 규제 구역 추리기")
    zones = ["자연녹지지역", "개발제한구역", "과밀억제권역"]
    ok("개발제한구역을 찾음", bldrgst.restricted(zones) == ["개발제한구역"])
    ok("규제가 없으면 빈 목록", bldrgst.restricted(["일반주거지역"]) == [])
    ok("없는 값도 안전", bldrgst.restricted(None) == [])

    # ── 6. 경고 뒤집기 ──
    print()
    print("  [6] 종교시설이 없다고 경고하지 않는다")
    small = [dong("일반목구조", "기와", 337.0, "제2종근린생활시설")]
    msgs = bldrgst.checks(small)
    ok("작은 절이 경고를 받지 않음",
       not any("종교시설인 건물이 없습니다" in m for m in msgs),
       " / ".join(msgs) or "(경고 없음)")
    house = [dong("일반목구조", "기와", 200.0, "단독주택")]
    ok("요사채가 단독주택이어도 경고 없음",
       not any("종교시설" in m for m in bldrgst.checks(house)))

    print()
    print("  [6-1] 이상한 용도가 있을 때만 경고한다")
    odd = [dong("일반목구조", "기와", 300.0, "종교시설"),
           dong("철골구조", "기타지붕", 900.0, "공장")]
    msgs = bldrgst.checks(odd)
    ok("공장이 섞이면 경고", any("있기 어려운 용도" in m for m in msgs),
       " / ".join(msgs))
    ok("용도 이름을 적어 줌", any("공장" in m for m in msgs))
    clean = [dong("일반목구조", "기와", 300.0, "종교시설"),
             dong("철근콘크리트구조", "(철근)콘크리트", 100.0, "단독주택")]
    ok("정상 조합에는 경고 없음",
       not any("있기 어려운 용도" in m for m in bldrgst.checks(clean)))

    print()
    print(LINE)
    if _fail:
        print(f"  {_fail}개 실패.")
    else:
        print("  모두 통과했습니다.")
    print(LINE)
    print()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
