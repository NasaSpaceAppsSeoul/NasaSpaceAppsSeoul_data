import sys
import nbformat as nbf

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
py = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

# --- cell 0
md(r'''
# Burnline 하모니제이션 노트북

MODIS와 VIIRS 핫스팟을 하나의 시계열로 잇고, 웹사이트가 읽을 JSON을 만듭니다.

**기준 단위는 VIIRS NOAA-20**입니다. MODIS(Terra/Aqua)와 S-NPP는 운영이 끝났거나 끝나 가므로, 지금 관측 중인 NOAA-20 값을 그대로 쓰고 과거 위성 값을 거기에 맞춥니다.

```
Terra 단독(2001~2002.07) ─①→ MODIS(Terra+Aqua) ─②→ S-NPP ─③→ NOAA-20 (기준)
                                                   NOAA-21 ─④→ NOAA-20 (예비, NOAA-20 이상 시)
```

**흐름:** ① 설정 → ② 불러오기 → ③ 정리(고정 열원·신뢰도) → ④ 화재 감지일 집계 → ⑤ 보정 계수 → ⑥ 교차검증 → ⑥-3 위성 사슬(Terra·NOAA-20·NOAA-21) → ⑦ 단절 검정 → ⑧ 차트 → ⑩ FRP → ⑪ 2×2 유형 → ⑫ 품질 → ⑬ 웹용 파일 → ⑭ 시·군·구 달력 → ⑮ 지역별 신뢰 기준·대체 지역·인접 경고

**다른 나라나 지역에 쓰려면** ① 설정 셀만 바꾸고 *Run All* 하면 됩니다.
''')

# --- cell 1
md(r'''
## ① 설정
''')

# --- cell 2
py(r'''
from pathlib import Path

import os
# 나라(지역) 선택: 환경 변수 BURNLINE_COUNTRY (기본 KOR). 예) BURNLINE_COUNTRY=CAL jupyter nbconvert ...
COUNTRY = os.environ.get("BURNLINE_COUNTRY", "KOR")   # 출력 폴더·경계 폴더 이름
# 원자료 폴더 (기본: 저장소의 inputs/, 다른 곳이면 환경 변수 BURNLINE_DATA). 구조는 고정:
#   inputs/firms/<지역>/{modis,snpp,noaa20,noaa21}/fire_archive_*.csv, fire_nrt_*.csv   (FIRMS 다운로드 zip을 그대로 풀기)
#   inputs/official/<지역>/<공식 기록 파일>
_IN = Path(os.environ.get("BURNLINE_DATA", "inputs")).expanduser()
_FIRMS = lambda c: dict(MODIS_DIR=_IN / "firms" / c / "modis", VIIRS_DIR=_IN / "firms" / c / "snpp",
                        N20_DIR=_IN / "firms" / c / "noaa20", N21_DIR=_IN / "firms" / c / "noaa21")
_OFF = lambda c, f: _IN / "official" / c / f
CONFIGS = {
    "KOR": dict(
        **_FIRMS("KOR"),
        KFS_FILE=_OFF("KOR", "산불통계.xlsx"),                                   # 산림청 산불 통계 (⑰ 외부 검증, 없으면 건너뜀)
        KOSIS_FILE=_OFF("KOR", "시도별_산불발생_현황_20261107002501.csv"),       # KOSIS 시도별 산불발생 현황 2001~ (⑰)
        CLIP_TO_ADM1=False,      # 한국은 바다 칸도 나라 합계에 넣음
        KM_LON=88.8,             # 경도 1° ≈ km (위도 36°)
        CASE_MONTH="2025-03",    # 예시 달 (지도·상위 지역 표)
        CASE_EVENT=("2025-03-20", "2025-03-31", ["Uiseong-gun", "Andong-si", "Cheongsong-gun", "Yeongyang-gun", "Yeongdeok-gun"]),
        KNOWN_FIRES={"의성 2025-03": ("2025-03-22", 36.39, 128.65), "울진 2022-03": ("2022-03-04", 37.08, 129.35),
                     "고성 2019-04": ("2019-04-04", 38.22, 128.54), "강릉·동해 2019-04": ("2019-04-04", 37.72, 128.95)}),
    "CAL": dict(
        **_FIRMS("CAL"),
        KFS_FILE=None, KOSIS_FILE=None,                                    # 외부 검증 자료 아직 없음 → ⑰ 건너뜀
        CLIP_TO_ADM1=True,       # FIRMS 사각형 범위에 섞인 네바다·멕시코·바다 탐지를 주 경계로 잘라냄
        KM_LON=88.8,             # 위도 37° 부근
        CASE_MONTH="2020-08",
        CASE_EVENT=("2018-11-07", "2018-11-30", ["Butte", "Plumas", "Yuba", "Tehama", "Glenn"]),   # Camp Fire
        KNOWN_FIRES={"Camp 2018-11": ("2018-11-08", 39.81, -121.44), "Dixie 2021-07": ("2021-07-13", 39.87, -121.39),
                     "Creek 2020-09": ("2020-09-04", 37.20, -119.27), "Park 2024-07": ("2024-07-24", 39.79, -121.75)}),   # 묶음은 NOAA-20(2018-04~) 기준이라 그 뒤 산불만
    "BC": dict(   # 캐나다 브리티시컬럼비아. 하위 단위 = regional district 28곳 (BC Data Catalogue, Open Government Licence – BC)
        **_FIRMS("BC"),
        KFS_FILE=None, KOSIS_FILE=None,                                    # 외부 검증 자료(CNFDB) 아직 없음 → ⑰ 건너뜀
        CLIP_TO_ADM1=True,       # 사각형 범위의 앨버타·유콘·미국·바다 탐지 제외
        KM_LON=66.8,             # 위도 53° 부근
        CASE_MONTH="2023-08",
        CASE_EVENT=("2023-08-14", "2023-08-31", ["Central Okanagan", "North Okanagan", "Okanagan-Similkameen", "Thompson-Nicola", "Columbia Shuswap"]),   # McDougall Creek
        KNOWN_FIRES={"Lytton 2021-06": ("2021-06-30", 50.23, -121.58), "McDougall Creek 2023-08": ("2023-08-15", 49.88, -119.55),
                     "Donnie Creek 2023-05": ("2023-05-12", 57.20, -121.20)}),   # 위치는 대략값
    "GRC": dict(   # 그리스 전체 (FIRMS 국가 선택). 상위 = 주 13 + 아토스산, 하위 = 시군 325 (geoBoundaries GRC ADM2/ADM3)
        **_FIRMS("GRC"),
        KFS_FILE=None, KOSIS_FILE=None,
        CLIP_TO_ADM1=True,       # FIRMS 국가 영역에 국경 너머(터키·알바니아·북마케도니아·불가리아) 탐지 약 1,400개가 섞여 있어 그리스 경계로 자름
        KM_LON=87.1,             # 위도 38.5° 부근
        CASE_MONTH="2023-08",
        CASE_EVENT=("2023-08-19", "2023-09-08", ["Alexandroupolis", "Soufliou", "Didymoteichou", "Orestiadas"]),   # 에브로스(다디아)
        KNOWN_FIRES={"Evros 2023-08": ("2023-08-19", 40.94, 26.08), "Evia 2021-08": ("2021-08-03", 38.79, 23.32),
                     "Rhodes 2023-07": ("2023-07-18", 36.23, 27.94), "Varnavas 2024-08": ("2024-08-11", 38.24, 23.93)}),   # 소방청 기록 좌표
    "CHL": dict(   # 칠레 전체 (FIRMS 국가 선택, 이스터섬 포함). 상위 = 주 16, 하위 = 시군 345 (geoBoundaries CHL ADM1/ADM3, BCN)
        **_FIRMS("CHL"),
        KFS_FILE=None, KOSIS_FILE=None,
        CLIP_TO_ADM1=False,
        KM_LON=None,             # 남위 17~56°라 값 하나로는 안 맞음 → 위도별 111.32·cos(위도)
        SEASON_START=7,          # 남반구: 산불 시즌 7월~다음 해 6월 (CONAF 집계 단위)
        CASE_MONTH="2023-02",
        CASE_EVENT=("2023-02-01", "2023-02-20", ["Nacimiento", "Santa Juana", "Negrete", "Florida", "Galvarino"]),
        KNOWN_FIRES={"Santa Ana (Nacimiento) 2023-02": ("2023-02-02", -37.44, -72.85), "El Cortijo (Florida) 2023-02": ("2023-02-02", -36.80, -72.85),
                     "Las Tablas (Valparaíso) 2024-02": ("2024-02-02", -33.19, -71.52), "Colonia Sur (Cochrane) 2019-02": ("2019-02-04", -47.32, -72.92)}),   # CONAF 좌표
    "NSW": dict(   # 호주 뉴사우스웨일스. FIRMS 사각형(140.9~153.7°E, 37.6~28.1°S)을 NSW 경계로 자름. 하위 = 지방정부 129 (ABS 2022)
        **_FIRMS("NSW"),
        KFS_FILE=None, KOSIS_FILE=None,
        CLIP_TO_ADM1=True,       # 사각형 안의 빅토리아·남호주·퀸즐랜드·ACT 탐지 제외 (ADM1 파일은 NSW 하나, ACT는 구멍)
        KM_LON=93.4,             # 위도 33° 부근
        SEASON_START=7,
        CASE_MONTH="2019-12",
        CASE_EVENT=("2019-11-25", "2020-01-15", ["Shoalhaven", "Eurobodalla", "Bega Valley", "Wingecarribee", "Wollondilly"]),   # Black Summer
        KNOWN_FIRES={"Gospers Mountain 2019-10": ("2019-10-25", -33.23, 150.50), "Currowan 2019-11": ("2019-11-25", -35.18, 150.28),
                     "Green Wattle Creek 2019-11": ("2019-11-26", -34.10, 150.23), "Dunns Road 2019-12": ("2019-12-27", -35.66, 148.18)}),   # NPWS 경계 중심점
}
for _c in CONFIGS.values():
    _c.setdefault("EXT_POINTS", None)   # 좌표가 있는 공식 산불 기록 CSV (⑰). 한국은 이름 맞추기를 쓰는 KFS_FILE
    _c.setdefault("ANNUAL_COUNTS", None)   # 연(시즌)별 공식 건수·면적 CSV (season_start_year 또는 year, n_fires, area_ha). 있으면 ⑰-2 단절 검정에 씀
    _c.setdefault("SEASON_START", 1)    # 시즌 시작 월. 남반구는 7 (7월~다음 해 6월)
    _c.setdefault("DETECT_POINTS", None)   # 크기별 감지율 전용 개별 산불 기록 (모든 크기, 일부 기간만 있을 때). 없으면 EXT_POINTS를 씀
    _c.setdefault("VALIDATION_NOTE", None)   # ⑰ 공식 기록 검정 해석 메모 (meta.external_validation.annual_records.note)
# 좌표 기록의 열 이름: 날짜, 위도, 경도, 원인, 면적(+ ha 환산 배수), 장소, 남길 행 조건
CONFIGS["BC"].update(EXT_POINTS=_OFF("BC", "bc_fire_incidents_2001_2025.csv"),
                     EXT_NAME="BC Wildfire Service 과거 산불 기록 (BC Data Catalogue, PROT_HISTORICAL_INCIDENTS_SP)",
                     EXT_COLS=dict(date="IGNITION_DATE", lat="LATITUDE", lon="LONGITUDE", cause="FIRE_CAUSE", size="CURRENT_SIZE", to_ha=1.0,
                                   place="GEOGRAPHIC_DESCRIPTION", keep=("FIRE_TYPE", "Fire")))
CONFIGS["CAL"].update(EXT_POINTS=_OFF("CAL", "cal_fire_perimeters_2001_2025.csv"),
                      EXT_NAME="CAL FIRE FRAP 화재 경계 (California Fire Perimeters, 경계 중심점)",
                      EXT_COLS=dict(date="ALARM_DATE", lat="LATITUDE", lon="LONGITUDE", cause="CAUSE", size="GIS_ACRES", to_ha=0.404686,
                                    place="FIRE_NAME", keep=None))
_EXT3 = dict(date="date", lat="lat", lon="lon", cause="cause", size="area_ha", to_ha=1.0, place="place", keep=None)   # 정리한 CSV 공통 열
CONFIGS["GRC"].update(EXT_POINTS=_OFF("GRC", "grc_fire_service_2000_2024.csv"),
                      EXT_NAME="그리스 소방청 산림 화재 기록 (Hellenic Fire Service, 2000~2024)", EXT_COLS=_EXT3,
                      VALIDATION_NOTE=("공식 건수 대비 단절이 보정 후 0.71배로 나오는 것은 보정 실패가 아니다. 위성끼리 단절은 1.01배이고, "
                                       "보정이 없는 Aqua 단독 화재 칸도 공식 1,000건당 107(2003~11) → 69(2017~21)으로 같이 줄었다. "
                                       "하락은 10월(−75%, 북부 마케도니아·트라키 평야의 수확 뒤 잔재 소각으로 보임)에 몰려 있고 공식 10월 건수는 거의 그대로다. "
                                       "9~11월을 빼면 0.93배, 6~8월만 보면 0.94배다. 위성이 보는 가을 농업 소각이 소방청 기록과 따로 움직여 공식 건수 검정의 가정이 깨지므로 판단 보류로 둔다."))
CONFIGS["CHL"].update(EXT_POINTS=_OFF("CHL", "chl_conaf_large_fires_1985_2024.csv"),
                      EXT_NAME="CONAF 대형 산불 (200 ha 이상, 1985~2024)", EXT_COLS=_EXT3,
                      ANNUAL_COUNTS=_OFF("CHL", "chl_conaf_national_season_1984_2024.csv"),
                      ANNUAL_NAME="CONAF 시즌별 전국 산불 건수·면적 (모든 크기)",
                      DETECT_POINTS=_OFF("CHL", "chl_conaf_fires_allsizes_2002_2020.csv"),
                      DETECT_NAME="CONAF 개별 산불 기록 (모든 크기, 2002~05·2018~20 시즌, doi:10.71578/UXAUN5)")
CONFIGS["NSW"].update(EXT_POINTS=_OFF("NSW", "nsw_npws_wildfires_2000_2026.csv"),
                      EXT_NAME="NSW NPWS Fire History (산불만, 경계 중심점)", EXT_COLS=_EXT3)
globals().update(CONFIGS[COUNTRY])
# 경도 1°의 km: KM_LON이 있으면 그 값, 없으면 위도별 111.32·cos(위도) (남북으로 긴 칠레)
KMX = (lambda lat: KM_LON) if KM_LON else (lambda lat: 111.32 * np.cos(np.radians(lat)))

# 하위 지역만 보고 싶을 때: (위도 최소, 위도 최대, 경도 최소, 경도 최대). 예) 경상북도 대략 (35.6, 37.6, 127.8, 129.6)
BBOX = None

GRID = 0.01            # 화재 감지일 집계 격자 (도, 약 1 km = MODIS 픽셀 크기). ⑥-2 민감도 표 참고
GRIDS_TO_TEST = [0.1, 0.05, 0.02, 0.01]
YEARS = (2001, 2025)   # 기후값(평년) 계산에 쓰는 완전한 연도
OVERLAP = (2012, 2025) # MODIS와 S-NPP가 함께 관측한 완전한 연도 → 보정 계수의 근거
OVERLAP_SN = (2019, 2025)   # S-NPP와 NOAA-20이 함께 관측한 완전한 연도 (NOAA-20은 2018-04부터)
OVERLAP_JN = (2024, 2025)   # NOAA-21과 NOAA-20 (NOAA-21은 2023-03부터)
TERRA_YEARS = (2003, 2011)  # Terra 단독 → Terra+Aqua 계수 (Aqua는 2002-07-11부터)
MODIS_MIN_CONF = 30    # MODIS 신뢰도(0~100) 최소값
VIIRS_CONF = {"n", "h"}  # VIIRS 신뢰도: l(low) 제외
STATIC_GRID = 0.02     # NRT 고정 열원 마스크 격자 (약 2 km)
STATIC_MIN_DAYS = 3    # 아카이브에서 type 2·3이 서로 다른 날 이만큼 잡힌 격자는 아카이브·NRT 모두 제외 (점 개수가 아니라 날짜 수: 하루짜리 산불이 빠지지 않게)
SHRINK = 20            # 월별 보정 계수를 전체 계수 쪽으로 당기는 강도 (감지일 수 단위)
WINDOW = 2             # 시간 가변 보정에서 앞뒤로 쓰는 연도 수
TYPE_PCT = 0.90        # 2×2 유형: 같은 달 평년 분포에서 이 분위수를 넘으면 "평년보다 높음"
BAND_Q = (0.15, 0.85)  # 보통 해 범위: 같은 달 15~85 퍼센타일 …
BAND_NOISE = 2         # … 에 위성 표본 잡음 여유 ±2√평년(평년 < 1이면 √1)을 더함. 두 위성 판정 일치 81% (q25~q75는 64%)
LOW_COUNT = 5          # 같은 달 평년(중앙값) 감지일이 이보다 작으면 배수 해석이 불안정 → 품질 한 단계 낮춤

OUT_DIR = Path("output") / COUNTRY
''')

# --- cell 3
md(r'''
## ② 불러오기

정식 아카이브(`fire_archive_*`)와 최근 준실시간(`fire_nrt_*`)을 합칩니다. NRT는 아카이브가 끝난 다음 날짜만 씁니다.

**날짜 기준:** FIRMS의 `acq_date`·`acq_time`은 세계 표준시(UTC)입니다. 그대로 쓰면 한국 새벽 1~3시의 NOAA-20 밤 관측이 전날로 들어갑니다. 그래서 모든 날짜를 **현지 태양시(UTC + 경도 ÷ 15시간)**의 날짜로 바꿔 씁니다. 시간대 표 없이 어느 나라에나 같은 식이 맞고, 한국에서는 한국 시간과 30분 안쪽으로 차이 납니다. 원래 UTC 날짜는 `acq_date_utc`에 남깁니다.
''')

# --- cell 4
py(r'''
import json, datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from matplotlib import font_manager
_fonts = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = next((f for f in ["AppleGothic", "Malgun Gothic", "NanumGothic", "Noto Sans CJK KR"] if f in _fonts), "DejaVu Sans")
plt.rcParams["axes.unicode_minus"] = False

def load(folder, sensor):
    arc = pd.concat([pd.read_csv(p) for p in sorted(folder.glob("fire_archive_*.csv"))], ignore_index=True)
    arc["src"] = "archive"
    nrt_files = sorted(folder.glob("fire_nrt_*.csv"))
    parts = [arc]
    if nrt_files:
        nrt = pd.concat([pd.read_csv(p) for p in nrt_files], ignore_index=True)
        nrt["src"] = "nrt"
        parts.append(nrt[pd.to_datetime(nrt.acq_date) > pd.to_datetime(arc.acq_date).max()])
    d = pd.concat(parts, ignore_index=True)
    # FIRMS 날짜·시각은 세계 표준시(UTC). 현지 태양시(UTC + 경도 ÷ 15시간)의 날짜로 바꿔, 한밤중 관측이 전날로 들어가지 않게 함.
    # 시간대 표가 없어도 어느 나라에나 같은 식이 맞고, 한국은 한국 시간과 30분 안쪽 차이.
    t = pd.to_numeric(d.acq_time, errors="coerce").fillna(0).astype(int)
    utc = pd.to_datetime(d.acq_date) + pd.to_timedelta(t // 100, unit="h") + pd.to_timedelta(t % 100, unit="m")
    d["acq_date_utc"] = pd.to_datetime(d.acq_date)
    d["acq_date"] = (utc + pd.to_timedelta(d.longitude / 15, unit="h")).dt.normalize()
    d["sensor"] = sensor
    return d

modis_raw = load(MODIS_DIR, "MODIS")
viirs_raw = load(VIIRS_DIR, "VIIRS")
n20_raw = load(N20_DIR, "N20")
n21_raw = load(N21_DIR, "N21")
for d in (modis_raw, viirs_raw, n20_raw, n21_raw):
    print(d.sensor.iat[0], f"현지 날짜가 UTC 날짜와 다른 감지 {(d.acq_date != d.acq_date_utc).mean():.1%}")
    print(d.sensor.iat[0], f"{len(d):,}건", d.acq_date.min().date(), "~", d.acq_date.max().date(),
          "| 아카이브", (d.src == "archive").sum(), "/ NRT", (d.src == "nrt").sum())
''')

# --- cell 5
md(r'''
## ③ 정리: 고정 열원과 낮은 신뢰도 제거

- 아카이브: `type == 0`(식생 화재)만 남깁니다. `type 2`는 공장 같은 고정 열원, `type 3`은 해상입니다.
- **고정 열원 격자 마스크:** 네 위성 아카이브에서 `type 2`·`type 3`이 **서로 다른 날 3일 이상** 잡힌 약 2 km 격자를 모두 모아, 그 격자 안의 감지는 **아카이브와 NRT 모두** 제외합니다. 제철소처럼 큰 시설은 일부 감지가 `type 0`으로 분류되어 새어 들어오기 때문입니다 (예: 포항·당진 부근 VIIRS 수백 건).
- 단계별로 몇 건이 빠졌는지 표로 남깁니다. 이 표는 방법론 페이지에 그대로 쓸 수 있습니다.
''')

# --- cell 6
py(r'''
def key(d, step):
    return (d.latitude / step).round().astype(int).astype(str) + "_" + (d.longitude / step).round().astype(int).astype(str)

# NRT에는 type 열이 없어 위치로 대신 거름: type 2(고정 열원)·type 3(해상·항만 열원)이 반복된 격자를 모두 제외
_st = pd.concat([modis_raw, viirs_raw, n20_raw, n21_raw]).query("type in [2, 3]")
static_days = _st.assign(c=key(_st, STATIC_GRID)).groupby("c").acq_date.nunique()
STATIC_MASK = set(static_days[static_days >= STATIC_MIN_DAYS].index)

if CLIP_TO_ADM1:   # 주(州) 경계 밖 탐지 제외용 다각형
    from matplotlib.path import Path as _MP
    ADM1_CLIP = []
    for f in json.loads((Path("boundaries") / COUNTRY / f"geoBoundaries-{COUNTRY}-ADM1.geojson").read_text(encoding="utf-8"))["features"]:
        g = f["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            ADM1_CLIP.append((_MP(np.asarray(poly[0])), [_MP(np.asarray(h)) for h in poly[1:]]))

def clean(d):
    log = [("원자료", len(d))]
    arc = d.src == "archive"
    d = d[(~arc | (d.type == 0))]
    log.append(("유형 필터 (아카이브 type 0만)", len(d)))
    d = d[~key(d, STATIC_GRID).isin(STATIC_MASK)]
    log.append(("고정 열원 격자 마스크", len(d)))
    if d.sensor.iat[0] == "MODIS":
        d = d[pd.to_numeric(d.confidence, errors="coerce") >= MODIS_MIN_CONF]
    else:
        d = d[d.confidence.isin(VIIRS_CONF)]
    log.append(("낮은 신뢰도 제거", len(d)))
    if BBOX:
        la0, la1, lo0, lo1 = BBOX
        d = d[d.latitude.between(la0, la1) & d.longitude.between(lo0, lo1)]
        log.append(("관심 영역", len(d)))
    if CLIP_TO_ADM1:
        xy = d[["longitude", "latitude"]].to_numpy(); inside = np.zeros(len(d), bool)
        for P in ADM1_CLIP:
            m = P[0].contains_points(xy)
            for h in P[1]:
                m &= ~h.contains_points(xy)
            inside |= m
        d = d[inside]
        log.append(("행정 경계 안", len(d)))
    return d.copy(), log, len(STATIC_MASK)

modis, log_m, n_static_m = clean(modis_raw)
viirs, log_v, n_static_v = clean(viirs_raw)
n20, log_n, _ = clean(n20_raw)
n21, log_j, _ = clean(n21_raw)
filter_log = pd.DataFrame({"단계": [s for s, _ in log_m], "MODIS": [n for _, n in log_m], "VIIRS": [n for _, n in log_v],
                           "NOAA-20": [n for _, n in log_n], "NOAA-21": [n for _, n in log_j]})
filter_log
''')
md(r'''
### ③-2 NRT 대체 필터 검증: 아카이브의 type을 정답으로

NRT에는 `type` 열이 없어서 위치로 대신 거릅니다. 이 규칙이 맞는지 **type이 있는 아카이브에 똑같이 적용해** 확인합니다.

| type | 뜻 | NRT 대체 규칙 |
|---|---|---|
| 0 | 식생 화재 | 남김 |
| 1 | 활화산 | 한국에는 없음 |
| 2 | 그 밖의 고정 열원 (공장 등) | 고정 열원 격자 마스크 |
| 3 | 해상 열원 | 같은 마스크 (type 3이 3번 이상 잡힌 격자) |

한국 자료의 type 3은 먼바다가 아니라 **항만·매립지의 산업 시설**에 몰려 있습니다(대부분 육지 경계 안). 그래서 육지 경계로는 못 거르고, 고정 열원처럼 "반복해서 잡힌 격자"로 거릅니다.

같은 기간 아카이브에서 "type으로 거른 월별 화재 칸"과 "대체 규칙으로 거른 월별 화재 칸"을 비교해, NRT 값이 얼마나 치우칠 수 있는지 봅니다.
''')
py(r'''
def proxy_check(raw, label):
    a = raw[(raw.src == "archive") & raw.type.isin([0, 2, 3])]
    a = a[a.confidence.isin(VIIRS_CONF)] if label != "MODIS" else a[pd.to_numeric(a.confidence, errors="coerce") >= MODIS_MIN_CONF]
    a = a.assign(static=key(a, STATIC_GRID).isin(STATIC_MASK).values)
    keep_truth = (a.type == 0) & ~a.static        # 아카이브: type + 마스크
    keep_proxy = ~a.static                         # NRT: 마스크만
    conf = {f"type {t}": {"남김 비율 (대체 규칙)": round(float(keep_proxy[a.type == t].mean()), 3), "남김 비율 (정답)": round(float(keep_truth[a.type == t].mean()), 3), "건수": int((a.type == t).sum())} for t in (0, 2, 3)}
    mt = lambda m: a[m].assign(cell=key(a[m], GRID)).drop_duplicates(["cell", "acq_date"]).acq_date.dt.to_period("M").value_counts()
    t_, p_ = mt(keep_truth), mt(keep_proxy)
    idx = t_.index.union(p_.index); t_, p_ = t_.reindex(idx, fill_value=0), p_.reindex(idx, fill_value=0)
    sel = t_ > 0
    diff = (p_[sel] - t_[sel]) / t_[sel]
    return conf, {"월별 차이 중앙값 %": round(float(diff.median() * 100), 1), "월별 |차이| 중앙값 %": round(float(diff.abs().median() * 100), 1),
                  "전체 합계 차이 %": round(float((p_[sel].sum() / t_[sel].sum() - 1) * 100), 1)}

nrt_proxy = {}
for raw, label in [(n20_raw, "NOAA-20"), (viirs_raw, "S-NPP"), (modis_raw, "MODIS")]:
    conf, mon = proxy_check(raw, label)
    nrt_proxy[label] = {"by_type": conf, "monthly": mon}
    print(label, "| 대체 규칙이 남기는 비율:", {k: v["남김 비율 (대체 규칙)"] for k, v in conf.items()}, "| 월별 화재 칸:", mon)
''')

# --- cell 7
md(r'''
## ④ 화재 감지일 집계

해상도가 높은 VIIRS는 같은 불도 점이 훨씬 많이 찍힙니다. 그래서 점 개수 대신 **격자에서 화재가 1건 이상 감지된 날**을 셉니다.
Terra와 Aqua는 하나의 MODIS로 묶이고, 같은 날 같은 격자의 중복은 하나로 칩니다. 격자 크기는 ⑥-2에서 데이터로 정합니다.
''')

# --- cell 8
py(r'''
def fire_days(d, grid):
    return d.assign(cell=key(d, grid)).drop_duplicates(["cell", "acq_date"])

end = max(modis.acq_date.max(), viirs.acq_date.max(), n20.acq_date.max())
months = pd.period_range(f"{YEARS[0]}-01", end.to_period("M"), freq="M")

def monthly(d, grid):
    return fire_days(d, grid).acq_date.dt.to_period("M").value_counts().reindex(months, fill_value=0).sort_index().astype(float)

def series(grid):
    m, v = monthly(modis, grid), monthly(viirs, grid)
    v[v.index < pd.Period("2012-02", "M")] = np.nan   # S-NPP는 2012-01-20부터 → 첫 달은 불완전
    return m, v

M, V = series(GRID)   # 월별 화재 감지일
yr = lambda s: s.index.year
ov = (yr(M) >= OVERLAP[0]) & (yr(M) <= OVERLAP[1])
print(f"겹침 기간 전체 비율 VIIRS/MODIS = {V[ov].sum() / M[ov].sum():.2f}")

N20_START, N21_START = n20.acq_date.min().to_period("M"), n21.acq_date.min().to_period("M")
DATA_END = n20_raw.acq_date.max().normalize()                         # 기준 위성 자료가 있는 마지막 날 (불이 없어도 관측은 있음)
AQUA_START = modis[modis.satellite == "Aqua"].acq_date.min().to_period("M")
N = monthly(n20, GRID); N[N.index < N20_START] = np.nan            # NOAA-20 (기준)
J = monthly(n21, GRID); J[J.index < N21_START] = np.nan            # NOAA-21
T = monthly(modis[modis.satellite == "Terra"], GRID)               # Terra 단독
V[V.index > viirs.acq_date.max().to_period("M")] = np.nan          # S-NPP 자료가 끝난 뒤
print("NOAA-20 시작", N20_START, "· NOAA-21 시작", N21_START, "· Aqua 시작", AQUA_START)
''')

# --- cell 9
md(r'''
## ⑤ 보정 계수

위성 사슬의 핵심 고리인 **MODIS ↔ S-NPP** 계수입니다. 두 센서는 2012~2025년을 함께 관측했습니다. 여기서 `k = VIIRS ÷ MODIS`를 구하고, ⑦에서 2012년 이전 MODIS 값을 `× k`로 S-NPP 단위로 올린 뒤 다시 NOAA-20 단위로 옮깁니다.

두 가지 방법을 만들고 ⑥에서 더 정확한 쪽을 고릅니다.

- **A. 월별 고정 계수:** 달마다 하나의 계수 `k[월] = Σ VIIRS / Σ MODIS` (겹침 기간 전체). 데이터가 적은 달은 전체 계수 쪽으로 당깁니다.
- **B. 월별 + 시간 가변 계수:** 같은 계산을 해당 연도 앞뒤 `WINDOW`년으로만 합니다. 센서 노후화처럼 비율이 해마다 바뀌는 경우를 반영합니다. 겹침 기간 뒤의 연도는 마지막 창을 씁니다.
''')

# --- cell 10
py(r'''
def k_monthly(years, M=M, V=V):
    sel = yr(M).isin(years)
    K = V[sel].sum() / M[sel].sum()
    vm = V[sel].groupby(V[sel].index.month).sum()
    mm = M[sel].groupby(M[sel].index.month).sum()
    return ((vm + SHRINK * K) / (mm + SHRINK)).reindex(range(1, 13)).fillna(K)

overlap_years = list(range(OVERLAP[0], OVERLAP[1] + 1))

def window_years(y, exclude=None):
    y = min(max(y, OVERLAP[0] + WINDOW), OVERLAP[1] - WINDOW)
    return [x for x in range(y - WINDOW, y + WINDOW + 1) if x != exclude]

def convert(method, exclude=None, M=M, V=V):
    """VIIRS를 MODIS 단위로 바꾼 월별 시계열. exclude 연도는 계수 계산에서 뺀다 (교차검증용)."""
    out = pd.Series(np.nan, index=V.index)
    k_all = k_monthly([y for y in overlap_years if y != exclude], M, V)
    for p in V.dropna().index:
        k = k_all if method == "A" else k_monthly(window_years(p.year, exclude), M, V)
        out[p] = V[p] / k[p.month]
    return out

kA = k_monthly(overlap_years)
ratio_by_year = (V[ov].groupby(yr(V)[ov]).sum() / M[ov].groupby(yr(M)[ov]).sum()).round(2)
pd.DataFrame({"월별 계수 A": kA.round(2)}).T
''')

# --- cell 11
md(r'''
## ⑥ 교차검증 (leave-one-year-out)

겹침 기간에서 한 해씩 빼고 계수를 다시 구한 뒤, 그 해의 VIIRS로 MODIS를 맞혀 봅니다. 실제 MODIS 값을 알고 있으니 오차를 직접 잴 수 있습니다.
''')

# --- cell 12
py(r'''
def validate(method, M=M, V=V):
    pred = pd.concat([convert(method, y, M, V)[lambda s, y=y: s.index.year == y] for y in overlap_years])
    act = M[pred.index]
    ann_p, ann_a = pred.groupby(pred.index.year).sum(), act.groupby(act.index.year).sum()
    ss_res, ss_tot = ((act - pred) ** 2).sum(), ((act - act.mean()) ** 2).sum()
    return pred, {
        "monthly_r2": round(1 - ss_res / ss_tot, 3),
        "monthly_mae": round((act - pred).abs().mean(), 1),
        "annual_mape_pct": round(((ann_p - ann_a).abs() / ann_a).mean() * 100, 1),
        "bias_pct": round((pred.sum() / act.sum() - 1) * 100, 1),
    }

predA, scoreA = validate("A")
predB, scoreB = validate("B")
scores = pd.DataFrame({"A 월별 고정": scoreA, "B 월별+시간 가변": scoreB})
METHOD = "A" if scoreA["annual_mape_pct"] <= scoreB["annual_mape_pct"] else "B"
pred_best = predA if METHOD == "A" else predB
print("선택한 방법:", METHOD)
scores
''')

# --- cell 13
md(r'''
### ⑥-2 격자 크기 민감도

격자가 크면 센서 해상도 차이는 줄지만, 대형 산불이 몇 칸 안에 뭉쳐서 실제보다 작게 보입니다.
격자마다 검증 오차와 2025년 3월 이상치 배수를 비교해서 ① 설정의 `GRID`를 고릅니다.
''')

# --- cell 14
py(r'''
def march_ratio(H, year):
    mar = H[(H.index.month == 3) & (yr(H) >= YEARS[0]) & (yr(H) <= YEARS[1])]
    return round(mar[pd.Period(f"{year}-03", "M")] / mar.median(), 2)

sens = []
for g in GRIDS_TO_TEST:
    m, v = series(g)
    _, sb = validate("B", m, v)
    h = m.where(m.index < pd.Period("2012-02", "M"), convert("B", None, m, v))
    sens.append({"격자(도)": g, "월별 R²": sb["monthly_r2"], "연간 오차 %": sb["annual_mape_pct"],
                 "2025년 3월 배수": march_ratio(h, 2025), "2022년 3월 배수": march_ratio(h, 2022)})
sensitivity = pd.DataFrame(sens).set_index("격자(도)")
sensitivity
''')

md(r'''
### ⑥-3 위성 사슬: Terra 단독, NOAA-20, NOAA-21

⑤와 같은 방식(월별 계수 + 축소, 한 해씩 빼고 검증)으로 나머지 고리를 잇습니다. `A ≈ B × k[월]`.

| 고리 | 왜 필요한가 | 겹침 기간 |
|---|---|---|
| Terra 단독 → MODIS(Terra+Aqua) | Aqua가 2002년 7월에 시작해, 그 전에는 위성 한 대라 감지가 절반 이하 | 2003~2011 |
| S-NPP → NOAA-20 | 기준 단위. S-NPP 신규 자료는 2026년 11월 2일부로 중단 | 2019~2025 |
| NOAA-21 → NOAA-20 | NOAA-20에 문제가 생기면 대신 쓸 예비 고리 | 2024~2025 |

Terra/MODIS 비율이 해마다 일정한지도 봅니다. 두 위성이 다르게 늙었다면 비율이 변하므로, 2012년 이전 MODIS의 안정성을 간접 확인할 수 있습니다.
''')
py(r'''
def k_pair(A, B, years):
    """A ≈ B × k[월]. 달마다 ΣA/ΣB, 자료가 적은 달은 전체 비율 쪽으로 당김."""
    sel = yr(A).isin(years) & A.notna() & B.notna()
    K = A[sel].sum() / B[sel].sum()
    a, b = A[sel].groupby(A[sel].index.month).sum(), B[sel].groupby(B[sel].index.month).sum()
    return ((a + SHRINK * K) / (b + SHRINK)).reindex(range(1, 13)).fillna(K)

def loyo_pair(A, B, years):
    """한 해씩 빼고 계수를 구해 그 해 A를 맞힘. (점수, 달별 오차 중앙값)"""
    preds = []
    for y in years:
        k = k_pair(A, B, [x for x in years if x != y])
        sel = (yr(B) == y) & B.notna() & A.notna()
        preds.append(B[sel] * k.reindex(B[sel].index.month).values)
    pred = pd.concat(preds); act = A[pred.index]
    ann_p, ann_a = pred.groupby(pred.index.year).sum(), act.groupby(act.index.year).sum()
    err_m = ((pred - act).abs() / act.clip(lower=1)).groupby(pred.index.month).median().reindex(range(1, 13))
    return {"years": [years[0], years[-1]], "annual_mape_pct": round(((ann_p - ann_a).abs() / ann_a).mean() * 100, 1),
            "bias_pct": round((pred.sum() / act.sum() - 1) * 100, 1)}, err_m

rng = lambda a: list(range(a[0], a[1] + 1))
kT, kSN, kJN = k_pair(M, T, rng(TERRA_YEARS)), k_pair(N, V, rng(OVERLAP_SN)), k_pair(N, J, rng(OVERLAP_JN))
score_T, err_T = loyo_pair(M, T, rng(TERRA_YEARS))
score_SN, err_SN = loyo_pair(N, V, rng(OVERLAP_SN))
score_JN, err_JN = loyo_pair(N, J, rng(OVERLAP_JN))
ann = lambda s, ys: pd.Series({y: s[yr(s) == y].sum() for y in ys})
terra_share = (ann(T, range(2003, 2026)) / ann(M, range(2003, 2026))).round(2)
sn_ratio = (ann(V, rng(OVERLAP_SN)) / ann(N, rng(OVERLAP_SN))).round(2)
chain_scores = pd.DataFrame({"Terra → MODIS": score_T, "S-NPP → NOAA-20": score_SN, "NOAA-21 → NOAA-20": score_JN}).T
print("Terra/MODIS 비율 (2003~2011):", terra_share.loc[2003:2011].to_dict())
print("S-NPP/NOAA-20 비율:", sn_ratio.to_dict())
display(pd.DataFrame({"Terra→MODIS": kT, "S-NPP→NOAA-20": kSN, "NOAA-21→NOAA-20": kJN}).round(2).T)
chain_scores
''')
md(r'''
**읽는 법:** S-NPP와 NOAA-20은 같은 종류의 센서(VIIRS)라 차이가 작고(교차검증 연간 오차 약 6%), 이 고리는 거의 오차를 더하지 않습니다. Terra 단독 보정도 오차 약 11%이고, Terra 비율이 2003~2011년에 0.35~0.51 사이로 뚜렷한 추세가 없어 그 시기 MODIS는 안정적이었다고 볼 수 있습니다. NOAA-21은 겹침이 2년뿐이라 계수가 불안정합니다. 예비 고리로만 두고, 겹침이 늘면 다시 확인합니다.
''')

# --- cell 15
md(r'''
## ⑦ 하모니제이션 결과와 단절 검정

- **H (하모니제이션, NOAA-20 단위):**
  - NOAA-20 관측 이후(2018년 4월~): NOAA-20 원값
  - 2012년 2월 ~ 2018년 3월: S-NPP × k_SN
  - 2002년 8월 ~ 2012년 1월: MODIS × k(⑤, 가장 이른 창) × k_SN
  - ~2002년 7월: Terra × k_T × k × k_SN
- **이어 붙이기:** 각 시기의 위성 원값을 그대로 이은 것 (Terra → MODIS → S-NPP → NOAA-20). 보정하지 않으면 생기는 문제를 보여 주는 비교 대상입니다.
- **센서 단절 검정:** 각 시계열을 "MODIS만 쓴 시계열(NOAA-20 단위로 환산)"로 나눈 **수준 비율**을 2012년 전후로 비교합니다. 실제 화재 변화는 양쪽에 똑같이 들어 있으므로, 2012년 뒤 비율이 앞과 달라지면 센서 탓입니다. 판정은 "2012년 뒤 ÷ 앞"의 95% 범위가 1을 포함하는지로 합니다. 차이에 대한 Pettitt 검정 p값도 참고로 남기지만, 보정 후에는 2012년 전 차이가 정확히 0이라 작은 차이의 부호에만 반응해 판정에는 쓰지 않습니다. 위성과 무관한 근거는 ⑰의 공식 산불 건수 검정입니다.
- **2012년 전·후 배율:** 같은 해 MODIS 환산값 대비 몇 배인지. 전후 모두 1.0에 가까울수록 단절이 없습니다.
- **MODIS만 쓴 시계열의 변화점**은 따로 보고합니다. 센서와 무관한 실제 변화 후보입니다.
''')

# --- cell 16
py(r'''
conv = convert(METHOD)   # S-NPP를 MODIS 단위로 (⑥ 검증과 품질 계산에 사용)
P2012 = pd.Period("2012-02", "M")
mo = lambda s: s.index.month
k_ms = pd.Series([(kA if METHOD == "A" else k_monthly(window_years(p.year)))[p.month] for p in months], index=months)
terra_only = M.index <= AQUA_START
M_fix = M.copy(); M_fix[terra_only] = T[terra_only] * kT.reindex(mo(T)[terra_only]).values   # Terra 단독 구간 보정
R = M_fix * k_ms * kSN.reindex(mo(M)).values                     # MODIS만 쓴 시계열을 NOAA-20 단위로
R[M.index > modis.acq_date.max().to_period("M")] = np.nan
H = pd.Series(np.select([N.index >= N20_START, N.index >= P2012], [N, V * kSN.reindex(mo(V)).values], R), index=months)
SOURCE = pd.Series(np.select([N.index >= N20_START, N.index >= P2012, ~terra_only], ["NOAA-20", "S-NPP→NOAA-20", "MODIS→NOAA-20"], "Terra→NOAA-20"), index=months)
naive = pd.Series(np.select([N.index >= N20_START, N.index >= P2012], [N, V], M), index=months)

def pettitt(x):
    x = np.asarray(x, float); n = len(x)
    U = np.array([np.sign(x[: t + 1, None] - x[None, t + 1 :]).sum() for t in range(n - 1)])
    t = int(np.abs(U).argmax()); K = float(np.abs(U).max())
    return t + 1, min(1.0, 2 * np.exp(-6 * K**2 / (n**3 + n**2)))

full = (yr(M) >= YEARS[0]) & (yr(M) <= YEARS[1])
annual = pd.DataFrame({
    "MODIS만": R[full].groupby(yr(M)[full]).sum(),
    "이어 붙이기": naive[full].groupby(yr(M)[full]).sum(),
    "H 하모니제이션": H[full].groupby(yr(M)[full]).sum(),
})
after = annual.index >= 2012
ci = lambda r: [round(r.mean() - 1.96 * r.std() / np.sqrt(len(r)), 2), round(r.mean() + 1.96 * r.std() / np.sqrt(len(r)), 2)]
break_tests = {}
for col in ["이어 붙이기", "H 하모니제이션"]:
    i, p = pettitt((annual[col] - annual["MODIS만"]).values)
    r = annual[col] / annual["MODIS만"]
    jump_ci = [round(x / r[~after].mean(), 2) for x in ci(r[after])]
    break_tests[col] = {"sensor_break_p": round(p, 4), "sensor_break": not (jump_ci[0] <= 1 <= jump_ci[1]),
                        "jump": round(r[after].mean() / r[~after].mean(), 2), "jump_ci95": jump_ci,
                        "ratio_before_2012": round(r[~after].mean(), 2), "ratio_before_ci95": ci(r[~after]),
                        "ratio_after_2012": round(r[after].mean(), 2), "ratio_ci95": ci(r[after])}
i, p = pettitt(M_fix[full].groupby(yr(M)[full]).sum().values)
real_change = {"change_year": int(annual.index[i]), "p_value": round(p, 4)}
print("MODIS만의 변화점 (실제 변화 후보):", real_change)
pd.DataFrame(break_tests).T
''')

# --- cell 17
md(r'''
## ⑧ 차트
''')

# --- cell 18
py(r'''
INK, MUTED, EMBER, COOL = "#141A22", "#8E9AA8", "#C9420E", "#6C7A8A"
fig, ax = plt.subplots(2, 2, figsize=(14, 9))

a = ax[0, 0]
bn, bh = break_tests["이어 붙이기"], break_tests["H 하모니제이션"]
a.plot(annual.index, annual["이어 붙이기"], color=MUTED, lw=2, ls="--", label=f"원값 이어 붙이기 (2012 전 {bn['ratio_before_2012']}배 → 후 {bn['ratio_after_2012']}배, 단절 p={bn['sensor_break_p']})")
a.plot(annual.index, annual["H 하모니제이션"], color=EMBER, lw=2.5, label=f"하모니제이션 (전 {bh['ratio_before_2012']}배 → 후 {bh['ratio_after_2012']}배, 단절 p={bh['sensor_break_p']})")
a.plot(annual.index, annual["MODIS만"], color=INK, lw=1, alpha=.6, label="MODIS만, NOAA-20 단위 환산 (참고)")
for x in (2002.5, 2011.5, 2018.25):
    a.axvline(x, color=MUTED, lw=1, ls=":")
a.set_title("A1. 위성 교체 단절: 보정 전 vs 보정 후", loc="left"); a.set_ylabel("화재 감지일 / 년 (NOAA-20 단위)"); a.legend(frameon=False, fontsize=8.5)

a = ax[0, 1]
act = M[pred_best.index]
lim = max(act.max(), pred_best.max()) * 1.05
a.scatter(act, pred_best, s=14, color=EMBER, alpha=.6); a.plot([0, lim], [0, lim], color=INK, lw=1)
s = scores[scores.columns[0 if METHOD == "A" else 1]]
a.set_title(f"A2. MODIS↔S-NPP 교차검증 (방법 {METHOD})", loc="left")
a.set_xlabel("실제 MODIS (감지일/월)"); a.set_ylabel("VIIRS로 예측한 MODIS")
a.text(.04, .9, f"R² {s['monthly_r2']}  ·  연간 오차 {s['annual_mape_pct']}%  ·  편향 {s['bias_pct']}%", transform=a.transAxes)

a = ax[1, 0]
a.bar(kA.index, kA.values, color=COOL); a.set_ylim(0, kA.max() * 1.8)
a.set_xticks(range(1, 13), [f"{m}월" for m in range(1, 13)])
a.set_title("A3. 월별 보정 계수 (VIIRS ÷ MODIS)", loc="left")
ins = a.inset_axes([.58, .58, .4, .38]); ins.plot(ratio_by_year.index, ratio_by_year.values, color=EMBER, marker="o", ms=3)
ins.set_title("연도별 비율", fontsize=8); ins.tick_params(labelsize=7)

a = ax[1, 1]
cal = H[full].to_frame("v").assign(y=yr(H)[full], m=H[full].index.month).pivot(index="y", columns="m", values="v")
im = a.imshow(np.sqrt(cal.values), aspect="auto", cmap="inferno_r")
a.set_yticks(range(0, len(cal), 4), cal.index[::4]); a.set_xticks(range(12), [f"{m}월" for m in range(1, 13)])
a.set_title("화재 달력 미리보기 (하모니제이션, 색은 √값)", loc="left")

for a in ax.flat:
    a.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
OUT_DIR.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT_DIR / "harmonization_overview.png", dpi=150)
plt.show()
''')

# --- cell 19
md(r'''
## ⑩ FRP: 센서 간 보정이 가능한가

FRP(화재 복사 강도, MW)는 불이 얼마나 **세게** 탔는지를 보여 줍니다. 감지일과 같은 방법(월별 + 시간 가변 계수, 한 해씩 빼고 검증)으로 보정을 시험합니다.

- 보정이 충분히 정확하면(연간 오차 15% 이하, 편향 ±10% 이내) 25년 전체를 보정값으로 씁니다.
- 아니면 **MODIS FRP만** 씁니다. MODIS는 2001년부터 같은 센서로 기록되어 보정 없이 25년 비교가 가능합니다.
''')

# --- cell 20
py(r'''
def monthly_frp(d):
    return d.groupby(d.acq_date.dt.to_period("M")).frp.sum().reindex(months, fill_value=0).astype(float)

FM, FV = monthly_frp(modis), monthly_frp(viirs)
FV[FV.index < pd.Period("2012-02", "M")] = np.nan
FM[FM.index > modis.acq_date.max().to_period("M")] = np.nan   # MODIS 운영 종료 뒤
_, frp_score = validate("B", FM, FV)
frp_ratio_by_year = (FV[ov].groupby(yr(FV)[ov]).sum() / FM[ov].groupby(yr(FM)[ov]).sum()).round(2)
FRP_HARMONIZE = frp_score["annual_mape_pct"] <= 15 and abs(frp_score["bias_pct"]) <= 10
F = FM.where(FM.index < pd.Period("2012-02", "M"), convert("B", None, FM, FV)) if FRP_HARMONIZE else FM
FRP_SOURCE = "보정된 MODIS+VIIRS" if FRP_HARMONIZE else "MODIS 단독"

print(f"감지 1건당 FRP 중앙값: MODIS {modis.frp.median():.1f} MW, VIIRS {viirs.frp.median():.1f} MW")
print("연도별 VIIRS/MODIS FRP 비율:", frp_ratio_by_year.min(), "~", frp_ratio_by_year.max())
print("결정:", FRP_SOURCE)
pd.DataFrame({"화재 감지일": scoreB, "FRP": frp_score})
''')

# --- cell 21
md(r'''
## ⑪ 감지일 × FRP 2×2 유형

각 달의 감지일과 FRP를 **같은 달의 평년 분포**와 비교해 네 유형으로 나눕니다. 가중치 없이 두 축만 씁니다.

| | FRP가 평년 수준 | FRP가 평년보다 높음 |
|---|---|---|
| **감지일이 평년보다 많음** | 작은 불이 많음 | 많고 강함 |
| **감지일이 평년 수준** | 평년 수준 | 드물지만 강함 |

"평년보다 높음"은 같은 달 25년 분포의 `TYPE_PCT` 분위수를 넘는 경우입니다. 기준에 따라 유형 개수가 어떻게 바뀌는지 표로 함께 남깁니다.
''')

# --- cell 22
py(r'''
TYPES = ["많고 강함", "작은 불이 많음", "드물지만 강함", "평년 수준"]

def pct_rank(s):
    """같은 달 평년(YEARS) 값들 중 몇 %보다 큰가 (0~1)."""
    base_s = s[full]
    return pd.Series([(base_s[base_s.index.month == p.month] < v).mean() for p, v in s.items()], index=s.index)

fd_pct, frp_pct = pct_rank(H), pct_rank(F)

def classify(pct):
    hi_fd, hi_fr = fd_pct > pct, frp_pct > pct
    return pd.Series(np.select([hi_fd & hi_fr, hi_fd & ~hi_fr, ~hi_fd & hi_fr], TYPES[:3], TYPES[3]), index=H.index)

month_type = classify(TYPE_PCT)
type_counts = pd.DataFrame({f"상위 {round((1 - q) * 100)}% 기준": classify(q)[full].value_counts() for q in (0.75, 0.90)}).reindex(TYPES).fillna(0).astype(int)

frp_med = F[full].groupby(F[full].index.month).median()
frp_ratio = F / frp_med.reindex(F.index.month).values
fd_ratio = H / H[full].groupby(H[full].index.month).median().reindex(H.index.month).values
strong = pd.DataFrame({"유형": month_type, "감지일 배수": fd_ratio.round(2), "FRP 배수": frp_ratio.round(2)})[month_type != "평년 수준"]
print(f"FRP 출처: {FRP_SOURCE}")
display(type_counts)
strong.sort_values("FRP 배수", ascending=False).head(10)
''')

# --- cell 23
py(r'''
COLORS = {"많고 강함": "#C9420E", "작은 불이 많음": "#E8A33C", "드물지만 강함": "#7A4FA3", "평년 수준": "#B8C1CC"}
fig, a = plt.subplots(figsize=(7, 6.6))
for t in TYPES[::-1]:
    sel = (month_type == t) & full
    a.scatter(fd_pct[sel] * 100, frp_pct[sel] * 100, s=18 if t == "평년 수준" else 30, color=COLORS[t], alpha=.8, label=f"{t} ({sel.sum()})")
a.axvline(TYPE_PCT * 100, color="#141A22", lw=1, ls="--"); a.axhline(TYPE_PCT * 100, color="#141A22", lw=1, ls="--")
for p, off in [(pd.Period("2025-03", "M"), (-150, -45)), (pd.Period("2022-03", "M"), (-150, -75))]:
    if p in H.index:
        a.annotate(f"{p.year}년 {p.month}월", (fd_pct[p] * 100, frp_pct[p] * 100), xytext=off, textcoords="offset points",
                   fontsize=9, arrowprops=dict(arrowstyle="-", color="#5A6573", lw=.8))
a.set_xlabel("감지일: 같은 달 평년 중 백분위"); a.set_ylabel(f"FRP ({FRP_SOURCE}): 같은 달 평년 중 백분위")
a.set_title(f"7번 감지일 × FRP 2×2 유형 ({YEARS[0]}~{YEARS[1]}, 기준 상위 {round((1 - TYPE_PCT) * 100)}%)", loc="left")
a.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(.5, -.12), ncol=4); a.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(OUT_DIR / "type_2x2.png", dpi=150); plt.show()
''')

# --- cell 24
md(r'''
## ⑫ 품질 표시

값마다 출처와 신뢰 수준을 붙입니다. confidence는 지표에 섞지 않고 품질 정보로만 씁니다 (MODIS는 0~100, VIIRS는 l/n/h라 두 센서를 직접 비교할 수 없습니다).

| 품질 | 조건 |
|---|---|
| 품질 | 조건 |
|---|---|
| 높음 | NOAA-20 직접 관측(아카이브), 또는 S-NPP→NOAA-20 변환 중 그 달 오차 10% 이하 |
| 보통 | 변환 오차 30% 이하, 또는 NOAA-20 준실시간(NRT, 유형 필터 대신 위치 마스크) |
| 낮음 | 변환 오차 30% 초과 |

여러 고리를 거친 값의 오차는 고리별 달 오차를 제곱해 더한 뒤 제곱근을 씁니다 (서로 독립이라고 가정). 예: 2005년 3월 = √(MODIS→S-NPP² + S-NPP→NOAA-20²).
같은 달 평년 감지일이 `LOW_COUNT`보다 작으면 배수 해석이 불안정해 한 단계 낮춥니다. 변환된 값에는 오차 범위(`value_lo`~`value_hi`)를 붙입니다.
''')

# --- cell 25
py(r'''
act_best = M[pred_best.index]
month_err = ((pred_best - act_best).abs() / act_best.clip(lower=1)).groupby(pred_best.index.month).median()   # MODIS↔S-NPP
n20_archive_end = n20_raw.loc[n20_raw.src == "archive", "acq_date"].max().to_period("M")
modis_conf = modis.assign(c=pd.to_numeric(modis.confidence, errors="coerce")).groupby(modis.acq_date.dt.to_period("M")).c.mean()
clim_med = H[full].groupby(H[full].index.month).median()
LEVELS = ["낮음", "보통", "높음"]

def quality(p):
    m = p.month
    if SOURCE[p] == "NOAA-20":
        level, note, err = (2, "NOAA-20 직접 관측", 0.0) if p <= n20_archive_end else (1, "NOAA-20 준실시간(NRT): 유형 필터 대신 위치 마스크", 0.0)
    elif SOURCE[p] == "S-NPP→NOAA-20":
        err = float(err_SN[m])
        level, note = (2 if err <= .1 else 1 if err <= .3 else 0), f"S-NPP→NOAA-20 변환, 이 달 교차검증 오차 약 {err:.0%}"
    else:
        parts = [month_err[m], err_SN[m]] + ([err_T[m]] if SOURCE[p] == "Terra→NOAA-20" else [])
        err = float(np.sqrt(np.sum(np.square(parts))))
        level, note = (1 if err <= .3 else 0), f"{SOURCE[p]} 변환 ({len(parts)}단계), 이 달 오차 약 {err:.0%}"
    if clim_med[m] < LOW_COUNT and level > 0:
        level -= 1; note += ", 평년 값이 작아 배수 해석 주의"
    return LEVELS[level], note, err

qual = pd.DataFrame([quality(p) for p in H.index], index=H.index, columns=["quality", "note", "err"])
qual["value_lo"], qual["value_hi"] = (H * (1 - qual.err)).clip(lower=0), H * (1 + qual.err)
print("월별 교차검증 오차 MODIS↔S-NPP:", (month_err * 100).round(0).astype(int).to_dict())
print("월별 교차검증 오차 S-NPP→NOAA-20:", (err_SN * 100).round(0).astype(int).to_dict())
print("구간별 품질:", qual.groupby(SOURCE).quality.value_counts().unstack(fill_value=0).to_dict("index"))
qual.quality.value_counts()
''')

# --- cell 26
md(r'''
## ⑬ 웹용 파일 내보내기

`output/<COUNTRY>/` 폴더에 프론트엔드가 그대로 읽을 파일을 만듭니다.

| 파일 | 내용 | 쓰는 곳 |
|---|---|---|
| `calendar.json` | 연·월별 감지일, 평년 대비 배수와 순위, FRP와 배수, 2×2 유형, 품질과 오차 범위 | 대시보드 화재 달력(토글·점 표시·툴팁), 브리핑 |
| `climatology.json` | 월별 중앙값·사분위·보통 해 범위(band_low·band_high)·최소·최대 | 올해 vs 평년 밴드 차트 |
| `meta.json` | 필터링 표, 보정 계수, 검증 수치, 단절 검정 | 방법론·인사이트 페이지 |
| `hotspots_clean.csv` | 정리된 핫스팟 원자료 | CSV 다운로드, 지도 |
''')

# --- cell 27
py(r'''
base = H[full].to_frame("v").assign(y=yr(H)[full], m=H[full].index.month)
clim = base.groupby("m").v.agg(median="median", q25=lambda s: s.quantile(.25), q75=lambda s: s.quantile(.75), min="min", max="max")
_noise = BAND_NOISE * np.sqrt(np.maximum(clim["median"], 1))
clim["band_low"] = np.minimum(base.groupby("m").v.quantile(BAND_Q[0]), clim["median"] - _noise)
clim["band_high"] = np.maximum(base.groupby("m").v.quantile(BAND_Q[1]), clim["median"] + _noise)

rows = []
for p, v in H.items():
    same = base[base.m == p.month].v
    med = clim.loc[p.month, "median"]
    rows.append({
        "year": p.year, "month": p.month, "value": round(float(v), 1),
        "raw_before": round(float(naive[p]), 1) if pd.notna(naive[p]) else None,   # 보정 전 원값 이어 붙이기 (⑦과 같음)
        "source": SOURCE[p],
        "partial": bool(p == months[-1] and DATA_END < p.end_time.normalize()),
        "median": round(float(med), 1),
        "ratio_to_median": round(float(v / med), 2) if med > 0 else None,
        "rank_in_month": int((same > v).sum() + 1),
        "years_in_month": int(len(same)),
        "frp_mw": round(float(F[p]), 1) if pd.notna(F[p]) else None,
        "frp_ratio_to_median": round(float(frp_ratio[p]), 2) if pd.notna(frp_ratio[p]) and np.isfinite(frp_ratio[p]) else None,
        "frp_high": bool(frp_pct[p] > TYPE_PCT),
        "type": month_type[p],
        "quality": qual.quality[p], "quality_note": qual.note[p],
        "value_lo": round(float(qual.value_lo[p]), 1), "value_hi": round(float(qual.value_hi[p]), 1),
        "modis_conf_mean": round(float(modis_conf[p]), 1) if p in modis_conf.index else None,
    })

meta = {
    "country": COUNTRY, "bbox": BBOX, "generated": datetime.date.today().isoformat(),
    "unit": f"VIIRS NOAA-20 기준 화재 감지일 ({GRID}° 격자 × 일)",
    "data_range": {"modis": [str(modis.acq_date.min().date()), str(modis.acq_date.max().date())],
                   "viirs_snpp": [str(viirs.acq_date.min().date()), str(viirs.acq_date.max().date())],
                   "noaa20": [str(n20.acq_date.min().date()), str(n20.acq_date.max().date())],
                   "noaa21": [str(n21.acq_date.min().date()), str(n21.acq_date.max().date())]},
    "filters": filter_log.to_dict("records"),
    "static_cells_masked": n_static_m,
    "nrt_proxy_validation": nrt_proxy,
    "calibration": {"base": "NOAA-20", "chain": "Terra → MODIS → S-NPP → NOAA-20 (NOAA-21 → NOAA-20 예비)",
                    "method": METHOD, "k_by_month": kA.round(3).to_dict(), "ratio_by_year": ratio_by_year.to_dict(),
                    "overlap_years": list(OVERLAP), "shrink": SHRINK, "window": WINDOW,
                    "terra_to_modis": {"k_by_month": kT.round(3).to_dict(), "validation": score_T, "terra_share_by_year": terra_share.to_dict()},
                    "snpp_to_noaa20": {"k_by_month": kSN.round(3).to_dict(), "validation": score_SN, "ratio_by_year": sn_ratio.to_dict()},
                    "noaa21_to_noaa20": {"k_by_month": kJN.round(3).to_dict(), "validation": score_JN}},
    "validation": {"A": scoreA, "B": scoreB},
    "break_test": break_tests,
    "modis_only_change_point": real_change,
    "grid_sensitivity": sensitivity.reset_index().to_dict("records"),
    "frp": {"source": FRP_SOURCE, "harmonized": bool(FRP_HARMONIZE), "validation": frp_score,
            "ratio_by_year": frp_ratio_by_year.to_dict(),
            "median_frp_per_detection_mw": {"MODIS": float(modis.frp.median()), "VIIRS": float(viirs.frp.median())}},
    "types": {"threshold_pct": TYPE_PCT, "labels": TYPES,
              "counts": {c: type_counts[c].to_dict() for c in type_counts}},
    "quality": {"rules": {"높음": "NOAA-20 직접 관측, 또는 S-NPP→NOAA-20 변환 중 월별 오차 10% 이하",
                          "보통": "변환 오차 30% 이하, 또는 NOAA-20 NRT", "낮음": "변환 오차 30% 초과"},
                "low_count": LOW_COUNT, "month_error": {"modis_snpp": month_err.round(3).to_dict(), "snpp_noaa20": err_SN.round(3).to_dict(),
                                                        "terra_modis": err_T.round(3).to_dict()}},
    "sources": ["NASA FIRMS MODIS Collection 6.1 (MCD14)", "NASA FIRMS VIIRS S-NPP 375 m (VNP14IMG)",
                "NASA FIRMS VIIRS NOAA-20 375 m (VJ114IMG)", "NASA FIRMS VIIRS NOAA-21 375 m (VJ214IMG)"],
}

(OUT_DIR / "calendar.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
(OUT_DIR / "climatology.json").write_text(clim.round(1).reset_index().to_json(orient="records", force_ascii=False), encoding="utf-8")
(OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
cols = ["latitude", "longitude", "acq_date", "acq_date_utc", "acq_time", "sensor", "satellite", "confidence", "frp", "daynight", "src"]
pd.concat([modis, viirs, n20, n21])[cols].sort_values("acq_date").to_csv(OUT_DIR / "hotspots_clean.csv", index=False)
print("저장:", *sorted(p.name for p in OUT_DIR.iterdir()))
''')

# --- cell 28
md(r'''
## 브리핑 문장 미리보기

대시보드 브리핑 카드에 들어갈 문장을 규칙으로 만듭니다. 같은 입력이면 항상 같은 문장이 나옵니다.
''')

# --- cell 29
py(r'''
def status(r):
    if r["ratio_to_median"] is None: return "자료 부족"
    pct = 1 - (r["rank_in_month"] - 1) / r["years_in_month"]
    return "이례적" if pct >= .9 else "평년보다 높음" if pct >= .75 else "평년 수준"

def briefing(year, month):
    r = next(x for x in rows if x["year"] == year and x["month"] == month)
    s = (f"{year}년 {month}월 [{status(r)}] {r['years_in_month']}년 중 {r['rank_in_month']}위, "
         f"{month}월 평년(중앙값)의 {r['ratio_to_median']}배")
    if r["type"] != "평년 수준":
        s += f" · {r['type']} (FRP 평년의 {r['frp_ratio_to_median']}배)"
    return s + f" · 품질 {r['quality']}"

for y, m in [(2025, 3), (2022, 3), (2024, 8), (2024, 3), (2026, 9)]:
    print(briefing(y, m))
''')

# --- cell 30
md(r'''
## ⑭ 시·군·구별 화재 달력

화재를 관리하는 사람은 자기 관할 구역 단위로 움직입니다. 핫스팟 좌표를 행정구역 경계와 겹쳐 시·군·구를 붙이고, 지역마다 달력·평년 대비 배수·순위·2×2 유형·품질을 계산합니다.

- **경계:** geoBoundaries (CC BY 3.0). `boundaries/<COUNTRY>/` 폴더의 ADM2(시·군·구)와 ADM1(시·도) 파일을 씁니다. 지역 이름은 영문이며, 시·도는 한글로 붙입니다. 이 시·도 경계는 일부 광역시와 맞지 않아, 확인된 오류(울진·달성·강화·광주 4개 구 등 13곳)는 `PROVINCE_FIX`로 바로잡았습니다. 발표 전에는 공식 행정구역 파일로 바꾸는 것을 권장합니다.
- **보정 계수는 나라 단위로 공유합니다.** 작은 지역마다 계수를 따로 구하면 자료가 적어 불안정해지기 때문입니다. 평년·순위·유형만 지역별로 계산합니다.
- **해안선 근처 점:** 경계 파일의 해안선이 단순화되어 있어 바다로 살짝 벗어난 점은 가장 가까운 지역(약 3 km 이내)에 붙입니다.
''')

# --- cell 31
py(r'''
from matplotlib.path import Path as MPath
from scipy.spatial import cKDTree

REGION_DIR = Path("boundaries") / COUNTRY
NEAREST_MAX = 0.03   # 경계 밖 점을 가장 가까운 지역에 붙이는 최대 거리 (도, 약 3 km)
PROVINCE_KO = {"Seoul": "서울", "Busan": "부산", "Daegu": "대구", "Incheon": "인천", "Gwangju": "광주", "Daejeon": "대전",
               "Ulsan": "울산", "Sejong": "세종", "Gyeonggi": "경기", "Gangwon": "강원", "North Chungcheong": "충북",
               "South Chungcheong": "충남", "North Jeolla": "전북", "South Jeolla": "전남", "North Gyeongsang": "경북",
               "South Gyeongsang": "경남", "Jeju": "제주"}
# 그 밖의 지역은 상위 단위 ID = ADM1 shapeName 그대로. 화면용 영어·한국어 이름은 ADM1 파일의 name_en·name_ko (백엔드 카탈로그가 읽음)

# geoBoundaries에 빠진 구역을 채우는 보강 파일 (한국: 영광군 = ADM1 전남 − 다른 ADM2). 없으면 건너뜀
PATCH_ADM2 = REGION_DIR / f"patch-{COUNTRY}-ADM2.geojson"
patch_feats = lambda: json.loads(PATCH_ADM2.read_text(encoding="utf-8"))["features"] if PATCH_ADM2.exists() else []

def load_polys(fp, extra=()):
    out = []
    for f in json.loads(Path(fp).read_text(encoding="utf-8"))["features"] + list(extra):
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [(MPath(np.asarray(p[0])), [MPath(np.asarray(h)) for h in p[1:]]) for p in polys]
        pts = np.concatenate([np.asarray(p[0]) for p in polys])
        out.append({"id": f["properties"]["shapeID"], "name": f["properties"]["shapeName"], "rings": rings,
                    "name_ko": f["properties"].get("name_ko"), "name_en": f["properties"].get("name_en"),
                    "bbox": (*pts.min(0), *pts.max(0)), "center": pts.mean(0), "pts": pts})
    return out

def locate(xy, polys):
    res = np.full(len(xy), -1)
    for i, P in enumerate(polys):
        x0, y0, x1, y1 = P["bbox"]
        cand = np.where((res < 0) & (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1))[0]
        if not len(cand):
            continue
        inside = np.zeros(len(cand), bool)
        for outer, holes in P["rings"]:
            m = outer.contains_points(xy[cand])
            for h in holes:
                m &= ~h.contains_points(xy[cand])
            inside |= m
        res[cand[inside]] = i
    return res

def nearest(xy, polys, max_dist):
    owner = np.concatenate([np.full(len(P["pts"]), i) for i, P in enumerate(polys)])
    d, j = cKDTree(np.concatenate([P["pts"] for P in polys])).query(xy)
    return np.where(d <= max_dist, owner[j], -1)

adm2 = load_polys(REGION_DIR / f"geoBoundaries-{COUNTRY}-ADM2.geojson", patch_feats())
adm1 = load_polys(REGION_DIR / f"geoBoundaries-{COUNTRY}-ADM1.geojson")
def province_of(P, n=12):
    """지역 안쪽의 격자 점들이 가장 많이 속한 시·도 (두 경계 파일의 해안선 차이에 덜 민감)."""
    x0, y0, x1, y1 = P["bbox"]
    gx, gy = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    pts = pts[locate(pts, [P]) == 0]
    if not len(pts):
        pts = P["center"][None, :]
    k = locate(pts, adm1)
    k = k[k >= 0] if (k >= 0).any() else nearest(pts, adm1, 1.0)
    return int(np.bincount(k).argmax())

# geoBoundaries 시·도(ADM1) 경계가 일부 광역시와 맞지 않아 확인된 오류만 shapeID로 바로잡음.
# 공식 행정구역 파일(통계청 SGIS 등)로 바꾸면 필요 없음.
PROVINCE_FIX = {
    "91817680B88731995383072": "경북",  # Uljin-gun
    "91817680B33489673734556": "대구",  # Dalseong-gun
    "91817680B68494559899558": "광주", "91817680B89733153975870": "광주",  # Nam-gu, Dong-gu
    "91817680B16538338684661": "광주", "91817680B87996420220515": "광주",  # Gwangsan-gu, Seo-gu
    "91817680B53616587081026": "서울",  # Eunpyeong-gu
    "91817680B54012703126739": "부산", "91817680B91211823266814": "부산",  # Gijang-gun, Gangseo-gu
    "91817680B73279111808647": "인천", "91817680B94833670639499": "인천",  # Seo-gu, Gyeyang-gu
    "91817680B53543824194985": "대전",  # Dong-gu
    "91817680B24929628173287": "인천",  # Ganghwa-gun
    "91817680B30315657457409": "대구",  # Gunwi-gun: 2023-07-01 경북 → 대구 편입 (geoBoundaries는 옛 소속)
} if COUNTRY == "KOR" else {
    "53547021B46893578630881": "Dytikis Elladas",  # Zacharo (엘리스): 2010년 시군 경계가 거칠어 펠로폰네소스로 잘못 배정됨
} if COUNTRY == "GRC" else {}

# 화면용 이름 (tools/build_names.py가 만듦): 하위 구역 한국어 이름은 names-<지역>.csv, 상위 단위는 ADM1 파일의 name_ko·name_en.
# 상위 단위 ID(province)는 그대로 두고(한국 "경북", 그 밖은 shapeName) 이름만 따로 붙인다
NAMES_CSV = REGION_DIR / f"names-{COUNTRY}.csv"
NAMES_KO = pd.read_csv(NAMES_CSV, dtype=str).fillna("").set_index("id")["name_ko"].to_dict() if NAMES_CSV.exists() else {}
PROV_NAMES = {PROVINCE_KO.get(a["name"], a["name"]): (a.get("name_ko") or PROVINCE_KO.get(a["name"], a["name"]), a.get("name_en") or a["name"])
              for a in adm1}

for P in adm2:
    k = province_of(P)
    P["province"] = PROVINCE_FIX.get(P["id"], PROVINCE_KO.get(adm1[k]["name"], adm1[k]["name"]))
    P["label"] = f"{P['province']} {P['name']}"
    P["name_ko"] = NAMES_KO.get(P["id"]) or None
    P["province_ko"], P["province_en"] = PROV_NAMES.get(P["province"], (P["province"], P["province"]))

def assign(d):
    xy = d[["longitude", "latitude"]].to_numpy()
    r = locate(xy, adm2)
    inside = r >= 0
    r[~inside] = nearest(xy[~inside], adm2, NEAREST_MAX)
    return d.assign(region=r), int(inside.sum()), int(((~inside) & (r >= 0)).sum()), int((r < 0).sum())

modis_r, *cm = assign(modis)
viirs_r, *cv = assign(viirs)
n20_r, *cn = assign(n20)
pd.DataFrame([cm, cv, cn], index=["MODIS", "S-NPP", "NOAA-20"], columns=["경계 안", "가까운 지역에 붙임", "지역 없음 (바다 등)"])
''')

# --- cell 32
py(r'''
R = len(adm2)

def region_monthly(d, value=None):
    d = d[d.region >= 0]
    if value is None:
        d = d.assign(cell=key(d, GRID)).drop_duplicates(["region", "cell", "acq_date"])
        t = d.groupby(["region", d.acq_date.dt.to_period("M")]).size()
    else:
        t = d.groupby(["region", d.acq_date.dt.to_period("M")])[value].sum()
    return t.unstack(fill_value=0).reindex(index=range(R), columns=months, fill_value=0).astype(float)

RM, RV, RN = region_monthly(modis_r), region_monthly(viirs_r), region_monthly(n20_r)
RT = region_monthly(modis_r[modis_r.satellite == "Terra"])
RF = region_monthly(modis_r, "frp")   # FRP는 MODIS 단독 (⑩ 참고)

# 나라 단위 위성 사슬 계수를 지역에 그대로 적용 (⑦과 같은 식)
col = lambda k: k.reindex([p.month for p in months]).to_numpy()[None, :]
RM_fix = RM.copy(); RM_fix.loc[:, terra_only] = (RT * col(kT)).loc[:, terra_only]
is_n20, is_snpp = (months >= N20_START), (months >= P2012) & (months < N20_START)
RVN = RV * col(kSN); RVN.loc[:, is_n20] = RN.loc[:, is_n20]          # VIIRS만, NOAA-20 단위 (2012-02~)
RVN.loc[:, months < P2012] = np.nan
R_naive = RM.copy()                                                   # 보정 전 원값 이어 붙이기 (웹 raw_before, ⑦ naive와 같은 정의):
R_naive.loc[:, months >= P2012] = RV.loc[:, months >= P2012]          #   2012-02 전 MODIS, 2018-03까지 S-NPP, 그 뒤 NOAA-20 원값
R_naive.loc[:, is_n20] = RN.loc[:, is_n20]
RH = RM_fix * k_ms.to_numpy()[None, :] * col(kSN)                    # 2012년 이전: MODIS → NOAA-20
RH.loc[:, months >= P2012] = RVN.loc[:, months >= P2012]

base_cols = [p for p in months if YEARS[0] <= p.year <= YEARS[1]]
def by_month_stats(T):
    med = pd.DataFrame({m: T[[p for p in base_cols if p.month == m]].median(axis=1) for m in range(1, 13)})
    pct = pd.DataFrame(index=T.index, columns=months, dtype=float)
    rank = pd.DataFrame(index=T.index, columns=months, dtype=float)
    for m in range(1, 13):
        B = T[[p for p in base_cols if p.month == m]].to_numpy()
        for p in [q for q in months if q.month == m]:
            v = T[p].to_numpy()[:, None]
            pct[p] = (B < v).mean(1)
            rank[p] = (B > v).sum(1) + 1
    return med, pct, rank

r_med, r_pct, r_rank = by_month_stats(RH)
_, rf_pct, _ = by_month_stats(RF)
hi_fd, hi_fr = r_pct > TYPE_PCT, rf_pct > TYPE_PCT
r_type = pd.DataFrame(np.select([hi_fd & hi_fr, hi_fd & ~hi_fr, ~hi_fd & hi_fr], [0, 1, 2], 3), index=RH.index, columns=months)

# 품질: 나라 단위 등급에서 시작해, 그 지역의 같은 달 평년이 LOW_COUNT보다 작으면 한 단계 낮춤
nat_level = pd.Series([LEVELS.index(q) for q in qual.quality], index=months)
low = pd.DataFrame({p: r_med[p.month] < LOW_COUNT for p in months})
r_quality = pd.DataFrame(np.maximum(nat_level.to_numpy()[None, :] - low.to_numpy().astype(int), 0), index=RH.index, columns=months)
print("지역 × 월 품질 분포:", {LEVELS[k]: int((r_quality.to_numpy() == k).sum()) for k in range(3)})
''')

# --- cell 33
py(r'''
names = pd.Series([P["label"] for P in adm2])
tot = RH[base_cols].sum(axis=1)
years_fire = (RH[base_cols].T.groupby([p.year for p in base_cols]).sum() > 0).sum()
summary = pd.DataFrame({"지역": names, "화재 감지일 (2001~2025)": tot.round(0).astype(int), "불이 난 연도 수": years_fire,
                        "가장 많이 탄 달": np.argmax([RH[[p for p in base_cols if p.month == m]].sum(axis=1).to_numpy() for m in range(1, 13)], axis=0) + 1})
print("25년 누적 화재 감지일 상위 10개 시·군·구")
display(summary.sort_values("화재 감지일 (2001~2025)", ascending=False).head(10).reset_index(drop=True))

def top_in(p, n=8):
    p = pd.Period(p, "M")
    t = pd.DataFrame({"지역": names, "감지일": RH[p].round(0), "평년(같은 달)": r_med[p.month].round(1),
                      "순위": r_rank[p].astype(int), "유형": [TYPES[k] for k in r_type[p]],
                      "품질": [LEVELS[k] for k in r_quality[p]]})
    return t.sort_values("감지일", ascending=False).head(n).reset_index(drop=True)

print(f"{CASE_MONTH} 상위 시·군·구")
top_in(CASE_MONTH)
''')

# --- cell 34
py(r'''
from matplotlib.patches import Polygon as MPoly
from matplotlib.collections import PatchCollection

def draw(ax, values, title, cmap="YlOrRd", vmax=None):
    patches, vals = [], []
    for P, v in zip(adm2, values):
        for outer, _ in P["rings"]:
            patches.append(MPoly(outer.vertices, closed=True)); vals.append(v)
    pc = PatchCollection(patches, cmap=cmap, edgecolor="#FFFFFF", linewidth=.2)
    pc.set_array(np.asarray(vals, float)); pc.set_clim(0, vmax or max(vals))
    ax.add_collection(pc); ax.autoscale_view(); ax.set_aspect(1.25); ax.axis("off"); ax.set_title(title, loc="left", fontsize=11)
    plt.colorbar(pc, ax=ax, shrink=.6)

fig, ax = plt.subplots(1, 2, figsize=(13, 7))
draw(ax[0], years_fire.to_numpy(), f"불이 난 연도 수 ({YEARS[0]}~{YEARS[1]}, 25년 중)", vmax=YEARS[1] - YEARS[0] + 1)
p = pd.Period(CASE_MONTH, "M")
draw(ax[1], RH[p].to_numpy(), f"{p.year}년 {p.month}월 화재 감지일 (NOAA-20 단위)")
plt.tight_layout(); plt.savefig(OUT_DIR / "regions_preview.png", dpi=150); plt.show()
''')

# --- cell 35
py(r'''
# 웹용 파일: 지역 경계(단순화본) + 요약, 지역별 달력(열 방향 압축)
simp = json.loads((REGION_DIR / f"geoBoundaries-{COUNTRY}-ADM2_simplified.geojson").read_text(encoding="utf-8"))
simp["features"] += patch_feats()
idx = {P["id"]: i for i, P in enumerate(adm2)}
for f in simp["features"]:
    i = idx[f["properties"]["shapeID"]]
    f["properties"] = {"id": adm2[i]["id"], "name": adm2[i]["name"], "province": adm2[i]["province"],
                       "label": adm2[i]["label"], "fire_days_2001_2025": int(round(tot[i])),
                       "years_with_fire": int(years_fire[i]), "peak_month": int(summary["가장 많이 탄 달"][i])}
(OUT_DIR / "regions.geojson").write_text(json.dumps(simp, ensure_ascii=False), encoding="utf-8")

r1 = lambda a: [None if pd.isna(x) else round(float(x), 1) for x in a]
by_region = {
    "months": [str(p) for p in months], "baseline_years": list(YEARS), "type_labels": TYPES, "quality_labels": LEVELS,
    "unit": f"VIIRS NOAA-20 기준 화재 감지일 ({GRID}° 격자 × 일), 위성 사슬 계수는 나라 단위",
    "regions": {adm2[i]["id"]: {"label": adm2[i]["label"], "value": r1(RH.loc[i]), "median_by_month": r1(r_med.loc[i]),
                                "rank": [int(x) for x in r_rank.loc[i]], "frp_mw": r1(RF.loc[i]),
                                "type": [int(x) for x in r_type.loc[i]], "quality": [int(x) for x in r_quality.loc[i]]}
                for i in range(R)},
}
(OUT_DIR / "calendar_by_region.json").write_text(json.dumps(by_region, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
for n in ["regions.geojson", "calendar_by_region.json"]:
    print(n, f"{(OUT_DIR / n).stat().st_size / 1e6:.1f} MB")
''')

# --- cell 36
md(r'''
## ⑮ 지역 단위별 신뢰 기준, 대체 지역, 인접 지역 경고

시·군·구는 대부분 불이 드물어서(대구 중구는 25년간 0건) 그 지역 숫자만 보여 주면 화면이 비거나 오차가 커집니다. 이 섹션은 네 가지를 정합니다.

1. **단위별 보정 오차:** 전국·시·도·시·군·구마다 교차검증 오차를 직접 잽니다. 오차가 `ERR_MAX` 이하인 단위만 25년 보정 시계열(MODIS 단위)로 비교합니다.
2. **오차가 큰 단위는 VIIRS만:** 2012년 이후 VIIRS(S-NPP를 NOAA-20 단위로 옮긴 값 + NOAA-20 원값)만 쓰면 MODIS 변환이 필요 없습니다. S-NPP↔NOAA-20은 같은 종류의 센서라 시·군·구에서도 잘 맞는지 아래에서 직접 확인합니다. 평년과 순위를 그 기간(약 14년) 안에서 계산합니다.
3. **자료 충분 여부:** 연간 감지일이 λ인 지역은 해마다 우연히 √λ 정도 흔들립니다(포아송). 흔들림이 `ERR_MAX` 이하가 되려면 λ ≥ 1/ERR_MAX² ≈ 11일. 이 기준으로 **충분 / 부족 / 감지 없음**을 나눕니다. 연평균은 **가장 많이 탄 한 해를 빼고** 계산합니다. 대형 산불 한 번(예: 2025년 3월 의성)이 그 지역을 "충분"으로 바꾸지 않게 하기 위해서입니다.
4. **위험 시기, 대체 지역, 인접 지역:** 자료가 부족하면 시·도(그것도 부족하면 전국) 값을 물려받고, 가장 가까운 "충분" 지역과 맞닿은 지역 목록을 붙입니다.
''')

# --- cell 37
py(r'''
ERR_MAX = 0.30            # 품질 규칙(⑫)과 같은 30% 기준
BIN_EDGES = [0, 10, 25, 50, 100, 200, np.inf]
RISK_SHARE = 0.50         # 위험 시기: 비중이 큰 달부터 더해 활동의 이만큼을 채우는 달들

def k_loyo(y):
    return k_monthly([x for x in overlap_years if x != y]) if METHOD == "A" else k_monthly(window_years(y, y))

def loyo_error(TM, TV):
    """행(지역)마다 겹침 기간 연간 |변환한 VIIRS − MODIS|의 합 / MODIS 합. 그 해는 계수 계산에서 뺀다."""
    err, act = np.zeros(len(TM)), np.zeros(len(TM))
    for y in overlap_years:
        cols = [p for p in months if p.year == y and p >= pd.Period("2012-02", "M")]
        k = k_loyo(y)
        pred = sum(TV[p].to_numpy() / k[p.month] for p in cols)
        a = TM[cols].sum(axis=1).to_numpy()
        err += np.abs(pred - a); act += a
    return pd.Series(np.where(act > 0, err / np.where(act > 0, act, 1), np.nan), index=TM.index)

prov = pd.Series([P["province"] for P in adm2])
PM, PV, PH = (T.groupby(prov.values).sum() for T in (RM, RV, RH))
nat_err = float(loyo_error(pd.DataFrame([M.to_numpy()], columns=months), pd.DataFrame([V.fillna(0).to_numpy()], columns=months))[0])
prov_err = loyo_error(PM, PV)
dist_err = loyo_error(RM, RV)

# S-NPP ↔ NOAA-20은 시·군·구에서도 맞는가 (겹침 기간 연간, 나라 계수 적용)
sn_cols = [p for p in months if OVERLAP_SN[0] <= p.year <= OVERLAP_SN[1]]
ann_r = lambda T: T[sn_cols].T.groupby([p.year for p in sn_cols]).sum().T
a_n, a_s = ann_r(RN), ann_r(RV * col(kSN))
sn_dist_err = (a_s - a_n).abs().sum(axis=1) / a_n.sum(axis=1).replace(0, np.nan)

scale = (pd.DataFrame({"구간": pd.cut(tot, BIN_EDGES, right=False), "오차": dist_err})
         .groupby("구간", observed=False).오차.agg(지역수="size", 오차_중앙값="median"))
print(f"전국 {nat_err:.1%} · 시·도 중앙값 {prov_err.median():.1%} · 시·군·구 중앙값 {dist_err.median():.1%}")
sn_scale = pd.DataFrame({"구간": pd.cut(tot, BIN_EDGES, right=False), "오차": sn_dist_err}).groupby("구간", observed=False).오차.median()
print(f"S-NPP↔NOAA-20 시·군·구 오차 중앙값 {sn_dist_err.median():.1%} (MODIS↔S-NPP는 {dist_err.median():.1%})")
print("시·군·구: 25년 누적 감지일 구간별 오차 중앙값")
display(scale.assign(오차_중앙값=(scale.오차_중앙값 * 100).round(0), SN=(sn_scale * 100).round(0)).rename(columns={"오차_중앙값": "MODIS↔S-NPP 오차 %", "SN": "S-NPP↔NOAA-20 오차 %"}))
print("시·도별 오차")
(pd.DataFrame({"오차 %": (prov_err * 100).round(0), "25년 누적 감지일": PH[base_cols].sum(axis=1).round(0)})
   .sort_values("25년 누적 감지일", ascending=False))
''')

# --- cell 38
md(r'''
**읽는 법:** 전국은 오차 약 15%로 보정이 잘 됩니다. 하지만 시·군·구는 가장 큰 지역들도 60% 이상 어긋납니다. 보정 계수를 시·도별로 따로 구해도 거의 줄지 않았습니다(시·도 69%→52%, 시·군·구 변화 없음).
작은 지역은 불이 몇 건뿐이라 해마다 우연히 흔들리고, 1 km MODIS는 VIIRS가 보는 작은 불을 놓치는 일이 많아 두 센서가 지역마다 **다른 불을 보기** 때문입니다. 계산 실수가 아니라 자료의 물리적 한계입니다.

그래서 **오차가 30% 이하인 시·도와 전국만 25년 보정 시계열**로 비교하고, 나머지 시·도와 모든 시·군·구는 **VIIRS 단일 센서(2012년~)** 기준으로 평년·순위·위험 시기를 계산합니다.
''')

md(r'''
### ⑮-2 시·군·구 장기 지표: 시·군·구별 보정 계수

한 해 값의 흔들림은 고칠 수 없지만, **지역마다 위성 비율이 다른 치우침**(소각이 많은 지역은 VIIRS가 훨씬 많이 잡음)은 지역별 계수로 줄일 수 있습니다.

- 시·군·구 계수 `f`: 겹침 기간(2012~2025) S-NPP 합 ÷ (MODIS × 전국 계수) 합. 자료가 적으면 시·도 계수 쪽으로(`F_SHRINK_D`), 시·도는 1 쪽으로(`F_SHRINK_P`) 당깁니다.
- 2012년 이전 시·군·구 값 = 전국 사슬 환산값 × `f`.
- **어떤 장기 지표를 쓸지는 검증으로 정합니다.** MODIS 시기를 흉내 내어, 겹침 기간의 MODIS로 VIIRS 값을 맞혀 봅니다(그 해는 계수 계산에서 뺌). 오차가 `ERR_MAX` 이하인 지표·지역 크기만 화면에 씁니다.
''')
py(r'''
F_SHRINK_D, F_SHRINK_P = 10, 20
cols_y = lambda y: [p for p in months if p.year == y and p >= P2012]
kk_y = {y: k_loyo(y) for y in overlap_years}
V_ann = pd.DataFrame({y: RV[cols_y(y)].sum(axis=1) for y in overlap_years})
M_k = pd.DataFrame({y: sum(RM[p] * kk_y[y][p.month] for p in cols_y(y)) for y in overlap_years})   # MODIS → S-NPP 단위 (전국 계수)

def fit_f(years):
    v, m = V_ann[years].sum(axis=1), M_k[years].sum(axis=1)
    fp = ((v.groupby(prov.values).sum() + F_SHRINK_P) / (m.groupby(prov.values).sum() + F_SHRINK_P)).reindex(prov.values).values
    return (v + F_SHRINK_D * fp) / (m + F_SHRINK_D)

f_dist = fit_f(overlap_years)
RH_lt = RH.copy()
RH_lt.loc[:, months < P2012] = RH.loc[:, months < P2012].mul(f_dist, axis=0)
lt_total = RH_lt[base_cols].sum(axis=1)                      # 시·군·구 계수를 적용한 25년 화재 칸

pred_lt = pd.DataFrame({y: M_k[y] * fit_f([x for x in overlap_years if x != y]) for y in overlap_years})
size_bin = pd.cut(lt_total, BIN_EDGES, right=False)
rel = lambda p_, a_: (p_ - a_).abs() / a_.replace(0, np.nan)
oy7a, oy7b = overlap_years[:7], overlap_years[7:]
lt_err = pd.DataFrame({
    "14년 합계": rel(pred_lt.sum(axis=1), V_ann.sum(axis=1)),
    "7년 합계": pd.concat([rel(pred_lt[b].sum(axis=1), V_ann[b].sum(axis=1)) for b in (oy7a, oy7b)], axis=1).median(axis=1),
    "한 해 값": ((pred_lt - V_ann).abs().sum(axis=1) / V_ann.sum(axis=1).replace(0, np.nan)),
})
lt_table = lt_err.groupby(size_bin.values, observed=False).median()
vy, my = V_ann >= 3, pred_lt >= 3
fire_year_recall = float(((vy & my).sum(axis=1) / vy.sum(axis=1).replace(0, np.nan)).median())
print("시·군·구 크기(25년 화재 칸)별 오차 중앙값 %"); display((lt_table * 100).round(0))
print(f"불 난 해(3칸 이상) 재현율: VIIRS가 불을 본 해 중 MODIS 환산으로도 잡히는 비율 {fire_year_recall:.0%}")

# 판정: 14년 합계 오차가 ERR_MAX 이하인 크기 구간부터 장기 합계를 씀
ok_bins = [b for b, e in lt_table["14년 합계"].items() if e <= ERR_MAX]
LT_MIN = min(b.left for b in ok_bins) if ok_bins else np.inf
lt_quality = pd.Series(np.select([lt_total >= max(LT_MIN, 50), lt_total >= LT_MIN], ["높음", "보통"], "낮음"), index=lt_total.index)
print(f"→ 장기 합계는 25년 화재 칸 {LT_MIN:g}개 이상 시·군·구에서 사용. 품질: {lt_quality.value_counts().to_dict()}")
print("→ 7년(10년 단위) 비교, 불 난 해 수, 한 해 값은 기준 미달이라 시·군·구에서는 2012년 이후만 씀")
''')

# --- cell 39
py(r'''
# VIIRS 단일 센서 기준 (2012-02 ~ YEARS 끝). 1월은 2013년부터라 13년.
v_cols = [p for p in base_cols if p >= pd.Period("2012-02", "M")]
v_years = YEARS[1] - 2012 + 1
MIN_ANNUAL = 1 / ERR_MAX ** 2       # 연평균 감지일이 이만큼이면 우연한 흔들림 ≤ ERR_MAX

def stats(T, cols):
    med = pd.DataFrame({m: T[[p for p in cols if p.month == m]].median(axis=1) for m in range(1, 13)})
    q25 = pd.DataFrame({m: T[[p for p in cols if p.month == m]].quantile(.25, axis=1) for m in range(1, 13)})
    q75 = pd.DataFrame({m: T[[p for p in cols if p.month == m]].quantile(.75, axis=1) for m in range(1, 13)})
    yrs = pd.DataFrame({m: (T[[p for p in cols if p.month == m]] > 0).sum(axis=1) for m in range(1, 13)})
    pct = pd.DataFrame(index=T.index, columns=months, dtype=float); rank = pct.copy(); n = pct.copy()
    for m in range(1, 13):
        B = T[[p for p in cols if p.month == m]].to_numpy()
        for p in [q for q in months if q.month == m]:
            v = T[p].to_numpy()[:, None]
            pct[p], rank[p], n[p] = (B < v).mean(1), (B > v).sum(1) + 1, B.shape[1]
    mt = pd.DataFrame({m: T[[p for p in cols if p.month == m]].sum(axis=1) for m in range(1, 13)})
    noise = BAND_NOISE * np.sqrt(np.maximum(med, 1))
    lo = np.minimum(pd.DataFrame({m: T[[p for p in cols if p.month == m]].quantile(BAND_Q[0], axis=1) for m in range(1, 13)}), med - noise)
    hi = np.maximum(pd.DataFrame({m: T[[p for p in cols if p.month == m]].quantile(BAND_Q[1], axis=1) for m in range(1, 13)}), med + noise)
    return dict(med=med, q25=q25, q75=q75, lo=lo, hi=hi, yrs=yrs, pct=pct, rank=rank, n=n, mt=mt)

def sufficiency(annual, total):
    """total: 전체 기간 연평균(감지가 한 번이라도 있었는지), annual: 가장 많이 탄 해를 뺀 연평균"""
    return np.select([total <= 0, annual < MIN_ANNUAL], ["감지 없음", "부족"], "충분")

rv = stats(RVN, v_cols)
def typical_annual(T):
    """연도별 합에서 가장 많이 탄 한 해를 뺀 평균. 대형 사건 한 번이 '충분' 판정을 좌우하지 않게 한다."""
    A = T[v_cols].T.groupby([p.year for p in v_cols]).sum().T
    return (A.sum(axis=1) - A.max(axis=1)) / (A.shape[1] - 1)

r_annual_all = RVN[v_cols].sum(axis=1) / v_years
r_annual = typical_annual(RVN)
r_suff = pd.Series(sufficiency(r_annual.to_numpy(), r_annual_all.to_numpy()), index=RVN.index)

p_basis = pd.Series(np.where(prov_err <= ERR_MAX, "보정 25년", "VIIRS 2012~"), index=PH.index)
PVN = RVN.groupby(prov.values).sum(min_count=1)
pv_v, pv_h = stats(PVN, v_cols), stats(PH, base_cols)
p_annual = typical_annual(PVN)
p_suff = pd.Series(sufficiency(p_annual.to_numpy(), (PVN[v_cols].sum(axis=1) / v_years).to_numpy()), index=PH.index)

print(f"충분 기준: VIIRS 연평균 감지일 {MIN_ANNUAL:.1f}일 이상 (가장 많이 탄 해를 뺀 {v_years - 1}년 평균)")
print("단순 평균으로는 충분이지만 한 해를 빼면 부족인 지역:", [adm2[i]["label"] for i in range(R) if r_annual_all[i] >= MIN_ANNUAL > r_annual[i]])
print("시·군·구:", r_suff.value_counts().to_dict())
print("시·도 기준 시계열:", p_basis.to_dict())
print("시·도 충분 여부:", p_suff.to_dict())
''')

# --- cell 40
py(r'''
def cyclic_order(ms):
    """달 목록을 해를 넘겨도 이어지게 정렬: 가장 긴 빈 구간 바로 다음 달부터 읽는다.
    예) [1, 11, 12] → [11, 12, 1], [1, 2, 12] → [12, 1, 2]. 빈 구간 길이가 같으면 시즌 시작 월(SEASON_START)에 가까운 쪽부터"""
    ms = sorted(ms)
    if len(ms) < 2:
        return ms
    n = len(ms)
    gap = lambda i: (ms[(i + 1) % n] - ms[i] - 1) % 12          # ms[i] 뒤에 비어 있는 달 수
    i = max(range(n), key=lambda i: (gap(i), -((ms[(i + 1) % n] - SEASON_START) % 12)))
    s = (i + 1) % n
    return ms[s:] + ms[:s]

def risk_period(m):
    m = np.asarray(m, float)
    if m.sum() == 0:
        return [], 0.0
    picked, acc = [], 0.0
    for i in np.argsort(-m, kind="stable"):
        picked.append(int(i) + 1); acc += m[i] / m.sum()
        if acc >= RISK_SHARE:
            break
    return cyclic_order(picked), round(acc, 3)

nat_mt = H[full].groupby(H[full].index.month).sum().reindex(range(1, 13), fill_value=0)   # 완전한 해들의 달별 합
nat_risk = risk_period(nat_mt)
nat_peak = int(nat_mt.idxmax())   # 정점 달: 달별 합이 가장 큰 달 (시·군·구 peak_month와 같은 정의)
p_risk = {pv: risk_period((pv_h if p_basis[pv] == "보정 25년" else pv_v)["mt"].loc[pv]) for pv in PH.index}

# 대체 시·도: 내 시·도가 부족하면 중심이 가장 가까운 "충분" 시·도
cen = np.array([P["center"] for P in adm2])
km = lambda a, b: np.hypot((a[..., 0] - b[..., 0]) * KMX((a[..., 1] + b[..., 1]) / 2), (a[..., 1] - b[..., 1]) * 111.0)   # 경도 1°의 km (① 설정 KM_LON, 없으면 위도별)
p_cen = {pv: cen[(prov == pv).to_numpy()].mean(0) for pv in PH.index}
ok_prov = [pv for pv in PH.index if p_suff[pv] == "충분"]
def ref_province(pv):
    if p_suff[pv] == "충분":
        return pv, "시·도"
    near = min(ok_prov, key=lambda q: float(km(p_cen[q], p_cen[pv])))
    return near, "인접 시·도"

def region_risk(i):
    if r_suff[i] == "충분":
        return (*risk_period(rv["mt"].loc[i]), "시·군·구")
    pv, src = ref_province(prov[i])
    return (*p_risk[pv], f"{src} ({pv})")
r_risk = [region_risk(i) for i in range(R)]

# 대체 지역: FALLBACK_KM 안에서 가장 가까운 "충분" 시·군·구 (중심점 거리). 너무 멀면 비교 의미가 없어 넣지 않음
FALLBACK_KM = 60
suff_idx = np.where(r_suff == "충분")[0]
def fallback(i):
    if r_suff[i] == "충분":
        return None
    pv, src = ref_province(prov[i])
    d = km(cen[suff_idx], cen[i])
    j = int(suff_idx[d.argmin()])
    near = {"region": adm2[j]["id"], "region_label": adm2[j]["label"], "distance_km": round(float(d.min()), 1)} if d.min() <= FALLBACK_KM else None
    return {"province": prov[i], "province_sufficient": bool(p_suff[prov[i]] == "충분"), "ref_province": pv, "ref_from": src, "nearest_sufficient": near}
r_fallback = [fallback(i) for i in range(R)]

# 인접 지역: 두 지역의 경계 꼭짓점이 ADJ_TOL 안에 있으면 맞닿은 것으로 봄
ADJ_TOL = 0.002   # 도, 약 200 m
pts = np.concatenate([P["pts"] for P in adm2])
owner = np.concatenate([np.full(len(P["pts"]), i) for i, P in enumerate(adm2)])
pairs = owner[cKDTree(pts).query_pairs(ADJ_TOL, output_type="ndarray")]
neighbors = {i: set() for i in range(R)}
for a, b in pairs[pairs[:, 0] != pairs[:, 1]]:
    neighbors[a].add(int(b)); neighbors[b].add(int(a))

lab = lambda i: adm2[i]["label"]
by_name = {P["name"]: i for i, P in enumerate(adm2)}
print("이웃이 없는 지역(섬):", [lab(i) for i in range(R) if not neighbors[i]])
print(f"{CASE_EVENT[2][0]} 이웃:", sorted(lab(j) for j in neighbors[by_name[CASE_EVENT[2][0]]]))
if COUNTRY == "KOR":
    daegu_jung = next(i for i in range(R) if adm2[i]["name"].startswith("Jung-gu") and prov[i] == "대구")
    print("대구 중구:", r_suff[daegu_jung], "| 위험 시기", r_risk[daegu_jung], "| 대체", r_fallback[daegu_jung])
pd.DataFrame({"지역": [lab(i) for i in suff_idx], "VIIRS 연평균 감지일": r_annual[suff_idx].round(1).values,
              "위험 시기": [r_risk[i][0] for i in suff_idx]}).sort_values("VIIRS 연평균 감지일", ascending=False).reset_index(drop=True)
''')

# --- cell 41
md(r'''
### 인접 지역 경고: 2025년 3월 경북 산불로 확인

경고 규칙 두 가지를 비교합니다.
- **맞닿은 지역 규칙:** 경계가 맞닿은 시·군·구에서 불이 감지되면 경고.
- **거리 규칙:** 내 지역 중심에서 `ALERT_KM` 안에서 불이 감지되면 경고.

월 단위로는 타이밍이 안 보이므로 **일 단위**(VIIRS 화재 감지일, 원값)로 봅니다.
''')

# --- cell 42
py(r'''
ALERT_KM = 50
event = [by_name[n] for n in CASE_EVENT[2]]
win = viirs_r[viirs_r.acq_date.between(CASE_EVENT[0], CASE_EVENT[1])].assign(cell=lambda d: key(d, GRID))
win = win.drop_duplicates(["cell", "acq_date"])
day = win[win.region.isin(event)]
daily = day.groupby([day.acq_date.dt.strftime("%m-%d"), day.region]).size().unstack(fill_value=0).reindex(columns=event, fill_value=0).rename(columns=lab)

def first_alerts(i):
    """지역 i에 대해: 자기 지역 첫 감지일, 맞닿은 지역 첫 감지일, ALERT_KM 안 첫 감지일 (2025-03-20 이후)."""
    own = win[win.region == i].acq_date.min()
    nb_ = win[win.region.isin(neighbors[i])].acq_date.min()
    d = km(win[["longitude", "latitude"]].to_numpy(), cen[i])
    near = win[(d <= ALERT_KM) & (win.region != i)].acq_date.min()
    f = lambda t: t.strftime("%m-%d") if pd.notna(t) else None
    lead = lambda t: int((own - t).days) if pd.notna(t) and pd.notna(own) else None
    return {"지역": lab(i), "자기 지역 첫 감지": f(own), "맞닿은 지역 첫 감지": f(nb_), "앞선 일수(맞닿음)": lead(nb_),
            f"{ALERT_KM} km 안 첫 감지": f(near), f"앞선 일수({ALERT_KM} km)": lead(near)}

display(daily)
lead_table = pd.DataFrame([first_alerts(i) for i in event[1:]])
lead_table
''')

# --- cell 43
py(r'''
# 웹용 파일 갱신
simp = json.loads((OUT_DIR / "regions.geojson").read_text(encoding="utf-8"))
for f in simp["features"]:
    i = idx[f["properties"]["id"]]
    rm, rs, rfrom = r_risk[i]
    f["properties"].update({
        "province": adm2[i]["province"], "label": adm2[i]["label"],
        "province_ko": adm2[i]["province_ko"], "province_en": adm2[i]["province_en"], "name_ko": adm2[i]["name_ko"],
        "sufficiency": r_suff[i], "viirs_annual_fire_days": round(float(r_annual[i]), 1), "viirs_annual_all_years": round(float(r_annual_all[i]), 1),
        "longterm": {"fire_cells_2001_2025": round(float(lt_total[i]), 1), "annual_avg": round(float(lt_total[i]) / len(range(YEARS[0], YEARS[1] + 1)), 1),
                     "quality": lt_quality[i], "district_factor": round(float(f_dist[i]), 3)},
        "risk_months": rm, "risk_share": rs, "risk_from": rfrom,
        "fallback": r_fallback[i], "neighbors": [adm2[j]["id"] for j in sorted(neighbors[i])]})
(OUT_DIR / "regions.geojson").write_text(json.dumps(simp, ensure_ascii=False), encoding="utf-8")

ints = lambda a: [int(x) for x in a]
for i in range(R):
    d = by_region["regions"][adm2[i]["id"]]
    d.update({"label": adm2[i]["label"], "sufficiency": r_suff[i],
              "province_ko": adm2[i]["province_ko"], "province_en": adm2[i]["province_en"], "name_ko": adm2[i]["name_ko"],
              "raw_before": r1(R_naive.loc[i]),   # value(25년 보정)와 같은 칸: 2012-02 전도 MODIS 원값이 있음
              "viirs": {"value": r1(RVN.loc[i]), "median_by_month": r1(rv["med"].loc[i]),
                        "q25_by_month": r1(rv["q25"].loc[i]), "q75_by_month": r1(rv["q75"].loc[i]),
                        "band_low_by_month": r1(rv["lo"].loc[i]), "band_high_by_month": r1(rv["hi"].loc[i]),
                        "years_with_fire_by_month": ints(rv["yrs"].loc[i]),
                        "rank": ints(rv["rank"].loc[i]), "years_in_month": ints(rv["n"].loc[i])}})
by_region["note"] = ("시·군·구는 두 센서가 해마다 크게 어긋나므로(교차검증 오차 중앙값 약 90%) 비교는 'viirs'(2012년~ 단일 센서) 값을 쓴다. "
                     "'value' 등 MODIS 단위 값은 25년 지도 같은 장기 누적 표시에만 쓴다.")
(OUT_DIR / "calendar_by_region.json").write_text(json.dumps(by_region, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

def prov_block(pv):
    s, T = (pv_h, PH) if p_basis[pv] == "보정 25년" else (pv_v, PVN)
    return {"basis": p_basis[pv], "loyo_error": None if pd.isna(prov_err[pv]) else round(float(prov_err[pv]), 3),
            "sufficiency": p_suff[pv], "value": r1(T.loc[pv]), "median_by_month": r1(s["med"].loc[pv]),
            "q25_by_month": r1(s["q25"].loc[pv]), "q75_by_month": r1(s["q75"].loc[pv]),
            "band_low_by_month": r1(s["lo"].loc[pv]), "band_high_by_month": r1(s["hi"].loc[pv]),
            "rank": ints(s["rank"].loc[pv]), "years_in_month": ints(s["n"].loc[pv]),
            "ratio_to_median": [round(float(T.loc[pv, p] / s["med"].loc[pv, p.month]), 2) if s["med"].loc[pv, p.month] > 0 else None for p in months],
            "risk_months": p_risk[pv][0], "risk_share": p_risk[pv][1],
            "regions": [adm2[i]["id"] for i in range(R) if prov[i] == pv]}
by_province = {"months": by_region["months"], "provinces": {pv: prov_block(pv) for pv in PH.index}}
(OUT_DIR / "calendar_by_province.json").write_text(json.dumps(by_province, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

meta = json.loads((OUT_DIR / "meta.json").read_text(encoding="utf-8"))
meta["regions"] = {
    "boundaries": "geoBoundaries KOR ADM2/ADM1 (CC BY 3.0)" + (" + 영광군 보강 (전남 − 다른 시·군)" if PATCH_ADM2.exists() else ""), "n_regions": R, "err_max": ERR_MAX,
    "error": {"national": round(nat_err, 3), "province": prov_err.round(3).to_dict(),
              "district_median": round(float(dist_err.median()), 3)},
    "snpp_noaa20_district_error": {"median": round(float(sn_dist_err.median()), 3),
                                    "by_size": {str(k): None if pd.isna(v) else round(float(v), 3) for k, v in sn_scale.items()}},
    "district_error_by_size": [{"bin": str(b), "n": int(r["지역수"]), "median": None if pd.isna(r["오차_중앙값"]) else round(float(r["오차_중앙값"]), 3)}
                               for b, r in scale.iterrows()],
    "province_basis": p_basis.to_dict(), "district_basis": "VIIRS 2012~",
    "longterm": {"method": "시·군·구별 보정 계수 (시·도·1 쪽으로 당김)", "shrink": [F_SHRINK_D, F_SHRINK_P], "min_total": LT_MIN,
                 "error_by_size": {str(b): {k: (None if pd.isna(v) else round(float(v), 3)) for k, v in r.items()} for b, r in lt_table.iterrows()},
                 "fire_year_recall": round(fire_year_recall, 2), "quality_counts": lt_quality.value_counts().to_dict(),
                 "used": "25년 합계·연평균만", "not_used": "7년(10년 단위) 비교, 불 난 해 수, 한 해·한 달 값 (오차 기준 미달)"},
    "sufficient_min_viirs_annual": round(MIN_ANNUAL, 1), "sufficiency_annual": "가장 많이 탄 한 해를 뺀 연평균", "sufficiency_counts": r_suff.value_counts().to_dict(),
    "province_sufficiency": p_suff.to_dict(), "risk_share": RISK_SHARE,
    "national_risk": {"months": nat_risk[0], "share": nat_risk[1], "peak_month": nat_peak,
                      "years": list(YEARS)},
    "adjacency_tol_deg": ADJ_TOL, "alert_km": ALERT_KM,
    "alert_rules": {"neighbor": "맞닿은 시·군·구에서 감지", "distance": f"지역 중심 {ALERT_KM} km 안에서 감지",
                    "monthly": f"맞닿은 '충분' 시·군·구의 이번 달 VIIRS 감지일이 같은 달 분포 상위 {1 - TYPE_PCT:.0%} 초과"},
    "case_event": {"window": list(CASE_EVENT[:2]), "regions": CASE_EVENT[2], "lead": lead_table.to_dict("records")},
    **({"event_2025_03": lead_table.to_dict("records")} if COUNTRY == "KOR" else {}),
}
(OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
for n in ["regions.geojson", "calendar_by_region.json", "calendar_by_province.json"]:
    print(n, f"{(OUT_DIR / n).stat().st_size / 1e6:.2f} MB")
''')

md(r'''
## ⑯ 감지 묶음: 화재 칸을 "불 하나" 단위로 묶기

화재 칸 합계는 넓이와 기간이 섞인 양이라, 화면에서 설명할 때는 "불 하나"로 묶어 보여 주는 게 쉽습니다. 묶는 규칙:

- 두 화재 칸이 **`D` km 안**에 있고 날짜 차이가 **`G`일 이하**면 같은 묶음. 이어진 것끼리는 모두 하나로 (연결 성분).
- 기준을 우리가 정하므로 세 규칙(A 2 km·1일, B 3 km·2일, C 5 km·3일)으로 결과가 얼마나 흔들리는지 보고, **알려진 대형 산불**이 하나의 묶음으로 잡히는지 확인합니다.
- 위성마다 묶음 모양이 달라 보정이 어렵기 때문에 **NOAA-20(2018년 4월~)만** 씁니다. 보정·달력·순위에는 계속 화재 칸 합계를 쓰고, 묶음은 설명과 사건 목록에만 씁니다.

화면에 쓰는 세 숫자 (지역 × 월):
- **불이 잡힌 날** (얼마나 오래): 그 달 감지가 있었던 날짜 수
- **가장 넓게 탄 날** (얼마나 넓게): 하루 화재 칸 수의 최댓값
- **감지 묶음 수**: 그 달에 시작한 묶음 수 (그중 10칸 이상인 큰 묶음 수도 따로)
''')
py(r'''
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

EVENT_RULES = {"A": (2, 1), "B": (3, 2), "C": (5, 3)}   # (거리 km, 날짜 차이 일)
EVENT_RULE = "B"
BIG_EVENT = 10                                           # 큰 묶음: 화재 칸 10개 이상
# KNOWN_FIRES: ① 설정의 나라별 값 (알려진 대형 산불: 시작일, 위도, 경도)

ec = (n20_r.assign(cell=key(n20_r, GRID))
      .groupby(["cell", "acq_date"]).agg(lat=("latitude", "mean"), lon=("longitude", "mean"), frp=("frp", "sum"),
                                          region=("region", lambda s: s.mode().iat[0])).reset_index())
if KM_LON:   # 경도 1° = KM_LON km로 펼친 평면 (한국·캘리포니아·BC 등 위도 폭이 좁은 지역)
    ex, ey = ec.lon.to_numpy() * KM_LON, ec.lat.to_numpy() * 111.0
    etree = cKDTree(np.c_[ex, ey])
else:        # 위도 폭이 넓은 지역(칠레): 지구 반지름 6371 km 구 위의 3차원 좌표 → 짧은 거리에서 현 길이 ≈ 실제 거리
    _la, _lo = np.radians(ec.lat.to_numpy()), np.radians(ec.lon.to_numpy())
    etree = cKDTree(6371.0 * np.c_[np.cos(_la) * np.cos(_lo), np.cos(_la) * np.sin(_lo), np.sin(_la)])
et = (ec.acq_date - ec.acq_date.min()).dt.days.to_numpy()

def cluster(D, G):
    pr = etree.query_pairs(D, output_type="ndarray")
    pr = pr[np.abs(et[pr[:, 0]] - et[pr[:, 1]]) <= G]
    A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(ec), len(ec)))
    return connected_components(A, directed=False)[1]

def summarize(lab):
    e = ec.assign(ev=lab)
    g = e.groupby("ev").agg(start=("acq_date", "min"), end=("acq_date", "max"), cells=("cell", "size"),
                            lat=("lat", "mean"), lon=("lon", "mean"), frp=("frp", "sum"))
    daily_n = e.groupby(["ev", "acq_date"]).size()
    g["peak"], g["peak_date"] = daily_n.groupby("ev").max(), daily_n.groupby("ev").idxmax().map(lambda x: x[1])
    g["days"] = (g.end - g.start).dt.days + 1
    g["regions"] = e[e.region >= 0].groupby("ev").region.agg(lambda s: list(s.value_counts().index))
    return e, g

def check_known(e, g):
    rows = []
    for k, (day, la, lo) in KNOWN_FIRES.items():
        day = pd.Timestamp(day)
        near = e[e.acq_date.between(day - pd.Timedelta(days=1), day + pd.Timedelta(days=12)) & (np.hypot((e.lat - la) * 111, (e.lon - lo) * KMX(la)) <= 40)]
        c = near.ev.value_counts()
        if c.empty:
            rows.append({"화재": k, "근처 묶음 수": 0}); continue
        m = g.loc[c.index[0]]
        rows.append({"화재": k, "근처 묶음 수": len(c), "주 묶음 비중": round(c.iloc[0] / c.sum(), 2),
                     "기간": f"{m.start:%m/%d}~{m.end:%m/%d}", "화재 칸": int(m.cells), "가장 넓은 날 칸": int(m.peak)})
    return pd.DataFrame(rows).set_index("화재")

ev_sens, ev_known, ev_monthly = [], {}, {}
for name, (D, G) in EVENT_RULES.items():
    e, g = summarize(cluster(D, G))
    ev_sens.append({"규칙": f"{name} {D} km·{G}일", "묶음 수": len(g), "1칸짜리 비율": round((g.cells == 1).mean(), 2),
                    f"큰 묶음 ({BIG_EVENT}칸+)": int((g.cells >= BIG_EVENT).sum())})
    ev_known[name] = check_known(e, g)
    ev_monthly[name] = g.groupby(g.start.dt.to_period("M")).size()
ev_corr = pd.DataFrame(ev_monthly).fillna(0).corr().round(2)
display(pd.DataFrame(ev_sens).set_index("규칙"))
for name in EVENT_RULES:
    print(f"규칙 {name}: 알려진 대형 산불"); display(ev_known[name])
print("월별 묶음 수의 규칙 간 상관:"); ev_corr
''')
md(r'''
**읽는 법:** 세 규칙 모두 알려진 대형 산불을 같은 기간·같은 크기의 묶음으로 잡고, 같은 날 60 km 떨어져 난 고성과 강릉·동해 산불은 따로 잡습니다. 월별 묶음 수도 규칙 사이 상관이 거의 1이라 **기준을 바꿔도 결론이 흔들리지 않습니다.** 가장 촘촘한 A는 의성 산불 주변에 작은 조각이 더 생겨, 가운데인 **B(3 km·2일)**를 씁니다.

묶음의 약 90%는 화재 칸 1개짜리입니다. 즉 "묶음 수"는 대부분 작은 소각이 좌우하므로, 화면에서는 **큰 묶음(10칸 이상) 수**와 **가장 큰 묶음**을 함께 보여 줘야 의미가 있습니다.
''')
py(r'''
ev_cells, events = summarize(cluster(*EVENT_RULES[EVENT_RULE]))
ev_months = [p for p in months if p >= N20_START]
ev_cells["m"] = ev_cells.acq_date.dt.to_period("M")
ev_start_m = events.start.dt.to_period("M")
main_region = events.regions.map(lambda r: r[0] if isinstance(r, list) and r else -1)

def per_region_month(s):
    return s.unstack(fill_value=0).reindex(index=range(R), columns=ev_months, fill_value=0)

rv_days = per_region_month(ev_cells[ev_cells.region >= 0].groupby(["region", "m"]).acq_date.nunique())
rv_peak = per_region_month(ev_cells[ev_cells.region >= 0].groupby(["region", "m", "acq_date"]).size().groupby(level=[0, 1]).max())
ev_rm = pd.DataFrame({"region": main_region, "m": ev_start_m, "big": events.cells >= BIG_EVENT})
rv_n = per_region_month(ev_rm[ev_rm.region >= 0].groupby(["region", "m"]).size())
rv_big = per_region_month(ev_rm[(ev_rm.region >= 0) & ev_rm.big].groupby(["region", "m"]).size())

def row(i, p):
    return {"지역": lab(i), "불이 잡힌 날": int(rv_days.loc[i, p]), "가장 넓게 탄 날 (칸)": int(rv_peak.loc[i, p]),
            "묶음 수": int(rv_n.loc[i, p]), "큰 묶음 수": int(rv_big.loc[i, p]), "화재 칸 합계": int(RN.loc[i, p])}
if COUNTRY == "KOR":
    print("예시: 고성 2019년 4월, 의성 2025년 3월")
    display(pd.DataFrame([row(next(i for i in range(R) if adm2[i]["label"] == "강원 Goseong-gun"), pd.Period("2019-04", "M")),
                          row(by_name["Uiseong-gun"], pd.Period("2025-03", "M"))]).set_index("지역"))
else:
    print(f"예시: {CASE_EVENT[2][0]} {CASE_EVENT[0][:7]}")
    display(pd.DataFrame([row(by_name[CASE_EVENT[2][0]], pd.Period(CASE_EVENT[0][:7], "M"))]).set_index("지역"))
''')
py(r'''
# 웹용 파일: 큰 묶음 목록 + 지역 × 월 세 숫자
ev_out = events[events.cells >= 3].sort_values("start")
ev_json = [{"id": int(k), "start": f"{r.start:%Y-%m-%d}", "end": f"{r.end:%Y-%m-%d}", "days": int(r.days), "cells": int(r.cells),
            "peak_cells": int(r.peak), "peak_date": f"{r.peak_date:%Y-%m-%d}", "lat": round(float(r.lat), 3), "lon": round(float(r.lon), 3),
            "frp_mw": round(float(r.frp), 1), "regions": [adm2[j]["id"] for j in (r.regions if isinstance(r.regions, list) else [])]}
           for k, r in ev_out.iterrows()]
ints2 = lambda df, i: [int(x) for x in df.loc[i]]
events_by_region = {
    "months": [str(p) for p in ev_months], "sensor": "VIIRS NOAA-20",
    "rule": {"name": EVENT_RULE, "distance_km": EVENT_RULES[EVENT_RULE][0], "gap_days": EVENT_RULES[EVENT_RULE][1], "big_event_cells": BIG_EVENT},
    "regions": {adm2[i]["id"]: {"fire_days": ints2(rv_days, i), "peak_day_cells": ints2(rv_peak, i),
                                "events": ints2(rv_n, i), "big_events": ints2(rv_big, i)} for i in range(R)},
}
(OUT_DIR / "events.json").write_text(json.dumps(ev_json, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(OUT_DIR / "events_by_region.json").write_text(json.dumps(events_by_region, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

meta = json.loads((OUT_DIR / "meta.json").read_text(encoding="utf-8"))
meta["events"] = {"sensor": "VIIRS NOAA-20", "rule": events_by_region["rule"], "sensitivity": ev_sens,
                  "known_fires": {k: v.reset_index().to_dict("records") for k, v in ev_known.items()},
                  "monthly_count_correlation": ev_corr.to_dict(),
                  "note": "묶음은 설명용. 보정·달력·순위에는 화재 칸 합계를 쓴다."}
(OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
for n in ["events.json", "events_by_region.json"]:
    print(n, f"{(OUT_DIR / n).stat().st_size / 1e6:.2f} MB")
''')

md(r'''
## ⑰ 외부 검증: 산림청 산불 통계와 비교

위성 결과를 **위성과 무관한 자료**로 확인합니다. 산림청 산불 통계(2011년~)에는 산불마다 발생일, 장소(시·도 시·군·구 읍·면), 원인, 피해 면적이 있습니다.

1. **장소 → 시·군·구:** 한글 시·군·구 이름을 로마자로 바꿔 같은 시·도 안의 경계 이름과 맞춥니다. 맞지 않는 몇 곳은 직접 지정합니다.
2. **연도·월 비교:** 하모니제이션한 화재 칸 합계가 공식 건수·면적과 같이 움직이는지 (순위 상관).
3. **크기별 감지율 (NOAA-20 시기):** 공식 산불이 난 시·군·구에서 그날부터 2일 안에 위성 감지가 있었는가. 같은 지역의 30일 전·후 날짜로 같은 계산을 해서 "우연히 맞을 확률"과 비교합니다.
4. **큰 산불 (100 ha 이상):** 공식 면적과 위성 화재 칸 수의 순위 상관.
5. **공식 기록 없는 큰 묶음:** 위성 큰 묶음(10칸 이상) 중 같은 시·군·구·같은 시기에 공식 산불이 없는 것. 산불 통계에 들어가지 않는 불(농경지 소각, 군사 지역 등) 후보입니다.

공식 통계는 산림 안 산불만 다루고, 위성은 농경지 소각도 잡으므로 둘이 완전히 같을 수는 없습니다. 그 차이 자체가 인사이트입니다.
''')
py(r'''
import difflib, re
from scipy.stats import spearmanr

def rr(s):
    """한글 → 국어의 로마자 표기법 (기본 규칙 + 연음, ㄹ 동화 일부). 이름 맞추기용."""
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

base_name = lambda n: re.sub(r"\[.*?\]", "", n).split("-")[0].strip().lower().replace(" ", "")
by_prov = {}
for i, P in enumerate(adm2):
    by_prov.setdefault(P["province"], []).append(i)
lab_idx = {P["label"]: i for i, P in enumerate(adm2)}
# 이름으로 맞지 않는 곳: 2023년 대구로 편입된 군위, 인천의 생활권 이름, 세종(시·군·구가 하나)
KFS_FIX = {("대구", "군위"): "대구 Gunwi-gun", ("경북", "군위"): "대구 Gunwi-gun",("인천", "영종"): "인천 Jung-gu [Central District]", ("인천", "검단"): "인천 Seo-gu [West District]"}
_cache = {}
def match_sgg(pv, sgg):
    if (pv, sgg) in _cache: return _cache[(pv, sgg)]
    if (pv, sgg) in KFS_FIX: res = (lab_idx[KFS_FIX[(pv, sgg)]], 1.0)
    elif pv == "세종": res = (lab_idx["세종 Sejong-si"], 1.0)
    else:
        r, best, bs = rr(sgg), -1, 0.0
        for i in [i for p in {"전남광주": ["전남", "광주"]}.get(pv, [pv]) for i in by_prov.get(p, [])]:
            b = base_name(adm2[i]["name"]); sc = difflib.SequenceMatcher(None, r, b).ratio()
            if len(b) >= 3 and r.startswith(b): sc = max(sc, 0.95)
            if sc > bs: best, bs = i, sc
        res = (best if bs >= 0.8 else -1, bs)
    _cache[(pv, sgg)] = res
    return res

HAS_EXT = EXT_POINTS is not None and EXT_POINTS.exists()
HAS_KFS = (KFS_FILE is not None and KFS_FILE.exists()) or HAS_EXT
if HAS_EXT:   # 좌표가 있는 기록: 점이 들어간 하위 구역으로 배정 (경계 밖 NEAREST_MAX 안은 가장 가까운 구역)
    C_ = EXT_COLS
    _x = pd.read_csv(EXT_POINTS)
    if C_["keep"]:
        _x = _x[_x[C_["keep"][0]] == C_["keep"][1]]
    _x = _x[_x[C_["date"]].notna() & _x[C_["lat"]].notna()]
    _d = pd.to_datetime(_x[C_["date"]].astype(str).str[:10], errors="coerce")
    _ok = _d.dt.year.between(YEARS[0], YEARS[1] + 1)   # 원자료의 잘못된 날짜(예: 0212-01-12)는 버림
    print("날짜 오류로 뺀 기록:", int((~_ok).sum()))
    _x, _d = _x[_ok], _d[_ok]
    kfs = pd.DataFrame({"date": _d, "place": _x[C_["place"]].fillna("").astype(str), "cause": _x[C_["cause"]],
                        "ha": pd.to_numeric(_x[C_["size"]], errors="coerce").fillna(0) * C_["to_ha"]})
    _xy = _x[[C_["lon"], C_["lat"]]].to_numpy()
    _r = locate(_xy, adm2); _r[_r < 0] = nearest(_xy[_r < 0], adm2, NEAREST_MAX)
    kfs["region"] = _r
    print(f"{EXT_NAME}: 산불 {len(kfs):,}건 ({kfs.date.min():%Y-%m} ~ {kfs.date.max():%Y-%m}), 하위 구역 배정 {(kfs.region >= 0).mean():.1%}")
elif HAS_KFS:
    kfs = pd.read_excel(KFS_FILE, header=0); kfs.columns = ["date", "place", "cause", "ha"]
    kfs["date"] = pd.to_datetime(kfs.date.astype(str).str[:10]); tok = kfs.place.str.split()
    kfs["region"] = [match_sgg(p, s)[0] for p, s in zip(tok.str[0], tok.str[1].fillna(""))]
    unmatched = kfs[kfs.region < 0].place.str.split().str[:2].str.join(" ").value_counts()
    print(f"산림청 기록 {len(kfs):,}건 ({kfs.date.min():%Y-%m} ~ {kfs.date.max():%Y-%m}), 시·군·구 매칭 {(kfs.region >= 0).mean():.1%}")
    print("매칭 안 됨:", unmatched.to_dict(), "")
else:
    print("산림청 통계 파일이 없어 ⑰을 건너뜁니다:", KFS_FILE)

# 크기별 감지율 전용 기록: 모든 크기 개별 산불이 일부 기간만 있으면 감지율·큰 산불 비교에만 쓰고, 연·월 상관은 EXT_POINTS로 계산
HAS_DET = DETECT_POINTS is not None and DETECT_POINTS.exists()
if HAS_DET:
    _y = pd.read_csv(DETECT_POINTS)
    _y = _y[_y.date.notna() & _y.lat.notna()]
    kdet = pd.DataFrame({"date": pd.to_datetime(_y.date.astype(str).str[:10], errors="coerce"), "place": _y.place.fillna("").astype(str),
                         "cause": _y.cause, "ha": pd.to_numeric(_y.area_ha, errors="coerce").fillna(0)})
    _yx = _y[["lon", "lat"]].to_numpy()
    _r = locate(_yx, adm2); _r[_r < 0] = nearest(_yx[_r < 0], adm2, NEAREST_MAX)
    kdet["region"] = _r
    print(f"{DETECT_NAME}: 산불 {len(kdet):,}건 ({kdet.date.min():%Y-%m} ~ {kdet.date.max():%Y-%m}), 하위 구역 배정 {(kdet.region >= 0).mean():.1%}")
elif HAS_KFS:
    kdet = kfs
''')
py(r'''
if HAS_KFS:
    kfs["y"] = kfs.date.dt.year
    vy = list(range(2012, YEARS[1] + 1))
    kfs_year = kfs.groupby("y").agg(공식_건수=("ha", "size"), 공식_면적_ha=("ha", "sum")).reindex(vy, fill_value=0)
    kfs_year["화재 칸 (하모니제이션)"] = H.groupby(yr(H)).sum().reindex(vy).round(0)
    kfs_year["큰 묶음 (NOAA-20)"] = events[events.cells >= BIG_EVENT].groupby(events.start.dt.year).size().reindex(vy)
    km_ = [p for p in months if vy[0] <= p.year <= vy[-1]]
    kfs_mon = kfs.groupby(kfs.date.dt.to_period("M")).agg(n=("ha", "size"), ha=("ha", "sum")).reindex(km_, fill_value=0)
    kfs_corr = {"annual_vs_count": round(spearmanr(kfs_year["화재 칸 (하모니제이션)"], kfs_year.공식_건수)[0], 2),
                "annual_vs_area": round(spearmanr(kfs_year["화재 칸 (하모니제이션)"], kfs_year.공식_면적_ha)[0], 2),
                "monthly_vs_count": round(spearmanr(H.reindex(km_), kfs_mon.n)[0], 2),
                "monthly_vs_area": round(spearmanr(H.reindex(km_), kfs_mon.ha)[0], 2), "years": [vy[0], vy[-1]]}
    print("순위 상관 (화재 칸 vs 공식):", kfs_corr)
    display(kfs_year)

    # 크기별 감지율: 공식 산불 지역에서 그날~2일 뒤 NOAA-20 감지가 있었나 / 30일 전·후로 같은 계산(우연)
    n20cd = n20_r[n20_r.region >= 0].assign(d=n20_r.acq_date.dt.normalize())
    det = set(zip(n20cd.region, n20cd.d))
    hit = lambda r, s=0: any((r.region, r.date + pd.Timedelta(days=d + s)) in det for d in range(3))
    k2 = kdet[(kdet.region >= 0) & (kdet.date >= N20_START.start_time) & (kdet.date <= n20.acq_date.max())].copy()
    k2["hit"] = k2.apply(hit, axis=1)
    k2["chance"] = k2.apply(lambda r: (hit(r, -30) + hit(r, 30)) / 2, axis=1)
    k2["size"] = pd.cut(k2.ha, [-1, 0.1, 1, 10, 100, 1e9], labels=["0.1 ha 미만", "0.1~1", "1~10", "10~100", "100 ha 이상"])
    kfs_detect = k2.groupby("size", observed=False).agg(건수=("hit", "size"), 감지율=("hit", "mean"), 우연=("chance", "mean")).round(2)
    print("크기별 감지율 (NOAA-20, 2018-04~)"); display(kfs_detect)

    # 큰 산불: 면적 vs 화재 칸 (그날~10일, 같은 시·군·구)
    n20c = n20cd.assign(cell=key(n20cd, GRID)).drop_duplicates(["region", "cell", "d"])
    kbig = kdet[(kdet.ha >= 100) & (kdet.region >= 0) & (kdet.date >= N20_START.start_time)].copy()
    kbig["화재 칸"] = [int(((n20c.region == g) & n20c.d.between(t, t + pd.Timedelta(days=10))).sum()) for g, t in zip(kbig.region, kbig.date)]
    kbig = kbig.sort_values("ha", ascending=False).drop_duplicates(["region", "date"])
    kfs_big_rho = round(spearmanr(kbig.ha, kbig["화재 칸"])[0], 2)
    print(f"100 ha 이상 산불 {len(kbig)}건: 면적 vs 화재 칸 순위 상관 {kfs_big_rho}, 위성 감지 없음 {(kbig['화재 칸'] == 0).sum()}건")

    # 공식 기록 없는 큰 묶음
    kd = set(zip(kfs.region, kfs.date.dt.normalize()))
    def has_record(r):
        regs = r.regions if isinstance(r.regions, list) else []
        return any((g, r.start + pd.Timedelta(days=d)) in kd for g in regs for d in range(-3, (r.end - r.start).days + 2))
    bigev = events[events.cells >= BIG_EVENT].copy(); bigev["공식 기록"] = bigev.apply(has_record, axis=1)
    no_rec = bigev[~bigev["공식 기록"]].assign(지역=lambda d: d.regions.map(lambda r: ", ".join(lab(x) for x in r[:3])))
    print(f"큰 묶음 {len(bigev)}개 중 공식 산불 기록과 맞는 것 {int(bigev['공식 기록'].sum())}개. 기록 없는 큰 묶음:")
    display(no_rec[["start", "end", "cells", "peak", "지역"]])
    if COUNTRY == "KOR":
        jeju_i = lab_idx["제주 Jeju-si"]
        print(f"제주: 공식 산불 {int((kfs.place.str.startswith('제주')).sum())}건 vs 제주시 위성 화재 칸 {int(RVN.loc[jeju_i, v_cols].sum())} (2012~2025) → 위성은 산불 통계 밖의 소각도 잡음")
''')
md(r'''
**읽는 법:**
- **크기별 감지율**이 핵심입니다. 100 ha 이상 산불은 위성이 대부분 잡고, 1 ha 미만은 거의 못 잡습니다. 즉 이 도구가 보여 주는 것은 "위성으로 보일 만큼 큰 불"의 활동이고, 작은 산불의 건수를 대신하지는 못합니다. 화면에 이 한계를 그대로 적습니다.
- **연·월 상관**이 1이 아닌 이유는 두 자료가 다른 불을 세기 때문입니다. 위성은 농경지 소각을 잡고(제주가 대표적), 산불 통계는 위성이 못 보는 작은 산불을 셉니다.
- **기록 없는 큰 묶음**이 연천·고성처럼 DMZ에 맞닿은 지역에 몰려 있다면, 산불 통계에 들어가지 않는 군사 지역 내 불일 가능성이 큽니다.
''')
md(r'''
### ⑰-2 2001년부터: 시·도별 연간 산불 통계 (KOSIS)

개별 기록은 2011년부터라, 2001~2010년은 국가통계포털(KOSIS)의 **시·도별 연간 산불 건수·면적**(산림청, 2001~)으로 확인합니다.

가장 중요한 시험은 **독립 단절 검정**입니다. 공식 산불 건수는 위성 교체와 무관하므로, "위성 값 ÷ 공식 건수" 비율이 2012년에 갑자기 바뀐다면 그것은 위성 교체 때문입니다. 보정 전(원값 이어 붙이기)과 보정 후를 같은 시험에 넣습니다.
''')
py(r'''
import csv
HAS_KOSIS = KOSIS_FILE is not None and KOSIS_FILE.exists()
HAS_ANNUAL = ANNUAL_COUNTS is not None and ANNUAL_COUNTS.exists()
if HAS_KOSIS:
    rows_k = list(csv.reader(open(KOSIS_FILE, encoding="utf-8-sig")))
    PK = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
          "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북",
          "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
          "제주특별자치도": "제주", "계": "전국"}
    rec = [(PK[r[0]], int(rows_k[0][j]), "n" if rows_k[2][j].startswith("건수") else "ha", 0.0 if r[j] in ("-", "") else float(r[j]))
           for r in rows_k[3:] if r and r[0] in PK for j in range(1, len(r)) if rows_k[1][j] == "금년"]
    kos = pd.DataFrame(rec, columns=["prov", "y", "m", "v"]).pivot_table(index=["prov", "y"], columns="m", values="v").reset_index()
    KY = list(range(max(YEARS[0], int(kos.y.min())), YEARS[1] + 1))
    kn = kos[kos.prov == "전국"].set_index("y").reindex(KY)
    kt = pd.DataFrame({"공식 건수": kn.n, "공식 면적 ha": kn.ha,
                       "화재 칸 (보정)": H.groupby(yr(H)).sum().reindex(KY), "원값 이어 붙이기": naive.groupby(yr(naive)).sum().reindex(KY)})
    display(kt.round(0))

    kos_break = {}
    for c in ["화재 칸 (보정)", "원값 이어 붙이기"]:
        r = kt[c] / kt["공식 건수"]
        i, p = pettitt(r.values)
        kos_break[c] = {"ratio_before_2012": round(r.loc[:2011].mean(), 2), "ratio_after_2012": round(r.loc[2012:].mean(), 2),
                        "after_over_before": round(r.loc[2012:].mean() / r.loc[:2011].mean(), 2), "pettitt_p": round(p, 4), "change_year": KY[i]}
    print("독립 단절 검정 (위성 ÷ 공식 건수):"); display(pd.DataFrame(kos_break).T)

    rho = lambda a, b: round(spearmanr(a, b)[0], 2)
    kos_corr = {f"{a}~{b}": {"vs_count": rho(kt.loc[a:b, "화재 칸 (보정)"], kt.loc[a:b, "공식 건수"]),
                             "vs_area": rho(kt.loc[a:b, "화재 칸 (보정)"], kt.loc[a:b, "공식 면적 ha"])}
                for a, b in [(KY[0], 2011), (2012, KY[-1]), (KY[0], KY[-1])]}
    PHy = PH.T.groupby([p.year for p in months]).sum().T
    kp = kos[(kos.prov != "전국") & (kos.prov != "제주")].merge(
        PHy.stack().rename("sat").reset_index().rename(columns={"level_0": "prov", "level_1": "y"}), on=["prov", "y"])
    for a, b in [(KY[0], 2011), (2012, KY[-1])]:
        s = kp[kp.y.between(a, b)]
        kos_corr[f"{a}~{b}"]["province_year_vs_count"] = rho(s.sat, s.n)
        kos_corr[f"{a}~{b}"]["province_year_vs_area"] = rho(s.sat, s.ha)
    print("순위 상관 (전국 연도별, 시·도×연도; 제주 제외):"); display(pd.DataFrame(kos_corr).T)
elif HAS_EXT or HAS_ANNUAL:   # 연(시즌) 합계로 같은 독립 단절 검정. 연별 공식 건수 파일이 있으면 그것을, 없으면 개별 기록을 합산
    # 시즌 연도: SEASON_START=7이면 2012 = 2012-07 ~ 2013-06. 시즌은 2011-07~2012-06이 위성 교체(2012-02)에 걸치므로 앞뒤 비교에서 뺌
    sy = lambda s: s.index.year - (s.index.month < SEASON_START)
    B0, B1 = (2011, 2012) if SEASON_START == 1 else (2010, 2012)
    if HAS_ANNUAL:
        _a = pd.read_csv(ANNUAL_COUNTS)
        _a["y"] = _a["season_start_year"] if "season_start_year" in _a else (_a["season"].str[:4].astype(int) if "season" in _a else _a["year"])
        _last = YEARS[1] if SEASON_START == 1 else YEARS[1] - 1   # 마지막 완전한 시즌
        KY = list(range(max(YEARS[0], int(_a.y.min())), min(_last, int(_a.y.max())) + 1))
        _ky = _a.groupby("y").agg(n=("n_fires", "sum"), ha=("area_ha", "sum")).reindex(KY)
        ANNUAL_SRC = ANNUAL_NAME
    else:
        _ksy = kfs.date.dt.year - (kfs.date.dt.month < SEASON_START)   # 위성과 같은 연(시즌) 단위
        _klast = int(_ksy.max()) if SEASON_START == 1 else int(_ksy[kfs.date.dt.month == SEASON_START - 1].max())   # 기록이 끝난 해(시즌) 뒤는 0건이 아니라 자료 없음
        KY = list(range(max(YEARS[0], int(_ksy.min())), min(YEARS[1] if SEASON_START == 1 else YEARS[1] - 1, _klast) + 1))
        _ky = kfs.groupby(_ksy).agg(n=("ha", "size"), ha=("ha", "sum")).reindex(KY, fill_value=0)
        ANNUAL_SRC = EXT_NAME
    kt = pd.DataFrame({"공식 건수": _ky.n, "공식 면적 ha": _ky.ha,
                       "화재 칸 (보정)": H.groupby(sy(H)).sum().reindex(KY), "원값 이어 붙이기": naive.groupby(sy(naive)).sum().reindex(KY)})
    print("집계 단위:", "연도" if SEASON_START == 1 else f"시즌 ({SEASON_START}월 시작, 표의 연도 = 시작 연도)", "| 공식 자료:", ANNUAL_SRC)
    display(kt.round(0))
    kos_break = {}
    for c in ["화재 칸 (보정)", "원값 이어 붙이기"]:
        for base in ["공식 건수", "공식 면적 ha"]:
            r = kt[c] / kt[base]
            i, p = pettitt(r.values)
            kos_break[f"{c} / {base}"] = {"ratio_before_2012": round(r.loc[:B0].mean(), 4), "ratio_after_2012": round(r.loc[B1:].mean(), 4),
                                          "after_over_before": round(r.loc[B1:].mean() / r.loc[:B0].mean(), 2), "pettitt_p": round(p, 4), "change_year": KY[i]}
    print("독립 단절 검정 (위성 ÷ 공식):"); display(pd.DataFrame(kos_break).T)
    rho = lambda a, b: round(spearmanr(a, b)[0], 2)
    kos_corr = {f"{a}~{b}": {"vs_count": rho(kt.loc[a:b, "화재 칸 (보정)"], kt.loc[a:b, "공식 건수"]),
                             "vs_area": rho(kt.loc[a:b, "화재 칸 (보정)"], kt.loc[a:b, "공식 면적 ha"])}
                for a, b in [(KY[0], B0), (B1, KY[-1]), (KY[0], KY[-1])]}
    print("순위 상관 (연도별):"); display(pd.DataFrame(kos_corr).T)
else:
    print("KOSIS 파일이 없어 ⑰-2를 건너뜁니다:", KOSIS_FILE)
''')
md(r'''
**읽는 법:** 보정 전에는 "위성 ÷ 공식 건수"가 2012년에 약 2.7배로 뛰고(변화점이 정확히 2012년), 보정 후에는 2012년 전후가 거의 같습니다. 위성끼리 비교한 ⑦의 단절 검정과 달리 **위성과 무관한 자료로 확인한 결과**라, 하모니제이션이 실제 화재 기록과 맞게 이어졌다는 가장 직접적인 근거입니다. 시·도×연도 상관은 2012년 이전이 조금 낮은데, MODIS가 VIIRS보다 작은 불을 덜 잡아 시·도 단위 값이 더 흔들리기 때문입니다.
''')
py(r'''
if HAS_KFS:
    meta = json.loads((OUT_DIR / "meta.json").read_text(encoding="utf-8"))
    meta["external_validation"] = {
        "source": EXT_NAME if HAS_EXT else "산림청 산불 통계 (발생일, 장소, 원인, 피해 면적)", "records": int(len(kfs)),
        "period": [f"{kfs.date.min():%Y-%m-%d}", f"{kfs.date.max():%Y-%m-%d}"], "district_match_rate": round(float((kfs.region >= 0).mean()), 3),
        "rank_correlation": kfs_corr,
        "detection_source": DETECT_NAME if HAS_DET else None, "detection_period": [f"{k2.date.min():%Y-%m-%d}", f"{k2.date.max():%Y-%m-%d}"],
        "detection_by_size": {str(k): {"n": int(r["건수"]), "detected": float(r["감지율"]), "chance": float(r["우연"])} for k, r in kfs_detect.iterrows()},
        "big_fires_area_vs_cells_rho": kfs_big_rho,
        "big_clusters_without_record": [{"start": f"{r.start:%Y-%m-%d}", "end": f"{r.end:%Y-%m-%d}", "cells": int(r.cells), "regions": r["지역"]}
                                        for _, r in no_rec.iterrows()],
        "note": "위성은 농경지 소각 등 산불 통계 밖의 불도 잡고, 1 ha 미만 산불은 대부분 못 잡는다.",
    }
    if HAS_EXT or HAS_ANNUAL:
        meta["external_validation"]["annual_records"] = {"source": ANNUAL_SRC, "years": [KY[0], KY[-1]], "season_start_month": SEASON_START,
                                                        "independent_break_test": kos_break, "rank_correlation": kos_corr,
                                                        **({"note": VALIDATION_NOTE} if VALIDATION_NOTE else {})}
    if HAS_KOSIS:
        meta["external_validation"]["kosis_annual"] = {"source": "KOSIS 시도별 산불발생 현황 (산림청)", "years": [KY[0], KY[-1]],
                                                      "independent_break_test": kos_break, "rank_correlation": kos_corr}
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("meta.json에 external_validation 저장")
''')

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
nbf.write(nb, sys.argv[1] if len(sys.argv) > 1 else "burnline_harmonization.ipynb")