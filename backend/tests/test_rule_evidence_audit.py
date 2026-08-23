"""규칙집 키워드가 팩 근거를 갖는지 지키는 회귀 테스트.

판정 근거를 사용자에게 보여주려면 그 근거가 팩 원문에 실제로 있어야 한다.
근거 없는 키워드가 규칙집에 새로 들어오는 걸 여기서 막는다.
"""

from scripts.rule_evidence_audit import audit, find_evidence

# 근거를 못 찾은 키워드. **비어 있는 게 정상이고, 이 목록을 늘리지 않는 게 목적이다.**
# 2026-08-23 기준 0건 — 95건은 팩 원문 문자열 대조, 8건은 큐레이션 매핑으로 해소했다.
_KNOWN_UNGROUNDED: set[str] = set()


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
    """감사 자체가 망가진 걸 잡는 안전장치."""
    result = audit()
    assert result["total"] > 90
    assert len(result["missing"]) / result["total"] < 0.15


def test_큐레이션_매핑은_실제_팩_파일을_가리킨다():
    """사람이 손으로 적은 위치라 오타·삭제가 그대로 남는다. 파일 존재만이라도 지킨다."""
    from scripts.rule_evidence_audit import _CURATED_EVIDENCE, _REF_DIR

    for keyword, (where, note) in _CURATED_EVIDENCE.items():
        rel = where.split(":")[0]
        assert (_REF_DIR / rel).exists(), f"{keyword}의 근거 파일이 없다: {rel}"
        assert note, f"{keyword}에 판단 이유가 안 적혀 있다"


def test_큐레이션_매핑은_규칙집에_있는_키워드만_담는다():
    """규칙에서 뺀 키워드가 매핑에 남아 있으면 근거가 있는 것처럼 보인다."""
    import json

    from scripts.rule_evidence_audit import _CURATED_EVIDENCE, _RULES_PATH

    rules = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    live = {
        kw
        for bucket in ("violation", "needs_review")
        for kws in rules.get(bucket, {}).values()
        for kw in kws
    }
    stale = set(_CURATED_EVIDENCE) - live
    assert not stale, f"규칙집에 없는 키워드가 매핑에 남아 있다: {sorted(stale)}"


def test_find_evidence_matches_normalized_form():
    """공백·가운뎃점이 섞인 팩 표기와도 대조된다."""
    index = [("샘플 절", "세포유전자dna활성화")]
    assert find_evidence("세포 유전자(DNA) 활성화", index) == "샘플 절"
    assert find_evidence("발모", index) is None
