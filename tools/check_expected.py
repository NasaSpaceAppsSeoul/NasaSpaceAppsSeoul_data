"""다시 돌린 output/<지역>/meta.json을 expected/<지역>/meta.json과 비교합니다 (generated 날짜는 뺌).

사용: python tools/check_expected.py          (여섯 지역 모두)
      python tools/check_expected.py GRC CHL  (고른 지역만)
"""
import json
import sys
from pathlib import Path

regions = sys.argv[1:] or ["KOR", "CAL", "BC", "GRC", "CHL", "NSW"]
for c in regions:
    out, exp = Path("output") / c / "meta.json", Path("expected") / c / "meta.json"
    if not out.exists():
        print(f"{c}: output/{c}/meta.json 없음 (아직 안 돌림)")
        continue
    a = json.loads(out.read_text(encoding="utf-8"))
    b = json.loads(exp.read_text(encoding="utf-8"))
    for d in (a, b):
        d.pop("generated", None)
    same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)   # 문자열로 비교 (NaN끼리도 같게)
    print(f"{c}: {'같음' if same else '다름'}")
