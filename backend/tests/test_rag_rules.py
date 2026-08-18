"""RagJudge 규칙 매칭(reference.rules) 유닛테스트.

순수 로직(문장 → 규칙 판정)만 테스트한다. VLM 호출 없음.

    ./venv/bin/python -m pytest tests/test_rag_rules.py -q
"""

from barum.models import JudgmentFlag, ViolationType
from barum.reference.rules import RuleOutcome, match_rule


def test_disease_keyword_is_violation():
    """질병명(아토피)은 실증 무관 명백한 1호 위반."""
    m = match_rule("아토피 피부에 도움을 주는 크림")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.violation_type == ViolationType.type_1_drug_misperception
    assert m.flag == JudgmentFlag.violation
    assert m.span == "아토피"


def test_soothing_alone_is_needs_review():
    """진정(단독)은 실증대상 — 위반 단정 말고 검토필요."""
    m = match_rule("피부를 진정시켜 편안하게 가꿔 줍니다")
    assert m is not None
    assert m.outcome == RuleOutcome.needs_review
    assert m.violation_type == ViolationType.type_1_drug_misperception
    assert m.flag == JudgmentFlag.needs_review
    assert m.span == "진정"


def test_elasticity_alone_is_legal_allow():
    """탄력(단독)은 일반화장품도 쓰는 일반 표현 — 합법 확정, finding 없음."""
    m = match_rule("피부에 탄력을 더해 주는 성분 함유")
    assert m is not None
    assert m.outcome == RuleOutcome.legal_allow
    assert m.violation_type is None
    assert m.flag is None


def test_no_match_returns_none():
    """규칙에 안 걸리는 일반 문장은 None(VLM에 위임)."""
    assert match_rule("촉촉하고 산뜻한 사용감의 데일리 로션") is None


def test_antiaging_with_elasticity_is_needs_review_not_legal():
    """'안티에이징 탄력크림'처럼 안티에이징과 탄력이 함께면 검토필요로 올라간다.

    탄력 단독은 합법이지만 안티에이징(=피부노화 관련)과 묶이면 실증대상이다
    (type_1_drug_misperception.md 27줄). 우선순위 스캔(needs_review > legal_allow)이
    이걸 의도대로 처리하는지 못박는다.
    """
    m = match_rule("안티에이징 탄력크림")
    assert m is not None
    assert m.outcome == RuleOutcome.needs_review
    assert m.span == "안티에이징"


def test_procedure_context_makes_soothing_violation():
    """'시술 후 진정'은 진정 단독과 달리 위반 — 시술이 먼저 hit한다.

    진정은 실증대상(검토필요)이나 '시술'이 의료맥락이라 위반이다(§3 ④ 경계).
    우선순위 스캔(violation > needs_review)으로 시술이 진정보다 먼저 걸린다.
    """
    m = match_rule("시술 후 예민해진 피부를 진정")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "시술"


def test_normalization_matches_across_spaces():
    """공백으로 갈라진 표현도 정규화로 매칭한다('다크 서클' → '다크서클')."""
    m = match_rule("다크 서클 완화에 도움")
    assert m is not None
    assert m.span == "다크서클"
    assert m.outcome == RuleOutcome.needs_review


# ── 동의어 매칭 테스트 ──────────────────────────────────────────────────


def test_synonym_detox_maps_to_haedok():
    """'디톡스'는 대표어 '해독'의 동의어 — violation hit."""
    m = match_rule("피부 디톡스로 깨끗하게")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "해독"
    assert m.violation_type == ViolationType.type_1_drug_misperception


def test_synonym_trouble_maps_to_acne():
    """'트러블'은 대표어 '여드름'의 동의어 — violation hit."""
    m = match_rule("트러블 피부를 위한 솔루션")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "여드름"


def test_synonym_healing_maps_to_treatment():
    """'힐링'은 대표어 '치료'의 동의어 — violation hit."""
    m = match_rule("힐링 케어로 피부를 관리")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "치료"


def test_synonym_antiaging_english_maps_to_needs_review():
    """'anti-aging'(영문)은 대표어 '안티에이징'의 동의어 — needs_review."""
    m = match_rule("anti-aging 크림으로 관리하세요")
    assert m is not None
    assert m.outcome == RuleOutcome.needs_review
    assert m.span == "안티에이징"


def test_synonym_sebum_control_maps_to_piji():
    """'피지 조절'은 대표어 '피지분비조절'의 동의어 — needs_review."""
    m = match_rule("피지 조절에 효과적인 성분")
    assert m is not None
    assert m.outcome == RuleOutcome.needs_review
    assert m.span == "피지분비조절"


def test_synonym_stemcell_maps_to_violation():
    """'stem cell'(영문)은 대표어 '줄기세포'의 동의어 — 5호 violation."""
    m = match_rule("stem cell 기술을 적용한 크림")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "줄기세포"
    assert m.violation_type == ViolationType.type_5_deception


def test_synonym_does_not_override_direct_keyword():
    """대표어가 직접 걸리면 동의어까지 안 간다(우선순위 보존)."""
    m = match_rule("해독 성분이 풍부한 팩")
    assert m is not None
    assert m.span == "해독"
    assert m.outcome == RuleOutcome.violation


# ── 문맥 예외(context_exceptions) 테스트 — 엑소좀 ──────────────────────────


def test_exosome_alone_is_violation():
    """'엑소좀' 단독은 여전히 위반 확정(원료 대분류 없이 그냥 엑소좀)."""
    m = match_rule("엑소좀 앰플로 탄탄한 피부")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "엑소좀"


def test_exosome_with_human_marker_is_violation():
    """'인체 유래 엑소좀'처럼 인체연상 단어가 같이 있으면 안전어가 있어도 위반 유지."""
    m = match_rule("인체 유래 엑소좀 성분이 피부 속까지")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "엑소좀"


def test_plant_exosome_is_exception_not_ruled_violation():
    """'식물 엑소좀'은 원료 대분류 예외 — 규칙이 위반으로 단정하지 않고 VLM에 넘긴다(None)."""
    assert match_rule("식물 엑소좀 유래 성분 함유") is None


def test_milk_exosome_is_exception():
    """'우유 엑소좀'도 같은 예외."""
    assert match_rule("우유 엑소좀으로 촉촉하게") is None


def test_cica_exosome_is_exception():
    """'시카 엑소좀'도 확정된 예외(2026-08-17 하니 확정, label_worksheet_expansion.xlsx)."""
    assert match_rule("시카 엑소좀 함유 크림") is None


# ── 니들류 — 2026-08-18 하니 확정으로 조건부 위반 폐지, 단어 자체로 위반 ──────
# 예전엔 "단어+메커니즘 서술 동반"일 때만 위반이었다(conditional_violation).
# "니들샷"처럼 메커니즘 없는 브랜드명도 합법 취급했는데, 그 완화의 원래 의도가
# "리들샷"이었던 걸로 정정됐다(기록 과정에서 리들→니들로 바뀌었다). §1 T5
# 마스터 문서(prohibited_expressions.md)는 원래부터 니들류를 단어로 나열하고
# 있어서, 이번 변경은 마스터 문서에 맞춘 것이다.


def test_needle_brand_name_alone_is_violation():
    """'니들샷'은 이제 메커니즘 서술 없이도 위반이다(브랜드명 완화 정정)."""
    m = match_rule("니들샷 앰플 추천")
    assert m is not None
    assert m.outcome == RuleOutcome.violation


def test_needle_word_alone_is_violation():
    """'니들' 단어 자체가 위반이다. 침투·흡수 서술이 없어도 된다."""
    m = match_rule("니들이 피부 속까지 침투해서 유효성분을 전달")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.violation_type == ViolationType.type_5_deception
    assert m.span == "니들"


def test_microneedle_alone_is_violation():
    """'마이크로니들'도 단어 자체로 위반(5호)."""
    m = match_rule("마이크로니들 기술로 흡수율을 높였습니다")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.violation_type == ViolationType.type_5_deception


def test_fine_needle_alone_is_violation():
    """실사례(51/9439804435). 정답셋과 하니 결정이 어긋나 있었는데, 하니가
    정답셋 라벨(위반)을 그대로 확정했다(2026-08-18)."""
    m = match_rule("이 모공 속으로 15㎛의 미세침이 넓고 빠르게 침투")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.violation_type == ViolationType.type_5_deception
    assert m.span == "미세침"


def test_pin_unit_notation_is_violation():
    """51번 원문 표현 그대로. 'Pin'만으로도 위반이다(case-sensitive, 대문자 P만 확인됨)."""
    m = match_rule("15㎛ Pin")
    assert m is not None
    assert m.outcome == RuleOutcome.violation


def test_needle_evasion_spelling_ridle_is_exempt():
    """'리들'은 이제 예외다. 상표 등록·장기 미제재된 회피표기라 하니가 뺐다
    (2026-08-18). synonyms.json의 "니들":["리들"] 매핑을 지웠다."""
    assert match_rule("리들 앰플로 피부 속까지 침투하는 케어") is None


def test_mts_alone_is_violation():
    """MTS도 이제 단어 자체로 위반이다(니들류와 동일 결정, 2026-08-18)."""
    m = match_rule("MTS 전용 세럼")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
