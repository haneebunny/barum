"""위반 문구 치환 조립(generate.replace) 유닛테스트 (순수 — 조건표 재사용).

get_remediation은 remediation_rules.json을 읽는 결정적 로직이라 VLM 없이 테스트한다.

    ./venv/bin/python -m pytest tests/test_generate_replace.py -q
"""

from barum.generate.replace import _BASIS_LLM, apply_replacements, build_replacements
from barum.judge.cosmetic import _rule_explanation
from barum.reference.rules import RuleOutcome, match_rule
from barum.models import (
    Finding,
    JudgmentFlag,
    Location,
    Replacement,
    ViolationType,
)


def _finding(span, sentence, vtype, flag=JudgmentFlag.violation):
    return Finding(
        span=span,
        sentence=sentence,
        violation_type=vtype,
        legal_basis="화장품법 제13조",
        flag=flag,
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


class _FakeRewriter:
    """대체표현 다듬기용 가짜 LLM. 호출 인자를 기록해 프롬프트 구성도 검증한다."""

    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []

    def generate_json(self, prompt, images):
        self.prompts.append(prompt)
        return self.payload


def test_llm_rewrite_drops_suggestion_when_nothing_can_be_suggested():
    """대체할 수 없는 문구에는 제안을 아예 안 낸다.

    2026-08-20 팀장 지시: "제안할 수 없는 표현은 제안도 하지 마라."
    도도3 실측에서 '전국 약국 오프라인매장 입점!'(유통 채널 안내)에 5호 fallback
    '우수한 효과'가 붙었다. 원문은 어디서 파는지인데 제안은 효능 주장이라,
    근거 없는 효과 주장을 새로 넣으라고 권하는 셈이었다.
    """
    rewriter = _FakeRewriter({"items": [{"index": 0, "can_suggest": False, "reason": "유통 채널 안내라 대체할 효능 표현이 없다"}]})
    findings = [
        _finding("전국 약국 오프라인매장 입점!", "전국 약국 오프라인매장 입점!", ViolationType.type_5_deception)
    ]
    reps = build_replacements(findings, rewriter=rewriter)
    assert reps == [], f"제안이 없어야 하는데 {reps}가 나왔다"


def test_llm_rewrite_uses_natural_sentence_when_it_can():
    """대체 가능하면 LLM이 다듬은 자연스러운 표현을 쓴다."""
    rewriter = _FakeRewriter(
        {"items": [{"index": 0, "can_suggest": True, "suggestion": "피부를 보호하는 성분이 함유된 세럼"}]}
    )
    findings = [
        _finding("치료", "상처를 치료하는 연고의 주성분이 함유된 세럼", ViolationType.type_1_drug_misperception)
    ]
    reps = build_replacements(findings, rewriter=rewriter)
    assert len(reps) == 1
    assert reps[0].replaced == "피부를 보호하는 성분이 함유된 세럼"


def test_llm_rewrite_is_rejected_when_it_produces_a_violation():
    """LLM이 낸 문구도 규칙집을 다시 통과해야 한다. 위반이면 제안하지 않는다.

    조건표에서 배운 것과 같은 함정이다. 만드는 쪽이 누구든 검증 없이 내보내면
    위반 문구를 위반 문구로 바꿔주게 된다.
    """
    rewriter = _FakeRewriter(
        {"items": [{"index": 0, "can_suggest": True, "suggestion": "줄기세포 배양액 함유"}]}
    )
    findings = [_finding("줄기세포", "줄기세포 배양액 세럼", ViolationType.type_5_deception)]
    reps = build_replacements(findings, rewriter=rewriter)
    # **버리지 않고 조건표 후보로 폴백한다(2026-08-23).** 예전엔 제안 자체를 없앴는데,
    # improve 모드에선 그게 곧 "원문 위반이 그대로 남는다"였다. 위반 문구가 안 나가는
    # 것이 핵심이고, 안전한 대안이 있으면 주는 게 낫다.
    assert len(reps) == 1
    assert "줄기세포" not in reps[0].replaced, "LLM이 낸 위반 문구가 그대로 나갔다"
    assert reps[0].basis != _BASIS_LLM, "조건표 폴백이어야 한다"


def test_llm_failure_falls_back_to_condition_table():
    """LLM 호출이 실패하면 조건표 결과로 돌아간다. 과금 호출이라 재시도는 안 한다."""

    class _BrokenRewriter:
        def generate_json(self, prompt, images):
            raise RuntimeError("API 죽음")

    findings = [_finding("완벽한", "완벽한 효과를 보장합니다", ViolationType.type_5_deception)]
    reps = build_replacements(findings, rewriter=_BrokenRewriter())
    assert len(reps) == 1
    assert reps[0].replaced == "우수한 효과"  # 조건표 1순위


def test_replacement_carries_evidence_note_for_needs_review_suggestion():
    """검토필요로 걸리는 대체표현에는 실증자료가 필요하다고 알린다.

    2026-08-20 팀장 지시. 안 붙이면 사용자는 위반에서 벗어난 줄 알고 그대로 쓴다.
    """
    # 게이트가 검토필요 제안을 막게 된 뒤(2026-08-23)로는 LLM 경로에서 이 상황이
    # 안 생긴다. 고지 판단은 원래도 "다시 쓴 결과"가 아니라 **원본 finding의 flag**
    # 기준이므로(`_note_for` docstring), 원본이 검토필요인 경우로 검사한다.
    rewriter = _FakeRewriter(
        {"items": [{"index": 0, "can_suggest": True, "suggestion": "자극을 줄여줍니다"}]}
    )
    findings = [
        _finding(
            "진정",
            "피부 진정에 도움을 줍니다",
            ViolationType.type_1_drug_misperception,
            flag=JudgmentFlag.needs_review,
        )
    ]
    reps = build_replacements(findings, rewriter=rewriter)
    assert len(reps) == 1
    assert reps[0].note, "실증자료 고지가 비어 있다"
    assert "실증" in reps[0].note


def test_evidence_number_is_kept_and_user_is_asked_for_substantiation():
    """실증 수치는 빼지 않고, 실증자료를 넣으라고 권한다.

    2026-08-20 팀장 지시: "그런건 사용자에게 실증자료를 넣으라고 권하자."
    LLM이 '콜라겐 밀도 38% 증가'에서 38%를 통째로 빼버렸다. 안전하긴 한데
    광고주에게는 그 숫자가 핵심이고, 실증자료가 있으면 쓸 수 있는 값이다.
    지우는 게 아니라 자료를 붙이라고 안내하는 게 맞다.
    """
    rewriter = _FakeRewriter(
        {"items": [{"index": 0, "can_suggest": True, "suggestion": "4주 사용 시 콜라겐 밀도 38% 증가 (인체적용시험 결과)"}]}
    )
    findings = [
        _finding(
            "콜라겐 밀도 38% 증가 (4주 사용시)",
            "임상 시험 결과 4주 사용 시 콜라겐 밀도 38% 증가.",
            ViolationType.type_1_drug_misperception,
        )
    ]
    reps = build_replacements(findings, rewriter=rewriter)
    assert len(reps) == 1
    assert "38%" in reps[0].replaced, "실증 수치가 사라졌다"
    assert reps[0].note and "실증자료" in reps[0].note


def test_prompt_tells_llm_to_keep_numbers():
    """프롬프트가 LLM에게 수치를 지우지 말라고 지시하는지."""
    rewriter = _FakeRewriter({"items": []})
    findings = [_finding("38% 증가", "콜라겐 밀도 38% 증가", ViolationType.type_1_drug_misperception)]
    build_replacements(findings, rewriter=rewriter)
    prompt = rewriter.prompts[0]
    assert "수치" in prompt and "지우지" in prompt


def test_llm_rewrite_applied_to_content_does_not_corrupt_the_sentence():
    """다시 쓴 문장을 실제로 적용했을 때 원문이 깨지지 않는다.

    2026-08-20 도도3 리뷰에서 잡힌 버그. LLM은 문장 전체를 다시 쓰는데
    `Replacement.original`이 span(단어 하나)으로 남아 있어서, 치환하면 단어 자리에
    문장이 통째로 박혔다.

        전: 피부 깊숙이, 세포재생의 시작
        후: 피부 깊숙이, 세포피부에 생기를 더해 ... 줍니다의 시작

    **고치려던 문제를 더 심하게 만든 상태였다.** build_replacements 출력만 보는
    테스트로는 안 잡힌다. apply_replacements까지 태워야 드러난다.
    """
    rewriter = _FakeRewriter(
        {"items": [{"index": 0, "can_suggest": True, "suggestion": "피부에 생기를 더해 건강해 보이는 피부로 가꿔 줍니다"}]}
    )
    content = "피부 깊숙이, 세포재생의 시작"
    findings = [_finding("재생", content, ViolationType.type_1_drug_misperception)]
    reps = build_replacements(findings, rewriter=rewriter)
    out = apply_replacements(content, reps)

    assert out == "피부에 생기를 더해 건강해 보이는 피부로 가꿔 줍니다", f"문장이 깨졌다: {out!r}"
    assert "세포피부에" not in out


def test_condition_table_path_still_replaces_only_the_span():
    """조건표 경로는 기존대로 span만 갈아끼운다(하위호환)."""
    content = "아토피 완화에 좋은 순한 크림"
    findings = [_finding("아토피", content, ViolationType.type_1_drug_misperception)]
    reps = build_replacements(findings)  # rewriter 없음
    assert reps[0].original == "아토피"
    out = apply_replacements(content, reps)
    assert out.endswith("완화에 좋은 순한 크림")


def test_needs_review_note_uses_original_finding_flag_not_rematch():
    """실증 고지는 원본 finding의 flag를 기준으로 붙인다. 재매칭 결과가 아니다.

    2026-08-20 도도3 리뷰: '콜라겐 밀도 38% 증가' 규칙 키워드는 붙여쓰기
    '콜라겐증가'라서, 다시 쓴 문장을 규칙에 재매칭하면 미매칭으로 걸려 고지가
    안 붙었다. 그 문장이 검토필요였던 건 규칙이 아니라 VLM이 잡은 것이었다.
    규칙 표현과 안 맞는 원본은 전부 이 구멍에 걸린다. 원본 finding.flag를
    신뢰하는 게 맞다. 판정기가 이미 검토필요라고 봤으면 그 판정을 따른다.
    """
    # 숫자가 없는 문장으로 잡는다. 숫자 검사(_NUMBER_PATTERN)가 우연히 커버해
    # 버그를 가리는 걸 피하려는 것이다. flag 자체를 봐야 잡히는 경우만 남긴다.
    rewriter = _FakeRewriter(
        {"items": [{"index": 0, "can_suggest": True, "suggestion": "피부 결 정돈에 도움을 주는 성분이 함유된 세럼"}]}
    )
    f = Finding(
        span="세럼",
        sentence="피부 결 정돈 효과가 있는 세럼",
        violation_type=ViolationType.type_1_drug_misperception,
        legal_basis="화장품법 제13조",
        flag=JudgmentFlag.needs_review,  # VLM이 검토필요로 판정 (규칙 매칭 아님)
        explanation="테스트",
        location=Location(order=0),
    )
    reps = build_replacements([f], rewriter=rewriter)
    assert len(reps) == 1
    assert reps[0].note, "원본이 검토필요인데 고지가 안 붙었다"


# ── 판정 설명을 LLM 문장으로 갈아끼우기 (2026-08-20 팀장 지시) ────────────────

def _rule_finding(span, sentence, vtype, flag=JudgmentFlag.violation):
    """규칙 경로가 만든 finding(설명이 고정 템플릿이고 source='rule')."""
    return Finding(
        span=span, sentence=sentence, violation_type=vtype,
        legal_basis="화장품법 제13조", flag=flag,
        explanation=_rule_explanation(RuleOutcome.violation, span, vtype),
        location=Location(order=0), source="rule",
    )


def test_규칙_경로_설명이_llm_문장으로_바뀐다():
    f = _rule_finding("줄기세포", "줄기세포 배양 기술 안티에이징",
                      ViolationType.type_5_deception)
    rewriter = _FakeRewriter({"items": [{
        "index": 0, "can_suggest": True, "suggestion": "최신 기술로 완성한 세럼",
        "explanation": "줄기세포는 인체 유래 성분을 연상시켜 화장품 범위를 벗어난 표현으로 봅니다.",
    }]})

    build_replacements([f], rewriter=rewriter, explain=True)

    assert not f.explanation.startswith("규칙문서 대조:")
    assert "인체 유래" in f.explanation


def test_vlm_경로_설명은_안_건드린다():
    """모델이 이미 직접 쓴 설명이다. 덮어쓰면 2호 성분 대조 안내 같은 걸 잃는다."""
    f = Finding(
        span="미백 기능성", sentence="미백 기능성", violation_type=ViolationType.type_2_functional_misperception,
        legal_basis="화장품법 제13조", flag=JudgmentFlag.needs_review,
        explanation="기능성 표방 (전성분 대조: 나이아신아마이드 확인됨, 기준 2~5%)",
        location=Location(order=0), source="vlm",
    )
    rewriter = _FakeRewriter({"items": [{
        "index": 0, "can_suggest": True, "suggestion": "피부 톤 케어",
        "explanation": "엉뚱한 설명으로 덮어쓰면 안 된다",
    }]})

    build_replacements([f], rewriter=rewriter, explain=True)

    assert "전성분 대조" in f.explanation


def test_llm이_설명을_못_내면_템플릿을_유지한다():
    """리포트가 빈 설명으로 나가면 안 된다(팀장·PM 지시)."""
    f = _rule_finding("재생", "세포재생의 시작", ViolationType.type_1_drug_misperception)
    before = f.explanation

    class _Broken:
        def generate_json(self, prompt, images):
            raise RuntimeError("LLM 호출 실패")

    # 호출 자체가 깨진 경우
    build_replacements([f], rewriter=_Broken(), explain=True)
    assert f.explanation == before

    # 응답은 왔는데 설명이 비었거나 너무 짧은 경우
    rewriter = _FakeRewriter({"items": [{"index": 0, "can_suggest": True,
                                         "suggestion": "생기 부여", "explanation": "위반임"}]})
    build_replacements([f], rewriter=rewriter, explain=True)
    assert f.explanation == before


def test_대체표현을_못_내도_설명은_받는다():
    """제품명·유통 채널은 바꿀 수 없지만 왜 걸렸는지는 알려줘야 한다."""
    f = _rule_finding("약국", "전국 약국 오프라인매장 입점!", ViolationType.type_5_deception)
    rewriter = _FakeRewriter({"items": [{
        "index": 0, "can_suggest": False,
        "explanation": "약국 판매를 내세우면 의약품처럼 오인될 수 있어 제한됩니다.",
    }]})

    reps = build_replacements([f], rewriter=rewriter, explain=True)

    assert reps == []  # 대체표현은 안 만든다
    assert "의약품처럼" in f.explanation  # 설명은 갱신된다


def test_explain을_안_켜면_설명이_그대로다():
    """개선 모드(/generate)는 설명을 안 바꾼다. 리포트 경로만 켠다."""
    f = _rule_finding("재생", "세포재생의 시작", ViolationType.type_1_drug_misperception)
    before = f.explanation
    rewriter = _FakeRewriter({"items": [{"index": 0, "can_suggest": True, "suggestion": "생기 부여",
                                         "explanation": "충분히 긴 설명 문장입니다 여기에."}]})

    build_replacements([f], rewriter=rewriter)

    assert f.explanation == before


# ── 치환 단위가 섞일 때 순서 (2026-08-23) ──────────────────────────────────

def test_긴_치환을_먼저_적용한다():
    """**위반어가 결과에 남던 버그다.**

    LLM 경로는 문장 전체를, 조건표 경로는 단어를 original로 쓴다. 짧은 단어를 먼저
    치환하면 그 단어를 품고 있던 긴 문장이 원문에서 사라져 문장 단위 치환이 조용히
    무시되고, 그 문장이 담고 있던 다른 위반어가 결과에 그대로 남는다.
    한 문장에 위반이 여러 개면 반드시 이 상황이 된다.
    """
    from barum.generate.replace import apply_replacements
    from barum.models import Replacement, ViolationType

    line = "줄기세포 배양 기술 세포재생의 시작 진피층까지 침투하여"
    reps = [
        # 단어 단위(조건표)가 앞에, 문장 단위(LLM)가 뒤에 오는 배치
        Replacement(original="세포재생", replaced="피부 생기 부여",
                    violation_type=ViolationType.type_1_drug_misperception, basis="조건표"),
        Replacement(original=line, replaced="피부 보호에 도움을 주는 포뮬러",
                    violation_type=ViolationType.type_1_drug_misperception, basis="LLM"),
    ]
    out = apply_replacements(line, reps)
    assert not any(w in out for w in ("줄기세포", "세포재생", "진피층")), f"위반어가 남았다: {out}"


def test_결과에_안_실린_대체표현을_알려준다():
    from barum.generate.replace import unapplied_originals
    from barum.models import Replacement, ViolationType

    def rep(original, replaced):
        return Replacement(original=original, replaced=replaced,
                           violation_type=ViolationType.type_1_drug_misperception, basis="x")

    final = "피부 보호에 도움을 주는 포뮬러"
    assert unapplied_originals(final, [rep("진피층", final)]) == []
    # 대상이 아예 없던 경우(낡은 리포트)
    assert unapplied_originals(final, [rep("없는 문장", "산뜻한 제형")]) == ["산뜻한 제형"]


# ── 대체표현 생성 분할 (2026-08-23) ────────────────────────────────────────

def test_기본은_한_호출로_전부_묶는다():
    """**기본은 한 호출로 전부**다(2026-08-25 정확성 우선). 겹칠 대체문구가 서로를
    봐야 프롬프트의 anti-repeat가 작동해 같은 문구 반복이 안 나온다. 예전엔 지연
    최적화로 1건씩 쪼갰는데, 그러면 각 호출이 다른 문구를 못 봐서 "피부 생기 부여"가
    여러 finding에 중복됐다. REPLACEMENT_BATCH_SIZE를 주면 예전처럼 쪼갠다.
    """
    from barum.generate.replace import build_replacements

    class CountingRewriter:
        calls = 0

        def generate_json(self, prompt, images):
            CountingRewriter.calls += 1
            return {"items": []}

    findings = [
        _finding(span, f"{span} 표현이 든 문장", ViolationType.type_1_drug_misperception)
        for span in ("아토피", "여드름", "건선", "치료")
    ]
    build_replacements(findings, rewriter=CountingRewriter())
    assert CountingRewriter.calls == 1, "기본은 한 호출로 전부 묶는다(anti-repeat 작동)"


def test_배치_크기를_키우면_호출이_준다(monkeypatch):
    from barum.generate.replace import build_replacements

    class CountingRewriter:
        calls = 0

        def generate_json(self, prompt, images):
            CountingRewriter.calls += 1
            return {"items": []}

    monkeypatch.setenv("REPLACEMENT_BATCH_SIZE", "10")
    findings = [
        _finding(span, f"{span} 표현이 든 문장", ViolationType.type_1_drug_misperception)
        for span in ("아토피", "여드름", "건선", "치료")
    ]
    build_replacements(findings, rewriter=CountingRewriter())
    assert CountingRewriter.calls == 1


def test_쪼갤_때_한_조각이_실패해도_나머지는_산다(monkeypatch):
    """REPLACEMENT_BATCH_SIZE로 쪼개 병렬로 돌릴 때, 호출 하나가 실패해도 그 조각만
    조건표로 떨어지고 나머지는 산다(전엔 전부 떨어졌다). 기본은 한 호출이라 이
    resilience는 쪼갤 때의 계약이므로 env로 분할을 켜고 확인한다.
    """
    from barum.generate.replace import build_replacements

    monkeypatch.setenv("REPLACEMENT_BATCH_SIZE", "1")

    class FlakyRewriter:
        calls = 0

        def generate_json(self, prompt, images):
            FlakyRewriter.calls += 1
            if FlakyRewriter.calls == 1:
                raise RuntimeError("첫 조각 실패")
            return {
                "items": [
                    {"index": i, "can_suggest": True, "suggestion": "산뜻하게 발리는 제형"}
                    for i in range(10)
                ]
            }

    findings = [
        _finding(span, f"{span} 표현이 든 문장", ViolationType.type_1_drug_misperception)
        for span in ("아토피", "여드름", "건선")
    ]
    reps = build_replacements(findings, rewriter=FlakyRewriter())
    assert any(r.basis == _BASIS_LLM for r in reps), "성공한 조각이 살아야 한다"


def test_같은_대체문구는_다른_안전후보로_분리된다(monkeypatch):
    """서로 다른 위반이 같은 첫 후보로 완화되면 뒤엣것을 다른 안전 후보로 갈아끼운다.

    2026-08-25 실측: "미백 효과"·"피부 재생"이 둘 다 "피부 생기 부여"로 완화돼
    improve 상세페이지에 같은 제목 카드가 두 장 나왔다. 코드가 결정적으로 분리한다.
    """
    import barum.generate.replace as mod

    def _fake_remediation(sentence, violation_type, span=None):
        # 두 finding 모두 같은 첫 후보 + 서로 다른 둘째 안전 후보를 준다.
        return ["피부 생기 부여", "촉촉함을 더하는 케어"], "면책"

    monkeypatch.setattr(mod, "get_remediation", _fake_remediation)

    findings = [
        _finding("미백 효과", "미백 효과가 뛰어난 크림", ViolationType.type_5_deception),
        _finding("피부 재생", "피부 재생을 돕는 크림", ViolationType.type_5_deception),
    ]
    reps = build_replacements(findings)  # 조건표 경로(rewriter 없음)

    assert len(reps) == 2
    assert len({r.replaced for r in reps}) == 2, "같은 대체문구 두 장이 남으면 안 된다"


def test_대체후보가_하나뿐이면_중복을_유지한다(monkeypatch):
    """분리할 다른 안전 후보가 없으면 억지로 지어내지 않고 그대로 둔다(로그만).

    없는 표현을 만들면 근거 없는 문구가 되므로, 마지막 수단으로 중복을 허용한다.
    """
    import barum.generate.replace as mod

    def _fake_remediation(sentence, violation_type, span=None):
        return ["유일한 안전 표현"], "면책"

    monkeypatch.setattr(mod, "get_remediation", _fake_remediation)

    findings = [
        _finding("미백 효과", "미백 효과가 뛰어난 크림", ViolationType.type_5_deception),
        _finding("피부 재생", "피부 재생을 돕는 크림", ViolationType.type_5_deception),
    ]
    reps = build_replacements(findings)

    assert len(reps) == 2
    assert all(r.replaced == "유일한 안전 표현" for r in reps)
