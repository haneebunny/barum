"""GeminiVLM의 동시성 안전장치 유닛테스트. 실제 API·인증은 안 탄다.

모듈 이미지를 병렬로 생성하면(2026-08-24, generate_module_images) 같은 인스턴스를
여러 스레드가 동시에 부른다. `_throttle`/`_record_usage`가 락 없이 공유 상태
(`_last_call`/`total_tokens`)를 건드리면 경합한다 - 그 락이 실제로 막아주는지 확인.
"""

import threading
import time

from barum.vlm import GeminiVLM


def _vlm(rpm: int = 600) -> GeminiVLM:
    """네트워크·인증 없이 어댑터를 만든다(test_image_generator.py의 _generator와 같은 패턴)."""
    v = GeminiVLM.__new__(GeminiVLM)
    v.model = "sim"
    v.total_tokens = 0
    v._min_interval = 60.0 / rpm if rpm else 0.0
    v._last_call = 0.0
    v._lock = threading.Lock()
    return v


def test_동시_호출이어도_최소_간격이_지켜진다():
    """락 없이 동시에 부르면 여러 스레드가 _last_call을 같은 값으로 읽어 간격이
    안 지켜진다(PM 지적, 2026-08-24) - rpm=600(간격 0.1초)으로 빠르게 확인."""
    v = _vlm(rpm=600)
    starts: list[float] = []
    lock = threading.Lock()

    def call():
        v._throttle()
        with lock:
            starts.append(time.monotonic())

    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    starts.sort()
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(gap >= v._min_interval - 0.01 for gap in gaps), (
        f"간격이 최소 간격({v._min_interval})보다 좁은 호출이 있음: {gaps}"
    )


def test_동시_토큰_누적이_유실되지_않는다():
    """`+=`는 락 없이 병렬 호출하면 읽기-더하기-쓰기가 원자적이지 않아 갱신이
    유실될 수 있다. 스레드 100개 × 10토큰이 정확히 1000이 되는지로 확인한다."""
    v = _vlm(rpm=0)  # 스로틀 끔 - 이 테스트는 누적만 본다

    class FakeUsage:
        total_tokens = 10

    class FakeInteraction:
        usage = FakeUsage()

    def call():
        v._record_usage(FakeInteraction())

    threads = [threading.Thread(target=call) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert v.total_tokens == 1000
