"""규칙집 키워드가 팩 근거를 갖는지 지키는 회귀 테스트.

판정 근거를 사용자에게 보여주려면 그 근거가 팩 원문에 실제로 있어야 한다.
근거 없는 키워드가 규칙집에 새로 들어오는 걸 여기서 막는다.
"""

from scripts.rule_evidence_audit import audit, find_evidence

# 2026-08-23 시점에 근거 문자열이 안 잡히는 키워드. **이걸 늘리지 않는 게 목적이다.**
# 셋 다 성격이 달라 조치가 다르다(PM 판단 대기).
#   - 표기 차이(팩이 실제로 덮음): 콜라겐증가·콜라겐활성화("콜라겐·효소 증가·감소·활성화"),
#     가려움개선("가려움 완화·개선·해결"), 시험완료("시험·검사 표현 예: 피부과 테스트 완료")
#   - 부분 확장(팩은 "약국·병원 전용/입점"까지만): 약국판매·약국납품
#   - 근거 없음: 유일
_KNOWN_UNGROUNDED = {
    "콜라겐증가",
    "콜라겐활성화",
    "가려움개선",
    "시험완료",
    "약국판매",
    "약국납품",
    "유일",
}


def test_no_new_ungrounded_keywords():
    """규칙집에 팩 근거 없는 키워드가 새로 들어오면 실패한다."""
    missing = {m["keyword"] for m in audit()["missing"]}
    new = missing - _KNOWN_UNGROUNDED
    assert not new, (
        f"팩에 근거가 없는 규칙 키워드가 새로 들어왔다: {sorted(new)}. "
        "팩 원문을 확인하고, 근거가 없으면 규칙에 넣지 않는다."
    )


def test_known_list_does_not_go_stale():
    """근거가 생긴 키워드는 목록에서 빼라고 알린다(목록이 낡는 걸 막는다)."""
    missing = {m["keyword"] for m in audit()["missing"]}
    fixed = _KNOWN_UNGROUNDED - missing
    assert not fixed, f"근거가 생겼다. _KNOWN_UNGROUNDED에서 빼라: {sorted(fixed)}"


def test_majority_of_rules_are_grounded():
    """대다수 규칙은 근거가 확인돼야 한다(감사 자체가 망가진 걸 잡는 안전장치)."""
    result = audit()
    assert result["total"] > 90
    assert len(result["missing"]) / result["total"] < 0.15


def test_find_evidence_matches_normalized_form():
    """공백·가운뎃점이 섞인 팩 표기와도 대조된다."""
    index = [("샘플 절", "세포유전자dna활성화")]
    assert find_evidence("세포 유전자(DNA) 활성화", index) == "샘플 절"
    assert find_evidence("발모", index) is None
