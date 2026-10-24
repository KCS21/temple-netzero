# -*- coding: utf-8 -*-
"""
건축HUB 건축물대장정보 서비스 클라이언트
사찰 넷제로 진단 도구 — 불교탄소중립실천단 지수광풍

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
    def kind(self) -> str:
        """전통 / 확인 필요 / 신식 **세 갈래**입니다.

        예전에는 목구조든 기와지붕이든 하나만 걸리면 「전통」으로 보고
        태양광 후보에서 빼 버렸습니다. 그런데 **철근콘크리트로 지어 놓고
        지붕만 기와를 얹은 전각**이 흔합니다. 그런 동은 지붕에 판을 올릴
        수 있는데도 자동으로 빠졌습니다.

        구조가 목재면 전통, 구조는 아닌데 지붕만 전통 재료면 **현장에서
        판단**하도록 세 번째 갈래로 둡니다(CLAUDE.md 2장).
        """
        s, r = self.strctCdNm or "", self.roofCdNm or ""
        if any(k in s for k in TRAD_STRCT):
            return "전통"
        if any(k in r for k in TRAD_ROOF):
            return "확인 필요"
        return "신식"

    @property
    def is_traditional(self) -> bool:
        return self.kind == "전통"

    @property
    def needs_check(self) -> bool:
        """구조는 목재가 아닌데 지붕만 기와·초가·너와."""
        return self.kind == "확인 필요"

    @property
    def solar_ok(self) -> bool:
        """옥상 태양광 후보가 될 수 있는지에 대한 1차 판단.

        「확인 필요」는 빼지 않습니다. 현장에서 보고 정할 일입니다.
        """
        return not self.is_traditional and self.totArea > 0

    @property
    def indr_parking(self) -> float:
        """연면적에 **들어 있는** 주차장 면적(옥내 기계식 + 옥내 자주식).

        원단위 통계의 분모는 주차장을 뺀 연면적입니다(통계집 3쪽·8쪽).

        **옥외는 빼지 않습니다.** 옥외 주차장은 건물이 아니라 애초에
        연면적에 들어가지 않습니다. 넷을 다 빼면 분모가 두 번 깎여
        배수가 부풀어 오릅니다. 실제로 수국사에 oudrAutoArea 184 m² 가
        있어서, 넷을 다 뺐으면 분모가 7% 잘못 깎였을 것입니다.
        """
        return (portal.num(self.raw.get("indrMechArea"))
                + portal.num(self.raw.get("indrAutoArea")))

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


# 사찰에 있을 까닭이 없는 주용도. 이런 것이 섞여 있으면 지번이 어긋났거나
# 남의 건물이 함께 잡힌 것입니다.
#
# **종교시설이 "없을 때" 경고하면 안 됩니다.** 건축법 시행령 별표1 에서
# 종교집회장은 **500m2 미만이면 제2종근린생활시설**입니다. 337m2 짜리 작은
# 절은 정상인데 경고를 받았습니다. 요사채가 단독주택으로 잡히는 것도
# 마찬가지입니다. 그래서 없을 때가 아니라 **이상한 것이 있을 때** 경고합니다.
ODD_PURPOSES = ("공장", "판매시설", "위험물", "자동차관련", "발전시설",
                "운수시설", "창고시설", "위락시설", "숙박시설")

# 태양광을 못 하는 것이 아니라 절차가 있는 곳. 후보에서 빼지 않습니다.
RESTRICTED_ZONES = ("개발제한구역", "보전녹지", "제한보호구역")


def restricted(jijigu: Optional[List[str]]) -> List[str]:
    """용도지역·구역 목록에서 태양광 협의가 필요한 것만 추립니다."""
    if not jijigu:
        return []
    return [z for z in jijigu if any(k in z for k in RESTRICTED_ZONES)]


def solar_label(d: Dong, has_restriction: bool = False) -> str:
    """표의 「태양광」 칸에 적을 한 마디.

    규제 구역이라고 후보에서 빼지 않습니다. **못 하는 것이 아니라 절차가
    있는 것**입니다(관할 지자체 질의로만 확정됩니다).
    """
    if d.is_traditional or d.totArea <= 0:
        return "제외"
    if d.needs_check:
        return "확인 필요"
    return "협의 필요" if has_restriction else "후보"


# 같은 본번에 지번이 이보다 많으면 **목록을 만들지 않습니다.**
#
# 청정사 본번 0001 에 다른 지번이 **89개**, 아리담문화원 0111 에 **166개**
# 있었습니다. 동네 전체가 한 본번인 곳입니다. 시험 삼아 전부 훑었더니
# 남의 건물 전기가 20여 건(최대 245,594 kWh) 잡혔습니다.
# 2026-09-13 에 고친 `picked or rows` 폴백과 **같은 종류의 사고**입니다.
#
# 명단 29곳 분포 — 0개 14 · 1~5개 8 · 그다음이 9, 13, 28, 33, 62, 166.
# 5와 9 사이가 비어 있어 10 에서 끊으면 안전합니다.
SIBLING_MAX = 10


def siblings(sigunguCd, bjdongCd, bun, service_key, platGbCd="0",
             exclude_ji: str = "") -> Dict[str, dict]:
    """같은 본번의 **다른 지번**들. `ji` 를 빼고 한 번만 호출합니다.

    부번을 1~20 으로 두드리면 호출이 20배입니다. `ji` 를 빼면 한 번에
    다 옵니다(원오사 375 -> 375, 375-3 이 함께. 2026-10-24 확인).

    {"0003": {"지번": "375-3", "연면적": 336.9, "주용도": "제2종근린생활시설",
              "사용승인일": "20161221", "동수": 1}} 꼴입니다.
    """
    p = {"sigunguCd": sigunguCd, "bjdongCd": bjdongCd,
         "platGbCd": str(platGbCd), "bun": str(bun).zfill(4)}
    rows, _ = portal.fetch_all(BASE, OP_TITLE, p, service_key, cap=200)
    here = str(exclude_ji or "").zfill(4)
    out: Dict[str, dict] = {}
    for it in rows:
        ji = (it.get("ji") or "0000").strip().zfill(4)
        if ji == here:
            continue
        # 「569」와 「569-1」은 **다른 땅**인데 목록에서 나란히 놓으면
        # 부번이 없는 쪽이 본번처럼 보여 헷갈립니다. 화면에 적을 이름을
        # 따로 둡니다(작업지시 08 ③). `지번` 은 그대로 둡니다 - 주소를
        # 만들 때 쓰는 값이라 괄호가 붙으면 안 됩니다.
        bare = f"{int(str(bun))}"
        cur = out.setdefault(ji, {
            "지번": bare + (f"-{int(ji)}" if int(ji) else ""),
            "표시": bare + (f"-{int(ji)}" if int(ji) else " (부번 없음)"),
            "연면적": 0.0, "주용도": "", "사용승인일": "", "동수": 0,
        })
        cur["연면적"] += portal.num(it.get("totArea"))
        cur["동수"] += 1
        nm = (it.get("mainPurpsCdNm") or "").strip()
        if nm and nm not in cur["주용도"]:
            cur["주용도"] = (cur["주용도"] + " / " + nm).strip(" /")
        ap = (it.get("useAprDay") or "").strip()
        if ap and (not cur["사용승인일"] or ap < cur["사용승인일"]):
            cur["사용승인일"] = ap
    return {k: v for k, v in out.items() if v["연면적"] > 0}


def summarize(dongs: List[Dong]) -> dict:
    """동 목록에서 사찰 진단에 필요한 것만 뽑습니다."""
    trad = [d for d in dongs if d.is_traditional]
    check = [d for d in dongs if d.needs_check]
    modern = [d for d in dongs if d.kind == "신식"]
    total_area = sum(d.totArea for d in dongs)
    parking = sum(d.indr_parking for d in dongs)
    return {
        "count": len(dongs),
        "total_area": total_area,
        # 원단위 분모. 주차장을 뺀 연면적입니다(통계집 3쪽·8쪽).
        "parking_area": parking,
        "area_excl_parking": max(total_area - parking, 0.0),
        "trad_count": len(trad),
        "trad_area": sum(d.totArea for d in trad),
        "check_count": len(check),
        "check_area": sum(d.totArea for d in check),
        "modern_count": len(modern),
        "modern_area": sum(d.totArea for d in modern),
        "purposes": sorted({d.mainPurpsCdNm for d in dongs if d.mainPurpsCdNm}),
        "religious_count": sum(1 for d in dongs if d.is_religious),
        "odd_purposes": sorted({
            d.mainPurpsCdNm for d in dongs
            if d.mainPurpsCdNm and any(k in d.mainPurpsCdNm for k in ODD_PURPOSES)
        }),
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
            "빠져 있는 경우가 많습니다. 목조 전각이 실제로 있는지 현장에서 확인해 주세요."
        )
    # 종교시설이 **없다고** 경고하지 않습니다(2026-10-24 뒤집음).
    # 종교집회장은 500m2 미만이면 제2종근린생활시설이고, 요사채는 단독주택으로
    # 잡힙니다. 작은 절이 정상인데 경고를 받던 문제였습니다.
    if s["odd_purposes"]:
        msgs.append(
            f"사찰에 있기 어려운 용도가 섞여 있습니다: {' · '.join(s['odd_purposes'])}. "
            "지번이 맞는지, 남의 건물이 함께 잡힌 것은 아닌지 확인해 주세요."
        )
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
