"""모듈별 이미지 생성 오케스트레이션 (FR-13, create 모드).

계획된 모듈마다 배경 이미지를 만든다. **텍스트도 제품도 그리지 않는다.** 원료·질감·추상
배경만 만들고, 문구는 프론트가 위에 얹고 제품샷은 판매자가 직접 올린다.

제품을 그리게 했더니 모델이 라벨에 깨진 글자를 박아 넣었다("AYN", "D-OIBELRAMOLAI" 등,
2026-08-18 실측). "글자 금지"라고 써도 안 지켜진다. 규제 준수를 검사하는 서비스가 가짜
제품 라벨을 만들어내면 자기모순이라, 아예 제품을 안 그리는 쪽으로 바꿨다(하니 확정).

과금 호출이라 모듈 단위로 실패를 격리한다. 한 모듈이 실패해도 나머지는 계속 만들고,
실패분은 `ModuleImage.status="skipped"`에 사유를 남긴다(조용히 빠지지 않게).

판매자가 제품사진을 올리면(`req.product_photo_ids`) 얘기가 달라진다. 그때는 그 실제
사진을 참조로 넘겨 배경과 합성한다(AI 배경·연출 합성, 팀장 승인 방식 A). 이 경우엔
위 "제품을 안 그린다" 원칙이 뒤집힌다: 상상으로 새로 그리는 대신 참조 사진 속 실제
제품을 유지하며 그 주위만 합성하므로 가짜 라벨 문제가 없다.
"""

from barum.models import GenerateRequest, LayoutModule, LayoutPlan, ModuleImage
from barum.reference.impersonation import check_impersonation

# 한 요청에 만들 이미지 수 상한. 과금 호출이라 모듈이 12개여도 다 만들지 않는다.
DEFAULT_MAX_IMAGES = 6

# 제품 종류별 질감 예시. 고정 목록 하나를 전부에 쓰면 토너에 크림 이미지가 나오는
# 식으로 제형이 안 맞는다(2026-08-19 실측, 팀장 지적, "촉촉 히알루론산 토너"인데
# 흰 크림 덩어리가 그려짐. build_image_prompt가 layout_plan.product_type을 아예
# 안 받고 예시에 "크림 질감"이 하드코딩돼 있던 게 원인).
_TEXTURE_HINTS: dict[str | None, str] = {
    "토너": "투명하거나 옅은 색의 맑은 액체, 튀는 물방울, 촉촉하게 젖은 표면. 걸쭉하거나 불투명한 질감은 넣지 마라",
    "세럼": "점도 있는 액상 방울, 유리 표면의 광택, 매끈하게 흐르는 액체 질감",
    "크림": "부드럽게 퍼바른 크림 스월, 뽀얗고 밀도 있는 질감",
    None: "잎, 물방울, 천, 돌 표면 같은 원료·소재 클로즈업(제품 제형은 특정하지 마라)",
}


def _texture_hint(product_type: str | None) -> str:
    """product_type에 맞는 질감 예시를 낸다. 모르는 종류거나 None이면 중립 힌트로 폴백."""
    return _TEXTURE_HINTS.get(product_type, _TEXTURE_HINTS[None])


# product_type별 기본 컬러톤·분위기. 인터뷰에서 값을 안 받았을 때 쓴다.
# 디디가 `layout_references/_vocabulary.json`의 `category_base_tone`으로 확정한 값
# (2026-08-19, PR #181). 이 파일의 hue_direction은 템플릿 색이 아니라 이 기본값
# 후보로 쓰라고 명시돼 있다(팀장 정정 커밋 71b3ebb 근거). 어휘집에 없는 종류(product_type
# 매핑 밖이거나 None)는 기존 중립 기본값으로 폴백.
_TONE_DEFAULTS: dict[str | None, str] = {
    "세럼": "투명・산뜻한 톤, 라이트 민트/세이지 계열",
    "토너": "맑고 산뜻한 톤, 워터 블루/민트 계열",
    "크림": "부드럽고 편안한 톤, 소프트 아이보리/베이지 계열(연한 톤만, 브라스·에스프레소 계열 금지)",
    "앰플": "집중・고농축 느낌, 딥그린 또는 딥네이비 + 화이트 대비",
    None: "투명하고 깨끗한 톤, 미니멀하고 차분한 분위기",
}


def _resolve_tone(req: GenerateRequest, product_type: str | None) -> str:
    """이번 생성 전체에 쓸 컬러톤·분위기 문구를 하나로 정한다.

    인터뷰에서 받은 값(req.color_tone·mood)이 있으면 그걸 우선한다. 없으면
    product_type 기본값, 그것도 없으면 전체 기본값(_TONE_DEFAULTS[None])으로
    폴백한다. **이 함수가 (req, product_type)에 대해 항상 같은 문자열을 내는 게
    핵심이다.** 그래야 6장 전부가 같은 아트 디렉션 문구를 받아서 한 페이지처럼
    읽힌다(지금까지는 모듈마다 톤 지정이 아예 없어서 색감·조명이 제각각이었다,
    2026-08-19 팀장 지적).
    """
    parts = [p for p in (req.color_tone, req.mood) if p]
    if parts:
        return ", ".join(parts)
    return _TONE_DEFAULTS.get(product_type, _TONE_DEFAULTS[None])


_PROMPT = """화장품 상세페이지에 쓸 **배경 이미지**를 만들어라.

제품 종류: {product_name}{product_type_line}
이 배경의 역할: {purpose}

**전체 컬러톤·분위기(이 상세페이지의 다른 배경 이미지들과 반드시 통일할 것): {tone}**

무엇을 그릴지:
{composition_lines}
{body_part_line}
- 위에 명시한 컬러톤·분위기를 따를 것
- **선명하고 또렷하게 그려라.** 안개 낀 듯 뿌옇거나 과도한 소프트포커스·흐림 효과는
  쓰지 마라. 실제 상품 사진처럼 디테일과 초점이 또렷해야 한다

절대 넣지 말 것:
{product_instruction}
- **라벨·글자·문구·숫자·로고를 넣지 마라.** 문구는 나중에 이 배경 위에 얹는다.
- **사람 얼굴은 어떤 형태로도 넣지 마라**(클로즈업뿐 아니라 원거리·실루엣도 금지).
- 의사·약사·전문가를 연상시키는 인물이나 소품(가운·청진기 등)을 넣지 마라.
- **실제 사용 후기·체험담처럼 보이는 연출을 만들지 마라**(사용 전후 비교, 손으로
  직접 촬영한 듯한 스냅샷 구도 등). 얼굴이 없어도 금지다. 실제 후기로 오인되면
  안 된다.
- 시험 결과 그래프나 차트를 만들지 마라.

문구를 얹을 여백이 남도록 화면 한쪽을 비교적 비워 둬라."""

# layout_type별 "무엇을 그릴지" 지시. 예전엔 전 모듈에 "질감 클로즈업 또는 추상
# 배경(색·빛 그라데이션)"이 동일하게 들어가서, 모델이 매번 더 쉬운 쪽(추상 그라데이션)
# 으로 수렴했다(2026-08-19 팀장 실측 지적: 6장 이어붙여보니 대부분 "그냥 초록 블러"
# 였고, "상세페이지에 쓰기 힘들 만큼 추상적"·"전체적으로 뿌옇다"는 두 가지 문제 확인).
# 사진성이 필요한 유형은 "그라데이션만" 옵션을 아예 빼고 구체적 질감을 강제한다.
# 사진성이 필요없는 유형(icon_grid·table_info·banner_strip)은 아예 이미지 생성을
# 스킵한다(_NO_IMAGE_LAYOUT_TYPES, generate_module_images에서 처리).
_COMPOSITION_BY_LAYOUT_TYPE_TEMPLATES: dict[str, str] = {
    "hero_fullbleed": (
        "- 넓은 분위기컷으로 그려라. 공간감이 느껴지는 전체 장면 안에 구체적 질감이\n"
        "  또렷이 보여야 한다: {hint}. **순수 색상 그라데이션만으로 채우지 마라.**\n"
        "  실사 상세페이지 사진처럼 보여야 한다"
    ),
    "image_text_split": (
        "- 화면 한쪽에 치우친 구체적 질감 클로즈업 하나만 그려라: {hint}\n"
        "  (반대쪽은 확실히 비워서 문구 자리를 만들어라). 색상 그라데이션만으로 채우지 마라"
    ),
    "mood_macro": (
        "- 극단적인 클로즈업으로 구체적 질감 하나를 프레임 가득 채워라: {hint}\n"
        "  순수 그라데이션·색면은 안 된다. 여백 없이 꽉 채워라"
    ),
    "clinical_bar_compare": "- 짙은 톤의 단색 또는 은은한 그라데이션 배경만 그려라(수치·막대는 프론트가 얹는다)",
    "clinical_photo_compare": "- 차분한 단색 또는 은은한 그라데이션 배경만 그려라(비교 사진은 판매자가 올린다)",
}

_DEFAULT_COMPOSITION = (
    "- 이 제품 제형에 맞는 질감·소재의 클로즈업: {hint}\n"
    "- 또는 색·빛·그라데이션 위주의 추상 배경(제형 질감 없이)"
)


def _composition_lines(layout_type: str, product_type: str | None) -> str:
    """layout_type별 "무엇을 그릴지" 지시를 낸다. 카탈로그에 없는 유형은 기존
    범용 문구(질감 또는 추상 배경)로 폴백한다."""
    hint = _texture_hint(product_type)
    template = _COMPOSITION_BY_LAYOUT_TYPE_TEMPLATES.get(layout_type, _DEFAULT_COMPOSITION)
    return template.format(hint=hint)


# 사진성 배경이 필요없는 layout_type. 어휘집 정의상 아이콘·표·배너 텍스트라 사진
# 배경 슬롯이 아니다. 지금까지는 여기도 이미지를 만들어서 프론트가 그냥 버리고
# 있었다(2026-08-19, 팀장 확인 후 스킵 승인).
_NO_IMAGE_LAYOUT_TYPES = frozenset({"icon_grid", "table_info", "banner_strip"})

# layout_type별 손·팔 허용 여부. "손으로 제품 바르는 장면"이 모든 모듈에 예시로
# 똑같이 들어가 있으면 모델이 매번 그리로 수렴한다(2026-08-19 실측·팀장 지적: 한
# 페이지 6장이 전부 손 장면으로 나옴). kind는 LLM이 자유롭게 짓는 문자열이라
# 커버리지를 보장 못 해서 layout_type을 쓴다.
_HAND_ALLOWED_LAYOUT_TYPES = frozenset({"hero_fullbleed", "step_list"})

_HAND_ALLOWED_LINE = (
    "- 필요하면 손·팔·뒷모습 등 얼굴이 안 보이는 신체 일부를 자연스럽게 넣어도 된다\n"
    "  (예: 손으로 제품을 바르는 장면). 얼굴은 절대 안 됨(아래 금지 목록 참고)"
)
_HAND_FORBIDDEN_LINE = "- 사람 신체(손·팔 포함)는 넣지 마라. 위 지시대로만 그려라"


def _body_part_line(layout_type: str) -> str:
    """모듈 구도 지시를 layout_type에 따라 가른다."""
    return _HAND_ALLOWED_LINE if layout_type in _HAND_ALLOWED_LAYOUT_TYPES else _HAND_FORBIDDEN_LINE


_NO_PRODUCT_INSTRUCTION = "- **제품(병·튜브·용기·패키지)을 그리지 마라.** 제품 사진은 판매자가 직접 올린다."
_COMPOSITE_PRODUCT_INSTRUCTION = (
    "- **참조로 첨부된 실제 제품 사진 속 병·용기·패키지의 형태·라벨·색상을 그대로 유지하라.** "
    "제품을 다시 그리거나 상상해서 새로 만들지 마라. 배경·연출만 자연스럽게 그 주위에 합성하라."
)


def build_image_prompt(
    module: LayoutModule,
    req: GenerateRequest,
    product_type: str | None = None,
    has_product_photo: bool = False,
) -> str:
    """모듈 하나의 이미지 프롬프트를 만든다.

    product_type(플래너가 추측한 세럼/토너/크림 등)을 주면 그 제형에 맞는 질감
    예시를 넣는다. 안 주면 중립 힌트로 폴백한다(제형을 특정하지 않는 원료 클로즈업).
    컬러톤·분위기는 req와 product_type만으로 결정되므로(_resolve_tone), 같은
    요청의 모듈들은 전부 같은 톤 문구를 받는다. 호출자가 따로 안 맞춰줘도 된다.

    has_product_photo: 판매자가 올린 제품사진을 참조 이미지로 넘기는 경우(True)엔
    "제품을 그리지 마라"가 아니라 "참조 사진 속 실제 제품을 유지하며 합성하라"로
    지시가 바뀐다. 참조가 없을 땐 기존처럼 제품을 아예 안 그린다(가짜 라벨 방지,
    39b2b54 참고).

    module.layout_type으로 구도(_composition_lines)와 손·팔 허용 여부(_body_part_line)를
    가른다. 안 가르면 모든 모듈이 비슷한 추상 그라데이션이나 "손으로 제품 바르는
    장면"으로 수렴한다(2026-08-19 실측·팀장 지적).
    """
    return _PROMPT.format(
        product_name=req.product_name or "화장품",
        product_type_line=f" ({product_type})" if product_type else "",
        purpose=module.purpose or module.kind,
        tone=_resolve_tone(req, product_type),
        composition_lines=_composition_lines(module.layout_type, product_type),
        body_part_line=_body_part_line(module.layout_type),
        product_instruction=_COMPOSITE_PRODUCT_INSTRUCTION if has_product_photo else _NO_PRODUCT_INSTRUCTION,
    )


def _user_controlled_text(module: LayoutModule, req: GenerateRequest) -> str:
    """사칭 가드가 검사할 부분만 뽑는다.

    조립된 프롬프트 전체를 검사하면 안 된다. 프롬프트에는 "의사를 넣지 마라" 같은
    금지 지시문이 들어 있어서, 키워드 가드가 우리 안전장치를 사칭으로 오인한다.
    가드가 막아야 할 건 사용자·LLM이 넣은 값(상품명, 모듈 목적, 컬러톤·분위기).
    컬러톤·분위기도 인터뷰 자유서술이라 검사 대상에 넣었다(2026-08-19 추가).
    """
    return f"{req.product_name or ''} {module.purpose or ''} {req.color_tone or ''} {req.mood or ''}"


def generate_module_images(
    plan: LayoutPlan,
    req: GenerateRequest,
    generator,
    max_images: int = DEFAULT_MAX_IMAGES,
    photo_resolver=None,
) -> tuple[list[ModuleImage], dict[str, bytes]]:
    """계획된 모듈마다 이미지를 만든다.

    반환: (모듈별 결과 메타, {모듈kind: PNG바이트}). 바이트 저장은 호출자가 정한다.
    generator가 None이면 아무것도 만들지 않는다(생성기 미도입 상태에서도 응답은 나가게).

    photo_resolver: `(photo_id 목록) -> PNG/JPEG 바이트 목록`. 판매자가 올린 제품사진이
    있으면(req.product_photo_ids) 모든 모듈에 같은 참조 이미지로 넘긴다(합성, 팀장
    승인 방식 A). 배경마다 다른 사진을 쓰는 기능은 아직 없다. 조회는 한 번만 한다
    (모듈마다 다시 부르면 저장소를 반복 왕복한다).
    """
    results: list[ModuleImage] = []
    blobs: dict[str, bytes] = {}
    if generator is None:
        return results, blobs

    reference_images: list[bytes] = []
    if photo_resolver is not None and req.product_photo_ids:
        try:
            reference_images = photo_resolver(req.product_photo_ids)
        except Exception as e:
            # 예상된 실패(사진 조회 실패)라 참조 없이 계속 진행한다(배경만 생성).
            print(f"    [skip] 제품사진 조회 실패(참조 없이 진행): {type(e).__name__}: {e}")

    made = 0
    for module in plan.modules:
        if module.layout_type in _NO_IMAGE_LAYOUT_TYPES:
            # 사진 배경이 필요없는 유형이라 애초에 시도하지 않는다(과금 호출 자체를
            # 안 함). 상한을 소모하지도 않는다. 원래 셀 자격이 없던 이미지다.
            results.append(
                ModuleImage(
                    module_kind=module.kind,
                    status="skipped",
                    reason=f"{module.layout_type}은 사진 배경이 필요없는 유형이라 이미지를 만들지 않습니다",
                )
            )
            continue

        if made >= max_images:
            # 상한으로 잘린 것도 기록한다. 조용히 자르면 "다 만들었다"로 오해된다.
            results.append(
                ModuleImage(
                    module_kind=module.kind,
                    status="skipped",
                    reason=f"이미지 생성 상한({max_images}장)을 넘어 건너뛰었습니다",
                )
            )
            continue

        prompt = build_image_prompt(
            module, req, plan.product_type, has_product_photo=bool(reference_images)
        )
        allowed, deny_reason = check_impersonation(_user_controlled_text(module, req))
        if not allowed:
            results.append(
                ModuleImage(module_kind=module.kind, status="skipped", reason=deny_reason)
            )
            continue

        try:
            blobs[module.kind] = generator.generate_image(prompt, reference_images)
        except Exception as e:
            # 과금 호출이라 재시도하지 않는다. 이 모듈만 스킵하고 나머지는 계속.
            reason = f"이미지 생성 실패: {type(e).__name__}"
            print(f"    [skip] 이미지 생성 실패({module.kind}): {type(e).__name__}: {e}")
            results.append(ModuleImage(module_kind=module.kind, status="skipped", reason=reason))
            continue

        results.append(ModuleImage(module_kind=module.kind, status="generated"))
        made += 1

    return results, blobs
