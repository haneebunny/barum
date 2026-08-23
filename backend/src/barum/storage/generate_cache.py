"""`/generate` 응답 캐시. 같은 입력이면 다시 안 만든다.

왜 필요한가. 상세페이지 생성은 이미지를 켜면 **요청당 약 125초**다(2026-08-23 실측,
이미지 끄면 66초). 시연을 준비하며 같은 입력으로 여러 번 돌리는 동안 매번 그 시간과
과금을 다시 쓸 이유가 없다.

**메모리 캐시만 둔다.** `/check`처럼 Supabase 2차 캐시를 두지 않는 이유는, 그쪽은
이미지 sha256이라는 자연 키가 있는데 `/generate`는 그런 게 없어서다. 프로세스가
재시작하면 비는데, 이건 오히려 안전한 쪽이다 — 코드가 바뀌면 캐시도 같이 비워진다.
"""

import os
from collections import OrderedDict

from ..models import GenerateRequest, GenerateResponse
from .checks_store import sha256_hex

# 응답 한 건이 카드 6장 + 이미지 URL이라 작지 않다. 시연용이라 이 정도면 충분하다.
_MAX_ENTRIES = 32
_CACHE: OrderedDict[str, GenerateResponse] = OrderedDict()

# **출력을 바꾸는 서버 스위치.** 키에 같이 넣는다.
#
# 이게 없으면 팀장이 `IMAGE_GENERATION_ENABLED`를 켠 직후 **이미지 없는 옛 응답이
# 캐시에서 그대로 나온다.** 그러면 "플래그를 켰는데 이미지가 안 나온다"로 읽혀
# 원인을 엉뚱한 데서 찾게 된다. 오늘 낡은 서버 프로세스로 같은 종류의 혼선이
# 실제로 있었다(2026-08-23).
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
    """요청 전체를 해시해 캐시 키를 만든다.

    **필드를 골라 담지 않는다.** 고르면 새 필드가 생길 때마다 키에 넣는 걸 잊고,
    그러면 서로 다른 요청이 같은 응답을 받는다. 조용히 틀리는 종류의 버그라
    실행해도 안 보인다. 요청 전체를 담으면 그 실수가 구조적으로 불가능해진다.

    출력을 바꾸는 서버 스위치도 같이 담는다(`_OUTPUT_AFFECTING_ENV` 주석 참고).
    """
    raw = f"{req.model_dump_json()}|{_env_fingerprint()}"
    return sha256_hex(raw.encode("utf-8"))


def get_cached_generate(key: str) -> GenerateResponse | None:
    """캐시된 응답. 없으면 None."""
    if not cache_enabled():
        return None
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


def clear_generate_cache() -> None:
    """테스트·수동 초기화용."""
    _CACHE.clear()
