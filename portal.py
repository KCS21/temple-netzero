# -*- coding: utf-8 -*-
"""
공공데이터포털 공통 호출부
사찰 넷제로 진단 도구 — 불교탄소중립실천단 지수화풍

건축HUB 두 서비스(건축물대장·건물에너지)가 같은 응답 구조와
같은 에러 코드표를 쓰기 때문에 여기에 모아 두었습니다.
"""
from __future__ import annotations

import time
from typing import List, Tuple

import requests

# 활용가이드 「OpenAPI 에러 코드정리」를 쉬운 말로 옮긴 것
ERRORS = {
    "00": None,
    "01": "제공기관 쪽에 일시적인 오류가 있습니다. 잠시 뒤 다시 해보세요.",
    "02": "제공기관 데이터베이스에 오류가 있습니다. 잠시 뒤 다시 해보세요.",
    "05": "서버 연결에 실패했습니다. 인터넷 연결을 확인해 주세요.",
    "10": "보낸 값의 형식이 맞지 않습니다.",
    "11": "필수 항목이 빠졌습니다.",
    "12": "해당 서비스가 없거나 폐기되었습니다.",
    "20": "이 서비스를 쓸 권한이 없습니다. 공공데이터포털에서 활용신청이 승인됐는지 확인해 주세요.",
    "21": "인증키를 일시적으로 쓸 수 없습니다. 잠시 뒤 다시 해보세요.",
    "30": "등록되지 않은 인증키입니다. 키를 다시 확인해 주세요.",
    "31": "인증키 사용 기한이 지났습니다. 공공데이터포털에서 갱신해 주세요.",
    "99": "알 수 없는 오류입니다.",
}

# 활용신청 직후 흔히 겪는 상황이라 따로 안내합니다.
HINT_20 = "\n신청한 지 얼마 안 됐다면 권한이 아직 안 열렸을 수 있습니다. 하루 뒤에 다시 해보세요."

NL = chr(10)            # 줄바꿈
MAX_ROWS = 100          # 1회 요청 최대 목록 수 (활용가이드 기준)


class PortalError(Exception):
    """화면에 그대로 보여줄 수 있는 오류."""


def request(base: str, op: str, params: dict, service_key: str,
            timeout: int = 15, retries: int = 2) -> dict:
    """공공데이터포털 호출. 일시적인 실패는 몇 번 다시 시도합니다.

    제공기관 서버가 잠깐 JSON 대신 HTML 오류 쪽지를 보내는 일이 잦습니다.
    예전에는 그 경우 바로 포기했는데, 한 번만 더 해보면 되는 일이 많아
    연결 실패와 똑같이 다시 시도합니다.
    """
    if not service_key:
        raise PortalError(
            "공공데이터포털 인증키가 비어 있습니다."
            + NL + NL +
            "같은 폴더의 키.txt 에 인증키를 넣어 주세요."
        )

    q = dict(params)
    q["serviceKey"] = service_key
    q["_type"] = "json"

    last, resp, head, bad_format = None, None, "", False
    for attempt in range(retries + 1):
        try:
            resp = requests.get(f"{base}/{op}", params=q, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except ValueError:
            bad_format = True
            head = " ".join((resp.text or "").split())[:150] if resp is not None else ""
        except requests.RequestException as e:
            last, bad_format = e, False
        if attempt < retries:
            time.sleep(0.8 * (attempt + 1))

    tries = retries + 1
    if bad_format:
        raise PortalError(
            f"제공기관 서버가 잠시 불안정합니다. {tries}번 시도했지만 자료를 받지 못했습니다."
            + NL + NL +
            "**1~2분 뒤에 다시 눌러 보세요.** 대개 그 사이에 풀립니다."
            + NL +
            "여러 번 해도 같으면 공공데이터포털이 점검 중일 수 있습니다."
            + NL + NL +
            f"(서버가 보낸 내용: {head})"
        )
    raise PortalError(
        f"서버에 연결하지 못했습니다. {tries}번 시도했습니다."
        + NL + NL +
        "인터넷 연결을 확인하시고, 1~2분 뒤에 다시 눌러 보세요."
        + NL + NL +
        f"({last})"
    )


def check(data: dict) -> dict:
    """헤더의 결과코드를 확인하고 body를 돌려줍니다."""
    resp = data.get("response") or {}
    head = resp.get("header") or {}

    code = str(head.get("resultCode", "")).strip()
    if code:
        code = code.zfill(2)
    if code and code != "00":
        msg = ERRORS.get(code) or head.get("resultMsg") or f"오류 {code}"
        if code == "20":
            msg += HINT_20
        raise PortalError(msg)
    return resp.get("body") or {}


def items(body: dict) -> List[dict]:
    """items.item 을 항상 리스트로 돌려줍니다. 자료가 없으면 빈 리스트."""
    box = body.get("items")
    if not box or isinstance(box, str):
        return []
    rows = box.get("item") if isinstance(box, dict) else box
    if not rows:
        return []
    if isinstance(rows, dict):      # 1건이면 객체 하나로 옵니다.
        return [rows]
    return list(rows)


def total(body: dict) -> int:
    try:
        return int(body.get("totalCount") or 0)
    except (TypeError, ValueError):
        return 0


def fetch_all(base: str, op: str, params: dict, service_key: str,
              cap: int = 300, pause: float = 0.12) -> Tuple[List[dict], int]:
    """페이지를 끝까지 넘기며 모읍니다. cap 건에서 멈춥니다."""
    page, out, grand = 1, [], 0
    while True:
        q = dict(params, numOfRows=str(MAX_ROWS), pageNo=str(page))
        body = check(request(base, op, q, service_key))
        rows = items(body)
        grand = total(body) or grand
        out.extend(rows)
        if len(out) >= min(grand, cap) or not rows or len(rows) < MAX_ROWS:
            break
        page += 1
        time.sleep(pause)
    return out[:cap], grand


def num(v, default=0.0) -> float:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default
