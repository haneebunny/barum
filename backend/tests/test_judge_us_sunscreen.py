"""미국 프리플라이트 판정(judge.us_sunscreen) 유닛테스트 (외부 의존 없음, VLM 미호출).

    venv/bin/python -m pytest tests/test_judge_us_sunscreen.py -q
"""

from barum.models import USPreflightCategory
from barum.judge.us_sunscreen import USSunscreenJudge


def _sentence(order: int, text: str) -> dict:
    return {"order": order, "tile": None, "text": text}


def test_no_spf_expression_means_no_findings_even_with_ingredients():
    """표현 트리거가 없으면 성분만 있어도 대상이 아니다(§3 세 번째 예시)."""
    judge = USSunscreenJudge()
    findings = judge.judge([_sentence(0, "촉촉한 수분크림")], ingredients=["Zinc oxide"])
    assert findings == []


def test_spf_expression_without_ingredients_flags_both():
    judge = USSunscreenJudge()
    findings = judge.judge([_sentence(0, "SPF50+ 자외선차단")], ingredients=None)
    categories = [f.category for f in findings]
    assert USPreflightCategory.otc_reclassification in categories
    assert USPreflightCategory.ingredient_info_missing in categories


def test_spf_expression_with_approved_ingredient_only_otc_finding():
    judge = USSunscreenJudge()
    findings = judge.judge([_sentence(0, "SPF50+ 자외선차단")], ingredients=["정제수", "Zinc oxide"])
    assert len(findings) == 1
    assert findings[0].category == USPreflightCategory.otc_reclassification


def test_spf_expression_with_korea_only_ingredient_flags_unapproved():
    """드로메트리졸은 한국 고시원료지만 미국 미승인 — sunscreen_otc_classification.md §3 실제 사례."""
    judge = USSunscreenJudge()
    findings = judge.judge([_sentence(0, "SPF50+ 자외선차단")], ingredients=["정제수", "드로메트리졸"])
    unapproved = [f for f in findings if f.category == USPreflightCategory.unapproved_ingredient]
    assert len(unapproved) == 1
    assert unapproved[0].span == "드로메트리졸"


def test_multiple_spf_sentences_each_get_own_finding():
    judge = USSunscreenJudge()
    sentences = [_sentence(0, "SPF50+ 자외선차단"), _sentence(1, "UV차단 강력한 선블록")]
    findings = judge.judge(sentences, ingredients=["Zinc oxide"])
    otc_findings = [f for f in findings if f.category == USPreflightCategory.otc_reclassification]
    assert len(otc_findings) == 2


def test_spf_matching_is_case_insensitive():
    judge = USSunscreenJudge()
    findings = judge.judge([_sentence(0, "spf50 sunscreen")], ingredients=["Zinc oxide"])
    otc_findings = [f for f in findings if f.category == USPreflightCategory.otc_reclassification]
    assert len(otc_findings) == 1
    assert otc_findings[0].span == "spf"  # 첫 매칭 키워드 원문 그대로


def test_finding_location_preserves_sentence_order():
    judge = USSunscreenJudge()
    findings = judge.judge([_sentence(3, "SPF50 자외선차단")], ingredients=["Zinc oxide"])
    assert findings[0].location.order == 3
