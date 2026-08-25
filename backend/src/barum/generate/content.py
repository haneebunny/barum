"""콘텐츠 생성·개선 오케스트레이션 (FR-11/13, improve + create).

improve: 원본 검사(findings) → 위반 조건표 치환 → 저위험 서술 LLM 생성 → PII 제거 →
이미지 배치·가드레일 → 생성물 재검증.
create: 원본 없이 인증서-인정문구 매칭으로 광고문구 조립(효능표현 자유창작 금지,
조건표 대신 인증서-인정문구 매칭이 소스) → 이하 동일.
judge·vlm을 주입받아 유닛테스트는 오프라인.
"""

import re

from pydantic import BaseModel

from barum.generate.images import generate_canvas_background, generate_module_images
from barum.reference.presets import apply_preset, audience_hint
from barum.generate.layout import (
    FULL_INGREDIENT_KIND,
    SURVEY_KIND,
    PRODUCT_SPEC_KIND,
    clinical_sections_text,
    ensure_full_ingredient_module,
    ensure_survey_module,
    ensure_product_spec_module,
    filter_risky_modules,
    plan_layout,
    select_top_modules,
)
from barum.generate.replace import (
    _accept,
    apply_replacements,
    build_replacements,
    unapplied_originals,
)
from barum.models import (
    ContentCard,
    Finding,
    GenerateRequest,
    GenerateResponse,
    ImageGenResult,
    JudgmentFlag,
    CanvasBackground,
    ImagePlan,
    LayoutModule,
    LayoutPlan,
    Location,
    ModuleImage,
    PlacedImage,
    RecheckSummary,
    Replacement,
    RiskConfirmation,
    Section,
    SkippedClaim,
    TableRow,
    ViolationType,
)
from barum.pipeline import run_check
from barum.reference.approved_claims import match_approved_claim
from barum.reference.impersonation import check_impersonation
from barum.reference.ingredients import match_ingredient_strict
from barum.reference.layout_references import infer_product_type, select_references
from barum.reference.mapping import legal_basis_for, legal_basis_text_for
from barum.reference.pii import remove_pii
from barum.reference.rules import RuleOutcome, match_all_rules
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

**입력이 비어 있어도 그 사실을 문장으로 쓰지 마라.** 값이 "(미상)"이면 그 항목을
언급하지 말고 아는 것만으로 써라. "정보가 제공되지 않았습니다" 같은 사과문은
고객에게 그대로 보이므로 금지다.

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

**입력이 비어 있어도 그 사실을 문장으로 쓰지 마라.** 제품명이나 전성분이 "(미상)"이면
그 항목을 아예 언급하지 말고, 아는 것만으로 카피를 써라. "제품명과 전성분 정보가
제공되지 않았습니다", "정보가 없어 안내할 수 없습니다" 같은 문장은 고객에게 그대로
보이는 사과문이라 절대 금지다. 쓸 내용이 없으면 그 모듈은 빼고 답해라.

**형식을 반드시 지켜라. 프론트가 첫 줄을 헤드라인으로 크게 키워 쓴다.**
- **헤드라인을 첫 줄에만 쓰고, 줄을 바꾼 뒤 설명을 이어라.** 이게 제일 중요하다.
  text 값 안에 줄바꿈 문자(\\n)를 넣으라는 뜻이다.
- **헤드라인은 20자 이내의 짧은 한 마디**다. 설명하지 말고 던져라.
- 설명은 둘째 줄부터 2~3문장으로 쓴다.

  올바른 예: "발림성부터 다릅니다\\n젤-세럼 타입의 가벼운 제형입니다. 끈적임이 거의 없습니다."
  틀린 예:   "발림성부터 다릅니다 젤-세럼 타입의 가벼운 제형입니다. 끈적임이 거의 없습니다."
             (줄을 안 바꿔서 헤드라인이 어디서 끝나는지 알 수 없다)
- 줄을 안 바꾸면 큰 글씨가 여러 줄로 흘러 헤드라인 구실을 못 한다.

JSON으로만 답하라: {{"sections": [{{"kind": "모듈kind", "text": "..."}}]}}"""

_CLINICAL_DISCLAIMER = (
    "실증자료(시험 결과)는 사업자가 입력한 내용이며, barum은 그 진위를 검증하지 않습니다."
)


# 입력이 비었을 때 LLM이 쓰는 사과문 표지. 상세페이지 카피에는 나올 이유가 없는
# 말들만 골랐다("전성분을 확인하세요" 같은 정상 안내문과 안 겹치게, 정보의 '부재'를
# 말하는 표현만).
_MISSING_INFO_MARKERS = (
    "제공되지 않",
    "제공하지 않",
    "제공되어 있지 않",
    "정보가 없",
    "정보가 부족",
    "기재되어 있지 않",
    "기재되지 않",
    "명시되어 있지 않",
    "명시되지 않",
    "확인할 수 없",
    "알 수 없습니다",
    "(미상)",
)

# 문장 끝. `_HEADLINE_SPLIT`과 같은 이유로 마침표 뒤 숫자는 소수점으로 본다.
_SENTENCE_END = re.compile(r"(?<=[.!?])(?!\d)\s+")


def _drop_missing_info_text(text: str) -> str:
    """입력 부재를 알리는 사과 문장만 걷어낸다. 나머지 문장은 그대로 둔다.

    **프롬프트 지시만으론 안 막힌다**(`_sanitize_generated`가 같은 이유로 존재한다).
    제품명·전성분을 비우고 돌리면 모델이 "제품명과 전성분 정보가 제공되지
    않았습니다"를 카피로 써서 고객 화면에 그대로 실렸다(2026-08-24 실측, 팀장
    다운로드본에서 확인). 사업자에게 입력을 더 받아야 한다는 안내는 화면 다른
    곳이 할 일이지 상세페이지 본문이 할 말이 아니다.

    줄 구조(첫 줄=헤드라인)를 지켜야 해서 줄 단위로 돌며 문장만 걸러낸다.
    """
    kept_lines: list[str] = []
    for line in (text or "").split("\n"):
        sentences = [
            s
            for s in _SENTENCE_END.split(line.strip())
            if s.strip() and not any(m in s for m in _MISSING_INFO_MARKERS)
        ]
        if sentences:
            kept_lines.append(" ".join(sentences))
    return "\n".join(kept_lines).strip()


def _drop_missing_info_sections(sections: list[Section]) -> list[Section]:
    """사과 문장을 걷어내고, 그러고도 남는 게 없는 섹션은 통째로 뺀다."""
    out: list[Section] = []
    for sec in sections:
        cleaned_text = _drop_missing_info_text(sec.text)
        if cleaned_text == (sec.text or ""):
            out.append(sec)
            continue
        if not cleaned_text:
            print(f"[generate] 입력 부재 사과문뿐이라 섹션 제외: {sec.kind}")
            continue
        print(f"[generate] 입력 부재 사과문 제거: {sec.kind}")
        out.append(sec.model_copy(update={"text": cleaned_text}))
    return out


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
        sections = _drop_missing_info_sections(sections)
        if sections:
            return sections
    except Exception as e:
        print(f"    [skip] 서술 생성 실패 → 템플릿 폴백: {type(e).__name__}: {e}")
    return _template_sections(req)


def _ingredients_for_judge(req: GenerateRequest) -> str | None:
    """판정기에 넘길 전성분. **없으면 None이다 — 자리표시자를 넘기면 안 된다.**

    create 모드는 성분을 `ingredient_amounts`에 담는다(`ingredients`는 improve
    모드 입력이라 항상 비어 있다). 그래서 재검증이 `req.ingredients`를 그대로 쓰면
    사업자가 성분을 입력했는데도 "전성분 미입력"으로 읽고, 어렵게 검증해 배치한
    인정문구를 **스스로 검토필요로 만든다**(2026-08-23 PM 발견).

    **`_ingredients_for_prompt`를 그대로 쓰면 안 된다.** 그쪽은 사람이 읽는
    프롬프트용이라 없을 때 "(미상)"을 낸다. 그 문자열을 판정기에 넘기면 성분명으로
    읽어서 "고시원료가 전성분에 없음"으로 보고 **검토필요를 위반으로 격상시킨다**
    (실측 확인). 없으면 없다고 해야 판정기가 "확인 못 함"으로 정직하게 남긴다.
    """
    if req.ingredients:
        return req.ingredients
    amounts = req.ingredient_amounts or []
    # **이름만 넘긴다.** 함량은 아래 `_amounts_for_judge`가 따로 넘긴다. 이름 칸에
    # "나이아신아마이드 3%"처럼 함량을 붙여 넣으면 성분표 대조가 이름을 못 찾아
    # "고시원료가 전성분에 없음"으로 읽고 **검토필요를 위반으로 격상시킨다**(실측).
    if amounts:
        return ", ".join(a.name for a in amounts if a.name)
    return None


def _amounts_for_judge(req: GenerateRequest) -> str | None:
    """판정기가 기대하는 `"성분:함량,성분:함량"` 형식. 없으면 None.

    함량까지 줘야 성분표 대조가 "기준 충족"까지 확인한다. 이름만 주면 거기서
    멈춰 검토필요로 남는다(그것도 정직한 결과이긴 하다).
    """
    amounts = [a for a in (req.ingredient_amounts or []) if a.name and a.amount]
    if not amounts:
        return None
    return ",".join(f"{a.name}:{a.amount}" for a in amounts)


def _ingredients_for_prompt(req: GenerateRequest) -> str:
    """카피 프롬프트에 실을 전성분 문자열.

    **create 모드는 `ingredients`가 아니라 `ingredient_amounts`에 성분을 담는다**
    (전자는 improve 모드 입력이다). 그걸 안 보고 `ingredients`만 쓰면 사업자가
    성분을 입력했는데도 프롬프트엔 "(미상)"이 들어가고, LLM이 "전성분 표기는
    제공되지 않습니다" 같은 사과문을 쓴다(2026-08-23 실측).
    """
    if req.ingredients:
        return req.ingredients
    amounts = req.ingredient_amounts or []
    if amounts:
        return ", ".join(f"{a.name} {a.amount}".strip() for a in amounts)
    return "(미상)"


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
        ingredients=_ingredients_for_prompt(req),
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
        sections = _drop_missing_info_sections(
            [
                Section(kind=m.kind, text=by_kind[m.kind], source="llm", module_kind=m.kind)
                for m in modules
                if by_kind.get(m.kind)
            ]
        )
        if sections:
            return sections
    except Exception as e:
        print(f"    [skip] 모듈 서술 생성 실패 → 템플릿 폴백: {type(e).__name__}: {e}")
    return _template_sections(req)


def _copy_by_module(sections: list[Section] | None) -> dict[str, str]:
    """모듈 kind → 그 모듈에 실릴 카피. 이미지 프롬프트에 참고로 넘긴다."""
    out: dict[str, str] = {}
    for sec in sections or []:
        key = sec.module_kind or sec.kind
        if key and sec.text and key not in out:
            out[key] = sec.text
    return out


def build_image_plan(
    req: GenerateRequest,
    plan: LayoutPlan | None = None,
    image_generator=None,
    image_sink=None,
    photo_resolver=None,
    sections: list[Section] | None = None,
) -> ImagePlan:
    """업로드 이미지 배치 + 생성요청 사칭 가드레일(FR-13).

    plan·image_generator를 주면 계획된 모듈마다 배경 이미지도 만든다(create 모드).
    안 주면 기존 동작 그대로다(배치·가드레일만, improve 모드 회귀 없음).

    image_sink: `(모듈kind, PNG바이트) -> 이미지 URL | None`. 저장은 여기서 하지 않고
    주입받는다(`content.py`는 저장소를 몰라야 오프라인 테스트가 된다. 실제 저장은
    `api/app.py`가 `storage/checks_store.py`로 한다).

    photo_resolver: `(req) -> 참조 이미지 바이트 목록`. image_sink와 같은 이유로
    저장소 접근은 여기서 안 하고 주입만 받는다. `generate_module_images`로 그대로
    넘긴다(req를 통째로 받는 이유는 그 함수 docstring 참고 - create·improve가
    서로 다른 필드로 참조를 찾는다).

    sections: 이미 만들어진 카피. **주면 그 모듈에 실제로 실릴 문장을 이미지
    프롬프트가 알게 된다.** 안 주면 플래너가 정한 한 줄 목적만 보고 그려서 배경이
    카피와 겉돈다. 텍스트가 이미지보다 먼저 만들어지니 순서상 문제는 없고, 그동안
    그냥 안 넘기고 있었다(2026-08-23).
    """
    placed: list[PlacedImage] = []
    if req.result_id:
        placed.append(PlacedImage(slot="hero", image_url=f"/reports/{req.result_id}/image"))
    for pid in req.product_photo_ids or []:
        placed.append(PlacedImage(slot="product_photo", image_url=f"/uploads/{pid}"))

    gen = ImageGenResult()
    ig = req.image_generation
    if ig and ig.requested:
        allowed, reason = check_impersonation(ig.prompt or "")
        gen = ImageGenResult(requested=True, allowed=allowed, reason=reason, ai_labeled=False)

    module_images: list[ModuleImage] = []
    canvas: CanvasBackground | None = None
    if plan is not None and image_generator is not None:
        module_images, blobs = generate_module_images(
            plan,
            req,
            image_generator,
            photo_resolver=photo_resolver,
            copy_by_kind=_copy_by_module(sections),
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


def _mask_pii_deep(value, pii_kinds: set[str]):
    """값 안의 모든 문자열을 마스킹한 사본을 낸다. 중첩 모델·목록까지 내려간다.

    **필드명을 하드코딩하지 않는다.** `_strip_pii`가 `text`만 훑던 시절엔 섹션이
    문장 한 덩어리라 그걸로 충분했다. 그런데 사업자 입력을 구조화해 싣는 필드가
    늘면서(`table_rows` 2026-08-23, `clinical_stat` 2026-08-24) 마스킹을 안 거치는
    샛길이 생겼다. `note`("피험자 수·조건 등 부연")나 전성분 표처럼 자유입력이라
    "문의: 02-1234-5678"이 그대로 API 응답에 실릴 수 있었다(PM 발견).

    필드를 나열해 막으면 다음에 필드가 늘 때 같은 구멍이 또 생긴다. 그래서 구조를
    타고 내려가며 문자열이면 전부 훑는다. `kind`·`source` 같은 내부 고정값도 지나가지만
    PII 패턴(이메일·주민번호·전화번호)에 걸릴 수 없는 값이라 바뀌지 않는다.
    """
    if isinstance(value, str):
        masked, kinds = remove_pii(value)
        pii_kinds.update(kinds)
        return masked
    if isinstance(value, BaseModel):
        updates = {}
        for name in type(value).model_fields:
            current = getattr(value, name)
            masked = _mask_pii_deep(current, pii_kinds)
            if masked is not current:
                updates[name] = masked
        return value.model_copy(update=updates) if updates else value
    if isinstance(value, list):
        masked_items = [_mask_pii_deep(v, pii_kinds) for v in value]
        if any(m is not o for m, o in zip(masked_items, value)):
            return masked_items
        return value
    return value


def _strip_pii(sections: list[Section]) -> tuple[list[Section], set[str]]:
    """모든 섹션에서 PII 제거. (정제된 섹션, 제거된 PII 종류) 반환.

    문장뿐 아니라 구조화 필드(표 행·실증자료)까지 훑는다. 왜 그렇게 하는지는
    `_mask_pii_deep` 참고.
    """
    pii_kinds: set[str] = set()
    cleaned: list[Section] = []
    for s in sections:
        # 필드를 하나씩 나열해 재조립하면 새 필드가 추가될 때마다 여기서 조용히
        # 유실된다. 실제로 module_kind가 그렇게 떨어져 나갔다(2026-08-20).
        cleaned.append(_mask_pii_deep(s, pii_kinds))
    return cleaned, pii_kinds


def _recheck(sections: list[Section], req: GenerateRequest, judge) -> tuple[RecheckSummary, list[RiskConfirmation]]:
    """생성물을 재검증하고 (요약, 남은 위반 확인항목)을 낸다."""
    combined = " ".join(s.text for s in sections)
    # **판정용 헬퍼를 쓴다.** create 모드 성분은 ingredient_amounts에 있어서,
    # req.ingredients를 그대로 쓰면 성분을 입력했는데도 "전성분 미입력"으로 읽고
    # 인정문구를 스스로 검토필요로 만든다.
    rc = run_check(
        "KR",
        combined,
        None,
        None,
        None,
        judge,
        ingredients=_ingredients_for_judge(req),
        ingredient_amounts=_amounts_for_judge(req),
    )
    recheck = RecheckSummary(
        safe=rc.summary.n_findings == 0,
        n_findings=rc.summary.n_findings,
        n_violation=rc.summary.n_violation,
        n_needs_review=rc.summary.n_needs_review,
        # 개수만 주면 화면이 "재검증 실패" 하나로 뭉뚱그린다. 검토필요는 실증자료를
        # 요구하는 정상 동작인데 그것까지 실패로 물든다(RecheckSummary 주석 참고).
        findings=rc.findings,
    )
    return recheck, _confirmations_by_sentence(rc.findings)


def _sanitize_generated(sections: list[Section], vlm) -> list[Section]:
    """자유생성 카피를 규칙집에 태워, 걸리면 대체표현으로 갈아끼운다.

    **프롬프트 지시만으론 안 막힌다.** `_MODULE_PROMPT`가 "효능·질병 표현을 쓰지
    마라"라고 하지만 그건 지시일 뿐이고 뒤에 아무 장치가 없었다. 특히 사용자
    자유서술(`notes`)에 위반 문구가 들어 있으면 모델이 그걸 그대로 옮긴다
    (2026-08-23 재현: notes에 "줄기세포 배양 기술"을 넣으니 성분 소개 카피에
    `줄기세포`가 그대로 나왔다. 재검증은 잡았지만 아무것도 안 고치고 내보냈다).

    개선(improve) 모드의 대체표현 경로를 그대로 쓴다 — 규칙 대조·조건표·게이트가
    이미 붙어 있어서 새로 만들 게 없다. **탐지는 규칙 매칭이라 과금이 없고**, 걸린
    문장이 있을 때만 재작성 호출이 나간다. 안 걸리면 비용도 0이다.

    규칙에 안 걸리고 VLM만 잡는 위반은 여기서 못 막는다. 그건 `_recheck`가 보고한다.
    """
    findings: list[Finding] = []
    for order, sec in enumerate(sections):
        for line in (sec.text or "").split("\n"):
            line = line.strip()
            if not line:
                continue
            for m in match_all_rules(line):
                if m.outcome not in (RuleOutcome.violation, RuleOutcome.needs_review):
                    continue
                findings.append(
                    Finding(
                        span=m.span,
                        sentence=line,
                        violation_type=m.violation_type,
                        legal_basis=legal_basis_for(m.violation_type),
                        legal_basis_text=legal_basis_text_for(m.violation_type),
                        flag=m.flag or JudgmentFlag.violation,
                        explanation=f"생성 카피 자체 검사: '{m.span}'",
                        location=Location(order=order),
                        source="rule",
                    )
                )
    if not findings:
        return sections

    print(f"[create] 생성 카피에서 위반 표현 {len(findings)}건 발견, 대체표현으로 교체")
    reps = build_replacements(findings, rewriter=vlm)
    for sec in sections:
        sec.text = apply_replacements(sec.text or "", reps)
    return sections


def _confirmations_by_sentence(findings: list[Finding]) -> list[RiskConfirmation]:
    """남은 지적을 **문장 하나당 확인항목 하나**로 묶는다.

    예전엔 finding마다 하나씩 냈다. 그때는 문장당 지적이 하나뿐이라 같은 결과였는데,
    문장의 매칭을 전부 내게 바꾸면서(2026-08-23) **같은 문장이 확인항목으로 여러 번
    찍히게 됐다.** 화면에는 토씨 하나 안 틀린 문장이 세 번 나오고, 사용자는 같은 걸
    세 번 확인해야 다음으로 넘어간다.

    사용자가 확인하는 단위는 "이 문장을 이대로 내보내도 되는가"다. 지적이 몇 개
    걸렸는지는 사유에 적으면 되고 체크박스를 늘릴 일이 아니다.

    사유는 순서를 지키며 합치고 중복은 지운다. 규칙 경로 설명은 span마다 달라서
    보통 서로 다른 문장이 되지만, 같은 설명이 두 번 붙는 경우도 있다.
    """
    reasons: dict[str, list[str]] = {}
    for f in findings:
        bucket = reasons.setdefault(f.sentence, [])
        if f.explanation and f.explanation not in bucket:
            bucket.append(f.explanation)
    return [
        RiskConfirmation(id=f"rc_{i}", text=sentence, reason="\n".join(rs))
        for i, (sentence, rs) in enumerate(reasons.items())
    ]


_CLAIM_CATEGORIES = ("미백", "주름개선", "자외선차단")


# 인정문구가 붙을 마지막 자리. 위험 모듈이 하나도 없을 때만 쓴다.
_HERO_KIND = "hero_intro"


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
    # 실증자료도 하나씩 배정한다. 예전엔 전부 clinical_slots[0]에 몰아넣어서,
    # 자료가 여러 건이어도 카드가 1장뿐이었다(2026-08-23 팀장 지시로 변경).
    clinical_iter = iter(clinical_slots)
    # 위험 모듈이 없을 때 인정문구가 갈 곳. 없으면 None이고 그때는 skipped로 나간다.
    hero = next((m for m in plan.modules if m.kind == _HERO_KIND), None)
    for section in sections:
        if section.module_kind is not None:
            continue
        if section.source == "approved_claim":
            module = next(claim_iter, None)
            if module is not None:
                section.module_kind = module.kind
            elif hero is not None:
                # **위험 모듈이 하나도 없으면 히어로에 붙인다**(2026-08-23 팀장 확정).
                # 플래너가 위험 모듈을 안 내는 계획을 만들면 인정문구가 붙을 자리가
                # 없어 조용히 사라졌다. 검증된 법정 문구가 없어지는 건데, 그게
                # create 모드의 존재 이유라 제일 나쁜 유실이다.
                #
                # 히어로를 고른 이유: 원래 한 마디 헤드라인 자리고, 검증된 문구가
                # 생성 카피보다 그 자리에 더 맞다. `build_cards`가 setdefault라
                # 인정문구 섹션이 앞에 있으면 자동으로 이겨서 히어로 카피를 대체한다.
                section.module_kind = hero.kind
                hero = None  # 인정문구가 여러 개여도 히어로는 한 번만 내준다
        elif section.source == "clinical_evidence":
            module = next(clinical_iter, None)
            if module is not None:
                section.module_kind = module.kind


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


def _unplaced_claim_skips(sections: list[Section]) -> list[SkippedClaim]:
    """모듈에 못 붙은 인정문구를 스킵 사유로 낸다.

    조용히 빠지는 것과 "왜 빠졌는지 적힌 채로 빠지는 것"은 완전히 다르다. 전자는
    아무도 못 알아채고, 후자는 화면에도 뜨고 다음 사람이 원인을 찾을 수 있다.
    """
    return [
        SkippedClaim(
            category="인정문구",
            reason=(
                f"계획에 이 문구를 실을 모듈이 없어 화면에 넣지 못했습니다: {s.text}"
            ),
        )
        for s in sections
        if s.source == "approved_claim" and s.module_kind is None
    ]


def build_full_ingredient_section(req: GenerateRequest) -> Section:
    """전성분 전체 목록 섹션. LLM을 안 태운다.

    화장품법상 의무 표시사항이라 지어낼 여지를 두면 안 된다. 사업자가 입력한 값을
    그대로 옮긴다. 함량이 있으면 같이 적는다.
    """
    rows: list[TableRow] = []
    if req.ingredients:
        for name in (n.strip() for n in req.ingredients.split(",")):
            if name:
                rows.append(TableRow(label="", value=name))
    else:
        for a in req.ingredient_amounts or []:
            rows.append(TableRow(label=a.name, value=a.amount or ""))
    return Section(kind=FULL_INGREDIENT_KIND, text="", source="full_ingredient", table_rows=rows)


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


# 대체표현 출처 표기. 리포트에서 사용자가 고른 값이지 우리가 새로 만든 게 아니다.
_BASIS_APPROVED = "리포트에서 사용자가 수용한 대체 표현"


def _accept_approved(req: GenerateRequest) -> tuple[list[Replacement], list[str]]:
    """사용자가 수용한 대체표현을 받아 (적용할 것, 게이트에 걸린 것)으로 가른다.

    **클라이언트가 보낸 문구를 그대로 믿지 않는다.** 서버가 만든 것과 같은 게이트를
    통과시킨다. 안 그러면 임의 텍스트가 상세페이지에 들어가 대체표현 게이트가 통째로
    우회된다. 게이트는 규칙·사례 대조라 LLM 호출이 없다(비용 0).
    """
    approved: list[Replacement] = []
    rejected: list[str] = []
    for a in req.approved_replacements or []:
        if not _accept(a.replaced, original=a.original):
            print(f"[generate] 수용 대체표현이 게이트에 걸림, 제외: {a.replaced!r}")
            rejected.append(a.replaced)
            continue
        approved.append(
            Replacement(
                original=a.original,
                replaced=a.replaced,
                violation_type=a.violation_type or ViolationType.type_5_deception,
                basis=_BASIS_APPROVED,
                finding_index=a.finding_index,
                note=a.note,
            )
        )
    return approved, rejected


# 승인된 대체표현을 이미지로 만들 때 쓰는 layout_type (image_text_split: 한쪽에 이미지, 한쪽에 문구)
_REPLACEMENT_IMAGE_LAYOUT_TYPE = "image_text_split"


def _replacement_image_modules(reps: list[Replacement]) -> list[LayoutModule]:
    """승인된 대체표현마다 이미지 1장을 만들도록 LayoutModule로 합성한다(improve 모드).

    improve 모드엔 플래너가 없어 진짜 LayoutPlan이 없다. `build_image_plan`은
    plan·image_generator를 주면 그대로 확장되게 이미 설계돼 있어서(docstring: "안
    주면 기존 동작 그대로다, improve 모드 회귀 없음") 그 확장 지점에 맞춰 합성한다 -
    가짜 계획을 억지로 끼우는 게 아니라 원래 예정된 사용법이다.

    purpose는 일반적인 목적 문구만 담는다(플래너 의도용 필드라 카피를 섞으면 나중에
    헷갈린다, 베베 지적). 실제 원문→대체문구는 `_replacement_copy_sections`로 따로
    만들어 `build_image_plan(sections=...)`에 넘긴다 - #341에서 생긴 copy_by_kind
    경로를 그대로 타면 "글자로 쓰지 마라" 방어(`images.py` `_copy_line`)까지 이미
    붙어 있어서 여기서 또 안 넣어도 된다.
    """
    return [
        LayoutModule(
            kind=f"replacement_{i}",
            purpose="완화된 광고 문구 옆에 놓일 배경 이미지",
            has_claim_risk=False,
            layout_type=_REPLACEMENT_IMAGE_LAYOUT_TYPE,
        )
        for i in range(len(reps))
    ]


def _replacement_copy_sections(reps: list[Replacement]) -> list[Section]:
    """`_replacement_image_modules`가 합성한 모듈에 짝지어질 카피(원문→대체문구).

    화면에 나가는 진짜 섹션이 아니라 `build_image_plan(sections=...)` → copy_by_kind
    → 이미지 프롬프트로만 흘러가는 힌트다. `GenerateResponse.sections`엔 안 섞는다
    (kind가 `replacement_i`라 실제 렌더 쪽 module_kind 짝짓기와 겹치지 않게 완전히
    분리된 용도로만 쓴다).
    """
    return [
        Section(
            kind=f"replacement_{i}",
            text=f'"{r.original}" → "{r.replaced}"',
            source="image_prompt_hint",
        )
        for i, r in enumerate(reps)
    ]


def _replacement_display_sections(reps: list[Replacement]) -> list[Section]:
    """승인된 대체표현마다 카드로 낼 실제 문구.

    `_replacement_copy_sections`(이미지 프롬프트 힌트용, "원문" → "대체문구" 표기)와
    달리 이건 사용자가 그대로 읽는 카드 본문이라 대체문구만 낸다. module_kind를
    이미지 쪽(`_replacement_image_modules`)과 같은 `replacement_i`로 맞춰야
    `build_cards`가 이미지와 짝짓는다.
    """
    return [
        Section(
            kind=f"replacement_{i}",
            text=r.replaced,
            source="remediation",
            module_kind=f"replacement_{i}",
        )
        for i, r in enumerate(reps)
    ]


def _image_backed_cards(cards: list[ContentCard]) -> list[ContentCard]:
    """이미지가 실제로 붙은 카드만 남긴다(improve 모드 전용).

    improve 모드 카드는 전부 "이미지 1 + 대체문구 1" 한 종류다. 이미지 생성 상한
    (`images.DEFAULT_MAX_IMAGES`, 6장)을 넘긴 대체표현은 글만 있는 카드로 나가서
    상세페이지 끝에 이미지 없는 카드가 줄줄이 붙었다(2026-08-24 팀장 다운로드본:
    이미지 카드 6장 뒤에 글만 있는 카드 5장). 팀장 지시로 이미지 있는 것만 낸다.

    **한 장도 없으면 전부 남긴다.** 이미지 생성이 꺼져 있거나(`IMAGE_GENERATION_
    ENABLED=0`) 전부 실패한 경우인데, 그때까지 빈 페이지를 내면 고친 문구를 통째로
    잃는다. 걸러낸 문구 자체는 `sections`·`replacements`에 그대로 남아 있어서
    화면 다른 곳에서는 여전히 볼 수 있다.

    create 모드엔 쓰지 않는다. 거기선 표(스펙·전성분)·수치강조처럼 이미지가 없는
    게 정상인 카드가 있다.
    """
    with_image = [c for c in cards if c.image_url]
    if not with_image:
        return cards
    dropped = len(cards) - len(with_image)
    if dropped:
        print(f"[generate] 이미지 없는 카드 {dropped}장 제외(문구는 sections에 남음)")
    # order는 화면 정렬 키라 걸러낸 뒤 다시 매긴다(비면 정렬이 뛴다).
    return [c.model_copy(update={"order": i}) for i, c in enumerate(with_image)]


def _generate_improve_content(
    req: GenerateRequest, *, judge, vlm, image_generator=None, image_sink=None, photo_resolver=None
) -> GenerateResponse:
    """개선 모드 오케스트레이션. judge·vlm 주입(테스트는 StubJudge+가짜LLM).

    image_generator를 주면 승인된 대체표현마다 배경 이미지도 만든다
    (`_replacement_image_modules` 참고). 안 주면 기존 동작 그대로다(배치·가드레일만,
    회귀 없음).

    **create 모드와 같은 카드형 산출물을 낸다**(팀장 지시, 2026-08-24). 전에는
    화면이 `sections`를 긴 HTML로 이어붙였는데, 대체표현 이미지의 module_kind
    (`replacement_i`)가 어떤 섹션의 kind와도 안 겹치게 일부러 분리해 둔 값이라
    화면 쪽 매칭이 원천적으로 안 됐다 - 이미지는 만들어지고 저장까지 됐는데 그릴
    자리가 없어 조용히 버려졌다(실측, 2026-08-24). `build_cards`(create 모드가
    쓰는 그 함수)를 그대로 재사용해 대체표현마다 카드 1장(이미지+문구)으로 낸다.
    """
    gate_rejected: list[str] = []
    if req.approved_replacements is not None:
        # **재계산하지 않는다.** 리포트에서 이미 판정하고 사용자가 승인한 결과를 쓴다.
        # 다시 돌리면 비용이 두 배고, 실행편차 때문에 승인한 문구와 생성물이 달라진다.
        reps, gate_rejected = _accept_approved(req)
    else:
        # 하위호환: 승인 목록 없이 부르면 예전처럼 처음부터 계산한다.
        initial = run_check(
            "KR", req.content, None, None, None, judge, ingredients=req.ingredients
        )
        reps = build_replacements(initial.findings, rewriter=vlm)
    safe_content = apply_replacements(req.content, reps)
    # 치환이 실제로 안 된 것. 조용히 넘어가면 "고쳤다"고 표시된 채로 원문이 나간다.
    # **최종 결과 기준으로 본다**(원문 기준으로 보면 다른 치환이 먼저 처리한 것까지
    # 미적용으로 세고, 정작 결과에 남은 위반은 못 잡는다).
    unapplied = unapplied_originals(safe_content, reps) + gate_rejected
    # 3. 섹션 조립.
    # **개선된 전체 원문(`광고문구`)을 항상 남긴다.** 한때 대체표현이 있으면 이걸
    # 빼고 대체표현 문장만 냈는데, 두 가지가 조용히 깨졌다(2026-08-24 실측).
    #   1) 원문에서 위반이 아니었던 부분이 통째로 사라졌다("전국 약국 오프라인매장
    #      입점!"처럼 고칠 이유가 없던 사업자 문구까지 없어졌다).
    #   2) 재검증이 빈 문자열을 검사했다. 아래 `recheck_input`이 대체표현 섹션을
    #      빼는데(원문에 이미 포함된 문장이라 두 번 세면 위반 수가 부풀려진다)
    #      `광고문구`가 없으니 검사 대상이 0자가 됐다. 그래서 대체표현이 있으면
    #      항상 "재검증 통과", 없으면 원문을 그대로 검사해 항상 "재검증 실패"가 났다.
    # 화면 카드는 아래 `_image_backed_cards`가 따로 고르므로, 이 섹션을 남겨도
    # 상세페이지에 글만 있는 카드가 늘지 않는다(텍스트 복사·재검증용으로만 쓰인다).
    sections = [
        Section(
            kind="광고문구",
            text=safe_content,
            source="remediation" if reps else "template",
            module_kind="ad_copy",
        )
    ] + _replacement_display_sections(reps)
    # 4. PII 제거 (대체표현 카드 문구도 여기서 같이 - 별도 필드로 새면 마스킹을
    # 우회한다, PR #345와 같은 이유)
    cleaned, pii_kinds = _strip_pii(sections)
    # 대체표현 카드 문구는 ad_copy 전체 문장 안에 이미 포함돼 있다. 재검증에
    # 그대로 또 넣으면 판정기가 같은 문장을 두 번 세서 위반 개수가 부풀려진다
    # (2026-08-24) - ad_copy·LLM 서술만 재검증한다.
    recheck_input = [s for s in cleaned if not (s.module_kind or "").startswith("replacement_")]
    # 5. 이미지 배치·가드레일 + 승인된 대체표현별 배경 이미지 생성
    replacement_modules = _replacement_image_modules(reps)
    image_plan = build_image_plan(
        req,
        plan=LayoutPlan(
            modules=replacement_modules,
            product_type=infer_product_type(req.product_name),
            source="improve_replacements",
        ),
        image_generator=image_generator,
        image_sink=image_sink,
        photo_resolver=photo_resolver,
        sections=_replacement_copy_sections(reps),
    )
    # 6. 생성물 재검증
    recheck, risks = _recheck(recheck_input, req, judge)
    # 7. 카드 조립. build_image_plan에 넘긴 plan(대체표현만)과 별개다 - 나머지
    # 모듈(ad_copy·LLM 서술)은 이미지가 필요 없어서 애초에 이미지 생성 쪽 plan에
    # 안 넣었다(과금 안 남). build_cards는 module_kind로 image_plan.module_images를
    # 찾으므로, 대응하는 이미지가 없는 모듈은 그냥 문구만 있는 카드로 나간다.
    # 7. 카드 조립.
    # 대체표현이 있으면 각 대체표현별 split 카드를 메인으로 구성하고,
    # 대체표현이 없을 때만 ad_copy 단일 카드를 statement로 구성한다.
    cards_plan = LayoutPlan(
        modules=replacement_modules if replacement_modules else [
            LayoutModule(
                kind="ad_copy",
                purpose="개선된 전체 광고 문구",
                has_claim_risk=False,
                layout_type="section_statement",
            )
        ],
        product_type=infer_product_type(req.product_name),
        source="improve_replacements",
    )
    return GenerateResponse(
        sections=cleaned,
        replacements=reps,
        image_plan=image_plan,
        pii_removed=sorted(pii_kinds),
        risk_confirmations=risks,
        recheck=recheck,
        unapplied_replacements=unapplied,
        disclaimer=_DISCLAIMER,
        cards=_image_backed_cards(build_cards(cleaned, cards_plan, image_plan)),
    )


# 첫 문장을 헤드라인으로 떼는 규칙. 프론트 `splitHeadline`과 같은 규칙이라
# 백엔드·프론트가 다르게 쪼개지 않는다.
# **마침표 뒤 숫자는 문장 끝이 아니라 소수점이다.** 이 예외가 없으면 실증자료
# "23.5% 개선"이 "…23." + "5% 개선…"으로 쪼개져 사업자 입력 수치가 왜곡된다
# (2026-08-20 실측). barum은 실증 수치를 LLM에도 안 태우고 그대로 싣는 게 원칙인데
# 렌더 단계에서 깨지고 있었다.
_HEADLINE_SPLIT = re.compile(r"^([\s\S]+?[.!?](?!\d))\s*([\s\S]*)$")


# 헤드라인으로 둘 수 있는 최대 길이. 넘으면 큰 글씨가 여러 줄로 흘러 헤드라인
# 구실을 못 한다(프롬프트가 요구하는 20자에 약간의 여유).
_MAX_HEADLINE = 24


def split_headline(text: str, *, allow_long_headline: bool = False) -> tuple[str, str]:
    """카드 문구를 (헤드라인, 본문)으로 쪼갠다. 줄바꿈이 있으면 그게 우선.

    **본문이 비고 헤드라인만 긴 결과를 만들지 않는다.** 프롬프트로 줄바꿈을 요구해도
    (#311) 모델이 가끔 안 지키는데, 그러면 긴 한 문장이 통째로 헤드라인이 되고 본문이
    빈다. 화면에서는 그 칸이 짧아지면서 **옆에 붙는 이미지까지 26px로 찌그러진다**
    (2026-08-23 실측). 그럴 땐 전부 본문으로 돌린다 — 큰 글씨 한 덩어리보다
    평범한 문단 하나가 덜 깨져 보인다.

    allow_long_headline: 인정문구처럼 **법으로 문구가 정해진 텍스트**에 쓴다.
    길어도 헤드라인 자리를 지켜야 한다(자외선차단 인정문구는 35자다). 길이로는
    LLM 카피와 못 가르므로 부르는 쪽이 출처를 보고 정해준다.
    """
    text = (text or "").strip()
    if "\n" in text:
        head, _, rest = text.partition("\n")
        return head.strip(), rest.strip()
    m = _HEADLINE_SPLIT.match(text)
    head, body = (text, "") if not m else (m.group(1).strip(), m.group(2).strip())
    if not body and not allow_long_headline and len(head) > _MAX_HEADLINE:
        return "", head
    return head, body


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
        if sec is None:
            continue
        # **표만 있는 카드가 있다.** 상품 스펙표는 문장이 없고 table_rows만 있다.
        # 문장 유무로만 거르면 그 카드가 통째로 사라진다(2026-08-23 실측).
        if not (sec.text or "").strip() and not sec.table_rows:
            continue
        img = images.get(module.kind)
        image_url = img.image_url if img else None
        image_status = img.status if img else "skipped"
        is_original = False
        # 제품 원본이 올라왔으면 히어로(첫 카드)는 **생성 이미지가 있어도** 원본을
        # 우선한다(팀장 지시 2026-08-24: "기존 입력 이미지는 그대로 사용"). 나노바나나
        # 재합성은 라벨을 뭉개고(YOURBERRY→YOUARFRAY) 비용도 드는데, 원본은 라벨이
        # 완벽하고 과금이 0이다. 그래서 히어로 모듈은 애초에 이미지 생성도 스킵한다
        # (_generate_create_content). placed의 product_photo 슬롯을 그대로 쓴다.
        if len(cards) == 0 and image_plan.placed:
            product_photo = next(
                (p for p in image_plan.placed if p.slot == "product_photo"), None
            )
            if product_photo is not None:
                image_url = product_photo.image_url
                image_status = "placed"
                is_original = True
            elif not image_url:
                # 제품사진은 없지만 다른 배치 이미지가 있으면 그걸 히어로에 쓴다(기존 동작).
                image_url = image_plan.placed[0].image_url
                image_status = "placed"

        # 인정문구는 법으로 정해진 문구라 길어도 헤드라인 자리를 지킨다.
        head, body = split_headline(
            sec.text, allow_long_headline=sec.source == "approved_claim"
        )
        cards.append(
            ContentCard(
                order=len(cards),
                module_kind=module.kind,
                layout_type=module.layout_type,
                headline=head,
                body=body,
                text=sec.text,
                text_source=sec.source,
                image_url=image_url,
                image_status=image_status,
                is_original=is_original,
                table_rows=sec.table_rows,
                clinical_stat=sec.clinical_stat,
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
    plan = ensure_full_ingredient_module(plan, req)
    plan = ensure_survey_module(plan, req)

    # 3. 모듈별 내용 채우기. 위험 모듈은 LLM을 안 태운다.
    #    임상 모듈이 여러 개여도 실증자료 섹션은 하나만 낸다(같은 자료 반복 방지).
    #    product_spec도 LLM을 안 태운다. 사업자 입력값을 표로 그대로 옮길 뿐이다.
    #    ensure_product_spec_module이 항상 plan.modules 맨 뒤에 붙이므로, 여기서도
    #    맨 뒤에 붙여야 렌더 순서가 계획된 모듈 순서와 어긋나지 않는다(2026-08-19,
    #    실제 export에서 표가 히어로보다 앞에 나오던 결함, 팀장 지시로 즉시 수정).
    safe_modules = [m for m in plan.modules if not m.has_claim_risk and m.kind not in (PRODUCT_SPEC_KIND, FULL_INGREDIENT_KIND, SURVEY_KIND)]
    clinical_planned = any(m.kind.startswith("clinical") for m in plan.modules)
    sections = list(claim_sections)
    if clinical_planned and evidence:
        # **자료 1건 = 섹션 1장.** 2026-08-20엔 "같은 자료 반복 방지"로 전부 한 섹션에
        # 묶었는데, 그러면 임상 모듈이 여러 개여도 채울 섹션이 하나뿐이라 나머지가
        # "자료 부족"으로 드롭됐다. 사업자가 실증자료를 3건 넣어도 카드는 1장이었다.
        # 팀장 지시로 뒤집는다(2026-08-23): "실증자료까지 다 넣어."
        # clinical_stat엔 입력 객체를 그대로 싣는다. text는 그대로 두므로 구버전
        # 프론트는 지금처럼 문장으로 렌더하고, 새 프론트만 수치를 골라 쓴다.
        sections += [
            Section(
                kind="실증자료",
                text=clinical_sections_text([e]),
                source="clinical_evidence",
                clinical_stat=e,
            )
            for e in evidence
        ]
    if surveys:
        sections.append(
            Section(
                kind="설문조사",
                text=" / ".join(survey_sentence(s) for s in surveys),
                source="survey_evidence",
                module_kind=SURVEY_KIND,
            )
        )
    _link_risky_module_sections(sections, plan)
    # **자리를 못 찾은 인정문구를 조용히 흘려보내지 않는다.**
    # 인정문구는 계획에 `has_claim_risk` 모듈이 있어야 거기 붙는다. 플래너가 그런
    # 모듈을 하나도 안 내면 `module_kind`가 None으로 남고, `build_cards`는
    # `plan.modules`를 돌기 때문에 카드가 안 생긴다. 검증된 법정 문구가 흔적도
    # 없이 사라지는데, 그게 create 모드의 존재 이유라 제일 나쁜 유실이다
    # (2026-08-23 실측: 위험 모듈이 없는 계획에서 재현됨).
    skipped += _unplaced_claim_skips(sections)
    plan, unfilled_skipped = _drop_unfilled_risky_modules(plan, sections)
    skipped += unfilled_skipped
    # 카드 5~6장으로 추린다. **위험 모듈 필터 뒤, 이미지 생성 앞**이어야 한다
    # (select_top_modules docstring 참고: 순서가 어긋나면 카드가 4장으로 줄거나
    # 버릴 모듈의 배경 이미지까지 과금해서 만든다).
    # 이미 내용이 붙은 모듈은 우선순위가 낮아도 보호한다. 버리면 섹션이 갈 곳을 잃는다.
    #
    # **상품 스펙표도 보호한다.** 사업자가 직접 입력한 제형·용량을 그대로 옮기는
    # 표라 LLM도 안 태우고 지어낼 것도 없다. 그런데 우선순위가 낮아 상한에 잘렸고,
    # 그러면서 섹션은 그대로 만들어져 **갈 곳 없는 섹션**이 됐다. `build_cards`가
    # `plan.modules`를 도니 카드가 안 생기고, 화면에서 표가 통째로 사라진다
    # (2026-08-23 실측: 제형·용량을 입력했는데 표가 안 나옴).
    filled_kinds = tuple(s.module_kind for s in sections if s.module_kind)
    plan, over_limit_skipped = select_top_modules(
        plan, protected=filled_kinds + (PRODUCT_SPEC_KIND, FULL_INGREDIENT_KIND, SURVEY_KIND)
    )
    skipped += over_limit_skipped
    # 추린 뒤에 다시 계산한다. 위에서 잡은 safe_modules에는 버린 모듈이 남아 있어,
    # 그대로 쓰면 카드로 안 나갈 모듈의 문장까지 LLM에 시킨다.
    safe_modules = [m for m in plan.modules if not m.has_claim_risk and m.kind not in (PRODUCT_SPEC_KIND, FULL_INGREDIENT_KIND, SURVEY_KIND)]
    sections += _sanitize_generated(generate_module_sections(req, safe_modules, vlm), vlm)
    # **추린 뒤의 계획으로 다시 확인한다.** 위에서 잡은 값은 추리기 전 것이라,
    # 모듈이 잘렸는데도 섹션만 만들어져 화면에 안 나오는 섹션이 생긴다.
    if any(m.kind == PRODUCT_SPEC_KIND for m in plan.modules):
        sections.append(build_product_spec_section(req))
    if any(m.kind == FULL_INGREDIENT_KIND for m in plan.modules):
        sections.append(build_full_ingredient_section(req))

    # 4. PII 제거
    cleaned, pii_kinds = _strip_pii(sections)
    # 5. 이미지 배치·가드레일 + 모듈별 배경 이미지 생성.
    # **제품 원본이 올라왔으면 히어로(첫 모듈) 배경은 만들지 않는다**(팀장 지시
    # 2026-08-24). 히어로 카드는 build_cards가 placed의 제품 원본을 그대로 쓰므로
    # (is_original), 여기서 배경을 만들어봐야 안 쓰이고 나노바나나 비용만 나간다.
    # placed 목록은 req 기반이라(build_image_plan 내부) 모듈을 빼도 원본은 남는다.
    image_plan_source = plan
    if req.product_photo_ids and plan.modules:
        image_plan_source = plan.model_copy(update={"modules": plan.modules[1:]})
    image_plan = build_image_plan(
        req, image_plan_source, image_generator, image_sink, photo_resolver, sections=cleaned
    )
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

    image_generator를 안 주면 이미지 생성을 건너뛴다(모델 확정 전까지 기본 비활성).
    두 모드 다 이미지를 만든다 - create는 계획된 모듈마다, improve는 승인된
    대체표현마다(`_replacement_image_modules`) 만든다.
    photo_resolver는 참조 이미지를 바꿔주는 콜백이다(AI 배경·연출 합성, `(req) ->
    바이트 목록`). create는 판매자가 올린 제품사진(req.product_photo_ids), improve는
    원본 검사에 첨부된 리포트 이미지(req.result_id)를 각자 다른 저장 위치에서
    찾는다 - 어느 쪽을 쓸지는 콜백 안에서 정해진다(`api/app.py`
    `_resolve_reference_photos`). 안 주거나 둘 다 없으면 참조 없이 배경만 생성한다.
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
    return _generate_improve_content(
        req,
        judge=judge,
        vlm=vlm,
        image_generator=image_generator,
        image_sink=image_sink,
        photo_resolver=photo_resolver,
    )
