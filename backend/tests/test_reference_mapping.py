"""T-체계 ↔ ViolationType 매핑 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_reference_mapping.py -q
"""

import pytest

from barum.models import ViolationType
from barum.reference.mapping import (
    NOT_A_JUDGMENT_LABEL,
    T_TO_VIOLATION_TYPE,
    legal_basis_for,
)


def test_t1_t2_map_one_to_one():
    assert T_TO_VIOLATION_TYPE["T1"] == ViolationType.type_1_drug_misperception
    assert T_TO_VIOLATION_TYPE["T2"] == ViolationType.type_2_functional_misperception


def test_t5_and_t6_both_fold_to_5ho():
    """별표5 세부유형(T6)은 독립 라벨이 아니라 5호의 하위 근거라 T5와 같은 값으로 접힌다."""
    assert T_TO_VIOLATION_TYPE["T5"] == ViolationType.type_5_deception
    assert T_TO_VIOLATION_TYPE["T6"] == ViolationType.type_5_deception


def test_t3_t4_are_not_judgment_labels():
    """T3(삭제조항)·T4(AI 가드레일)는 문구 판정 라벨이 아니다."""
    assert "T3" not in T_TO_VIOLATION_TYPE
    assert "T4" not in T_TO_VIOLATION_TYPE
    assert "T3" in NOT_A_JUDGMENT_LABEL
    assert "T4" in NOT_A_JUDGMENT_LABEL


def test_legal_basis_cites_real_article_numbers():
    assert "제1호" in legal_basis_for(ViolationType.type_1_drug_misperception)
    assert "제2호" in legal_basis_for(ViolationType.type_2_functional_misperception)
    assert "제5호" in legal_basis_for(ViolationType.type_5_deception)


def test_legal_basis_undefined_for_non_violations():
    """합법·대상외는 근거 조항이 없다(위반이 아니므로)."""
    with pytest.raises(KeyError):
        legal_basis_for(ViolationType.legal)
    with pytest.raises(KeyError):
        legal_basis_for(ViolationType.out_of_scope)
