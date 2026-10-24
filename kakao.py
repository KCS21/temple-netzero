# -*- coding: utf-8 -*-
"""
카카오 지도 — 절 이름으로 장소 찾기
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

도로명주소 검색은 **건물 이름이 등록된 절만** 찾습니다. 「원오사」로 찾으면
부산 한 곳만 나오고 계룡 원오사는 안 나옵니다. 교수님이 네이버 지도에서
손으로 하시던 일을 여기서 합니다.

**결과를 저장하지 않습니다.**

카카오 개발자 포럼에 운영자가 「DB 에 저장해 배치로 돌리는 방식은 정책상
금지」라고 답한 글이 있습니다(약관 원문은 확인하지 못했습니다). 그래서

  - 화면에 **보여 주기만** 하고 `사찰기록.csv` 에 남기지 않습니다
  - 회원이 고른 주소는 **도로명주소 API 로 다시 조회**해서 그 결과만 저장합니다
  - 일괄 조회(`batch.py`)에는 **쓰지 않습니다**

키가 없으면 단추를 아예 보이지 않습니다. 오류 화면이 나오면 안 됩니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import requests

import portal          # hide_keys

URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
SIZE = 15          # 한 쪽 최대 15. page 는 최대 45 쪽
MAX_PAGES = 3      # 45건이면 충분합니다. 더 보려면 주소로 찾는 편이 빠릅니다

_NL = chr(10)


class KakaoError(Exception):
    """화면에 그대로 보여줄 수 있는 오류. 다음 행동이 붙어 있습니다."""


@dataclass
class Place:
    """지도에서 찾은 장소 한 건."""

    name: str = ""            # place_name
    jibun: str = ""           # address_name (지번)
    road: str = ""            # road_address_name (도로명)
    category: str = ""        # category_name
    raw: dict = field(default_factory=dict, repr=False)

    def label(self) -> str:
        addr = self.jibun or self.road or "주소 없음"
        return f"{self.name}  ·  {addr}"

    @property
    def search_key(self) -> str:
        """도로명주소 API 로 다시 찾을 때 넣을 말.

        지번이 가장 잘 걸립니다. 없으면 도로명으로.
        """
        return self.jibun or self.road


def _app_name(body: str) -> str:
    """오류 본문의 App(이름) 에서 앱 이름을 꺼냅니다. 못 찾으면 빈 문자열."""
    i, j = body.find("App("), body.find(")")
    return body[i + 4:j] if 0 <= i < j else ""


def _message(status: int, body: str) -> str:
    """회원이 알아들을 말로 바꿉니다. 도로명주소 검색은 계속 쓸 수 있습니다."""
    if status == 401:
        return ("카카오 키가 올바르지 않습니다." + _NL + _NL +
                "키.txt 의 `카카오=` 줄을 확인해 주세요. "
                "developers.kakao.com 의 **REST API 키**여야 합니다.")
    if status == 403:
        app = _app_name(body)
        who = f"앱 **「{app}」** 에서 " if app else ""
        return ("카카오 지도(로컬) 사용이 꺼져 있습니다." + _NL + _NL +
                f"developers.kakao.com → 내 애플리케이션 → {who}"
                "**카카오맵** 을 켜 주세요. 키는 제대로 들어 있습니다." + _NL + _NL +
                "**그동안 주소로 찾기는 그대로 됩니다.**")
    if status == 429:
        return ("카카오 하루 호출 한도를 넘었습니다(무료 10만 건)." + _NL + _NL +
                "내일 다시 되고, 그동안 **주소로 찾기**는 그대로 됩니다.")
    return ("지도 검색이 되지 않습니다." + _NL + _NL +
            "**주소로 찾기는 그대로 쓸 수 있습니다.** "
            f"(서버가 보낸 것: {status} {body[:80]})")


def search(keyword: str, rest_key: str, pages: int = MAX_PAGES
           ) -> Tuple[List[Place], int]:
    """절 이름으로 지도를 찾습니다. (목록, 전체 건수).

    키가 비어 있으면 부르지 마십시오. 부르는 쪽에서 막습니다.
    """
    kw = (keyword or "").strip()
    if not kw:
        raise KakaoError("찾을 말을 넣어 주세요.")
    if not rest_key:
        raise KakaoError("카카오 키가 없습니다.")

    out: List[Place] = []
    total = 0
    for page in range(1, max(1, pages) + 1):
        try:
            r = requests.get(
                URL, params={"query": kw, "size": SIZE, "page": page},
                headers={"Authorization": f"KakaoAK {rest_key}"}, timeout=10)
        except requests.RequestException as e:
            raise KakaoError(
                "지도 서버에 연결하지 못했습니다." + _NL + _NL +
                f"**주소로 찾기는 그대로 됩니다.** ({portal.hide_keys(e)})")
        if r.status_code != 200:
            raise KakaoError(_message(r.status_code, r.text))
        try:
            data = r.json()
        except ValueError:
            raise KakaoError(_message(r.status_code, r.text))

        meta = data.get("meta") or {}
        total = int(meta.get("pageable_count") or meta.get("total_count") or 0)
        for d in data.get("documents") or []:
            out.append(Place(
                name=(d.get("place_name") or "").strip(),
                jibun=(d.get("address_name") or "").strip(),
                road=(d.get("road_address_name") or "").strip(),
                category=(d.get("category_name") or "").strip(),
                raw=d,
            ))
        if meta.get("is_end", True):
            break
    return out, total
