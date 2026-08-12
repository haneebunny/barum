"""성분 정합 조회(reference.ingredients) 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_reference_ingredients.py -q
"""

from barum.reference.ingredients import (
    check_amount_threshold,
    find_amount_for,
    infer_category,
    match_ingredient,
    match_ingredient_strict,
    parse_amount,
)


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


def test_parse_amount_single_percent():
    assert parse_amount("2%") == (2.0, 2.0, "%")


def test_parse_amount_range_percent():
    assert parse_amount("2~5%") == (2.0, 5.0, "%")


def test_parse_amount_iu_per_g_with_thousands_comma():
    assert parse_amount("2,500 IU/g") == (2500.0, 2500.0, "IU/g")


def test_parse_amount_rejects_annotated_values():
    """"산으로 10%"·"25% (자외선차단성분으로서)"처럼 주석 붙은 값은 비교 불가로 처리."""
    assert parse_amount("산으로 10%") is None
    assert parse_amount("25% (자외선차단성분으로서)") is None


def test_check_amount_threshold_single_value_needs_at_least():
    """단일 기준함량(닥나무추출물 2%)은 그 이상이면 통과."""
    row = {"성분명": "닥나무추출물", "기준 함량": "2%"}
    assert check_amount_threshold("미백", row, "3%") is True
    assert check_amount_threshold("미백", row, "1%") is False


def test_check_amount_threshold_range_must_stay_within_bounds():
    """범위 기준함량(알부틴 2~5%)은 상한을 넘으면 실패해야 한다(정식 심사 대상)."""
    row = {"성분명": "알부틴", "기준 함량": "2~5%"}
    assert check_amount_threshold("미백", row, "3%") is True
    assert check_amount_threshold("미백", row, "10%") is False  # 범위 상한 초과 → 스킵
    assert check_amount_threshold("미백", row, "1%") is False  # 범위 하한 미달 → 스킵


def test_check_amount_threshold_max_field_needs_at_most():
    row = {"성분명": "드로메트리졸", "최대 함량": "1%"}
    assert check_amount_threshold("자외선차단", row, "0.5%") is True
    assert check_amount_threshold("자외선차단", row, "2%") is False


def test_check_amount_threshold_unit_mismatch_fails():
    row = {"성분명": "레티놀", "기준 함량": "2,500 IU/g"}
    assert check_amount_threshold("주름개선", row, "2500%") is False


def test_match_ingredient_strict_requires_name_amount_and_threshold():
    assert match_ingredient_strict("미백", [("나이아신아마이드", "3%")]) is not None
    # 이름은 맞는데 범위 상한 초과 → 스킵
    assert match_ingredient_strict("미백", [("알부틴", "10%")]) is None
    # 함량 자체가 없음(리스트에 없는 성분) → 스킵
    assert match_ingredient_strict("미백", [("정제수", "50%")]) is None


def test_find_amount_for_matches_by_normalized_name():
    row = {"성분명": "알파-비사보롤", "기준 함량": "0.5%"}
    assert find_amount_for(row, [("알파 비사보롤", "1%")]) == "1%"  # 공백·하이픈 차이 흡수


def test_find_amount_for_returns_none_when_not_given():
    row = {"성분명": "나이아신아마이드", "기준 함량": "2~5%"}
    assert find_amount_for(row, [("알부틴", "3%")]) is None
