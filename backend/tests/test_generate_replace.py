"""위반 문구 치환 조립(generate.replace) 유닛테스트 (순수 — 조건표 재사용).

get_remediation은 remediation_rules.json을 읽는 결정적 로직이라 VLM 없이 테스트한다.

    ./venv/bin/python -m pytest tests/test_generate_replace.py -q
"""

from barum.generate.replace import apply_replacements, build_replacements
from barum.models import (
    Finding,
    JudgmentFlag,
    Location,
    Replacement,
    ViolationType,
)


def _finding(span, sentence, vtype):
    return Finding(
        span=span,
        sentence=sentence,
        violation_type=vtype,
        legal_basis="화장품법 제13조",
        flag=JudgmentFlag.violation,
        explanation="테스트",
        location=Location(order=0),
    )


def test_build_replacements_from_remediation_table():
    """위반 finding마다 조건표에서 안전표현을 뽑아 Replacement를 만든다."""
    findings = [
        _finding("아토피 완화", "아토피 완화에 좋은 크림", ViolationType.type_1_drug_misperception)
    ]
    reps = build_replacements(findings)
    assert len(reps) == 1
    assert reps[0].original == "아토피 완화"
    assert reps[0].replaced  # 조건표에서 나온 비어있지 않은 대체표현
    assert reps[0].violation_type == ViolationType.type_1_drug_misperception
    assert reps[0].basis  # 근거 문구 채워짐


def test_apply_replacements_rewrites_content():
    """원문에서 위반 표현을 안전표현으로 치환한다."""
    reps = [
        Replacement(
            original="아토피 완화",
            replaced="건조함으로 인한 가려움 완화",
            violation_type=ViolationType.type_1_drug_misperception,
            basis="조건표",
        )
    ]
    out = apply_replacements("아토피 완화에 좋은 순한 크림", reps)
    assert "아토피 완화" not in out
    assert "건조함으로 인한 가려움 완화" in out


def test_apply_replacements_empty_leaves_content():
    assert apply_replacements("촉촉한 크림", []) == "촉촉한 크림"
