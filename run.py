# -*- coding: utf-8 -*-
"""
더블클릭 실행용 시작 프로그램
사찰 넷제로 진단 도구 - 불교탄소중립실천단 지수광풍

배치 파일(키확인.bat, 화면열기.bat, 수집_돌리기.bat)이 이 파일을 부릅니다.
한글 안내는 전부 여기서 처리합니다. 배치 파일에 한글을 넣으면
윈도우 명령창이 파일을 잘못 읽어 깨지기 때문입니다.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BAR = "=" * 52


def need(mod: str) -> bool:
    """필요한 프로그램이 깔려 있는지 확인하고, 없으면 설치법을 알려줍니다."""
    try:
        __import__(mod)
        return True
    except ImportError:
        print()
        print(f"  '{mod}' 이(가) 설치되어 있지 않습니다.")
        print()
        print("  아래 한 줄을 명령창에 넣어 설치하세요.")
        print(f'  "{sys.executable}" -m pip install {mod}')
        print()
        return False


def check() -> int:
    print(BAR)
    print("  사찰 넷제로 진단 - 인증키 확인")
    print(BAR)
    print()
    print(f"  파이썬: {sys.version.split()[0]}")
    print()

    if not need("requests"):
        return 1

    print("  주소를 넣고 엔터를 누르세요.")
    print("  그냥 엔터만 누르면 기본 주소(구산동 314)로 합니다.")
    print()
    print("  예)  산내면 입석리      <- 산 지번 확인용")
    print("       금산면 금산리 39")
    print("       삼성동 73")
    print()

    try:
        addr = input("  주소: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1
    if not addr:
        addr = "구산동 314"

    print()
    return subprocess.call([sys.executable, os.path.join(HERE, "test_key.py"), addr])


def app() -> int:
    print(BAR)
    print("  사찰 넷제로 진단 - 화면 열기")
    print(BAR)
    print()
    print(f"  파이썬: {sys.version.split()[0]}")
    print()

    for mod in ("requests", "streamlit"):
        if not need(mod):
            return 1

    print("  잠시 뒤 인터넷 창이 저절로 열립니다.")
    print("  안 열리면 아래 주소를 복사해 붙여넣으세요.")
    print("      http://localhost:8501")
    print()
    print("  끝내실 때는 이 검은 창에서 Ctrl 키를 누른 채 C 를 누르세요.")
    print()

    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", os.path.join(HERE, "app.py")]
    )


def collect(extra=()) -> int:
    """수집_돌리기.bat - 지원사업·법령 자동 수집. 앱과는 따로 돕니다.

    뒤에 붙인 말은 그대로 넘깁니다 - `python run.py collect --다시쓰기`
    는 인터넷 없이 기준선으로 보고서만 다시 씁니다.
    """
    script = os.path.join(HERE, "scripts", "지원사업_수집.py")
    if "--다시쓰기" in extra:
        print("  기준선으로 보고서만 다시 씁니다(인터넷 안 씀).")
        return subprocess.call([sys.executable, script] + list(extra))
    print(BAR)
    print("  지원사업·법령 자동 수집")
    print(BAR)
    print()
    print(f"  파이썬: {sys.version.split()[0]}")
    print()
    if not need("requests"):
        return 1
    try:
        __import__("pypdf")
    except ImportError:
        print("  [알림] PDF 첨부를 읽을 'pypdf' 가 없습니다. PDF 는 건너뛰고")
        print("         보고서의 「자동으로 못 잡은 것」에 적습니다. 설치하시려면")
        print(f'         "{sys.executable}" -m pip install pypdf')
        print()
    print("  다섯 곳을 차례로 훑습니다. 2~3분 걸립니다.")
    print("  (사이트에 무리가 가지 않게 요청 사이를 1초씩 쉽니다)")
    print()
    code = subprocess.call([sys.executable, script] + list(extra))
    print()
    if code == 0:
        print("  data\\수집 폴더의 「수집보고_날짜.md」를 열어 보십시오.")
        print("  지원사업.csv 와 지원사업 문서는 고치지 않았습니다(후보만 적음).")
    return code


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        code = (app() if what == "app" else
                collect(sys.argv[2:]) if what == "collect" else check())
    except KeyboardInterrupt:
        code = 0
    raise SystemExit(code)
