"""미국 선스크린 수출 준비도 MVP의 결정적 체크리스트 판정.

이 모듈은 FDA 실시간 조회나 LLM 판정을 하지 않는다. 입력값과 현재 저장된 M020
참조 데이터만으로 "무엇을 준비해야 하는지"를 계산하고, 외부 증빙 검토가 필요한
항목은 COMPLIANT로 올리지 않는다.
"""

from __future__ import annotations

import re
from typing import Any

from barum.models import (
    ExportProduct,
    ExportProfile,
    ExportReadinessCategory,
    ExportReadinessStatus,
    ReadinessItem,
    ReadinessSummary,
    USExportReadinessReport,
    USPreflightReport,
)
from barum.reference.us_ingredients import (
    canonical_name,
    check_sunscreen_ingredients,
    sunscreen_active_details,
)

FDA_OTC_IMPORTS = "FDA_OTC_IMPORTS"
FDA_OTC_MONOGRAPHS = "FDA_OTC_MONOGRAPHS"
FDA_OTC000039 = "FDA_OTC000039"
FDA_SUNSCREEN_GUIDANCE = "FDA_SUNSCREEN_GUIDANCE"
FDA_DRUG_FACTS = "FDA_DRUG_FACTS"
FDA_ESTABLISHMENT_REGISTRATION = "FDA_ESTABLISHMENT_REGISTRATION"
FDA_DRUG_LISTING = "FDA_DRUG_LISTING"

_STATUS_PRIORITY = {
    ExportReadinessStatus.COMPLIANT: 0,
    ExportReadinessStatus.NOT_ASSESSED: 1,
    ExportReadinessStatus.VERIFICATION_REQUIRED: 2,
    ExportReadinessStatus.REQUIRED_CHANGE: 3,
    ExportReadinessStatus.BLOCKER: 4,
}

_SUNSCREEN_KEYWORDS = (
    "spf",
    "자외선차단",
    "uv차단",
    "선블록",
    "sunscreen",
    "sun protection",
    "sunburn protection",
)
_CLAIM_KEYWORDS = _SUNSCREEN_KEYWORDS + (
    "waterproof",
    "sweatproof",
    "all-day protection",
    "all day protection",
    "방수",
    "땀에도",
    "하루종일",
)


def _present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "ready", "active", "registered", "완료", "있음"}
    return value is True


def _falsey(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"false", "no", "not_started", "not_ready", "미준비", "없음"}
    return value is False


def _has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _item(
    item_id: str,
    category: ExportReadinessCategory,
    status: ExportReadinessStatus,
    title: str,
    summary: str,
    next_action: str,
    *,
    evidence: list[str] | None = None,
    rule_id: str | None = None,
    source_id: str | None = None,
    profile_based: bool = False,
) -> ReadinessItem:
    return ReadinessItem(
        id=item_id,
        category=category,
        status=status,
        title=title,
        summary=summary,
        next_action=next_action,
        evidence=evidence or [],
        rule_id=rule_id,
        source_id=source_id,
        profile_based=profile_based,
    )


def _parse_ingredient_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,\n]+", raw) if part.strip()]


def _parse_percentage(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%?", value)
    return float(match.group(1)) if match else None


def _ingredient_amounts(product: ExportProduct) -> dict[str, float]:
    raw = product.ingredient_amounts
    if raw is None:
        return {}
    pairs: list[tuple[Any, Any]] = []
    if isinstance(raw, dict):
        pairs.extend(raw.items())
    elif isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict):
                name = row.get("name") or row.get("ingredient")
                amount = row.get("amount") or row.get("percentage")
                if name is not None:
                    pairs.append((name, amount))
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                pairs.append((row[0], row[1]))
    result: dict[str, float] = {}
    for name, amount in pairs:
        parsed = _parse_percentage(amount)
        if parsed is not None and _present(name):
            result[canonical_name(str(name))] = parsed
    return result


def _classification_item(
    text: str, product: ExportProduct, old_report: USPreflightReport | None
) -> ReadinessItem:
    intended_use = (product.intended_use or "").strip().lower()
    detected = _has_keyword(text, _SUNSCREEN_KEYWORDS)
    if old_report is not None:
        detected = detected or any(
            finding.category.value == "OTC의약품_분류전환" for finding in old_report.findings
        )
    if detected or intended_use == "sunscreen":
        return _item(
            "classification",
            ExportReadinessCategory.CLASSIFICATION,
            ExportReadinessStatus.VERIFICATION_REQUIRED,
            "미국 OTC 선스크린 경로 분류",
            "자외선차단 의도가 확인되어 미국 OTC 선스크린 경로와 적용 요건을 확인해야 합니다. 이는 법적 최종판정이 아닙니다.",
            "미국 판매 용도와 OTC monograph 적용 경로를 전문가와 확인하세요.",
            evidence=["사용자 입력 또는 광고 문구에서 자외선차단 표현 감지"],
            rule_id="US-SUN-CLASS-001",
            source_id=FDA_OTC_IMPORTS,
        )
    if intended_use == "other":
        return _item(
            "classification",
            ExportReadinessCategory.CLASSIFICATION,
            ExportReadinessStatus.COMPLIANT,
            "미국 OTC 선스크린 경로 분류",
            "제품 용도가 선스크린이 아니며 자외선차단 표현도 감지되지 않았습니다.",
            "미국용 광고·포장에 자외선차단 표현을 추가할 경우 분류를 다시 확인하세요.",
            evidence=["사용자 의도 용도: other", "자외선차단 표현 미검출"],
            rule_id="US-SUN-CLASS-001",
            source_id=FDA_OTC_IMPORTS,
        )
    return _item(
        "classification",
        ExportReadinessCategory.CLASSIFICATION,
        ExportReadinessStatus.NOT_ASSESSED,
        "미국 OTC 선스크린 경로 분류",
        "의도 용도와 자외선차단 claim이 없어 미국 규제 경로를 아직 판단하지 않았습니다.",
        "제품의 미국 판매 용도와 자외선차단 claim 사용 여부를 입력하세요.",
        rule_id="US-SUN-CLASS-001",
        source_id=FDA_OTC_IMPORTS,
    )


def _formula_item(
    ingredients: list[str], product: ExportProduct, sunscreen_scope: bool
) -> ReadinessItem:
    if not ingredients:
        return _item(
            "formula",
            ExportReadinessCategory.FORMULA,
            ExportReadinessStatus.NOT_ASSESSED,
            "활성성분 및 M020 경로",
            "전성분이 없어 미국 OTC Monograph M020 경로의 활성성분을 확인하지 않았습니다.",
            "최신 전성분과 활성성분의 함량·제형 정보를 입력하세요.",
            rule_id="US-SUN-FORMULA-001",
            source_id=FDA_OTC_MONOGRAPHS,
        )

    result = check_sunscreen_ingredients(ingredients)
    amounts = _ingredient_amounts(product)
    exceeded: list[str] = []
    for name in result["approved"]:
        detail = sunscreen_active_details(name)
        if not detail:
            continue
        limit = _parse_percentage(detail.get("최대 함량"))
        amount = amounts.get(canonical_name(name))
        if limit is not None and amount is not None and amount > limit:
            exceeded.append(f"{name} ({amount:g}% > {limit:g}%)")

    if exceeded:
        return _item(
            "formula",
            ExportReadinessCategory.FORMULA,
            ExportReadinessStatus.BLOCKER,
            "활성성분 및 M020 경로",
            "입력된 함량이 M020 데이터의 최대 함량을 초과했습니다. 이는 미국 판매 경로가 확인되지 않는다는 뜻이며, 성분 자체의 금지를 의미하지 않습니다.",
            "처방·함량을 수정하거나 별도 승인 경로가 필요한지 전문가와 확인하세요.",
            evidence=exceeded,
            rule_id="US-SUN-FORMULA-CONCENTRATION-001",
            source_id=FDA_OTC_MONOGRAPHS,
        )

    if product.bemotrizinol_confirmed_ineligible:
        return _item(
            "formula",
            ExportReadinessCategory.FORMULA,
            ExportReadinessStatus.BLOCKER,
            "활성성분 및 M020 경로",
            "Bemotrizinol에 대해 입력된 증빙이 OTC000039의 적용 조건과 맞지 않습니다.",
            "Bemotrizinol의 조합·제형·적용 조건을 재검토하고 별도 경로를 확인하세요.",
            evidence=["Bemotrizinol 적용 조건 불일치 사용자 선언"],
            rule_id="US-SUN-FORMULA-BEMOTRIZINOL-001",
            source_id=FDA_OTC000039,
        )

    if result["unapproved"]:
        names = ", ".join(result["unapproved"])
        return _item(
            "formula",
            ExportReadinessCategory.FORMULA,
            ExportReadinessStatus.BLOCKER,
            "활성성분 및 M020 경로",
            f"다음 자외선차단 활성성분은 현재 M020 경로에서 확인되지 않았습니다: {names}. M020 미포함은 미국에서 다른 승인 경로가 없다는 의미가 아닙니다.",
            "성분 식별·농도·제형을 확인하고 별도 승인 경로가 필요한지 전문가 검토를 받으세요.",
            evidence=result["unapproved"],
            rule_id="US-SUN-FORMULA-ACTIVE-001",
            source_id=FDA_OTC_MONOGRAPHS,
        )

    if not result["approved"]:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED if sunscreen_scope else ExportReadinessStatus.NOT_ASSESSED
        return _item(
            "formula",
            ExportReadinessCategory.FORMULA,
            status,
            "활성성분 및 M020 경로",
            "전성분은 입력됐지만 자외선차단 활성성분을 결정적으로 식별하지 못했습니다.",
            "활성성분명(INCI/CAS/UNII), 함량, 제형을 확인하세요.",
            evidence=["입력 전성분 보유", "M020 활성성분 미식별"],
            rule_id="US-SUN-FORMULA-ACTIVE-001",
            source_id=FDA_OTC_MONOGRAPHS,
        )

    if any(canonical_name(name).lower() == "bemotrizinol" for name in result["approved"]):
        summary = "Bemotrizinol은 OTC000039에 추가됐지만 농도·조합·제형 조건과 적용 증빙을 별도로 확인해야 합니다."
        source_id = FDA_OTC000039
    else:
        summary = "입력된 자외선차단 활성성분이 현재 M020 데이터에서 확인됐지만 농도·조합·제형 조건의 증빙 검토가 필요합니다."
        source_id = FDA_OTC_MONOGRAPHS
    return _item(
        "formula",
        ExportReadinessCategory.FORMULA,
        ExportReadinessStatus.VERIFICATION_REQUIRED,
        "활성성분 및 M020 경로",
        summary,
        "최종 처방의 농도·허용 조합·제형과 원료 증빙을 전문가와 확인하세요.",
        evidence=result["approved"],
        rule_id="US-SUN-FORMULA-ACTIVE-001",
        source_id=source_id,
    )


def _testing_item(product: ExportProduct, sunscreen_scope: bool) -> ReadinessItem:
    fields = {
        "SPF": product.spf_test_report,
        "Broad Spectrum": product.broad_spectrum_test_report,
        "Water Resistance": product.water_resistance_test_report,
    }
    provided = [name for name, value in fields.items() if value is not None]
    missing = [name for name, value in fields.items() if value is False]
    if not provided:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary = "SPF·Broad Spectrum·Water Resistance 시험자료 보유 여부가 입력되지 않았습니다."
    elif missing:
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = f"다음 시험자료가 없다고 입력됐습니다: {', '.join(missing)}."
    else:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "시험자료가 있다고 입력됐지만 시험법·시험기관·원자료와 표시 claim의 연결은 확인하지 않았습니다."
    if not sunscreen_scope and not provided:
        status = ExportReadinessStatus.NOT_ASSESSED
    return _item(
        "testing",
        ExportReadinessCategory.TESTING,
        status,
        "선스크린 시험자료",
        summary,
        "해당 시험성적서의 시험법·기관·시험일·제품 처방을 확인하세요.",
        evidence=[f"{name}: {value}" for name, value in fields.items() if value is not None],
        rule_id="US-SUN-TEST-001",
        source_id=FDA_SUNSCREEN_GUIDANCE,
    )


def _labeling_item(product: ExportProduct, sunscreen_scope: bool) -> ReadinessItem:
    value = product.drug_facts_ready if product.drug_facts_ready is not None else product.us_label_ready
    if value is False:
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "미국용 Drug Facts 또는 라벨이 준비되지 않았다고 입력됐습니다."
    elif value is True:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "Drug Facts 또는 미국용 라벨이 준비됐지만 필수 항목·배치·가독성은 확인하지 않았습니다."
    else:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary = "미국용 Drug Facts 및 라벨 준비 여부가 입력되지 않았습니다."
    return _item(
        "labeling",
        ExportReadinessCategory.LABELING,
        status,
        "미국용 Drug Facts 라벨",
        summary,
        "Statement of Identity, Active Ingredients, Uses, Warnings, Directions 등 미국용 라벨을 준비·검토하세요.",
        evidence=[] if value is None else [f"라벨 준비 입력: {value}"],
        rule_id="US-SUN-LABEL-001",
        source_id=FDA_DRUG_FACTS,
    )


def _claims_item(text: str, product: ExportProduct) -> ReadinessItem:
    claims = _has_keyword(text, _CLAIM_KEYWORDS)
    reviewed = product.claims_reviewed
    if claims and reviewed is False:
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "자외선차단 관련 claim이 감지됐지만 미국용 claim 검토가 완료되지 않았습니다."
    elif claims:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "자외선차단 관련 claim이 감지됐습니다. 시험 근거와 미국용 표현의 맥락 검토가 필요합니다."
    elif reviewed is True:
        status = ExportReadinessStatus.COMPLIANT
        summary = "입력 문구에서 자외선차단 관련 claim은 감지되지 않았고, 사용자가 claim 검토 완료로 표시했습니다."
    elif reviewed is False:
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "미국용 claim 검토가 완료되지 않았습니다."
    else:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary = "광고 문구의 미국용 claim 검토 여부가 입력되지 않았습니다."
    return _item(
        "claims",
        ExportReadinessCategory.CLAIMS,
        status,
        "미국용 광고 claim",
        summary,
        "패키지·상세페이지·웹사이트의 claim별 시험 근거와 미국용 표현을 검토하세요.",
        evidence=["자외선차단 관련 claim 감지" if claims else "자외선차단 관련 claim 미감지"],
        rule_id="US-SUN-CLAIM-001",
        source_id=FDA_SUNSCREEN_GUIDANCE,
    )


def _profile_value(profile: ExportProfile, *names: str) -> Any:
    for name in names:
        value = getattr(profile, name, None)
        if _present(value):
            return value
    return None


def _establishment_item(profile: ExportProfile) -> ReadinessItem:
    fields = {
        "제조사": _profile_value(profile, "legal_manufacturer", "manufacturer_name"),
        "제조시설": _profile_value(profile, "manufacturing_site", "manufacturing_site_address"),
        "U.S. Agent": _profile_value(profile, "us_agent_name", "us_agent_contact"),
        "FDA 시설 등록": _profile_value(profile, "fda_establishment_registration", "fda_establishment_registration_number", "registration_status"),
        "CGMP": profile.cgmp_ready if profile.cgmp_ready is not None else profile.cgmp_readiness,
    }
    missing = [name for name, value in fields.items() if not _present(value)]
    if missing:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary = f"프로필에서 다음 시설 정보가 입력되지 않았습니다: {', '.join(missing)}."
    elif profile.cgmp_ready is False or _falsey(profile.cgmp_readiness):
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "CGMP 자료가 준비되지 않았다고 입력됐습니다."
    else:
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "시설·U.S. Agent·등록·CGMP 정보가 입력됐지만 FDA의 현재 상태와 증빙은 확인하지 않았습니다."
    return _item(
        "establishment",
        ExportReadinessCategory.ESTABLISHMENT,
        status,
        "제조시설·U.S. Agent·CGMP",
        summary,
        "제조시설 등록 상태, U.S. Agent 정보, CGMP 증빙을 확인하세요.",
        evidence=[f"{name}: 입력됨" for name, value in fields.items() if _present(value)],
        rule_id="US-SUN-ESTABLISHMENT-001",
        source_id=FDA_ESTABLISHMENT_REGISTRATION,
        profile_based=True,
    )


def _listing_import_item(profile: ExportProfile, product: ExportProduct) -> ReadinessItem:
    listing = product.drug_listing_ready
    if listing is None:
        listing = profile.drug_listing_status
    importer = _profile_value(profile, "importer_name", "importer_contact")
    registration = _profile_value(profile, "fda_establishment_registration", "fda_establishment_registration_number", "registration_status")
    if _falsey(listing):
        status = ExportReadinessStatus.REQUIRED_CHANGE
        summary = "Drug Listing이 준비되지 않았다고 입력됐습니다."
    elif _truthy(listing):
        status = ExportReadinessStatus.VERIFICATION_REQUIRED
        summary = "Drug Listing이 준비됐다고 입력됐지만 실제 listing·수입자·시설 등록 상태는 확인하지 않았습니다."
    else:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary = "Drug Listing 준비 여부가 입력되지 않았습니다."
    missing = []
    if not _present(importer):
        missing.append("수입자")
    if not _present(registration):
        missing.append("시설 등록")
    if missing and status != ExportReadinessStatus.REQUIRED_CHANGE:
        status = ExportReadinessStatus.NOT_ASSESSED
        summary += f" 다음 정보도 입력되지 않았습니다: {', '.join(missing)}."
    return _item(
        "listing_import",
        ExportReadinessCategory.LISTING_IMPORT,
        status,
        "Drug Listing·수입 준비",
        summary,
        "Drug Listing, 시설 등록, 미국 수입자와 통관 준비 정보를 확인하세요.",
        evidence=["수입자 입력됨"] if _present(importer) else [],
        rule_id="US-SUN-LISTING-001",
        source_id=FDA_DRUG_LISTING,
        profile_based=True,
    )


def build_us_export_readiness_report(
    *,
    ad_text: str | None,
    ingredients: str | None,
    product_name: str | None,
    product: ExportProduct,
    profile: ExportProfile,
    old_report: USPreflightReport | None = None,
    created_at: str,
) -> USExportReadinessReport:
    """제품·프로필 입력으로 항상 7개 카테고리의 준비도 항목을 만든다."""
    text = " ".join(
        value.strip()
        for value in (product_name, ad_text)
        if isinstance(value, str) and value.strip()
    )
    sunscreen_scope = (
        (product.intended_use or "").strip().lower() == "sunscreen"
        or _has_keyword(text, _SUNSCREEN_KEYWORDS)
        or old_report is not None
        and any(f.category.value == "OTC의약품_분류전환" for f in old_report.findings)
    )
    items = [
        _classification_item(text, product, old_report),
        _formula_item(_parse_ingredient_names(ingredients), product, sunscreen_scope),
        _testing_item(product, sunscreen_scope),
        _labeling_item(product, sunscreen_scope),
        _claims_item(text, product),
        _establishment_item(profile),
        _listing_import_item(profile, product),
    ]
    counts = {status: 0 for status in ExportReadinessStatus}
    for item in items:
        counts[item.status] += 1
    overall = max(items, key=lambda item: _STATUS_PRIORITY[item.status]).status
    return USExportReadinessReport(
        created_at=created_at,
        product_name=product_name,
        profile_snapshot=profile.model_copy(deep=True),
        product_snapshot=product.model_copy(deep=True),
        summary=ReadinessSummary(
            overall_status=overall,
            total=len(items),
            counts_by_status=counts,
        ),
        items=items,
        disclaimer=(
            "본 결과는 법적 자문이나 미국 수출 가능 여부의 최종판정이 아닙니다. "
            "입력자료와 결정적 MVP 규칙을 바탕으로 준비자료·추가확인 사항을 안내하며, "
            "FDA 실시간 등록 조회·NDC 제출·라벨 및 시험성적서의 완전한 법정 검토는 포함하지 않습니다."
        ),
    )
