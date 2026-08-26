"""검사 이력 저장/조회 어댑터(storage.checks_store) 유닛테스트 (Supabase 가짜 주입).

실제 저장·이미지 업로드는 수동 스모크. 여기선 해시·row·쿼리 계약만 본다.

    ./venv/bin/python -m pytest tests/test_checks_store.py -q
"""

import hashlib
from types import SimpleNamespace

from barum.storage.checks_store import (
    build_check_row,
    get_check,
    new_result_id,
    save_check,
    sha256_hex,
)


class _Query:
    """table() 뒤에 체이닝되는 쿼리 흉내. execute()가 캔드 data를 준다."""

    def __init__(self, data):
        self._data = data
        self.inserted = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, row):
        self.inserted = row
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class FakeClient:
    def __init__(self, data=None):
        self.query = _Query(data)
        self.table_name = None

    def table(self, name):
        self.table_name = name
        return self.query


def test_sha256_hex_matches_hashlib():
    data = b"evidence-bytes"
    assert sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_new_result_id_is_urlsafe_and_long():
    rid = new_result_id()
    assert isinstance(rid, str)
    assert len(rid) >= 32  # token_urlsafe(32)는 43자 안팎
    assert all(c.isalnum() or c in "-_" for c in rid)  # URL-safe 문자만


def test_build_check_row_shape():
    row = build_check_row(
        "rid123", "KR", {"summary": {}}, image_sha256="abc", image_path="evi/x.png"
    )
    assert row == {
        "id": "rid123",
        "region": "KR",
        "report": {"summary": {}},
        "image_sha256": "abc",
        "image_path": "evi/x.png",
    }


def test_build_check_row_defaults_image_fields_none():
    row = build_check_row("rid", "KR", {})
    assert row["image_sha256"] is None
    assert row["image_path"] is None


def test_build_check_row_stores_only_owner_token_hash():
    row = build_check_row("rid", "KR", {}, owner_token_hash="hashed-owner")
    assert row["owner_token_hash"] == "hashed-owner"
    assert "history_token" not in row


def test_save_check_inserts_into_checks_table():
    client = FakeClient()
    save_check(client, {"id": "rid", "region": "KR", "report": {}})
    assert client.table_name == "checks"
    assert client.query.inserted == {"id": "rid", "region": "KR", "report": {}}


def test_get_check_returns_row_when_found():
    client = FakeClient(data=[{"id": "rid", "report": {"summary": {}}}])
    got = get_check(client, "rid")
    assert got == {"id": "rid", "report": {"summary": {}}}
    assert client.table_name == "checks"


def test_get_check_returns_none_when_missing():
    client = FakeClient(data=[])
    assert get_check(client, "nope") is None
