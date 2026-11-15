"""화면용 지역 이름 파일을 만든다 (노트북이 읽음).

- boundaries/<지역>/names-<지역>.csv : 하위 구역 shapeID → name_ko (한국어 이름)
    KOR  : 백엔드 공식 이름표 names/KOR_district_ko.csv (영광군 보강 포함)
    그 밖: tools/transliterate.py MANUAL (팀원 작성 음역 사전)
- boundaries/<지역>/geoBoundaries-<지역>-ADM1.geojson 속성 name_ko·name_en (상위 단위)
    name_ko: KOR은 시·도 약칭(노트북 PROVINCE_KO), 그 밖은 transliterate.py PROVINCE_MANUAL
    name_en: KOR은 shapeName, 그리스·칠레는 영어 관용 이름(아래 EN), CAL·BC·NSW는 shapeName

또 칠레 경계의 이름 오류를 바로잡는다: geoBoundaries CHL ADM3가 타라파카의 Pozo Almonte를 "Tocopilla"로 적음
(안토파가스타의 진짜 Tocopilla와 이름이 겹침). shapeID는 그대로라 값에는 영향이 없다.

사용: python3 tools/build_names.py [백엔드 KOR 이름표 경로]
"""
import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KOR_CSV = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/backend/common/src/main/resources/names/KOR_district_ko.csv")

spec = importlib.util.spec_from_file_location("transliterate", ROOT / "tools" / "transliterate.py")
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)

KOR_PROVINCE_KO = {"Seoul": "서울", "Busan": "부산", "Daegu": "대구", "Incheon": "인천", "Gwangju": "광주", "Daejeon": "대전",
                   "Ulsan": "울산", "Sejong": "세종", "Gyeonggi": "경기", "Gangwon": "강원", "North Chungcheong": "충북",
                   "South Chungcheong": "충남", "North Jeolla": "전북", "South Jeolla": "전남", "North Gyeongsang": "경북",
                   "South Gyeongsang": "경남", "Jeju": "제주"}
EN = {  # 그리스·칠레 상위 단위의 영어 관용 이름 (shapeName은 그리스어 속격 로마자·스페인어)
    "Agion Oros": "Mount Athos", "Anatolikis Makedonias kai Thrakis": "Eastern Macedonia and Thrace", "Attikis": "Attica",
    "Dytikis Elladas": "Western Greece", "Dytikis Makedonias": "Western Macedonia", "Ionion Nison": "Ionian Islands",
    "Ipeiroy": "Epirus", "Kentrikis Makedonias": "Central Macedonia", "Kritis": "Crete", "Notioy Aigaioy": "South Aegean",
    "Peloponnisoy": "Peloponnese", "Stereas Elladas": "Central Greece", "Thessalias": "Thessaly", "Voreioy Aigaioy": "North Aegean",
    "Región Metropolitana de Santiago": "Santiago Metropolitan", "Región de Antofagasta": "Antofagasta",
    "Región de Arica y Parinacota": "Arica y Parinacota", "Región de Atacama": "Atacama",
    "Región de Aysén del Gral.Ibañez del Campo": "Aysén", "Región de Coquimbo": "Coquimbo",
    "Región de La Araucanía": "La Araucanía", "Región de Los Lagos": "Los Lagos", "Región de Los Ríos": "Los Ríos",
    "Región de Magallanes y Antártica Chilena": "Magallanes", "Región de Tarapacá": "Tarapacá",
    "Región de Valparaíso": "Valparaíso", "Región de Ñuble": "Ñuble", "Región del Bío-Bío": "Biobío",
    "Región del Libertador Bernardo O'Higgins": "O'Higgins", "Región del Maule": "Maule"}
CHL_FIX = {"31580391B91621176177599": "Pozo Almonte"}   # Tarapacá, geoBoundaries 표기 "Tocopilla"


def rw(path, fn):
    g = json.loads(path.read_text(encoding="utf-8"))
    fn(g)
    path.write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    return g


for c in ["KOR", "CAL", "BC", "GRC", "CHL", "NSW"]:
    d = ROOT / "boundaries" / c
    if c == "CHL":   # 이름 오류 바로잡기 (원본·지도용 둘 다)
        for f in ["geoBoundaries-CHL-ADM2.geojson", "geoBoundaries-CHL-ADM2_simplified.geojson"]:
            def fix(g):
                for ft in g["features"]:
                    if ft["properties"]["shapeID"] in CHL_FIX:
                        ft["properties"]["shapeName"] = CHL_FIX[ft["properties"]["shapeID"]]
            rw(d / f, fix)

    def adm1(g):
        for ft in g["features"]:
            p = ft["properties"]
            n = p["shapeName"]
            p["name_ko"] = KOR_PROVINCE_KO[n] if c == "KOR" else tr.PROVINCE_MANUAL[n]
            p["name_en"] = EN.get(n, n)
    rw(d / f"geoBoundaries-{c}-ADM1.geojson", adm1)

    feats = json.loads((d / f"geoBoundaries-{c}-ADM2.geojson").read_text(encoding="utf-8"))["features"]
    patch = d / f"patch-{c}-ADM2.geojson"
    if patch.exists():
        feats += json.loads(patch.read_text(encoding="utf-8"))["features"]
    if c == "KOR":
        ko = {r["id"]: r["label_ko"] for r in csv.DictReader(open(KOR_CSV, encoding="utf-8"))}
    rows, missing = [], []
    for ft in feats:
        sid, name = ft["properties"]["shapeID"], ft["properties"]["shapeName"]
        k = ko.get(sid) if c == "KOR" else tr.MANUAL.get(name)
        if not k:
            missing.append(name)
        rows.append((sid, name, k or ""))
    with open(d / f"names-{c}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")   # LF 고정 (.gitattributes와 같게)
        w.writerow(["id", "name", "name_ko"])
        w.writerows(rows)
    print(f"{c}: 하위 구역 {len(rows)}곳, 한국어 이름 없음 {len(missing)} {missing[:5]}")
