# -*- coding: utf-8 -*-
"""
지원사업·법령 자동 수집
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

한 번 돌리면 다섯 곳을 훑어 **지난번과 달라진 것만** 보고서로 냅니다.

    ① 보조금24 (행정안전부 「대한민국 공공서비스(혜택) 정보」 API)
    ② 한국에너지공단 재생에너지센터 사업공고 (knrec.or.kr) + 첨부 글자
    ③ 법제처 국민참여입법센터 입법예고 목록
    ④ 국가법령정보 API (법령·행정규칙·별표·법령해석·자치법규)
    ⑤ ②에서 뽑은 건물지원 단가·상한을 지원사업 문서 8장 기준값과 대조

나오는 것

    data/수집/수집보고_YYYYMMDD.md   보고서 (달라진 것만)
    data/수집/YYYYMM/                원자료 (응답·첨부·뽑은 글자)
    data/수집/기준선.json            「지난번」. 다음 실행이 이것과 견줍니다

**앱은 이 파일을 부르지 않습니다.** `data/지원사업.csv` 와 지원사업 문서도
고치지 않습니다. 보고서 끝에 **후보 줄**만 냅니다(사람이 보고 옮깁니다).

지킬 것

- 키는 `키.txt` 에서만 읽습니다(「공공데이터포털」·「국가법령OC」).
  **저장하는 원자료와 보고서에서 키를 지웁니다.** 국가법령정보 응답의
  링크에 `OC=` 가 그대로 들어 있습니다
- 요청 사이 1초 이상 쉽니다(`Fetcher.WAIT`)
- 한 곳이 못 읽혀도 멈추지 않습니다. 「자동으로 못 잡은 것」에 적고,
  그곳의 기준선은 **지난번 것을 그대로 둡니다.** 실패를 「전부 사라짐」으로
  읽으면 안 됩니다
- 한 곳 안에서 일부 질의만 실패했으면 「사라진 것」을 세지 않습니다
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import io
import json
import os
import re
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import region  # noqa: E402  (시·도 이름 맞추기를 그대로 씁니다)

NL = "\n"

# ── 무엇을 찾는가 ──────────────────────────────────────────────

GOV24_URL = "https://api.odcloud.kr/api/gov24/v3/serviceList"
GOV24_WORDS = ("태양광", "재생에너지", "신재생", "히트펌프", "지열",
               "태양열", "단열", "그린리모델링")
# 서비스명만 보면 「지원내용」에만 단어가 있는 사업을 놓칩니다
# (태양광: 서비스명 12건, 지원내용 23건 — 2026-11-08 확인).
GOV24_FIELDS = ("서비스명", "서비스목적요약", "지원내용", "지원대상")
GOV24_KEEP = ("서비스ID", "서비스명", "소관기관명", "소관기관유형", "사용자구분",
              "지원대상", "지원내용", "신청기한", "지원유형", "서비스분야",
              "전화문의", "상세조회URL", "수정일시")
GOV24_COMPARE = ("서비스명", "지원대상", "지원내용", "신청기한", "소관기관명")

# ── 보조금24 「사찰 관련성」 규칙 ── 고치실 곳은 여기입니다 ─────────
#
# 사업마다 **위에서부터** 차례로 맞춰 보고 처음 걸린 줄의 분류를 씁니다.
# (분류, 볼 칸, 말들). 말 가운데 하나라도 그 칸들에 들어 있으면 걸립니다.
# 그래서 **순서가 중요합니다.** 「무관」을 맨 위에 둔 까닭은 축산 농가
# 사업의 대상에 「건물」이 섞여 있어도 무관으로 보내기 위해서입니다.
#
# 어느 줄에도 안 걸린 사업은 「분류 못 함」으로 **보이게** 둡니다(접지
# 않습니다). 모르는 것을 숨기지 않으려는 것입니다(CLAUDE.md 2장).
# 그런 사업이 보이면 아래 목록에 말을 더해 주십시오.
REL_HIGH, REL_HOUSE, REL_NONE, REL_UNKNOWN = "관련 높음", "주택 전용", "무관", "분류 못 함"
RELEVANCE_RULES = (
    (REL_NONE, ("서비스명", "지원대상"),
     ("축산", "양돈", "양계", "가금", "축사", "가축", "귀농", "귀향", "농업인", "농가",
      "어업", "양식", "소상공인", "견학", "주차장", "보증", "해외진출", "KS인증",
      "농사용", "설치의무화제도", "일자리", "대학생", "중소벤처", "신성장기반")),
    (REL_HIGH, ("서비스명", "지원대상"),
     ("건물", "비주거", "비영리", "종교", "사회복지시설", "복지시설", "노유자", "일반건축물")),
    # 에너지공단 건물지원·융복합에 얹는 지방비 추가 보조
    (REL_HIGH, ("서비스명", "지원대상", "지원내용"), ("건물지원", "융복합")),
    (REL_HIGH, ("서비스명",), ("금융지원",)),
    (REL_HOUSE, ("서비스명", "지원대상"), ("주택", "가구", "거주", "세대")),
)
# 맞춰 보기 전에 지우는 말. 「건물등기부등본」의 「건물」이 「관련 높음」으로,
# 「건축사 사무소」의 「축사」가 「무관」으로 걸리지 않게 합니다.
RELEVANCE_IGNORE = ("건물등기부", "건축물대장", "건축법", "단독주택인 건물", "주택건물형",
                    "지방자치단체 소유 건물", "건축사")

KNREC = "https://www.knrec.or.kr"
KNREC_LIST = KNREC + "/biz/pds/businoti/list.do"
KNREC_VIEW = KNREC + "/biz/pds/businoti/view.do"
KNREC_FILE = KNREC + "/biz/file/File_down.do"
KNREC_PAGES = 5            # 한 쪽 10건 남짓. 한 달 새 공고는 대개 1~2쪽
# 첨부를 열어 볼 공고. 해상풍력·KS인증 같은 것까지 열면 시간만 듭니다
KNREC_ATTACH_WORDS = ("건물지원", "주택지원", "융복합", "보급", "지붕",
                      "태양광", "금융지원", "히트펌프", "공기열", "지열")
KNREC_ATTACH_MAX = 8       # 한 번에 첨부를 열어 볼 공고 수
# 서식·동의서에는 단가가 없습니다. 내려받지 않습니다
KNREC_SKIP_FILES = ("신청서", "동의서", "양식", "서식", "확인서", "서약서", "위임장", "체크리스트")
FILE_MAX = 30 * 1024 * 1024

LAWMAKING = "https://opinion.lawmaking.go.kr/gcom/ogLmPp"
LAWMAKING_WORDS = ("재생에너지", "영농형", "공기열", "히트펌프")

LAW_URL = "http://www.law.go.kr/DRF/lawSearch.do"
LAW_SITE = "https://www.law.go.kr"
# (질의, 법령명이 이것으로 시작해야 함). 「재생에너지」로 그냥 찾으면 남의 법이 섞입니다
LAW_QUERIES = (
    ("재생에너지 개발", "재생에너지 개발"),       # 법·시행령·시행규칙
    ("영농형", "영농형 태양광"),                  # 2026-12-17 시행 예정
    ("전통사찰의 보존", "전통사찰의 보존"),
)
# (질의, 이름에 들어 있어야 할 말, 기대하는 발령번호 또는 "")
ADMRUL_QUERIES = (
    ("재생에너지 발전설비 이격거리", "이격거리", "2026-235"),
    ("공기열에너지 재생에너지 인정기준", "공기열", ""),
)
LICBYL_QUERIES = ("재생에너지 개발", "영농형", "전통사찰")
ADMBYL_QUERIES = ("이격거리", "공기열")
# 기후에너지환경부의 1차 해석. 환경부 시절 이름(me)이 그대로입니다(2026-11-08 확인)
EXPC_TARGET = "meCgmExpc"
EXPC_WORDS = ("재생에너지", "신재생", "태양광", "이격거리", "히트펌프", "공기열")
ORDIN_WORDS = ("신재생에너지", "이격거리", "재생에너지")
ORDIN_NAME_HAS = ("재생에너지", "이격거리")

# ── 지원사업 문서 8장 「진단 도구가 쓰는 기준값」 ─────────────────
# 원본: 사찰_정부지원사업_정리_20261108.docx 8장 (확인일 2026-11-07).
# 문서 값이 바뀌면 여기 두 줄도 고치십시오.
BASE = {
    "단가_만원": 52.5,      # kW당, 일반 200 kW 이하, 저탄소 모듈, 부가세 제외
    "상한_kW": 200,         # 일반 건물 최대 지원범위 용량
    "근거": "지원사업 문서 8장(2026-11-07 확인) - 공고 제2026-237호",
}

CSV_COLUMNS = ("사업", "설비", "조건_시도", "조건_용량", "조건_기타", "지원 내용",
               "일정", "근거", "근거 수준", "확인일", "링크")


# ── 키 ─────────────────────────────────────────────────────────

SERVICE = "공공데이터포털"
LAWOC = "국가법령OC"


def read_keys(path: str) -> dict:
    """키.txt 를 읽어 {이름: 값}. 없거나 못 읽으면 빈 dict."""
    if not os.path.exists(path):
        return {}
    text = ""
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = io.open(path, encoding=enc).read()
            break
        except UnicodeDecodeError:
            continue
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip().strip('"').strip("'")
    return out


class Secrets:
    """나가는 글(원자료·보고서·화면)에서 키를 지웁니다."""

    def __init__(self, *values):
        self.values = [v for v in values if v and len(v) >= 4]

    def hide(self, text: str) -> str:
        if not text:
            return text
        for v in self.values:
            text = text.replace(v, "***")
        # 국가법령정보 링크의 OC, 공공데이터포털 serviceKey
        text = re.sub(r"(OC=)[^&\"'\s<]+", r"\1***", text)
        text = re.sub(r"(serviceKey=)[^&\"'\s<]+", r"\1***", text)
        return text


def law_link(link: str) -> str:
    """국가법령정보 상세링크에서 OC 를 **빼고** 누구나 열 수 있는 주소로."""
    if not link:
        return ""
    link = html.unescape(link)
    link = re.sub(r"OC=[^&]*&?", "", link)
    if link.startswith("/"):
        link = LAW_SITE + link
    return link


# ── 요청 ───────────────────────────────────────────────────────

class FetchError(Exception):
    """사람에게 보여 줄 수 있는 실패. 키는 지워져 있습니다."""


class Fetcher:
    """요청 사이를 **1초 이상** 띄웁니다. 실패하면 두 번까지 다시 해 봅니다."""

    WAIT = 1.1
    TRIES = 3
    UA = "Mozilla/5.0 (jisu-netzero collector; +https://github.com/KCS21/temple-netzero)"

    def __init__(self, secrets: Secrets, session=None, sleep=time.sleep):
        import requests
        self.requests = requests
        self.s = session or requests.Session()
        self.s.headers["User-Agent"] = self.UA
        self.secrets = secrets
        self.sleep = sleep
        self.last = 0.0
        self.count = 0

    def get(self, url, params=None, headers=None, timeout=30, binary=False):
        why = ""
        for i in range(self.TRIES):
            gap = time.time() - self.last
            if gap < self.WAIT:
                self.sleep(self.WAIT - gap)
            self.last = time.time()
            self.count += 1
            try:
                r = self.s.get(url, params=params, headers=headers, timeout=timeout)
                if r.status_code >= 500:
                    why = f"서버가 {r.status_code} 로 답했습니다"
                    self.sleep(2 + 2 * i)
                    continue
                if r.status_code >= 400:
                    raise FetchError(f"{r.status_code} 로 거절했습니다 ({self.secrets.hide(r.url)})")
                return r.content if binary else r.text
            except FetchError:
                raise
            except Exception as e:     # 연결 끊김·시간 초과
                why = self.secrets.hide(f"{type(e).__name__}: {e}")
                self.sleep(2 + 2 * i)
        raise FetchError(why or "응답이 없습니다")


# ── 공통 ───────────────────────────────────────────────────────

def clean(s) -> str:
    """태그·여러 칸 공백을 걷어 한 줄로."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    return re.sub(r"\s+", " ", s).strip()


def short(s, n=120) -> str:
    s = clean(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def as_list(v):
    """국가법령정보는 한 건이면 dict, 여러 건이면 list 로 줍니다."""
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def diff(prev: dict | None, cur: dict, fields) -> dict:
    """{new: [id], changed: [(id, {필드: (옛, 새)})], removed: [id], first: bool}"""
    if prev is None:
        return {"first": True, "new": sorted(cur), "changed": [], "removed": []}
    new = sorted(k for k in cur if k not in prev)
    removed = sorted(k for k in prev if k not in cur)
    changed = []
    for k in sorted(cur):
        if k in prev:
            d = {f: (prev[k].get(f, ""), cur[k].get(f, ""))
                 for f in fields if str(prev[k].get(f, "")) != str(cur[k].get(f, ""))}
            if d:
                changed.append((k, d))
    return {"first": False, "new": new, "changed": changed, "removed": removed}


def sido_of(org: str) -> str:
    """소관기관명의 첫 말로 시·도를 정합니다. 못 정하면 빈 문자열."""
    tok = (org or "").strip().split(" ")[0] if org else ""
    return region._SIDO.get(tok, "")


SIDO_ORDER = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
              "경기", "강원", "충북", "충남", "전북", "전남", "전남광주",
              "경북", "경남", "제주")


def sido_label(item: dict) -> str:
    s = sido_of(item.get("소관기관명", ""))
    if s:
        return s
    if "중앙" in item.get("소관기관유형", ""):
        return "전국(중앙부처)"
    return "기타(공공기관 등)"


def is_local(item: dict) -> bool:
    """지자체 사업인가. 소관기관명이 시·도 이름으로 시작하면 지자체로 봅니다."""
    return bool(sido_of(item.get("소관기관명", "")))


def _tbody(page_html: str, mark: str) -> str:
    """표 본문 가운데 `mark` 가 든 것. 쪽마다 표가 여럿입니다
    (에너지공단 목록은 메일 신청 창의 표가 먼저 나옵니다)."""
    for m in re.finditer(r"<tbody[^>]*>(.*?)</tbody>", page_html, re.S):
        if mark in m.group(1):
            return m.group(1)
    return ""


# ── ① 보조금24 ─────────────────────────────────────────────────

def gov24_rows(payload: dict) -> list:
    return [r for r in (payload.get("data") or []) if isinstance(r, dict)]


def gov24_item(row: dict, word: str) -> dict:
    it = {k: clean(row.get(k)) if k not in ("상세조회URL",) else (row.get(k) or "")
          for k in GOV24_KEEP}
    it["사용자구분"] = "·".join(x for x in it["사용자구분"].split("|") if x.strip())
    it["시도"] = ""
    it["찾은말"] = [word]
    return it


def relevance(item: dict) -> tuple:
    """(분류, 걸린 말). RELEVANCE_RULES 를 위에서부터 봅니다."""
    for cat, fields, words in RELEVANCE_RULES:
        text = " ".join(str(item.get(f, "")) for f in fields)
        for w in RELEVANCE_IGNORE:
            text = text.replace(w, " ")
        for w in words:
            if w in text:
                return cat, w
    return REL_UNKNOWN, ""


def collect_gov24(f: Fetcher, key: str, raw: dict, problems: list) -> dict:
    items, failed = {}, 0
    for word in GOV24_WORDS:
        for field in GOV24_FIELDS:
            page = 1
            while page <= 10:
                try:
                    text = f.get(GOV24_URL, params={
                        "page": page, "perPage": 100, "serviceKey": key,
                        f"cond[{field}::LIKE]": word})
                    payload = json.loads(text)
                except (FetchError, ValueError) as e:
                    failed += 1
                    problems.append(f"보조금24 「{word}」({field}) {page}쪽 - {short(e, 200)}")
                    break
                raw.setdefault("보조금24", []).append(
                    {"말": word, "칸": field, "쪽": page, "응답": payload})
                for row in gov24_rows(payload):
                    sid = str(row.get("서비스ID") or "")
                    if not sid:
                        continue
                    if sid in items:
                        if word not in items[sid]["찾은말"]:
                            items[sid]["찾은말"].append(word)
                    else:
                        items[sid] = gov24_item(row, word)
                match = int(payload.get("matchCount") or 0)
                if page * 100 >= match:
                    break
                page += 1
    for it in items.values():
        it["시도"] = sido_label(it)
        it["찾은말"] = "·".join(it["찾은말"])
    return {"items": items, "partial": failed > 0, "ok": failed < len(GOV24_WORDS) * len(GOV24_FIELDS)}


# ── ② 에너지공단 사업공고 ──────────────────────────────────────

def knrec_list(page_html: str) -> list:
    """목록 쪽 HTML -> [{no, 진행, 분류, 제목, 부서, 등록일, 마감일, 첨부수}]."""
    out = []
    body = _tbody(page_html, "view.do?no=")
    for tr in re.split(r"<tr[\s>]", body)[1:]:
        m = re.search(r"view\.do\?no=(\d+)", tr)
        if not m:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        cells = [clean(t) for t in tds]
        if len(cells) < 7:
            continue
        out.append({
            "no": m.group(1),
            "진행": cells[1], "분류": cells[2], "제목": cells[3],
            "부서": cells[4], "등록일": cells[5], "마감일": cells[6],
            "첨부수": len(re.findall(r"file_down\(", tr)),
            "링크": f"{KNREC_VIEW}?no={m.group(1)}",
        })
    return out


def knrec_view(view_html: str) -> dict:
    """본문 쪽 HTML -> {제목, 첨부: [(gubun, 파일이름)]}. 제목은 목록에서 잘립니다."""
    title = ""
    m = re.search(r'class="notice_view_tit"[^>]*>(.*?)</p>', view_html, re.S)
    if m:
        title = re.sub(r"^\[[^\]]{1,6}\]\s*", "", clean(m.group(1)))
    if not title:
        # 쪽 제목 「재생에너지센터 | 자료실 | … | 공고 제목」 의 끝 칸
        m = re.search(r"<title>(.*?)</title>", view_html, re.S)
        if m and "|" in m.group(1):
            title = clean(m.group(1).rsplit("|", 1)[-1])
    # 본문 첫머리의 공고 번호 (「기후에너지환경부 공고 제2026-237호」)
    num = ""
    m = re.search(r"((?:[가-힣]+\s*)?공고\s*제\s*\d{4}\s*-\s*\d+\s*호)", view_html)
    if m:
        num = clean(m.group(1))
    files = []
    for g, name in re.findall(
            r"file_down\('\d+'\s*,\s*'(\d+)'\s*,\s*'notice'\)\"\s*>(.*?)</a>", view_html, re.S):
        # 앞의 <p class="ico_hwp"><span>한글파일</span></p> 는 그림 글자라 뺍니다
        name = re.sub(r"<p[^>]*class=\"ico_[^\"]*\"[^>]*>.*?</p>", "", name, flags=re.S)
        files.append((g, clean(name)))
    return {"제목": title, "공고번호": num, "첨부": files}


def _text_hwpx(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    parts = []
    for n in sorted(z.namelist()):
        if n.startswith("Contents/section") and n.endswith(".xml"):
            x = z.read(n).decode("utf-8", "replace")
            x = re.sub(r"</hp:p>", NL, x)
            x = re.sub(r"<hp:tab[^>]*/>", " ", x)
            parts.append(html.unescape(re.sub(r"<[^>]+>", "", x)))
    if not parts and "Preview/PrvText.txt" in z.namelist():
        parts.append(z.read("Preview/PrvText.txt").decode("utf-8", "replace"))
    return NL.join(parts)


def _text_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("PDF 를 열 프로그램(pypdf)이 없습니다 - pip install pypdf")
    rd = PdfReader(io.BytesIO(data))
    return NL.join((p.extract_text() or "") for p in rd.pages)


def _hwp_para_text(buf: bytes) -> str:
    """HWP 5 본문 레코드에서 문단 글자(태그 67)만 뽑습니다."""
    out, i = [], 0
    while i + 4 <= len(buf):
        h = int.from_bytes(buf[i:i + 4], "little")
        tag, size = h & 0x3FF, (h >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            size = int.from_bytes(buf[i:i + 4], "little")
            i += 4
        rec = buf[i:i + size]
        i += size
        if tag != 67:
            continue
        chars, j = [], 0
        while j + 2 <= len(rec):
            c = int.from_bytes(rec[j:j + 2], "little")
            if c < 32:
                if c in (9,):
                    chars.append(" ")
                if c in (10, 13):
                    chars.append(NL)
                # 확장·인라인 조판 부호는 16바이트(8글자)를 차지합니다
                j += 2 if c in (0, 10, 13, 24, 25, 26, 27, 28, 29, 30, 31) else 16
                continue
            chars.append(chr(c))
            j += 2
        out.append("".join(chars))
    return NL.join(out)


class _Cfb:
    """복합 문서(OLE) 읽기. HWP 5 파일이 이 꼴입니다.

    `olefile` 이 있으면 그것을 쓰고, 없으면 이것으로 엽니다. 배치 파일이 고르는
    파이썬 3.14 에 `olefile` 이 없어서 만들었습니다(2026-11-08). 스트림을
    읽는 데 필요한 만큼만 구현했습니다.
    """

    END = 0xFFFFFFFA

    def __init__(self, data: bytes):
        if data[:8] != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise ValueError("OLE 파일이 아닙니다")
        u16 = lambda o: int.from_bytes(data[o:o + 2], "little")
        u32 = lambda o: int.from_bytes(data[o:o + 4], "little")
        self.d, self.u32 = data, u32
        self.ss = 1 << u16(0x1E)
        self.mss = 1 << u16(0x20)
        self.cutoff = u32(0x38)
        difat = [u32(0x4C + 4 * i) for i in range(109)]
        nxt, n = u32(0x44), u32(0x48)
        per = self.ss // 4 - 1
        while n > 0 and nxt < self.END:
            off = self._off(nxt)
            difat += [u32(off + 4 * i) for i in range(per)]
            nxt = u32(off + 4 * per)
            n -= 1
        self.fat = []
        for sec in difat[:u32(0x2C)]:
            if sec >= self.END:
                continue
            off = self._off(sec)
            self.fat += [u32(off + 4 * i) for i in range(self.ss // 4)]
        dirs = self._chain_bytes(u32(0x30), self.fat, self.ss)
        self.entries = []
        for i in range(len(dirs) // 128):
            e = dirs[i * 128:(i + 1) * 128]
            ln = int.from_bytes(e[0x40:0x42], "little")
            self.entries.append({
                "name": e[:max(0, ln - 2)].decode("utf-16-le", "replace"),
                "type": e[0x42],
                "left": int.from_bytes(e[0x44:0x48], "little"),
                "right": int.from_bytes(e[0x48:0x4C], "little"),
                "child": int.from_bytes(e[0x4C:0x50], "little"),
                "start": int.from_bytes(e[0x74:0x78], "little"),
                "size": int.from_bytes(e[0x78:0x7C], "little"),
            })
        root = self.entries[0]
        self.mini = self._chain_bytes(root["start"], self.fat, self.ss)[:root["size"]]
        mf = self._chain_bytes(u32(0x3C), self.fat, self.ss) if u32(0x40) else b""
        self.minifat = [int.from_bytes(mf[i:i + 4], "little") for i in range(0, len(mf), 4)]
        self.paths = {}
        self._walk(root["child"], "")

    def _off(self, sec):
        return (sec + 1) * self.ss

    def _chain(self, start, fat):
        seen = set()
        while start < self.END and start < len(fat) and start not in seen:
            seen.add(start)
            yield start
            start = fat[start]

    def _chain_bytes(self, start, fat, size, src=None):
        if src is None:
            return b"".join(self.d[self._off(s):self._off(s) + size] for s in self._chain(start, fat))
        return b"".join(src[s * size:(s + 1) * size] for s in self._chain(start, fat))

    def _walk(self, i, prefix, depth=0):
        if i >= len(self.entries) or i >= self.END or depth > 64:
            return
        e = self.entries[i]
        self._walk(e["left"], prefix, depth + 1)
        path = prefix + e["name"]
        if e["type"] == 2:
            self.paths[path] = e
        elif e["type"] == 1:
            self._walk(e["child"], path + "/", depth + 1)
        self._walk(e["right"], prefix, depth + 1)

    def listdir(self):
        return [p.split("/") for p in self.paths]

    def exists(self, path):
        return path in self.paths

    def read(self, path):
        e = self.paths[path if isinstance(path, str) else "/".join(path)]
        if e["size"] < self.cutoff:
            return self._chain_bytes(e["start"], self.minifat, self.mss, self.mini)[:e["size"]]
        return self._chain_bytes(e["start"], self.fat, self.ss)[:e["size"]]


def _text_hwp(data: bytes) -> str:
    try:
        import olefile
        ole = olefile.OleFileIO(io.BytesIO(data))
        names = ole.listdir()
        read = lambda p: ole.openstream(p).read()
        has = ole.exists
    except ImportError:
        ole = _Cfb(data)
        names = ole.listdir()
        read, has = ole.read, ole.exists
    head = read("FileHeader")
    flags = int.from_bytes(head[36:40], "little") if len(head) >= 40 else 1
    compressed = bool(flags & 1)
    parts = []
    if not (flags & 4):          # 배포용 문서는 본문이 잠겨 있습니다
        for entry in sorted(names, key=lambda e: (len(e), e[0], int(re.sub(r"\D", "", e[-1]) or 0))):
            if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section"):
                buf = read("/".join(entry))
                if compressed:
                    buf = zlib.decompress(buf, -15)
                parts.append(_hwp_para_text(buf))
    if not "".join(parts).strip() and has("PrvText"):
        parts = [read("PrvText").decode("utf-16-le", "replace")]
        if flags & 4:
            parts.append("(배포용 문서라 첫 쪽 미리보기 글자만 읽었습니다)")
    return NL.join(parts)


def file_text(name: str, data: bytes, depth: int = 0) -> str:
    """첨부 한 개의 글자. 못 열면 RuntimeError (까닭이 붙어 있습니다)."""
    low = name.lower()
    try:
        if low.endswith(".hwpx"):
            return _text_hwpx(data)
        if low.endswith(".pdf"):
            return _text_pdf(data)
        if low.endswith(".hwp"):
            return _text_hwp(data)
        if low.endswith(".zip") and depth == 0:
            z = zipfile.ZipFile(io.BytesIO(data))
            parts = []
            for n in z.namelist():
                if n.lower().endswith((".hwpx", ".pdf", ".hwp")):
                    try:
                        parts.append(file_text(n, z.read(n), 1))
                    except RuntimeError:
                        pass
            if not parts:
                raise RuntimeError("압축 안에 읽을 수 있는 hwpx·pdf·hwp 가 없습니다")
            return NL.join(parts)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"파일을 열다 막혔습니다({type(e).__name__})")
    raise RuntimeError("hwpx·pdf·hwp·zip 이 아니라 열지 않았습니다")


def _norm(text: str) -> str:
    t = text.replace("㎾", "kW").replace("KW", "kW").replace("kw", "kW")
    t = t.replace("ㆍ", "·").replace("･", "·")
    return t


def find_terms(text: str) -> dict:
    """공고문 글자에서 보조금 단가·신청 상한·접수기간을 찾습니다.

    표가 글자로 풀리면 칸이 줄마다 갈라집니다. 그래서 줄바꿈을 공백으로
    합친 글과 줄 단위 글을 둘 다 봅니다.
    """
    t = _norm(text)
    flat = re.sub(r"\s+", " ", t)
    out = {"단가들": [], "일반단가_천원": None, "상한_kW": None, "접수기간": ""}

    for m in re.finditer(r"(\d{2,4}(?:\.\d+)?)\s*(천원|만원|원)?\s*/\s*kW", flat):
        ctx = flat[max(0, m.start() - 45): m.end()]
        out["단가들"].append({"값": m.group(1), "단위": m.group(2) or "", "앞뒤": ctx.strip()})

    m = re.search(r"일반\s*200\s*kW\s*이하.{0,60}?(\d{2,4})\s*/\s*kW", flat)
    if m:
        out["일반단가_천원"] = float(m.group(1))

    m = (re.search(r"\(\s*일반[·\s]*축사\s*\)\s*([\d,]+)\s*kW", flat)
         or re.search(r"최대\s*지원\s*범위\s*용량.{0,80}?일반.{0,10}?([\d,]+)\s*kW", flat))
    if m:
        out["상한_kW"] = float(m.group(1).replace(",", ""))

    m = re.search(r"접수\s*기간\s*[:：]\s*([^\n]{4,80})", t)
    if m:
        p = m.group(1)
        p = re.split(r"\s\(매일|\s※|\s\*", p)[0]
        out["접수기간"] = p.strip()
    return out


def _file_name(cd: str, fallback: str) -> str:
    m = re.search(r'filename="?([^";]+)', cd or "")
    if not m:
        return fallback
    raw = m.group(1)
    try:
        return raw.encode("latin-1").decode("cp949")
    except Exception:
        return fallback


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name)[:80]


def collect_knrec(f: Fetcher, prev: dict | None, run_dir: str, problems: list) -> dict:
    items, pages_ok = {}, 0
    for page in range(1, KNREC_PAGES + 1):
        try:
            text = f.get(KNREC_LIST, params={"page": page})
        except FetchError as e:
            problems.append(f"에너지공단 사업공고 {page}쪽 - {e}")
            continue
        save(os.path.join(run_dir, "에너지공단", f"목록_{page}.html"), text)
        rows = knrec_list(text)
        if not rows:
            problems.append(f"에너지공단 사업공고 {page}쪽 - 목록 칸을 찾지 못했습니다"
                            "(사이트 모양이 바뀌었을 수 있음)")
            continue
        pages_ok += 1
        for r in rows:
            items.setdefault(r["no"], r)

    prev_items = (prev or {}).get("items", {})
    extracted = dict((prev or {}).get("추출", {}))
    first = prev is None
    new = [no for no in items if no not in prev_items]

    def rank(no):
        """먼저 열 공고. 건물지원 > 주택·융복합·보급 > 그 밖의 관심어."""
        title = items[no]["제목"]
        if "건물지원" in title:
            return 0
        if any(w in title for w in ("주택지원", "융복합", "보급")):
            return 1
        return 2 if any(w in title for w in KNREC_ATTACH_WORDS) else 9

    # 아직 안 열어 본 관심 공고는 **새것이 아니어도** 차례를 기다립니다.
    # 한 번에 다 못 열면 다음 실행이 이어서 엽니다(첫 실행에 50건이 다 「새것」).
    todo = sorted((no for no in items if rank(no) < 9 and no not in extracted),
                  key=lambda no: (rank(no), -int(no)))
    skipped = todo[KNREC_ATTACH_MAX:]
    todo = todo[:KNREC_ATTACH_MAX]
    if skipped:
        problems.append(f"에너지공단 첨부 - 관심 공고 {len(skipped)}건은 다음 실행에 엽니다"
                        f"(한 번에 {KNREC_ATTACH_MAX}건까지): " +
                        ", ".join(items[n]["제목"][:30] for n in skipped))

    for no in todo:
        extracted[no] = knrec_attachments(f, items[no], run_dir, problems)

    return {"items": items, "추출": extracted, "new": new, "first": first,
            "ok": pages_ok > 0, "partial": pages_ok < KNREC_PAGES}


def knrec_attachments(f: Fetcher, item: dict, run_dir: str, problems: list) -> dict:
    no = item["no"]
    res = {"제목": item["제목"], "등록일": item["등록일"], "링크": item["링크"],
           "첨부": [], "단가들": [], "일반단가_천원": None, "상한_kW": None, "접수기간": ""}
    try:
        vh = f.get(KNREC_VIEW, params={"no": no})
    except FetchError as e:
        problems.append(f"에너지공단 공고 「{item['제목'][:40]}」 본문 - {e}")
        return res
    save(os.path.join(run_dir, "에너지공단", f"본문_{no}.html"), vh)
    v = knrec_view(vh)
    if v["제목"]:
        res["제목"] = v["제목"]
    res["공고번호"] = v["공고번호"]
    if not v["첨부"]:
        problems.append(f"에너지공단 공고 「{res['제목'][:40]}」 - 첨부 목록을 찾지 못했습니다")
    for g, name in v["첨부"]:
        entry = {"이름": name, "열림": False, "까닭": ""}
        res["첨부"].append(entry)
        if not name.lower().endswith((".hwpx", ".pdf", ".hwp", ".zip")):
            ext = name.rsplit(".", 1)[-1] if "." in name else "?"
            entry["까닭"] = f"{ext} 형식은 열지 못함"
            problems.append(f"에너지공단 첨부 「{name[:50]}」(공고 {no}) - {ext} 형식은 열지 못합니다")
            continue
        if any(w in name for w in KNREC_SKIP_FILES) and "공고" not in name:
            entry["까닭"] = "서식이라 열지 않음"
            continue
        try:
            data = f.get(KNREC_FILE, params={"no": no, "gubun": g, "kinds": "notice"},
                         headers={"Referer": f"{KNREC_VIEW}?no={no}"}, timeout=90, binary=True)
            if len(data) > FILE_MAX:
                raise RuntimeError("파일이 너무 큽니다")
            path = os.path.join(run_dir, "첨부", f"{no}_{g}_{_safe(name)}")
            save_bytes(path, data)
            text = file_text(name, data)
            if len(text.strip()) < 50:
                raise RuntimeError("글자가 거의 없습니다(그림으로 된 문서일 수 있음)")
            save(path + ".txt", text)
            entry["열림"] = True
            t = find_terms(text)
            res["단가들"] += t["단가들"]
            for k in ("일반단가_천원", "상한_kW"):
                if res[k] is None and t[k] is not None:
                    res[k] = t[k]
            if not res["접수기간"] and t["접수기간"]:
                res["접수기간"] = t["접수기간"]
        except (FetchError, RuntimeError) as e:
            entry["까닭"] = str(e)
            problems.append(f"에너지공단 첨부 「{name[:50]}」(공고 {no}) - {e}")
    return res


# ── ③ 입법예고 ─────────────────────────────────────────────────

def lawmaking_rows(page_html: str) -> list:
    out = []
    body = _tbody(page_html, "/gcom/ogLmPp/")
    for tr in re.split(r"<tr[\s>]", body)[1:]:
        m = re.search(r'href="/gcom/ogLmPp/(\d+)[^"]*"\s*title="([^"]+)"', tr)
        if not m:
            continue
        cells = {}
        for th, inner in re.findall(r'<td data-th="([^"]+)"[^>]*>(.*?)</td>', tr, re.S):
            cells[clean(th)] = [clean(p) for p in re.findall(r"<p>(.*?)</p>", inner, re.S)] or [clean(inner)]
        dept = cells.get("소관부처 (법령종류)", ["", ""])
        period = cells.get("입법의견 접수기간", [])
        out.append({
            "id": m.group(1),
            "제목": clean(m.group(2)),
            "소관부처": dept[0] if dept else "",
            "법령종류": (dept[1] if len(dept) > 1 else "").strip("()"),
            "접수기간": " ".join(period),
            "링크": f"{LAWMAKING}/{m.group(1)}",
        })
    return out


def lawmaking_total(page_html: str) -> int | None:
    m = re.search(r'class="numBuild">\s*전체\s*<span>([\d,]+)</span>', page_html)
    return int(m.group(1).replace(",", "")) if m else None


def collect_lawmaking(f: Fetcher, today: _dt.date, run_dir: str, problems: list) -> dict:
    items, failed = {}, 0
    st = (today - _dt.timedelta(days=400)).strftime("%Y%m%d")
    ed = today.strftime("%Y%m%d")
    for word in LAWMAKING_WORDS:
        for page in range(1, 6):
            try:
                text = f.get(LAWMAKING, params={
                    "lsNm": word, "finishIncludeYn": "Y", "stYd": st, "edYd": ed,
                    "isOgYn": "Y", "opYn": "Y", "pageIndex": page})
            except FetchError as e:
                failed += 1
                problems.append(f"입법예고 「{word}」 - {e}")
                break
            save(os.path.join(run_dir, "입법예고", f"{word}_{page}.html"), text)
            total = lawmaking_total(text)
            rows = lawmaking_rows(text)
            if total is None:
                failed += 1
                problems.append(f"입법예고 「{word}」 - 건수 칸을 찾지 못했습니다(사이트 모양이 바뀌었을 수 있음)")
                break
            for r in rows:
                r["찾은말"] = word
                items.setdefault(r["id"], r)
            if not rows or page * 10 >= total:
                break
    return {"items": items, "ok": failed < len(LAWMAKING_WORDS), "partial": failed > 0}


# ── ④ 국가법령정보 ─────────────────────────────────────────────

def law_body(payload: dict) -> dict:
    if not isinstance(payload, dict) or not payload:
        return {}
    v = next(iter(payload.values()))
    return v if isinstance(v, dict) else {}


def law_get(f: Fetcher, oc: str, target: str, query: str, raw: dict, **extra) -> list:
    """한 질의의 모든 쪽. 실패하면 FetchError."""
    rows, page = [], 1
    while page <= 10:
        p = {"OC": oc, "target": target, "type": "JSON", "query": query,
             "display": 100, "page": page}
        p.update(extra)
        text = f.get(LAW_URL, params=p)
        try:
            payload = json.loads(text)
        except ValueError:
            raise FetchError("JSON 이 아닌 답이 왔습니다(OC 미승인 또는 대상 이름 변경)")
        raw.setdefault("법령", []).append({"대상": target, "말": query, "쪽": page, **extra,
                                         "응답": payload})
        body = law_body(payload)
        got = []
        for k, v in body.items():
            if isinstance(v, (list, dict)) and k not in ("키워드",):
                got += [x for x in as_list(v) if isinstance(x, dict)]
        rows += got
        total = int(body.get("totalCnt") or 0)
        if not got or page * 100 >= total:
            break
        page += 1
    return rows


def _id_from_link(link: str) -> str:
    m = re.search(r"[?&](?:ID|MST)=(\d+)", link or "")
    return m.group(1) if m else ""


def collect_law(f: Fetcher, oc: str, raw: dict, problems: list) -> dict:
    groups = {"법령": {}, "행정규칙": {}, "별표": {}, "법령해석": {}, "자치법규": {}}
    failed = {g: 0 for g in groups}

    def run(group, target, query, **extra):
        try:
            return law_get(f, oc, target, query, raw, **extra)
        except FetchError as e:
            failed[group] += 1
            problems.append(f"국가법령정보 {group} 「{query}」 - {e}")
            return []

    for query, prefix in LAW_QUERIES:
        for nw in ("3", "2"):          # 현행, 시행예정
            for r in run("법령", "law", query, nw=nw):
                name = r.get("법령명한글", "")
                if not name.startswith(prefix):
                    continue
                key = f"{r.get('법령ID')}|{r.get('현행연혁코드')}"
                groups["법령"][key] = {
                    "이름": name, "구분": r.get("법령구분명", ""),
                    "상태": r.get("현행연혁코드", ""), "공포일자": r.get("공포일자", ""),
                    "시행일자": r.get("시행일자", ""), "공포번호": r.get("공포번호", ""),
                    "제개정": r.get("제개정구분명", ""), "링크": law_link(r.get("법령상세링크", "")),
                }

    for query, must, expect in ADMRUL_QUERIES:
        for r in run("행정규칙", "admrul", query):
            name = r.get("행정규칙명", "")
            if must not in name:
                continue
            groups["행정규칙"][str(r.get("행정규칙ID"))] = {
                "이름": name, "종류": r.get("행정규칙종류", ""),
                "발령번호": r.get("발령번호", ""), "발령일자": r.get("발령일자", ""),
                "시행일자": r.get("시행일자", ""), "제개정": r.get("제개정구분명", ""),
                "기대번호": expect, "링크": law_link(r.get("행정규칙상세링크", "")),
            }

    for query in LICBYL_QUERIES:
        for r in run("별표", "licbyl", query, search="2"):
            key = f"법령|{r.get('관련법령ID')}|{r.get('별표종류')}|{r.get('별표번호')}"
            groups["별표"][key] = {
                "법령": r.get("관련법령명", ""), "이름": r.get("별표명", ""),
                "종류": r.get("별표종류", ""), "공포일자": r.get("공포일자", ""),
                "일련번호": r.get("별표일련번호", ""), "링크": law_link(r.get("별표법령상세링크", "")),
            }
    for query in ADMBYL_QUERIES:
        for r in run("별표", "admbyl", query, search="2"):
            key = f"행정규칙|{r.get('관련법령ID')}|{r.get('별표종류')}|{r.get('별표번호')}"
            groups["별표"][key] = {
                "법령": r.get("관련행정규칙명", ""), "이름": r.get("별표명", ""),
                "종류": r.get("별표종류", ""), "공포일자": r.get("발령일자", ""),
                "일련번호": r.get("별표일련번호", ""),
                "링크": law_link(r.get("별표행정규칙상세링크", "")),
            }

    for query in EXPC_WORDS:
        for r in run("법령해석", EXPC_TARGET, query):
            link = r.get("법령해석상세링크", "")
            key = _id_from_link(link) or r.get("안건번호", "") or r.get("안건명", "")
            if not key:
                continue
            groups["법령해석"][key] = {
                "이름": r.get("안건명", ""), "안건번호": r.get("안건번호", ""),
                # 해석일자가 비어 오는 일이 많습니다(2026-11-08). 그때는 자료 기준일
                "해석일자": (r.get("해석일자", "") or r.get("회신일자", "")
                             or r.get("데이터기준일시", "")),
                "해석기관": r.get("해석기관명", ""), "링크": law_link(link),
            }

    for query in ORDIN_WORDS:
        for r in run("자치법규", "ordin", query):
            name = r.get("자치법규명", "")
            if r.get("자치법규종류") != "조례":
                continue
            if not any(w in name.replace("·", "").replace("ㆍ", "") for w in ORDIN_NAME_HAS):
                continue
            groups["자치법규"][str(r.get("자치법규ID"))] = {
                "이름": name, "지자체": r.get("지자체기관명", ""),
                "공포일자": r.get("공포일자", ""), "시행일자": r.get("시행일자", ""),
                "공포번호": r.get("공포번호", ""), "제개정": r.get("제개정구분명", ""),
                "링크": law_link(r.get("자치법규상세링크", "")),
            }
    return {"groups": groups, "failed": failed}


LAW_COMPARE = {
    "법령": ("공포일자", "시행일자", "공포번호", "제개정"),
    "행정규칙": ("발령번호", "발령일자", "시행일자", "제개정"),
    "별표": ("공포일자", "일련번호", "이름"),
    "법령해석": ("해석일자", "이름"),
    "자치법규": ("공포일자", "시행일자", "공포번호", "제개정"),
}


# ── 파일 ───────────────────────────────────────────────────────

_SECRETS = Secrets()


def save(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8").write(_SECRETS.hide(text))


def save_bytes(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def save_json(path: str, obj):
    save(path, json.dumps(obj, ensure_ascii=False, indent=1))


def load_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


# ── ⑤ 기준값 대조 ──────────────────────────────────────────────

def compare_base(extracted: dict) -> dict:
    """가장 최근 건물지원 공고의 단가·상한을 BASE 와 견줍니다."""
    cands = [(no, e) for no, e in extracted.items() if "건물지원" in e.get("제목", "")]
    if not cands:
        return {"공고": None, "후보": [], "같음": [], "못봄": ["건물지원 공고를 찾지 못했습니다"]}
    no, e = max(cands, key=lambda x: int(x[0]))
    res = {"공고": {"no": no, "제목": e.get("제목", ""), "링크": e.get("링크", ""),
                   "등록일": e.get("등록일", "")}, "후보": [], "같음": [], "못봄": []}
    price = e.get("일반단가_천원")
    if price is None:
        res["못봄"].append("보조금 단가(일반 200 kW 이하)")
    else:
        man = round(price / 10, 2)
        row = ("보조금 단가(kW당, 일반)", f"{BASE['단가_만원']}만 원", f"{man:g}만 원")
        (res["같음"] if abs(man - BASE["단가_만원"]) < 1e-6 else res["후보"]).append(row)
    cap = e.get("상한_kW")
    if cap is None:
        res["못봄"].append("신청 상한(일반 건물 kW)")
    else:
        row = ("신청 상한(일반 건물)", f"{BASE['상한_kW']:g} kW", f"{cap:g} kW")
        (res["같음"] if abs(cap - BASE["상한_kW"]) < 1e-6 else res["후보"]).append(row)
    res["접수기간"] = e.get("접수기간", "")
    return res


# ── ⑥ 지원사업.csv 후보 ────────────────────────────────────────

_EQUIP = (("히트펌프", "공기열"), ("공기열", "공기열"), ("지열", "지열"),
          ("태양열", "태양열"), ("태양광", "태양광"), ("단열", "단열"),
          ("그린리모델링", "효율"), ("재생에너지", "태양광"))


def equip_of(text: str) -> str:
    found = []
    for w, e in _EQUIP:
        if w in text and e not in found:
            found.append(e)
    return " / ".join(found) or "확인 필요"


def csv_line(vals) -> str:
    out = []
    for v in vals:
        s = str(v or "").replace(NL, " ")
        if any(c in s for c in ',"'):
            s = '"' + s.replace('"', '""') + '"'
        out.append(s)
    return ",".join(out)


def csv_candidates(gov_items: dict, gov_ids, knrec_ex: dict, knrec_ids, checked: str) -> list:
    rows = []
    for no in knrec_ids:
        e = knrec_ex.get(no)
        if not e:
            continue
        price = e.get("일반단가_천원")
        what = f"kW당 {price / 10:g}만 원(공고문에서 자동 추출, 확인 필요)" if price else "첨부 원문 확인"
        cap = f"{e['상한_kW']:g} kW 이하" if e.get("상한_kW") else ""
        rows.append([e.get("제목", ""), equip_of(e.get("제목", "")), "전국", cap, "",
                     what, e.get("접수기간", "") or "", e.get("공고번호") or ("에너지공단 사업공고 " + no),
                     "원문", checked, e.get("링크", "")])
    for sid in gov_ids:
        it = gov_items.get(sid)
        # 보조금24 는 「관련 높음」만 후보로 냅니다(주택 전용·무관·분류 못 함은 뺌)
        if not it or relevance(it)[0] != REL_HIGH:
            continue
        sido = it.get("시도", "")
        if sido.startswith("전국"):
            sido = "전국"
        elif sido.startswith("기타"):
            sido = "확인 필요"
        else:
            sido = it.get("소관기관명", "") or sido
        rows.append([it.get("서비스명", ""),
                     equip_of(it.get("서비스명", "") + it.get("지원내용", "")),
                     sido, "", short("대상: " + it.get("지원대상", "") + " / " + it.get("사용자구분", ""), 90),
                     short(it.get("지원내용", ""), 90), it.get("신청기한", ""),
                     "보조금24 서비스ID " + sid, "원문", checked, it.get("상세조회URL", "")])
    return rows


# ── 보고서 ─────────────────────────────────────────────────────

def md_cell(s, n=None) -> str:
    s = short(s, n) if n else clean(s)
    return s.replace("|", "／") or "-"


def md_table(head, rows) -> list:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join(md_cell(c) for c in r) + " |")
    return out


def _date(s: str) -> str:
    s = str(s or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if re.fullmatch(r"\d{8}", s) else s


def _gov_rows(items, ids, with_word=False):
    rows = []
    for i in ids:
        it = items[i]
        name = (f"[{md_cell(it['서비스명'])}]({it['상세조회URL']})"
                if it["상세조회URL"] else it["서비스명"])
        r = [it["시도"], name, it["소관기관명"], short(it["지원대상"], 70),
             short(it["지원내용"], 90), it["신청기한"]]
        if with_word:
            r.append(relevance(it)[1] or "-")
        rows.append(r)
    return rows


def _by_sido(items, ids):
    order = {s: n for n, (s, _) in enumerate(sido_counts(items, ids))}
    return sorted(ids, key=lambda i: (order.get(items[i]["시도"], 99), items[i]["서비스명"]))


def gov24_section(items: dict, ids, rel: dict, label: str = "") -> list:
    """보조금24 사업을 사찰 관련성으로 나눠 그립니다.

    관련 높음 = 표 전체 · 분류 못 함 = 표(접지 않음) · 주택 전용 = 시·도별 건수만 ·
    무관 = 접어 둠(<details>). 시·도별 건수 표는 넷을 나란히 셉니다.
    """
    L = []
    group = {c: [i for i in ids if rel[i][0] == c]
             for c in (REL_HIGH, REL_UNKNOWN, REL_HOUSE, REL_NONE)}
    L.append(f"### {label}시·도별 건수")
    L.append("")
    rows = []
    for s_, n in sido_counts(items, ids):
        cnt = {c: sum(1 for i in group[c] if items[i]["시도"] == s_) for c in group}
        rows.append((s_, n, cnt[REL_HIGH] or "-", cnt[REL_HOUSE] or "-", cnt[REL_NONE] or "-",
                     cnt[REL_UNKNOWN] or "-"))
    rows.append(("**합계**", len(ids), len(group[REL_HIGH]), len(group[REL_HOUSE]),
                 len(group[REL_NONE]), len(group[REL_UNKNOWN])))
    L += md_table(("시·도", "전체", REL_HIGH, REL_HOUSE, REL_NONE, REL_UNKNOWN), rows)
    L.append("")
    head = ("시·도", "사업명", "소관기관", "대상", "지원 내용", "신청기간")

    L.append(f"### {label}{REL_HIGH} ({len(group[REL_HIGH])})")
    L.append("")
    if group[REL_HIGH]:
        L.append("대상에 건물·비주거·비영리·종교·사회복지시설·노유자가 있거나, "
                 "건물지원·융복합·금융지원에 얹는 사업입니다.")
        L.append("")
        L += md_table(head + ("걸린 말",), _gov_rows(items, _by_sido(items, group[REL_HIGH]), True))
    else:
        L.append("없습니다.")
    L.append("")

    if group[REL_UNKNOWN]:
        L.append(f"### {REL_UNKNOWN} ({len(group[REL_UNKNOWN])}) - 사람이 봐 주십시오")
        L.append("")
        L.append("어느 규칙에도 걸리지 않았습니다. 사찰에 맞는지 보시고, 맞으면 "
                 "`RELEVANCE_RULES` 에 말을 더해 주십시오.")
        L.append("")
        L += md_table(head, _gov_rows(items, _by_sido(items, group[REL_UNKNOWN])))
        L.append("")

    L.append(f"### {label}{REL_HOUSE} ({len(group[REL_HOUSE])})")
    L.append("")
    if group[REL_HOUSE]:
        L.append("대상이 주택·가구·거주자로만 되어 있어 사찰은 해당하기 어렵습니다. "
                 "시·도별 건수만 적습니다: " +
                 " · ".join(f"{s_} {n}" for s_, n in sido_counts(items, group[REL_HOUSE])))
    else:
        L.append("없습니다.")
    L.append("")

    if group[REL_NONE]:
        L.append("<details>")
        L.append(f"<summary>{label}{REL_NONE} {len(group[REL_NONE])}건 - 펼쳐 보기</summary>")
        L.append("")
        L += md_table(head + ("걸린 말",), _gov_rows(items, _by_sido(items, group[REL_NONE]), True))
        L.append("")
        L.append("</details>")
        L.append("")
    return L


def sido_counts(items: dict, ids=None) -> list:
    ids = list(items) if ids is None else ids
    cnt = {}
    for i in ids:
        it = items[i]
        cnt[it["시도"]] = cnt.get(it["시도"], 0) + 1
    order = [s for s in SIDO_ORDER if s in cnt]
    order += sorted(s for s in cnt if s not in SIDO_ORDER)
    return [(s, cnt[s]) for s in order]


def build_report(ctx: dict) -> str:
    """ctx: 아래 run() 이 채웁니다. 시험에서도 이 함수만 따로 부릅니다."""
    L = []
    day = ctx["today"].isoformat()
    first = ctx["first"]
    L.append(f"# 지원사업·법령 수집 보고 {day}")
    L.append("")
    L.append(f"돌린 시각 {ctx['stamp']} · 요청 {ctx['requests']}회 · "
             f"원자료 `data/수집/{ctx['today'].strftime('%Y%m')}/`")
    L.append("")
    if ctx.get("rebuilt"):
        L.append("> **기준선에서 다시 쓴 보고서입니다.** 인터넷에 묻지 않고 `기준선.json` 에 "
                 f"저장된 것({ctx['rebuilt']} 저장)을 지금 규칙으로 다시 나눴습니다. "
                 "기준선은 바꾸지 않았습니다.")
        L.append("")
    elif first:
        L.append("> **첫 실행입니다.** 「지난번」이 없어 이번에 모은 것을 **전부 기준선으로**"
                 " 저장했습니다. 아래는 전체 목록이고, 다음부터는 달라진 것만 나옵니다.")
        L.append("")

    # ⑤ 기준값 — 맨 위
    cmp_ = ctx["base"]
    if cmp_["후보"]:
        L.append("## ⚠ 기준값 변경 후보")
        L.append("")
        L.append("에너지공단 공고문에서 뽑은 값이 지원사업 문서 8장과 **다릅니다.** 원문을 열어 "
                 "확인하신 뒤 맞으면 `수정대기목록.md` 에 한 줄 더해 주십시오.")
        L.append("")
        L += md_table(("기준값", "문서 8장", "공고문"), cmp_["후보"])
        L.append("")
        L.append(f"근거 공고: [{md_cell(cmp_['공고']['제목'])}]({cmp_['공고']['링크']})")
        L.append("")
    else:
        L.append("## 기준값 대조")
        L.append("")
        if cmp_["공고"] and cmp_["같음"]:
            L.append(f"건물지원 공고 [{md_cell(cmp_['공고']['제목'])}]({cmp_['공고']['링크']}) 의 값이 "
                     "문서 8장과 **같습니다**: " +
                     " · ".join(f"{a} {c}" for a, b, c in cmp_["같음"]))
            if cmp_.get("접수기간"):
                L.append("")
                L.append(f"접수기간(공고문): {cmp_['접수기간']}")
        else:
            L.append("대조하지 못했습니다. 아래 「자동으로 못 잡은 것」을 보십시오.")
        L.append("")

    # 요약
    L.append("## 한눈에")
    L.append("")
    rows = []
    for name, d, n in ctx["summary"]:
        if d is None:
            rows.append((name, n, "못 읽음", "-", "-"))
        elif d["first"]:
            rows.append((name, n, f"기준선 {len(d['new'])}", "-", "-"))
        else:
            rows.append((name, n, len(d["new"]), len(d["changed"]),
                         "안 셈(일부 실패)" if d.get("partial") else len(d["removed"])))
    L += md_table(("어디", "이번에 본 것", "새로", "바뀜", "사라짐"), rows)
    L.append("")

    # ① 보조금24
    g = ctx["gov"]
    L.append("## ① 보조금24 (대한민국 공공서비스 정보)")
    L.append("")
    L.append("찾은 말: " + ", ".join(GOV24_WORDS) + f" — 칸 {', '.join(GOV24_FIELDS)}")
    L.append("")
    if g["d"] is None:
        L.append("이번에 읽지 못했습니다.")
    else:
        items, d = g["items"], g["d"]
        rel = {i: relevance(items[i]) for i in items}
        show = d["new"]
        if first:
            local = [i for i in items if is_local(items[i])]
            L.append(f"전체 **{len(items)}건**, 그중 지자체 사업 **{len(local)}건**. "
                     "사찰 관련성은 스크립트 위쪽 `RELEVANCE_RULES` 로 자동으로 나눈 것입니다.")
            L.append("")
        if show:
            L += gov24_section(items, show, rel, "" if first else "새로 잡힌 ")
        if d["changed"]:
            L.append("### 내용이 바뀐 사업")
            L.append("")
            for i, ch in d["changed"]:
                L.append(f"- **{md_cell(items[i]['서비스명'])}** ({items[i]['소관기관명']}) "
                         f"- {rel[i][0]}")
                for fld, (a, b) in ch.items():
                    L.append(f"  - {fld}: {short(a, 80)} → **{short(b, 80)}**")
            L.append("")
        if d["removed"] and not d.get("partial"):
            L.append("### 목록에서 빠진 사업")
            L.append("")
            for i in d["removed"]:
                p = g["prev"].get(i, {})
                L.append(f"- {md_cell(p.get('서비스명', i))} ({p.get('소관기관명', '')})")
            L.append("")
        if not first and not (d["new"] or d["changed"] or d["removed"]):
            L.append("달라진 것이 없습니다.")
            L.append("")

    # ② 에너지공단
    k = ctx["knrec"]
    L.append("## ② 에너지공단 재생에너지센터 사업공고")
    L.append("")
    if k["d"] is None:
        L.append("이번에 읽지 못했습니다.")
        L.append("")
    else:
        items, d = k["items"], k["d"]
        ids = sorted(d["new"], key=int, reverse=True)
        if ids:
            L += md_table(("등록일", "제목", "부서", "진행", "마감일"),
                          [(items[i]["등록일"], f"[{md_cell(items[i]['제목'])}]({items[i]['링크']})",
                            items[i]["부서"], items[i]["진행"], items[i]["마감일"]) for i in ids])
            L.append("")
        else:
            L.append("새 공고가 없습니다.")
            L.append("")
        opened = [(no, e) for no, e in k["추출"].items() if no in k["opened_now"]]
        if opened:
            L.append("### 첨부에서 뽑은 값")
            L.append("")
            for no, e in sorted(opened, key=lambda x: int(x[0]), reverse=True):
                L.append(f"**[{md_cell(e['제목'])}]({e['링크']})**")
                L.append("")
                files = ", ".join(a["이름"] + ("" if a["열림"] else f" ({a.get('까닭') or '못 엶'})")
                                  for a in e["첨부"]) or "없음"
                L.append(f"- 첨부: {files}")
                if e.get("일반단가_천원") is not None:
                    L.append(f"- 보조금 단가(일반 200 kW 이하): **{e['일반단가_천원']:g}천원/kW**"
                             f" = {e['일반단가_천원'] / 10:g}만 원/kW")
                if e.get("상한_kW") is not None:
                    L.append(f"- 신청 상한(일반): **{e['상한_kW']:g} kW**")
                if e.get("접수기간"):
                    L.append(f"- 접수기간: {e['접수기간']}")
                uniq = []
                for p in e.get("단가들", []):
                    s = f"{p['값']}{p['단위']}/kW"
                    if s not in uniq:
                        uniq.append(s)
                if uniq:
                    L.append("- 글에 나온 kW당 값: " + ", ".join(uniq[:12]))
                if not (e.get("일반단가_천원") or e.get("상한_kW") or e.get("접수기간") or uniq):
                    L.append("- 단가·상한·접수기간을 찾지 못했습니다")
                L.append("")

    # ③ 입법예고
    lm = ctx["lawmaking"]
    L.append("## ③ 법제처 입법예고")
    L.append("")
    L.append("찾은 말(법령 제명): " + ", ".join(LAWMAKING_WORDS) + " · 최근 400일, 끝난 것 포함")
    L.append("")
    if lm["d"] is None:
        L.append("이번에 읽지 못했습니다.")
    elif lm["d"]["new"]:
        it = lm["items"]
        L += md_table(("제목", "소관부처", "종류", "의견 접수기간"),
                      [(f"[{md_cell(it[i]['제목'])}]({it[i]['링크']})", it[i]["소관부처"],
                        it[i]["법령종류"], it[i]["접수기간"])
                       for i in sorted(lm["d"]["new"], key=int, reverse=True)])
    else:
        L.append("새 입법예고가 없습니다.")
    L.append("")

    # ④ 법령
    law = ctx["law"]
    L.append("## ④ 국가법령정보")
    L.append("")
    if law["d"] is None:
        L.append("이번에 읽지 못했습니다.")
        L.append("")
    else:
        for grp, d in law["d"].items():
            items = law["groups"][grp]
            L.append(f"### {grp} ({len(items)})")
            L.append("")
            if d is None:
                L.append("이번에 읽지 못했습니다.")
                L.append("")
                continue
            if grp == "행정규칙":
                for i, it in items.items():
                    if it.get("기대번호") and it["발령번호"] != it["기대번호"]:
                        L.append(f"> **{it['이름']}** 의 발령번호가 **제{it['발령번호']}호** 입니다"
                                 f"(지원사업 문서는 제{it['기대번호']}호). 개정됐는지 확인하십시오.")
                        L.append("")
            ids = d["new"]
            if grp == "자치법규" and first:
                L.append("지자체별: " + " · ".join(
                    f"{s} {n}" for s, n in _ordin_by_sido(items)))
                L.append("")
                ids = sorted(ids, key=lambda i: items[i]["공포일자"], reverse=True)[:25]
                L.append(f"최근 공포 {len(ids)}건:")
                L.append("")
            if ids:
                L += _law_rows(grp, items, ids)
                L.append("")
            if d["changed"]:
                L.append("**바뀐 것**")
                L.append("")
                for i, ch in d["changed"]:
                    L.append(f"- [{md_cell(items[i]['이름'])}]({items[i]['링크']}): " + "; ".join(
                        f"{f} {_date(a)} → **{_date(b)}**" for f, (a, b) in ch.items()))
                L.append("")
            if d["removed"] and not d.get("partial"):
                L.append("**목록에서 빠진 것**(현행에서 내려갔거나 시행예정이 시행됨): " + ", ".join(
                    md_cell(law["prev"].get(grp, {}).get(i, {}).get("이름", i)) for i in d["removed"]))
                L.append("")
            if not first and not (d["new"] or d["changed"] or d["removed"]):
                L.append("달라진 것이 없습니다.")
                L.append("")

    # ⑥ CSV 후보
    L.append("## 지원사업.csv 후보 줄")
    L.append("")
    cand = ctx["csv"]
    if cand:
        L.append("`data/지원사업.csv` 는 **고치지 않았습니다.** 맞는 줄만 골라 옮겨 주십시오. "
                 f"보조금24 는 「{REL_HIGH}」만 넣었습니다. "
                 "보조금24 줄의 「조건_용량」은 비어 있습니다(공고문을 봐야 압니다). "
                 f"같은 내용을 `data/수집/{ctx['today'].strftime('%Y%m')}/지원사업_후보.csv` 에도 두었습니다.")
        L.append("")
        L.append("```csv")
        L.append(csv_line(CSV_COLUMNS))
        for r in cand:
            L.append(csv_line(r))
        L.append("```")
    else:
        L.append("후보가 없습니다.")
    L.append("")

    # ⑦ 못 잡은 것
    L.append("## 자동으로 못 잡은 것")
    L.append("")
    probs = ctx["problems"] + [f"기준값 대조 - {x}" for x in cmp_["못봄"]]
    if probs:
        for p in probs:
            L.append(f"- {p}")
    else:
        L.append("없습니다.")
    L.append("")
    L.append("---")
    L.append("이 보고서는 `scripts/지원사업_수집.py` 가 만들었습니다. 숫자는 공고문 글자에서 "
             "자동으로 뽑은 것이라 **신청 전 원문을 확인**하십시오.")
    return NL.join(L) + NL


def _ordin_by_sido(items: dict) -> list:
    cnt = {}
    for it in items.values():
        s = sido_of(it["지자체"]) or it["지자체"].split(" ")[0]
        cnt[s] = cnt.get(s, 0) + 1
    order = [s for s in SIDO_ORDER if s in cnt] + sorted(s for s in cnt if s not in SIDO_ORDER)
    return [(s, cnt[s]) for s in order]


def _law_rows(grp: str, items: dict, ids) -> list:
    if grp == "법령":
        return md_table(("법령", "상태", "공포", "시행", "제개정"),
                        [(f"[{md_cell(items[i]['이름'])}]({items[i]['링크']})", items[i]["상태"],
                          _date(items[i]["공포일자"]), _date(items[i]["시행일자"]), items[i]["제개정"])
                         for i in ids])
    if grp == "행정규칙":
        return md_table(("행정규칙", "번호", "발령", "시행", "제개정"),
                        [(f"[{md_cell(items[i]['이름'])}]({items[i]['링크']})", items[i]["발령번호"],
                          _date(items[i]["발령일자"]), _date(items[i]["시행일자"]), items[i]["제개정"])
                         for i in ids])
    if grp == "별표":
        return md_table(("법령", "별표", "종류", "공포·발령"),
                        [(items[i]["법령"], f"[{md_cell(items[i]['이름'], 60)}]({items[i]['링크']})",
                          items[i]["종류"], _date(items[i]["공포일자"])) for i in ids])
    if grp == "법령해석":
        return md_table(("안건", "해석일", "기관"),
                        [(f"[{md_cell(items[i]['이름'], 80)}]({items[i]['링크']})",
                          _date(items[i]["해석일자"]), items[i]["해석기관"]) for i in ids])
    return md_table(("조례", "지자체", "공포", "시행", "제개정"),
                    [(f"[{md_cell(items[i]['이름'])}]({items[i]['링크']})", items[i]["지자체"],
                      _date(items[i]["공포일자"]), _date(items[i]["시행일자"]), items[i]["제개정"])
                     for i in ids])


# ── 한 번 돌리기 ───────────────────────────────────────────────

def _kst_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=9)))


def run(keys_path: str, out_dir: str, fetcher=None, now=None, log=print) -> str:
    """수집하고 보고서 경로를 돌려줍니다. 어느 한 곳이 실패해도 끝까지 갑니다."""
    global _SECRETS
    now = now or _kst_now()
    today = now.date()
    keys = read_keys(keys_path)
    svc, oc = keys.get(SERVICE, ""), keys.get(LAWOC, "")
    _SECRETS = Secrets(svc, oc)
    f = fetcher or Fetcher(_SECRETS)
    f.secrets = _SECRETS

    run_dir = os.path.join(out_dir, today.strftime("%Y%m"))
    base_path = os.path.join(out_dir, "기준선.json")
    base = load_json(base_path) or {}
    first = not base.get("sources")
    src = dict(base.get("sources") or {})
    problems, raw = [], {}

    # ①
    log("  [1/4] 보조금24 ...")
    gov = {"items": {}, "d": None, "prev": (src.get("보조금24") or {}).get("items", {})}
    if not svc:
        problems.append(f"보조금24 - 키.txt 에 「{SERVICE}」 키가 없습니다")
    else:
        try:
            r = collect_gov24(f, svc, raw, problems)
            if r["ok"]:
                gov["items"] = r["items"]
                gov["d"] = diff(src.get("보조금24", {}).get("items") if "보조금24" in src else None,
                                r["items"], GOV24_COMPARE)
                gov["d"]["partial"] = r["partial"]
                keep = dict(gov["prev"]) if r["partial"] else {}
                keep.update(r["items"])
                src["보조금24"] = {"items": keep, "저장": now.isoformat()}
        except Exception as e:
            problems.append(f"보조금24 - 처리하다 멈췄습니다({type(e).__name__}: {_SECRETS.hide(str(e))[:150]})")
    save_json(os.path.join(run_dir, "보조금24.json"), raw.get("보조금24", []))

    # ②
    log("  [2/4] 에너지공단 사업공고 ...")
    knrec = {"items": {}, "d": None, "추출": {}, "opened_now": set()}
    try:
        prev_k = src.get("에너지공단")
        before = set((prev_k or {}).get("추출", {}))
        r = collect_knrec(f, prev_k, run_dir, problems)
        if r["ok"]:
            knrec["items"] = r["items"]
            knrec["추출"] = r["추출"]
            knrec["opened_now"] = set(r["추출"]) - before
            knrec["d"] = diff((prev_k or {}).get("items") if prev_k else None, r["items"], ())
            knrec["d"]["partial"] = r["partial"]
            items = dict((prev_k or {}).get("items", {}))
            items.update(r["items"])     # 공고는 목록 뒤로 밀려도 지우지 않습니다
            src["에너지공단"] = {"items": items, "추출": r["추출"], "저장": now.isoformat()}
            knrec["d"]["removed"] = []
    except Exception as e:
        problems.append(f"에너지공단 - 처리하다 멈췄습니다({type(e).__name__}: {_SECRETS.hide(str(e))[:150]})")
    save_json(os.path.join(run_dir, "에너지공단_추출.json"), knrec["추출"])

    # ③
    log("  [3/4] 입법예고 ...")
    lm = {"items": {}, "d": None}
    try:
        prev_l = src.get("입법예고")
        r = collect_lawmaking(f, today, run_dir, problems)
        if r["ok"]:
            lm["items"] = r["items"]
            lm["d"] = diff((prev_l or {}).get("items") if prev_l else None, r["items"], ())
            lm["d"]["removed"] = []        # 400일 창이 밀리며 빠지는 것은 알릴 일이 아닙니다
            items = dict((prev_l or {}).get("items", {}))
            items.update(r["items"])
            src["입법예고"] = {"items": items, "저장": now.isoformat()}
    except Exception as e:
        problems.append(f"입법예고 - 처리하다 멈췄습니다({type(e).__name__}: {_SECRETS.hide(str(e))[:150]})")
    save_json(os.path.join(run_dir, "입법예고.json"), lm["items"])

    # ④
    log("  [4/4] 국가법령정보 ...")
    law = {"groups": {}, "d": None, "prev": {}}
    if not oc:
        problems.append(f"국가법령정보 - 키.txt 에 「{LAWOC}」 가 없습니다")
    else:
        try:
            r = collect_law(f, oc, raw, problems)
            prev_g = (src.get("법령") or {}).get("groups")
            law["prev"] = prev_g or {}
            law["groups"] = r["groups"]
            law["d"] = {}
            newsrc = dict(prev_g or {})
            for grp, cur in r["groups"].items():
                calls_failed = r["failed"][grp]
                if calls_failed and not cur:
                    law["d"][grp] = None
                    continue
                pg = (prev_g or {}).get(grp) if prev_g is not None else None
                d = diff(pg, cur, LAW_COMPARE[grp])
                d["partial"] = calls_failed > 0
                law["d"][grp] = d
                keep = dict(pg or {}) if calls_failed else {}
                keep.update(cur)
                newsrc[grp] = keep
            if any(v is not None for v in law["d"].values()):
                src["법령"] = {"groups": newsrc, "저장": now.isoformat()}
            else:
                law["d"] = None
        except Exception as e:
            problems.append(f"국가법령정보 - 처리하다 멈췄습니다({type(e).__name__}: {_SECRETS.hide(str(e))[:150]})")
    save_json(os.path.join(run_dir, "법령.json"), raw.get("법령", []))

    # ⑤⑥
    cmp_ = compare_base(knrec["추출"] or (src.get("에너지공단") or {}).get("추출", {}))
    checked = today.isoformat()
    cand = csv_candidates(gov["items"], (gov["d"] or {}).get("new", []) +
                          [i for i, _ in (gov["d"] or {}).get("changed", [])],
                          knrec["추출"], sorted(knrec["opened_now"], key=int, reverse=True), checked)
    if cand:
        save(os.path.join(run_dir, "지원사업_후보.csv"),
             "\ufeff" + NL.join(csv_line(r) for r in [CSV_COLUMNS] + cand) + NL)

    summary = [
        ("① 보조금24", gov["d"], len(gov["items"])),
        ("② 에너지공단 공고", knrec["d"], len(knrec["items"])),
        ("③ 입법예고", lm["d"], len(lm["items"])),
    ]
    if law["d"]:
        for grp, d in law["d"].items():
            summary.append((f"④ {grp}", d, len(law["groups"].get(grp, {}))))
    else:
        summary.append(("④ 국가법령정보", None, 0))

    ctx = {"today": today, "stamp": now.strftime("%Y-%m-%d %H:%M"), "first": first,
           "requests": f.count, "base": cmp_, "summary": summary, "gov": gov,
           "knrec": knrec, "lawmaking": lm, "law": law, "csv": cand, "problems": problems}
    report = build_report(ctx)
    rpath = os.path.join(out_dir, f"수집보고_{today.strftime('%Y%m%d')}.md")
    save(rpath, report)

    base = {"저장": now.isoformat(), "sources": src}
    save_json(base_path, base)
    return rpath


def rebuild(out_dir: str, now=None) -> str:
    """인터넷 없이 `기준선.json` 만으로 보고서를 다시 씁니다.

    `RELEVANCE_RULES` 를 고친 뒤 결과를 바로 보려고 둡니다. 기준선은
    건드리지 않고, 보고서 이름 끝에 「_다시씀」을 붙여 그날 보고서를 덮지 않습니다.
    """
    now = now or _kst_now()
    today = now.date()
    base = load_json(os.path.join(out_dir, "기준선.json"))
    if not base or not base.get("sources"):
        raise FileNotFoundError("기준선.json 이 없습니다. 먼저 한 번 수집을 돌려 주십시오.")
    src = base["sources"]
    gi = (src.get("보조금24") or {}).get("items", {})
    kn = src.get("에너지공단") or {}
    lmi = (src.get("입법예고") or {}).get("items", {})
    lg = (src.get("법령") or {}).get("groups", {})
    gov = {"items": gi, "d": diff(None, gi, ()) if gi else None, "prev": {}}
    knrec = {"items": kn.get("items", {}), "추출": kn.get("추출", {}),
             "opened_now": set(kn.get("추출", {})),
             "d": diff(None, kn.get("items", {}), ()) if kn else None}
    lm = {"items": lmi, "d": diff(None, lmi, ()) if lmi else None}
    law = {"groups": lg, "prev": {},
           "d": {g: diff(None, v, ()) for g, v in lg.items()} if lg else None}
    cmp_ = compare_base(knrec["추출"])
    checked = (base.get("저장") or today.isoformat())[:10]
    cand = csv_candidates(gi, sorted(gi), knrec["추출"],
                          sorted(knrec["추출"], key=int, reverse=True), checked)
    summary = [("① 보조금24", gov["d"], len(gi)), ("② 에너지공단 공고", knrec["d"], len(knrec["items"])),
               ("③ 입법예고", lm["d"], len(lmi))]
    summary += [(f"④ {g}", d, len(lg[g])) for g, d in (law["d"] or {}).items()]
    stamp = (base.get("저장") or "")[:16].replace("T", " ")
    ctx = {"today": today, "stamp": now.strftime("%Y-%m-%d %H:%M"), "first": True,
           "rebuilt": stamp, "requests": 0, "base": cmp_, "summary": summary, "gov": gov,
           "knrec": knrec, "lawmaking": lm, "law": law, "csv": cand, "problems": []}
    rpath = os.path.join(out_dir, f"수집보고_{today.strftime('%Y%m%d')}_다시씀.md")
    save(rpath, build_report(ctx))
    if cand:
        save(os.path.join(out_dir, today.strftime("%Y%m"), "지원사업_후보.csv"),
             "\ufeff" + NL.join(csv_line(r) for r in [CSV_COLUMNS] + cand) + NL)
    return rpath


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="지원사업·법령 자동 수집")
    ap.add_argument("--keys", default=os.path.join(ROOT, "키.txt"), help="키.txt 위치")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "수집"), help="내보낼 폴더")
    ap.add_argument("--다시쓰기", dest="rebuild", action="store_true",
                    help="인터넷 없이 기준선.json 으로 보고서만 다시 씀(규칙을 고친 뒤)")
    a = ap.parse_args(argv)
    if a.rebuild:
        try:
            path = rebuild(a.out)
        except FileNotFoundError as e:
            print(f"  {e}")
            return 1
        print(f"  보고서를 다시 썼습니다: {path}")
        return 0
    if not os.path.exists(a.keys):
        print(f"  키 파일이 없습니다: {a.keys}")
        print(f"  「{SERVICE}=」 과 「{LAWOC}=」 두 줄을 넣어 만들어 주세요.")
        return 1
    t0 = time.time()
    path = run(a.keys, a.out)
    print()
    print(f"  다 됐습니다 ({time.time() - t0:.0f}초).")
    print(f"  보고서: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
