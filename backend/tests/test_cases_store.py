"""사례 저장/검색 어댑터(storage.cases_store) 유닛테스트 (Supabase 가짜 주입).

실제 적재·검색은 수동 스모크(스키마 생긴 뒤). 여기선 호출 계약·파싱만 본다.

    ./venv/bin/python -m pytest tests/test_cases_store.py -q
"""

from types import SimpleNamespace

import pytest

from barum.storage.cases_store import (
    build_case_rows,
    search_similar_cases,
)


class _Exec:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return SimpleNamespace(data=self._data)


class FakeClient:
    """rpc 호출을 기록하고 캔드 data를 돌려주는 가짜 Supabase 클라이언트."""

    def __init__(self, rpc_data=None):
        self._rpc_data = rpc_data or []
        self.rpc_calls = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return _Exec(self._rpc_data)


def test_search_similar_cases_calls_rpc_with_params_and_returns_data():
    client = FakeClient(rpc_data=[{"text": "아토피 완화", "similarity": 0.92}])
    out = search_similar_cases(client, [0.1, 0.2, 0.3], k=2)
    assert out == [{"text": "아토피 완화", "similarity": 0.92}]
    name, params = client.rpc_calls[0]
    assert name == "match_reference_cases"
    assert params["match_count"] == 2
    assert params["query_embedding"] == [0.1, 0.2, 0.3]


def test_search_similar_cases_returns_empty_on_none_data():
    """RPC가 data=None을 주면 빈 리스트(방어)."""
    client = FakeClient(rpc_data=None)
    assert search_similar_cases(client, [0.1], k=3) == []


def test_build_case_rows_zips_cases_with_embeddings():
    cases = [
        {"text": "문구A", "violation": "T1", "disposition": "정지3개월", "source": "식약처"},
    ]
    rows = build_case_rows(cases, [[0.1, 0.2]])
    assert rows == [
        {
            "text": "문구A",
            "violation": "T1",
            "disposition": "정지3개월",
            "source": "식약처",
            "embedding": [0.1, 0.2],
        }
    ]


def test_build_case_rows_rejects_length_mismatch():
    with pytest.raises(ValueError):
        build_case_rows([{"text": "A"}], [[0.1], [0.2]])
