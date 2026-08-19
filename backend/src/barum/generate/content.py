"""콘텐츠 생성·개선 오케스트레이션 (FR-11/13, improve + create).

improve: 원본 검사(findings) → 위반 조건표 치환 → 저위험 서술 LLM 생성 → PII 제거 →
이미지 배치·가드레일 → 생성물 재검증.
create: 원본 없이 인증서-인정문구 매칭으로 광고문구 조립(효능표현 자유창작 금지,
조건표 대신 인증서-인정문구 매칭이 소스) → 이하 동일.
judge·vlm을 주입받아 유닛테스트는 오프라인.
"""

from barum.generate.images import generate_module_images
from barum.generate.layout import (
    PRODUCT_SPEC_KIND,
    clinical_sections_text,
    ensure_product_spec_module,
    filter_risky_modules,
    plan_layout,
)
from barum.generate.replace import apply_replacements, build_replacements
from barum.models import (
    GenerateRequest,
    GenerateResponse,
    ImageGenResult,
    ImagePlan,
    LayoutModule,
    LayoutPlan,
    ModuleImage,
    PlacedImage,
    RecheckSummary,
    RiskConfirmation,
    Section,
    SkippedClaim,
    TableRow,
)
from barum.pipeline import run_check
from barum.reference.approved_claims import match_approved_claim
from barum.reference.impersonation import check_impersonation
from barum.reference.ingredients import match_ingredient_strict
from barum.reference.layout_references import infer_product_type, select_references
from barum.reference.pii import remove_pii

_DISCLAIMER = (
    "생성된 콘텐츠는 참고용이며, 최종 표시·광고 책임은 사업자에게 있습니다. "
    "효능·기능 표현은 기능성 심사·실증 자료를 확인하세요."
)

# 저위험 서술 전용 프롬프트. 효능·기능·치료 표현은 금지(그건 조건표가 따로 처리).
_SECTION_PROMPT = """너는 화장품 상세페이지의 '저위험 서술'만 작성한다.
효능·기능·치료·미백·주름·질병 관련 표현은 절대 쓰지 마라(그건 별도 처리된다).
아래 제품 정보로 제품개요·사용법·주의사항만 담백하고 사실적으로 써라.

제품명: {product_name}
전성분: {ingredients}
추가정보: {notes}

JSON으로만 답하라: {{"제품개요": "...", "사용법": "...", "주의사항": "..."}}"""

_SECTION_KINDS = ("제품개요", "사용법", "주의사항")

# create 모드 모듈별 저위험 서술 프롬프트. 계획된 모듈만큼 한 번에 받는다(호출 1회).
_MODULE_PROMPT = """너는 화장품 상세페이지의 '저위험 서술'만 작성한다.
효능·기능·치료·미백·주름·질병 관련 표현과 수치 주장은 절대 쓰지 마라(그건 별도 처리된다).

제품명: {product_name}
전성분: {ingredients}
추가정보: {notes}

아래 모듈마다 2~3문장씩 써라. kind는 그대로 돌려줘라.
{modules}

JSON으로만 답하라: {{"sections": [{{"kind": "모듈kind", "text": "..."}}]}}"""

_CLINICAL_DISCLAIMER = (
    "실증자료(시험 결과)는 사업자가 입력한 내용이며, barum은 그 진위를 검증하지 않습니다."
)


def _template_sections(req: GenerateRequest) -> list[Section]:
    """LLM 실패 시 폴백 표준 문구(기획서 '데모 큐레이션' 폴백)."""
    name = req.product_name or "본 제품"
    return [
        Section(kind="제품개요", text=f"{name}은(는) 일상 사용에 적합한 화장품입니다.", source="template"),
        Section(kind="사용법", text="적당량을 덜어 피부에 부드럽게 펴 발라 줍니다.", source="template"),
        Section(kind="주의사항", text="개봉 후 가급적 빠르게 사용하고, 사용 중 이상이 있으면 사용을 중단하세요.", source="template"),
    ]


def generate_sections(req: GenerateRequest, vlm) -> list[Section]:
    """LLM으로 저위험 서술 섹션을 만든다. 실패·빈 응답이면 템플릿 폴백.

    과금 호출이라 실패 시 재시도하지 않고 폴백(응답은 항상 나가게).
    """
    prompt = _SECTION_PROMPT.format(
        product_name=req.product_name or "(미상)",
        ingredients=req.ingredients or "(미상)",
        notes=req.notes or "(없음)",
    )
    try:
        res = vlm.generate_json(prompt, [])
        sections = []
        for kind in _SECTION_KINDS:
            text = (res.get(kind) or "").strip() if isinstance(res, dict) else ""
            if text:
                sections.append(Section(kind=kind, text=text, source="llm"))
        if sections:
            return sections
    except Exception as e:
        print(f"    [skip] 서술 생성 실패 → 템플릿 폴백: {type(e).__name__}: {e}")
    return _template_sections(req)


def generate_module_sections(
    req: GenerateRequest, modules: list[LayoutModule], vlm
) -> list[Section]:
    """계획된 모듈만큼 저위험 서술을 만든다(create 모드).

    위반소지 모듈은 여기 들어오지 않는다. 가드가 이미 걸렀고, 남은 위험 모듈의
    내용은 LLM이 아니라 검증된 인정문구·사업자 입력 실증자료로 채우기 때문이다.
    과금 호출이라 실패 시 재시도하지 않고 템플릿으로 폴백한다.
    """
    if not modules:
        return []
    listed = "\n".join(f"- {m.kind}: {m.purpose}" for m in modules)
    prompt = _MODULE_PROMPT.format(
        product_name=req.product_name or "(미상)",
        ingredients=req.ingredients or "(미상)",
        notes=req.notes or "(없음)",
        modules=listed,
    )
    try:
        res = vlm.generate_json(prompt, [])
        raw = res.get("sections", []) if isinstance(res, dict) else []
        by_kind = {
            str(s.get("kind", "")).strip(): str(s.get("text", "")).strip()
            for s in raw
            if isinstance(s, dict)
        }
        sections = [
            Section(kind=m.kind, text=by_kind[m.kind], source="llm")
            for m in modules
            if by_kind.get(m.kind)
        ]
        if sections:
            return sections
    except Exception as e:
        print(f"    [skip] 모듈 서술 생성 실패 → 템플릿 폴백: {type(e).__name__}: {e}")
    return _template_sections(req)


def build_image_plan(
    req: GenerateRequest,
    plan: LayoutPlan | None = None,
    image_generator=None,
    image_sink=None,
    photo_resolver=None,
) -> ImagePlan:
    """업로드 이미지 배치 + 생성요청 사칭 가드레일(FR-13).

    plan·image_generator를 주면 계획된 모듈마다 배경 이미지도 만든다(create 모드).
    안 주면 기존 동작 그대로다(배치·가드레일만, improve 모드 회귀 없음).

    image_sink: `(모듈kind, PNG바이트) -> 이미지 URL | None`. 저장은 여기서 하지 않고
    주입받는다(`content.py`는 저장소를 몰라야 오프라인 테스트가 된다. 실제 저장은
    `api/app.py`가 `storage/checks_store.py`로 한다).

    photo_resolver: `(product_photo_ids) -> 참조 이미지 바이트 목록`. image_sink와 같은
    이유로 저장소 접근은 여기서 안 하고 주입만 받는다. `generate_module_images`로
    그대로 넘긴다.
    """
    placed: list[PlacedImage] = []
    if req.result_id:
        placed.append(PlacedImage(slot="hero", image_url=f"/reports/{req.result_id}/image"))

    gen = ImageGenResult()
    ig = req.image_generation
    if ig and ig.requested:
        allowed, reason = check_impersonation(ig.prompt or "")
        gen = ImageGenResult(requested=True, allowed=allowed, reason=reason, ai_labeled=False)

    module_images: list[ModuleImage] = []
    if plan is not None and image_generator is not None:
        module_images, blobs = generate_module_images(
            plan, req, image_generator, photo_resolver=photo_resolver
        )
        _store_module_images(module_images, blobs, image_sink)
    return ImagePlan(placed=placed, generation=gen, module_images=module_images)


def _store_module_images(module_images: list[ModuleImage], blobs: dict, image_sink) -> None:
    """생성된 이미지를 싱크에 넘기고 URL을 채운다.

    싱크가 없거나 저장에 실패하면 그 사실을 남긴다. 과금해서 만든 이미지를 조용히
    버리면 "생성됐다"는 결과만 보고 실제로는 못 쓰는 상태가 된다.
    """
    for image in module_images:
        blob = blobs.get(image.module_kind)
        if image.status != "generated" or blob is None:
            continue
        if image_sink is None:
            image.reason = "저장소가 없어 생성된 이미지를 보관하지 못했습니다"
            continue
        try:
            image.image_url = image_sink(image.module_kind, blob)
        except Exception as e:
            print(f"    [skip] 이미지 저장 실패({image.module_kind}): {type(e).__name__}: {e}")
        if not image.image_url:
            image.reason = "이미지 저장에 실패해 보관되지 않았습니다"


def _strip_pii(sections: list[Section]) -> tuple[list[Section], set[str]]:
    """모든 섹션 텍스트에서 PII 제거. (정제된 섹션, 제거된 PII 종류) 반환."""
    pii_kinds: set[str] = set()
    cleaned: list[Section] = []
    for s in sections:
        text, kinds = remove_pii(s.text)
        pii_kinds.update(kinds)
        cleaned.append(Section(kind=s.kind, text=text, source=s.source, table_rows=s.table_rows))
    return cleaned, pii_kinds


def _recheck(sections: list[Section], req: GenerateRequest, judge) -> tuple[RecheckSummary, list[RiskConfirmation]]:
    """생성물을 재검증하고 (요약, 남은 위반 확인항목)을 낸다."""
    combined = " ".join(s.text for s in sections)
    rc = run_check("KR", combined, None, None, None, judge, ingredients=req.ingredients)
    recheck = RecheckSummary(
        safe=rc.summary.n_findings == 0,
        n_findings=rc.summary.n_findings,
        n_violation=rc.summary.n_violation,
        n_needs_review=rc.summary.n_needs_review,
    )
    risks = [
        RiskConfirmation(id=f"rc_{i}", text=f.sentence, reason=f.explanation)
        for i, f in enumerate(rc.findings)
    ]
    return recheck, risks


_CLAIM_CATEGORIES = ("미백", "주름개선", "자외선차단")


def build_approved_claim_sections(req: GenerateRequest) -> tuple[list[Section], list[SkippedClaim]]:
    """인증서-인정문구 매칭으로 광고문구 섹션을 조립한다(create 모드).

    카테고리마다 ① 인증서 매칭 ② 성분명 매칭 ③ 함량 명시 ④ 함량기준 충족을
    전부 통과해야 생성한다. 하나라도 실패하면 그 카테고리는 생성하지 않고
    사유를 `skipped_claims`로 명시한다(조용히 빠지지 않게).
    """
    amounts = [(ia.name, ia.amount) for ia in (req.ingredient_amounts or [])]
    sections: list[Section] = []
    skipped: list[SkippedClaim] = []
    for category in _CLAIM_CATEGORIES:
        phrase = match_approved_claim(category, req.certifications)
        if phrase is None:
            skipped.append(
                SkippedClaim(
                    category=category,
                    reason="인증서 매칭 실패 또는 해당 카테고리 인정문구가 아직 원문 대조 미완료(status != confirmed)",
                )
            )
            continue
        if match_ingredient_strict(category, amounts) is None:
            skipped.append(
                SkippedClaim(category=category, reason="성분명·함량 명시·함량기준 중 하나 이상 미충족")
            )
            continue
        sections.append(Section(kind="광고문구", text=phrase, source="approved_claim"))
    return sections, skipped


def build_product_spec_section(req: GenerateRequest) -> Section:
    """제형·용량으로 상품 스펙표 섹션을 만든다(table_info layout_type 전용).

    LLM을 안 태운다. 사업자가 입력한 값을 그대로 표로 옮길 뿐이라 지어낼 게 없다.
    호출 전에 formulation_type·volume 중 하나는 있다고 가정한다(둘 다 없으면
    ensure_product_spec_module이 애초에 이 모듈을 계획에 안 넣는다).
    """
    rows = []
    if req.formulation_type:
        rows.append(TableRow(label="제형", value=req.formulation_type))
    if req.volume:
        rows.append(TableRow(label="용량", value=req.volume))
    return Section(kind=PRODUCT_SPEC_KIND, text="", source="product_spec", table_rows=rows)


def _generate_improve_content(req: GenerateRequest, *, judge, vlm) -> GenerateResponse:
    """개선 모드 오케스트레이션. judge·vlm 주입(테스트는 StubJudge+가짜LLM)."""
    # 1. 원본 검사 → 위반 findings
    initial = run_check("KR", req.content, None, None, None, judge, ingredients=req.ingredients)
    # 2. 위반 문구 조건표 치환
    reps = build_replacements(initial.findings)
    safe_content = apply_replacements(req.content, reps)
    # 3. 섹션 조립: 개선된 원문(광고문구) + LLM 저위험 서술
    sections = [
        Section(kind="광고문구", text=safe_content, source="remediation" if reps else "template")
    ]
    sections += generate_sections(req, vlm)
    # 4. PII 제거
    cleaned, pii_kinds = _strip_pii(sections)
    # 5. 이미지 배치·가드레일
    image_plan = build_image_plan(req)
    # 6. 생성물 재검증
    recheck, risks = _recheck(cleaned, req, judge)
    return GenerateResponse(
        sections=cleaned,
        replacements=reps,
        image_plan=image_plan,
        pii_removed=sorted(pii_kinds),
        risk_confirmations=risks,
        recheck=recheck,
        disclaimer=_DISCLAIMER,
    )


def _generate_create_content(
    req: GenerateRequest, *, judge, vlm, image_generator=None, image_sink=None, photo_resolver=None
) -> GenerateResponse:
    """신규 생성(create) 모드 오케스트레이션. 원본 검사 없음, replacements 항상 빈 배열.

    레이아웃 레퍼런스를 퓨샷으로 모듈 구성을 계획한 뒤, 모듈 종류에 따라 내용을 채운다.
    효능·수치는 LLM이 쓰지 않는다. 검증된 인정문구나 사업자 입력 실증자료를 그대로 쓴다.
    """
    # 1. 광고문구: 인증서-인정문구 매칭(자유창작 없음)
    claim_sections, skipped = build_approved_claim_sections(req)
    evidence = req.clinical_evidence or []

    # 2. 모듈 구성 계획 + 근거 없는 위험 모듈 제거
    product_type = infer_product_type(req.product_name)
    plan = plan_layout(req, select_references(product_type), product_type, vlm)
    plan, plan_skipped = filter_risky_modules(
        plan,
        has_approved_claim=bool(claim_sections),
        has_clinical_evidence=bool(evidence),
    )
    skipped += plan_skipped
    plan = ensure_product_spec_module(plan, req)

    # 3. 모듈별 내용 채우기. 위험 모듈은 LLM을 안 태운다.
    #    임상 모듈이 여러 개여도 실증자료 섹션은 하나만 낸다(같은 자료 반복 방지).
    #    product_spec도 LLM을 안 태운다. 사업자 입력값을 표로 그대로 옮길 뿐이다.
    safe_modules = [m for m in plan.modules if not m.has_claim_risk and m.kind != PRODUCT_SPEC_KIND]
    clinical_planned = any(m.kind.startswith("clinical") for m in plan.modules)
    product_spec_planned = any(m.kind == PRODUCT_SPEC_KIND for m in plan.modules)
    sections = list(claim_sections)
    if clinical_planned and evidence:
        sections.append(
            Section(kind="실증자료", text=clinical_sections_text(evidence), source="clinical_evidence")
        )
    if product_spec_planned:
        sections.append(build_product_spec_section(req))
    sections += generate_module_sections(req, safe_modules, vlm)

    # 4. PII 제거
    cleaned, pii_kinds = _strip_pii(sections)
    # 5. 이미지 배치·가드레일 + 모듈별 배경 이미지 생성
    image_plan = build_image_plan(req, plan, image_generator, image_sink, photo_resolver)
    # 6. 생성물 재검증
    recheck, risks = _recheck(cleaned, req, judge)
    # 7. 실증자료는 미검증이라 사용자 확인 항목으로 남긴다
    disclaimer = _DISCLAIMER
    if evidence:
        risks.append(
            RiskConfirmation(
                id="rc_clinical_evidence",
                text=clinical_sections_text(evidence),
                reason="사업자가 입력한 실증자료입니다. barum은 진위를 검증하지 않으니 사실인지 다시 확인하세요.",
            )
        )
        disclaimer = f"{disclaimer} {_CLINICAL_DISCLAIMER}"

    return GenerateResponse(
        sections=cleaned,
        replacements=[],
        image_plan=image_plan,
        pii_removed=sorted(pii_kinds),
        risk_confirmations=risks,
        skipped_claims=skipped,
        layout_plan=plan,
        recheck=recheck,
        disclaimer=disclaimer,
    )


def generate_content(
    req: GenerateRequest, *, judge, vlm, image_generator=None, image_sink=None, photo_resolver=None
) -> GenerateResponse:
    """`POST /generate` 오케스트레이션. `req.mode`로 improve/create 분기.

    image_generator·image_sink·photo_resolver는 create 모드에서만 쓴다.
    image_generator를 안 주면 이미지 생성을 건너뛴다(모델 확정 전까지 기본 비활성).
    photo_resolver는 판매자가 올린 제품사진(req.product_photo_ids)을 참조 이미지로
    바꿔주는 콜백이다(AI 배경·연출 합성). 안 주면 참조 없이 배경만 생성한다.
    """
    if req.mode == "create":
        return _generate_create_content(
            req,
            judge=judge,
            vlm=vlm,
            image_generator=image_generator,
            image_sink=image_sink,
            photo_resolver=photo_resolver,
        )
    return _generate_improve_content(req, judge=judge, vlm=vlm)
