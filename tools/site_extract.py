"""샘플 사이트(랜딩 → 대시보드 → 인사이트)용 데이터를 mockup/site/data.js 로 만든다.

python3 tools/site_extract.py          # 한국 → mockup/site/data.js
python3 tools/site_extract.py CAL      # 캘리포니아 → mockup/site/data_CAL.js (BC도 같음)
"""
import json, re, difflib, sys
import numpy as np, pandas as pd
from pathlib import Path
from matplotlib.path import Path as MP
from scipy.spatial import cKDTree

B = Path(__file__).resolve().parents[1]
C = sys.argv[1].upper() if len(sys.argv) > 1 else "KOR"
O = B / "output" / C
OUT = B / "mockup/site" / ("data.js" if C == "KOR" else f"data_{C}.js")
LABELS = {
    "KOR": {"country": "대한민국", "short": "전국", "lv1": "시·도", "lv2": "시·군·구", "single": False, "bins": [3, 10, 30],
            "boundary": "geoBoundaries (CC BY 3.0) + 영광군 보강", "official": "산림청"},
    "CAL": {"country": "캘리포니아", "short": "캘리포니아", "lv1": "주", "lv2": "카운티", "single": True,
            "boundary": "geoBoundaries USA (미국 인구조사국, 퍼블릭 도메인)", "official": "CAL FIRE"},
    "BC": {"country": "브리티시컬럼비아", "short": "BC", "lv1": "주", "lv2": "지역구", "single": True,
           "boundary": "BC Data Catalogue regional district (Open Government Licence – BC)", "official": "BC Wildfire Service"},
}[C]

geo = json.load(open(O / "regions.geojson", encoding="utf-8"))
_patch = B / f"boundaries/{C}/patch-{C}-ADM2.geojson"   # geoBoundaries에 빠진 구역 보강 (한국: 영광군)
full = {f["properties"]["shapeID"]: f for f in json.load(open(B / f"boundaries/{C}/geoBoundaries-{C}-ADM2.geojson", encoding="utf-8"))["features"] + (json.load(open(_patch, encoding="utf-8"))["features"] if _patch.exists() else [])}
cal = json.load(open(O / "calendar.json", encoding="utf-8"))
clim = json.load(open(O / "climatology.json", encoding="utf-8"))
creg = json.load(open(O / "calendar_by_region.json", encoding="utf-8"))
cprov = json.load(open(O / "calendar_by_province.json", encoding="utf-8"))
meta = json.load(open(O / "meta.json", encoding="utf-8"))
months = creg["months"]
r1 = lambda x: None if x is None else round(float(x), 1)

# ---------- 한글 시·군·구 이름: 산림청 기록의 한글 이름을 로마자로 바꿔 경계 이름과 맞춤 (노트북 ⑰과 같은 규칙)
def rr(s):
    I = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
    V = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
    F = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]
    FV = {1: "g", 2: "kk", 4: "n", 7: "d", 8: "r", 16: "m", 17: "b", 19: "s", 20: "ss", 22: "j", 23: "ch", 25: "t", 26: "p"}
    js = [((ord(c) - 0xAC00) // 588, ((ord(c) - 0xAC00) % 588) // 28, (ord(c) - 0xAC00) % 28) for c in s if 0xAC00 <= ord(c) <= 0xD7A3]
    out = ""
    for k, (i, v, f) in enumerate(js):
        ini = I[i]
        if k > 0:
            pf = js[k - 1][2]
            if i == 5 and pf == 8: ini = "l"
            elif i == 5 and pf == 4: out = out[:-1] + "l"; ini = "l"
            elif i == 5 and pf in (16, 21): ini = "n"
            elif i == 11 and pf in FV: out = out[: -len(F[pf])] + FV[pf]; ini = ""
        out += ini + V[v] + F[f]
    return out

feats = geo["features"]
P = [f["properties"] for f in feats]
base_name = lambda n: re.sub(r"\[.*?\]", "", n).split("-")[0].strip().lower().replace(" ", "")
SUF = {"gun": "군", "si": "시", "gu": "구"}
ko = {}
if C != "KOR":   # 한국 밖은 영문 이름 그대로
    pairs = set(); ko = {p["id"]: p["name"] for p in P}
else:
    kfs = pd.read_excel(B / "inputs" / "official" / "KOR" / "산불통계.xlsx", header=0)
    kfs.columns = ["date", "place", "cause", "ha"]
    pairs = set(tuple(t[:2]) for t in kfs.place.str.split() if len(t) >= 2)
for pv, sgg in pairs:
    r, best, bs = rr(sgg), None, 0
    for p in P:
        if p["province"] not in {"전남광주": ["전남", "광주"]}.get(pv, [pv]): continue
        b = base_name(p["name"]); sc = difflib.SequenceMatcher(None, r, b).ratio()
        if len(b) >= 3 and r.startswith(b): sc = max(sc, 0.95)
        if sc > bs: best, bs = p, sc
    if best and bs >= 0.8 and best["id"] not in ko:
        suf = SUF.get(best["name"].split("[")[0].strip().split("-")[-1].lower(), "")
        ko[best["id"]] = sgg + suf
KO_FIX = {"Damyang-gun": "담양군", "Gokseong-gun": "곡성군", "Gurye-gun": "구례군", "Hwasun-gun": "화순군", "Naju-si": "나주시", "Hampyeong-gun": "함평군",
          "Jangheung-gun": "장흥군", "Gangjin-gun": "강진군", "Haenam-gun": "해남군", "Yeongam-gun": "영암군", "Boseong-gun": "보성군", "Suncheon-si": "순천시",
          "Gwangsan-gu": "광산구", "Gwangyang-si": "광양시", "Goheung-gun": "고흥군", "Wando-gun": "완도군", "Muan-gun": "무안군", "Mokpo-si": "목포시",
          "Michuhol-gu [Nam-gu]": "미추홀구", "Dongdaemun-gu": "동대문구", "Seongdong-gu": "성동구", "Dongjak-gu": "동작구", "Mapo-gu": "마포구",
          "Yeongdeungpo-gu": "영등포구", "Yeosu-si": "여수시", "Jindo-gun": "진도군", "Sinan-gun": "신안군",
          "Pohang-si": "포항시", "Cheongju-si": "청주시", "Cheonan-si": "천안시", "Yongin-si": "용인시", "Changwon-si": "창원시", "Ansan-si": "안산시", "Yeoju": "여주시"}
if C == "KOR":
    ko.update({p["id"]: KO_FIX[p["name"]] for p in P if p["name"] in KO_FIX})
    ko.update({p["id"]: "서구" for p in P if p["label"] == "인천 Seo-gu [West District]"})
DIR = {"Jung": "중구", "Dong": "동구", "Seo": "서구", "Nam": "남구", "Buk": "북구"}
for p in P:
    if p["id"] in ko or C != "KOR": continue
    if p["name"] in KO_FIX: ko[p["id"]] = KO_FIX[p["name"]]
    elif p["name"].split("-")[0] in DIR and p["name"].split(" ")[0].endswith("-gu"): ko[p["id"]] = DIR[p["name"].split("-")[0]]
missing = [p["label"] for p in P if p["id"] not in ko]
print("한글 이름", len(ko), "/", len(P), "· 영문 유지:", missing)

# ---------- 지도: 시·군·구 경계 (소수 3자리)
def rings(g): return g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
def simp(g):
    out = []
    for poly in rings(g):
        rr_ = []
        for ring in poly[:1]:
            pts, last = [], None
            for x, y in ring:
                q = (round(x, 3), round(y, 3))
                if q != last: pts.append(q); last = q
            if len(pts) >= 4: rr_.append([c for q in pts for c in (int(q[0] * 1000), int(q[1] * 1000))])
        if rr_: out.append(rr_[0])
    return out

# ---------- 감지 점: 기준 위성 (2018-04 전 S-NPP, 그 뒤 NOAA-20), 2012년 전은 MODIS. 0.01° 칸·하루 하나로
hs = pd.read_csv(O / "hotspots_clean.csv", parse_dates=["acq_date"])
hs = hs[((hs.sensor == "MODIS") & (hs.acq_date < "2012-02-01")) |
        ((hs.sensor == "VIIRS") & (hs.acq_date >= "2012-02-01") & (hs.acq_date < "2018-04-01")) |
        ((hs.sensor == "N20") & (hs.acq_date >= "2018-04-01"))].copy()
hs["cell"] = (hs.latitude / 0.01).round().astype(int).astype(str) + "_" + (hs.longitude / 0.01).round().astype(int).astype(str)
hs = hs.drop_duplicates(["cell", "acq_date"]).reset_index(drop=True)
xy = hs[["longitude", "latitude"]].to_numpy()
idx = {p["id"]: i for i, p in enumerate(P)}
reg = np.full(len(xy), -1)
for sid, f in full.items():
    if sid not in idx: continue
    pts = np.concatenate([np.asarray(q[0]) for q in rings(f["geometry"])]); x0, y0 = pts.min(0); x1, y1 = pts.max(0)
    c = np.where((reg < 0) & (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1))[0]
    if not len(c): continue
    m = np.zeros(len(c), bool)
    for q in rings(f["geometry"]):
        a = MP(np.asarray(q[0])).contains_points(xy[c])
        for h in q[1:]: a &= ~MP(np.asarray(h)).contains_points(xy[c])
        m |= a
    reg[c[m]] = idx[sid]
own = np.concatenate([[idx.get(sid, -1)] * sum(len(q[0]) for q in rings(f["geometry"])) for sid, f in full.items()])
tree = cKDTree(np.concatenate([np.asarray(q[0]) for f in full.values() for q in rings(f["geometry"])]))
o = np.where(reg < 0)[0]; dd, jj = tree.query(xy[o]); reg[o[dd <= 0.03]] = own[jj[dd <= 0.03]]
hs["reg"] = reg
pts, ptsN, PTS_MAX = {}, {}, 4000   # 한 달 점이 많으면(캘리포니아·BC 대형 산불 달) 고르게 표본만 보냄
for (ym), g in hs.groupby(hs.acq_date.dt.strftime("%Y-%m")):
    ptsN[ym] = len(g)
    if len(g) > PTS_MAX: g = g.sample(PTS_MAX, random_state=0).sort_values("acq_date")
    pts[ym] = [v for lo, la, d, r in zip(g.longitude, g.latitude, g.acq_date.dt.day, g.reg) for v in (int(round(lo * 1000)), int(round(la * 1000)), int(d), int(r))]
print("감지 점", len(hs), "· 지역 밖", int((reg < 0).sum()))

# ---------- 랜딩: 이어 붙이기(보정 전) vs 보정 후, 나라 연간 화재 칸
raw = pd.read_csv(O / "hotspots_clean.csv", parse_dates=["acq_date"])
raw["cell"] = (raw.latitude / 0.01).round().astype(int).astype(str) + "_" + (raw.longitude / 0.01).round().astype(int).astype(str)
raw = raw.drop_duplicates(["sensor", "cell", "acq_date"])
yrs = list(range(2001, 2026))
modis_y = raw[raw.sensor == "MODIS"].groupby(raw.acq_date.dt.year).size()
snpp_y = raw[raw.sensor == "VIIRS"].groupby(raw.acq_date.dt.year).size()
before = [int(modis_y.get(y, 0)) if y < 2012 else int(snpp_y.get(y, 0)) for y in yrs]
calm = pd.DataFrame(cal)
after = [r1(calm[calm.year == y].value.sum()) for y in yrs]
print("보정 전", before, "\n보정 후", after)

# ---------- 지역 시계열
nat = {"value": [r1(c["value"]) for c in cal], "rank": [c["rank_in_month"] for c in cal], "n": [c["years_in_month"] for c in cal],
       "ratio": [c["ratio_to_median"] for c in cal], "quality": [c["quality"] for c in cal], "partial": [c["partial"] for c in cal],
       "source": [c["source"] for c in cal], "med": [r1(c["median"]) for c in clim], "lo": [r1(c["band_low"]) for c in clim], "hi": [r1(c["band_high"]) for c in clim],
       "risk": meta["regions"]["national_risk"]["months"], "basis": "보정 25년", "suff": "충분"}
assert len(nat["value"]) == len(months)
prov = {}
for k, v in cprov["provinces"].items():
    prov[k] = {"value": [r1(x) for x in v["value"]], "rank": v["rank"], "n": v["years_in_month"], "ratio": v["ratio_to_median"],
               "med": [r1(x) for x in v["median_by_month"]], "lo": [r1(x) for x in v["band_low_by_month"]], "hi": [r1(x) for x in v["band_high_by_month"]],
               "risk": v["risk_months"], "basis": v["basis"], "suff": v["sufficiency"], "err": v["loyo_error"], "regions": [idx[i] for i in v["regions"] if i in idx]}
dist = []
for p, f in zip(P, feats):
    c = creg["regions"][p["id"]]["viirs"]
    dist.append({"id": p["id"], "ko": ko.get(p["id"]), "en": p["name"], "prov": p["province"], "suff": p["sufficiency"],
                 "value": [r1(x) for x in c["value"]], "rank": c["rank"], "n": c["years_in_month"],
                 "med": [r1(x) for x in c["median_by_month"]], "lo": [r1(x) for x in c["band_low_by_month"]], "hi": [r1(x) for x in c["band_high_by_month"]],
                 "risk": p["risk_months"], "riskFrom": p["risk_from"], "nb": [idx[n] for n in p["neighbors"] if n in idx],
                 "ref": (p["fallback"] or {}).get("ref_province"), "geom": simp(f["geometry"])})

if "bins" not in LABELS:   # 지도 구역 색 경계: 2012-02~ 하위 구역-달의 0이 아닌 값 사분위 (한국은 3·10·30 고정)
    vv = np.array([x for d in dist for m_, x in zip(months, d["value"]) if x and m_ >= "2012-02"])
    LABELS["bins"] = [float(np.round(np.quantile(vv, q))) for q in (.25, .5, .75)]
ev = meta.get("external_validation", {})
D = {"months": months, "nat": nat, "prov": prov, "dist": dist, "pts": pts, "ptsN": ptsN, "labels": LABELS,
     "landing": {"years": yrs, "before": before, "after": after,
                 "kosis": (ev.get("kosis_annual") or ev.get("annual_records") or {}).get("independent_break_test"),
                 "pettitt": {"before": meta["break_test"]["이어 붙이기"]["sensor_break_p"], "after": meta["break_test"]["H 하모니제이션"]["sensor_break_p"]},
                 "jump": {k: {"ratio": meta["break_test"][k]["ratio_after_2012"], "ci": meta["break_test"][k]["ratio_ci95"], "before": meta["break_test"][k]["ratio_before_2012"]} for k in ["이어 붙이기", "H 하모니제이션"]},
                 "detect": ev.get("detection_by_size")},
     "samples": {   # 월별 인사이트 샘플 (tools/mockup_extract.py 의 CFG 와 같게)
         "KOR": {"91817680B75376031789242": ["uiseong", "2025-03"], "91817680B50485812736392": ["goseong", "2019-04"], "91817680B11201690622195": ["daegu-jung", "2025-03"]},
         "CAL": {"52423323B88547646561946": ["butte-2018", "2018-11"], "52423323B20293708991619": ["fresno-2020", "2020-09"], "52423323B75131784459442": ["sanmateo-2020", "2020-08"]},
         "BC": {"BC-RD-60": ["peace-2023", "2023-05"], "BC-RD-82": ["okanagan-2023", "2023-08"], "BC-RD-151": ["thompson-2021", "2021-07"]}}[C],
     "dataEnd": meta["data_range"]["noaa20"][1]}
# ---------- 랜딩 숫자 카드: 나라별 값을 mockup/site/landing.js 한 파일에 모음 (다른 나라 값은 그대로 둠)
OFF = B / "inputs" / "official"
CASE = {"KOR": "2025-03", "CAL": "2020-09", "BC": "2023-05"}[C]   # 숫자 카드 ②의 대표 달
if C == "KOR":   # 공식 피해면적: 한국은 KOSIS 2025년 값(산림청)
    area = {"year": 2025, "ha": 105099, "source": "KOSIS", "record": True}
else:
    if C == "CAL":
        x = pd.read_csv(OFF / "CAL" / "cal_fire_perimeters_2001_2025.csv"); ya = x.groupby("YEAR_").GIS_ACRES.sum() * 0.404686
    else:
        x = pd.read_csv(OFF / "BC" / "bc_fire_incidents_2001_2025.csv"); x = x[x.FIRE_TYPE == "Fire"]; ya = x.groupby("FIRE_YEAR").CURRENT_SIZE.sum()
    ya = ya.loc[2001:2025]; yb = int(ya.idxmax())
    area = {"year": yb, "ha": int(round(ya.max())), "source": LABELS["official"], "record": True}
ci = months.index(CASE); risk = nat["risk"]
base = [(m_, v) for m_, v in zip(months, nat["value"]) if "2001" <= m_ < "2026" and v is not None]
share = sum(v for m_, v in base if int(m_[5:]) in risk) / sum(v for _, v in base)
ib = ev.get("annual_records", {}).get("independent_break_test", {})
kb = (ev.get("kosis_annual") or {}).get("independent_break_test") or {k.split(" / ")[0]: v for k, v in ib.items() if k.endswith("공식 건수")}
det = ev.get("detection_by_size") or {}
LND = {"labels": LABELS, "area": area,
       "case": {"month": CASE, "value": nat["value"][ci], "ratio": nat["ratio"][ci], "rank": nat["rank"][ci], "n": nat["n"][ci]},
       "risk": {"months": risk, "share": round(share, 3)},
       "years": yrs, "before": before, "after": after, "kosis": kb,
       "jump": {k: {"ratio": meta["break_test"][k]["ratio_after_2012"], "ci": meta["break_test"][k]["ratio_ci95"], "before": meta["break_test"][k]["ratio_before_2012"]} for k in ["이어 붙이기", "H 하모니제이션"]},
       "detect": det, "detect_n": int(sum(v["n"] for v in det.values())) if det else 0,
       "n_regions": len(dist), "n_prov": len(prov),
       "places": [[d["ko"] or d["en"], d["prov"], i] for i, d in enumerate(dist)]}   # 첫 화면 검색용 (이름, 상위 구역, 대시보드 d= 번호)
LJ = B / "mockup/site/landing.js"
cur = json.loads(LJ.read_text(encoding="utf-8")[len("window.LANDING="):].rstrip().rstrip(";")) if LJ.exists() else {}
cur[C] = LND
LJ.write_text("window.LANDING=" + json.dumps(cur, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
print("랜딩", C, {k: LND[k] for k in ["area", "case", "risk"]}, "kosis", {k: v.get("after_over_before") for k, v in kb.items()})

OUT.parent.mkdir(parents=True, exist_ok=True)
s = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
OUT.write_text("window.BURN=" + s + ";\n", encoding="utf-8")
print(OUT, f"{len(s)/1e6:.2f} MB")
