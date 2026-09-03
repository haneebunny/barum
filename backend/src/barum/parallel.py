"""과금 호출을 나눠 동시에 보내는 작은 도우미.

/check는 OCR·1차필터·판정이 배치 단위 순차 호출이라 배치 수만큼 대기가 쌓였다
(2026-08-23 실측: 선크림 데모 1차필터 52초, RAG판정 98초). 배치끼리는 서로
독립이므로 동시에 보내고, 결과만 **입력 순서대로** 돌려준다. 프롬프트·배치 크기·
모델은 그대로라 판정 내용은 안 바뀐다. 대기만 겹친다.

대체표현 단계는 여기 안 태운다. 그쪽은 "한 호출로 전부"가 확정이다
(2026-08-25 팀장 지시, generate/replace.py 주석 참고).
"""
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")

_DEFAULT_WORKERS = 4


def check_workers() -> int:
    """`CHECK_MAX_WORKERS`(기본 4). 1이면 예전처럼 순차로 돈다."""
    raw = os.environ.get("CHECK_MAX_WORKERS", "")
    try:
        n = int(raw) if raw else _DEFAULT_WORKERS
    except ValueError:
        n = _DEFAULT_WORKERS
    return max(1, n)


def run_in_order(
    fn: Callable[[T], R], items: Iterable[T], workers: int
) -> list[R | Exception]:
    """items 각각에 fn을 적용해 입력 순서대로 결과를 낸다.

    예외는 삼키지 않고 그 자리에 예외 객체로 돌려준다. 스킵할지 터뜨릴지는
    호출자가 정한다(CLAUDE.md §E, 과금 호출은 재시도 없이 스킵). fn이 정상 결과로
    Exception 인스턴스를 돌려주는 경우는 없다고 가정한다.
    workers가 1 이하이거나 항목이 하나면 스레드를 안 만든다.
    """
    items = list(items)

    def _guard(item: T) -> R | Exception:
        try:
            return fn(item)
        except Exception as e:  # noqa: BLE001 - 호출자에게 그대로 넘긴다
            return e

    if workers <= 1 or len(items) <= 1:
        return [_guard(item) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(_guard, items))
