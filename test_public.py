# -*- coding: utf-8 -*-
"""
공개 홈페이지 확인 (작업지시 10 7장 · 11)

실행:  python test_public.py

인터넷도 인증키도 쓰지 않습니다. 구글 시트로 보내는 것은 가짜로 받습니다.

확인하는 것
  - 유형 판정표 여섯 줄
  - 계절비 (12달 중 0 이 있으면 None)
  - 연료 환산과 배출량이 emissions.burn 과 같은지
  - 자가진단 기록에 이름·연락처 열쇠가 없는지, 열쇠가 .gs 와 같은지
  - 컨설팅 요청 (동의 · 숨은 칸 · 연락처 형식)
  - 소개글 설정 칸 (비면 숨김, 값이 있으면 표시)
  - 결과 PDF 가 만들어지는지
"""
import io
import os
import re

import emissions as em
from public import content, report_pdf, selfcheck as sc, sheet

LINE = "-" * 68
HERE = os.path.dirname(os.path.abspath(__file__))
_fail = 0
_count = 0


def ok(name, cond, detail=""):
    global _fail, _count
    _count += 1
    if not cond:
        _fail += 1
    print(f"  [{'OK' if cond else 'FAIL'}]  {name}")
    if detail and not cond:
        print(f"         {detail}")


def months(vals):
    return {f"2025{m:02d}": v for m, v in zip(range(1, 13), vals)}


# 겨울 30,000 / 여름 최소 10,000 -> 3.0 · 겨울 20,000 / 여름 10,000 -> 2.0
HIGH = months([30000, 25000, 20000, 15000, 12000, 10000,
               11000, 12000, 10500, 12000, 18000, 28000])
LOW = months([20000, 18000, 16000, 14000, 12000, 10000,
              11000, 12000, 10500, 12000, 15000, 19000])


class FakeResp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class FakePost:
    """보낸 것을 받아 두기만 합니다."""

    def __init__(self, body=None, boom=False):
        self.calls, self.body, self.boom = [], body or {"ok": True}, boom

    def __call__(self, url, json=None, timeout=None):
        self.calls.append((url, json, timeout))
        if self.boom:
            raise TimeoutError("느림")
        return FakeResp(self.body)


def good_form(**kw):
    f = {"절 이름": "시험사", "주소": "어딘가 1", "담당자 이름": "홍길동",
         "연락처": "010-1234-5678", "요청 내용": "", "동의": True,
         "자가진단 요약": ""}
    f.update(kw)
    return f


def _screen_tests():
    """AppTest 로 화면을 돌립니다. 검색 모듈은 가짜로 바꿔 끼웁니다."""
    import logging
    import bldrgst
    import juso
    import kakao
    import keys
    from streamlit.testing.v1 import AppTest
    logging.getLogger("streamlit").setLevel(logging.ERROR)

    def fake_rows(n, mountain=False):
        return [juso.Juso(jibunAddr=f"어느군 어느면 어느리 {i + 1}", admCd="1111010100",
                          lnbrMnnm=str(i + 1), mtYn="1" if mountain else "0",
                          bdNm="시험사") for i in range(n)]

    calls = []

    def fake_search(kw, key, page=1, per_page=5, **_k):
        calls.append((kw, page))
        n = 12 if "많이" in kw else 1
        rows = fake_rows(n)[(page - 1) * per_page: page * per_page]
        return rows, n

    saved = (keys.load, keys.kakao, juso.search, kakao.search, bldrgst.fetch_dongs)
    map_calls = []
    keys.load = lambda *a, **k: ("가짜승인키", "가짜인증키")
    juso.search = fake_search
    kakao.search = lambda kw, key, *a, **k: (map_calls.append(kw) or
                                             [kakao.Place(name="시험사", jibun="어느군 1")], 1)
    bldrgst.fetch_dongs = lambda *a, **k: []
    app = os.path.join(HERE, "public_app.py")
    try:
        def run(kw, kakao_key=""):
            keys.kakao = lambda *a, **k: kakao_key
            at = AppTest.from_file(app, default_timeout=60).run()
            at.session_state["nav"] = "자가진단"
            at.run()
            at.text_input[0].set_value(kw)
            at.button(key="FormSubmitter:search-찾기").click()
            return at.run()

        at = run("시험사")
        ok("카카오 키 없음 -> 지도 칸 숨김", not map_calls and
           not [r for r in at.radio if r.label == "지도 결과"])
        at = run("시험사", "가짜카카오키")
        ok("카카오 키 있고 이름 검색 -> 지도 결과를 먼저",
           map_calls == ["시험사"] and [r for r in at.radio if r.label == "지도 결과"])
        map_calls.clear()
        at = run("어느리 314", "가짜카카오키")
        ok("번지가 든 주소는 지도를 부르지 않음", not map_calls)

        at = run("많이 나오는 절")
        labels = [b.label for b in at.button]
        ok("결과 6건 이상 -> 「더 보기」", "더 보기" in labels)
        at.button(key="pg_next").click()
        at.run()
        ok("더 보기 -> 2쪽을 부름", calls[-1] == ("많이 나오는 절", 2))
        ok("산 지번 단추", "산 지번만 찾기" in [b.label for b in at.button])
        at.button(key="mt_go").click()
        at.run()
        ok("산 지번만 찾기 -> 검색어 끝에 「산」", calls[-1] == ("많이 나오는 절 산", 1))
        at = run("시험사")
        ok("결과 5건 이하 -> 더 보기 없음", "더 보기" not in [b.label for b in at.button])
        ok("지번 직접 넣기 칸이 있음 (접어 둠)",
           any("지번을 직접 넣기" in e.label for e in at.expander))
        ok("화면 오류 없음", not at.exception)
    finally:
        keys.load, keys.kakao, juso.search, kakao.search, bldrgst.fetch_dongs = saved


def main() -> int:
    print()
    print(LINE)
    print("  공개 홈페이지 확인 (작업지시 10)")
    print(LINE)

    print("\n[1] 유형 판정표")
    ok("등유·LPG·화목 + 전기난방 아님 -> 연료 난방형",
       sc.classify([sc.HEAT_KERO, sc.HEAT_GAS], 5000, HIGH) == sc.TYPE_FUEL)
    ok("전기판넬 고름 -> 전기 난방형 (등유를 함께 골라도)",
       sc.classify([sc.HEAT_ELEC, sc.HEAT_KERO]) == sc.TYPE_ELEC)
    ok("도시가스 고름 -> 도시가스 난방형", sc.classify([sc.HEAT_GAS]) == sc.TYPE_GAS)
    ok("아무것도 안 골랐어도 도시가스 > 0 -> 도시가스 난방형",
       sc.classify([], 1200.0, HIGH) == sc.TYPE_GAS)
    ok("12달 · 계절비 3.0 -> 전기 난방형 (자료로 추정)",
       sc.classify([sc.HEAT_UNKNOWN], 0, HIGH) == sc.TYPE_ELEC_EST)
    ok("12달 · 계절비 2.0 -> 연료 난방 추정형",
       sc.classify([], 0, LOW) == sc.TYPE_FUEL_EST)
    ok("그 밖 -> 판정 보류", sc.classify([], 0, None) == sc.TYPE_HOLD)
    ok("화목만 -> 연료 난방형", sc.classify([sc.HEAT_WOOD]) == sc.TYPE_FUEL)

    print("\n[2] 계절비")
    ok("겨울 최대 / 여름 최소 = 3.0", abs(sc.season_ratio(HIGH) - 3.0) < 1e-9)
    holed = dict(HIGH)
    holed["202507"] = 0
    ok("12달 중 0 이 있으면 None", sc.season_ratio(holed) is None)
    ok("11달뿐이면 None", sc.season_ratio({k: v for k, v in HIGH.items()
                                           if k != "202503"}) is None)
    ok("월만 적힌 열쇠('01')도 읽음",
       abs(sc.season_ratio({k[4:]: v for k, v in HIGH.items()}) - 3.0) < 1e-9)
    ok("화면 문구", sc.ratio_text(3.0) == "겨울 전기가 여름의 3.0배")
    ok("12달이 안 되면 계절비로 추정하지 않음 -> 판정 보류",
       sc.classify([], 0, holed) == sc.TYPE_HOLD)

    print("\n[3] 연료 환산 · 배출량")
    ok("등유 2드럼 -> 400 L", sc.kerosene_l(2) == 400)
    ok("LPG 20kg 3통 + 50kg 1통 -> 110 kg", sc.lpg_kg(3, 1) == 110)
    ok("비워 두면 0", sc.kerosene_l(None) == 0 and sc.lpg_kg(None, None) == 0)
    r = sc.diagnose("시험사", "어딘가 1", 2025, sc.MODE_LOOKUP, 200000, 50000,
                    [sc.HEAT_KERO, sc.HEAT_LPG, sc.HEAT_WOOD], 2, 3, 1, HIGH)
    want = (em.power_t(200000) + em.gas_t(50000)
            + em.burn("등유(Kerosene)", 400).ar5_t
            + em.burn("LPG-프로판(LPG1호)", 110).ar5_t)
    ok("배출량 = 전기 발전단 + 도시가스 + emissions.burn(등유·LPG)",
       abs(r.total_t - want) < 1e-9, f"{r.total_t} != {want}")
    ok("등유 400 L 은 emissions.burn 과 같음",
       abs(r.kero_t - em.burn("등유(Kerosene)", 400).ar5_t) < 1e-12)
    ok("LPG 는 프로판 표", abs(r.lpg_t - em.burn("LPG-프로판(LPG1호)", 110).ar5_t) < 1e-12)
    ok("전기는 발전단 0.3844", abs(r.elec_t - 200000 * 0.3844 / 1000) < 1e-9)
    ok("국민 환산 = 배출량 / 13.1", abs(r.people - r.total_t / em.KOR_PER_CAPITA) < 1e-9)
    ok("태양광 = 전기 / 365 / 3.5", abs(r.solar_kw - 200000 / 365 / 3.5) < 1e-9)
    ok("화목은 합계에 안 넣고 한계에 밝힘", r.wood and sc.WOOD_TEXT in r.notes)
    ok("먼저 해 볼 일 세 가지, 1번은 계약전력",
       len(r.todo) == 3 and "계약전력" in r.todo[0])
    ok("한계 문구 고정", sc.LIMIT_TEXT in r.notes)
    r2 = sc.diagnose("시험사", "", None, sc.MODE_BILL, 10000, 0, [sc.HEAT_KERO])
    ok("등유를 골랐는데 양이 없으면 그렇다고 밝힘",
       any("양을 넣지 않은" in n for r_ in [r2] for n in r_.notes))

    print("\n[4] 자가진단 기록 (구글 시트)")
    d = sc.diag_payload(r, "abc1234")
    ok("열쇠가 sheet.DIAG_COLS 와 같음", tuple(d) == sheet.DIAG_COLS)
    banned = ("담당자", "연락처", "이름", "전화", "이메일")
    leaked = [k for k in d if any(b in k for b in banned) and k != "절 이름"]
    ok("이름·연락처 열쇠가 없음", not leaked, str(leaked))
    gs = os.path.join(HERE, "apps_script_지수광풍.gs")
    if not os.path.exists(gs):
        gs = os.path.join(HERE, "..", "..", "..", "apps_script_지수광풍.gs")
    if os.path.exists(gs):
        src = io.open(gs, encoding="utf-8").read()

        def cols(name):
            m = re.search(name + r"\s*=\s*\[(.*?)\];", src, re.S)
            return tuple(re.findall(r"'([^']*)'", m.group(1))) if m else ()
        ok(".gs DIAG_COLS 와 글자까지 같음 (받은시각 빼고)",
           cols("DIAG_COLS")[1:] == sheet.DIAG_COLS)
        ok(".gs REQ_COLS 와 글자까지 같음 (받은시각·처리 상태 빼고)",
           cols("REQ_COLS")[1:-1] == sheet.REQ_COLS)
    else:
        print("  [건너뜀]  .gs 파일이 옆에 없어 열 이름 대조는 못 했습니다")
    fp = FakePost()
    ok("보낼 곳이 비어 있으면 보내지 않음(None)",
       sheet.post("", "t", sheet.KIND_DIAG, d, http=fp) is None and not fp.calls)
    ok("보내는 모양 {token, kind, data}",
       sheet.post("https://x", "t", "diag", d, http=fp) is True
       and fp.calls[-1][1] == {"token": "t", "kind": "diag", "data": d})
    ok("자가진단 기록 시간 제한 10초", fp.calls[-1][2] == 10)
    ok("느려서 터져도 예외 없이 False",
       sheet.post("https://x", "t", "diag", d, http=FakePost(boom=True)) is False)
    ok("서버가 ok:false 면 False",
       sheet.post("https://x", "t", "diag", d, http=FakePost({"ok": False})) is False)

    print("\n[5] 컨설팅 요청")
    fp = FakePost()
    ok("정상 -> 보냄", sheet.send_request(good_form(), "", "https://x", "t", fp) == "sent")
    sent = fp.calls[-1][1]
    ok("request 로 보냄 · 동의 true", sent["kind"] == "request"
       and sent["data"]["동의"] is True)
    ok("열쇠가 REQ_COLS 뿐", tuple(sent["data"]) == sheet.REQ_COLS)
    fp = FakePost()
    ok("동의가 없으면 보내지 않음",
       sheet.send_request(good_form(동의=False), "", "https://x", "t", fp) == "invalid"
       and not fp.calls)
    ok("숨은 칸에 값이 있으면 보내지 않음",
       sheet.send_request(good_form(), "http://spam", "https://x", "t", fp) == "blocked"
       and not fp.calls)
    ok("실패 -> failed",
       sheet.send_request(good_form(), "", "https://x", "t", FakePost(boom=True)) == "failed")
    for v, want in [("010-1234-5678", True), ("0212345678", True),
                    ("02-123-4567", True), ("1234", False), ("12-34", False),
                    ("abc@def.kr", True), ("abc@def", False), ("전화주세요", False)]:
        ok(f"연락처 {v!r} -> {'맞음' if want else '틀림'}", sheet.contact_ok(v) == want)
    ok("요청 내용 1,000자 넘으면 막음",
       sheet.check_request(good_form(**{"요청 내용": "가" * 1001})) != [])
    ok("담당자 이름이 비면 막음", sheet.check_request(good_form(**{"담당자 이름": " "})) != [])

    print("\n[5-1] 요청 실패 이유 (작업지시 11 ①)")
    import requests

    class Boom:
        def __init__(self, exc):
            self.exc, self.calls = exc, []

        def __call__(self, url, json=None, timeout=None):
            self.calls.append(timeout)
            raise self.exc

    b = Boom(requests.Timeout("느림"))
    st_, code = sheet.send_request_detail(good_form(), "", "https://x", "t", b)
    ok("Timeout -> failed · 코드 timeout", (st_, code) == ("failed", "timeout"))
    ok("요청 시간 제한 20초", b.calls == [20])
    ok("ConnectionError -> connection",
       sheet.post_detail("https://x", "t", "diag", {},
                         http=Boom(requests.ConnectionError()))[1] == "connection")
    # requests 가 302 를 따라간 뒤 받은 JSON 은 성공으로 읽어야 합니다
    ok("302 를 따라간 뒤 JSON ok -> sent",
       sheet.send_request_detail(good_form(), "", "https://x", "t",
                                 FakePost({"ok": True}))[0] == "sent")
    ok("302 가 그대로 남으면 http_302",
       sheet.post_detail("https://x", "t", "diag", {},
                         http=lambda *a, **k: FakeResp({}, 302))[1] == "http_302")
    st_, code = sheet.send_request_detail(good_form(), "", "https://x", "t",
                                          FakePost({"ok": False, "err": "token"}))
    ok("err=token -> 코드 token", (st_, code) == ("failed", "token"))
    ok("오류 코드에 이름·연락처가 안 섞임", "홍길동" not in code and "010" not in code)

    class Html(FakeResp):
        def json(self):
            raise ValueError("html")
    ok("JSON 아님 -> not_json",
       sheet.post_detail("https://x", "t", "diag", {},
                         http=lambda *a, **k: Html(None))[1] == "not_json")
    fp = FakePost({"ok": False, "err": "kind"})
    pg = sheet.ping("https://x", "t", fp)
    ok("ping 미설치(err=kind) -> 연결됨(ping 미설치)",
       pg["verdict"] == "연결됨(ping 미설치)")
    ok("ping 은 kind=ping · 빈 data",
       fp.calls[-1][1]["kind"] == "ping" and fp.calls[-1][1]["data"] == {})
    ok("ping 성공 -> 연결됨", sheet.ping("https://x", "t", FakePost())["verdict"] == "연결됨")
    ok("ping 토큰 틀림 -> 코드 token",
       sheet.ping("https://x", "t", FakePost({"ok": False, "err": "token"}))["code"] == "token")
    ok("주소가 비면 ping 은 보내지 않음", sheet.ping("", "t")["code"] == "off")

    print("\n[6] 소개글 설정 칸")
    body, st_ = content.parse(io.open(content.INTRO, encoding="utf-8").read())
    ok("본문을 읽음 · 사이트 이름 제목은 뺌",
       "지수광풍이 하는 일" in body and not body.startswith("# 불교탄소중립실천단"))
    ok("설정 칸은 본문에 안 섞임", "인사말_본문" not in body and "<!--" not in body)
    ok("인사말 본문이 비면 숨김", content.greeting(st_) is None)
    ok("전화가 비면 문의 줄 숨김", content.contact_line(st_) == "")
    filled = "본문\n\n---\n<!-- 설명: 값 -->\n인사말_본문: 반갑습니다\n문의_기관: 불교환경연대 사무실\n문의_전화: 02-000-0000\n"
    _b, s2 = content.parse(filled)
    g = content.greeting(s2)
    ok("인사말 본문이 있으면 표시 (제목은 기본값)",
       g is not None and g[0] == "단장 인사말" and g[1] == "반갑습니다")
    ok("전화가 있으면 「문의: … ☎ …」",
       content.contact_line(s2) == "문의: 불교환경연대 사무실 ☎ 02-000-0000")
    ok("주석 안의 「:」 는 설정으로 안 읽음", "설명" not in s2)

    print("\n[7] 결과 PDF")
    pdf = report_pdf.build(r, "문의: 불교환경연대 사무실 ☎ 02-000-0000")
    ok("PDF 가 만들어짐", pdf[:5] == b"%PDF-")
    ok("A4 한 장", pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page>") <= 1
       and b"/Count 1" in pdf)
    import datetime as dt
    ok("파일 이름 양식",
       report_pdf.file_name("수국사", dt.date(2026, 10, 30))
       == "지수광풍_자가진단_수국사_20261030.pdf")
    rb = sc.diagnose("고지서사", "", None, sc.MODE_BILL, 5000)
    ok("월별 없이도 만들어짐", report_pdf.build(rb)[:5] == b"%PDF-")

    print("\n[8] 절이 맞는지 (작업지시 11 ②)")
    ok("종교시설 -> 안내 없음", not sc.not_temple(["종교시설", "단독주택"]))
    ok("작은 절(근린생활·주택만) -> 안내 없음",
       not sc.not_temple(["제2종근린생활시설", "단독주택"]))
    ok("업무시설 -> 안내", sc.not_temple(["업무시설"]))
    ok("교육연구시설(학교) -> 안내", sc.not_temple(["교육연구시설"]))
    ok("종교시설이 있어도 숙박시설이 섞이면 안내", sc.not_temple(["종교시설", "숙박시설"]))
    ok("건물이 없으면 이 안내는 안 띄움", not sc.not_temple([]))

    print("\n[9] 주소 찾기 화면 (가짜 검색, 인터넷 안 씀)")
    _screen_tests()

    print()
    print(LINE)
    if _fail:
        print(f"  {_count}개 중 {_fail}개 실패.")
    else:
        print(f"  {_count}개 모두 통과했습니다.")
    print(LINE)
    print()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
