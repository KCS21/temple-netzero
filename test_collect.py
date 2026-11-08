# -*- coding: utf-8 -*-
"""
지원사업·법령 수집(scripts/지원사업_수집.py) 확인
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

**인터넷도 인증키도 쓰지 않습니다.** `scripts/수집_표본/` 에 2026-11-08 에
실제로 받아 둔 응답으로 돌립니다. 사이트가 모양을 바꾸면 표본을 새로 받아
여기 시험이 그대로 통과하는지 보십시오.

출력은 cp949 로 찍히는 글자만 씁니다(CLAUDE.md 7장).
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "scripts", "수집_표본")

_spec = importlib.util.spec_from_file_location(
    "collect", os.path.join(HERE, "scripts", "지원사업_수집.py"))
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

passed = failed = 0


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        print(f"  [실패] {name} {extra}")


def sample(name, binary=False):
    p = os.path.join(SAMPLE, name)
    return open(p, "rb").read() if binary else io.open(p, encoding="utf-8").read()


def make_hwpx(text: str) -> bytes:
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w")
    z.writestr("mimetype", "application/hwp+zip")
    paras = "".join(f"<hp:p><hp:run><hp:t>{line}</hp:t></hp:run></hp:p>"
                    for line in text.replace("&", "&amp;").replace("<", "&lt;").split("\n"))
    z.writestr("Contents/section0.xml", f'<?xml version="1.0"?><hs:sec>{paras}</hs:sec>')
    z.close()
    return buf.getvalue()


print("== 키와 가리기")
tmp = tempfile.mkdtemp()
try:
    p = os.path.join(tmp, "키.txt")
    io.open(p, "w", encoding="cp949").write('# 설명\n공공데이터포털="abcd1234"\n국가법령OC=myoc77\n')
    k = c.read_keys(p)
    ok("cp949 키.txt 를 읽는다", k.get("공공데이터포털") == "abcd1234" and k.get("국가법령OC") == "myoc77")
    ok("키.txt 가 없으면 빈 dict", c.read_keys(os.path.join(tmp, "없음.txt")) == {})
finally:
    shutil.rmtree(tmp)

s = c.Secrets("abcd1234", "myoc77")
ok("키 값을 가린다", "abcd1234" not in s.hide("x?serviceKey=abcd1234&y=1"))
ok("링크의 OC 를 가린다(값을 몰라도)", s.hide("/DRF/lawService.do?OC=other99&target=law") ==
   "/DRF/lawService.do?OC=***&target=law")
ok("law_link 는 OC 를 빼고 사이트 주소를 붙인다",
   c.law_link("/DRF/lawService.do?OC=myoc77&target=law&MST=1") ==
   "https://www.law.go.kr/DRF/lawService.do?target=law&MST=1")

print("== ① 보조금24")
g = json.loads(sample("보조금24_태양광.json"))
rows = c.gov24_rows(g)
ok("표본 3줄", len(rows) == 3)
it = c.gov24_item(rows[0], "태양광")
ok("필요한 칸이 다 있다", all(k in it for k in c.GOV24_KEEP))
ok("노원구 사업은 서울", c.sido_label(it) == "서울" and c.is_local(it))
ok("중앙부처는 전국", c.sido_label({"소관기관명": "기후에너지환경부", "소관기관유형": "중앙행정기관"})
   == "전국(중앙부처)")
ok("공공기관은 기타", c.sido_label({"소관기관명": "한국전력공사", "소관기관유형": "공공기관"})
   == "기타(공공기관 등)")
ok("통합시는 전남광주", c.sido_of("전남광주통합특별시 구례군") == "전남광주")
ok("옛 이름 강원도도 강원", c.sido_of("강원도 원주시") == "강원" and c.sido_of("강원특별자치도") == "강원")
it2 = c.gov24_item({"서비스ID": "1", "사용자구분": "개인||법인/시설/단체"}, "x")
ok("사용자구분의 || 를 · 로", it2["사용자구분"] == "개인·법인/시설/단체")

print("== ② 에너지공단")
lst = c.knrec_list(sample("에너지공단_목록_1.html"))
ok("목록에서 10줄 넘게 읽는다", len(lst) >= 10, len(lst))
ok("메일 신청 창의 표를 공고로 읽지 않는다", all(r["no"].isdigit() and r["제목"] for r in lst))
ok("등록일 모양", all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["등록일"]) for r in lst))
ok("모양이 다른 쪽은 빈 목록(멈추지 않음)", c.knrec_list("<html><tbody><tr><td>x</td></tr></tbody>") == [])
v = c.knrec_view(sample("에너지공단_본문_6324.html"))
ok("본문 제목", v["제목"] == "2026년 재생에너지보급(건물지원) 사업 공고(수정)", v["제목"])
ok("공고 번호", "제2026-237호" in v["공고번호"], v["공고번호"])
ok("첨부 둘", len(v["첨부"]) == 2)
ok("첨부 이름에 그림 글자(한글파일)가 안 붙는다",
   v["첨부"][0][1] == "2026년 재생에너지보급(건물지원)사업 지원 공고문.hwpx", v["첨부"])

text = sample("건물지원_공고문_6324.txt")
t = c.find_terms(text)
ok("일반 단가 525 천원/kW", t["일반단가_천원"] == 525, t["일반단가_천원"])
ok("신청 상한 200 kW", t["상한_kW"] == 200, t["상한_kW"])
ok("접수기간", t["접수기간"].startswith("2026. 4. 14."), t["접수기간"])
vals = {p["값"] for p in t["단가들"]}
ok("다른 단가(축사 571, 200 kW 초과 414)도 남긴다", {"571", "414"} <= vals)
ok("㎾ 를 kW 로 맞춘다", c.find_terms("일반 200㎾ 이하 13,869 저탄소 모듈 600/㎾")["일반단가_천원"] == 600)
ok("값이 없으면 None", c.find_terms("아무 숫자 없음")["일반단가_천원"] is None)

print("== 첨부 열기")
ok("hwpx 글자", "지원단가 525/kW" in c.file_text("a.hwpx", make_hwpx("머리\n지원단가 525/kW")))
hwp = sample("하자보증_확인서_양식.hwp", binary=True)
mine = c._text_hwp(hwp) if True else ""
ok("hwp 글자 (내장 OLE 읽기)", "하자보증기간 발급 확인서" in mine)
try:
    import olefile  # noqa: F401
    import importlib
    cfb = c._Cfb(hwp)
    ok("내장 읽기와 olefile 이 같은 스트림을 본다",
       sorted("/".join(x) for x in cfb.listdir()) ==
       sorted("/".join(x) for x in olefile.OleFileIO(io.BytesIO(hwp)).listdir()))
except ImportError:
    print("  (olefile 이 없어 대조는 건너뜀)")
for name, data in (("a.xlsx", b"x"), ("a.hwpx", b"not zip"), ("a.hwp", b"not ole"), ("a.pdf", b"%PDF-broken")):
    try:
        c.file_text(name, data)
        ok(f"{name} 못 열면 RuntimeError", False)
    except RuntimeError:
        ok(f"{name} 못 열면 RuntimeError", True)
    except Exception as e:
        ok(f"{name} 못 열면 RuntimeError", False, type(e).__name__)

print("== 사찰 관련성")
R = c.relevance
ok("사회복지시설 -> 관련 높음", R({"서비스명": "사회복지시설 신재생에너지 보급 지원", "지원대상": "사회복지시설"})[0] == c.REL_HIGH)
ok("비영리·종교 -> 관련 높음", R({"서비스명": "x", "지원대상": "비영리법인, 종교단체"})[0] == c.REL_HIGH)
ok("노유자 -> 관련 높음", R({"서비스명": "x", "지원대상": "노유자시설"}) == (c.REL_HIGH, "노유자"))
ok("건물지원 지방비 추가 보조 -> 관련 높음",
   R({"서비스명": "신재생에너지 보급 지원", "지원대상": "사업 승인자", "지원내용": "건물지원사업 선정 시 시비 추가"})[0] == c.REL_HIGH)
ok("금융지원 -> 관련 높음 (대상의 「중소기업」에 걸리지 않음)",
   R({"서비스명": "신재생에너지금융지원", "지원대상": "개인, 중소, 중견 기업 * 중소기업"})[0] == c.REL_HIGH)
ok("단독주택 -> 주택 전용", R({"서비스명": "포천시 태양광 주택 지원", "지원대상": "단독주택의 소유자"})[0] == c.REL_HOUSE)
ok("「건물등기부등본」의 건물은 안 셈",
   R({"서비스명": "태양광주택보급사업", "지원대상": "건물등기부등본 또는 건축물대장의 용도가 단독주택인 건물로"})[0] == c.REL_HOUSE)
ok("거주자 -> 주택 전용", R({"서비스명": "미니태양광 설치 지원", "지원대상": "노원구 거주 신청자"})[0] == c.REL_HOUSE)
ok("축사 단열 -> 무관 (대상에 건물이 있어도)",
   R({"서비스명": "축사 단열처리 지원", "지원대상": "양돈농가 건물"})[0] == c.REL_NONE)
ok("「건축사 사무소」의 축사는 안 셈",
   R({"서비스명": "냉방설비 설치지원", "지원대상": "건축사 사무소, 연면적 1,000m2 이상의 건물"})[0] == c.REL_HIGH)
ok("가스냉방·가스히트펌프는 화석연료 설비라 무관 (대상에 건물이 있어도)",
   R({"서비스명": "가스냉방설비 설치지원", "지원대상": "가스히트펌프 설치 건물"})[0] == c.REL_NONE)
ok("이용검토 -> 참고(절차·사후관리)",
   R({"서비스명": "신재생에너지 보급사업 지열이용검토 지원", "지원대상": "보급지원사업 설치자"})
   == (c.REL_REF, "이용검토"))
ok("고장·A/S -> 참고", R({"서비스명": "설비 고장 접수 지원센터", "지원대상": "설비 소유자"})[0] == c.REL_REF
   and R({"서비스명": "x", "지원대상": "A/S 를 받지 못한 설비"})[0] == c.REL_REF)
ok("발전사업 + 군민 개인 -> 무관",
   R({"서비스명": "에너지사업기금 융자 지원", "지원대상": "봉화군민",
      "지원내용": "신재생에너지 발전사업을 진행하는 봉화군민에게 융자"}) == (c.REL_NONE, "발전사업+군민"))
ok("발전사업이어도 대상이 군민·주민이 아니면 무관이 아님",
   R({"서비스명": "x", "지원대상": "비영리법인", "지원내용": "발전사업"})[0] == c.REL_HIGH)
ok("미니태양광은 대상에 일반건축물이 있어도 관련 높음이 아니라 참고",
   R({"서비스명": "미니태양광 보급사업", "지원대상": "주택 및 일반건축물"})[0] == c.REL_REF)
ok("주택만 대상인 미니태양광은 그대로 주택 전용",
   R({"서비스명": "미니태양광 설치 지원", "지원대상": "노원구 거주 신청자"})[0] == c.REL_HOUSE)
for name in ("발전소 시설 견학", "공영주차장 이용요금 감면", "기후환경보증", "신재생에너지산업 해외진출지원",
             "귀농 정착 지원", "2026년 영광군 소상공인 신용보증수수료 지원"):
    ok(f"{name} -> 무관", R({"서비스명": name, "지원대상": ""})[0] == c.REL_NONE)
K = "한국전력공사"
ok("한전 고효율 LED -> 참고 (지원대상의 「농사용」보다 먼저)",
   R({"서비스명": "고효율 LED 지원", "소관기관명": K, "지원대상": "농사용 전력을 사용하며"}) == (c.REL_REF, "LED+한국전력공사"))
ok("한전 고효율 인버터 -> 참고 (지원대상의 「사출기」보다 먼저)",
   R({"서비스명": "고효율 인버터 지원", "소관기관명": K, "지원대상": "부하기기(팬, 펌프, 유압식 사출기)"})[0] == c.REL_REF)
ok("한전 고효율 펌프 -> 참고", R({"서비스명": "고효율 펌프 지원", "소관기관명": K, "지원대상": "고객"})[0] == c.REL_REF)
ok("한전이 아닌 곳의 펌프는 참고 규칙에 안 걸림",
   R({"서비스명": "고효율 펌프 지원", "소관기관명": "가시", "지원대상": "고객"})[0] != c.REL_REF)
ok("인버터제어형 공기압축기는 압축기라 무관",
   R({"서비스명": "인버터제어형 공기압축기 지원", "소관기관명": K, "지원대상": "고객"}) == (c.REL_NONE, "압축기"))
for name in ("고효율 터보압축기 지원", "고효율 냉동기 지원", "고효율 변압기 지원", "전동식 사출성형기 지원",
             "회생제동장치 지원", "김건조기 EHP 지원", "시설원예 EHP 지원"):
    ok(f"{name} -> 무관", R({"서비스명": name, "소관기관명": K, "지원대상": "고객"})[0] == c.REL_NONE)
ok("복지할인 고효율가전 -> 무관",
   R({"서비스명": "복지할인 고효율가전 구매비용 지원사업", "소관기관명": K, "지원대상": "가구원"})[0] == c.REL_NONE)
ok("복지시설냉난방기는 그대로 관련 높음",
   R({"서비스명": "복지시설냉난방기 지원", "소관기관명": K,
      "지원대상": "고효율 냉난방기를 설치하는 노인복지법 … 사회복지시설 - 에너지소비효율 1등급 제품(냉방기, 냉난방기, EHP 실외기)"})
   == (c.REL_HIGH, "사회복지시설"))
ok("어디에도 안 걸리면 「분류 못 함」", R({"서비스명": "설비 점검 지원", "지원대상": "설비 소유자"})
   == (c.REL_UNKNOWN, ""))
ok("표본 3줄은 모두 주택 전용", all(R(c.gov24_item(r, "태양광"))[0] == c.REL_HOUSE for r in rows))

_items = {}
for n, (name, who) in enumerate((("사회복지시설 태양광", "사회복지시설"), ("주택 태양광", "단독주택"),
                                 ("양돈 단열", "양돈농가"), ("설비 점검", "설비 소유자"),
                                 ("지열이용검토 지원", "설치자"))):
    _items[str(n)] = dict(c.gov24_item({"서비스ID": str(n), "서비스명": name, "지원대상": who,
                                        "소관기관명": "경기도 안양시"}, "x"), 시도="경기")
_rel = {i: R(_items[i]) for i in _items}
sec = chr(10).join(c.gov24_section(_items, list(_items), _rel))
ok("관련 높음은 표로", "### 관련 높음 (1)" in sec and "사회복지시설 태양광" in sec)
ok("주택 전용은 건수만 (사업명 없음)", "### 주택 전용 (1)" in sec and "주택 태양광" not in sec)
ok("무관은 접어 둠", "<details>" in sec and sec.index("<details>") < sec.index("양돈 단열"))
ok("분류 못 함은 펼친 채", "### 분류 못 함 (1)" in sec and sec.index("설비 점검") < sec.index("<details>"))
ok("참고는 관련 높음 다음, 주택 전용 앞",
   sec.index("### 관련 높음") < sec.index(f"### {c.REL_REF} (1)") < sec.index("### 주택 전용")
   and "지열이용검토 지원" in sec)
ok("시·도별 건수 표에 다섯이 나란히", "| 경기 | 5 | 1 | 1 | 1 | 1 | 1 |" in sec)

print("== ③ 입법예고")
lh = sample("입법예고_재생에너지.html")
lr = c.lawmaking_rows(lh)
ok("건수 칸과 줄 수가 같다", c.lawmaking_total(lh) == len(lr) == 7, c.lawmaking_total(lh))
ok("7줄 (표본)", len(lr) == 7, len(lr))
ok("줄마다 번호·제목·부처·기간", all(r["id"].isdigit() and "재생에너지" in r["제목"]
                                and r["소관부처"] and "~" in r["접수기간"] for r in lr))
ok("모양이 다르면 건수 None", c.lawmaking_total("<html></html>") is None)

print("== ④ 국가법령정보")
one = json.loads(sample("법령_영농형_시행예정.json"))
body = c.law_body(one)
ok("한 건이면 dict 로 오는 것을 list 로", len(c.as_list(body.get("law"))) == 1)
ok("_id_from_link", c._id_from_link("/DRF/x?OC=***&target=meCgmExpc&ID=20856&type=HTML") == "20856")

print("== 견주기")
d = c.diff(None, {"a": {}}, ())
ok("첫 실행은 전부 기준선", d["first"] and d["new"] == ["a"])
d = c.diff({"a": {"x": 1}, "b": {"x": 1}}, {"a": {"x": 2}, "c": {"x": 1}}, ("x",))
ok("새로·바뀜·사라짐", d["new"] == ["c"] and d["changed"] == [("a", {"x": (1, 2)})] and d["removed"] == ["b"])

same = c.compare_base({"6324": {"제목": "2026년 재생에너지보급(건물지원) 사업 공고", "일반단가_천원": 525.0, "상한_kW": 200.0}})
ok("기준값이 같으면 후보 없음", not same["후보"] and len(same["같음"]) == 2)
diff_ = c.compare_base({"6324": {"제목": "건물지원 공고", "일반단가_천원": 525.0, "상한_kW": 200.0},
                        "7400": {"제목": "2027년 건물지원 공고", "일반단가_천원": 550.0, "상한_kW": 300.0}})
ok("가장 최근 건물지원 공고와 견준다", diff_["공고"]["no"] == "7400")
ok("다르면 후보 둘", len(diff_["후보"]) == 2 and diff_["후보"][0][2] == "55만 원")
miss = c.compare_base({})
ok("공고가 없으면 「못봄」", miss["못봄"] and not miss["후보"])

ok("CSV 쉼표·따옴표", c.csv_line(['a,b', 'say "hi"', None]) == '"a,b","say ""hi""",')
ok("설비 짐작", c.equip_of("히트펌프 지원") == "공기열" and c.equip_of("주택 태양광") == "태양광")


print("== ⑥ 기관 공지")
mrows = c.mcee_rows(sample("기관공지_기후부_보도자료.html"), "10598")
ok("기후부 보도자료 10줄", len(mrows) == 10, len(mrows))
ok("줄마다 id·제목·날짜·링크", all(r["id"].startswith("mcee10598-") and r["제목"]
                                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["날짜"]) for r in mrows))
ok("링크에 jsessionid 가 없고 boardId 가 있다",
   all("jsessionid" not in r["링크"] and "boardId=" in r["링크"] for r in mrows))
ok("담당자 이름은 가져오지 않는다", all(set(r) == {"id", "제목", "날짜", "링크"} for r in mrows))
grows = c.green_rows(sample("기관공지_그린리모델링.html"))
ok("그린리모델링 공지 20줄", len(grows) == 20, len(grows))
ok("그린리모델링 링크·날짜", all("boardView.asp?bid=notice&nSeq=" in r["링크"]
                            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["날짜"]) for r in grows))
ok("모양이 다르면 빈 목록", c.mcee_rows("<html></html>", "1") == [] and c.green_rows("<p>x</p>") == [])
ok("제목 검색어", c.notice_hit("2027년 공공건축물 그린리모델링 사업") == "그린리모델링"
   and c.notice_hit("자동차 시험시설 수요조사") == "")


class NoticeFake:
    """기관 공지 목록만 돌려주는 가짜. `extra` 를 그린리모델링 1쪽 맨 위에 끼웁니다."""

    def __init__(self, extra="", bad=()):
        self.count, self.extra, self.bad, self.secrets = 0, extra, set(bad), None

    def get(self, url, params=None, **kw):
        self.count += 1
        if any(b in url for b in self.bad):
            raise c.FetchError("시험용 실패")
        if url.startswith(c.MCEE):
            return sample("기관공지_기후부_보도자료.html")
        h = sample("기관공지_그린리모델링.html")
        if self.extra and params.get("page") == 1:
            at = h.find("<tr", h.find("<tbody"))
            h = h[:at] + (f"<tr onClick='onView(9999)'><td>1</td><td><a href=\"#\">{self.extra}</a></td>"
                          "<td>공지</td><td>2026-12-01</td></tr>") + h[at:]
        return h


_src, _probs = {}, []
_tmpn = tempfile.mkdtemp()
try:
    n1 = c.notice_step(NoticeFake(), _src, _tmpn, _probs, dt.datetime(2026, 11, 8))
    g1 = n1["by"]["그린리모델링 창조센터 공지"]
    ok("처음 도는 수집처는 「처음 수집」(first)", g1["d"]["first"] and len(g1["items"]) > 0)
    ok("못 잡은 곳(한전)을 「못 잡은 것」에 적는다", any("한전" in x and "robots.txt" in x for x in _probs))
    n2 = c.notice_step(NoticeFake(extra="2027년 히트펌프 난방전기화 지원 안내"), _src, _tmpn, [],
                       dt.datetime(2026, 12, 8))
    g2 = n2["by"]["그린리모델링 창조센터 공지"]
    ok("두 번째는 새로 나온 글만", g2["d"]["new"] == ["green-notice-9999"], g2["d"]["new"])
    ok("새 글의 걸린 말", g2["items"]["green-notice-9999"]["찾은말"] == "히트펌프")
    ok("기후부는 새 글 없음", n2["by"]["기후에너지환경부 보도자료"]["d"]["new"] == [])
    before_n = len(_src["기관공지"]["items"])
    _p3 = []
    n3 = c.notice_step(NoticeFake(bad=("greenremodeling",)), _src, _tmpn, _p3, dt.datetime(2026, 12, 9))
    ok("한 곳이 실패하면 그곳만 「못 읽음」", n3["by"]["그린리모델링 창조센터 공지"]["d"] is None
       and n3["by"]["기후에너지환경부 보도자료"]["d"] is not None)
    ok("실패한 곳의 기준선은 그대로", len(_src["기관공지"]["items"]) == before_n)
    sec = "\n".join(c.notice_section(n1, False))
    ok("보고서: 처음 수집은 건수만", "**처음 수집:" in sec and "boardView.asp" not in sec)
    sec2 = "\n".join(c.notice_section(n2, False))
    ok("보고서: 새 글은 표로", "2027년 히트펌프 난방전기화 지원 안내" in sec2)
finally:
    shutil.rmtree(_tmpn)

print("== 조례 상한 · 처음 수집")


def _ord(n, name, words):
    return {str(n): {"이름": name, "찾은말": words, "공포일자": "20260101", "지자체": "경기도"}}


_o = {}
for n in range(250):
    _o.update(_ord(n, f"가시 기후위기 대응 기본 조례 {n}", "기후위기 대응"))
for n in range(250, 300):
    _o.update(_ord(n, f"나군 기후위기 대응 지원 조례 {n}", "기후위기 대응"))
for n in range(300, 310):
    _o.update(_ord(n, f"다시 재생에너지 발전설비 이격거리 조례 {n}", "이격거리"))
_small = {k: v for k, v in list(_o.items())[:100]}
cap0 = c.ordin_cap(_small)
ok("300건 이하면 거르지 않는다", not cap0["걸렀나"] and len(_small) == 100)
cap1 = c.ordin_cap(_o)
ok("300건 넘으면 걸러 낸다", cap1["걸렀나"] and cap1["전체"] == 310)
ok("더한 말로만 잡힌 것은 「지원」·「보조」가 든 것만 남김", sum(1 for v in _o.values()
   if "기후위기" in v["이름"]) == 50 and all("지원" in v["이름"] for v in _o.values() if "기후위기" in v["이름"]))
ok("이격거리 조례는 「지원」이 없어도 남김", sum(1 for v in _o.values() if "이격거리" in v["이름"]) == 10)
ok("남김·뺌 건수", cap1["남김"] == 60 and cap1["뺌"] == 250, cap1)

_items = {"a": {"찾은말": "재생에너지"}, "b": {"찾은말": "기후위기 대응"}, "c": {"찾은말": "태양광·이격거리"}}
_d = {"first": False, "new": ["a", "b", "c"], "changed": [], "removed": []}
c.split_fresh(_d, _items, c.ORDIN_WORDS_V1)
ok("예전 말로 잡히면 「새로」, 더한 말로만 잡히면 「처음 수집」", _d["new"] == ["a", "c"] and _d["fresh"] == ["b"])
_items2 = {"e": {"찾은말": "재생에너지", "이름": "가시 에너지 기본 조례"},
           "f": {"찾은말": "재생에너지", "이름": "나시 재생에너지 보급 조례"}}
_d2 = {"first": False, "new": ["e", "f"], "changed": [], "removed": []}
c.split_fresh(_d2, _items2, c.ORDIN_WORDS_V1, c.ORDIN_NAME_HAS_V1)
ok("예전 말로 잡혀도 예전 이름 거르기에서 빠졌을 조례는 「처음 수집」",
   _d2["new"] == ["f"] and _d2["fresh"] == ["e"])
_g = {"x": {"찾은말": "고효율"}, "y": {"찾은말": "태양광·고효율"}}
_dg = {"first": False, "new": ["x", "y"], "changed": [], "removed": []}
c.split_fresh(_dg, _g, c.GOV24_WORDS_V1)
ok("보조금24 도 같은 규칙", _dg["new"] == ["y"] and _dg["fresh"] == ["x"])
ok("더한 검색어가 들어 있다", all(w in c.GOV24_WORDS for w in ("공기열", "난방전기화", "고효율", "에너지효율", "펠릿"))
   and all(w in c.ORDIN_WORDS for w in ("기후위기 대응", "에너지 기본", "태양광", "히트펌프")))
ok("새 검색어로 잡힌 농어업·축사·주택은 그대로 무관·주택 전용",
   R({"서비스명": "고효율 소형 농기계 지원", "지원대상": "농업경영체등록을 한 농업인"})[0] == c.REL_NONE
   and R({"서비스명": "가축분뇨 퇴비 부숙용 톱밥 지원", "지원대상": "한우 농가"})[0] == c.REL_NONE
   and R({"서비스명": "목재펠릿 연소기 보급 지원", "지원대상": "1세대 당 1대"})[0] == c.REL_HOUSE)

print("== data/지원사업.csv (수정대기 #8 원본)")
import codecs
import csv
_sp = os.path.join(HERE, "data", "지원사업.csv")
_raw = open(_sp, "rb").read()
ok("UTF-8 BOM 으로 시작 (엑셀에서 한글이 안 깨짐)", _raw.startswith(codecs.BOM_UTF8))
_rows = list(csv.reader(io.open(_sp, encoding="utf-8-sig", newline="")))
ok("머리줄 11열이 수집 후보 형식과 같다", tuple(_rows[0]) == c.CSV_COLUMNS, _rows[0])
_body = [r for r in _rows[1:] if any(x.strip() for x in r)]
ok("내용 7줄", len(_body) == 7, len(_body))
ok("줄마다 11열", all(len(r) == 11 for r in _body), [len(r) for r in _body])
_col = {n: i for i, n in enumerate(c.CSV_COLUMNS)}


def _is_date(v):
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)) and dt.date.fromisoformat(v) is not None
    except ValueError:
        return False


ok("확인일이 날짜(YYYY-MM-DD)", all(_is_date(r[_col["확인일"]]) for r in _body),
   [r[_col["확인일"]] for r in _body])
ok("근거 수준이 원문·기사·옛자료·교수님 중 하나",
   all(r[_col["근거 수준"]] in ("원문", "기사", "옛자료", "교수님") for r in _body),
   [r[_col["근거 수준"]] for r in _body])
ok("사업·설비는 비지 않음", all(r[_col["사업"]] and r[_col["설비"]] for r in _body))
ok("링크는 비었거나 https", all(all(u.strip().startswith("https://") for u in r[_col["링크"]].split(";"))
                              for r in _body if r[_col["링크"]].strip()))
ok("건물지원 단가가 기준값(BASE)과 같다",
   any("건물지원" in r[0] and "태양광" in r[1] and f"{c.BASE['단가_만원']}만 원" in r[_col["지원 내용"]]
       and f"{c.BASE['상한_kW']} kW" in r[_col["조건_용량"]] for r in _body))


# ── 한 바퀴 (가짜 인터넷) ──────────────────────────────────────

FAKE_OC = "fakeoc99"
FAKE_KEY = "FAKEKEY12345"


class Fake:
    """URL 을 보고 표본을 돌려줍니다. `bad` 에 든 곳은 실패시킵니다."""

    def __init__(self, bad=(), gov_patch=None, extra_notice=False):
        self.count, self.secrets, self.bad = 0, None, set(bad)
        self.gov_patch, self.extra_notice = gov_patch, extra_notice

    def get(self, url, params=None, headers=None, timeout=30, binary=False):
        self.count += 1
        params = params or {}
        if any(b in url for b in self.bad):
            raise c.FetchError("시험용 실패")
        if url == c.GOV24_URL:
            if params.get("cond[서비스명::LIKE]") == "태양광":
                g = json.loads(sample("보조금24_태양광.json"))
                g["matchCount"] = len(g["data"])
                if self.gov_patch:
                    self.gov_patch(g["data"])
                return json.dumps(g, ensure_ascii=False)
            return json.dumps({"data": [], "matchCount": 0})
        if url == c.KNREC_LIST:
            h = sample("에너지공단_목록_5.html" if params.get("page") == 5 else "에너지공단_목록_1.html")
            if self.extra_notice:
                at = h.rfind("<tr", 0, h.find("view.do?no="))
                h = (h[:at] + "<tr><td>공지</td><td><a href=\"./view.do?no=9999\">진행</a></td>"
                     "<td>[공고]</td><td>2027년 재생에너지보급(건물지원) 사업 공고</td>"
                     "<td>재생지원사업처</td><td>2027-03-17</td><td>2027-04-24</td>"
                     "<td></td><td>1</td></tr>" + h[at:])
            return h
        if url == c.KNREC_VIEW:
            if params.get("no") in (6324, "6324"):
                return sample("에너지공단_본문_6324.html")
            if params.get("no") in (9999, "9999"):
                return sample("에너지공단_본문_6324.html").replace("6324", "9999")
            return "<html>첨부 없음</html>"
        if url == c.KNREC_FILE:
            text = sample("건물지원_공고문_6324.txt")
            if params.get("no") == "9999":
                text = text.replace("525/kW", "550/kW")
            return make_hwpx(text)
        if url == c.LAWMAKING:
            return sample("입법예고_재생에너지.html") if params.get("lsNm") == "재생에너지" else \
                '<p class="numBuild">전체<span>0</span>건</p>'
        if url == c.LAW_URL:
            key = (params.get("target"), params.get("query"), params.get("nw"))
            table = {
                ("law", "영농형", "2"): "법령_영농형_시행예정.json",
                ("law", "재생에너지 개발", "3"): "법령_재생에너지법_현행.json",
                ("admrul", "재생에너지 발전설비 이격거리", None): "행정규칙_이격거리.json",
                ("ordin", "이격거리", None): "자치법규_이격거리.json",
                ("meCgmExpc", "태양광", None): "법령해석_태양광.json",
                ("admbyl", "공기열", None): "별표_공기열.json",
            }
            if key in table:
                # 실제 응답처럼 링크에 OC 가 들어 있게 합니다 -> 저장할 때 지워져야 함
                return sample(table[key]).replace("OC=***", "OC=" + FAKE_OC)
            return json.dumps({"X": {"totalCnt": "0", "resultCode": "00"}})
        raise c.FetchError("모르는 주소 " + url)


def files_text(folder):
    out = []
    for root, _, names in os.walk(folder):
        for n in names:
            if n.endswith((".md", ".json", ".csv", ".html", ".txt")):
                out.append(io.open(os.path.join(root, n), encoding="utf-8", errors="replace").read())
    return "\n".join(out)


print("== 한 바퀴 - 첫 실행")
tmp = tempfile.mkdtemp()
try:
    kp = os.path.join(tmp, "키.txt")
    io.open(kp, "w", encoding="utf-8").write(f"공공데이터포털={FAKE_KEY}\n국가법령OC={FAKE_OC}\n")
    out = os.path.join(tmp, "수집")
    now1 = dt.datetime(2026, 11, 8, 10, 0)
    def add(rows):
        base = dict(rows[0])
        rows.append(dict(base, 서비스ID="T-HIGH", 서비스명="사회복지시설 신재생에너지 보급 지원",
                         지원대상="사회복지시설", 소관기관명="기후에너지환경부", 소관기관유형="중앙행정기관"))
        rows.append(dict(base, 서비스ID="T-NONE", 서비스명="축사 단열처리 지원", 지원대상="양돈농가"))
    r1 = c.run(kp, out, fetcher=Fake(gov_patch=add), now=now1, log=lambda *_: None)
    rep = io.open(r1, encoding="utf-8").read()
    ok("보고서 이름", os.path.basename(r1) == "수집보고_20261108.md")
    ok("첫 실행 안내", "첫 실행입니다" in rep)
    ok("기준선 저장", os.path.exists(os.path.join(out, "기준선.json")))
    ok("원자료 폴더 YYYYMM", os.path.isdir(os.path.join(out, "202611", "첨부")))
    ok("기준값 같음", "문서 8장과 **같습니다**" in rep and "기준값 변경 후보" not in rep)
    ok("시·도별 건수 표", "### 시·도별 건수" in rep and "| 서울 |" in rep)
    ok("CSV 후보 머리줄", c.csv_line(c.CSV_COLUMNS) in rep)
    ok("CSV 후보 파일", os.path.exists(os.path.join(out, "202611", "지원사업_후보.csv")))
    cand = io.open(os.path.join(out, "202611", "지원사업_후보.csv"), encoding="utf-8-sig").read()
    ok("CSV 후보에 관련 높음은 들어감", "사회복지시설 신재생에너지 보급 지원" in cand)
    ok("CSV 후보에 주택 전용·무관은 안 들어감", "미니태양광 설치 지원" not in cand and "축사 단열" not in cand)
    ok("보고서 CSV 칸도 같음", "미니태양광 설치 지원," not in rep and "사회복지시설 신재생에너지 보급 지원," in rep)
    ok("보고서: 무관은 접힘", "<summary>무관 1건" in rep)
    ok("영농형 시행예정 법률", "영농형 태양광 발전사업의 활성화" in rep and "시행예정" in rep)
    ok("못 잡은 것 칸", "## 자동으로 못 잡은 것" in rep)
    allt = files_text(out)
    ok("어디에도 OC 값이 없다", FAKE_OC not in allt)
    ok("어디에도 공공데이터포털 키가 없다", FAKE_KEY not in allt)

    print("== 한 바퀴 - 두 번째 (바뀜·새 공고·한 곳 실패)")

    def patch(rows):
        rows[0]["신청기한"] = "2027. 3. ~ 2027. 11."     # 바뀜
        rows.pop()                                       # 사라짐
        add(rows)
    before = json.load(io.open(os.path.join(out, "기준선.json"), encoding="utf-8"))
    n_lm = len(before["sources"]["입법예고"]["items"])
    r2 = c.run(kp, out, fetcher=Fake(bad=("lawmaking",), gov_patch=patch, extra_notice=True),
               now=dt.datetime(2026, 12, 8, 10, 0), log=lambda *_: None)
    rep2 = io.open(r2, encoding="utf-8").read()
    ok("첫 실행 안내가 없다", "첫 실행입니다" not in rep2)
    ok("바뀐 신청기한", "내용이 바뀐 사업" in rep2 and "2027. 3." in rep2)
    ok("빠진 사업", "목록에서 빠진 사업" in rep2)
    ok("새 공고가 표에", "2027년 재생에너지보급(건물지원)" in rep2)
    ok("기준값 변경 후보가 맨 위", "기준값 변경 후보" in rep2 and
       rep2.index("기준값 변경 후보") < rep2.index("## 한눈에"), "")
    ok("55만 원으로 읽음", "55만 원" in rep2)
    ok("입법예고 실패가 「못 잡은 것」에", "입법예고 「재생에너지」 - 시험용 실패" in rep2)
    after = json.load(io.open(os.path.join(out, "기준선.json"), encoding="utf-8"))
    ok("실패한 곳은 지난 기준선을 그대로 둔다",
       len(after["sources"]["입법예고"]["items"]) == n_lm and n_lm > 0)
    ok("법령은 달라진 것이 없다", "달라진 것이 없습니다" in rep2)

    print("== 기준선에서 다시 쓰기 (인터넷 없음)")
    snap = io.open(os.path.join(out, "기준선.json"), encoding="utf-8").read()
    rr = c.rebuild(out, now=dt.datetime(2026, 12, 9, 9, 0))
    reb = io.open(rr, encoding="utf-8").read()
    ok("다시 쓴 보고서 이름", os.path.basename(rr) == "수집보고_20261209_다시씀.md")
    ok("다시 쓴 안내", "기준선에서 다시 쓴 보고서" in reb and "첫 실행입니다" not in reb)
    ok("관련성으로 나뉜다", "### 관련 높음 (1)" in reb and "<summary>무관" in reb)
    ok("기준선은 그대로", io.open(os.path.join(out, "기준선.json"), encoding="utf-8").read() == snap)
    r_same = c.run(kp, out, fetcher=Fake(), now=dt.datetime(2026, 12, 8, 15, 0), log=lambda *_: None)
    ok("같은 날 두 번 돌면 _2 로 (앞 보고서를 덮지 않음)",
       os.path.basename(r_same) == "수집보고_20261208_2.md" and os.path.exists(r2))
    try:
        c.rebuild(os.path.join(tmp, "없는곳"))
        ok("기준선이 없으면 알림", False)
    except FileNotFoundError:
        ok("기준선이 없으면 알림", True)

    print("== 한 바퀴 - 모든 곳 실패해도 보고서는 나온다")
    r3 = c.run(kp, os.path.join(tmp, "수집3"),
               fetcher=Fake(bad=("odcloud", "knrec", "lawmaking", "law.go.kr")),
               now=now1, log=lambda *_: None)
    rep3 = io.open(r3, encoding="utf-8").read()
    ok("보고서가 나온다", rep3.startswith("# 지원사업"))
    ok("네 곳 모두 「못 읽음」", rep3.count("못 읽음") >= 4, rep3.count("못 읽음"))
finally:
    shutil.rmtree(tmp)

print()
print(f"통과 {passed} / 실패 {failed}")
sys.exit(1 if failed else 0)
