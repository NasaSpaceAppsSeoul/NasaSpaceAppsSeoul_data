"""노트북을 만들고 실행해 output/<지역>/ 결과를 만듭니다. 맥·윈도우·리눅스 같은 명령.

사용 (저장소 루트에서):
    python tools/run_all.py              여섯 지역 모두
    python tools/run_all.py GRC CHL      고른 지역만
    python tools/run_all.py --check      실행 후 expected/<지역>/meta.json과 비교

원자료는 기본으로 inputs/ 에서 찾습니다 (다른 곳이면 환경 변수 BURNLINE_DATA).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
ALL = ["KOR", "CAL", "BC", "GRC", "CHL", "NSW"]


def notebook_name(c):
    return "burnline_harmonization.ipynb" if c == "KOR" else f"burnline_harmonization_{c}.ipynb"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    regions = [a.upper() for a in args] or ALL
    bad = [c for c in regions if c not in ALL]
    if bad:
        sys.exit(f"모르는 지역: {bad} (가능: {ALL})")
    data = Path(os.environ.get("BURNLINE_DATA", ROOT / "inputs"))
    if not (data / "firms").is_dir():
        sys.exit(f"원자료 폴더가 없습니다: {data / 'firms'}  (README의 '원자료 받기'를 보세요)")
    os.chdir(ROOT)                                  # 노트북은 저장소 루트 기준 상대 경로를 씀
    os.environ["BURNLINE_DATA"] = str(data)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYDEVD_DISABLE_FILE_VALIDATION", "1")   # 커널 시작 때 디버거 경고 끄기
    failed = []
    for c in regions:
        nb_path = ROOT / notebook_name(c)
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_notebook.py"), str(nb_path)], check=True)
        os.environ["BURNLINE_COUNTRY"] = c          # 커널은 이 환경 변수를 물려받음
        nb = nbformat.read(nb_path, as_version=4)
        t0 = time.time()
        print(f"[{c}] 실행 중 ...", flush=True)
        try:
            NotebookClient(nb, timeout=None, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
            print(f"[{c}] 끝 ({time.time() - t0:.0f}초) → output/{c}/", flush=True)
        except Exception as e:                      # 실패해도 어디까지 돌았는지 보이게 노트북은 저장
            print(f"[{c}] 실패: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}", flush=True)
            failed.append(c)
        nbformat.write(nb, nb_path)
    if check:
        subprocess.run([sys.executable, str(ROOT / "tools" / "check_expected.py"), *[c for c in regions if c not in failed]])
    if failed:
        sys.exit(f"실패한 지역: {failed} (노트북을 열어 오류 셀을 확인)")


if __name__ == "__main__":
    main()
