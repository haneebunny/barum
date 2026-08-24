"""국가·국내 카테고리·claim 기반 generic 수출 준비도 v2.

현재는 미국의 결정적 최소 체크만 지원한다. 키워드 탐지는 rule-pack을 고르는
보조 신호일 뿐 최종 법적 분류가 아니며, 사용자 자기진술만으로 COMPLIANT를
만들지 않는다.
"""

from __future__ import annotations

import re
from typing import Iterable

from barum.models import (
    AppliedRulePack,
    DomesticProductCategory,
    ExportReadinessReport,
    ExportReadinessRequest,
    ExportReadinessStatus,
    GenericExportProduct,
    GenericReadinessItem,
    PriorityAction,
    ReadinessEvidenceInput,
    ReadinessInputState,
    ReadinessSummary,
    ReadinessSupportLevel,
    RegulatoryRoute,
)
from barum.reference.us_ingredients import check_sunscreen_ingredients

US_COSMETIC_BASIC = "US_COSMETIC_BASIC"
US_SUNSCREEN_OTC = "US_SUNSCREEN_OTC"
HIGH_RISK_CLAIM_REVIEW = "HIGH_RISK_CLAIM_REVIEW"

_PACK_VERSION = "2026-08-24"

_STATUS_PRIORITY = {
    ExportReadinessStatus.COMPLIANT: 0,
    ExportReadinessStatus.NOT_ASSESSED: 1,
    ExportReadinessStatus.VERIFICATION_REQUIRED: 2,
    ExportReadinessStatus.REQUIRED_CHANGE: 3,
    ExportReadinessStatus.BLOCKER: 4,
}

_SUNSCREEN_PATTERN = re.compile(
    r"\bspf\s*\d*|\bsunscreen\b|\bsun\s*protection\b|\bsunburn\s*prevention\b|"
    r"\buv\s*protection\b|자외선\s*차단|선스크린|선블록",
    re.IGNORECASE,
)

_HIGH_RISK_PATTERNS: tuple[tuple[str, str, re.Pattern[str], str], ...] = (
    (
        "acne",
        "여드름 치료·예방 claim",
        re.compile(r"\bacne\b|\bpimples?\b|\bblackheads?\b|\bwhiteheads?\b|여드름\s*(치료|예방)", re.IGNORECASE),
        "FDA_M006",
    ),
    (
        "dandruff",
        "비듬·지루성 피부염 claim",
        re.compile(r"\bdandruff\b|seborrheic\s+dermatitis|\bpsoriasis\b|비듬\s*(치료|완화|예방)|지루성\s*피부염|건선", re.IGNORECASE),
        "FDA_M032",
    ),
    (
        "hair_growth",
        "모발 성장·탈모 예방 claim",
        re.compile(r"hair\s*(growth|regrowth|restoration)|restore\s+hair|prevent\s+hair\s+loss|발모|모발\s*성장|탈모\s*예방", re.IGNORECASE),
        "FDA_HAIR_GROWTH_310_527",
    ),
    (
        "skin_lightening",
        "피부 미백·색소침착 치료 claim",
        re.compile(r"skin\s*(lightening|bleaching)|hyperpigmentation|\bmelasma\b|\bhydroquinone\b|melanin\s*(reduction|inhibition)|기미\s*치료|색소침착\s*치료|멜라닌\s*억제", re.IGNORECASE),
        "FDA_SKIN_LIGHTENING",
    ),
    (
        "structure_function",
        "주름·구조기능 변화 claim",
        re.compile(r"remove\s+wrinkles?|increase\s+collagen|regenerate\s+cells?|eyelash\s+growth|주름\s*제거|콜라겐\s*증가|세포\s*재생|속눈썹\s*성장", re.IGNORECASE),
        "FDA_CLASSIFICATION",
    ),
    (
        "antiperspirant",
        "발한 억제 claim",
        re.compile(r"\bantiperspirant\b|reduc(?:e|es|ing)\s+perspiration|발한\s*억제|땀\s*억제", re.IGNORECASE),
        "FDA_M019",
    ),
    (
        "anticaries",
        "충치 예방 claim",
        re.compile(r"\banticavit(?:y|ies)\b|prevent(?:s|ing)?\s+cavities|caries\s+prevention|충치\s*예방", re.IGNORECASE),
        "FDA_M021",
    ),
)

_PROHIBITED_EXACT = {
    "bithionol",
    "vinyl chloride",
    "chloroform",
    "methylene chloride",
    "hexachlorophene",
}

_COLOR_PATTERN = re.compile(
    r"^(?:fd&c|d&c|external\s+d&c|ci)\s*[a-z#]*\s*\d+|\b(?:iron oxides?|ultramarines?)\b",
    re.IGNORECASE,
)


def _combined_text(req: ExportReadinessRequest) -> str:
    """claim과 intended use를 trigger 검색용 한 문자열로 합친다."""
    values = [req.intended_use or "", *req.claims]
    return " ".join(value.strip() for value in values if value and value.strip())


def _evidence_strings(evidence: ReadinessEvidenceInput) -> list[str]:
    values = list(evidence.evidence)
    if evidence.value not in (None, "", [], {}):
        values.append(f"사용자 입력값: {evidence.value}")
    return values


def _label_item(
    *,
    item_id: str,
    title: str,
    evidence: ReadinessEvidenceInput,
    why_it_matters: str,
    what_document: str,
    how_to_find: str,
) -> GenericReadinessItem:
    """라벨 필수 블록의 입력 상태를 내부 상태와 분리해 항목으로 만든다."""
    state = evidence.input_state
    if state == ReadinessInputState.NOT_ENTERED:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary = "해당 라벨 항목이 입력되지 않아 평가하지 않았습니다."
    elif state == ReadinessInputState.NOT_AVAILABLE:
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "사용자가 해당 필수 라벨 항목이 없다고 답했습니다."
    elif state == ReadinessInputState.UNKNOWN:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "해당 라벨 항목의 존재 여부를 모른다고 답했습니다."
    else:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "자료가 있다고 답했지만 실제 문구·배치·가독성은 검증하지 않았습니다."
    return GenericReadinessItem(
        id=item_id,
        category="LABELING",
        status=status,
        user_state=state,
        title=title,
        summary=summary,
        why_it_matters=why_it_matters,
        what_document=what_document,
        how_to_find=how_to_find,
        next_action=f"미국용 라벨에서 {title} 항목을 확인하고 최종 artwork에 반영하세요.",
        evidence=_evidence_strings(evidence),
        rule_pack_id=US_COSMETIC_BASIC,
        source_id="FDA_COSMETIC_LABELING",
    )


def _basic_label_items(req: ExportReadinessRequest) -> list[GenericReadinessItem]:
    label = req.label_evidence
    specs = (
        ("us_basic_label_identity", "제품 정체성 표시", label.statement_of_identity, "소비자가 제품의 정체성을 알 수 있어야 합니다.", "Principal Display Panel", "전면 표시부의 제품 유형·정체성 문구"),
        ("us_basic_label_net_quantity", "순내용량 표시", label.net_quantity, "순내용량은 미국 화장품 라벨의 기본 표시사항입니다.", "Principal Display Panel", "전면 표시부의 중량·부피와 미국 단위 표기"),
        ("us_basic_label_business", "사업자명·사업장소 표시", label.business_name_address, "제조자·포장자·유통자 중 책임 표시 주체를 식별해야 합니다.", "Information Panel", "사업자명, 주소, Manufactured for 또는 Distributed by 문구"),
        ("us_basic_label_ingredients", "성분 선언", label.ingredient_declaration, "미국용 성분명과 표시 순서를 확인해야 합니다.", "Ingredient declaration", "Ingredients로 시작하는 전체 성분 목록"),
        ("us_basic_label_language", "필수정보 영어 표시", label.english_required_information, "미국 판매 필수정보는 영어 표시가 필요합니다.", "미국용 라벨 전체", "정체성·순내용량·사업자·성분·경고의 영어 표기"),
        ("us_mocra_label_ae_contact", "부작용 연락 수단", label.adverse_event_contact, "책임 주체가 부작용 보고를 받을 연락 수단이 필요합니다.", "미국용 retail label", "미국 내 주소·전화번호 또는 전자 연락처"),
    )
    return [
        _label_item(
            item_id=item_id,
            title=title,
            evidence=evidence,
            why_it_matters=why,
            what_document=document,
            how_to_find=how,
        )
        for item_id, title, evidence, why, document, how in specs
    ]


def _classification_item(req: ExportReadinessRequest) -> GenericReadinessItem:
    supplied = bool((req.intended_use or "").strip() or req.claims)
    state = ReadinessInputState.PROVIDED if supplied else ReadinessInputState.NOT_ENTERED
    status = (
        ExportReadinessStatus.VERIFICATION_REQUIRED
        if supplied
        else ExportReadinessStatus.NOT_ASSESSED
    )
    return GenericReadinessItem(
        id="us_basic_classification",
        category="CLASSIFICATION",
        status=status,
        user_state=state,
        title="미국 intended use 분류",
        summary=(
            "intended use와 claim을 받았지만 최종 화장품·의약품 분류는 자동 확정하지 않습니다."
            if supplied
            else "intended use와 claim이 없어 미국 규제 경로를 충분히 평가하지 않았습니다."
        ),
        why_it_matters="미국 분류는 국내 카테고리보다 실제 사용 목적과 claim의 영향을 받습니다.",
        what_document="미국용 포장·상세페이지·광고 claim 목록",
        how_to_find="용기, 외포장, 웹사이트, 마켓플레이스, SNS 문구를 함께 확인",
        next_action="미국 판매용 전체 claim과 제품 사용 목적을 규제 전문가와 검토하세요.",
        evidence=[f"국내 카테고리: {req.domestic_category.value}", *req.claims],
        rule_pack_id=US_COSMETIC_BASIC,
        source_id="FDA_CLASSIFICATION",
    )


def _basic_formula_items(req: ExportReadinessRequest) -> list[GenericReadinessItem]:
    if not req.ingredients:
        return [GenericReadinessItem(
            id="us_basic_formula_screen",
            category="FORMULA",
            status=ExportReadinessStatus.NOT_ASSESSED,
            user_state=ReadinessInputState.NOT_ENTERED,
            title="금지·제한 성분 후보 확인",
            summary="전성분이 입력되지 않아 exact-match 후보 검사를 수행하지 않았습니다.",
            why_it_matters="일부 성분과 색소는 제품형·사용 부위·조건에 따라 제한됩니다.",
            what_document="최신 전체 INCI와 정량 처방",
            how_to_find="제조 처방서와 미국용 ingredient declaration을 대조",
            next_action="최신 전성분과 필요한 함량·사용 부위 정보를 입력하세요.",
            rule_pack_id=US_COSMETIC_BASIC,
            source_id="FDA_COSMETIC_INGREDIENTS",
        )]

    normalized = {ingredient.strip().lower(): ingredient for ingredient in req.ingredients}
    prohibited = [original for key, original in normalized.items() if key in _PROHIBITED_EXACT]
    color_candidates = [name for name in req.ingredients if _COLOR_PATTERN.search(name.strip())]
    if prohibited:
        formula_status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "FDA 금지·제한 목록의 exact-match 성분 후보가 발견됐습니다."
        action = "처방을 변경하거나 해당 성분의 정확한 적용 조건을 전문가와 확인하세요."
    else:
        formula_status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "제한된 exact-match 후보는 없었지만 이 결과가 처방 안전성이나 미국 적합성을 보장하지 않습니다."
        action = "정량 처방, 제형, 사용 부위와 전체 제한 조건을 검토하세요."
    items = [GenericReadinessItem(
        id="us_basic_formula_screen",
        category="FORMULA",
        status=formula_status,
        user_state=ReadinessInputState.PROVIDED,
        title="금지·제한 성분 후보 확인",
        summary=summary,
        why_it_matters="일부 화장품 성분은 미국에서 금지되거나 조건부로 제한됩니다.",
        what_document="최신 전체 INCI와 정량 처방",
        how_to_find="제조 처방서의 공식 INCI명을 FDA 목록과 대조",
        next_action=action,
        evidence=prohibited or [f"전성분 {len(req.ingredients)}개 입력"],
        rule_pack_id=US_COSMETIC_BASIC,
        source_id="FDA_COSMETIC_INGREDIENTS",
    )]
    color_state = req.product_evidence.color_additives.input_state
    if color_candidates or color_state != ReadinessInputState.NOT_ENTERED:
        if color_candidates and color_state == ReadinessInputState.NOT_ENTERED:
            color_state = ReadinessInputState.PROVIDED
        items.append(GenericReadinessItem(
            id="us_basic_color_use",
            category="FORMULA",
            status=ExportReadinessStatus.VERIFICATION_REQUIRED,
            user_state=color_state,
            title="색소 사용조건 확인",
            summary="색소 후보 또는 색소 자료가 있어 허용 부위·인증 lot·제품형 조건을 확인해야 합니다.",
            why_it_matters="색소는 intended use와 사용 부위별 허용 조건이 다를 수 있습니다.",
            what_document="색소 supplier 자료, CIN 또는 batch certification 자료",
            how_to_find="전성분의 CI·FD&C·D&C 표기와 원료 공급자 증빙 확인",
            next_action="색소별 사용 부위, 규격, 제한과 batch certification 필요 여부를 확인하세요.",
            evidence=[*color_candidates, *_evidence_strings(req.product_evidence.color_additives)],
            rule_pack_id=US_COSMETIC_BASIC,
            source_id="FDA_COLOR_COSMETICS",
        ))
    return items


def _profile_or_product_item(
    *,
    item_id: str,
    title: str,
    evidence: ReadinessEvidenceInput,
    fallback_provided: bool,
    source_id: str,
    profile_based: bool,
    why_it_matters: str,
    what_document: str,
) -> GenericReadinessItem:
    state = evidence.input_state
    if state == ReadinessInputState.NOT_ENTERED and fallback_provided:
        state = ReadinessInputState.PROVIDED
    status = (
        ExportReadinessStatus.NOT_ASSESSED
        if state == ReadinessInputState.NOT_ENTERED
        else ExportReadinessStatus.VERIFICATION_REQUIRED
    )
    messages = {
        ReadinessInputState.PROVIDED: "자료가 있다고 입력됐지만 FDA 현재 상태나 문서 유효성은 확인하지 않았습니다.",
        ReadinessInputState.NOT_AVAILABLE: "자료가 없다고 답했습니다. 적용 여부와 준비 경로를 확인해야 합니다.",
        ReadinessInputState.UNKNOWN: "자료 보유 여부를 모른다고 답했습니다.",
        ReadinessInputState.NOT_ENTERED: "자료 상태가 입력되지 않아 평가하지 않았습니다.",
    }
    return GenericReadinessItem(
        id=item_id,
        category="ESTABLISHMENT" if profile_based else "LISTING_IMPORT",
        status=status,
        user_state=state,
        title=title,
        summary=messages[state],
        why_it_matters=why_it_matters,
        what_document=what_document,
        how_to_find="제출 receipt·식별자·갱신일과 대상 제품 또는 시설을 함께 확인",
        next_action=f"{title} 적용 여부와 최신 증빙을 확인하세요. 등록·listing은 FDA 승인이나 인증을 뜻하지 않습니다.",
        evidence=_evidence_strings(evidence),
        rule_pack_id=US_COSMETIC_BASIC,
        source_id=source_id,
        profile_based=profile_based,
    )


def _basic_registration_items(req: ExportReadinessRequest) -> list[GenericReadinessItem]:
    profile = req.profile
    facility_fallback = any(
        value not in (None, "")
        for value in (
            profile.fda_establishment_registration,
            profile.fda_establishment_registration_number,
            profile.registration_status,
        )
    )
    listing_fallback = any(
        value not in (None, "")
        for value in (profile.drug_listing_status, profile.ndc_or_listing_number)
    )
    return [
        _profile_or_product_item(
            item_id="us_mocra_facility_registration",
            title="MoCRA 시설 등록",
            evidence=req.product_evidence.facility_registration,
            fallback_provided=facility_fallback,
            source_id="FDA_MOCRA_REG_LIST",
            profile_based=True,
            why_it_matters="해당되는 제조·가공 시설은 등록과 갱신 준비가 필요할 수 있습니다.",
            what_document="시설 FEI, 등록 receipt, 최초·갱신일, U.S. Agent 자료",
        ),
        _profile_or_product_item(
            item_id="us_mocra_product_listing",
            title="MoCRA 제품 listing",
            evidence=req.product_evidence.product_listing,
            fallback_provided=listing_fallback,
            source_id="FDA_MOCRA_REG_LIST",
            profile_based=False,
            why_it_matters="제품 listing은 시설 등록과 별개의 제품별 제출입니다.",
            what_document="listing 식별자, 제출·갱신일, 제품·시설·성분 snapshot",
        ),
        _profile_or_product_item(
            item_id="us_mocra_safety_substantiation",
            title="안전성 입증 기록",
            evidence=req.product_evidence.safety_substantiation,
            fallback_provided=False,
            source_id="FDA_MOCRA",
            profile_based=False,
            why_it_matters="책임 주체는 제품 안전성을 뒷받침하는 기록을 확보·유지해야 합니다.",
            what_document="처방 버전과 연결된 안전성 보고서 index, 검토자·검토일",
        ),
    ]


def _sunscreen_items(req: ExportReadinessRequest, trigger_evidence: list[str]) -> list[GenericReadinessItem]:
    items = [GenericReadinessItem(
        id="us_sunscreen_route_review",
        category="CLASSIFICATION",
        status=ExportReadinessStatus.VERIFICATION_REQUIRED,
        user_state=ReadinessInputState.PROVIDED,
        title="미국 OTC 선스크린 경로 확인",
        summary="선케어 카테고리 또는 자외선 보호 claim이 감지됐습니다. 최종 법적 분류는 자동 확정하지 않습니다.",
        why_it_matters="자외선 보호 intended use는 미국 OTC 의약품 경로와 화장품 요건을 함께 검토하게 할 수 있습니다.",
        what_document="미국용 전체 claim, 정량 처방, 시험자료, Drug Facts 라벨",
        how_to_find="포장·상세페이지의 SPF, sunburn, sun protection, UV protection 문구 확인",
        next_action="OTC Monograph M020 적용 가능성과 drug+cosmetic 요건을 전문가와 확인하세요.",
        evidence=trigger_evidence,
        rule_pack_id=US_SUNSCREEN_OTC,
        source_id="FDA_OTC_MONOGRAPHS",
    )]

    if not req.ingredients:
        status = ExportReadinessStatus.NOT_ASSESSED
        user_state = ReadinessInputState.NOT_ENTERED
        summary = "전성분이 없어 M020 활성성분 후보를 확인하지 않았습니다."
        formula_evidence: list[str] = []
    else:
        result = check_sunscreen_ingredients(req.ingredients)
        user_state = ReadinessInputState.PROVIDED
        formula_evidence = [*result["approved"], *result["unapproved"]]
        if result["unapproved"]:
            status = ExportReadinessStatus.BLOCKER
            summary = "현재 M020 경로에서 확인되지 않는 자외선차단 활성성분 후보가 있습니다. 이는 성분 자체의 금지를 의미하지 않습니다."
        else:
            status = ExportReadinessStatus.VERIFICATION_REQUIRED
            summary = "M020 활성성분 후보를 확인했지만 농도·조합·제형·증빙은 최종 검토가 필요합니다."
    items.append(GenericReadinessItem(
        id="us_sunscreen_formula",
        category="FORMULA",
        status=status,
        user_state=user_state,
        title="M020 활성성분 경로",
        summary=summary,
        why_it_matters="선스크린 경로는 활성성분뿐 아니라 농도·조합·제형 조건을 함께 봅니다.",
        what_document="전체 INCI, 활성성분별 함량, 최종 제형과 원료 증빙",
        how_to_find="정량 처방서와 M020/행정명령 적용 조건 대조",
        next_action="활성성분 식별과 농도·조합·제형 조건을 검토하세요.",
        evidence=formula_evidence,
        rule_pack_id=US_SUNSCREEN_OTC,
        source_id="FDA_OTC_MONOGRAPHS",
    ))

    for item_id, title, evidence, source in (
        ("us_sunscreen_spf_test", "SPF 시험자료", req.product_evidence.spf_test, "FDA_SUNSCREEN_GUIDANCE"),
        ("us_sunscreen_broad_spectrum", "Broad Spectrum 시험자료", req.product_evidence.broad_spectrum_test, "FDA_SUNSCREEN_GUIDANCE"),
        ("us_sunscreen_water_resistance", "Water Resistance 시험자료", req.product_evidence.water_resistance_test, "FDA_SUNSCREEN_GUIDANCE"),
        ("us_sunscreen_drug_facts", "Drug Facts 라벨", req.product_evidence.drug_facts_label, "FDA_DRUG_FACTS"),
    ):
        state = evidence.input_state
        status = (
            ExportReadinessStatus.NOT_ASSESSED
            if state == ReadinessInputState.NOT_ENTERED
            else ExportReadinessStatus.REQUIRED_CHANGE
            if state == ReadinessInputState.NOT_AVAILABLE
            else ExportReadinessStatus.VERIFICATION_REQUIRED
        )
        items.append(GenericReadinessItem(
            id=item_id,
            category="TESTING" if "test" in item_id or "spectrum" in item_id or "resistance" in item_id else "LABELING",
            status=status,
            user_state=state,
            title=title,
            summary={
                ReadinessInputState.PROVIDED: "자료가 있다고 입력됐지만 방법·기관·제품 처방 연결은 검증하지 않았습니다.",
                ReadinessInputState.NOT_AVAILABLE: "해당 자료가 없다고 입력됐습니다.",
                ReadinessInputState.UNKNOWN: "해당 자료 보유 여부를 모른다고 입력됐습니다.",
                ReadinessInputState.NOT_ENTERED: "해당 자료 상태가 입력되지 않았습니다.",
            }[state],
            why_it_matters="선스크린 claim과 Drug Facts는 해당 시험·표시 요건과 연결됩니다.",
            what_document=title,
            how_to_find="미국용 제품과 같은 처방의 시험성적서 또는 최종 라벨 artwork 확인",
            next_action=f"{title}의 존재와 미국 적용 요건을 확인하세요.",
            evidence=_evidence_strings(evidence),
            rule_pack_id=US_SUNSCREEN_OTC,
            source_id=source,
        ))
    return items


def _high_risk_matches(text: str) -> list[tuple[str, str, str, str]]:
    """고위험 claim trigger와 근거 구절을 찾는다. 상세 적합 판정은 하지 않는다."""
    matches: list[tuple[str, str, str, str]] = []
    for code, label, pattern, source_id in _HIGH_RISK_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append((code, label, match.group(0), source_id))
    return matches


def _high_risk_items(matches: Iterable[tuple[str, str, str, str]]) -> list[GenericReadinessItem]:
    return [GenericReadinessItem(
        id=f"high_risk_claim_{code}",
        category="CLAIMS",
        status=ExportReadinessStatus.VERIFICATION_REQUIRED,
        user_state=ReadinessInputState.PROVIDED,
        title=label,
        summary="고위험 intended-use 신호가 감지됐습니다. 키워드만으로 법적 분류나 적합성을 자동 확정하지 않습니다.",
        why_it_matters="치료·예방·구조기능 claim은 화장품 외 의약품 또는 복합 경로 검토가 필요할 수 있습니다.",
        what_document="미국용 전체 claim, 제품 사용 목적, 활성성분·함량과 승인 경로 자료",
        how_to_find="포장·웹사이트·마켓플레이스·SNS에서 같은 의미의 claim까지 함께 수집",
        next_action="해당 claim을 유지할지 결정하고 적용 가능한 OTC monograph 또는 별도 승인 경로를 확인하세요.",
        evidence=[f"탐지 구절: {matched_text}"],
        rule_pack_id=HIGH_RISK_CLAIM_REVIEW,
        source_id=source_id,
    ) for code, label, matched_text, source_id in matches]


def _priority_actions(items: list[GenericReadinessItem]) -> list[PriorityAction]:
    """내부 상태 우선순위로 최대 세 개의 행동을 고른다."""
    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: (-_STATUS_PRIORITY[pair[1].status], pair[0]))
    return [
        PriorityAction(
            item_id=item.id,
            title=item.title,
            status=item.status,
            next_action=item.next_action,
        )
        for _, item in indexed[:3]
    ]


def build_export_readiness_report(
    req: ExportReadinessRequest,
    *,
    created_at: str,
) -> ExportReadinessReport:
    """현재 지원하는 미국 rule-pack을 조합해 generic readiness 리포트를 만든다."""
    if req.destination_country != "US":
        raise ValueError(f"지원하지 않는 destination_country: {req.destination_country}")

    text = _combined_text(req)
    sunscreen_claim = _SUNSCREEN_PATTERN.search(text)
    sunscreen_triggered = (
        req.domestic_category == DomesticProductCategory.SUN_CARE
        or sunscreen_claim is not None
    )
    high_risk = _high_risk_matches(text)

    packs = [AppliedRulePack(
        rule_pack_id=US_COSMETIC_BASIC,
        version=_PACK_VERSION,
        support_level=ReadinessSupportLevel.PARTIAL,
    )]
    if sunscreen_triggered:
        packs.append(AppliedRulePack(
            rule_pack_id=US_SUNSCREEN_OTC,
            version=_PACK_VERSION,
            support_level=ReadinessSupportLevel.PARTIAL,
        ))
    if high_risk:
        packs.append(AppliedRulePack(
            rule_pack_id=HIGH_RISK_CLAIM_REVIEW,
            version=_PACK_VERSION,
            support_level=ReadinessSupportLevel.REVIEW_ONLY,
        ))

    items = [
        _classification_item(req),
        *_basic_label_items(req),
        *_basic_formula_items(req),
        *_basic_registration_items(req),
    ]
    if sunscreen_triggered:
        trigger_evidence = ["국내 카테고리: sun_care"] if req.domestic_category == DomesticProductCategory.SUN_CARE else []
        if sunscreen_claim is not None:
            trigger_evidence.append(f"탐지 구절: {sunscreen_claim.group(0)}")
        items.extend(_sunscreen_items(req, trigger_evidence))
    items.extend(_high_risk_items(high_risk))

    counts = {status: 0 for status in ExportReadinessStatus}
    for item in items:
        counts[item.status] += 1
    overall = max(items, key=lambda item: _STATUS_PRIORITY[item.status]).status

    if sunscreen_triggered or high_risk:
        route = RegulatoryRoute(
            code="DRUG_COSMETIC_CANDIDATE",
            label="미국 의약품·화장품 복합 경로 후보",
            support_level=(
                ReadinessSupportLevel.REVIEW_ONLY
                if high_risk
                else ReadinessSupportLevel.PARTIAL
            ),
            reasons=[
                *( ["선케어 카테고리 또는 자외선 보호 claim 감지"] if sunscreen_triggered else [] ),
                *( [f"고위험 claim trigger {len(high_risk)}종 감지"] if high_risk else [] ),
            ],
        )
    else:
        route = RegulatoryRoute(
            code="COSMETIC_ONLY_CANDIDATE",
            label="미국 일반 화장품 경로 후보",
            support_level=ReadinessSupportLevel.PARTIAL,
            reasons=[f"국내 카테고리: {req.domestic_category.value}", "고위험 claim trigger 미감지"],
        )

    product_snapshot = GenericExportProduct(
        product_name=req.product_name,
        intended_use=req.intended_use,
        claims=list(req.claims),
        ingredients=list(req.ingredients),
        domestic_subcategory=req.domestic_subcategory,
        product_subtype=req.product_subtype,
        use_site=req.use_site,
        application_mode=req.application_mode,
        ingredient_amounts=dict(req.ingredient_amounts),
        label_evidence=req.label_evidence.model_copy(deep=True),
        product_evidence=req.product_evidence.model_copy(deep=True),
    )
    support_level = (
        ReadinessSupportLevel.REVIEW_ONLY
        if high_risk
        else ReadinessSupportLevel.PARTIAL
    )
    return ExportReadinessReport(
        created_at=created_at,
        destination_country=req.destination_country,
        domestic_category=req.domestic_category,
        domestic_subcategory=req.domestic_subcategory,
        product_name=req.product_name,
        product_snapshot=product_snapshot,
        profile_status=req.profile_state,
        profile_snapshot=req.profile.model_copy(deep=True),
        regulatory_route=route,
        applied_rule_packs=packs,
        support_level=support_level,
        summary=ReadinessSummary(
            overall_status=overall,
            total=len(items),
            counts_by_status=counts,
        ),
        priority_actions=_priority_actions(items),
        items=items,
        disclaimer=(
            "본 결과는 입력한 제품 정보와 FDA 공개 자료를 바탕으로 준비 항목과 추가 확인 경로를 안내합니다. "
            "FDA 승인, 법률 자문 또는 통관 가능 판정이 아닙니다. 등록·listing 자기진술과 OCR·LLM 추출만으로 "
            "적합을 확정하지 않으며, 고위험 claim은 세부 규칙 판정 없이 추가 검토 대상으로만 표시합니다."
        ),
    )
