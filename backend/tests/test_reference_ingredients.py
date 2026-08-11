"""성분 정합 조회(reference.ingredients) 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_reference_ingredients.py -q
"""

from barum.reference.ingredients import infer_category, match_ingredient


def test_infer_category_by_keyword():
    assert infer_category("멜라닌 생성을 억제해 미백에 도움") == "미백"
    assert infer_category("주름을 개선하는 안티에이징") == "주름개선"
    assert infer_category("자외선 차단 효과") == "자외선차단"
    assert infer_category("촉촉한 보습 크림") is None


def test_match_ingredient_found():
    row = match_ingredient("미백", ["정제수", "나이아신아마이드", "글리세린"])
    assert row is not None
    assert row["성분명"] == "나이아신아마이드"


def test_match_ingredient_not_found():
    assert match_ingredient("미백", ["정제수", "글리세린"]) is None


def test_match_ingredient_normalizes_spacing_and_dash():
    """'알파-비사보롤'처럼 붙임표가 있어도 공백·표기 차이를 흡수해 대조한다."""
    row = match_ingredient("미백", ["알파 비사보롤"])  # 하이픈 없이 입력
    assert row is not None
    assert row["성분명"] == "알파-비사보롤"


def test_match_ingredient_unknown_category_returns_none():
    assert match_ingredient("존재안함", ["정제수"]) is None
