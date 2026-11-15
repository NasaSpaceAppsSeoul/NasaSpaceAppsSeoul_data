# Burnline · FIRMS 화재 달력 파이프라인

NASA Space Apps Challenge 2026. MODIS와 VIIRS 핫스팟을 NOAA-20 단위의 25년 시계열 하나로 이어, 여섯 지역(KOR, CAL, BC, GRC, CHL, NSW)의 화재 활동 달력을 만듭니다. 결과(`output/<지역>/`)는 백엔드 데이터 패키지로 들어갑니다.

경로와 인코딩은 모두 고정되어 있습니다. 저장소를 받고 원자료를 `inputs/`에 풀면 맥·윈도우·리눅스에서 같은 명령으로 돌아가고, 고칠 곳은 없습니다.

## 1. 준비 (처음 한 번)

Python 3.12를 권합니다(`expected/`가 이 버전으로 만든 결과입니다).

**맥·리눅스**

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**윈도우 (PowerShell)**

```powershell
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

## 2. 원자료 받기

원자료(zip 205 MB, 풀면 약 950 MB)는 용량 때문에 저장소에 넣지 않고 GitHub Release에 올려 두었습니다. Release의 `burnline_inputs.zip`을 받아 **저장소 루트에서** 풀면 `inputs/` 폴더가 생깁니다.

```
inputs/
  firms/<지역>/modis/    MODIS C6.1      fire_archive_*.csv, fire_nrt_*.csv
  firms/<지역>/snpp/     VIIRS S-NPP     〃
  firms/<지역>/noaa20/   VIIRS NOAA-20   〃
  firms/<지역>/noaa21/   VIIRS NOAA-21   〃
  official/<지역>/       공식 산불 기록 (외부 검증용)
```

폴더 이름은 노트북이 그대로 찾으므로 바꾸지 않습니다. 원자료를 다른 곳에 두려면 환경 변수 `BURNLINE_DATA`에 그 폴더를 지정합니다(안의 구조는 같아야 함).

윈도우에서는 탐색기의 "압축 풀기"나 7-Zip으로 풀면 됩니다(한글 파일 이름은 UTF-8). 경로가 너무 길지 않게 `C:\burnline\`처럼 짧은 곳에 저장소를 두는 것을 권합니다.

## 3. 실행

저장소 루트에서, 맥·윈도우 같은 명령입니다(맥·리눅스는 `python` 대신 `python3`도 됨).

```bash
python tools/run_all.py --check
```

- 지역마다 `tools/make_notebook.py`로 노트북을 만들고 실행해 `output/<지역>/`를 씁니다.
- 지역만 고르려면 `python tools/run_all.py GRC CHL`.
- 여섯 지역 합쳐 20~30분쯤 걸립니다(NSW·BC·CAL이 가장 김).
- `--check`는 끝난 뒤 `output/<지역>/meta.json`을 `expected/<지역>/meta.json`과 비교합니다. 날짜(`generated`) 외에는 모두 `같음`이 나와야 합니다.
- 실행된 노트북(`burnline_harmonization*.ipynb`)은 루트에 남아 그래프와 중간 표를 볼 수 있습니다. 노트북은 만들어지는 파일이라 커밋하지 않습니다.

## 4. 고칠 때

| 고칠 것 | 방법 |
|---|---|
| 계산 방법 | `tools/make_notebook.py`를 고치고 `run_all.py`를 다시 돌림. 노트북을 직접 고치면 다음 실행 때 덮어써짐 |
| 지역 설정 (기간, 경계 처리, 예시 달 등) | `tools/make_notebook.py`의 `CONFIGS` |
| 화면용 이름 | `tools/transliterate.py`(음역 사전)를 고치고 `python tools/build_names.py` → `boundaries/<지역>/names-<지역>.csv`, ADM1 `name_ko`·`name_en` |
| FIRMS 자료 새로 받기 | FIRMS Archive Download에서 같은 범위로 받은 zip을 `inputs/firms/<지역>/<센서>/`에 풀어 덮어씀 |
| 공식 기록 다시 만들기 | `tools/data_prep/` (아래) |

결과가 바뀌는 수정이면 `expected/<지역>/meta.json`도 새 결과로 바꿔서 같이 커밋합니다.

```bash
python tools/check_expected.py
```

## 폴더 구성

| 경로 | 내용 |
|---|---|
| `tools/make_notebook.py` | 노트북 생성기 (계산 전체가 여기 있음) |
| `tools/run_all.py` | 노트북 생성 + 실행 + 결과 비교 |
| `tools/check_expected.py` | `output/`과 `expected/` 비교 |
| `tools/build_names.py`, `tools/transliterate.py` | 화면용 한국어·영어 이름 |
| `tools/data_prep/` | 공식 기록 CSV를 원본에서 만드는 스크립트 (다시 돌리는 데는 필요 없음) |
| `tools/site_extract.py`, `tools/mockup_extract.py` | 샘플 사이트(`mockup/site/`)용 데이터 추출 |
| `boundaries/<지역>/` | 행정 경계 (ADM1 상위, ADM2 하위, ADM2_simplified 지도용), `names-<지역>.csv` |
| `expected/<지역>/meta.json` | 기준 결과 |
| `method_page.html` | 방법론 페이지 |
| `문서/` | 분석 보고서, 지표 기획안, 처리 단계 PDF |
| `mockup/` | 샘플 사이트와 상세페이지 시안 |

## 결과 파일 (`output/<지역>/`)

| 파일 | 내용 |
|---|---|
| `calendar.json` | 나라 전체 연·월 달력 (NOAA-20 단위 25년): 평년 대비 배수, 순위, FRP, 2×2 유형, 품질, `raw_before` |
| `climatology.json` | 나라 전체 월별 평년 범위 (중앙값, 사분위, 최소, 최대) |
| `calendar_by_province.json` | 상위 단위별 달력 |
| `calendar_by_region.json` | 하위 구역별 달력 (`viirs` 블록은 2012~, NOAA-20 단위) |
| `regions.geojson` | 하위 구역 경계 + 충분도, 위험 시기, 대체 지역, 이웃, 이름 |
| `events.json`, `events_by_region.json` | 화재 묶음 |
| `meta.json` | 보정 계수, 검증 오차, 경고 규칙, 외부 검증 (방법론 페이지용) |
| `hotspots_clean.csv` | 정제된 핫스팟 (CSV 다운로드용) |

## 공식 기록 (`inputs/official/<지역>/`)

| 지역 | 파일 | 출처 |
|---|---|---|
| KOR | `산불통계.xlsx`, `시도별_산불발생_현황_*.csv` | 산림청 산불 통계, KOSIS |
| CAL | `cal_fire_perimeters_2001_2025.csv` | CAL FIRE FRAP California Fire Perimeters |
| BC | `bc_fire_incidents_2001_2025.csv` | BC Wildfire Service (BC Data Catalogue `PROT_HISTORICAL_INCIDENTS_SP`) |
| GRC | `grc_fire_service_2000_2024.csv` | 그리스 소방청 연도별 기록 → `tools/data_prep/build_grc.py` |
| CHL | `chl_conaf_*.csv` 4개 | CONAF 통계 → `tools/data_prep/build_chl.py`, `build_chl_perfire.py` |
| NSW | `nsw_npws_wildfires_2000_2026.csv` | NSW NPWS Fire History → `tools/data_prep/build_nsw.py` |

`tools/data_prep/`의 스크립트는 첫 인자로 원본 다운로드 폴더를 받아 `inputs/official/<지역>/`에 씁니다(NSW는 서버에서 직접 받음). 그리스 원본 xlsx 묶음은 Release의 `greece_fire_service_2000-2024.zip`입니다.

## 알아 둘 점

- 남반구(CHL, NSW)는 공식 기록을 7월~다음 해 6월 시즌 단위로 비교합니다(`SEASON_START=7`). 월별 계산은 다른 지역과 같습니다.
- 그래프의 한글 글꼴은 AppleGothic, Malgun Gothic, NanumGothic, Noto Sans CJK KR 중 있는 것을 씁니다. 없으면 그래프 글자만 네모로 나오고 숫자 결과에는 영향이 없습니다.
- 줄 끝은 `.gitattributes`로 LF 고정입니다. 윈도우에서 커밋해도 CRLF가 섞이지 않습니다.

## 출처

- NASA FIRMS: MODIS Collection 6.1 (MCD14), VIIRS S-NPP (VNP14IMG), NOAA-20 (VJ114IMG), NOAA-21 (VJ214IMG) 375 m
- geoBoundaries ADM1/ADM2 (CC BY 3.0), BC Data Catalogue regional districts (Open Government Licence – BC)
- 공식 기록은 위 표의 각 기관
