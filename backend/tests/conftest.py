"""테스트 공통 설정.

**`/generate` 응답 캐시를 테스트마다 격리한다.** 안 하면 두 가지가 같이 깨진다.

1. *테스트가 개발자 캐시를 지운다.* `clear_generate_cache()`가 `_CACHE_FILE.unlink()`
   를 하는데, 경로가 실제 `backend/.cache/generate_cache.json`이면 돈 주고 만들어둔
   생성 결과가 날아간다(2026-08-24에 실제로 날렸다. 같은 입력을 다시 넣으면
   이미지가 재생성돼 과금된다).
2. *캐시가 테스트 결과를 뒤바꾼다.* `/generate`를 부르는 테스트가 앞선 실행이 남긴
   응답을 그대로 받아서, 가짜 생성기가 호출되지 않는다. 그래서 "캐시를 켜면 A·B가
   깨지고 끄면 C·D가 깨지는" 재현 안 되는 실패가 났다(2026-08-24 실측).

경로를 임시 폴더로 돌리고 매 테스트 전후로 비운다. 테스트는 자기 캐시만 본다.
"""

import pytest

import barum.storage.generate_cache as generate_cache


@pytest.fixture(autouse=True)
def _isolated_generate_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "generate_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(generate_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(generate_cache, "_CACHE_FILE", cache_dir / "generate_cache.json")
    generate_cache._CACHE.clear()
    yield
    generate_cache._CACHE.clear()
