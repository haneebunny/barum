"""레퍼런스 표 파서 유닛테스트 (외부 의존 없음, 순수 파싱 로직).

    venv/bin/python -m pytest tests/test_extract_reference_tables.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import extract_reference_tables as ext  # noqa: E402


def test_parse_table_basic():
    block = """
| a | b |
|---|---|
| 1 | x |
| 2 | y |
"""
    rows = ext._parse_table(block)
    assert rows == [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]


def test_parse_table_empty_for_no_table():
    assert ext._parse_table("그냥 텍스트, 표 아님") == []


def test_sections_splits_by_h2():
    text = "머리말\n## 첫째\n본문1\n## 둘째\n본문2\n"
    secs = ext._sections(text)
    assert set(secs.keys()) == {"첫째", "둘째"}
    assert "본문1" in secs["첫째"]
    assert "본문2" in secs["둘째"]


def test_extract_functional_ingredients_counts():
    """실제 레퍼런스 md 대비 카테고리별 성분 개수(문서 채움 상태와 일치해야 함)."""
    data = ext.extract_functional_ingredients()
    assert len(data["categories"]["미백"]) == 9
    assert len(data["categories"]["주름개선"]) == 4
    assert len(data["categories"]["자외선차단"]) == 27
    assert data["categories"]["미백"][0]["성분명"] == "닥나무추출물"


def test_extract_prohibited_expressions_rows():
    data = ext.extract_prohibited_expressions()
    assert len(data["rows"]) == 17
    types = {r["위반유형"] for r in data["rows"]}
    assert types == {"T1", "T2", "T5"}  # T3(삭제)·T4(가드레일)·T6은 이 표에 없음
