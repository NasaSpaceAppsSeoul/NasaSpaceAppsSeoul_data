"""월별 인사이트 페이지(insight.html)에 넣을 샘플 지역 데이터를 만든다.

python3 tools/mockup_extract.py <출력.json> [KOR CAL BC]   # 나라를 빼면 KOR만
"""
import json, sys, os, numpy as np, pandas as pd
from pathlib import Path
from matplotlib.path import Path as MP
from scipy.spatial import cKDTree

B = str(Path(__file__).resolve().parents[1])
OFF = Path(B) / "inputs" / "official"

# 나라별: 샘플(지역 id, 달, 주소 토큰), 화면 이름, 경도 1° km, 공식 기록 읽는 법
CAL_CAUSE = {1: "번개", 2: "장비 사용", 3: "흡연", 4: "캠프파이어", 5: "쓰레기 소각", 6: "철도", 7: "방화", 8: "불장난", 9: "기타",
             10: "차량", 11: "전선", 12: "소방 훈련", 13: "기타 훈련", 14: "원인 미상", 15: "건물", 16: "항공기", 18: "처방 화입 확산", 19: "불법 캠프파이어"}
CFG = {
    "KOR": {"samples": [("goseong", "강원 Goseong-gun", "2019-04"), ("uiseong", "91817680B75376031789242", "2025-03"), ("daegu-jung", "91817680B11201690622195", "2025-03")],
            "km_lon": 88.8, "prov_short": None,
            "lab": {"country": "대한민국", "lv1": "시·도", "lv2": "시·군·구", "official": "산림청",
                    "source": "NASA FIRMS VIIRS NOAA-20 (VJ114IMG)·S-NPP (VNP14IMG) 375 m, 산림청 산불 통계, 경계 geoBoundaries (CC BY 3.0)"}},
    "CAL": {"samples": [("butte-2018", "52423323B88547646561946", "2018-11"), ("fresno-2020", "52423323B20293708991619", "2020-09"), ("sanmateo-2020", "52423323B75131784459442", "2020-08")],
            "km_lon": 88.8, "prov_short": "California",
            "lab": {"country": "캘리포니아", "lv1": "주", "lv2": "카운티", "official": "CAL FIRE",
                    "source": "NASA FIRMS VIIRS NOAA-20·S-NPP 375 m, CAL FIRE FRAP 화재 경계, 경계 geoBoundaries USA (미국 인구조사국)"},
            "ext": {"file": OFF / "CAL" / "cal_fire_perimeters_2001_2025.csv", "date": "ALARM_DATE", "place": "FIRE_NAME", "size": "GIS_ACRES", "to_ha": 0.404686,
                    "cause": lambda v: CAL_CAUSE.get(int(v), "기타") if pd.notna(v) else "원인 미상", "keep": None}},
    "BC": {"samples": [("peace-2023", "BC-RD-60", "2023-05"), ("okanagan-2023", "BC-RD-82", "2023-08"), ("thompson-2021", "BC-RD-151", "2021-07")],
           "km_lon": 66.8, "prov_short": "BC",
           "lab": {"country": "브리티시컬럼비아", "lv1": "주", "lv2": "지역구", "official": "BC Wildfire Service",
                   "source": "NASA FIRMS VIIRS NOAA-20·S-NPP 375 m, BC Wildfire Service 과거 산불 기록, 경계 BC Data Catalogue (Open Government Licence – BC)"},
           "ext": {"file": OFF / "BC" / "bc_fire_incidents_2001_2025.csv", "date": "IGNITION_DATE", "place": "GEOGRAPHIC_DESCRIPTION", "size": "CURRENT_SIZE", "to_ha": 1.0,
                   "cause": lambda v: {"Lightning": "번개", "Person": "사람"}.get(v, "원인 미상"), "keep": ("FIRE_TYPE", "Fire")}},
}


def rings(geom):
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def inside(geom, xy):
    m = np.zeros(len(xy), bool)
    for p in rings(geom):
        a = MP(np.asarray(p[0])).contains_points(xy)
        for h in p[1:]:
            a &= ~MP(np.asarray(h)).contains_points(xy)
        m |= a
    return m


def simp(geom, r=4):
    return [[[[round(x, r), round(y, r)] for x, y in ring] for ring in p] for p in rings(geom)]


def run(C):
    cfg = CFG[C]; O = f"{B}/output/{C}"
    g = json.load(open(f"{O}/regions.geojson", encoding="utf-8")); F = {f["properties"]["id"]: f for f in g["features"]}
    patch = f"{B}/boundaries/{C}/patch-{C}-ADM2.geojson"
    full = {f["properties"]["shapeID"]: f for f in json.load(open(f"{B}/boundaries/{C}/geoBoundaries-{C}-ADM2.geojson", encoding="utf-8"))["features"]
            + (json.load(open(patch, encoding="utf-8"))["features"] if os.path.exists(patch) else [])}
    cal = json.load(open(f"{O}/calendar_by_region.json", encoding="utf-8")); months = cal["months"]; R = cal["regions"]
    prov = json.load(open(f"{O}/calendar_by_province.json", encoding="utf-8"))["provinces"]
    meta = json.load(open(f"{O}/meta.json", encoding="utf-8"))
    hs = pd.read_csv(f"{O}/hotspots_clean.csv", parse_dates=["acq_date"])
    hs = hs[((hs.sensor == "VIIRS") & (hs.acq_date < "2018-04-01")) | ((hs.sensor == "N20") & (hs.acq_date >= "2018-04-01"))].copy()   # NOAA-20 기준: 그 전은 S-NPP
    hs["cell"] = (hs.latitude / 0.01).round().astype(int).astype(str) + "_" + (hs.longitude / 0.01).round().astype(int).astype(str)
    km = lambda lon, lat, c: np.hypot((lon - c[0]) * cfg["km_lon"], (lat - c[1]) * 111.0)
    xy = hs[["longitude", "latitude"]].to_numpy()
    # 노트북 ⑭와 같은 지역 판정: 경계 안이면 그 지역, 경계 밖이면 3 km 안의 가장 가까운 경계 지역
    reg = np.full(len(xy), None, dtype=object)
    for sid, f in full.items():
        pts = np.concatenate([np.asarray(q[0]) for q in rings(f["geometry"])]); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
        c = np.where((reg == None) & (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1))[0]
        if len(c): reg[c[inside(f["geometry"], xy[c])]] = sid
    owner = np.concatenate([[sid] * sum(len(q[0]) for q in rings(f["geometry"])) for sid, f in full.items()])
    tree = cKDTree(np.concatenate([np.asarray(q[0]) for f in full.values() for q in rings(f["geometry"])]))
    out_ = np.where(reg == None)[0]
    if len(out_):
        dd, jj = tree.query(xy[out_]); reg[out_[dd <= 0.03]] = owner[jj[dd <= 0.03]]
    hs["region"] = reg
    hs_u = hs.drop_duplicates(["cell", "acq_date"])
    evr = json.load(open(f"{O}/events_by_region.json", encoding="utf-8")); evl = json.load(open(f"{O}/events.json", encoding="utf-8"))

    # 화면 이름: 주가 하나뿐인 지역은 라벨 앞 주 이름을 짧게(공백 없이), 상위 구역 이름은 한국어 지역 이름으로
    ps = cfg["prov_short"]
    p0 = next(iter(prov)) + " "
    lbl = lambda s: ps + " " + s[len(p0):] if ps and s.startswith(p0) else s
    pname = lambda p: cfg["lab"]["country"] if ps else p

    # 공식 기록
    if C == "KOR":
        kfs = pd.read_excel(OFF / "KOR" / "산불통계.xlsx", header=0); kfs.columns = ["date", "place", "cause", "ha"]
        kfs["date"] = pd.to_datetime(kfs.date.astype(str).str[:10])
    else:
        e = cfg["ext"]; x = pd.read_csv(e["file"])
        if e["keep"]: x = x[x[e["keep"][0]] == e["keep"][1]]
        x = x[x.LATITUDE.notna()]
        d = pd.to_datetime(x[e["date"]].astype(str).str[:10], errors="coerce")
        kfs = pd.DataFrame({"date": d, "place": x[e["place"]].fillna("").astype(str).str.title(), "cause": x.CAUSE.map(e["cause"]) if "CAUSE" in x else x.FIRE_CAUSE.map(e["cause"]),
                            "ha": pd.to_numeric(x[e["size"]], errors="coerce").fillna(0) * e["to_ha"], "lon": x.LONGITUDE, "lat": x.LATITUDE}).dropna(subset=["date"])
    KO_NAME = {"Goseong-gun": ("강원", "고성"), "Uiseong-gun": ("경북", "의성"), "Jung-gu [Central District]": ("대구", "중")}

    def official(rid, name, y, m):
        if C == "KOR":
            pv, nm = KO_NAME[name]; t = kfs.place.str.split()
            sel = (t.str[0] == pv) & (t.str[1].fillna("") == nm) & (kfs.date.dt.year == y) & (kfs.date.dt.month == m)
            rows = kfs.loc[sel].sort_values("date")
        else:
            k = kfs[(kfs.date.dt.year == y) & (kfs.date.dt.month == m)]
            rows = k[inside(full[rid]["geometry"], k[["lon", "lat"]].to_numpy())].sort_values("date")
        return [{"date": f"{d:%m/%d}", "place": pl, "cause": c, "ha": round(float(h), 2)} for d, pl, c, h in rows[["date", "place", "cause", "ha"]].itertuples(index=False)]

    ev = meta.get("external_validation", {})
    if "kosis_annual" in ev: kb = ev["kosis_annual"]["independent_break_test"]
    else:
        ib = ev.get("annual_records", {}).get("independent_break_test", {})
        kb = {k.split(" / ")[0]: v for k, v in ib.items() if k.endswith("공식 건수")}
    nat = {"risk": meta["regions"]["national_risk"], "min_annual": meta["regions"]["sufficient_min_viirs_annual"],
           "err_nat": meta["regions"]["error"]["national"], "err_dist": meta["regions"]["error"]["district_median"]}
    val = {"detect": ev.get("detection_by_size", {}), "kosis": kb}

    def build(tok, rid, ym):
        f = F[rid]; p = f["properties"]; r = R[rid]; v = r["viirs"]; y, m = map(int, ym.split("-")); i = months.index(ym)
        gfull = full[rid]["geometry"]; d = hs[(hs.region == rid).to_numpy()].drop_duplicates(["cell", "acq_date"])
        pts = np.concatenate([np.asarray(q[0]) for q in rings(gfull)]); c = pts.mean(0)
        mon = d[(d.acq_date.dt.year == y) & (d.acq_date.dt.month == m)]
        daily = mon.groupby(mon.acq_date.dt.day).size().to_dict()
        days = sorted(daily); eps = []
        for dd in days:   # 감지가 이어진 날 묶음 (하루 건너뜀까지)
            if eps and dd - eps[-1]["end"] <= 2: eps[-1]["end"] = dd; eps[-1]["n"] += daily[dd]
            else: eps.append({"start": dd, "end": dd, "n": daily[dd]})
        for e in eps:
            sub = mon[mon.acq_date.dt.day.between(e["start"], e["end"])]
            e["lon"] = round(float(sub.longitude.mean()), 3); e["lat"] = round(float(sub.latitude.mean()), 3)
        strip = [{"year": int(mo[:4]), "v": v["value"][j]} for j, mo in enumerate(months) if mo.endswith(f"-{m:02d}") and 2012 <= int(mo[:4]) <= 2025 and v["value"][j] is not None and mo != "2012-01"]
        own_mt = [sum(v["value"][j] or 0 for j, mo in enumerate(months) if mo.endswith(f"-{k:02d}") and "2012-02" <= mo <= "2025-12") for k in range(1, 13)]
        P = prov[p["province"]]; refn = p["fallback"]["ref_province"] if p["fallback"] else p["province"]; RP = prov[refn]
        lo = "2001-01" if RP["basis"] == "보정 25년" else "2012-02"
        prov_mt = [sum(RP["value"][j] or 0 for j, mo in enumerate(months) if mo.endswith(f"-{k:02d}") and lo <= mo <= "2025-12") for k in range(1, 13)]
        hist = d[(d.acq_date >= "2012-02-01") & (d.acq_date < "2026-01-01")]
        rec = hist.assign(c2=(hist.latitude / 0.02).round().astype(int).astype(str) + "_" + (hist.longitude / 0.02).round().astype(int).astype(str)).groupby("c2").acq_date.apply(lambda s: s.dt.year.nunique())
        rec = [{"lat": round(int(k.split("_")[0]) * 0.02, 3), "lon": round(int(k.split("_")[1]) * 0.02, 3), "y": int(n)} for k, n in rec.items()]
        nbs = [{"label": lbl(R[n]["label"]), "suff": R[n]["sufficiency"], "v": R[n]["viirs"]["value"][i], "rank": R[n]["viirs"]["rank"][i],
                "n": R[n]["viirs"]["years_in_month"][i], "geom": simp(F[n]["geometry"], 3)} for n in p["neighbors"]]
        allm = hs_u[(hs_u.acq_date.dt.year == y) & (hs_u.acq_date.dt.month == m) & (hs_u.region != rid)]
        near = allm[km(allm.longitude.to_numpy(), allm.latitude.to_numpy(), c) <= 50]
        fb = p["fallback"]
        if fb and ps:
            fb = {**fb, "province": pname(fb["province"]), "ref_province": pname(fb["ref_province"])}
            if fb.get("nearest_sufficient"): fb["nearest_sufficient"] = {**fb["nearest_sufficient"], "region_label": lbl(fb["nearest_sufficient"]["region_label"])}
        out = {"id": rid, "tok": tok, "country": C, "lab": cfg["lab"], "nat": nat, "val": val,
               "label": lbl(p["label"]), "name": p["name"], "province": pname(p["province"]), "suff": p["sufficiency"],
               "annual": p["viirs_annual_fire_days"], "annual_all": p["viirs_annual_all_years"], "longterm": p.get("longterm"),
               "risk": p["risk_months"], "risk_share": p["risk_share"], "risk_from": p["risk_from"], "fallback": fb,
               "ym": ym, "value": v["value"][i], "median": v["median_by_month"][m - 1], "lo": v["band_low_by_month"][m - 1], "hi": v["band_high_by_month"][m - 1],
               "rank": v["rank"][i], "n": v["years_in_month"][i], "yrs_fire": v["years_with_fire_by_month"][m - 1],
               "strip": strip, "own_mt": own_mt, "prov_mt": prov_mt,
               "prov": {"name": pname(p["province"]), "basis": P["basis"], "suff": P["sufficiency"], "err": P["loyo_error"], "v": P["value"][i], "rank": P["rank"][i],
                        "n": P["years_in_month"][i], "ratio": P["ratio_to_median"][i], "risk": P["risk_months"]},
               "ref": {"name": pname(refn), "basis": RP["basis"], "suff": RP["sufficiency"], "err": RP["loyo_error"], "v": RP["value"][i], "rank": RP["rank"][i],
                       "n": RP["years_in_month"][i], "ratio": RP["ratio_to_median"][i]},
               "daily": {int(k): int(x) for k, x in daily.items()}, "episodes": eps,
               "points": [[round(a, 3), round(b, 3), int(t.day)] for a, b, t in zip(mon.longitude, mon.latitude, mon.acq_date)],
               "rec": rec, "geom": simp(f["geometry"], 4), "center": [round(c[0], 4), round(c[1], 4)], "neighbors": nbs,
               "near50": {"n": int(len(near)), "first": int(near.acq_date.min().day) if len(near) else None}}
        e = evr["regions"][rid]; j = evr["months"].index(ym) if ym in evr["months"] else None
        out["clusters"] = None if j is None else {"fire_days": e["fire_days"][j], "peak_day_cells": e["peak_day_cells"][j], "events": e["events"][j], "big_events": e["big_events"][j]}
        big = sorted([x for x in evl if rid in x["regions"] and x["start"][:7] <= ym <= x["end"][:7]], key=lambda x: -x["cells"])[:1]
        out["main_cluster"] = None if not big else {**{k: big[0][k] for k in ["start", "end", "days", "cells", "peak_cells", "peak_date"]},
                                                    "regions": [lbl(F[x]["properties"]["label"]) for x in big[0]["regions"] if x in F][:6]}
        out["official"] = official(rid, p["name"], y, m)
        return out

    res = []
    for tok, rid, ym in cfg["samples"]:
        if rid not in F: rid = next(k for k, f in F.items() if f["properties"]["label"] == rid)
        res.append(build(tok, rid, ym))
    return res, nat, val


out_path = sys.argv[1]
countries = [c.upper() for c in sys.argv[2:]] or ["KOR"]
regions, first = [], None
for C in countries:
    rs, nat, val = run(C); regions += rs
    if first is None: first = (nat, val)
    for r in rs:
        print(C, r["tok"], r["label"], r["suff"], r["value"], r["rank"], r["n"], "official", len(r["official"]), "near50", r["near50"], r["main_cluster"] and r["main_cluster"]["cells"])
# national·validation 최상위 값은 첫 나라(한국) 것으로 남겨 예전 화면 코드와 호환
json.dump({"regions": regions, "national": first[0], "validation": first[1]}, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
