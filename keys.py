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

KEY_FILE = "키.txt"
CONFM = "도로명주소"
SERVICE = "공공데이터포털"

TEMPLATE = f"{CONFM}=\n{SERVICE}=\n"


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
        return confm, service

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
    return confm, service
