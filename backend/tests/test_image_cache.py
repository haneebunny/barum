"""이미지 검증 리포트 캐시 유닛테스트.

동일 이미지가 들어왔을 때 OCR/VLM 및 run_check를 다시 돌리지 않고 기존 캐시 데이터를 사용하는지 검증한다.
"""

import io
import os
from PIL import Image
import pytest

os.environ["JUDGE_KIND"] = "stub"
os.environ["CHECKS_PERSIST"] = "0"

from fastapi.testclient import TestClient
from barum.api.app import app
from barum.models import CheckReport, Region, Summary
from barum.storage.checks_store import (
    build_cache_key,
    clear_image_cache,
    get_cached_check,
    save_cached_check,
    sha256_hex,
)

client = TestClient(app)


def _make_dummy_png_bytes(color: str = "white") -> bytes:
    im = Image.new("RGB", (10, 10), color=color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_image_cache()
    yield
    clear_image_cache()


def test_cache_key_generation():
    key1 = build_cache_key("sha123", "KR", ad_text="test")
    key2 = build_cache_key("sha123", "KR", ad_text="test")
    key3 = build_cache_key("sha123", "US", ad_text="test")
    assert key1 == key2
    assert key1 != key3


def test_memory_cache_get_save_clear():
    key = build_cache_key("sha_abc", "KR")
    assert get_cached_check(None, key) is None

    dummy_report = CheckReport(
        findings=[],
        unjudged=[],
        summary=Summary(region=Region.KR, n_sentences=0, n_findings=0),
    )
    save_cached_check(key, dummy_report)
    assert get_cached_check(None, key) is dummy_report

    clear_image_cache()
    assert get_cached_check(None, key) is None


def test_check_endpoint_caches_duplicate_image(monkeypatch):
    """동일 이미지를 두 번 POST하면 두 번째 요청은 run_check를 돌리지 않고 캐시된 리포트를 반환한다."""
    from barum.api import app as app_module

    run_check_calls = []
    orig_run_check = app_module.run_check

    def mock_run_check(*args, **kwargs):
        run_check_calls.append(kwargs)
        return orig_run_check(*args, **kwargs)

    monkeypatch.setattr(app_module, "run_check", mock_run_check)

    img_bytes = _make_dummy_png_bytes("white")

    # 1회차 요청 (미스)
    r1 = client.post(
        "/check",
        data={"region": "KR", "ad_text": "광고문구"},
        files={"image": ("test.png", io.BytesIO(img_bytes), "image/png")},
    )
    assert r1.status_code == 200
    assert len(run_check_calls) == 1

    # 2회차 요청 (동일 이미지 & 파라미터 -> 캐시 히트)
    r2 = client.post(
        "/check",
        data={"region": "KR", "ad_text": "광고문구"},
        files={"image": ("test.png", io.BytesIO(img_bytes), "image/png")},
    )
    assert r2.status_code == 200
    assert len(run_check_calls) == 1  # run_check 재호출되지 않음!
    assert r2.json() == r1.json()

    # 3회차 요청 (다른 이미지 -> 캐시 미스)
    img_bytes2 = _make_dummy_png_bytes("blue")
    r3 = client.post(
        "/check",
        data={"region": "KR", "ad_text": "광고문구"},
        files={"image": ("test2.png", io.BytesIO(img_bytes2), "image/png")},
    )
    assert r3.status_code == 200
    assert len(run_check_calls) == 2  # run_check 재호출됨!


def _fake_client_with_row(fake_row):
    class FakeQuery:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def order(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self):
            from types import SimpleNamespace
            return SimpleNamespace(data=[fake_row])

    class FakeClient:
        def table(self, name): return FakeQuery()

    return FakeClient()


def _fake_row(img_sha, cache_key=None):
    report = {
        "findings": [],
        "unjudged": [],
        "summary": {"region": "KR", "n_sentences": 1, "n_findings": 0},
    }
    if cache_key is not None:
        report["_cache_key"] = cache_key
    return {"id": "rid_from_db_123", "region": "KR", "image_sha256": img_sha, "report": report}


def test_supabase_fallback_restores_when_cache_key_matches():
    """메모리에 없어도, 저장된 _cache_key가 요청 키와 같으면 Supabase에서 복원한다."""
    img_sha = sha256_hex(b"supabase-stored-image")
    cache_key = build_cache_key(img_sha, "KR")
    row = _fake_row(img_sha, cache_key=cache_key)

    cached = get_cached_check(_fake_client_with_row(row), cache_key, img_sha)
    assert cached is not None
    assert isinstance(cached, CheckReport)
    assert cached.result_id == "rid_from_db_123"


def test_supabase_fallback_rejects_mismatched_inputs_same_image():
    """같은 이미지라도 입력(광고문구)이 다르면 2차 캐시를 복원하지 않는다(엉뚱한 옛 결과 방지)."""
    img_sha = sha256_hex(b"supabase-stored-image")
    stored_key = build_cache_key(img_sha, "KR", ad_text="옛날 문구")
    requested_key = build_cache_key(img_sha, "KR", ad_text="새 문구")
    row = _fake_row(img_sha, cache_key=stored_key)

    cached = get_cached_check(_fake_client_with_row(row), requested_key, img_sha)
    assert cached is None  # 키 불일치 -> 재검사


def test_supabase_fallback_rejects_legacy_row_without_cache_key():
    """_cache_key가 없는 옛 레코드는 로직 버전을 알 수 없어 복원하지 않는다(스테일 방지)."""
    img_sha = sha256_hex(b"supabase-stored-image")
    cache_key = build_cache_key(img_sha, "KR")
    row = _fake_row(img_sha, cache_key=None)  # 옛 스키마: _cache_key 없음

    cached = get_cached_check(_fake_client_with_row(row), cache_key, img_sha)
    assert cached is None


def test_cache_key_changes_with_logic_version():
    """로직 버전이 키에 들어가 있어, 같은 입력이어도 버전이 바뀌면 키가 달라진다."""
    from barum.storage import checks_store

    img_sha = sha256_hex(b"same-image")
    key_v_current = build_cache_key(img_sha, "KR", ad_text="문구")

    original = checks_store._CACHE_LOGIC_VERSION
    try:
        checks_store._CACHE_LOGIC_VERSION = "999"
        key_v_bumped = build_cache_key(img_sha, "KR", ad_text="문구")
    finally:
        checks_store._CACHE_LOGIC_VERSION = original

    assert key_v_current != key_v_bumped
