"""레퍼런스 팩(T-체계) ↔ 판정 enum(ViolationType) 매핑.

`reference/cosmetic_kr/prohibited_expressions.md`는 화장품법 위반을 T1~T6
6종으로 분류한다(법조문·시행규칙 별표5를 그대로 따라간 세분류). 반면 우리
판정기 출력(`ViolationType`)은 5값뿐이다. 이 파일이 그 둘을 잇는 단일 지점이라,
근거 조항 문자열을 여기저기 하드코딩하지 않고 다 여기서 가져온다(드리프트 방지).

매핑 근거(2026-08-11, PM 확정):
- T1(의약품 오인) → 1호_의약품오인
- T2(기능성 오인) → 2호_기능성오인
- T3(삭제 조항, 2025.1.31)  → 판정에 미사용
- T4(AI 생성물·전문가 추천 오인, 2026.11.27 시행 신설) → 판정 라벨 아님.
  문구 판정이 아니라 콘텐츠 생성 시점 가드레일(FR-13) 영역이라 이 enum에 없다.
- T5(그 밖의 거짓·과장·기만) → 5호_거짓과장기만
- T6(시행규칙 별표5 세부유형: 천연·유기농 오인, 의사 추천 암시, 배타적 표현 등)
  → 5호_거짓과장기만으로 접는다. 별표5는 법13조①5호(개정 기준)의 하위 근거이지
  독립된 판정 라벨이 아니다(`law_article_13.md` 참조).
"""

from barum.models import ViolationType

# T-code → ViolationType. T3·T4는 문구 판정 라벨이 아니라 의도적으로 없다
# (NOT_A_JUDGMENT_LABEL 참조). 여기 없는 T-code로 조회하면 KeyError로 즉시 드러난다.
T_TO_VIOLATION_TYPE: dict[str, ViolationType] = {
    "T1": ViolationType.type_1_drug_misperception,
    "T2": ViolationType.type_2_functional_misperception,
    "T5": ViolationType.type_5_deception,
    "T6": ViolationType.type_5_deception,
}

# 판정 라벨이 아닌 T-code와 그 이유. 코드에서 "왜 매핑에 없는지" 조회할 때 쓴다.
NOT_A_JUDGMENT_LABEL: dict[str, str] = {
    "T3": "삭제된 조항(2025.1.31) — 효력 없음, 판정 미사용",
    "T4": "AI 생성물·전문가 추천 오인(2026.11.27 시행 신설) — 문구 판정이 아니라 "
    "콘텐츠 생성 시 이미지 요청을 거부하는 가드레일(FR-13) 영역",
}

# ViolationType → 근거 조항 문자열. judge(PromptJudge)의 legal_basis가 여기서 나온다.
# 화장품법 제13조 제1항 체계(개정법 기준, 2026.11.26 시행 이후 번호).
_LEGAL_BASIS: dict[ViolationType, str] = {
    ViolationType.type_1_drug_misperception: "화장품법 제13조 제1항 제1호 (의약품 오인)",
    ViolationType.type_2_functional_misperception: "화장품법 제13조 제1항 제2호 (기능성 오인)",
    ViolationType.type_5_deception: "화장품법 제13조 제1항 제5호 (거짓·과장·기만, 개정법 기준)",
}


def legal_basis_for(vtype: ViolationType) -> str:
    """위반유형에 대응하는 근거 조항 문자열을 낸다.

    합법·대상외는 근거 조항이 없다(위반이 아니므로) — 호출하면 KeyError.
    """
    return _LEGAL_BASIS[vtype]


# ViolationType → 조문 원문 전체. 사용자가 리포트에서 "왜 위반인지"를 우리 설명
# 말고 실제 법조문으로도 확인할 수 있게 한다(2026-08-15, 하니 지시). 원문은
# `reference/cosmetic_kr/statute/law_article_13.md`에서 WebFetch로 재검증한 것과
# 동일 문자열(단일 출처 원칙, `citation_registry.md` id: kr_law_art13).
_LEGAL_BASIS_TEXT: dict[ViolationType, str] = {
    ViolationType.type_1_drug_misperception: "의약품으로 잘못 인식할 우려가 있는 표시 또는 광고",
    ViolationType.type_2_functional_misperception: (
        "기능성화장품이 아닌 화장품을 기능성화장품으로 잘못 인식할 우려가 있거나 "
        "기능성화장품의 안전성ㆍ유효성에 관한 심사결과와 다른 내용의 표시 또는 광고"
    ),
    ViolationType.type_5_deception: (
        "그 밖에 사실과 다르게 소비자를 속이거나 소비자가 잘못 인식하도록 할 우려가 있는 "
        "표시 또는 광고"
    ),
}


def legal_basis_text_for(vtype: ViolationType) -> str | None:
    """위반유형에 대응하는 조문 원문 전체를 낸다.

    원문을 아직 못 채운 유형은 None(있는 만큼만 노출, 없는 걸 지어내지 않는다).
    """
    return _LEGAL_BASIS_TEXT.get(vtype)
