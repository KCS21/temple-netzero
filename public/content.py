# -*- coding: utf-8 -*-
"""
소개글 읽기 — 공개 홈페이지 (작업지시 10 ①)
불교탄소중립실천단 지수광풍

`public/소개글.md` 는 본문과 맨 아래 설정 칸으로 되어 있습니다.

    ---
    <!-- 설명 -->
    인사말_본문:
    문의_전화:

**값이 비어 있으면 화면에 나오지 않습니다.** 교수님이 md 파일만 고치면
코드를 건드리지 않고 인사말·전화가 나타나게 하려는 것입니다.
"""
from __future__ import annotations

import io
import os
import re
from typing import Dict, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
INTRO = os.path.join(HERE, "소개글.md")
SITE_TITLE = "불교탄소중립실천단 지수광풍"

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SETTING = re.compile(r"^([^\s:#][^:]*?)\s*:\s*(.*)$")
_RULE = re.compile(r"^\s*-{3,}\s*$", re.M)


def parse(text: str) -> Tuple[str, Dict[str, str]]:
    """(본문, 설정). 본문은 **마지막** `---` 줄 위, 설정은 그 아래입니다.

    본문 첫 줄이 사이트 이름 제목이면 뺍니다. 화면 머리에 이미 있습니다.
    """
    text = (text or "").replace("\r\n", "\n")
    cuts = list(_RULE.finditer(text))
    if cuts:
        body, tail = text[:cuts[-1].start()], text[cuts[-1].end():]
    else:
        body, tail = text, ""

    settings: Dict[str, str] = {}
    for line in _COMMENT.sub("", tail).splitlines():
        m = _SETTING.match(line.strip())
        if m:
            settings[m.group(1).strip()] = m.group(2).strip()

    lines = body.strip().splitlines()
    if lines and lines[0].lstrip("# ").strip() == SITE_TITLE:
        lines = lines[1:]
    return "\n".join(lines).strip(), settings


def load(path: str = INTRO) -> Tuple[str, Dict[str, str]]:
    try:
        return parse(io.open(path, encoding="utf-8-sig").read())
    except OSError:
        return "", {}


def greeting(settings: Dict[str, str]):
    """인사말 (제목, 본문, 사진 경로 또는 ''). **본문이 비면 None.**"""
    body = (settings.get("인사말_본문") or "").strip()
    if not body:
        return None
    title = (settings.get("인사말_제목") or "").strip() or "단장 인사말"
    photo = (settings.get("인사말_사진") or "").strip()
    p = os.path.join(HERE, os.path.basename(photo)) if photo else ""
    return title, body, (p if p and os.path.exists(p) else "")


def contact_line(settings: Dict[str, str]) -> str:
    """「문의: 불교환경연대 사무실 ☎ …」. **전화가 비면 빈 문자열.**"""
    tel = (settings.get("문의_전화") or "").strip()
    if not tel:
        return ""
    org = (settings.get("문의_기관") or "").strip()
    return f"문의: {org} ☎ {tel}" if org else f"문의: ☎ {tel}"


# ── 소개 화면 꾸미기 (작업지시 11 ③) ──
IMG_DIR = os.path.join(HERE, "img")
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.M)
_STEP = re.compile(r"^\s*\d+\.\s*\*\*(.+?)\*\*\s*[—\-–:]\s*(.+)$", re.M)


def sections(body: str) -> Tuple[str, Dict[str, str]]:
    """(첫 「##」 앞 글, {제목: 글}). 소개 화면이 제목으로 자리를 찾아 그림을 붙입니다.

    md 를 고쳐 제목이 바뀌면 그 칸은 그림 없이 글만 나옵니다. 깨지지 않습니다.
    """
    parts = _H2.split(body or "")
    lead = parts[0].strip()
    out: Dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip()] = parts[i + 1].strip()
    return lead, out


def steps(text: str):
    """「1. **진단** — 설명」 줄들을 [(제목, 설명)] 으로."""
    return [(m.group(1).strip(), m.group(2).strip()) for m in _STEP.finditer(text or "")]


def find(secs: Dict[str, str], *keys: str) -> Tuple[str, str]:
    """제목에 낱말이 든 칸을 찾습니다. (제목, 글) 또는 ('', '')."""
    for k in keys:
        for title, text in secs.items():
            if k in title:
                return title, text
    return "", ""


def img(name: str) -> str:
    """그림 경로. 없으면 빈 문자열 — 그림이 없어도 화면은 섭니다."""
    p = os.path.join(IMG_DIR, name)
    return p if os.path.exists(p) else ""
