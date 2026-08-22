"""콘텐츠 생성·개선 오케스트레이션 (FR-11/13, improve + create).

improve: 원본 검사(findings) → 위반 조건표 치환 → 저위험 서술 LLM 생성 → PII 제거 →
이미지 배치·가드레일 → 생성물 재검증.
create: 원본 없이 인증서-인정문구 매칭으로 광고문구 조립(효능표현 자유창작 금지,
조건표 대신 인증서-인정문구 매칭이 소스) → 이하 동일.
judge·vlm을 주입받아 유닛테스트는 오프라인.
"""

import re

from barum.generate.images import generate_canvas_background, generate_module_images
from barum.reference.presets import apply_preset, audience_hint
from barum.generate.layout import (
    PRODUCT_SPEC_KIND,
    clinical_sections_text,
    ensure_product_spec_module,
    filter_risky_modules,
    plan_layout,
    select_top_modules,
)
from barum.generate.replace import apply_replacements, build_replacements
from barum.models import (
    ContentCard,
    GenerateRequest,
    GenerateResponse,
    ImageGenResult,
    CanvasBackground,
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
from barum.reference.survey import is_efficacy_survey, survey_sentence

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
#
# 헤드라인 길이 제약(20자)은 디디(디자이너)가 설화수 레퍼런스 15개 헤드라인을 실측한
# 값이다: 12~31자, 대부분 15~25자, 전부 1줄(2026-08-20). **레퍼런스 JSON에는 실제 카피가
# 없어서(kind/purpose/layout_type만) 우리 데이터로는 재현 검증이 안 된다** — 디디가 실제
# 페이지를 직접 잰 값이다.
#
# 우리 생성물은 첫 문장이 56자·5줄까지 나와서 헤드라인 구실을 못 했다(팀장 지적).
# headline/subcopy가 스키마로 분리돼 있지 않고 프론트가 첫 문장을 정규식으로 잘라 쓰는
# 구조라, 지금은 프롬프트로 길이를 강제한다. 안 지켜지면 스키마 분리(B안,
# memory `barum-structured-section-content-gap`)로 간다.
_MODULE_PROMPT = """너는 화장품 상세페이지의 '저위험 서술'만 작성한다.
효능·기능·치료·미백·주름·질병 관련 표현과 수치 주장은 절대 쓰지 마라(그건 별도 처리된다).

제품명: {product_name}
전성분: {ingredients}
추가정보: {notes}
{audience}

아래 모듈마다 써라. kind는 그대로 돌려줘라.
{modules}

**모듈 설명은 무엇을 다루는지 알려줄 뿐이다. 배치·이미지 구성을 문장으로 옮기지 마라.**
고객이 읽을 카피만 써라. "비주얼:", "이미지:", "설명:", "아이콘 그리드:", "좌우 배치"
같은 말은 쓰지 않는다. 그건 화면이 알아서 하고, 여기 쓰면 고객에게 그대로 보인다.

**문장 구조를 반드시 지켜라. 프론트가 첫 문장을 헤드라인으로 크게 키워 쓴다.**
- **첫 문장은 20자 이내의 짧은 한 마디**여야 한다. 설명하지 말고 던져라.
  좋은 예: "속기미, 왜 생길까요?" / "발림성부터 다릅니다" / "이렇게 쓰세요"
  나쁜 예: "칙칙함이나 속기미는 수면, 스트레스, 외부 환경 등 여러 요인으로 인해
  피부 표면에서 나타나는 현상일 수 있습니다." (설명을 첫 문장에 넣었다)
- 설명은 **두 번째 문장부터** 2~3문장으로 쓴다.
- 첫 문장이 길면 상세페이지에서 큰 글씨가 다섯 줄로 흘러 헤드라인 구실을 못 한다.

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
        # 프리셋의 타겟팅만. 레이아웃 방향은 여기 넣으면 안 된다 — 지시문이 그대로
        # 카피로 새어나온다(presets.audience_hint docstring에 실측 결과).
        audience=audience_hint(req),
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
            Section(kind=m.kind, text=by_kind[m.kind], source="llm", module_kind=m.kind)
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
    canvas: CanvasBackground | None = None
    if plan is not None and image_generator is not None:
        module_images, blobs = generate_module_images(
            plan, req, image_generator, photo_resolver=photo_resolver
        )
        _store_module_images(module_images, blobs, image_sink)
        # 긴 배경은 옵트인이다. 모듈 이미지를 대신하지 않고 더해지므로 과금이 는다.
        if ig and ig.canvas_requested:
            canvas, canvas_blob = generate_canvas_background(req, plan.product_type, image_generator)
            _store_canvas(canvas, canvas_blob, image_sink)
    return ImagePlan(placed=placed, generation=gen, module_images=module_images, canvas=canvas)


def _store_canvas(canvas: CanvasBackground | None, blob: bytes | None, image_sink) -> None:
    """긴 배경 이미지를 싱크에 넘기고 URL을 채운다.

    `_store_module_images`와 같은 원칙: 과금해서 만든 걸 조용히 버리지 않고, 못
    보관했으면 그 사실을 reason에 남긴다.
    """
    if canvas is None or blob is None or canvas.status != "generated":
        return
    if image_sink is None:
        canvas.reason = "저장소가 없어 생성된 배경 이미지를 보관하지 못했습니다"
        return
    try:
        canvas.image_url = image_sink("_canvas", blob)
    except Exception as e:
        print(f"    [skip] 배경 이미지 저장 실패: {type(e).__name__}: {e}")
    if not canvas.image_url:
        canvas.reason = "배경 이미지 저장에 실패해 보관되지 않았습니다"


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
        # 필드를 하나씩 나열해 재조립하면 새 필드가 추가될 때마다 여기서 조용히
        # 유실된다. 실제로 module_kind가 그렇게 떨어져 나갔다(2026-08-20). 텍스트만
        # 갈아끼우는 방식으로 바꿔 앞으로 필드가 늘어도 자동으로 따라가게 한다.
        cleaned.append(s.model_copy(update={"text": text}))
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


def _link_risky_module_sections(sections: list[Section], plan: LayoutPlan) -> None:
    """위반소지 모듈이 채워진 섹션에 원래 모듈 kind를 달아준다(제자리 수정).

    **왜 필요한가**: 위반소지 모듈(hero_intro·value_prop·clinical_*)은 근거가 있어
    계획에 남아도, 그 내용을 LLM이 쓰지 않는다. 인정문구가 채우면 섹션 kind가
    "광고문구", 실증자료가 채우면 "실증자료"로 나온다. 그런데 프론트는 모듈 이미지를
    `moduleImageDataUris[section.kind]`로 찾는다. kind가 안 맞으니 **그 모듈들의
    이미지가 통째로 버려졌다.**

    2026-08-20 실측: 6장을 과금해서 만들었는데 실제로 상세페이지에 들어간 건 2장이고
    hero_intro·value_prop·clinical_intro·clinical_result 4장이 버려졌다. 히어로
    이미지가 있는데도 페이지가 텍스트로 시작했다.

    PR #215(중복 kind가 이미지를 덮어쓰던 문제)와 같은 계열이다. kind를 모듈 식별자로
    쓰는 구조의 구멍이라, 섹션이 자기가 어느 모듈 자리인지 알게 해서 막는다.

    계획 순서대로 짝짓는다. 임상 계열은 실증자료 섹션 하나가 대표하므로 첫 임상
    모듈에만 붙인다(실증자료 섹션은 하나만 나온다).
    """
    claim_slots = [m for m in plan.modules if m.has_claim_risk and not m.kind.startswith("clinical")]
    clinical_slots = [m for m in plan.modules if m.has_claim_risk and m.kind.startswith("clinical")]
    claim_iter = iter(claim_slots)
    for section in sections:
        if section.module_kind is not None:
            continue
        if section.source == "approved_claim":
            module = next(claim_iter, None)
            if module is not None:
                section.module_kind = module.kind
        elif section.source == "clinical_evidence" and clinical_slots:
            section.module_kind = clinical_slots[0].kind


def _drop_unfilled_risky_modules(
    plan: LayoutPlan, sections: list[Section]
) -> tuple[LayoutPlan, list[SkippedClaim]]:
    """내용이 안 채워진 위반소지 모듈을 계획에서 뺀다.

    `filter_risky_modules`의 게이트는 "인정문구가 하나라도 있나"라는 **불리언**이라,
    인정문구가 2개인데 위반소지 모듈이 3개면 셋 다 통과한다. 그런데 실제로 채울
    문구는 2개뿐이라 세 번째는 **내용이 아예 없는 빈 모듈**이 된다.

    빈 모듈은 화면에 안 나오는데 이미지 생성 대상에는 들어가서, 과금해놓고 버려진다
    (2026-08-20 실측: persistence_claim이 그렇게 남았다). 여기서 미리 뺀다.

    반드시 `_link_risky_module_sections` 뒤, `build_image_plan` 앞에 불러야 한다.
    """
    filled = {s.module_kind for s in sections if s.module_kind}
    kept: list[LayoutModule] = []
    skipped: list[SkippedClaim] = []
    for module in plan.modules:
        if module.has_claim_risk and module.kind not in filled:
            skipped.append(
                SkippedClaim(
                    category=module.kind,
                    reason="이 모듈을 채울 인정문구·실증자료가 부족해 계획에서 뺐습니다",
                )
            )
            continue
        kept.append(module)
    return LayoutPlan(modules=kept, product_type=plan.product_type, source=plan.source), skipped


def _usable_surveys(req: GenerateRequest) -> tuple[list, list[SkippedClaim]]:
    """설문조사 입력 중 실제로 쓸 수 있는 것만 고른다.

    피부 변화(효능)를 주장하는 설문은 뺀다. [별표2]가 효능·효과 주장의 실증 수단으로
    인체적용시험·인체외시험만 인정하고 설문은 인정하지 않기 때문이다. 뺀 건 조용히
    사라지지 않게 `skipped_claims`에 사유를 남긴다(인정문구·임상 모듈과 같은 원칙).
    """
    usable = []
    skipped: list[SkippedClaim] = []
    for survey in req.survey_evidence or []:
        if is_efficacy_survey(survey.claim):
            skipped.append(
                SkippedClaim(
                    category="설문조사",
                    reason=f'"{survey.claim}"은 피부 변화(효능) 주장이라 설문조사로는 쓸 수 없습니다. '
                    "효능·효과는 인체적용시험 등 실증자료라야 합니다(관리지침 [별표2] 2.).",
                )
            )
            continue
        usable.append(survey)
    return usable, skipped


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
    # 2. 위반 문구 치환. 조건표가 방향을 정하고 LLM이 문장을 다듬는다.
    #    LLM이 "대체할 수 없다"고 본 문구(유통 채널 안내·제품명 등)는 제안 자체를 안 낸다.
    reps = build_replacements(initial.findings, rewriter=vlm)
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


# 첫 문장을 헤드라인으로 떼는 규칙. 프론트 `splitHeadline`과 같은 규칙이라
# 백엔드·프론트가 다르게 쪼개지 않는다.
# **마침표 뒤 숫자는 문장 끝이 아니라 소수점이다.** 이 예외가 없으면 실증자료
# "23.5% 개선"이 "…23." + "5% 개선…"으로 쪼개져 사업자 입력 수치가 왜곡된다
# (2026-08-20 실측). barum은 실증 수치를 LLM에도 안 태우고 그대로 싣는 게 원칙인데
# 렌더 단계에서 깨지고 있었다.
_HEADLINE_SPLIT = re.compile(r"^([\s\S]+?[.!?](?!\d))\s*([\s\S]*)$")


def split_headline(text: str) -> tuple[str, str]:
    """카드 문구를 (헤드라인, 본문)으로 쪼갠다. 줄바꿈이 있으면 그게 우선."""
    text = (text or "").strip()
    if "\n" in text:
        head, _, rest = text.partition("\n")
        return head.strip(), rest.strip()
    m = _HEADLINE_SPLIT.match(text)
    if not m:
        return text, ""
    return m.group(1).strip(), m.group(2).strip()


def build_cards(
    sections: list[Section], plan: LayoutPlan, image_plan: ImagePlan
) -> list[ContentCard]:
    """모듈 순서대로 카드를 만든다. **카드 한 장 = 이미지 1 + 문장 1**(팀장 확정 2026-08-22).

    전에는 프론트가 sections·module_images·layout_plan 세 곳을 module_kind로 짝지어
    긴 HTML 한 장으로 이어붙였다. 그 짝짓기를 여기서 한다.

    **짝짓기 키는 `module_kind or kind`다.** 위반소지 모듈의 내용은 LLM이 아니라
    인정문구·실증자료가 채우므로 그 섹션의 `kind`는 '광고문구'·'실증자료'가 되고
    모듈 kind와 달라진다(`Section.module_kind` 주석 참고).

    문장이 없는 모듈은 카드로 안 낸다. 이미지만 있고 글이 없는 카드는 빈 칸으로 보인다.
    반대로 이미지가 없는데 문장은 있으면 카드로 낸다(이미지 생성이 꺼져 있거나 실패한
    경우인데, 글은 여전히 쓸모가 있다).
    """
    by_kind: dict[str, Section] = {}
    for sec in sections:
        key = sec.module_kind or sec.kind
        by_kind.setdefault(key, sec)  # 같은 모듈에 여러 섹션이면 첫 번째만
    images = {img.module_kind: img for img in image_plan.module_images}

    cards: list[ContentCard] = []
    for module in plan.modules:
        sec = by_kind.get(module.kind)
        if sec is None or not (sec.text or "").strip():
            continue
        img = images.get(module.kind)
        head, body = split_headline(sec.text)
        cards.append(
            ContentCard(
                order=len(cards),
                module_kind=module.kind,
                layout_type=module.layout_type,
                headline=head,
                body=body,
                text=sec.text,
                text_source=sec.source,
                image_url=img.image_url if img else None,
                image_status=img.status if img else "skipped",
            )
        )
    return cards


def _generate_create_content(
    req: GenerateRequest, *, judge, vlm, image_generator=None, image_sink=None, photo_resolver=None
) -> GenerateResponse:
    """신규 생성(create) 모드 오케스트레이션. 원본 검사 없음, replacements 항상 빈 배열.

    레이아웃 레퍼런스를 퓨샷으로 모듈 구성을 계획한 뒤, 모듈 종류에 따라 내용을 채운다.
    효능·수치는 LLM이 쓰지 않는다. 검증된 인정문구나 사업자 입력 실증자료를 그대로 쓴다.
    """
    # 0. 프리셋을 요청에 펼친다. 아래 코드는 color_tone·mood·targeting을 그냥 읽으면 된다.
    req, _preset = apply_preset(req)

    # 1. 광고문구: 인증서-인정문구 매칭(자유창작 없음)
    claim_sections, skipped = build_approved_claim_sections(req)
    evidence = req.clinical_evidence or []
    surveys, survey_skipped = _usable_surveys(req)
    skipped += survey_skipped

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
    #    ensure_product_spec_module이 항상 plan.modules 맨 뒤에 붙이므로, 여기서도
    #    맨 뒤에 붙여야 렌더 순서가 계획된 모듈 순서와 어긋나지 않는다(2026-08-19,
    #    실제 export에서 표가 히어로보다 앞에 나오던 결함, 팀장 지시로 즉시 수정).
    safe_modules = [m for m in plan.modules if not m.has_claim_risk and m.kind != PRODUCT_SPEC_KIND]
    clinical_planned = any(m.kind.startswith("clinical") for m in plan.modules)
    product_spec_planned = any(m.kind == PRODUCT_SPEC_KIND for m in plan.modules)
    sections = list(claim_sections)
    if clinical_planned and evidence:
        sections.append(
            Section(kind="실증자료", text=clinical_sections_text(evidence), source="clinical_evidence")
        )
    if surveys:
        sections.append(
            Section(
                kind="설문조사",
                text=" / ".join(survey_sentence(s) for s in surveys),
                source="survey_evidence",
            )
        )
    _link_risky_module_sections(sections, plan)
    plan, unfilled_skipped = _drop_unfilled_risky_modules(plan, sections)
    skipped += unfilled_skipped
    # 카드 5~6장으로 추린다. **위험 모듈 필터 뒤, 이미지 생성 앞**이어야 한다
    # (select_top_modules docstring 참고: 순서가 어긋나면 카드가 4장으로 줄거나
    # 버릴 모듈의 배경 이미지까지 과금해서 만든다).
    # 이미 내용이 붙은 모듈은 우선순위가 낮아도 보호한다. 버리면 섹션이 갈 곳을 잃는다.
    filled_kinds = tuple(s.module_kind for s in sections if s.module_kind)
    plan, over_limit_skipped = select_top_modules(plan, protected=filled_kinds)
    skipped += over_limit_skipped
    # 추린 뒤에 다시 계산한다. 위에서 잡은 safe_modules에는 버린 모듈이 남아 있어,
    # 그대로 쓰면 카드로 안 나갈 모듈의 문장까지 LLM에 시킨다.
    safe_modules = [m for m in plan.modules if not m.has_claim_risk and m.kind != PRODUCT_SPEC_KIND]
    sections += generate_module_sections(req, safe_modules, vlm)
    if product_spec_planned:
        sections.append(build_product_spec_section(req))

    # 4. PII 제거
    cleaned, pii_kinds = _strip_pii(sections)
    # 5. 이미지 배치·가드레일 + 모듈별 배경 이미지 생성
    image_plan = build_image_plan(req, plan, image_generator, image_sink, photo_resolver)
    # 6. 생성물 재검증
    recheck, risks = _recheck(cleaned, req, judge)
    # 7. 실증자료·설문조사는 미검증이라 사용자 확인 항목으로 남긴다
    disclaimer = _DISCLAIMER
    for survey in surveys:
        risks.append(
            RiskConfirmation(
                id=f"rc_survey_{surveys.index(survey)}",
                text=survey_sentence(survey),
                reason="사업자가 입력한 설문조사 결과입니다. barum은 진위를 검증하지 않습니다. "
                "설문 결과는 실증자료가 아니므로 효능·효과의 근거로는 쓸 수 없습니다. "
                "또한 조사기관·시기·표본을 밝혀도 수치형 설문 표현은 5호(거짓·과장) 검토필요로 "
                "남습니다. 게시 전 원자료(조사방법·무작위성·질문 문항)를 준비하세요.",
            )
        )
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
        cards=build_cards(cleaned, plan, image_plan),
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
