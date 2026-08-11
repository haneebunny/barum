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

    uvicorn.run(
        "barum.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        timeout_keep_alive=args.timeout_keep_alive,
    )


if __name__ == "__main__":
    main()
