# -*- coding: utf-8 -*-
"""
인증키 읽기
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

같은 폴더의 `키.txt` 에서 인증키 두 개를 읽습니다.
코드에는 키를 남기지 않습니다. 모임에 배포할 때는 `키.txt` 만 빼고 주면 됩니다.

키.txt 는 두 줄입니다.

    도로명주소=여기에_승인키
    공공데이터포털=여기에_인증키

메모장으로 저장하면 인코딩이 제각각이라 UTF-8 과 cp949 를 모두 받습니다.
"""
from __future__ import annotations

import io
import os

NL = chr(10)            # 줄바꿈 (백슬래시 escape 를 쓰지 않습니다)
KEY_FILE = "키.txt"
CONFM = "도로명주소"
SERVICE = "공공데이터포털"
KAKAO = "카카오"          # 지도에서 절 이름 찾기. **없어도 도구는 돕니다**

TEMPLATE = f"{CONFM}=\n{SERVICE}=\n"


# 키에 쓰일 수 있는 글자. 영문·숫자에 더해, base64 와 URL 인코딩에 나오는
# 기호까지만 엽니다. 실제 키 셋을 보면 도로명주소가 `=` 로 끝나고 나머지는
# 영문·숫자뿐입니다.
_KEY_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
              "abcdefghijklmnopqrstuvwxyz"
              "0123456789"
              "-_=+/.%~")


def bad_key(value: str) -> str:
    """키 값이 성하면 빈 문자열, 이상하면 **까닭**을 돌려줍니다.

    **왜 미리 보는가** — 카카오 키는 HTTP 헤더에 실립니다. 헤더는 영문만
    담을 수 있어서, 값에 한글이 섞이면 `requests` 가 보내기도 전에
    UnicodeEncodeError 로 터집니다. 실제로 배포판에서 「지도에서 찾기」를
    누르자 **화면 전체가 죽었습니다**(2026-10-24).

    도로명주소·공공데이터포털 키는 질의 문자열이라 터지지는 않지만, 대신
    「승인되지 않은 KEY」 같은 **엉뚱한 안내**로 되돌아옵니다. 어느 쪽이든
    사람은 무엇이 잘못됐는지 알 수 없습니다. 보내기 전에 걸러 냅니다.
    """
    v = (value or "").strip()
    if not v:
        return "값이 비어 있습니다."
    if any(not c.isascii() for c in v):
        return ("한글 같은 영문 아닌 글자가 섞여 있습니다. "
                "이름 칸의 글자가 값 칸에 딸려 들어갔을 수 있습니다.")
    bad = sorted({c for c in v if c not in _KEY_OK})
    if bad:
        shown = " ".join(("빈칸" if c == " " else c) for c in bad[:5])
        return f"키에 쓰이지 않는 글자가 있습니다: {shown}"
    return ""


def _checked(name: str, value: str, folder: str) -> str:
    """키를 검사해 그대로 돌려줍니다. 이상하면 다음 행동을 붙여 멈춥니다."""
    why = bad_key(value)
    if not why:
        return value
    raise KeyError_(
        f"**{name} 키 값이 잘못 들어갔습니다.** {why}" + NL + NL +
        "**영문·숫자만 넣어 주세요.** "
        "(도로명주소 키는 끝에 = 가 올 수 있습니다)" + NL + NL +
        f"고치실 곳: {path(folder)} "
        "— 웹에 올리셨으면 Streamlit 비밀 보관함입니다."
    )


class KeyError_(Exception):
    """화면에 그대로 보여줄 수 있는 오류. 다음 행동이 붙어 있습니다."""


def path(folder: str = "") -> str:
    here = folder or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, KEY_FILE)


def guide(folder: str = "") -> str:
    """오류로 끝내지 않고 만드는 법을 알려줍니다."""
    return (
        f"인증키 파일이 없거나 비어 있습니다.\n\n"
        f"아래 위치에 `{KEY_FILE}` 을 만들고, 등호 뒤에 각자 받은 키를 넣어 주세요.\n\n"
        f"    {path(folder)}\n\n"
        f"    {CONFM}=여기에_승인키\n"
        f"    {SERVICE}=여기에_인증키\n\n"
        f"{CONFM} 승인키는 business.juso.go.kr, "
        f"{SERVICE} 인증키는 data.go.kr 마이페이지에서 받습니다.\n"
        f"공공데이터포털은 Decoding 키를 넣으셔야 합니다."
    )


def make_blank(folder: str = "") -> str:
    """빈 키 파일을 만들어 둡니다. 이미 있으면 그대로 둡니다."""
    p = path(folder)
    if not os.path.exists(p):
        io.open(p, "w", encoding="utf-8").write(TEMPLATE)
    return p


def _read(p: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return io.open(p, encoding=enc).read()
        except UnicodeDecodeError:
            continue
    raise KeyError_(f"`{KEY_FILE}` 을 읽지 못했습니다. 메모장에서 다시 저장해 주세요.")


def _from_secrets() -> tuple:
    """웹에 올렸을 때 씁니다. Streamlit 이 관리하는 비밀 보관함에서 읽습니다.

    파일로 두면 GitHub 에 딸려 올라갈 수 있어, 웹에서는 이쪽을 씁니다.
    내 컴퓨터에서 돌릴 때는 보관함이 없으므로 그냥 넘어갑니다.
    """
    try:
        import streamlit as st
        sec = st.secrets
        return (str(sec.get(CONFM, "")).strip(),
                str(sec.get(SERVICE, "")).strip())
    except Exception:
        return ("", "")


def load(folder: str = "") -> tuple:
    """(도로명주소 승인키, 공공데이터포털 인증키) 를 돌려줍니다.

    웹에 올렸으면 Streamlit 비밀 보관함을, 내 컴퓨터면 키.txt 를 씁니다.
    """
    confm, service = _from_secrets()
    if confm and service:
        return (_checked(CONFM, confm, folder),
                _checked(SERVICE, service, folder))

    p = path(folder)
    if not os.path.exists(p):
        raise KeyError_(guide(folder))

    found = {}
    for line in _read(p).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        found[name.strip()] = value.strip().strip('"').strip("'")

    confm, service = found.get(CONFM, ""), found.get(SERVICE, "")
    missing = [n for n, v in ((CONFM, confm), (SERVICE, service)) if not v]
    if missing:
        raise KeyError_(
            f"`{KEY_FILE}` 에서 {' 과 '.join(missing)} 키를 찾지 못했습니다.\n\n"
            + guide(folder)
        )
    return (_checked(CONFM, confm, folder),
            _checked(SERVICE, service, folder))


def kakao(folder: str = "") -> str:
    """카카오 REST API 키. **없으면 빈 문자열을 돌려줍니다.**

    지도 검색은 **있으면 좋은 것**이지 없으면 안 되는 것이 아닙니다.
    키가 없으면 화면에서 단추를 숨기고, 도로명주소 검색만으로 그대로
    돌아야 합니다. 오류를 내지 마십시오(작업지시 07 ①).

    웹에 올렸으면 Streamlit 비밀 보관함을, 내 컴퓨터면 키.txt 를 봅니다.
    """
    try:
        import streamlit as st
        v = str(st.secrets.get(KAKAO, "")).strip()
        if v:
            return v
    except Exception:
        pass

    p = path(folder)
    if not os.path.exists(p):
        return ""
    try:
        text = _read(p)
    except KeyError_:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == KAKAO:
            return value.strip().strip('"').strip("'")
    return ""


KAKAO_GUIDE = (
    "**지도에서 절 이름으로 찾기**를 쓰시려면 카카오 키가 필요합니다." + chr(10)
    + chr(10) +
    "1. developers.kakao.com 에 로그인" + chr(10) +
    "2. 내 애플리케이션 → 애플리케이션 추가하기" + chr(10) +
    "3. 앱 키에서 **REST API 키** 를 복사" + chr(10) +
    "4. 같은 폴더 `키.txt` 에 한 줄 추가 — `카카오=복사한키`" + chr(10)
    + chr(10) +
    "없어도 **주소로 찾기는 그대로 됩니다.**"
)
