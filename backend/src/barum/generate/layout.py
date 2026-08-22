"""상세페이지 모듈 구조 플래너 (FR-11 create 모드).

레이아웃 레퍼런스를 퓨샷 예시로 넣고, 이번 상품엔 어떤 모듈을 어떤 순서로 넣을지
LLM이 계획하게 한다. 계획은 **구조만** 정한다. 실제 문구는 여기서 쓰지 않는다.

위반소지 모듈(has_claim_risk)은 LLM 판단을 믿지 않고 코드로 걸러낸다. 근거가
없으면 계획에서 빼고 사유를 남긴다(조용히 빠지지 않게).
"""

import re

from barum.models import ClinicalEvidence, GenerateRequest, LayoutModule, LayoutPlan, SkippedClaim
from barum.reference.layout_references import load_layout_vocabulary

# 근거 없이도 안전한 기본 구성. LLM 계획이 실패하면 이걸로 간다.
# layout_type은 어휘집(_vocabulary.json) 12종 카탈로그 중 각 모듈 성격에 맞는 걸 배정했다
# (2026-08-19, 냐냐·PM 확인). 이래야 LLM 플래너를 안 타는 폴백 경로에서도 프론트가
# 항상 layout_type을 받는다.
_FALLBACK_MODULES: tuple[tuple[str, str, str], ...] = (
    ("hero_intro", "제품 도입부", "hero_fullbleed"),
    ("ingredient_highlight", "핵심 성분 소개", "image_text_split"),
    ("texture", "제형·발림성 소개", "mood_macro"),
    ("how_to_use", "사용법 안내", "step_list"),
    ("target_audience", "추천 대상 소개", "icon_grid"),
    ("caution", "사용 시 주의사항", "table_info"),
)

# 임상 계열 모듈. 기능성 인증서로는 못 받치고 실증자료가 있어야 한다.
_CLINICAL_PREFIX = "clinical"

# 상품 스펙표(제형·용량) 모듈 kind. LLM 퓨샷 예시엔 이 kind가 없어서(8건 레퍼런스에
# 없는 개념) 플래너가 스스로 못 만든다. req에 데이터가 있으면 계획에 결정적으로
# 끼워넣는다(2026-08-19, 팀장 확정: table_info 지원 범위 = 제형·용량만).
PRODUCT_SPEC_KIND = "product_spec"

# LLM이 카탈로그 밖 값을 내거나 layout_type을 빠뜨렸을 때 쓰는 안전한 기본값.
# 텍스트 블록 하나짜리라 어떤 모듈에 붙어도 어색하지 않다.
_DEFAULT_LAYOUT_TYPE = "section_statement"

_PLAN_PROMPT = """너는 화장품 상세페이지의 구조를 설계한다.
아래는 실제 상세페이지들의 모듈 구성 예시다.

{examples}

이번 상품:
- 상품명: {product_name}
- 종류: {product_type}
- 추가정보: {notes}

위 예시를 참고해 이번 상품의 상세페이지 모듈 구성을 순서대로 제안하라.

각 모듈의 layout_type은 반드시 아래 카탈로그 중 하나로 골라라:
{layout_type_catalog}

규칙:
- 구조만 정한다. 실제 광고 카피나 수치는 절대 쓰지 마라.
- kind는 예시에 나온 것을 우선 쓴다.
- 효능·수치·시험결과를 주장하는 모듈은 has_claim_risk를 true로 표시하라.
- layout_type은 위 카탈로그에 있는 값만 써라. 카탈로그에 없는 값은 안 된다.
- 6~12개 모듈이 적당하다.

JSON으로만 답하라:
{{"modules": [{{"kind": "...", "purpose": "...", "has_claim_risk": false, "layout_type": "..."}}]}}"""


def _layout_type_catalog() -> dict[str, str]:
    """어휘집의 layout_type 12종 카탈로그(키→설명)를 낸다."""
    return load_layout_vocabulary()["layout_types"]


def _format_layout_type_catalog() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in _layout_type_catalog().items())


def _valid_layout_type(value) -> str:
    """카탈로그에 있는 값만 그대로 쓰고, 아니면 안전한 기본값으로 바꾼다."""
    v = str(value).strip() if value else ""
    return v if v in _layout_type_catalog() else _DEFAULT_LAYOUT_TYPE


def _format_examples(refs: list[dict]) -> str:
    """레퍼런스를 퓨샷 예시 텍스트로 만든다. 구조만 넣는다(카피·수치는 원래 없다)."""
    blocks = []
    for ref in refs:
        lines = [f"[예시: {ref.get('product_type', '?')}]"]
        for module in ref.get("modules", []):
            risk = "위반소지있음" if module.get("has_claim_risk") else "안전"
            layout_type = module.get("layout_type", _DEFAULT_LAYOUT_TYPE)
            lines.append(f"- {module['kind']} / {module['purpose']} / {risk} / layout_type={layout_type}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _uniquify_kinds(modules: list[LayoutModule]) -> list[LayoutModule]:
    """중복된 kind에 순번을 붙여 유일하게 만든다.

    **kind는 파이프라인 전체에서 모듈의 식별자로 쓰인다.** 생성 이미지를 담는
    `blobs[module.kind]`(images.py), 저장 후 URL 매핑(`_store_module_images`),
    프론트의 `moduleImageDataUris[s.kind]`가 전부 kind로 찾는다. 그런데 kind는
    LLM이 자유롭게 짓는 문자열이라 유일성이 보장되지 않는다.

    실제로 플래너가 `clinical_result`를 두 개 낸 적이 있고(2026-08-20 실측),
    두 번째 이미지가 첫 번째를 덮어써서 **과금해서 만든 첫 이미지가 버려지고
    화면엔 같은 사진이 두 번** 나왔다. 여기서 미리 갈라둔다.

    `clinical` 접두사 판정(`filter_risky_modules`)은 startswith라 순번이 붙어도
    그대로 동작한다.
    """
    seen: dict[str, int] = {}
    out: list[LayoutModule] = []
    for module in modules:
        count = seen.get(module.kind, 0)
        seen[module.kind] = count + 1
        if count == 0:
            out.append(module)
            continue
        out.append(
            LayoutModule(
                kind=f"{module.kind}_{count + 1}",
                purpose=module.purpose,
                has_claim_risk=module.has_claim_risk,
                layout_type=module.layout_type,
            )
        )
    return out


def _fallback_plan(product_type: str | None) -> LayoutPlan:
    """LLM 없이 쓰는 고정 플랜. 전부 위반소지 없는 모듈이라 근거가 필요없다."""
    return LayoutPlan(
        modules=[
            LayoutModule(kind=k, purpose=p, has_claim_risk=False, layout_type=lt)
            for k, p, lt in _FALLBACK_MODULES
        ],
        product_type=product_type,
        source="fallback",
    )


def plan_layout(req: GenerateRequest, refs: list[dict], product_type: str | None, vlm) -> LayoutPlan:
    """퓨샷 레퍼런스로 이번 상품의 모듈 구성을 계획한다.

    과금 호출이라 실패 시 재시도하지 않고 폴백 플랜으로 넘어간다(응답은 항상 나가게).
    """
    if not refs:
        return _fallback_plan(product_type)

    prompt = _PLAN_PROMPT.format(
        examples=_format_examples(refs),
        product_name=req.product_name or "(미상)",
        product_type=product_type or "(미상)",
        notes=req.notes or "(없음)",
        layout_type_catalog=_format_layout_type_catalog(),
    )
    try:
        res = vlm.generate_json(prompt, [])
        raw = res.get("modules", []) if isinstance(res, dict) else []
        modules = [
            LayoutModule(
                kind=str(m["kind"]).strip(),
                purpose=str(m.get("purpose", "")).strip(),
                has_claim_risk=bool(m.get("has_claim_risk", False)),
                layout_type=_valid_layout_type(m.get("layout_type")),
            )
            for m in raw
            if isinstance(m, dict) and str(m.get("kind", "")).strip()
        ]
        if modules:
            return LayoutPlan(
                modules=_uniquify_kinds(modules), product_type=product_type, source="planner"
            )
    except Exception as e:
        print(f"    [skip] 레이아웃 계획 실패 → 폴백 플랜: {type(e).__name__}: {e}")
    return _fallback_plan(product_type)


# 근거가 없어 빠질 때, 같은 자리를 대신 채울 안전한 모듈. 효능 주장을 뺀 버전이다.
#
# 왜 필요한가: 근거 없는 상품은 hero_intro가 통째로 사라져서 도입부 없이 cause_explain부터
# 시작하는 페이지가 나왔다(2026-08-20 A/B 실측: 근거없음 7모듈 vs 근거있음 11모듈, 히어로
# 소실). 모듈이 줄어드는 건 원칙대로지만, 도입부가 없는 건 빈약한 게 아니라 구조가 깨진
# 것이다(팀장·PM 확인).
#
# **효능 주장을 대신 만들어주는 게 아니다.** 주장은 그대로 빠지고 skipped_claims에 남는다.
# 여기서 넣는 건 주장이 없는 자리표시 모듈뿐이다(제품 소개·분위기컷). 그래서
# has_claim_risk=False다.
#
# 히어로만 대상으로 둔다. 나머지(value_prop·bundle_suggestion 등)는 없어도 페이지가
# 성립하지만, 도입부 없는 상세페이지는 성립하지 않는다.
_SAFE_REPLACEMENTS: dict[str, tuple[str, str]] = {
    "hero_intro": ("제품 도입부(효능 주장 없이 제품 소개만)", "hero_fullbleed"),
}


def _safe_replacement(module: LayoutModule) -> LayoutModule | None:
    """근거 부족으로 빠지는 모듈을 대신할 안전한 모듈을 낸다. 대상이 아니면 None."""
    entry = _SAFE_REPLACEMENTS.get(module.kind)
    if entry is None:
        return None
    purpose, layout_type = entry
    return LayoutModule(
        kind=module.kind,
        purpose=purpose,
        has_claim_risk=False,
        layout_type=module.layout_type or layout_type,
    )


def filter_risky_modules(
    plan: LayoutPlan, *, has_approved_claim: bool, has_clinical_evidence: bool
) -> tuple[LayoutPlan, list[SkippedClaim]]:
    """위반소지 모듈 중 근거 없는 것을 계획에서 뺀다.

    **근거는 주장 종류에 맞는 것만 인정한다.** 아무 근거나 있다고 아무 주장이나
    통과시키면, 계획에는 남았는데 채울 내용이 없는 빈 모듈이 생긴다.

    - 임상 계열(clinical_*)은 실증자료라야 한다. "미백 기능성 인증"은 "미백에 도움"
      표현의 근거일 뿐 "다크스팟 87% 개선" 같은 구체 수치의 근거가 아니다.
    - 그 외 위반소지 모듈(value_prop 등)은 검증된 인정문구라야 한다. 실증자료는
      임상 수치의 근거일 뿐 일반 효능 주장의 근거가 아니다.

    통과한 모듈의 내용은 LLM이 아니라 각각 실증자료 섹션·인정문구 섹션이 채운다.
    """
    kept: list[LayoutModule] = []
    skipped: list[SkippedClaim] = []
    for module in plan.modules:
        if not module.has_claim_risk:
            kept.append(module)
            continue
        if module.kind.startswith(_CLINICAL_PREFIX):
            if has_clinical_evidence:
                kept.append(module)
            else:
                skipped.append(
                    SkippedClaim(
                        category=module.kind,
                        reason="실증자료(인체적용시험 결과)가 입력되지 않아 임상 수치 모듈을 뺐습니다",
                    )
                )
            continue
        if has_approved_claim:
            kept.append(module)
            continue
        skipped.append(
            SkippedClaim(
                category=module.kind,
                reason="기능성 인증서로 뒷받침되는 인정문구가 없어 효능 주장 모듈을 뺐습니다",
            )
        )
        replacement = _safe_replacement(module)
        if replacement is not None:
            kept.append(replacement)
    filtered = LayoutPlan(modules=kept, product_type=plan.product_type, source=plan.source)
    return filtered, skipped


def ensure_product_spec_module(plan: LayoutPlan, req: GenerateRequest) -> LayoutPlan:
    """제형·용량 데이터가 있으면 상품 스펙표 모듈을 계획에 끼워넣는다.

    둘 다 없으면 아무것도 안 한다(채울 내용 없는 빈 테이블을 만들지 않는다,
    filter_risky_modules와 같은 원칙). 이미 같은 kind가 있으면 중복 추가 안 함.
    """
    if not (req.formulation_type or req.volume):
        return plan
    if any(m.kind == PRODUCT_SPEC_KIND for m in plan.modules):
        return plan
    module = LayoutModule(
        kind=PRODUCT_SPEC_KIND, purpose="상품 기본 정보", has_claim_risk=False, layout_type="table_info"
    )
    return LayoutPlan(modules=[*plan.modules, module], product_type=plan.product_type, source=plan.source)


def clinical_sections_text(evidence: list[ClinicalEvidence]) -> str:
    """실증자료를 그대로 문장으로 만든다. LLM을 태우지 않는다(수치를 지어낼 여지 제거)."""
    parts = []
    for e in evidence:
        text = f"{e.claim} {e.value}"
        if e.period:
            text += f" ({e.period})"
        if e.institution:
            text += f", {e.institution} 시험"
        if e.note:
            text += f". {e.note}"
        parts.append(text)
    return " / ".join(parts)


# 카드로 낼 모듈 우선순위. 레퍼런스 팩 8종을 실측해 정했다(2026-08-22).
#   kind                  등장   평균위치
#   hero_intro            5/8    0.06
#   ingredient_highlight  5/8    0.31
#   clinical_result       10회   0.50
#   how_to_use            3/8    0.70
#   caution               3/8    1.00
#   texture_visual        2/8    0.00
# 레퍼런스 모듈 수 평균이 7.2개라 5~6장으로 줄이는 건 무리한 축소가 아니다.
_CARD_PRIORITY: tuple[str, ...] = (
    "hero_intro",
    "texture_visual",
    "ingredient_highlight",
    "clinical_result",
    "how_to_use",
    "caution",
)
CARD_LIMIT = 6


def _priority_rank(kind: str) -> int:
    """우선순위 순번. 목록에 없으면 맨 뒤(같은 값이면 계획 순서가 tiebreak)."""
    # `_uniquify_kinds`가 붙인 순번(clinical_result_2)을 떼고 본다.
    base = re.sub(r"_\d+$", "", kind)
    for i, k in enumerate(_CARD_PRIORITY):
        if base == k or base.startswith(k):
            return i
    return len(_CARD_PRIORITY)


def select_top_modules(
    plan: LayoutPlan, limit: int = CARD_LIMIT, *, protected: tuple[str, ...] = ()
) -> tuple[LayoutPlan, list[SkippedClaim]]:
    """카드 수만큼 모듈을 추린다. **무엇을 남길지만 고르고 계획 순서는 안 건드린다.**

    플래너는 보통 6~12개를 낸다. 카드는 이미지 1장 + 문장 1개라 그대로 다 내면
    화면이 늘어진다(팀장 확정 2026-08-22, 5~6장).

    **반드시 위험 모듈 필터(`filter_risky_modules`·`_drop_unfilled_risky_modules`)
    뒤에 부른다.** 먼저 6개를 고른 뒤에 거르면 근거 없는 임상 모듈이 빠지면서
    카드가 4장으로 줄어든다.

    **이미지 생성 앞에서도 불러야 한다.** 뒤에서 부르면 버릴 모듈의 배경 이미지까지
    과금해서 만든 뒤 버리게 된다.

    protected: 이미 내용이 붙은 모듈 kind(인정문구·실증자료가 연결된 것). 우선순위가
    낮아도 안 버린다. 버리면 만들어둔 섹션이 갈 곳을 잃는다.
    """
    if len(plan.modules) <= limit:
        return plan, []

    protected_set = set(protected)
    ordered = sorted(
        enumerate(plan.modules),
        key=lambda pair: (
            0 if pair[1].kind in protected_set else 1,
            _priority_rank(pair[1].kind),
            pair[0],  # 동점이면 계획 순서가 이긴다
        ),
    )
    keep_idx = {i for i, _ in ordered[:limit]}
    kept = [m for i, m in enumerate(plan.modules) if i in keep_idx]
    dropped = [m for i, m in enumerate(plan.modules) if i not in keep_idx]
    skipped = [
        SkippedClaim(category=m.kind, reason=f"카드 {limit}장으로 추리면서 제외했습니다.")
        for m in dropped
    ]
    return (
        LayoutPlan(modules=kept, product_type=plan.product_type, source=plan.source),
        skipped,
    )
