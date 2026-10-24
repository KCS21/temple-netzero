# -*- coding: utf-8 -*-
"""
사찰 넷제로 진단 도구 — 개략 진단
불교탄소중립실천단 지수광풍

실행:  streamlit run app.py
"""
import datetime as dt
import io
import os
import tempfile
import time

_NL = chr(10)

import streamlit as st

import bldengy
import bldrgst
import emissions as em
import juso
import keys
import batch
import portal
import region
import store
import template_out as tpl

# 인증키는 같은 폴더의 키.txt 에서 읽습니다. 코드에 키를 넣지 마십시오.

PER_PAGE = 5

st.set_page_config(page_title="사찰 넷제로 진단", page_icon="🪷", layout="centered")
st.markdown("""
<style>
  html, body, [class*="css"] { font-size: 18px; }
  .stButton > button { font-size: 20px; font-weight: 700;
      padding: 0.7rem 1.6rem; border-radius: 10px; }
  .stTextInput input { font-size: 20px; padding: 0.7rem; }
  div[role="radiogroup"] label { font-size: 19px; padding: 6px 0; }
  .hint { color: #6b6a64; font-size: 16px; }
</style>""", unsafe_allow_html=True)

def _share_mode() -> bool:
    """의견을 받으려고 남에게 보여주는 판인가.

    남들이 보는 판에서는 1~4단계(주소 -> 엑셀)만 보입니다. 사찰 기록·일괄
    조회·방문 우선순위는 감춥니다. 까닭 둘.

    1. 조사한 사찰 목록은 모임 안의 자료입니다. 남에게 보일 것이 아닙니다
    2. 웹에 올리면 여러 사람이 같은 파일에 쓰게 되어 서로의 기록이 섞이고,
       서버가 다시 뜨면 사라집니다. 기록은 교수님 컴퓨터에서만 쌓습니다
    """
    if os.environ.get("JISU_SHARE", "").strip():
        return True
    try:
        return bool(st.secrets.get("share_mode", False))
    except Exception:
        return False


SHARE = _share_mode()

try:
    CONFM_KEY, SERVICE_KEY = keys.load()
except keys.KeyError_ as e:
    st.title("사찰 넷제로 진단")
    st.error(str(e))
    st.stop()

for k, v in [("rows", []), ("total", 0), ("page", 1), ("kw", ""),
             ("picked", None), ("error", None), ("bld", None), ("diag", None),
             ("xlsx", None)]:
    st.session_state.setdefault(k, v)


# ═══════════ 1단계 — 주소 찾기 ═══════════
st.title("사찰 주소 찾기")
st.markdown('<p class="hint"><b>주소 또는 절 이름</b>을 넣어 주세요. '
            "예: 구산동 314 · 봉은사<br>"
            "절 이름으로 찾은 것에는 <b>(이름으로 찾음)</b> 표시가 붙습니다. "
            "<b>주소가 맞는지 꼭 확인해 주세요.</b> 같은 이름의 다른 절이 흔합니다."
            "</p>", unsafe_allow_html=True)


def run_search(keyword, page):
    try:
        rows, total = juso.search(keyword, CONFM_KEY, page=page, per_page=PER_PAGE)
    except juso.JusoError as e:
        st.session_state.update(rows=[], total=0, error=str(e), searched=True)
        return
    st.session_state.update(rows=rows, total=total, page=page, kw=keyword,
                            picked=None, error=None, bld=None, diag=None,
                            searched=True)


with st.form("search"):
    c1, c2 = st.columns([4, 1])
    keyword = c1.text_input("주소", value=st.session_state.kw,
                            placeholder="예: 구산동 314  또는  봉은사",
                            label_visibility="collapsed")
    submitted = c2.form_submit_button("찾기", width="stretch")

if submitted:
    run_search(keyword, 1)
if st.session_state.error:
    st.error(st.session_state.error)
    # 0건일 때도 「없다」가 아니라 「이름이 등록 안 됐다」일 수 있습니다.
    # 원오사(계룡)가 그랬습니다.
    if st.session_state.get("searched"):
        st.warning(
            "**절 이름으로 찾으셨다면, 이름이 등록되지 않은 절은 "
            "여기 나오지 않습니다.**"
            + _NL + _NL +
            "지도 앱에서 주소를 확인해 **주소로** 찾아 주세요."
        )

rows = st.session_state.rows
if rows:
    total, page = st.session_state.total, st.session_state.page
    last = (total + PER_PAGE - 1) // PER_PAGE
    # 「1건」이 「유일」로 읽히면 안 됩니다. 도로명주소 검색은 **건물 이름이
    # 등록된 절만** 찾습니다. 원오사(계룡)는 이름이 등록되지 않아 부산 것 한 건만
    # 나왔고, 교수님이 지도 앱으로 직접 찾아야 했습니다.
    _by_name = any(r.name_hit for r in rows)
    if _by_name:
        st.markdown(f"**건물 이름이 등록된 {total}곳**을 찾았습니다. 아래에서 고르세요.")
        st.warning(
            "**이름이 등록되지 않은 같은 이름의 절은 여기 나오지 않습니다.**"
            + _NL + _NL +
            "찾는 절이 아니면 지도 앱에서 주소를 확인해 **주소로** 찾아 주세요."
        )
    else:
        st.markdown(f"**{total}건**을 찾았습니다. 아래에서 고르세요.")
    choice = st.radio("주소 선택", options=list(range(len(rows))),
                      format_func=lambda i: rows[i].label(),
                      index=None, label_visibility="collapsed")
    if choice is not None and st.session_state.picked is not rows[choice]:
        st.session_state.update(picked=rows[choice], bld=None, diag=None)

    # 산중 사찰은 산 지번이 뒤쪽 쪽수에 묻혀 있는 일이 많습니다.
    # 검색어 끝에 "산"을 붙이면 산 지번만 올라옵니다.
    kw_now = (st.session_state.kw or "").rstrip()
    if not any(r.is_mountain for r in rows) and not kw_now.endswith("산"):
        st.markdown('<p class="hint">산중 사찰인데 목록에 <b>(산)</b> 표시가 없으면, '
                    "아래 단추를 눌러 보세요.</p>", unsafe_allow_html=True)
        if st.button("산 지번만 찾기", width="stretch"):
            run_search(kw_now + " 산", 1); st.rerun()
    if last > 1:
        a, b, c = st.columns([1, 2, 1])
        if page > 1 and a.button("← 앞으로", width="stretch"):
            run_search(st.session_state.kw, page - 1); st.rerun()
        b.markdown(f"<p style='text-align:center;padding-top:0.8rem'>{page} / {last} 쪽</p>",
                   unsafe_allow_html=True)
        if page < last and c.button("더 보기 →", width="stretch"):
            run_search(st.session_state.kw, page + 1); st.rerun()
elif submitted and not st.session_state.error:
    st.warning("찾으시는 주소가 없습니다. 동 이름만 넣고 다시 해보세요. 예: 은평구 구산동")


# ═══════════ 2단계 — 건물 정보 ═══════════
picked = st.session_state.picked
if picked:
    st.divider()
    st.subheader(picked.jibunAddr + ("  ·  산 지번" if picked.is_mountain else ""))
    st.markdown(f'<p class="hint">도로명 {picked.roadAddr}</p>', unsafe_allow_html=True)
    if picked.name_hit:
        st.warning("""**절 이름으로 찾은 주소입니다.** 같은 이름의 다른 절일 수 있으니 위 주소가 맞는지 확인해 주세요.

명단이나 고지서에 주소가 있으면 그 주소로 찾으시는 편이 확실합니다.""")
    for w in picked.check():
        st.warning(w)

    p = picked.building_params()
    if st.session_state.bld is None:
        with st.spinner("건축물대장을 가져오는 중입니다"):
            try:
                dongs = bldrgst.fetch_dongs(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                            p["ji"], SERVICE_KEY, p["platGbCd"])
                recap = bldrgst.fetch_recap(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                            p["ji"], SERVICE_KEY, p["platGbCd"])
                jjg = bldrgst.fetch_jijigu(p["sigunguCd"], p["bjdongCd"], p["bun"],
                                           p["ji"], SERVICE_KEY, p["platGbCd"])
                st.session_state.bld = (dongs, recap, jjg)
            except portal.PortalError as e:
                st.error(str(e)); st.stop()

    dongs, recap, jjg = st.session_state.bld
    if not dongs:
        st.warning("건축물대장에 등록된 건물이 없습니다. 미등재 전각일 수 있으니 방문해서 확인해야 합니다.")
    else:
        s = bldrgst.summarize(dongs)
        zones = bldrgst.restricted(jjg)
        st.markdown("#### 건물 정보")
        c1, c2, c3 = st.columns(3)
        c1.metric("동 수", f"{s['count']}동")
        c2.metric("연면적", f"{s['total_area']:,.0f} m²")
        c3.metric("대지면적", f"{recap['platArea']:,.0f} m²" if recap else "—")

        st.table({
            "동": [d.name(i) for i, d in enumerate(dongs, 1)],
            "연면적": [f"{d.totArea:,.1f} m²" for d in dongs],
            "주용도": [d.mainPurpsCdNm or "-" for d in dongs],
            "구조": [d.strctCdNm or "-" for d in dongs],
            "지붕": [d.roofCdNm or "-" for d in dongs],
            "구분": [d.kind for d in dongs],
            "태양광": [bldrgst.solar_label(d, bool(zones)) for d in dongs],
        })
        bits = [f'전통 {s["trad_count"]}동 {s["trad_area"]:,.0f} m²']
        if s["check_count"]:
            bits.append(f'확인 필요 {s["check_count"]}동 {s["check_area"]:,.0f} m²')
        bits.append(f'신식 {s["modern_count"]}동 {s["modern_area"]:,.0f} m²')
        if s["parking_area"]:
            bits.append(f'옥내 주차장 {s["parking_area"]:,.0f} m²')
        if recap and recap["totPkngCnt"]:
            bits.append(f'주차 {recap["totPkngCnt"]}대')
        st.markdown('<p class="hint">' + " · ".join(bits) + "</p>",
                    unsafe_allow_html=True)

        # 참고 정보는 파란색, 손봐야 할 것은 노란색으로 나눕니다.
        # 둘 다 노란색이면 모든 상자가 문제로 읽힙니다.
        if s["trad_count"]:
            st.info("목조 전각은 태양광 설치 대상에서 빠집니다. 구조와 지붕은 "
                    "건축물대장 기준이므로 현장에서 확인해 주세요.")
        if s["check_count"]:
            st.info(
                "**구조는 목재가 아닌데 지붕만 기와·초가인 동이 "
                f"{s['check_count']}동** 있습니다." "  지붕에 판을 올릴 수 "
                "있는 경우가 많아 「확인 필요」로 두었습니다. "
                "현장에서 보고 정해 주세요."
            )
        if s["parking_area"]:
            st.info(
                f"연면적에 **옥내 주차장 {s['parking_area']:,.0f} m²** 가 "
                "들어 있습니다. 면적당 에너지를 낼 때는 이것을 뺀 "
                f"**{s['area_excl_parking']:,.0f} m²** 로 나눕니다. "
                "통계의 원단위가 주차장을 뺀 연면적 기준이기 때문입니다."
            )

        for m in bldrgst.checks(dongs, recap):
            st.warning(m)
        if jjg:
            msg = "용도지역·구역: " + " / ".join(jjg)
            if zones:
                st.warning(
                    msg + "\n\n**" + " · ".join(zones) + "** 이 걸려 있어 태양광은 "
                    "「협의 필요」로 표시했습니다. **못 하는 것이 아니라 절차가 "
                    "있는 것**입니다. 규제 해당 여부는 관할 지자체 질의로만 "
                    "확정됩니다."
                )
            else:
                st.info(msg + "\n\n규제 해당 여부는 관할 지자체 질의로만 확정됩니다.")


# ═══════════ 3단계 — 개략 진단 ═══════════
if picked:
    st.divider()
    st.markdown("#### 에너지 진단")
    this_year = dt.date.today().year
    c1, c2 = st.columns(2)
    year = c1.selectbox("조회할 해", [this_year - 1, this_year - 2, this_year - 3])
    ttype = c2.selectbox("사찰 유형", ["도심", "산중"], index=1 if picked.is_mountain else 0)

    st.markdown('<p class="hint">전기와 가스는 <b>지번 한 곳</b>을 기준으로 찾습니다. '
                "전기요금은 전각마다 따로 나오지 않고 <b>특정 건물로 묶여</b> 나오기 때문에, "
                "사찰 전체가 이 지번 하나에 잡히지 않을 수 있습니다.<br>"
                "<b>고지서가 있으시면, 고지서에 적힌 주소로 찾으시는 편이 가장 정확합니다.</b>"
                "</p>", unsafe_allow_html=True)

    if st.button("자료 가져오기  (30초쯤 걸립니다)", width="stretch"):
        bar = st.progress(0.0, text="시작합니다")
        p = picked.building_params()
        try:
            data = bldengy.fetch_year(
                p["sigunguCd"], p["bjdongCd"], p["bun"], p["ji"], year, SERVICE_KEY,
                plat_gb=p["platGbCd"],
                progress=lambda d, t, lbl: bar.progress(d / t, text=f"{lbl} ({d}/{t})"))
        except portal.PortalError as e:
            bar.empty(); st.error(str(e)); st.stop()
        bar.empty()
        st.session_state.diag = (data, ttype, year)

    d = st.session_state.diag
    if d:
        data, ttype, year = d
        es, gs = bldengy.summarize(data["elec"]), bldengy.summarize(data["gas"])
        r = em.diagnose(es["total"], gs["total"], ttype)
        lvl, msg = em.confidence(es["total"], gs["total"])

        if es["total"] == 0 and gs["total"] == 0:
            st.error(f"""**{picked.jibunAddr}** 의 {year}년 자료가 없습니다.

이 지번에 없을 뿐, 전기가 **다른 지번으로 잡혀 있을 수 있습니다.**
고지서에 적힌 주소로 다시 찾아 보세요. 해를 바꿔 보셔도 됩니다.

그래도 없으면 공개자료가 없는 사찰입니다. 방문해서 고지서를 받아야 합니다.""")
        else:
            st.markdown(f"##### {year}년 개략 진단")
            k1, k2, k3 = st.columns(3)
            k1.metric("공개자료 배출량", f"{r.subtotal_t:,.1f} t")
            k2.metric("국민 환산", f"{r.people:,.1f}명분")
            k3.metric("태양광 필요용량", f"{r.solar_kw:,.0f} kW")
            st.caption("전기와 도시가스만 더한 값입니다. " + em.UNCOVERED_TEXT)

            st.info(f"이 값은 **{picked.jibunAddr}** 한 지번에 잡힌 것만 더한 것입니다. "
                    "사찰 전체가 아닐 수 있습니다. "
                    "고지서에 적힌 주소가 이와 다르면 그 주소로 다시 찾아 주세요.")

            dropped = data.get("dropped", 0)
            if dropped:
                st.warning(f"""같은 번지에서 대지구분이 다른 자료 **{dropped}건을 제외**했습니다.

이 사찰의 전기가 그쪽에 물려 있을 수 있습니다. 현장에서 고지서 주소를 확인해 주세요.""")

            # ── 면적당 에너지 — 그 지역 사찰 원단위와 견줍니다 ──
            #
            # 옛 방식(전기만 / 고정 200)은 폐기되었습니다. 통계의 원단위는
            # 전기+가스 합을 **주차장 뺀 연면적**으로 나눈 **중간값**입니다.
            bld = st.session_state.bld
            area = area_gross = 0.0
            use = em.AreaUse()
            if bld and bld[0]:
                ds0 = bldrgst.summarize(bld[0])
                area_gross = ds0["total_area"]
                area = ds0["area_excl_parking"]
                use = em.area_use(
                    es["total"], gs["total"], area,
                    region.of(picked.jibunAddr),
                    parking_area=ds0["parking_area"],
                    trad_count=ds0["trad_count"],
                )
            if use.area:
                reg = region.label(picked.jibunAddr)
                if use.suspect:
                    # 「높다」가 아니라 「못 믿는다」입니다. 배수를 내지 않습니다.
                    st.warning(
                        f"**배수를 내지 않았습니다 — {em.SUSPECT_NOTE}**"
                        + _NL + _NL +
                        f"전통 전각이 한 동도 없는데 면적당 에너지가 "
                        f"{use.per:,.0f} kWh/m² 로 지역 원단위({use.base})의 "
                        f"{use.per / use.base:.1f}배입니다. "
                        + em.SUSPECT_TEXT
                    )
                elif use.has_ratio:
                    # 배수(효율)와 총량(규모)을 **나란히** 둡니다.
                    # 배수만 보면 작은 절부터 가게 됩니다.
                    q1, q2 = st.columns(2)
                    q1.metric(f"면적당 에너지 ({reg} 원단위 {use.base} 대비)",
                              f"{use.per:,.0f} kWh/m²", f"{use.ratio:.2f}배",
                              delta_color="off")
                    q2.metric("연간 총에너지", f"{use.total_kwh:,.0f} kWh")
                    st.caption(em.EUI_NOTE + "  출처: " + em.EUI_SOURCE)
                else:
                    st.markdown(
                        f"**전기만 {use.elec_per:,.0f} kWh/m²** · "
                        f"연간 전기 **{use.elec_kwh:,.0f} kWh** — "
                        f"배수와 총에너지는 내지 않았습니다. {use.note}"
                    )
                    if use.note == em.NO_HEAT_NOTE:
                        st.warning(
                            "**도시가스가 0 입니다.** 산중 사찰은 LPG·등유·화목으로 "
                            "난방하는데 공개자료에는 그 연료가 없습니다. 분자에 난방이 "
                            "통째로 빠지므로 배수를 내면 실제보다 낮게 나옵니다."
                            + _NL + _NL +
                            "위 전기 사용량은 **실제로 잰 값**입니다. 4단계에 LPG·등유를 "
                            "넣으시면 그때 합산해 배수를 냅니다."
                        )
                st.caption(
                    f"분모 {use.area:,.0f} m²"
                    + (f" (연면적 {area_gross:,.0f} - 옥내 주차장 {use.parking_area:,.0f})"
                       if use.parking_area else " (옥내 주차장 없음)")
                    + " · 분자 " + em.EUI_NUMERATOR_NOTE
                )

            if es["ratio"]:
                st.markdown(
                    f"**난방 부담 지표 {es['ratio']:.2f}배** — 전기를 가장 많이 쓴 달"
                    f"({int(es['max_ym'][4:])}월)이 가장 적게 쓴 달({int(es['min_ym'][4:])}월)의 "
                    f"{es['ratio']:.1f}배입니다. "
                    + ("난방 개선 여지가 큽니다." if es["ratio"] >= 2.5 else "난방 부담은 크지 않습니다."))

            if es["total"]:
                st.caption("월별 전기 사용량 (kWh)")
                st.bar_chart({f"{k[4:]}월": v for k, v in sorted(data["elec"].items())})

            with st.expander("자세히 보기"):
                st.table({
                    "항목": ["전기 사용량", "가스 사용량", "가스 환산",
                             "전기 배출량", "가스 배출량", "공개자료 소계",
                             "전력 기준", "도시가스 기준", "GWP"],
                    "값": [f"{es['total']:,.0f} kWh ({es['months']}개월)",
                           f"{gs['total']:,.0f} kWh ({gs['months']}개월)",
                           f"{r.gas_nm3:,.1f} Nm³",
                           f"{r.elec_t:,.2f} t", f"{r.gas_t:,.2f} t",
                           f"{r.subtotal_t:,.2f} t",
                           f"{r.elec_ef} kgCO2eq/kWh ({r.elec_basis})",
                           r.gas_basis, r.gwp]})

            (st.success if lvl == "높음" else st.warning)(f"신뢰도 {lvl} — {msg}")

            if not SHARE and st.button("이 사찰 기록에 저장하기", width="stretch"):
                pp = picked.building_params()
                dongs = bld[0] if bld else []
                jjg = bld[2] if bld else []
                ds = bldrgst.summarize(dongs) if dongs else {}
                try:
                    rows, replaced = store.save({
                        "사찰": (picked.bdNm or picked.jibunAddr).strip(),
                        "지번주소": picked.jibunAddr,
                        "도로명주소": picked.roadAddr,
                        "조회연도": str(year),
                        "Scope1(t)": f"{r.gas_t:.2f}",
                        "Scope2(t)": f"{r.elec_t:.2f}",
                        "공개자료 배출량(t)": f"{r.subtotal_t:.2f}",
                        "전기(kWh)": f"{es['total']:.0f}",
                        "가스(kWh)": f"{gs['total']:.0f}",
                        "면적당 전기(kWh/m2)": (f"{use.per:,.0f}" if use.per
                                                else (f"{use.elec_per:,.0f}"
                                                      if use.elec_per else "")),
                        "난방부담 지표": f"{es['ratio']:.2f}" if es.get("ratio") else "",
                        "동수": str(ds.get("count", "")),
                        "연면적(m2)": f"{area:.1f}" if area else "",
                        "전통 동수": str(ds.get("trad_count", "")),
                        "신식 동수": str(ds.get("modern_count", "")),
                        "태양광 필요용량(kW)": f"{r.solar_kw:.0f}",
                        "신뢰도": lvl,
                        # 되살렸습니다(지시 05 6번).
                        # 전통 0동 + 배수 3.0 초과일 때만 붙습니다.
                        "대장누락 의심": "예" if use.suspect else "",
                        "제외된 자료(건)": str(data.get("dropped", 0)),
                        "전력 기준": r.elec_basis,
                        "도시가스 기준": r.gas_basis,
                        "GWP": r.gwp,
                        "용도지역": " / ".join(jjg),
                        "시군구": pp["sigunguCd"], "법정동": pp["bjdongCd"],
                        "번": pp["bun"], "지": pp["ji"], "대지구분": pp["platGbCd"],
                    })
                except store.StoreError as e:
                    st.error(str(e)); st.stop()
                st.success(
                    ("같은 지번·같은 해 기록을 **새것으로 바꿨습니다.**"
                     if replaced else "기록에 **더했습니다.**")
                    + f" 지금까지 {len(rows)}곳입니다.")
            st.markdown('<p class="hint"><b>아직 모르는 것</b> — 계약전력, LPG·등유·화목, '
                        "차량, 상수도. 모두 방문해서 확인해야 합니다.</p>", unsafe_allow_html=True)

# ═══════════ 4단계 — 정식 산정 (엑셀 서식) ═══════════
if picked and st.session_state.diag:
    data, ttype, year = st.session_state.diag
    es = bldengy.summarize(data["elec"])
    gs = bldengy.summarize(data["gas"])

    st.divider()
    st.markdown("#### 정식 산정 — 엑셀 서식 만들기")
    st.markdown('<p class="hint">「온실가스 배출량 산정 실무용 템플릿」의 활동량 칸을 '
                "채워 드립니다. 엑셀에서 열면 <b>활동량 x 발열량 x 배출계수 x 산화계수 "
                "x GWP</b> 5단계가 그대로 계산됩니다.</p>", unsafe_allow_html=True)

    # 계수 고르기는 접어 둡니다. 기본값이 옳고 대부분 손댈 일이 없는데
    # 눈에 띄는 자리에 두면 시니어에게 판단을 요구하는 셈이 됩니다(2장).
    with st.expander("자세한 설정 — 배출계수 고르기", icon=":material/tune:"):
        st.caption(f"그냥 두셔도 됩니다. 기본값은 전력 {em.ELEC_DEFAULT}, "
                   f"도시가스 {em.GAS_BASIS_DEFAULT} 입니다.")
        b1, b2 = st.columns(2)
        elec_basis = b1.selectbox("전력 배출계수", list(em.ELEC_EF),
                                  index=list(em.ELEC_EF).index(em.ELEC_DEFAULT))
        gas_basis = b2.selectbox("도시가스 환산기준", list(em.GAS_BASIS),
                                 index=list(em.GAS_BASIS).index(em.GAS_BASIS_DEFAULT))

        if elec_basis != em.ELEC_DEFAULT:
            st.warning(
                f"**이 선택은 화면에만 적용됩니다.** 내려받으실 엑셀은 서식에 박힌 "
                f"{em.ELEC_EF[em.ELEC_DEFAULT]}({em.ELEC_DEFAULT})로 계산합니다. "
                "서식의 수식은 고칠 수 없기 때문입니다. "
                "기존 다섯 사찰과 견주어 보실 때만 쓰시고, 엑셀로 내실 때는 "
                f"{em.ELEC_DEFAULT}로 되돌려 주세요."
            )
        if gas_basis != em.GAS_BASIS_DEFAULT:
            st.caption("도시가스 환산기준은 고지서로 최종 확인이 남아 있습니다. "
                       "고지서에 kWh 와 Nm³ 이 함께 찍혀 있으면 나눠 보아 확정됩니다. "
                       "이 선택은 엑셀에도 그대로 반영됩니다.")

    st.markdown('<p class="hint"><b>현장 조사값</b> — 방문해서 확인한 값만 넣으세요. '
                "모르면 비워 두시면 됩니다(0).</p>", unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    lpg = f1.number_input("LPG-프로판 (kg)", min_value=0.0, value=0.0, step=10.0)
    kero = f2.number_input("등유 (L)", min_value=0.0, value=0.0, step=10.0)
    gaso = f3.number_input("휘발유 (L)", min_value=0.0, value=0.0, step=10.0)
    dies = f4.number_input("경유 (L)", min_value=0.0, value=0.0, step=10.0)

    # 도시가스가 0 이라 3단계에서 배수를 못 냈던 사찰도, 여기에 난방 연료를
    # 넣으면 그때 배수를 냅니다(지시 04 3번).
    # **휘발유·경유는 더하지 않습니다.** 차량 연료라 건물 에너지가 아닙니다.
    _bld = st.session_state.bld
    if _bld and _bld[0] and gs["total"] <= 0 and (lpg > 0 or kero > 0):
        _ds = bldrgst.summarize(_bld[0])
        _heat = (em.fuel_kwh("LPG-프로판(LPG1호)", lpg)
                 + em.fuel_kwh("등유(Kerosene)", kero))
        _u = em.area_use(
            es["total"], 0.0, _ds["area_excl_parking"],
            region.of(picked.jibunAddr),
            parking_area=_ds["parking_area"], other_kwh=_heat,
        )
        if _u.has_ratio:
            st.success(
                f"현장 조사값을 더해 배수를 냈습니다 — 면적당 에너지 "
                f"**{_u.per:,.0f} kWh/m²**, {region.label(picked.jibunAddr)} 사찰 "
                f"원단위 {_u.base} 대비 **{_u.ratio:.2f}배**"
                + _NL + _NL +
                f"난방 연료 {_heat:,.0f} kWh 를 전기 {es['total']:,.0f} kWh 에 "
                "더한 값입니다. 차량 연료(휘발유·경유)는 건물 에너지가 아니라 "
                "빼고 셈했습니다."
            )

    if st.button("엑셀 서식 만들기", width="stretch"):
        extra = []
        for fuel, qty, scope in (("LPG-프로판(LPG1호)", lpg, "고정연소"),
                                 ("등유(Kerosene)", kero, "고정연소"),
                                 ("휘발유(Gasoline)", gaso, "이동연소"),
                                 ("경유(Diesel)", dies, "이동연소")):
            if qty > 0:
                extra.append(tpl.Activity(fuel, float(qty), scope=scope))

        temple = (picked.bdNm or picked.jibunAddr).strip()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, f"{temple}_{year}_온실가스산정.xlsx")
                path, acts = tpl.from_diagnosis(
                    out, temple, year, es["total"], gs["total"],
                    gas_basis=gas_basis, extra=extra)
                blob = io.open(path, "rb").read()
        except tpl.TemplateError as e:
            st.error(str(e)); st.stop()

        pv = tpl.preview(es["total"], acts, elec_basis=elec_basis)
        st.session_state.xlsx = (blob, f"{temple}_{year}_온실가스산정.xlsx", pv, acts)

    x = st.session_state.xlsx
    if x:
        blob, fname, pv, acts = x
        st.markdown("##### 미리보기")
        if pv["rows"]:
            st.table({
                "연료": [r["연료"] for r in pv["rows"]],
                "구분": [r["구분"] for r in pv["rows"]],
                "활동량": [r["활동량"] for r in pv["rows"]],
                "발열량": [r["발열량"] for r in pv["rows"]],
                "배출량": [r["배출량"] for r in pv["rows"]],
            })
        else:
            st.caption("연료 활동량이 없습니다. 전력만 들어갑니다.")

        s1, s2, s3 = st.columns(3)
        s1.metric("Scope 1 (연료)", f"{pv['scope1_t']:,.2f} t")
        s2.metric("Scope 2 (전력)", f"{pv['scope2_t']:,.2f} t")
        s3.metric("합계", f"{pv['total_t']:,.2f} t")
        st.caption(f"전력 {pv['elec_basis']} · GWP {pv['gwp']} 기준. "
                   "상수도는 Scope 3 이라 이 서식에 들어가지 않습니다.")

        with st.expander("산식 보기 (5단계가 어떻게 계산되는지)"):
            for r in pv["rows"]:
                st.markdown(f"**{r['연료']}**")
                st.code(r["산식"], language=None)
            st.markdown("**전력**")
            st.code(f"{es['total']:,.0f} kWh x {em.ELEC_EF[pv['elec_basis']]}"
                    f" = {pv['scope2_t']:,.2f} t", language=None)

        st.download_button("엑셀 내려받기", data=blob, file_name=fname,
                           mime="application/vnd.openxmlformats-officedocument."
                                "spreadsheetml.sheet",
                           width="stretch")
        st.caption("내려받은 파일을 엑셀에서 열면 ⑥종합요약에 합계가 나옵니다. "
                   "합계가 0 이면 연료명이 서식과 다른 것이니 알려 주세요.")


# ═══════════ 5·6·7단계 — 모임 안에서만 보는 부분 ═══════════
# 남에게 보여주는 판에서는 통째로 감춥니다. 까닭은 _share_mode() 를 보십시오.
saved = []
if not SHARE:
    # ═══════════ 5단계 — 사찰 목록 (쌓아서 비교) ═══════════
    st.divider()
    try:
        saved = store.load()
    except store.StoreError as e:
        st.error(str(e))
        saved = []

    st.markdown(f"#### 저장된 사찰 — {len(saved)}곳")

    if not saved:
        st.markdown('<p class="hint">아직 저장된 사찰이 없습니다. 위에서 진단한 뒤 '
                    "<b>[이 사찰 기록에 저장하기]</b> 를 누르시면 여기에 쌓입니다.<br>"
                    "여러 곳이 쌓이면 서로 견주어 볼 수 있습니다.</p>",
                    unsafe_allow_html=True)
    else:
        b = store.benchmark(saved)
        m1, m2, m3 = st.columns(3)
        m1.metric("사찰 수", f"{b['count']}곳")
        m2.metric("배출량 평균", f"{b['ton_avg']:,.1f} t" if b["ton_avg"] else "—")
        m3.metric("면적당 전기 평균",
                  f"{b['per_avg']:,.0f} kWh/m²" if b["per_avg"] else "—")

        bits = []
        if b["ton_n"]:
            bits.append(f"배출량은 {b['ton_n']}곳 평균이고 "
                        f"{b['ton_min']:,.1f} ~ {b['ton_max']:,.1f} t 사이입니다")
        if b["suspect"]:
            bits.append(f"대장 누락이 의심되는 {b['suspect']}곳은 면적당 평균에서 뺐습니다")
        if b["count"] < 5:
            bits.append("아직 표본이 적어 평균은 참고만 하십시오")
        if bits:
            st.caption(" · ".join(bits) + ".")

        st.table({
            "사찰": [r.get("사찰", "") for r in saved],
            "연도": [r.get("조회연도", "") for r in saved],
            "배출량(t)": [r.get("공개자료 배출량(t)", "") for r in saved],
            "면적당(kWh/m²)": [r.get("면적당 전기(kWh/m2)", "") or "—" for r in saved],
            "연면적(m²)": [r.get("연면적(m2)", "") or "—" for r in saved],
            "신뢰도": [r.get("신뢰도", "") for r in saved],
            "누락 의심": [r.get("대장누락 의심", "") for r in saved],
        })

        # ── 두 축 — 배수(효율) x 총량(규모) ──
        #
        # **여러 절을 모아 볼 때만** 네 칸으로 나눕니다. 총량 기준선이
        # 표본의 중간값이라 한 곳만 보고는 정할 수 없습니다.
        # 단일 사찰 화면에는 판정 문구를 붙이지 않습니다.
        _rr = batch.ratio_rows()
        _med, _usable = batch.classify(_rr)      # CSV 와 같은 함수를 씁니다
        _pts = [(r.get("사찰", ""), q, t) for q, t, r in _usable]

        if len(_pts) >= 3:
            st.markdown("##### 두 축으로 보기 — 효율과 규모")
            st.markdown(
                '<p class="hint">처방이 다르므로 섞지 않습니다. '
                "<b>효율 개선 후보</b>는 낭비를 줄이는 일이고, "
                "<b>설비·태양광 후보</b>는 이미 효율적이지만 규모가 커서 "
                "설비를 바꿀 값어치가 있는 절입니다.</p>",
                unsafe_allow_html=True)

            import altair as alt
            import pandas as pd
            df = pd.DataFrame(
                [{"사찰": n, "배수": q, "총에너지(kWh)": t,
                  "분류": em.quadrant(q, t, _med)} for n, q, t in _pts])
            base = alt.Chart(df)
            pts = base.mark_circle(size=120, opacity=0.8).encode(
                x=alt.X("배수:Q", title="지역 원단위 대비 배수"),
                y=alt.Y("총에너지(kWh):Q", title="연간 총에너지 (kWh, 로그)",
                        scale=alt.Scale(type="log")),
                color=alt.Color("분류:N", title=""),
                tooltip=["사찰", "배수", "총에너지(kWh)", "분류"],
            )
            vline = base.mark_rule(strokeDash=[6, 4]).encode(
                x=alt.datum(em.QUAD_RATIO))
            hline = base.mark_rule(strokeDash=[6, 4]).encode(
                y=alt.datum(_med))
            st.altair_chart((pts + vline + hline).properties(height=360),
                            width="stretch")
            st.caption(
                f"세로 점선 = 배수 {em.QUAD_RATIO:.1f} (원단위 자체가 전국 중간값) · "
                f"가로 점선 = 이 {len(_pts)}곳의 총에너지 중간값 "
                f"{_med:,.0f} kWh. **가로선은 절대 기준이 아니라 "
                "모인 절들 안에서의 상대적인 선입니다.**")

            _cnt = df["분류"].value_counts().to_dict()
            st.table({
                "분류": list(em.QUAD.values()),
                "곳": [_cnt.get(v, 0) for v in em.QUAD.values()],
                "사찰": [" · ".join(df[df["분류"] == v]["사찰"].tolist()) or "—"
                         for v in em.QUAD.values()],
            })
        elif _rr:
            st.caption("배수와 총에너지가 함께 나온 곳이 3곳을 넘으면 "
                       "두 축 그림이 나옵니다.")

        with st.expander("나눠 돌린 기록 합치기"):
            st.markdown('<p class="hint">여러 분이 나눠 조회하셨다면 각자의 '
                        "<b>사찰기록.csv</b> 를 여기에 올리십시오. 같은 사찰·같은 해가 "
                        "겹치면 <b>나중에 저장한 것</b>만 남습니다.<br>"
                        "적어 두신 <b>방문 상태와 메모는 지워지지 않습니다.</b></p>",
                        unsafe_allow_html=True)
            ups = st.file_uploader("합칠 CSV", type="csv", accept_multiple_files=True,
                                   label_visibility="collapsed")
            if ups and st.button("합치기", width="stretch"):
                try:
                    res = store.merge([u.getvalue() for u in ups])
                except store.StoreError as e:
                    st.error(str(e)); st.stop()
                st.success(
                    f"**{len(ups)}개 파일에서 {res['seen']}줄**을 읽어 "
                    f"새로 {res['added']}곳을 더하고 {res['updated']}곳을 새것으로 "
                    f"바꿨습니다. 오래되어 넘긴 것 {res['older']}줄. "
                    f"이제 모두 {res['total']}곳입니다.")
                st.rerun()

        d1, d2 = st.columns([3, 2])
        with d1:
            st.download_button("표 내려받기 (엑셀에서 열림)",
                               data=store.as_csv_bytes(),
                               file_name="사찰기록.csv", mime="text/csv",
                               width="stretch")
            st.caption(f"파일은 이 폴더의 {store.FILE_NAME} 에도 그대로 있습니다.")
        with d2:
            labels = [f"{r.get('사찰','')} · {r.get('조회연도','')}" for r in saved]
            pick = st.selectbox("지울 기록", options=list(range(len(saved))),
                                format_func=lambda i: labels[i], index=None,
                                placeholder="고르세요")
            if pick is not None and st.button("이 기록 지우기", width="stretch"):
                try:
                    store.remove(saved[pick].get("지번주소", ""),
                                 saved[pick].get("조회연도", ""))
                except store.StoreError as e:
                    st.error(str(e)); st.stop()
                st.rerun()


    # ═══════════ 6단계 — 명단 일괄 조회 ═══════════
    st.divider()
    st.markdown("#### 명단으로 한꺼번에 조회")

    _here = os.path.dirname(os.path.abspath(__file__))
    _list_path = os.path.join(_here, batch.LIST_NAME)

    try:
        targets = batch.read_list(_list_path) if os.path.exists(_list_path) else []
        list_err = ""
    except batch.BatchError as e:
        targets, list_err = [], str(e)

    if list_err:
        st.error(list_err)
    elif not targets:
        st.markdown(f'<p class="hint">같은 폴더에 <b>{batch.LIST_NAME}</b> 이 있으면 '
                    "여기서 한꺼번에 조회할 수 있습니다.</p>", unsafe_allow_html=True)
    else:
        have = batch.done_map()
        left = [t for t in targets if (t.no or t.name) not in have]
        bad = [t for t in targets if have.get(t.no or t.name)]

        c1, c2, c3 = st.columns(3)
        c1.metric("명단", f"{len(targets)}곳")
        c2.metric("조회함", f"{len(targets) - len(left)}곳")
        c3.metric("남음", f"{len(left)}곳")

        st.markdown('<p class="hint">한 번에 <b>10곳씩</b> 합니다. 한 곳이 끝날 때마다 '
                    "바로 저장하므로 <b>중간에 멈춰도 이어집니다.</b> "
                    "이미 조회한 곳은 건너뜁니다.<br>"
                    "한 곳에 10~20초 걸립니다. 제공기관 서버가 느리면 더 걸리는데, "
                    "3분을 넘기면 그 곳은 건너뛰고 다음으로 갑니다.</p>",
                    unsafe_allow_html=True)

        b1, b2, b3 = st.columns([2, 2, 1])
        year_b = b3.selectbox("해", [dt.date.today().year - 1,
                                     dt.date.today().year - 2,
                                     dt.date.today().year - 3], key="batch_year")
        go = b1.button(f"10곳 조회하기  (남은 {len(left)}곳 중)",
                       width="stretch", disabled=not left)
        again = b2.button(f"실패한 {len(bad)}곳만 다시",
                          width="stretch", disabled=not bad)

        if go or again:
            bar = st.progress(0.0, text="시작합니다")
            log = st.empty()
            t0 = time.time()
            lines = []

            def prog(done, total, t, why):
                gone = time.time() - t0
                eta = (gone / done) * (total - done) if done else 0
                bar.progress(done / total,
                             text=f"{done}/{total}  {t.label()}  ·  "
                                  f"남은 시간 약 {eta/60:.0f}분")
                lines.append(f"{'OK ' if why == '성공' else '-- '} {t.label()}  {why}")
                log.code(_NL.join(lines[-10:]), language=None)

            try:
                res = batch.run(targets, year_b, CONFM_KEY, SERVICE_KEY,
                                limit=10, retry_failed=bool(again), progress=prog)
            except Exception as e:
                bar.empty(); st.error(f"조회 중 멈췄습니다: {e}"); st.stop()
            bar.empty()

            st.success(f"**성공 {res['ok']}곳 · 실패 {len(res['failed'])}곳** "
                       f"({(time.time()-t0)/60:.0f}분). "
                       f"아직 {res['remaining']}곳 남았습니다.")
            if res["failed"]:
                st.warning("**실패한 곳**" + _NL + _NL +
                           _NL.join(f"- {t.label()} — {why}" for t, why in res["failed"]))
            st.rerun()


    # ═══════════ 7단계 — 방문 우선순위 ═══════════
    if saved:
        st.divider()
        ready, hold = store.priority(saved)
        st.markdown(f"#### 방문 우선순위 — {len(ready)}곳")
        st.markdown('<p class="hint">세 가지를 <b>나란히</b> 보여 드립니다. '
                    "점수를 합쳐 하나로 만들지 않습니다. 어느 것을 중히 볼지는 "
                    "사람이 정할 일입니다.<br>"
                    "배출 규모가 큰 순으로 줄을 세웠을 뿐입니다. "
                    "난방 부담은 2.5배 이상이면 <b>◀</b> 를 붙였습니다.</p>",
                    unsafe_allow_html=True)

        if ready:
            st.table({
                "번호": [r.get("번호", "") for r in ready],
                "사찰": [r.get("사찰", "") for r in ready],
                "배출 규모(t)": [r.get("공개자료 배출량(t)", "") for r in ready],
                "난방 부담": [store.heating_flag(r) for r in ready],
                "태양광 여지": [store.solar_room(r) for r in ready],
                "방문 상태": [r.get("방문 상태", "") for r in ready],
            })
        else:
            st.caption("아직 판단할 수 있는 곳이 없습니다.")

        if hold:
            st.markdown(f"##### 판단 보류 — {len(hold)}곳")
            st.markdown('<p class="hint">우선순위가 <b>낮은</b> 것이 아니라 '
                        "<b>자료가 부족해 판단을 미룬</b> 곳입니다. 섞어 보지 마십시오. "
                        "현장에서 확인해야 합니다.</p>", unsafe_allow_html=True)
            st.table({
                "번호": [r.get("번호", "") for r in hold],
                "사찰": [r.get("사찰", "") for r in hold],
                "보류 사유": [r.get("_보류사유", "") for r in hold],
                "전기(kWh)": [r.get("전기(kWh)", "") or "—" for r in hold],
                "연면적(m²)": [r.get("연면적(m2)", "") or "—" for r in hold],
            })
