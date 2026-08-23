"""`/generate` 응답 캐시 (오프라인).

    ./venv/bin/python -m pytest tests/test_generate_cache.py -q
"""

import os

os.environ["JUDGE_KIND"] = "stub"
os.environ["CHECKS_PERSIST"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from barum.api import app as app_module  # noqa: E402
from barum.models import GenerateRequest  # noqa: E402
from barum.storage.generate_cache import (  # noqa: E402
    build_generate_cache_key,
    clear_generate_cache,
)

client = TestClient(app_module.app)


class CountingVLM:
    calls = 0

    def generate_json(self, prompt, images):
        CountingVLM.calls += 1
        return {"제품개요": "담백한 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"}


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    clear_generate_cache()
    CountingVLM.calls = 0
    monkeypatch.setattr(app_module, "_section_vlm", lambda: CountingVLM())
    yield
    clear_generate_cache()


_REQ = {"content": "재생 크림입니다", "product_name": "테스트크림"}


def test_같은_입력은_두_번째부터_안_만든다():
    first = client.post("/generate", json=_REQ).json()
    calls_after_first = CountingVLM.calls
    second = client.post("/generate", json=_REQ).json()

    assert CountingVLM.calls == calls_after_first, "캐시 적중인데 LLM을 다시 불렀다"
    assert first == second


def test_입력이_다르면_다시_만든다():
    client.post("/generate", json=_REQ)
    calls_after_first = CountingVLM.calls
    client.post("/generate", json={**_REQ, "product_name": "다른크림"})
    assert CountingVLM.calls > calls_after_first


def test_키는_요청_전체를_담는다():
    """필드를 골라 담으면 새 필드가 생길 때 넣는 걸 잊는다. 조용히 틀린다."""
    base = GenerateRequest(content="x", product_name="크림")
    assert build_generate_cache_key(base) == build_generate_cache_key(
        GenerateRequest(content="x", product_name="크림")
    )
    # 최근에 추가된 필드들도 키를 바꿔야 한다.
    for field, value in [
        ("preset", "minimal_white"),
        ("targeting", "20대"),
        ("notes", "메모"),
        ("ingredients", "정제수"),
        ("result_id", "rid1"),
    ]:
        other = GenerateRequest(content="x", product_name="크림", **{field: value})
        assert build_generate_cache_key(base) != build_generate_cache_key(other), field


def test_승인_대체표현이_다르면_다른_캐시다():
    a = GenerateRequest(content="x", approved_replacements=[])
    b = GenerateRequest(
        content="x",
        approved_replacements=[{"original": "가", "replaced": "나"}],
    )
    assert build_generate_cache_key(a) != build_generate_cache_key(b)


def test_이미지_생성_스위치가_키에_반영된다(monkeypatch):
    """**이게 없으면 플래그를 켠 직후 이미지 없는 옛 응답이 캐시에서 나온다.**

    "플래그를 켰는데 이미지가 안 나온다"로 읽혀 원인을 엉뚱한 데서 찾게 된다.
    """
    req = GenerateRequest(content="x", product_name="크림")
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "0")
    off = build_generate_cache_key(req)
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "1")
    assert build_generate_cache_key(req) != off


def test_판정_모드가_바뀌면_다른_캐시다(monkeypatch):
    req = GenerateRequest(content="x", product_name="크림")
    monkeypatch.setenv("JUDGE_KIND", "stub")
    stub = build_generate_cache_key(req)
    monkeypatch.setenv("JUDGE_KIND", "rag")
    assert build_generate_cache_key(req) != stub


def test_캐시를_끄면_매번_만든다(monkeypatch):
    monkeypatch.setenv("GENERATE_CACHE_ENABLED", "0")
    client.post("/generate", json=_REQ)
    calls_after_first = CountingVLM.calls
    client.post("/generate", json=_REQ)
    assert CountingVLM.calls > calls_after_first


def test_상한을_넘으면_오래된_것부터_버린다():
    from barum.storage.generate_cache import (
        _CACHE,
        _MAX_ENTRIES,
        get_cached_generate,
        put_cached_generate,
    )
    from barum.models import GenerateResponse, ImagePlan, RecheckSummary

    def _resp():
        return GenerateResponse(
            sections=[], replacements=[], image_plan=ImagePlan(),
            recheck=RecheckSummary(safe=True, n_findings=0), disclaimer="x",
        )

    for i in range(_MAX_ENTRIES + 5):
        put_cached_generate(f"k{i}", _resp())
    assert len(_CACHE) == _MAX_ENTRIES
    assert get_cached_generate("k0") is None  # 가장 오래된 것은 밀려났다
    assert get_cached_generate(f"k{_MAX_ENTRIES + 4}") is not None
