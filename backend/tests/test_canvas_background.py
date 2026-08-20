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


# ── 섹션-모듈 연결 (2026-08-20, 이미지 6장 중 4장이 버려지던 문제) ──


def test_pii_제거가_섹션_필드를_떨구지_않는다():
    """필드를 나열해 재조립하던 탓에 module_kind가 조용히 유실됐다."""
    from barum.generate.content import _strip_pii
    from barum.models import Section, TableRow

    original = Section(
        kind="광고문구",
        text="문구",
        source="approved_claim",
        module_kind="hero_intro",
        table_rows=[TableRow(label="제형", value="크림")],
    )
    cleaned, _ = _strip_pii([original])
    assert cleaned[0].module_kind == "hero_intro"
    assert cleaned[0].table_rows == original.table_rows


def test_인정문구_섹션이_위반소지_모듈에_연결된다():
    """hero_intro의 내용은 인정문구가 채워서 kind가 '광고문구'로 나온다.
    연결이 없으면 프론트가 hero_intro 이미지를 못 찾아 버린다."""
    from barum.generate.content import _link_risky_module_sections
    from barum.models import Section

    plan = LayoutPlan(
        modules=[
            LayoutModule(kind="hero_intro", purpose="도입", has_claim_risk=True),
            LayoutModule(kind="value_prop", purpose="가치", has_claim_risk=True),
            LayoutModule(kind="clinical_result", purpose="수치", has_claim_risk=True),
        ],
        product_type="세럼",
        source="planner",
    )
    sections = [
        Section(kind="광고문구", text="a", source="approved_claim"),
        Section(kind="광고문구", text="b", source="approved_claim"),
        Section(kind="실증자료", text="c", source="clinical_evidence"),
    ]
    _link_risky_module_sections(sections, plan)
    assert [s.module_kind for s in sections] == ["hero_intro", "value_prop", "clinical_result"]


def test_안전한_모듈_섹션은_건드리지_않는다():
    from barum.generate.content import _link_risky_module_sections
    from barum.models import Section

    plan = LayoutPlan(modules=[], product_type="세럼", source="planner")
    sections = [Section(kind="how_to_use", text="x", source="llm", module_kind="how_to_use")]
    _link_risky_module_sections(sections, plan)
    assert sections[0].module_kind == "how_to_use"


def test_인정문구보다_위반소지_모듈이_많으면_남는_모듈을_뺀다():
    """게이트가 불리언이라 문구 2개에 모듈 3개여도 셋 다 통과한다.
    셋째는 채울 내용이 없는 빈 모듈인데 이미지 생성 대상엔 들어가 과금만 나갔다."""
    from barum.generate.content import _drop_unfilled_risky_modules, _link_risky_module_sections
    from barum.models import Section

    plan = LayoutPlan(
        modules=[
            LayoutModule(kind="hero_intro", purpose="도입", has_claim_risk=True),
            LayoutModule(kind="value_prop", purpose="가치", has_claim_risk=True),
            LayoutModule(kind="persistence_claim", purpose="지속", has_claim_risk=True),
            LayoutModule(kind="how_to_use", purpose="사용법", has_claim_risk=False),
        ],
        product_type="세럼",
        source="planner",
    )
    sections = [
        Section(kind="광고문구", text="a", source="approved_claim"),
        Section(kind="광고문구", text="b", source="approved_claim"),
    ]
    _link_risky_module_sections(sections, plan)
    pruned, skipped = _drop_unfilled_risky_modules(plan, sections)

    assert [m.kind for m in pruned.modules] == ["hero_intro", "value_prop", "how_to_use"]
    assert [s.category for s in skipped] == ["persistence_claim"]
    assert "부족해" in skipped[0].reason


def test_안전한_모듈은_섹션이_없어도_안_뺀다():
    """안전 모듈의 내용은 나중에 generate_module_sections가 채운다. 여기서 빼면 안 된다."""
    from barum.generate.content import _drop_unfilled_risky_modules

    plan = LayoutPlan(
        modules=[LayoutModule(kind="how_to_use", purpose="사용법", has_claim_risk=False)],
        product_type="세럼",
        source="planner",
    )
    pruned, skipped = _drop_unfilled_risky_modules(plan, [])
    assert len(pruned.modules) == 1
    assert skipped == []
