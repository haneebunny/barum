"""긴 배경 이미지(레이어 구조 1단계) 유닛테스트. 실제 생성기는 안 부른다.

핵심 불변식:
1. 옵트인이다 — 요청 안 하면 과금 호출이 아예 안 일어난다.
2. 모듈 이미지를 대신하지 않는다 — 둘 다 나온다.
3. 실패해도 나머지 생성은 계속된다.
"""

from barum.generate.content import build_image_plan
from barum.generate.images import build_canvas_prompt, generate_canvas_background
from barum.models import GenerateRequest, ImageGenRequest, LayoutModule, LayoutPlan


class FakeGenerator:
    def __init__(self, *results):
        self._results = list(results)
        self.prompts: list[str] = []

    def generate_image(self, prompt, images):
        self.prompts.append(prompt)
        result = self._results.pop(0) if self._results else b"PNG"
        if isinstance(result, Exception):
            raise result
        return result


def _plan():
    return LayoutPlan(
        modules=[LayoutModule(kind="hero_intro", purpose="도입", layout_type="hero_fullbleed")],
        product_type="세럼",
        source="planner",
    )


def _req(canvas: bool):
    return GenerateRequest(
        mode="create",
        product_name="테스트 세럼",
        image_generation=ImageGenRequest(requested=True, canvas_requested=canvas),
    )


# ── 프롬프트 ──


def test_배경_프롬프트가_세로로_긴_비율을_요구한다():
    prompt = build_canvas_prompt(_req(True), "세럼")
    assert "세로로 아주 긴" in prompt
    assert "3배" in prompt


def test_배경_프롬프트가_글자와_제품을_금지한다():
    """긴 배경에서도 같은 안전장치가 걸려야 한다(모듈 이미지와 동일 원칙)."""
    prompt = build_canvas_prompt(_req(True), "세럼")
    assert "글자가 단 하나도 없어야 한다" in prompt
    assert "제품(병·튜브·용기·패키지)을 그리지 마라" in prompt
    assert "얼굴" in prompt


def test_배경_프롬프트가_모듈_이미지와_같은_톤을_쓴다():
    """배경과 그 위 이미지가 다른 톤이면 한 페이지로 안 읽힌다."""
    req = GenerateRequest(
        mode="create", product_name="x", color_tone="베이지 톤", mood="차분한"
    )
    assert "베이지 톤, 차분한" in build_canvas_prompt(req, "세럼")


# ── 옵트인 ──


def test_요청_안_하면_배경을_안_만든다():
    """과금이 느는 변경이라 기본은 꺼져 있어야 한다."""
    gen = FakeGenerator()
    plan = build_image_plan(_req(canvas=False), _plan(), gen)
    assert plan.canvas is None
    # 모듈 이미지 1장만 만들어야 한다(배경 호출이 추가로 안 일어남).
    assert len(gen.prompts) == 1


def test_요청하면_모듈_이미지에_더해_배경도_만든다():
    """대체가 아니라 추가다(팀장 확정)."""
    gen = FakeGenerator()
    plan = build_image_plan(_req(canvas=True), _plan(), gen)
    assert plan.canvas is not None
    assert plan.canvas.status == "generated"
    assert len(plan.module_images) == 1
    assert len(gen.prompts) == 2


# ── 실패 격리 ──


def test_배경_생성이_실패해도_모듈_이미지는_남는다():
    gen = FakeGenerator(b"PNG", RuntimeError("blocked"))  # 모듈 성공, 배경 실패
    plan = build_image_plan(_req(canvas=True), _plan(), gen)
    assert plan.module_images[0].status == "generated"
    assert plan.canvas.status == "skipped"
    assert "실패" in plan.canvas.reason


def test_생성기가_없으면_배경도_없다():
    canvas, blob = generate_canvas_background(_req(True), "세럼", None)
    assert canvas is None and blob is None


# ── 2단계 예약 필드 ──


def test_placements는_지금_항상_비어있다():
    """배치 규칙은 2단계에서 정한다. 프론트는 비면 기존 렌더로 폴백하면 된다."""
    gen = FakeGenerator()
    plan = build_image_plan(_req(canvas=True), _plan(), gen)
    assert plan.canvas.placements == []
