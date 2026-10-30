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
import time
from typing import Callable, List, Optional, Tuple

import requests

KIND_DIAG = "diag"
KIND_REQUEST = "request"
KIND_PING = "ping"
# 초. Apps Script 웹앱은 한동안 안 쓰면 처음 부를 때 늦게 깨고, 요청은
# 시트 쓰기 + 메일까지 합니다. 5초로는 **시트에 줄이 생겼는데 화면은 실패**로
# 나왔습니다(작업지시 11 ①).
TIMEOUT_REQUEST = 20
TIMEOUT_DIAG = 10
TIMEOUT = TIMEOUT_DIAG

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


def post_detail(url: str, token: str, kind: str, data: dict,
                timeout: float = TIMEOUT,
                http: Optional[Callable] = None) -> Tuple[Optional[bool], str, float]:
    """보내고 (성공 여부, 오류 코드, 걸린 초) 를 돌려줍니다.

    성공 여부 — True · False · **주소가 없으면 None**(개발 중).
    오류 코드 — 개인정보가 없는 짧은 말만: `.gs` 가 돌려준 `err`
    (token·consent·required·kind·server) 또는 timeout · connection ·
    not_json · http_403 같은 것. 화면에 작게 보여 줘 원인을 가립니다.

    Apps Script 는 POST 에 **302** 를 돌려주고, `requests` 가 따라가며 GET 으로
    바꿉니다. 따라간 곳의 본문이 `doPost` 결과이므로 그대로 읽으면 됩니다.
    따라가지 못하고 302 가 남으면 `http_302` 로 밝힙니다.
    """
    if not (url or "").strip():
        return None, "off", 0.0
    http = http or requests.post
    t0 = time.monotonic()
    try:
        r = http(url.strip(), json={"token": token, "kind": kind, "data": data},
                 timeout=timeout)
    except requests.Timeout:
        return False, "timeout", time.monotonic() - t0
    except requests.ConnectionError:
        return False, "connection", time.monotonic() - t0
    except Exception as e:                      # 가짜 http 의 TimeoutError 등
        code = "timeout" if isinstance(e, TimeoutError) else type(e).__name__
        return False, code, time.monotonic() - t0
    took = time.monotonic() - t0
    status = getattr(r, "status_code", 200)
    if status >= 300:
        return False, f"http_{status}", took
    try:
        body = r.json()
    except ValueError:
        return False, "not_json", took
    if not isinstance(body, dict):
        return False, "not_json", took
    if body.get("ok"):
        return True, "ok", took
    return False, str(body.get("err") or "unknown")[:30], took


def post(url: str, token: str, kind: str, data: dict,
         timeout: float = TIMEOUT,
         http: Optional[Callable] = None) -> Optional[bool]:
    """보냅니다. 성공 True, 실패 False, **주소가 없으면 None**(개발 중).

    실패해도 예외를 내지 않습니다. 부르는 쪽이 사찰 화면을 멈추지 않도록.
    """
    return post_detail(url, token, kind, data, timeout, http)[0]


def ping(url: str, token: str, http: Optional[Callable] = None) -> dict:
    """관리자 점검(`?check=1`). 개인정보 없이 `kind: ping` 만 보냅니다.

    `.gs` 에 ping 을 받는 줄이 아직 없으면 `{"ok":false,"err":"kind"}` 가
    옵니다. **그것도 토큰·주소가 맞다는 증거**입니다 — 토큰이 틀리면
    kind 를 보기도 전에 `err: token` 으로 돌아옵니다.
    """
    ok, code, took = post_detail(url, token, KIND_PING, {}, TIMEOUT_REQUEST, http)
    if ok:
        verdict = "연결됨"
    elif code == "kind":
        verdict = "연결됨(ping 미설치)"
    elif code == "off":
        verdict = "보낼 곳이 설정되지 않음(APPS_SCRIPT_URL 비어 있음)"
    else:
        verdict = "연결 안 됨"
    return {"ok": ok, "code": code, "seconds": round(took, 1), "verdict": verdict}


def send_request(form: dict, honeypot: str, url: str, token: str,
                 http: Optional[Callable] = None) -> str:
    """컨설팅 요청. 돌려주는 것: 'sent' · 'failed' · 'invalid' · 'blocked' · 'off'."""
    return send_request_detail(form, honeypot, url, token, http)[0]


def send_request_detail(form: dict, honeypot: str, url: str, token: str,
                        http: Optional[Callable] = None) -> Tuple[str, str]:
    """(상태, 오류 코드). 상태는 'sent' · 'failed' · 'invalid' · 'blocked' · 'off'.

    - 숨은 칸에 값이 있으면 **자동 입력**으로 보고 보내지 않습니다('blocked')
    - 동의가 없거나 칸이 틀리면 보내지 않습니다('invalid')
    - 시간 제한은 20초. 시트 쓰기 + 메일이라 오래 걸립니다
    """
    if (honeypot or "").strip():
        return "blocked", ""
    if check_request(form):
        return "invalid", ""
    ok, code, _t = post_detail(url, token, KIND_REQUEST, request_payload(form),
                               TIMEOUT_REQUEST, http)
    if ok is None:
        return "off", code
    return ("sent", "") if ok else ("failed", code)
