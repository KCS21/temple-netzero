# -*- coding: utf-8 -*-
"""
지역 구분 — 건축물의 에너지절약설계기준 별표1
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

국토교통부고시 제2022-52호 「건축물의 에너지절약설계기준」 별표1 비고의
네 구분(중부1·중부2·남부·제주)입니다.

**네 구분으로 들고 있다가 쓸 때 합칩니다.**

- 그린투게더 원단위는 둘로 합쳐 씁니다 (중부1+중부2=중부, 제주+남부=남부)
- 상쇄사업 표준베이스라인은 **네 구분을 그대로** 씁니다

나중에 표준베이스라인을 붙일 수 있으므로 네 구분을 보존합니다.
그래서 region4() 와 region2() 가 따로 있습니다.

    region4("전북특별자치도 김제시 금산면 금산리 39")  ->  "중부2"
    region2("중부2")                                   ->  "중부"
"""
from __future__ import annotations

from typing import Optional

# ── 네 구분 ──
JUNGBU1 = "중부1"
JUNGBU2 = "중부2"
NAMBU = "남부"
JEJU = "제주"

ZONES4 = (JUNGBU1, JUNGBU2, NAMBU, JEJU)
ZONES2 = ("중부", "남부")


# ── 시도 이름 정규화 ──
#
# 같은 곳을 여러 이름으로 부릅니다. 전라북도는 2024년에 전북특별자치도가
# 되었고, 강원도는 강원특별자치도가 되었습니다. 도로명주소 API 는 새 이름을
# 돌려주지만 손으로 넣은 주소에는 옛 이름이 섞입니다. 둘 다 받습니다.
_SIDO = {
    "서울": "서울", "서울특별시": "서울",
    "부산": "부산", "부산광역시": "부산",
    "대구": "대구", "대구광역시": "대구",
    "인천": "인천", "인천광역시": "인천",
    "광주": "광주", "광주광역시": "광주",
    "대전": "대전", "대전광역시": "대전",
    "울산": "울산", "울산광역시": "울산",
    "세종": "세종", "세종시": "세종",
    "세종특별자치시": "세종", "세종특별시": "세종",
    "경기": "경기", "경기도": "경기",
    "강원": "강원", "강원도": "강원", "강원특별자치도": "강원",
    "충북": "충북", "충청북도": "충북",
    "충남": "충남", "충청남도": "충남",
    "전북": "전북", "전라북도": "전북", "전북특별자치도": "전북",
    "전남": "전남", "전라남도": "전남",
    # 2026년 통합. 도로명주소 API 가 광주·전남 주소를 이 이름으로 돌려줍니다.
    # 모르는 이름이면 region4() 가 빈 문자열을 내고 **화면의 배수 칸이
    # 통째로 비었습니다**(녹색사찰 9곳·전통사찰 22곳).
    "전남광주": "전남광주", "전남광주통합특별시": "전남광주",
    "전남광주통합시": "전남광주", "전남광주특별시": "전남광주",
    "경북": "경북", "경상북도": "경북",
    "경남": "경남", "경상남도": "경남",
    "제주": "제주", "제주도": "제주", "제주특별자치도": "제주",
}

# ── 시도만으로 정해지는 곳 ──
_BY_SIDO = {
    "서울": JUNGBU2, "대전": JUNGBU2, "세종": JUNGBU2, "인천": JUNGBU2,
    "충남": JUNGBU2,
    # 전북은 **중부2 입니다.** 지도에서 남쪽이라 남부로 착각하기 쉬운데
    # 별표1은 중부2로 둡니다. 금산사와 실상사가 둘 다 여기 속합니다.
    # 남부(79)로 잘못 보면 배수가 1.3배쯤 부풀어 오릅니다.
    "전북": JUNGBU2,
    "부산": NAMBU, "대구": NAMBU, "울산": NAMBU, "광주": NAMBU,
    "전남": NAMBU,
    # 통합 전의 광주광역시와 전라남도가 **별표1에서 둘 다 남부**입니다.
    # 그래서 통합시는 시군구를 보지 않고도 남부로 정해집니다.
    # (어느 쪽 출신인지는 `old_sido()` 가 시군구 이름으로 가립니다 —
    #  지명 표기와, 건물에너지 옛 코드 조회에 씁니다)
    "전남광주": NAMBU,
    "제주": JEJU,
}

# ── 시군구를 봐야 갈리는 곳 ──
#
# 각 시도에서 '예외 목록에 들면 A, 아니면 B' 꼴입니다.
# 시군구 이름은 앞부분만 맞춰 봅니다(고성 -> 고성군, 남양주 -> 남양주시).
_BY_SIGUNGU = {
    # 강원: 동해안 여섯 곳만 중부2, 나머지는 중부1
    "강원": (("고성", "속초", "양양", "강릉", "동해", "삼척"), JUNGBU2, JUNGBU1),
    # 경기: 북부 여덟 곳만 중부1, 나머지는 중부2
    "경기": (("연천", "포천", "가평", "남양주", "의정부", "양주",
              "동두천", "파주"), JUNGBU1, JUNGBU2),
    # 충북: 제천만 중부1
    "충북": (("제천",), JUNGBU1, JUNGBU2),
    # 경북: 봉화·청송은 중부1, 남부 여섯 곳은 남부, 나머지는 중부2
    #   -> 두 단계라 아래에서 따로 처리합니다.
    # 경남: 거창·함양만 중부2, 나머지는 남부
    "경남": (("거창", "함양"), JUNGBU2, NAMBU),
}

# 경북만 세 갈래입니다.
_GB_JUNGBU1 = ("봉화", "청송")
_GB_NAMBU = ("울진", "영덕", "포항", "경주", "청도", "경산")


# 통합 전 광주광역시의 다섯 구. 전남에는 자치구가 없어 이것으로 갈립니다.
_GWANGJU_GU = ("동구", "서구", "남구", "북구", "광산구")


def old_sido(addr: str) -> str:
    """통합시 주소가 **통합 전 어느 시도**였는지. 아니면 빈 문자열.

    별표1 지역은 둘 다 남부라 구분이 필요 없지만, 지명 표기(「광주 동구」
    대 「구례군」)와 건물에너지 조회에는 갈라야 합니다. 건물에너지 자료가
    **옛 시군구코드에만** 붙어 있습니다(2026-10-25 확인).
    """
    sido, sigungu = split(addr)
    if sido != "전남광주":
        return ""
    return "광주" if sigungu.strip() in _GWANGJU_GU else "전남"


def _norm_sido(token: str) -> str:
    return _SIDO.get(token.strip(), "")


def _starts_any(name: str, names) -> bool:
    """'고성군' 이 ('고성',) 에 드는지. 앞부분만 맞춰 봅니다.

    '남양주시' 가 '양주' 에 걸리면 안 되므로 startswith 를 씁니다.
    """
    return any(name.startswith(n) for n in names)


def split(addr: str):
    """주소에서 (시도, 시군구) 를 떼어 냅니다. 못 알아보면 ("", "") 입니다."""
    if not addr:
        return ("", "")
    parts = str(addr).strip().split()
    if not parts:
        return ("", "")
    sido = _norm_sido(parts[0])
    if not sido:
        return ("", "")
    sigungu = parts[1] if len(parts) > 1 else ""
    return (sido, sigungu)


def region4(addr: str) -> str:
    """주소 -> "중부1" | "중부2" | "남부" | "제주". 모르면 빈 문자열.

    **모르면 빈 문자열을 돌려줍니다.** 아무 값이나 돌려주면 화면에 그럴듯한
    배수가 찍히는데, 지역을 잘못 잡으면 배수가 30%쯤 어긋납니다.
    모르는 것은 모른다고 표시해야 합니다(CLAUDE.md 2장).
    """
    sido, sigungu = split(addr)
    if not sido:
        return ""

    if sido in _BY_SIDO:
        return _BY_SIDO[sido]

    if sido == "경북":
        if _starts_any(sigungu, _GB_JUNGBU1):
            return JUNGBU1
        if _starts_any(sigungu, _GB_NAMBU):
            return NAMBU
        return JUNGBU2

    rule = _BY_SIGUNGU.get(sido)
    if rule:
        names, hit, miss = rule
        return hit if _starts_any(sigungu, names) else miss

    return ""


def region2(r4: str) -> str:
    """네 구분 -> 원단위 비교용 두 구분. 모르면 빈 문자열.

    통계집 2쪽·8쪽: 중부1·2는 중부로, 제주는 남부로 합쳐 발표합니다.
    """
    if r4 in (JUNGBU1, JUNGBU2):
        return "중부"
    if r4 in (NAMBU, JEJU):
        return "남부"
    return ""


def of(addr: str) -> str:
    """주소에서 바로 두 구분을 얻습니다. 화면에서 가장 많이 쓰는 꼴."""
    return region2(region4(addr))


def label(addr: str) -> str:
    """화면에 적을 한 줄. 네 구분과 두 구분을 함께 밝힙니다."""
    r4 = region4(addr)
    if not r4:
        return "지역 미확인"
    r2 = region2(r4)
    return f"{r2} ({r4})"


# 광역시·특별시는 시도까지 붙여야 알아봅니다(부산 해운대구).
# 도는 시군만으로 충분합니다(계룡시).
_METRO = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종")


def place(addr: str) -> str:
    """같은 이름 절을 가르는 짧은 지명. 모르면 빈 문자열.

    녹색사찰 명단 43번 원오사(부산 해운대구)와 교수님 제적 사찰
    원오사(계룡시)가 다른 절입니다. 이름만 적으면 사람이 헷갈립니다.
    """
    sido, sigungu = split(addr)
    if not sido:
        return ""
    if sido == "세종":
        return "세종"
    if not sigungu:
        return sido
    if sido == "전남광주":
        # 광주 쪽은 구 이름이 다른 광역시와 겹쳐 시도를 붙입니다.
        return f"광주 {sigungu}" if sigungu in _GWANGJU_GU else sigungu
    return f"{sido} {sigungu}" if sido in _METRO else sigungu


def named(name: str, addr: str) -> str:
    """사찰명에 지명을 붙입니다 — 원오사(부산 해운대구)."""
    p = place(addr)
    name = (name or "").strip()
    return f"{name}({p})" if p and name else (name or p)
