"""OpenAPI 스키마를 파일로 덤프.

    ./venv/bin/python scripts/dump_openapi.py        # backend/openapi.json 갱신

서버를 띄우지 않고 앱의 OpenAPI 스펙을 뽑는다. 프론트가 이 파일로 타입 생성·목킹을
할 수 있다. (서버가 떠 있으면 /openapi.json·/docs로도 같은 스펙을 받는다.)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from barum.api.app import app  # noqa: E402

OUT = ROOT / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n_paths = len(spec.get("paths", {}))
    n_schemas = len(spec.get("components", {}).get("schemas", {}))
    print(f"저장: {OUT}  (paths {n_paths}, schemas {n_schemas})")


if __name__ == "__main__":
    main()
