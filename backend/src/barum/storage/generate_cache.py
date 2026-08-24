"""`/generate` 응답 캐시. 같은 입력이면 다시 안 만든다.

왜 필요한가. 상세페이지 생성은 이미지를 켜면 **요청당 약 125초**다(2026-08-23 실측,
이미지 끄면 66초). 시연을 준비하며 같은 입력으로 여러 번 돌리는 동안 매번 그 시간과
과금을 다시 쓸 이유가 없다.

**메모리 캐시만 둔다.** `/check`처럼 Supabase 2차 캐시를 두지 않는 이유는, 그쪽은
이미지 sha256이라는 자연 키가 있는데 `/generate`는 그런 게 없어서다. 프로세스가
재시작하면 비는데, 이건 오히려 안전한 쪽이다 — 코드가 바뀌면 캐시도 같이 비워진다.
"""

import json
import os
from collections import OrderedDict
from pathlib import Path

from ..models import GenerateRequest, GenerateResponse
from .checks_store import sha256_hex

# 응답 한 건이 카드 6장 + 이미지 URL이라 작지 않다. 시연용이라 이 정도면 충분하다.
_MAX_ENTRIES = 32
_CACHE: OrderedDict[str, GenerateResponse] = OrderedDict()
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "generate_cache.json"

# **출력을 바꾸는 서버 스위치.** 키에 같이 넣는다.
_OUTPUT_AFFECTING_ENV = (
    "IMAGE_GENERATION_ENABLED",
    "JUDGE_KIND",
    "JUDGE_MODEL",
    "GENERATE_MODEL",
    "IMAGE_MODEL",
    "BARUM_VERIFY_GATE",
    "BARUM_REWRITE_GROUNDING",
    "BARUM_GROUNDING_CHECKLIST",
)


def cache_enabled() -> bool:
    """캐시 스위치. 기본 켜짐, `GENERATE_CACHE_ENABLED=0`이면 끈다."""
    return os.environ.get("GENERATE_CACHE_ENABLED", "1") != "0"


def _env_fingerprint() -> str:
    return ";".join(f"{k}={os.environ.get(k, '')}" for k in _OUTPUT_AFFECTING_ENV)


def build_generate_cache_key(req: GenerateRequest) -> str:
    """요청 전체를 해시해 캐시 키를 만든다."""
    raw = f"{req.model_dump_json()}|{_env_fingerprint()}"
    return sha256_hex(raw.encode("utf-8"))


def _load_disk_cache() -> None:
    if not _CACHE_FILE.exists():
        return
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        for k, v in data.items():
            if k not in _CACHE:
                _CACHE[k] = GenerateResponse.model_validate(v)
    except Exception as e:
        print(f"    [warn] 디스크 캐시 로드 실패: {e}")


def _save_disk_cache() -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        dump = {k: v.model_dump(mode="json") for k, v in _CACHE.items()}
        _CACHE_FILE.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"    [warn] 디스크 캐시 저장 실패: {e}")


def get_cached_generate(key: str) -> GenerateResponse | None:
    """캐시된 응답. 없으면 None."""
    if not cache_enabled():
        return None
    if not _CACHE:
        _load_disk_cache()
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)  # 최근 쓴 것을 뒤로(LRU)
    return hit


def put_cached_generate(key: str, resp: GenerateResponse) -> None:
    """응답을 캐시에 넣는다. 상한을 넘으면 가장 오래된 것부터 버린다."""
    if not cache_enabled():
        return
    _CACHE[key] = resp
    _CACHE.move_to_end(key)
    while len(_CACHE) > _MAX_ENTRIES:
        _CACHE.popitem(last=False)
    _save_disk_cache()


def clear_generate_cache() -> None:
    """테스트·수동 초기화용."""
    _CACHE.clear()
    if _CACHE_FILE.exists():
        try:
            _CACHE_FILE.unlink()
        except Exception:
            pass
