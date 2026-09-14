# -*- coding: utf-8 -*-
"""
건축HUB 건축물대장정보 서비스 클라이언트
사찰 넷제로 진단 도구 — 불교탄소중립실천단 지수화풍

공공데이터포털 15134735 / BldRgstHubService
  getBrTitleInfo        표제부 (동별 연면적·구조·지붕·용도)
  getBrRecapTitleInfo   총괄표제부 (대지 전체 요약)
  getBrJijiguInfo       지역지구구역 (용도지역·용도구역)

건물에너지와 달리 요청에 platGbCd(대지구분)를 넣을 수 있어서
산 지번 사찰도 깔끔하게 걸러집니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import portal
from portal import PortalError  # noqa: F401  (호출하는 쪽에서 함께 씁니다)

BASE = "https://apis.data.go.kr/1613000/BldRgstHubService"
OP_TITLE = "getBrTitleInfo"
OP_RECAP = "getBrRecapTitleInfo"
OP_JIJIGU = "getBrJijiguInfo"

# 전통 목조 전각을 가려내는 말. 구조코드·지붕코드가 바뀌어도 견디도록
# 코드 숫자가 아니라 이름으로 판정합니다.
TRAD_STRCT = ("목",)                     # 목구조, 통나무구조 등
TRAD_ROOF = ("기와", "초가", "너와")


def _params(sigunguCd, bjdongCd, bun, ji, platGbCd="0") -> dict:
    return {
        "sigunguCd": sigunguCd,
        "bjdongCd": bjdongCd,
        "platGbCd": str(platGbCd),
        "bun": str(bun).zfill(4),
        "ji": str(ji).zfill(4),
    }


@dataclass
class Dong:
    """표제부 한 건 = 건물 한 동."""

    dongNm: str = ""
    bldNm: str = ""
    totArea: float = 0.0          # 연면적(㎡)
    archArea: float = 0.0         # 건축면적(㎡)
    strctCdNm: str = ""           # 구조
    roofCdNm: str = ""            # 지붕
    mainPurpsCdNm: str = ""       # 주용도
    etcPurps: str = ""
    grndFlrCnt: int = 0
    useAprDay: str = ""           # 사용승인일
    mainAtchGbCdNm: str = ""      # 주건축물 / 부속건축물
    engrGrade: str = ""           # 에너지효율등급
    platPlc: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_traditional(self) -> bool:
        s, r = self.strctCdNm or "", self.roofCdNm or ""
        return any(k in s for k in TRAD_STRCT) or any(k in r for k in TRAD_ROOF)

    @property
    def kind(self) -> str:
        return "전통" if self.is_traditional else "신식"

    @property
    def solar_ok(self) -> bool:
        """옥상 태양광 후보가 될 수 있는지에 대한 1차 판단."""
        return not self.is_traditional and self.totArea > 0

    @property
    def is_religious(self) -> bool:
        return "종교" in (self.mainPurpsCdNm or "")

    def name(self, seq: int = 0) -> str:
        """동명칭이 비는 일이 잦아 용도·층수로 보완합니다."""
        if self.dongNm:
            return self.dongNm
        if self.bldNm:
            return self.bldNm
        bits = []
        if self.mainPurpsCdNm:
            bits.append(self.mainPurpsCdNm)
        if self.grndFlrCnt:
            bits.append(f"{self.grndFlrCnt}층")
        tail = " ".join(bits)
        return f"이름없음 {seq}" + (f" ({tail})" if tail else "") if seq else (tail or "이름없음")

    def label(self, seq: int = 0) -> str:
        bits = [self.name(seq), f"{self.totArea:,.1f} m²"]
        if self.mainPurpsCdNm:
            bits.append(self.mainPurpsCdNm)
        if self.strctCdNm:
            bits.append(self.strctCdNm)
        if self.roofCdNm:
            bits.append(self.roofCdNm)
        return "  ·  ".join(bits)


def _to_dong(it: dict) -> Dong:
    return Dong(
        dongNm=(it.get("dongNm") or "").strip(),
        bldNm=(it.get("bldNm") or "").strip(),
        totArea=portal.num(it.get("totArea")),
        archArea=portal.num(it.get("archArea")),
        strctCdNm=(it.get("strctCdNm") or "").strip(),
        roofCdNm=(it.get("roofCdNm") or "").strip(),
        mainPurpsCdNm=(it.get("mainPurpsCdNm") or "").strip(),
        etcPurps=(it.get("etcPurps") or "").strip(),
        grndFlrCnt=int(portal.num(it.get("grndFlrCnt"))),
        useAprDay=(it.get("useAprDay") or "").strip(),
        mainAtchGbCdNm=(it.get("mainAtchGbCdNm") or "").strip(),
        engrGrade=(it.get("engrGrade") or "").strip(),
        platPlc=(it.get("platPlc") or "").strip(),
        raw=it,
    )


def fetch_dongs(sigunguCd, bjdongCd, bun, ji, service_key,
                platGbCd="0") -> List[Dong]:
    """그 지번의 건물을 동별로 가져옵니다."""
    rows, _ = portal.fetch_all(
        BASE, OP_TITLE, _params(sigunguCd, bjdongCd, bun, ji, platGbCd), service_key
    )
    dongs = [_to_dong(r) for r in rows]
    dongs.sort(key=lambda d: (-d.totArea, d.name()))
    return dongs


def fetch_recap(sigunguCd, bjdongCd, bun, ji, service_key,
                platGbCd="0") -> Optional[dict]:
    """대지 전체 요약(총괄표제부). 없는 지번도 많습니다."""
    body = portal.check(portal.request(
        BASE, OP_RECAP,
        dict(_params(sigunguCd, bjdongCd, bun, ji, platGbCd), numOfRows="10", pageNo="1"),
        service_key,
    ))
    rows = portal.items(body)
    if not rows:
        return None
    it = rows[0]
    return {
        "platArea": portal.num(it.get("platArea")),      # 대지면적
        "totArea": portal.num(it.get("totArea")),        # 연면적 합
        "archArea": portal.num(it.get("archArea")),      # 건축면적
        "mainBldCnt": int(portal.num(it.get("mainBldCnt"))),
        "atchBldCnt": int(portal.num(it.get("atchBldCnt"))),
        "totPkngCnt": int(portal.num(it.get("totPkngCnt"))),   # 주차장 태양광 검토용
        "mainPurpsCdNm": (it.get("mainPurpsCdNm") or "").strip(),
        "useAprDay": (it.get("useAprDay") or "").strip(),
        "engrGrade": (it.get("engrGrade") or "").strip(),
    }


def fetch_jijigu(sigunguCd, bjdongCd, bun, ji, service_key,
                 platGbCd="0") -> List[str]:
    """용도지역·용도구역 이름 목록. 규제 확인의 첫 실마리입니다."""
    rows, _ = portal.fetch_all(
        BASE, OP_JIJIGU, _params(sigunguCd, bjdongCd, bun, ji, platGbCd),
        service_key, cap=50,
    )
    names, seen = [], set()
    for r in rows:
        nm = (r.get("jijiguCdNm") or r.get("etcJijigu") or "").strip()
        if nm and nm not in seen:
            seen.add(nm)
            names.append(nm)
    return names


def summarize(dongs: List[Dong]) -> dict:
    """동 목록에서 사찰 진단에 필요한 것만 뽑습니다."""
    trad = [d for d in dongs if d.is_traditional]
    modern = [d for d in dongs if not d.is_traditional]
    return {
        "count": len(dongs),
        "total_area": sum(d.totArea for d in dongs),
        "trad_count": len(trad),
        "trad_area": sum(d.totArea for d in trad),
        "modern_count": len(modern),
        "modern_area": sum(d.totArea for d in modern),
        "purposes": sorted({d.mainPurpsCdNm for d in dongs if d.mainPurpsCdNm}),
        "religious_count": sum(1 for d in dongs if d.is_religious),
        "unnamed_count": sum(1 for d in dongs if not (d.dongNm or d.bldNm)),
        "oldest": min((d.useAprDay for d in dongs if d.useAprDay), default=""),
    }


def checks(dongs: List[Dong], recap: Optional[dict] = None) -> List[str]:
    """조회 결과를 어디까지 믿어도 되는지 스스로 밝힙니다.

    수국사 실제 조회에서 목조 전각이 한 동도 잡히지 않은 일이 있었습니다.
    (보고서 연면적 2,985.6 m² / 건축물대장 2,658.3 m²)
    반면 봉은사는 26동 중 21동이 전통으로 정상 분류되었습니다.
    사찰인데 전통 전각이 0동이면 '없다'가 아니라 '누락'으로 읽어야 합니다.
    """
    msgs = []
    if not dongs:
        return ["건축물대장에 등록된 건물이 없습니다. 미등재 전각일 수 있으니 방문해서 확인해야 합니다."]

    s = summarize(dongs)

    if s["trad_count"] == 0:
        msgs.append(
            "목조·기와 전각이 한 동도 잡히지 않았습니다. 전통 전각은 건축물대장에 "
            "빠져 있는 경우가 많습니다. 대웅전·법당이 실제로 있는지 현장에서 확인해 주세요."
        )
    if s["religious_count"] == 0:
        msgs.append("주용도가 종교시설인 건물이 없습니다. 지번이 맞는지 다시 확인해 주세요.")
    if s["unnamed_count"]:
        msgs.append(
            f"동 이름이 비어 있는 건물이 {s['unnamed_count']}동 있습니다. "
            "현장에서 어떤 전각인지 확인해 채워 주세요."
        )
    if recap and recap.get("totArea"):
        gap = recap["totArea"] - s["total_area"]
        if abs(gap) > max(50, recap["totArea"] * 0.03):
            msgs.append(
                f"총괄표제부 연면적({recap['totArea']:,.0f} m²)과 동별 합계"
                f"({s['total_area']:,.0f} m²)가 {abs(gap):,.0f} m² 차이납니다. "
                "누락된 동이 있을 수 있습니다."
            )
    return msgs
