"""법령·고시 인용 레지스트리(reference.citations) 유닛테스트.

실 데이터는 비비가 계속 채우는 중이라 바뀔 수 있으므로, 조회·변환 로직은
가짜 레지스트리로 monkeypatch해서 확인한다.

    ./venv/bin/python -m pytest tests/test_reference_citations.py -q
"""

import pytest

from barum.reference import citations


def _fake_data():
    return {
        "entries": [
            {
                "id": "kr_law_art13",
                "jurisdiction": "KR",
                "law_name": "화장품법 제13조",
                "citation_id": None,
                "effective_date": "현행",
                "source_url": "https://example.kr/law13",
            },
            {
                "id": "kr_rule_appendix5",
                "jurisdiction": "KR",
                "law_name": "시행규칙 별표5",
                "citation_id": "별표5",
                "effective_date": "2019-12-12",
                "source_url": None,
            },
            {
                "id": "kr_guideline_2025_08_14",
                "jurisdiction": "KR",
                "law_name": "표시·광고 관리 지침",
                "citation_id": None,
                "effective_date": "2025-08-14",
                "source_url": None,
            },
            {
                "id": "kr_notice_review_2023_61",  # core 목록엔 없는 조건부 고시 — 안 나와야 함
                "jurisdiction": "KR",
                "law_name": "기능성화장품 심사에 관한 규정",
                "citation_id": "식약처고시 제2023-61호",
                "effective_date": "2023-09-21",
                "source_url": None,
            },
            {
                "id": "us_mocra_2022",
                "jurisdiction": "US",
                "law_name": "MoCRA",
                "citation_id": "2022년 제정",
                "effective_date": None,
                "source_url": None,
            },
            {
                "id": "us_fda_ftc_general",
                "jurisdiction": "US",
                "law_name": "FDA/FTC 화장품 광고 일반 규제",
                "citation_id": None,
                "effective_date": None,
                "source_url": None,
            },
        ]
    }


def test_get_core_citations_kr_returns_only_core_three(monkeypatch):
    monkeypatch.setattr(citations, "_load", _fake_data)
    ids = [e["id"] for e in citations.get_core_citations("KR")]
    assert ids == ["kr_law_art13", "kr_rule_appendix5", "kr_guideline_2025_08_14"]


def test_get_core_citations_excludes_conditional_notice(monkeypatch):
    """2호 성분정합 전용 고시(2023-61호)는 모든 검사 공통 근거가 아니라 core에서 빠져야 한다."""
    monkeypatch.setattr(citations, "_load", _fake_data)
    ids = [e["id"] for e in citations.get_core_citations("KR")]
    assert "kr_notice_review_2023_61" not in ids


def test_get_core_citations_us(monkeypatch):
    monkeypatch.setattr(citations, "_load", _fake_data)
    ids = [e["id"] for e in citations.get_core_citations("US")]
    assert ids == ["us_mocra_2022", "us_fda_ftc_general"]


def test_build_regulatory_basis_maps_fields(monkeypatch):
    monkeypatch.setattr(citations, "_load", _fake_data)
    basis = citations.build_regulatory_basis("KR")
    assert basis.jurisdiction == "KR"
    assert [c.id for c in basis.citations] == [
        "kr_law_art13", "kr_rule_appendix5", "kr_guideline_2025_08_14",
    ]
    first = basis.citations[0]
    assert first.law_name == "화장품법 제13조"
    assert first.source_url == "https://example.kr/law13"


def test_entry_by_id_missing_raises(monkeypatch):
    monkeypatch.setattr(citations, "_load", _fake_data)
    with pytest.raises(KeyError):
        citations._entry_by_id("no_such_id")
