"""인증서-인정문구 매칭(reference.approved_claims) 유닛테스트.

실제 data/approved_efficacy_statements.json은 `status: "draft"`(별표4 원문 대조
전, 비비 노트 "실제 생성에 쓰지 말 것")라 매칭 로직 자체는 가짜 데이터로
monkeypatch해서 확인하고, draft 게이트는 실 데이터로 직접 확인한다.

    ./venv/bin/python -m pytest tests/test_reference_approved_claims.py -q
"""

from barum.reference import approved_claims


def _fake_approved_data():
    return {
        "status": "verified",
        "categories": {
            "미백": {"statements": ["피부 미백에 도움을 줍니다."]},
            "주름개선": {"statements": []},
            "자외선차단": {"statements": []},
        },
    }


def _fake_draft_data():
    return {
        "status": "draft",
        "categories": {"미백": {"statements": ["피부 미백에 도움을 줍니다."]}},
    }


def test_match_approved_claim_found(monkeypatch):
    monkeypatch.setattr(approved_claims, "_load", _fake_approved_data)
    phrase = approved_claims.match_approved_claim("미백", ["미백 기능성 인증"])
    assert phrase == "피부 미백에 도움을 줍니다."


def test_match_approved_claim_no_matching_certification(monkeypatch):
    monkeypatch.setattr(approved_claims, "_load", _fake_approved_data)
    assert approved_claims.match_approved_claim("미백", ["다른 인증"]) is None


def test_match_approved_claim_empty_category_returns_none(monkeypatch):
    monkeypatch.setattr(approved_claims, "_load", _fake_approved_data)
    assert approved_claims.match_approved_claim("주름개선", ["아무 인증"]) is None


def test_match_approved_claim_draft_status_blocks_even_with_matching_certification(monkeypatch):
    """status=draft면 인증서가 맞아도 절대 문구를 내지 않는다(원문 대조 전 안전장치)."""
    monkeypatch.setattr(approved_claims, "_load", _fake_draft_data)
    assert approved_claims.match_approved_claim("미백", ["미백 기능성 인증"]) is None


def test_match_approved_claim_real_data_is_still_draft():
    """실제 적재 데이터(비비, 2026-08-12)는 아직 draft라 항상 None — 원문 대조 끝나면 자동 해제."""
    assert approved_claims.match_approved_claim("미백", ["미백 기능성 인증"]) is None
