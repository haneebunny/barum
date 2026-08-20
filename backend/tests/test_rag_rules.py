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


def test_sensitive_with_whitening_claim_falls_through_to_vlm():
    """'예민'이 legal_allow로 먼저 안 걸리고, 같은 문장의 미백(2호) 클레임이
    VLM 경로로 넘어간다(2026-08-19 실측 사례, 정답셋 963문장 크로스탭 발견:
    legal_allow가 다른 미판정 클레임까지 통째로 스킵시키던 구조적 문제)."""
    assert match_rule("예민한 피부도 안심하고 쓰는 순한 미백") is None


def test_elasticity_with_wrinkle_claim_falls_through_to_vlm():
    """'탄력'도 같은 문장에 주름개선(2호) 클레임이 있으면 legal_allow를 취소한다."""
    assert match_rule("탄력과 주름개선에 도움을 주는 아이크림") is None


def test_sensitive_alone_is_still_legal_allow():
    """2호·5호 클레임이 전혀 없으면 '민감'은 여전히 합법 확정(회귀 없음 확인)."""
    m = match_rule("민감 피부도 안심하고 사용하는 순한 크림")
    assert m is not None
    assert m.outcome == RuleOutcome.legal_allow
    assert m.span == "민감"


def test_sensitive_with_low_irritation_claim_is_not_legal_allow():
    """'저자극'이 같이 있으면 예외를 취소해 VLM 경로로 넘긴다.

    정답셋 40·48·49번 실사례("민감 피부도 안심하고 사용하는 비건 저자극 솔루션"
    등)가 5호(시험검사표현) 검토필요인데 '민감'의 legal_allow에 먼저 걸려
    VLM에도 못 가고 증발했다(2026-08-19 정답셋 크로스탭 재확인, 스윕으로 확인).
    2호 마커(미백 등)와 같은 취급 — '저자극' 자체를 위반 키워드로 쓰는 게
    아니라, 민감/탄력/예민이 이미 매치된 문장에서만 예외를 취소한다(그래서
    '저자극 딥클렌징'처럼 민감/탄력/예민이 없는 무관한 합법 문장은 안 건드린다).
    """
    assert match_rule("민감 피부도 안심하고 사용하는 비건 저자극 솔루션") is None


def test_sensitive_with_completed_test_claim_is_not_legal_allow():
    """'완료'가 같이 있으면(테스트/시험 완료류) 마찬가지로 예외를 취소한다.

    정답셋 53번 실사례. '완료'는 이미 별도 needs_review 규칙의 판별자라(시험·
    테스트 완료류), 민감/탄력/예민의 legal_allow가 그 판정 기회를 가로채면 안 된다.
    """
    assert match_rule("피부 자극 테스트를 완료한 세럼으로 민감한 피부에도 걱정없이 사용 가능합니다") is None


def test_legal_allow_markers_cover_pack_synonyms():
    """마커가 '미백'만이 아니라 팩이 같이 묶어 놓은 표기까지 봐야 한다.

    `prohibited_expressions.md` §1 T2가 "미백·화이트닝(whitening)·주름(wrinkle)개선"을
    한 항목으로 명시하는데 마커엔 한글 대표어만 있었다. 영문·한글 변형으로 쓴 광고가
    그대로 증발한다(2026-08-19 정답셋 크로스탭 발견).
    """
    for s in [
        "탄력 케어와 화이트닝을 한 번에",
        "탄력에 좋은 whitening 세럼",
        "민감 피부를 위한 wrinkle care",
    ]:
        assert match_rule(s) is None, s


def test_legal_allow_marker_covers_pigmentation():
    """정답셋 53번 실사례. '색소침착'은 §1 T1(기미·주근깨=과색소침착증) 근거로,
    T2 계열과 조항은 다르지만 마찬가지로 판단이 필요한 클레임이라 증발시키면 안 된다."""
    assert match_rule("색소침착&탄력개선&저자극에 뛰어난 크림") is None


def test_uv_abbreviation_is_not_a_marker():
    """'UV'는 마커에 안 넣는다. 정답셋에서 인증기관 표기(Bureau Veritas ... 대상외)에
    부분일치했다 — 마커는 `_keyword_present`를 안 거쳐 영단어 경계 보호조차 없다."""
    m = match_rule("탄력 케어 UV 인증 제품")
    assert m is not None
    assert m.outcome == RuleOutcome.legal_allow


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


def test_procedure_alone_is_not_violation():
    """'시술 후 진정'은 이제 위반이 아니다(2026-08-18 정정).

    옛 규칙은 "시술 동반이면 진정보다 시술이 먼저 걸려 위반"이었는데, 정답셋에
    "시술 후 예민해진 피부 진정에 도움이 필요하신 분"이 합법으로 확정돼 있어
    오탐이었다. type_1_drug_misperception.md '시술 vs 치료' 확정규칙("시술"은
    구체적 시술명 없이 맥락으로만 쓰이면 중립)과도 맞다. "시술"을 문맥예외로
    돌려 메디컬·피부과 같은 구체적 주체가 없으면 위반 아니게 했다. 다만 "진정"
    자체는 여전히 검토필요 대상이라(§2 실증대상), 완전한 합법이 아니라
    needs_review로 남는다 — 위반보다는 개선이다.
    """
    m = match_rule("시술 후 예민해진 피부를 진정")
    assert m is not None
    assert m.outcome == RuleOutcome.needs_review
    assert m.span == "진정"


def test_medical_procedure_context_is_still_violation():
    """'메디컬시술'·'피부과시술'처럼 구체적 주체가 붙으면 위반을 유지한다(하니 확정)."""
    for s in ["메디컬시술로 관리된 피부", "피부과시술 전후 케어에 좋은 크림"]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome == RuleOutcome.violation, s


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


def test_synonym_trouble_alone_is_not_violation():
    """'트러블'은 이제 단독으로는 위반이 아니다(2026-08-18 정정).

    정답셋 "★피부 트러블로 인한 경우 반품 불가"(반품정책 문구, 효능주장 아님)가
    여드름의 동의어로 오탐 났다. "여드름"의 동의어 3개(트러블·피부트러블·뾰루지)
    전부 문맥예외로 돌려, "치료"급 단어가 같이 있을 때만 위반으로 올린다.
    """
    assert match_rule("트러블 피부를 위한 솔루션") is None


def test_synonym_trouble_with_treatment_claim_is_violation():
    """'치료'급 단어가 같이 있으면 트러블 계열도 위반을 유지한다."""
    m = match_rule("트러블을 치료하는 솔루션")
    assert m is not None
    assert m.outcome == RuleOutcome.violation


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
    """'리들'은 니들류 플랫 위반의 예외다. 상표 등록·장기 미제재된 회피표기라
    2026-08-18에 synonyms.json의 "니들":["리들"] 매핑을 지웠다.

    **2026-08-19 정정**: 이 테스트는 원래 "리들 앰플로 피부 속까지 침투하는 케어"로
    예외를 확인했는데, 그 문장은 침투 서술이 있어서 위반이 맞다(팀장 확정: 리들샷이
    브랜드명이고 침투 내용이 없으면 합법, 있으면 위반). 예외를 확인하려는 테스트가
    회귀를 못박고 있었다. 메커니즘 서술이 없는 문장으로 바꾼다. 조건부 위반 쪽은
    아래 test_ridle_with_penetration_context_is_violation이 맡는다.
    """
    assert match_rule("리들 앰플 신제품 출시") is None


def test_mts_alone_is_violation():
    """MTS도 이제 단어 자체로 위반이다(니들류와 동일 결정, 2026-08-18)."""
    m = match_rule("MTS 전용 세럼")
    assert m is not None
    assert m.outcome == RuleOutcome.violation


# ── 비교광고(별표5 "바"항) — 2026-08-19 신설 ────────────────────────────
# 근거 없는 비교수치(N배)는 위반, 배타적 최상급(NO.1·최고 등)은 일반 수식어와
# 같은 취급으로 needs_review. prohibited_expressions.md:59 · cases.md:32 근거.


def test_comparison_with_multiplier_is_violation():
    """정답셋 06번 원문. '대비'+'N배'가 같이 있으면 근거 없는 비교수치로 위반."""
    m = match_rule("시중 제품 대비 3배 이상에 해당하는 용량!")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.violation_type == ViolationType.type_5_deception
    assert m.span == "비교수치"


def test_comparison_multiplier_generalizes_beyond_three():
    """배수가 3이 아니어도(예: 5배) 같은 패턴으로 걸려야 한다(정규식이므로 숫자 나열 아님)."""
    m = match_rule("타사 대비 5배 빠른 흡수력")
    assert m is not None
    assert m.outcome == RuleOutcome.violation


def test_comparison_without_multiplier_is_not_flagged_by_this_rule():
    """정답셋 53번. '대비'만 있고 배수가 없으면 비교수치 규칙에 안 걸린다(다른 경로로 처리)."""
    m = match_rule("레티놀 대비 자극이 적고, 우수한 효과")
    assert m is None or m.span != "비교수치"


def test_exclusive_superlative_no1_is_needs_review():
    """정답셋 29·32번. 'NO.1'·'No.1'·'1위'는 배타적 최상급 — needs_review."""
    for s in [
        "No.1* 선스틱",
        "전세계적으로 10초에 1개씩 판매되는 록시땅 베스트 셀러 NO.1",
        "전 세계 록시땅 매장 내 판매 1위를 고수하고 있는",
    ]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome == RuleOutcome.needs_review, s
        assert m.violation_type == ViolationType.type_5_deception, s


def test_hash_one_is_needs_review():
    """'#1'도 같은 배타적 최상급 계열(록시땅 실사례, 2026-08-19 팀장 승인)."""
    m = match_rule("록시땅의 #1 베스트셀러 시어 버터 핸드크림")
    assert m is not None
    assert m.outcome == RuleOutcome.needs_review
    assert m.violation_type == ViolationType.type_5_deception


def test_rank_number_with_leading_digit_is_not_flagged():
    """'11위'·'#123'처럼 앞뒤에 다른 숫자가 붙으면 매칭하지 않는다.

    'NO.1'·'1위'·'#1'은 순수 영단어가 아니라(#·마침표·한글 혼합) 기존
    `_keyword_present`의 우측경계 보호를 못 받는다 — "Pin"이 "Pintox"에 부분일치로
    걸렸던 사고와 같은 클래스라, 정규식으로 숫자 경계를 직접 봤다(2026-08-19).
    """
    for s in ["매출 11위 브랜드", "판매순위 21위", "상품코드 #123"]:
        m = match_rule(s)
        assert m is None or m.span != "배타적순위", s


def test_exclusive_superlative_choego_is_needs_review():
    """'최고'·'최상'·'유일'도 배타적 최상급 — needs_review(기존 완벽한·최적의·파워와 동일 취급)."""
    for kw in ["최고", "최상", "유일"]:
        m = match_rule(f"{kw}의 보습 크림")
        assert m is not None, kw
        assert m.outcome == RuleOutcome.needs_review, kw


# ── 근거 없는 검증방법 주장(별표5 "사"·"아"항) — 2026-08-19 신설 ──────────────
# type_5_deception.md #38 근거(cases.md #38 실사례). 의도적으로 좁게: 구체적 검증방법
# (임상시험 등)을 근거없이 단정할 때만 위반, 막연한 자기주장형은 대상 아님.


def test_verification_claim_with_clinical_trial_is_violation():
    """cases.md #38 원문 그대로. 임상시험+검증받았다는 단정은 위반."""
    m = match_rule("신뢰도 높은 여러 기관의 임상시험으로 철저히 검증받은 제품입니다")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.violation_type == ViolationType.type_5_deception
    assert m.span == "검증방법단정"


def test_verification_claim_generalizes_to_other_method_terms():
    """임상시험이 아니어도(인체적용시험 등) 같은 패턴이면 걸려야 한다."""
    m = match_rule("인체적용시험으로 안전성이 입증된 순한 세럼")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "검증방법단정"


def test_vague_self_claim_without_method_is_not_flagged_by_this_rule():
    """'효과로 증명합니다'처럼 구체적 검증방법 언급이 없는 막연한 자기주장형은 이 규칙 대상이
    아니다(2026-08-19 하니 재확인 — 이 규칙을 의도적으로 좁게 유지하는 핵심 근거)."""
    m = match_rule("거짓 없는 화장품, 효과로 증명하는 화장품입니다")
    assert m is None or m.span != "검증방법단정"


def test_method_term_alone_without_certainty_marker_is_not_flagged():
    """검증방법 용어가 있어도 '검증/입증' 단정이 없으면 이 규칙에 안 걸린다."""
    m = match_rule("임상시험 참가자를 모집합니다")
    assert m is None or m.span != "검증방법단정"


# ── 모공수축 표방 — 2026-08-12 확정 규칙, 2026-08-19 규칙집 반영 ───────────────


def test_pore_shrink_claim_is_needs_review():
    """정답셋 02번. prohibited_expressions.md:46이 T5로 명시하고 "실증자료 없이
    표방하면 위반후보(검토필요), 뒷받침되면 예외"로 확정해 뒀는데 규칙집에 반영이
    안 돼 있었다."""
    for s in ["모공수축", "모공 축소 효과를 원하시는 분"]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome == RuleOutcome.needs_review, s
        assert m.violation_type == ViolationType.type_5_deception, s


def test_bare_pore_word_is_not_flagged():
    """맨 '모공'은 규칙에 안 넣는다. 정답셋에서 해부학적 사실 서술(대상외)과
    합법 문장에 걸린다 — 복합어로만 잡아야 하는 전형적 substring 함정."""
    for s in ["1cm에 모공 60~70개", "피지-모공-수분 3단계 과학적 설계"]:
        m = match_rule(s)
        assert m is None or m.span not in ("모공수축", "모공축소"), s


# ── 시험·검사 표현 — §3 실증대상, 2026-08-19 반영 ─────────────────────────────


def test_test_completion_claim_is_needs_review():
    """prohibited_expressions.md:75가 "시험·검사 표현(예: 피부과 테스트 완료)"을
    §3 실증대상으로 명시한다. 정답셋 18번과 축자 일치."""
    for s in ["피부과 테스트 완료", "인체적용시험 완료", "지속내수성테스트 완료"]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome == RuleOutcome.needs_review, s
        assert m.violation_type == ViolationType.type_5_deception, s


def test_test_without_completion_is_not_flagged():
    """'완료'가 판별자다. 정답셋에서 '피부 무자극 테스트'(완료 없음)는 합법 4건인데
    '테스트 완료'는 검토필요 7건으로 갈린다. 맨 '테스트'로 잡으면 합법을 오탐한다."""
    for s in ["피부 무자극 테스트", "피부 무자극 테스트 EXCELLENT 0.00"]:
        m = match_rule(s)
        assert m is None or m.span not in ("테스트완료", "시험완료"), s


def test_low_irritation_alone_is_not_flagged():
    """'저자극'은 안 넣는다. 정답셋에 합법 2건('저자극 딥클렌징'·'저자극 토너')이 있다."""
    for s in ["저자극 딥클렌징", "✓ 지성, 문제성 피부용 저자극 토너"]:
        m = match_rule(s)
        assert m is None or m.outcome != RuleOutcome.needs_review, s


# ── 콜라겐 표방 — 2026-08-19 정정(violation -> needs_review) ──────────────────


def test_collagen_claim_is_needs_review_not_violation():
    """콜라겐은 실증대상이라 위반 단정 대상이 아니다.

    `prohibited_expressions.md` §3(실증대상, 관리지침 별표2)이 "콜라겐·효소 증가·감소·
    활성화"를 조건부 목록에 싣고, §3 머리말이 "우리 판정에선 검토필요, 위반 단정 금지"
    라고 못박는다. §3 형제 표현(피부노화·붓기·다크서클·피부장벽·진정)은 전부
    needs_review인데 콜라겐만 violation에 혼자 있었다(5ab0942 일괄 추가분).
    """
    for s in ["콜라겐 증가에 도움을 주는 크림", "콜라겐 활성화 앰플"]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome == RuleOutcome.needs_review, s
        assert m.violation_type == ViolationType.type_1_drug_misperception, s


# ── 리들 = 조건부 위반 (니들과 갈래가 다름) ───────────────────────────────────
# 2026-08-18에 니들류를 플랫 violation으로 옮기면서 "리들"을 synonyms.json에서 통째로
# 뺐는데, 그때 "리들+침투" 조합을 잡던 경로까지 같이 사라진 회귀가 있었다(2026-08-19
# 실측). 니들=단어 자체로 위반, 리들=메커니즘 서술 동반 시에만 위반으로 구분한다.


def test_ridle_with_penetration_context_is_violation():
    """회귀 재현 케이스. "리들샷으로 ... 침투"는 위반이어야 한다."""
    for s in [
        "리들샷으로 유효성분이 피부 깊숙이 침투합니다",
        "리들 앰플로 피부 속까지 침투하는 케어",
        "리들샷 흡수가 빠른 앰플",
    ]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome == RuleOutcome.violation, s
        assert m.violation_type == ViolationType.type_5_deception, s
        assert m.span == "리들", s


def test_ridle_brand_name_alone_is_not_violation():
    """메커니즘 서술 없이 브랜드명만 쓰면 통과다(상표 등록·장기 미제재 회피표기)."""
    for s in ["리들샷 앰플 추천", "리들샷 세럼 신제품"]:
        assert match_rule(s) is None, s


def test_needle_stays_unconditional_violation():
    """니들은 조건부가 아니다. 메커니즘 서술이 없어도 단어 자체로 위반을 유지한다."""
    m = match_rule("니들샷 앰플 추천")
    assert m is not None
    assert m.outcome == RuleOutcome.violation
    assert m.span == "니들"


def test_penetration_context_alone_is_not_violation():
    """맥락어만 있고 리들이 없으면 이 규칙은 발동하지 않는다("흡수"는 합법 문장에 흔하다)."""
    m = match_rule("피부에 부드럽게 흡수되며")
    assert m is None or m.span != "리들"
