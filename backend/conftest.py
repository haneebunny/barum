"""pytest import 경로 설정.

이 저장소는 얕은 패키지(`src/barum/`)와 top-level 스크립트(`tile_split.py` 등)를
섞어 쓴다. 실행 진입점은 각자 sys.path를 넣지만, pytest는 공통으로 여기서 잡아
`barum` 패키지와 top-level 모듈을 모두 import 가능하게 한다.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)
