# -*- coding: utf-8 -*-
"""
도로명주소 검색 API 클라이언트
사찰 넷제로 진단 도구 — 불교탄소중립실천단 지수화풍

검색어를 넣으면 주소 목록을 돌려주고,
고른 주소에서 건축물대장·건물에너지 API에 넣을 값을 뽑아냅니다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Tuple

import requests

# 검색 API 호출 주소. 앞의 것이 실패하면 뒤의 것으로 한 번 더 시도합니다.
ENDPOINTS = [
    "https://business.juso.go.kr/addrlink/addrLinkApi.do",
    "https://www.juso.go.kr/addrlink/addrLinkApi.do",
]

# 보안장비가 SQL 공격으로 오인해 IP를 차단하는 일이 있어 검색어를 미리 걸러냅니다.
_SPECIAL = re.compile(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ\s\-]")
_BANNED = re.compile(
    r"\b(select|insert|update|delete|union|drop|create|alter|truncate|table|"
    r"where|from|having|exec|script|or|and)\b",
    re.I,
)
_DASHES = re.compile(r"-{2,}")

# 자주 나오는 오류에만 쉬운 말을 붙이고, 나머지는 API가 보낸 문구를 그대로 씁니다.
FRIENDLY = {
    "E0005": "승인키가 비어 있습니다.",
    "E0006": "승인키가 올바르지 않거나 기간이 지났습니다. 주소기반산업지원서비스 마이페이지에서 확인해 주세요.",
}


class JusoError(Exception):
    """검색을 진행할 수 없을 때 발생합니다. 메시지를 그대로 화면에 보여주면 됩니다."""


@dataclass
class Juso:
    """검색 결과 한 건."""

    roadAddr: str = ""       # 전체 도로명주소
    jibunAddr: str = ""      # 지번주소
    zipNo: str = ""          # 우편번호
    admCd: str = ""          # 행정구역코드 10자리
    lnbrMnnm: str = ""       # 지번 본번
    lnbrSlno: str = ""       # 지번 부번
    mtYn: str = "0"          # 1=산, 0=대지
    bdNm: str = ""           # 건물명
    bdMgtSn: str = ""        # 건물관리번호
    name_hit: bool = False   # 건물명에 검색어가 들어감 = 절 이름으로 찾은 것
    raw: dict = field(default_factory=dict, repr=False)

    # ── 건축물대장·건물에너지 API 파라미터 ──
    @property
    def sigunguCd(self) -> str:
        return self.admCd[:5]

    @property
    def bjdongCd(self) -> str:
        return self.admCd[5:10]

    @property
    def bun(self) -> str:
        return str(self.lnbrMnnm or "0").strip().zfill(4)

    @property
    def ji(self) -> str:
        return str(self.lnbrSlno or "0").strip().zfill(4)

    @property
    def platGbCd(self) -> str:
        """대지구분코드. 0=대지, 1=산. 산중 사찰은 1인 경우가 많습니다."""
        return "1" if str(self.mtYn).strip() == "1" else "0"

    @property
    def is_mountain(self) -> bool:
        return self.platGbCd == "1"

    def building_params(self) -> dict:
        """건축물대장 API에 그대로 넣을 수 있는 형태."""
        return {
            "sigunguCd": self.sigunguCd,
            "bjdongCd": self.bjdongCd,
            "platGbCd": self.platGbCd,
            "bun": self.bun,
            "ji": self.ji,
        }

    def energy_params(self, high_voltage: bool = False) -> dict:
        """건물에너지 API용. 고압/저압은 주소로 알 수 없어 따로 정해야 합니다."""
        p = self.building_params()
        p.pop("platGbCd", None)
        p["hsprcGbCd"] = "1" if high_voltage else "2"   # 1=고압, 2=저압
        return p

    def label(self) -> str:
        """화면에 보여줄 한 줄."""
        mark = " (산)" if self.is_mountain else ""
        name = f"  · {self.bdNm}" if self.bdNm else ""
        found = "   (이름으로 찾음)" if self.name_hit else ""
        return f"{self.jibunAddr}{mark}{name}{found}"

    def check(self) -> List[str]:
        """값이 이상하면 경고 문구를 돌려줍니다."""
        msgs = []
        if len(self.admCd) != 10:
            msgs.append("행정구역코드가 10자리가 아닙니다. 이 주소로는 건물 조회가 어렵습니다.")
        if not str(self.lnbrMnnm).strip().isdigit():
            msgs.append("지번 본번이 비어 있습니다. 건물이 없는 땅일 수 있습니다.")
        if self.is_mountain:
            msgs.append("산 지번입니다. 건물 조회 시 대지구분코드를 1로 넣어야 합니다.")
        return msgs


def clean_keyword(keyword: str) -> str:
    kw = _SPECIAL.sub(" ", keyword or "")
    kw = _BANNED.sub(" ", kw)
    kw = _DASHES.sub(" ", kw)
    return re.sub(r"\s+", " ", kw).strip()


# 절 이름으로 찾으면 뒤쪽 쪽수에 묻힙니다. 금산사는 270건 중 1쪽에 없었습니다
# (`금산면` 때문에 쌍용리가 밀려 올라옴). 결과를 버리지 않고 정렬만 바꿉니다.
NAME_SCAN = 100          # 1쪽에서 훑어볼 건수. API 1회 최대치


def _name_first(rows: List["Juso"], keyword: str) -> List["Juso"]:
    """건물명에 검색어가 들어간 것을 표시하고 앞으로 올립니다.

    그냥 "들어갔는가"로만 보면 엉뚱한 것이 1위가 됩니다. 수국사로 찾으면
    "봉산 수국사지구 공중 화장실" 이 진짜 수국사보다 위에 왔습니다.
    이름이 **딱 맞는 것**을 먼저 올립니다.
    """
    kw = clean_keyword(keyword).replace(" ", "")
    if not kw:
        return rows

    def rank(j) -> int:
        nm = (j.bdNm or "").replace(" ", "")
        if not nm or kw not in nm:
            return 9
        if nm == kw:
            return 0            # 이름이 딱 맞음
        if nm.startswith(kw):
            return 1            # 실상사약수암
        return 2                # 봉산수국사지구공중화장실

    for j in rows:
        j.name_hit = rank(j) < 9
    # 같은 등급 안에서는 API 가 준 차례를 지킵니다(sorted 는 안정 정렬).
    return sorted(rows, key=rank)


def _loads(text: str) -> dict:
    """순수 JSON과 콜백으로 감싼 응답을 모두 받아냅니다."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise JusoError("주소 서버가 알 수 없는 형식으로 답했습니다. 잠시 뒤 다시 시도해 주세요.")
        return json.loads(m.group(0))


def search(
    keyword: str,
    confm_key: str,
    page: int = 1,
    per_page: int = 5,
    timeout: int = 10,
) -> Tuple[List[Juso], int]:
    """주소를 검색합니다. (결과 목록, 전체 건수)를 돌려줍니다."""
    if not confm_key:
        raise JusoError(FRIENDLY["E0005"])

    kw = clean_keyword(keyword)
    if len(kw) < 2:
        raise JusoError("주소를 두 글자 이상 넣어 주세요. 예: 구산동 314")

    # 1쪽에서는 넓게 훑어 이름으로 찾은 것을 앞으로 올립니다.
    # 호출 수는 그대로입니다(한 번). 2쪽부터는 예전대로 쪽 단위로 받습니다.
    wide = page == 1
    params = {
        "confmKey": confm_key,
        "currentPage": page,
        "countPerPage": NAME_SCAN if wide else per_page,
        "keyword": kw,
        "resultType": "json",
        "hstryYn": "N",
        "firstSort": "none",
        "addInfoYn": "N",
    }

    last_err = None
    for url in ENDPOINTS:
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            data = _loads(r.text)
        except requests.RequestException as e:
            last_err = e
            continue

        rows, total = _unpack(data)
        if wide:
            rows = _name_first(rows, kw)[:per_page]
        return rows, total

    raise JusoError(f"주소 서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요. ({last_err})")


def _unpack(data: dict) -> Tuple[List[Juso], int]:
    results = data.get("results") or {}
    common = results.get("common") or {}

    code = str(common.get("errorCode", "")).strip()
    if code and code != "0":
        raise JusoError(FRIENDLY.get(code) or common.get("errorMessage") or f"오류 {code}")

    rows = results.get("juso") or []
    out = [
        Juso(
            roadAddr=j.get("roadAddr", ""),
            jibunAddr=j.get("jibunAddr", ""),
            zipNo=j.get("zipNo", ""),
            admCd=str(j.get("admCd", "")).strip(),
            lnbrMnnm=str(j.get("lnbrMnnm", "")).strip(),
            lnbrSlno=str(j.get("lnbrSlno", "")).strip(),
            mtYn=str(j.get("mtYn", "0")).strip(),
            bdNm=j.get("bdNm", ""),
            bdMgtSn=j.get("bdMgtSn", ""),
            raw=j,
        )
        for j in rows
    ]
    try:
        total = int(common.get("totalCount", len(out)))
    except (TypeError, ValueError):
        total = len(out)
    return out, total
