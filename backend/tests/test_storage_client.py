"""Supabase 클라이언트 자격 검증 유닛테스트 (네트워크 없음).

실제 연결·쿼리는 수동 스모크(scripts). 여기선 순수 검증 로직만 본다.

    ./venv/bin/python -m pytest tests/test_storage_client.py -q
"""

import pytest

from barum.storage.client import _normalize_url, _require_credentials


def test_normalize_url_strips_rest_v1_and_trailing_slash():
    """REST 엔드포인트 전체를 넣어도 베이스 URL로 정규화한다(흔한 실수 방어)."""
    assert (
        _normalize_url("https://abc.supabase.co/rest/v1/") == "https://abc.supabase.co"
    )
    assert _normalize_url("https://abc.supabase.co/") == "https://abc.supabase.co"
    assert _normalize_url("https://abc.supabase.co") == "https://abc.supabase.co"


def test_require_credentials_returns_pair_when_present():
    assert _require_credentials("https://x.supabase.co", "secretkey") == (
        "https://x.supabase.co",
        "secretkey",
    )


def test_require_credentials_raises_when_url_missing():
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        _require_credentials(None, "secretkey")


def test_require_credentials_raises_when_key_missing():
    with pytest.raises(RuntimeError, match="SUPABASE_KEY"):
        _require_credentials("https://x.supabase.co", "")
