# -*- coding: utf-8 -*-
"""
구글 시트로 보내기 — 공개 홈페이지 (작업지시 10 3장)
불교탄소중립실천단 지수광풍

받는 곳은 교수님이 설치한 Apps Script 웹앱(`apps_script_지수광풍.gs`)입니다.
**이것 말고는 아무 데도 저장하지 않습니다.** 화면·로그·파일에 개인정보를
남기지 않습니다(0장 6번). 그래서 실패해도 내용을 찍지 않습니다.

열쇠 이름은 `.gs` 의 `DIAG_COLS`·`REQ_COLS` 와 **글자까지 같아야** 합니다.
다르면 시트에 빈칸으로 들어갑니다. `test_public.py` 가 맞대어 봅니다.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional

import requests

KIND_DIAG = "diag"
KIND_REQUEST = "request"
TIMEOUT = 5            # 초. 넘으면 실패로 보고 사찰 화면은 그대로 갑니다

# `.gs` 의 열에서 Apps Script 가 채우는 「받은시각」·「처리 상태」를 뺀 것
DIAG_COLS = ("절 이름", "지번주소", "조회연도", "입력 방식",
             "연간 전기(kWh)", "도시가스(kWh)", "등유(L)", "LPG(kg)", "화목 사용",
             "난방 수단", "배출량(t)", "계절비", "유형", "앱 버전")
REQ_COLS = ("절 이름", "주소", "담당자 이름", "연락처", "요청 내용", "동의",
            "자가진단 요약")

REQ_MAX_TEXT = 1000     # 요청 내용 글자 수
SEND_LIMIT = 3          # 한 사람(세션)이 보낼 수 있는 요청 수

CONSENT_TITLE = "개인정보 수집·이용 동의 (필수)"
CONSENT_LINES = (
    "수집하는 곳: 불교탄소중립실천단 지수광풍",
    "목적: 컨설팅 요청에 대한 상담 연락",
    "항목: 담당자 이름, 연락처(전화 또는 이메일)",
    "보유 기간: 상담이 끝난 뒤 1년. 요청하시면 즉시 지웁니다",
    "동의하지 않으실 수 있으며, 이 경우 컨설팅 요청을 접수할 수 없습니다",
)
CONSENT_CHECK = "위 내용을 읽고 동의합니다"

SENT_TEXT = "요청이 접수되었습니다. 지수광풍이 연락드리겠습니다."
FAIL_TEXT = "접수 중 문제가 생겼습니다. 잠시 뒤 다시 보내 주세요."

_PHONE = re.compile(r"^[0-9\-]{9,}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def contact_ok(v: str) -> bool:
    """전화(숫자·하이픈 9자 이상) 또는 이메일 형식 중 하나."""
    v = (v or "").strip()
    if _PHONE.match(v.replace(" ", "")):
        return sum(c.isdigit() for c in v) >= 9
    return bool(_EMAIL.match(v))


def check_request(form: dict) -> List[str]:
    """빠진 것·틀린 것을 사람이 읽을 말로. 비어 있으면 보내도 됩니다."""
    errs = []
    for k in ("절 이름", "주소", "담당자 이름"):
        if not str(form.get(k) or "").strip():
            errs.append(f"{k}을(를) 넣어 주세요.")
    c = str(form.get("연락처") or "").strip()
    if not c:
        errs.append("연락처를 넣어 주세요.")
    elif not contact_ok(c):
        errs.append("연락처는 전화번호(예: 02-123-4567) 또는 이메일로 넣어 주세요.")
    if len(str(form.get("요청 내용") or "")) > REQ_MAX_TEXT:
        errs.append(f"요청 내용은 {REQ_MAX_TEXT:,}자 이내로 줄여 주세요.")
    if form.get("동의") is not True:
        errs.append("개인정보 수집·이용에 동의해 주셔야 접수할 수 있습니다.")
    return errs


def request_payload(form: dict) -> dict:
    """`.gs` 의 REQ_COLS 열쇠만 골라 담습니다. 다른 것은 보내지 않습니다."""
    out = {k: str(form.get(k) or "").strip() for k in REQ_COLS}
    out["동의"] = form.get("동의") is True
    return out


def post(url: str, token: str, kind: str, data: dict,
         timeout: float = TIMEOUT,
         http: Optional[Callable] = None) -> Optional[bool]:
    """보냅니다. 성공 True, 실패 False, **주소가 없으면 None**(개발 중).

    실패해도 예외를 내지 않습니다. 부르는 쪽이 사찰 화면을 멈추지 않도록.
    """
    if not (url or "").strip():
        return None
    http = http or requests.post
    try:
        r = http(url.strip(), json={"token": token, "kind": kind, "data": data},
                 timeout=timeout)
        if getattr(r, "status_code", 200) >= 400:
            return False
        try:
            body = r.json()
        except ValueError:
            return False
        return bool(body.get("ok"))
    except Exception:
        return False


def send_request(form: dict, honeypot: str, url: str, token: str,
                 http: Optional[Callable] = None) -> str:
    """컨설팅 요청. 돌려주는 것: 'sent' · 'failed' · 'invalid' · 'blocked' · 'off'.

    - 숨은 칸에 값이 있으면 **자동 입력**으로 보고 보내지 않습니다('blocked')
    - 동의가 없거나 칸이 틀리면 보내지 않습니다('invalid')
    """
    if (honeypot or "").strip():
        return "blocked"
    if check_request(form):
        return "invalid"
    ok = post(url, token, KIND_REQUEST, request_payload(form), http=http)
    if ok is None:
        return "off"
    return "sent" if ok else "failed"
