"""모듈별 이미지 생성 오케스트레이션 (FR-13, create 모드).

계획된 모듈마다 배경 이미지를 만든다. **텍스트도 제품도 그리지 않는다.** 원료·질감·추상
배경만 만들고, 문구는 프론트가 위에 얹고 제품샷은 판매자가 직접 올린다.

제품을 그리게 했더니 모델이 라벨에 깨진 글자를 박아 넣었다("AYN", "D-OIBELRAMOLAI" 등,
2026-08-18 실측). "글자 금지"라고 써도 안 지켜진다. 규제 준수를 검사하는 서비스가 가짜
제품 라벨을 만들어내면 자기모순이라, 아예 제품을 안 그리는 쪽으로 바꿨다(하니 확정).

과금 호출이라 모듈 단위로 실패를 격리한다. 한 모듈이 실패해도 나머지는 계속 만들고,
실패분은 `ModuleImage.status="skipped"`에 사유를 남긴다(조용히 빠지지 않게).
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
# **디디(디자이너) 확정 전 임시값이다.** PM이 준 예시("스킨케어→투명·깨끗")만
# 반영했고 토너/세럼/크림 세부 구분은 아직 없다(2026-08-19). 디디가 타입별
# 값을 주면 이 딕셔너리만 바꾸면 된다. 나머지 코드는 안 건드려도 됨.
_TONE_DEFAULTS: dict[str | None, str] = {
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
- 이 제품 제형에 맞는 질감·소재의 클로즈업: {texture_hint}
- 또는 색·빛·그라데이션 위주의 추상 배경(제형 질감 없이)
- 위에 명시한 컬러톤·분위기를 따를 것

절대 넣지 말 것:
- **제품(병·튜브·용기·패키지)을 그리지 마라.** 제품 사진은 판매자가 직접 올린다.
- **라벨·글자·문구·숫자·로고를 넣지 마라.** 문구는 나중에 이 배경 위에 얹는다.
- 사람 얼굴을 클로즈업하지 마라.
- 의사·약사·전문가를 연상시키는 인물이나 소품(가운·청진기 등)을 넣지 마라.
- 시험 결과 그래프나 차트를 만들지 마라.

문구를 얹을 여백이 남도록 화면 한쪽을 비교적 비워 둬라."""


def build_image_prompt(module: LayoutModule, req: GenerateRequest, product_type: str | None = None) -> str:
    """모듈 하나의 이미지 프롬프트를 만든다.

    product_type(플래너가 추측한 세럼/토너/크림 등)을 주면 그 제형에 맞는 질감
    예시를 넣는다. 안 주면 중립 힌트로 폴백한다(제형을 특정하지 않는 원료 클로즈업).
    컬러톤·분위기는 req와 product_type만으로 결정되므로(_resolve_tone), 같은
    요청의 모듈들은 전부 같은 톤 문구를 받는다. 호출자가 따로 안 맞춰줘도 된다.
    """
    return _PROMPT.format(
        product_name=req.product_name or "화장품",
        product_type_line=f" ({product_type})" if product_type else "",
        purpose=module.purpose or module.kind,
        texture_hint=_texture_hint(product_type),
        tone=_resolve_tone(req, product_type),
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
) -> tuple[list[ModuleImage], dict[str, bytes]]:
    """계획된 모듈마다 이미지를 만든다.

    반환: (모듈별 결과 메타, {모듈kind: PNG바이트}). 바이트 저장은 호출자가 정한다.
    generator가 None이면 아무것도 만들지 않는다(생성기 미도입 상태에서도 응답은 나가게).
    """
    results: list[ModuleImage] = []
    blobs: dict[str, bytes] = {}
    if generator is None:
        return results, blobs

    made = 0
    for module in plan.modules:
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

        prompt = build_image_prompt(module, req, plan.product_type)
        allowed, deny_reason = check_impersonation(_user_controlled_text(module, req))
        if not allowed:
            results.append(
                ModuleImage(module_kind=module.kind, status="skipped", reason=deny_reason)
            )
            continue

        try:
            blobs[module.kind] = generator.generate_image(prompt, [])
        except Exception as e:
            # 과금 호출이라 재시도하지 않는다. 이 모듈만 스킵하고 나머지는 계속.
            reason = f"이미지 생성 실패: {type(e).__name__}"
            print(f"    [skip] 이미지 생성 실패({module.kind}): {type(e).__name__}: {e}")
            results.append(ModuleImage(module_kind=module.kind, status="skipped", reason=reason))
            continue

        results.append(ModuleImage(module_kind=module.kind, status="generated"))
        made += 1

    return results, blobs
