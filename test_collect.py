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
    r1 = c.run(kp, out, fetcher=Fake(), now=now1, log=lambda *_: None)
    rep = io.open(r1, encoding="utf-8").read()
    ok("보고서 이름", os.path.basename(r1) == "수집보고_20261108.md")
    ok("첫 실행 안내", "첫 실행입니다" in rep)
    ok("기준선 저장", os.path.exists(os.path.join(out, "기준선.json")))
    ok("원자료 폴더 YYYYMM", os.path.isdir(os.path.join(out, "202611", "첨부")))
    ok("기준값 같음", "문서 8장과 **같습니다**" in rep and "기준값 변경 후보" not in rep)
    ok("시·도별 건수 표", "지자체 사업 시·도별 건수" in rep and "| 서울 |" in rep)
    ok("CSV 후보 머리줄", c.csv_line(c.CSV_COLUMNS) in rep)
    ok("CSV 후보 파일", os.path.exists(os.path.join(out, "202611", "지원사업_후보.csv")))
    ok("영농형 시행예정 법률", "영농형 태양광 발전사업의 활성화" in rep and "시행예정" in rep)
    ok("못 잡은 것 칸", "## 자동으로 못 잡은 것" in rep)
    allt = files_text(out)
    ok("어디에도 OC 값이 없다", FAKE_OC not in allt)
    ok("어디에도 공공데이터포털 키가 없다", FAKE_KEY not in allt)

    print("== 한 바퀴 - 두 번째 (바뀜·새 공고·한 곳 실패)")

    def patch(rows):
        rows[0]["신청기한"] = "2027. 3. ~ 2027. 11."     # 바뀜
        rows.pop()                                       # 사라짐
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
