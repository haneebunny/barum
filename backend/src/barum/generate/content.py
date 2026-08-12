"""콘텐츠 생성·개선 오케스트레이션 (FR-11/13, improve + create).

improve: 원본 검사(findings) → 위반 조건표 치환 → 저위험 서술 LLM 생성 → PII 제거 →
이미지 배치·가드레일 → 생성물 재검증.
create: 원본 없이 인증서-인정문구 매칭으로 광고문구 조립(효능표현 자유창작 금지,
조건표 대신 인증서-인정문구 매칭이 소스) → 이하 동일.
judge·vlm을 주입받아 유닛테스트는 오프라인.
"""

from barum.generate.replace import apply_replacements, build_replacements
from barum.models import (
    GenerateRequest,
    GenerateResponse,
    ImageGenResult,
    ImagePlan,
    PlacedImage,
    RecheckSummary,
    RiskConfirmation,
    Section,
    SkippedClaim,
)
from barum.pipeline import run_check
from barum.reference.approved_claims import match_approved_claim
from barum.reference.impersonation import check_impersonation
from barum.reference.ingredients import match_ingredient_strict
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


def build_image_plan(req: GenerateRequest) -> ImagePlan:
    """업로드 이미지 배치 + 생성요청 사칭 가드레일(FR-13). 실제 생성은 안 함."""
    placed: list[PlacedImage] = []
    if req.result_id:
        placed.append(PlacedImage(slot="hero", image_url=f"/reports/{req.result_id}/image"))

    gen = ImageGenResult()
    ig = req.image_generation
    if ig and ig.requested:
        allowed, reason = check_impersonation(ig.prompt or "")
        gen = ImageGenResult(requested=True, allowed=allowed, reason=reason, ai_labeled=False)
    return ImagePlan(placed=placed, generation=gen)


def _strip_pii(sections: list[Section]) -> tuple[list[Section], set[str]]:
    """모든 섹션 텍스트에서 PII 제거. (정제된 섹션, 제거된 PII 종류) 반환."""
    pii_kinds: set[str] = set()
    cleaned: list[Section] = []
    for s in sections:
        text, kinds = remove_pii(s.text)
        pii_kinds.update(kinds)
        cleaned.append(Section(kind=s.kind, text=text, source=s.source))
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
                    reason="인증서 매칭 실패 또는 인정문구 레퍼런스가 아직 원문 대조 전(draft)이라 사용 보류",
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


def _generate_create_content(req: GenerateRequest, *, judge, vlm) -> GenerateResponse:
    """신규 생성(create) 모드 오케스트레이션. 원본 검사 없음, replacements 항상 빈 배열."""
    # 1. 광고문구: 인증서-인정문구 매칭(자유창작 없음)
    claim_sections, skipped = build_approved_claim_sections(req)
    # 2. 저위험 서술(제품개요·사용법·주의사항)은 improve와 동일 로직 재사용
    sections = claim_sections + generate_sections(req, vlm)
    # 3. PII 제거
    cleaned, pii_kinds = _strip_pii(sections)
    # 4. 이미지 배치·가드레일
    image_plan = build_image_plan(req)
    # 5. 생성물 재검증
    recheck, risks = _recheck(cleaned, req, judge)
    return GenerateResponse(
        sections=cleaned,
        replacements=[],
        image_plan=image_plan,
        pii_removed=sorted(pii_kinds),
        risk_confirmations=risks,
        skipped_claims=skipped,
        recheck=recheck,
        disclaimer=_DISCLAIMER,
    )


def generate_content(req: GenerateRequest, *, judge, vlm) -> GenerateResponse:
    """`POST /generate` 오케스트레이션. `req.mode`로 improve/create 분기."""
    if req.mode == "create":
        return _generate_create_content(req, judge=judge, vlm=vlm)
    return _generate_improve_content(req, judge=judge, vlm=vlm)
