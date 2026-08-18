"""미국 자외선차단 성분 정합 조회(reference.us_ingredients) 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_reference_us_ingredients.py -q
"""

from barum.reference.us_ingredients import (
    canonical_name,
    check_sunscreen_ingredients,
    is_known_uv_filter,
    is_us_approved,
)


def test_canonical_name_maps_inci_to_cfr():
    assert canonical_name("Octinoxate") == "Octyl methoxycinnamate"
    assert canonical_name("Octisalate") == "Octyl salicylate"


def test_canonical_name_passthrough_when_unknown():
    assert canonical_name("정제수") == "정제수"


def test_is_us_approved_direct_cfr_name():
    assert is_us_approved("Zinc oxide") is True


def test_is_us_approved_via_inci_synonym():
    """전성분표엔 보통 INCI명(Octinoxate)이 적히지만, 대조는 CFR 공식명 기준으로 통과해야 한다."""
    assert is_us_approved("Octinoxate") is True


def test_is_us_approved_newly_added_ingredient():
    """OTC000039로 추가된 베모트리지놀도 승인 목록에 포함돼야 한다."""
    assert is_us_approved("Bemotrizinol") is True


def test_is_us_approved_false_for_korea_only_ingredient():
    """드로메트리졸은 한국 고시원료지만 미국 승인 17종엔 없다(sunscreen_otc_classification.md §3)."""
    assert is_us_approved("드로메트리졸") is False


def test_is_known_uv_filter_true_for_korea_only_ingredient():
    """미국엔 없어도 한국 고시원료표에 있으면 '자외선차단 성분'으로는 인식해야 미승인 지목이 가능하다."""
    assert is_known_uv_filter("드로메트리졸") is True


def test_is_known_uv_filter_false_for_unrelated_ingredient():
    assert is_known_uv_filter("정제수") is False


def test_check_sunscreen_ingredients_splits_approved_and_unapproved():
    result = check_sunscreen_ingredients(["정제수", "Zinc oxide", "드로메트리졸", "글리세린"])
    assert result == {"approved": ["Zinc oxide"], "unapproved": ["드로메트리졸"]}


def test_check_sunscreen_ingredients_empty_when_no_uv_filters():
    assert check_sunscreen_ingredients(["정제수", "글리세린"]) == {"approved": [], "unapproved": []}


def test_check_sunscreen_ingredients_preserves_input_order():
    result = check_sunscreen_ingredients(["Octinoxate", "Avobenzone"])
    assert result["approved"] == ["Octinoxate", "Avobenzone"]
