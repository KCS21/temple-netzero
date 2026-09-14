# -*- coding: utf-8 -*-
"""
건축HUB 건물에너지정보 서비스 클라이언트
사찰 넷제로 진단 도구 — 불교탄소중립실천단 지수화풍

공공데이터포털 15135963 / BldEngyHubService
  getBeElctyUsgInfo  지번별 전기사용량 조회
  getBeGasUsgInfo    지번별 가스사용량 조회

사용년월이 필수라 한 달씩 부릅니다. 1년치는 전기 12회 + 가스 12회입니다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import portal
from portal import PortalError as EnergyError  # noqa: F401

BASE = "https://apis.data.go.kr/1613000/BldEngyHubService"
OP_ELEC = "getBeElctyUsgInfo"
OP_GAS = "getBeGasUsgInfo"


@dataclass
class MonthUse:
    useYm: str
    useQty: float
    platPlc: str = ""
    platGbCd: str = "0"
    raw: dict = field(default_factory=dict, repr=False)


def _rows(op: str, params: dict, service_key: str, timeout: int, retries: int):
    body = portal.check(portal.request(BASE, op, params, service_key, timeout, retries))
    out = []
    for it in portal.items(body):
        out.append(
            MonthUse(
                useYm=str(it.get("useYm", "")).strip(),
                useQty=portal.num(it.get("useQty")),
                platPlc=it.get("platPlc", ""),
                platGbCd=str(it.get("platGbCd", "0")).strip(),
                raw=it,
            )
        )
    return out


def fetch_month(
    kind: str,
    sigunguCd: str,
    bjdongCd: str,
    bun: str,
    ji: str,
    useYm: str,
    service_key: str,
    plat_gb: Optional[str] = None,
    timeout: int = 15,
    retries: int = 2,
) -> Tuple[float, int]:
    """한 달치 사용량(kWh). 자료가 없으면 0.0을 돌려줍니다.

    plat_gb 를 주면 응답에서 그 대지구분(0=대지, 1=산)만 골라 씁니다.
    요청 파라미터에는 대지구분이 없어서 응답에서 걸러야 합니다.

    같은 번지에 대지와 산이 겹칠 수 있습니다(162 와 산162 는 둘 다 bun=0162).
    응답이 대지구분을 밝혔는데 맞는 것이 하나도 없으면 **남의 건물**이므로
    0.0 을 돌려줍니다. 없는 것을 없다고 해야 방문 안내로 이어집니다.
    응답이 대지구분을 아예 안 밝힌 경우에만 거르지 않고 전부 씁니다.
    """
    op = OP_ELEC if kind == "elec" else OP_GAS
    params = {
        "sigunguCd": sigunguCd,
        "bjdongCd": bjdongCd,
        "bun": str(bun).zfill(4),
        "ji": str(ji).zfill(4),
        "useYm": useYm,
        "numOfRows": "100",
        "pageNo": "1",
    }
    rows = _rows(op, params, service_key, timeout, retries)
    dropped = 0
    if plat_gb is not None:
        tagged = [r for r in rows if str(r.raw.get("platGbCd", "")).strip() != ""]
        if tagged:
            keep = [r for r in tagged if r.platGbCd == str(plat_gb)]
            dropped = len(tagged) - len(keep)
            rows = keep
        # 응답이 대지구분을 아예 안 밝혔으면 거를 수가 없으므로 손대지 않습니다.
    return sum(r.useQty for r in rows), dropped


def fetch_year(
    sigunguCd: str,
    bjdongCd: str,
    bun: str,
    ji: str,
    year: int,
    service_key: str,
    plat_gb: Optional[str] = None,
    progress: Optional[Callable[[int, int, str], None]] = None,
    pause: float = 0.12,
    timeout: int = 15,
    retries: int = 2,
    deadline: Optional[float] = None,
) -> Dict[str, Dict[str, float]]:
    """1년치 전기·가스 사용량.

    {'elec': {'202501': 1234.0, ...}, 'gas': {...}, 'dropped': 3}
    dropped 는 대지구분이 달라 제외한 자료 건수입니다.

    deadline 은 time.time() 기준 마감 시각입니다. 제공기관 서버가 아플 때
    24회 x 재시도 x 타임아웃이 겹쳐 **한 곳에 34분**을 쓴 일이 있습니다.
    일괄 조회에서는 상한을 두고 넘기는 편이 낫습니다.
    """
    months = [f"{year}{m:02d}" for m in range(1, 13)]
    out: Dict[str, Dict[str, float]] = {"elec": {}, "gas": {}}
    dropped = 0

    total = len(months) * 2
    done = 0
    for kind in ("elec", "gas"):
        for ym in months:
            if deadline and time.time() > deadline:
                raise portal.PortalError(
                    "제공기관 서버가 느려 이 사찰은 건너뜁니다. "
                    "나중에 [실패한 곳만 다시] 로 다시 해보세요."
                )
            qty, drop = fetch_month(
                kind, sigunguCd, bjdongCd, bun, ji, ym, service_key, plat_gb,
                timeout=timeout, retries=retries,
            )
            out[kind][ym] = qty
            dropped += drop
            done += 1
            if progress:
                progress(done, total, f"{'전기' if kind == 'elec' else '가스'} {ym}")
            time.sleep(pause)     # 초당 30건 제한을 넉넉히 지킵니다.

    # 걸러냈다는 사실 자체가 단서입니다. 같은 번지에 다른 건물이 있다는 뜻이고,
    # 사찰 전기가 그쪽에 물려 있을 수 있습니다. 숨기지 않고 화면에 드러냅니다.
    out["dropped"] = dropped
    return out


def summarize(series: Dict[str, float]) -> dict:
    """월별 사용량에서 연간 합계와 난방 부담 지표를 뽑습니다."""
    vals = {k: v for k, v in series.items() if v and v > 0}
    if not vals:
        return {"total": 0.0, "months": 0, "max_ym": None, "min_ym": None, "ratio": None}

    max_ym = max(vals, key=vals.get)
    min_ym = min(vals, key=vals.get)
    return {
        "total": sum(vals.values()),
        "months": len(vals),
        "max_ym": max_ym,
        "max": vals[max_ym],
        "min_ym": min_ym,
        "min": vals[min_ym],
        "ratio": vals[max_ym] / vals[min_ym] if vals[min_ym] else None,
    }
