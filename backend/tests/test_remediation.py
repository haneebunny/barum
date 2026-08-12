# -*- coding: utf-8 -*-
"""Remediation logic unit tests."""

from barum.models import ViolationType
from barum.reference.remediation import get_remediation


def test_remediation_by_keyword_in_sentence():
    """sentence 안에 키워드가 있을 때 알맞은 대체 표현이 선택되는지 검증."""
    suggestions, disclaimer = get_remediation(
        sentence="피부에 발생한 아토피성 건선 치료용 연고",
        violation_type=ViolationType.type_1_drug_misperception,
    )
    assert "극건성 피부용 보습" in suggestions
    assert "건조함으로 인한 가려움 완화" in suggestions
    assert len(suggestions) == 2
    assert "면책" in disclaimer or "보장하지 않습니다" in disclaimer


def test_remediation_by_keyword_in_span():
    """span 안에 키워드가 있을 때 알맞은 대체 표현이 선택되는지 검증."""
    suggestions, _ = get_remediation(
        sentence="이 제품은 피부에 완벽한 효과를 보장합니다.",
        violation_type=ViolationType.type_5_deception,
        span="완벽한",
    )
    assert "우수한 효과" in suggestions
    assert "만족스러운 사용감" in suggestions


def test_remediation_fallback_when_no_keyword_match():
    """매칭되는 키워드가 없을 때 violation_type의 fallback으로 복귀하는지 검증."""
    suggestions, _ = get_remediation(
        sentence="알 수 없는 무작위 문구",
        violation_type=ViolationType.type_1_drug_misperception,
    )
    assert "일반 보습 및 피부 장벽 강화" in suggestions
    assert "피부 보호" in suggestions


def test_remediation_accepts_string_violation_type():
    """violation_type이 문자열로 들어와도 올바르게 매칭되는지 검증."""
    suggestions, _ = get_remediation(
        sentence="자외선차단 완료 선크림",
        violation_type="2호_기능성오인",
    )
    assert "자외선으로부터 피부 보호" in suggestions
