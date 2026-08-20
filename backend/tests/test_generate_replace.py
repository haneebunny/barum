"""위반 문구 치환 조립(generate.replace) 유닛테스트 (순수 — 조건표 재사용).

get_remediation은 remediation_rules.json을 읽는 결정적 로직이라 VLM 없이 테스트한다.

    ./venv/bin/python -m pytest tests/test_generate_replace.py -q
"""

from barum.generate.replace import apply_replacements, build_replacements
from barum.reference.rules import RuleOutcome, match_rule
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


def test_build_replacements_never_emits_a_violating_suggestion(monkeypatch):
    """조건표가 위반 표현을 제안해도 그대로 내보내지 않는다.

    2026-08-20 실사고: 조건표 5호 규칙이 '줄기세포'를 잡아서 '줄기세포 배양액 함유'를
    대체표현으로 내놨다. 위반 키워드가 제안 안에 그대로 들어 있었는데 아무도 안 걸렀다.
    조건표는 손으로 쓰는 JSON이라 같은 실수가 또 난다. 코드가 막아야 한다.
    """
    import barum.generate.replace as mod

    def _fake_remediation(sentence, violation_type, span=None):
        # 첫 후보가 위반, 두 번째가 안전한 조건표를 흉내낸다.
        return ["줄기세포 배양액 함유", "만족스러운 사용감"], "면책"

    monkeypatch.setattr(mod, "get_remediation", _fake_remediation)

    findings = [
        _finding("줄기세포", "줄기세포 배양액으로 피부가 재생됩니다", ViolationType.type_5_deception)
    ]
    reps = build_replacements(findings)

    assert len(reps) == 1
    m = match_rule(reps[0].replaced)
    assert m is None or m.outcome is not RuleOutcome.violation, (
        f"대체표현 {reps[0].replaced!r}이 규칙집에서 위반으로 걸린다"
    )


def test_remediation_table_has_no_violating_suggestion():
    """조건표에 실린 모든 대체표현이 규칙집에서 위반으로 안 걸린다(데이터 회귀 감시).

    새 규칙을 조건표에 추가할 때 여기서 걸린다. API 비용 0.
    """
    import json
    from pathlib import Path
    from barum.reference.remediation import DATA_PATH

    data = json.loads(Path(DATA_PATH).read_text(encoding="utf-8"))
    suggestions = [s for r in data["rules"] for s in r["suggestions"]]
    suggestions += [s for sugs in data["fallbacks"].values() for s in sugs]

    offenders = []
    for s in suggestions:
        m = match_rule(s)
        if m is not None and m.outcome is RuleOutcome.violation:
            offenders.append(s)

    assert not offenders, f"조건표가 위반 표현을 대체표현으로 싣고 있다: {offenders}"


def test_build_replacements_prefers_a_clean_suggestion_over_needs_review(monkeypatch):
    """후보가 여럿이면 규칙에 안 걸리는 쪽을 검토필요보다 먼저 고른다.

    2026-08-20 도도3 리뷰: 조건표 5건에서 1순위가 검토필요인데 그 뒤에 깨끗한 후보가
    있었다(`피부 진정` 뒤의 `자극 완화` 등). 위반만 거르면 뒤에 있는 더 안전한 표현을
    두고도 검토필요를 내보낸다. 검토필요를 막지는 않는다. 팩이 §3 실증대상으로 명시한
    표현이라 금지하면 팩이 허용한 것을 우리가 막는 셈이 된다. 순서만 바꾼다.
    """
    import barum.generate.replace as mod

    def _fake_remediation(sentence, violation_type, span=None):
        # 1순위는 검토필요, 2순위는 규칙에 안 걸리는 표현.
        return ["피부 진정", "자극 완화"], "면책"

    monkeypatch.setattr(mod, "get_remediation", _fake_remediation)

    findings = [
        _finding("염증", "염증을 가라앉힙니다", ViolationType.type_1_drug_misperception)
    ]
    reps = build_replacements(findings)

    assert len(reps) == 1
    assert reps[0].replaced == "자극 완화", (
        f"검토필요인 1순위 대신 깨끗한 후보를 골라야 하는데 {reps[0].replaced!r}가 나왔다"
    )


def test_build_replacements_falls_back_to_needs_review_when_nothing_cleaner(monkeypatch):
    """깨끗한 후보가 없으면 검토필요라도 쓴다(막지 않는다)."""
    import barum.generate.replace as mod

    def _fake_remediation(sentence, violation_type, span=None):
        return ["피부 진정"], "면책"

    monkeypatch.setattr(mod, "get_remediation", _fake_remediation)

    findings = [
        _finding("염증", "염증을 가라앉힙니다", ViolationType.type_1_drug_misperception)
    ]
    reps = build_replacements(findings)

    assert len(reps) == 1
    assert reps[0].replaced == "피부 진정"
