"""인증서-인정문구 매칭(reference.approved_claims) 유닛테스트.

게이트는 카테고리 단위(status=confirmed만 통과)라 카테고리마다 대조 완료
시점이 달라도 안전하다. 실 데이터는 비비의 대조 진행 상황에 따라 계속
바뀌므로, 매칭·게이트 로직은 가짜 데이터로 monkeypatch해서 확인한다.

    ./venv/bin/python -m pytest tests/test_reference_approved_claims.py -q
"""

from barum.reference import approved_claims


def _fake_data():
    return {
        "categories": {
            "미백": {"status": "confirmed", "statements": ["피부의 미백에 도움을 준다."]},
            "주름개선": {"status": "confirmed", "statements": []},
            "자외선차단": {
                "status": "needs_confirmation",
                "candidate_statement": "피부를 곱게 태워주거나 자외선으로부터 피부를 보호하는데 도움을 주는 제품",
            },
        }
    }


def test_match_approved_claim_found_when_confirmed(monkeypatch):
    monkeypatch.setattr(approved_claims, "_load", _fake_data)
    phrase = approved_claims.match_approved_claim("미백", ["미백 기능성 인증"])
    assert phrase == "피부의 미백에 도움을 준다."


def test_match_approved_claim_no_matching_certification(monkeypatch):
    monkeypatch.setattr(approved_claims, "_load", _fake_data)
    assert approved_claims.match_approved_claim("미백", ["다른 인증"]) is None


def test_match_approved_claim_confirmed_but_empty_statements_returns_none(monkeypatch):
    monkeypatch.setattr(approved_claims, "_load", _fake_data)
    assert approved_claims.match_approved_claim("주름개선", ["주름개선 기능성 인증"]) is None


def test_match_approved_claim_needs_confirmation_category_blocked_even_with_certification(monkeypatch):
    """자외선차단(needs_confirmation)은 인증서가 맞아도 막힌다 — candidate_statement는 절대 안 읽는다."""
    monkeypatch.setattr(approved_claims, "_load", _fake_data)
    assert approved_claims.match_approved_claim("자외선차단", ["자외선차단 기능성 인증"]) is None


def test_match_approved_claim_confirmed_category_does_not_unblock_others(monkeypatch):
    """하나(미백)가 confirmed라고 다른 카테고리(자외선차단)까지 같이 풀리면 안 된다 — 카테고리별 독립 게이트."""
    monkeypatch.setattr(approved_claims, "_load", _fake_data)
    assert approved_claims.match_approved_claim("미백", ["미백 기능성 인증"]) is not None
    assert approved_claims.match_approved_claim("자외선차단", ["미백 기능성 인증", "자외선차단 기능성 인증"]) is None
