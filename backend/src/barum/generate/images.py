"""모듈별 이미지 생성 오케스트레이션 (FR-13, create 모드).

계획된 모듈마다 배경 이미지를 만든다. **텍스트는 굽지 않는다.** 프론트가 이미지 위에
문구를 얹는 구조라, 모델에는 배경·연출만 시킨다(하니·PM 확정, 2026-08-18).

과금 호출이라 모듈 단위로 실패를 격리한다. 한 모듈이 실패해도 나머지는 계속 만들고,
실패분은 `ModuleImage.status="skipped"`에 사유를 남긴다(조용히 빠지지 않게).
"""

from barum.models import GenerateRequest, LayoutModule, LayoutPlan, ModuleImage
from barum.reference.impersonation import check_impersonation

# 한 요청에 만들 이미지 수 상한. 과금 호출이라 모듈이 12개여도 다 만들지 않는다.
DEFAULT_MAX_IMAGES = 6

_PROMPT = """화장품 상세페이지에 쓸 배경 이미지를 만들어라.

제품: {product_name}
이 이미지의 역할: {purpose}

규칙:
- 이미지 안에 글자·문구·숫자를 절대 넣지 마라. 문구는 나중에 따로 얹는다.
- 사람 얼굴을 클로즈업하지 마라.
- 의사·약사·전문가를 연상시키는 인물이나 소품(가운·청진기 등)을 넣지 마라.
- 시험 결과 그래프나 차트를 만들지 마라.
- 깨끗하고 차분한 화장품 광고 톤으로."""


def build_image_prompt(module: LayoutModule, req: GenerateRequest) -> str:
    """모듈 하나의 이미지 프롬프트를 만든다."""
    return _PROMPT.format(
        product_name=req.product_name or "화장품",
        purpose=module.purpose or module.kind,
    )


def _user_controlled_text(module: LayoutModule, req: GenerateRequest) -> str:
    """사칭 가드가 검사할 부분만 뽑는다.

    조립된 프롬프트 전체를 검사하면 안 된다. 프롬프트에는 "의사를 넣지 마라" 같은
    금지 지시문이 들어 있어서, 키워드 가드가 우리 안전장치를 사칭으로 오인한다.
    가드가 막아야 할 건 사용자·LLM이 넣은 값(상품명, 모듈 목적)이다.
    """
    return f"{req.product_name or ''} {module.purpose or ''}"


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

        prompt = build_image_prompt(module, req)
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
