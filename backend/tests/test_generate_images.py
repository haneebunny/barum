"""모듈별 이미지 생성 오케스트레이션 유닛테스트. 실제 생성기는 안 부른다(가짜 주입)."""

from barum.generate.images import build_image_prompt, generate_module_images
from barum.models import GenerateRequest, LayoutModule, LayoutPlan


class FakeGenerator:
    """호출 순서대로 바이트를 내거나 예외를 던지는 가짜 이미지 생성기."""

    def __init__(self, *results):
        self._results = list(results)
        self.prompts: list[str] = []

    def generate_image(self, prompt, images):
        self.prompts.append(prompt)
        result = self._results.pop(0) if self._results else b"PNG"
        if isinstance(result, Exception):
            raise result
        return result


def _plan(*kinds):
    return LayoutPlan(
        modules=[LayoutModule(kind=k, purpose=f"{k} 목적") for k in kinds],
        product_type="세럼",
        source="planner",
    )


_REQ = GenerateRequest(mode="create", product_name="테스트 세럼")


# ── 프롬프트 ──


def test_프롬프트가_텍스트_금지를_명시한다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입부"), _REQ)
    assert "글자" in prompt
    assert "테스트 세럼" in prompt
    assert "도입부" in prompt


def test_프롬프트가_사칭_소재를_금지한다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "의사" in prompt
    assert "그래프" in prompt or "차트" in prompt


# ── 오케스트레이션 ──


def test_모듈마다_이미지를_만든다():
    gen = FakeGenerator(b"A", b"B")
    results, blobs = generate_module_images(_plan("hero_intro", "texture"), _REQ, gen)
    assert [r.status for r in results] == ["generated", "generated"]
    assert blobs == {"hero_intro": b"A", "texture": b"B"}


def test_한_모듈이_실패해도_나머지는_계속_만든다():
    # 과금 호출이라 재시도 없이 그 모듈만 스킵한다.
    gen = FakeGenerator(RuntimeError("safety block"), b"B")
    results, blobs = generate_module_images(_plan("hero_intro", "texture"), _REQ, gen)
    assert results[0].status == "skipped"
    assert "RuntimeError" in results[0].reason
    assert results[1].status == "generated"
    assert blobs == {"texture": b"B"}


def test_생성기가_없으면_아무것도_안_만든다():
    results, blobs = generate_module_images(_plan("hero_intro"), _REQ, None)
    assert results == []
    assert blobs == {}


def test_상한을_넘으면_사유를_남기고_건너뛴다():
    # 조용히 자르면 "다 만들었다"로 오해된다.
    results, blobs = generate_module_images(
        _plan("a", "b", "c"), _REQ, FakeGenerator(), max_images=2
    )
    assert [r.status for r in results] == ["generated", "generated", "skipped"]
    assert "상한" in results[2].reason
    assert len(blobs) == 2


def test_실패한_모듈은_상한을_소모하지_않는다():
    # 실패분까지 상한에 세면 만들 수 있는 이미지가 부당하게 줄어든다.
    gen = FakeGenerator(RuntimeError("boom"), b"B", b"C")
    results, blobs = generate_module_images(_plan("a", "b", "c"), _REQ, gen, max_images=2)
    assert [r.status for r in results] == ["skipped", "generated", "generated"]
    assert len(blobs) == 2


def test_사칭_가드에_걸리면_생성_안_하고_사유를_남긴다():
    # 모듈 purpose에 사칭 소재가 섞여 들어온 경우.
    plan = LayoutPlan(
        modules=[LayoutModule(kind="hero_intro", purpose="의사가 추천하는 장면")],
        product_type="세럼",
        source="planner",
    )
    gen = FakeGenerator(b"A")
    results, blobs = generate_module_images(plan, _REQ, gen)
    assert results[0].status == "skipped"
    assert results[0].reason
    assert blobs == {}
    assert gen.prompts == []  # 생성기를 아예 안 부른다(과금 방지)


def test_프롬프트의_금지문구가_사칭가드를_스스로_트리거하지_않는다():
    """프롬프트에 "의사를 넣지 마라"가 들어있다고 해서 생성이 막히면 안 된다.

    조립된 프롬프트 전체를 가드에 넣으면 우리 안전장치가 사칭으로 오인돼 모든
    이미지 생성이 조용히 막힌다(실제로 있었던 결함).
    """
    gen = FakeGenerator(b"A")
    results, blobs = generate_module_images(_plan("hero_intro"), _REQ, gen)
    assert results[0].status == "generated"
    assert blobs == {"hero_intro": b"A"}
    # 가드가 통과시킨 뒤 실제로 보낸 프롬프트에는 금지 지시문이 그대로 살아있어야 한다.
    assert "의사" in gen.prompts[0]
