"""판정 백엔드 서버 실행.

    ./venv/bin/python scripts/run_api.py               # 0.0.0.0:8000, reload
    ./venv/bin/python scripts/run_api.py --port 9000
    ./venv/bin/python scripts/run_api.py --no-reload

top-level 모듈(tile_split)과 barum 패키지를 둘 다 import하므로 backend 루트와
src를 경로에 넣는다. reload는 서브프로세스를 새로 띄우므로 sys.path만으론 부족해
PYTHONPATH env로도 넣어 자식 프로세스가 상속하게 한다.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_paths = [str(ROOT), str(ROOT / "src")]
for _sp in _paths:
    if _sp not in sys.path:
        sys.path.insert(0, _sp)
os.environ["PYTHONPATH"] = os.pathsep.join(
    _paths + [os.environ.get("PYTHONPATH", "")]
).rstrip(os.pathsep)

import uvicorn  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="barum 판정 백엔드 서버")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True)
    # 동기 판정(OCR)이 수십 초 걸릴 수 있어 keep-alive를 넉넉히 잡는다.
    ap.add_argument("--timeout-keep-alive", type=int, default=120)
    args = ap.parse_args()

    # **레퍼런스 팩도 감시 대상에 넣는다.** 팩은 `backend/` 밖(저장소 루트
    # `reference/`)에 있어서 기본 감시 범위(작업 디렉터리)에 안 걸린다. 그런데 팩을
    # 읽는 함수들은 전부 lru_cache라, 팩을 고쳐도 서버는 **옛 규정으로 계속 판정한다.**
    # 조용히, 무기한으로. 판정 근거가 바뀌는 것이라 응답이 낡는 것보다 훨씬 나쁘다
    # (2026-08-23 발견).
    reload_dirs = [str(ROOT)]
    pack_dir = ROOT.parent / "reference"
    if pack_dir.exists():
        reload_dirs.append(str(pack_dir))

    uvicorn.run(
        "barum.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=reload_dirs if args.reload else None,
        timeout_keep_alive=args.timeout_keep_alive,
    )


if __name__ == "__main__":
    main()
