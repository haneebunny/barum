"""모듈 기준 카드 산출물 + 프리셋 (2026-08-22 팀장 확정).

긴 스크롤 상세페이지를 대체한다. 카드 한 장 = 이미지 1장 + 문장 1개.

    venv/bin/python -m pytest tests/test_content_cards.py -q
"""

from barum.generate.content import build_cards
from barum.generate.layout import CARD_LIMIT, select_top_modules
from barum.models import (
    GenerateRequest,
    ImageGenResult,
    ImagePlan,
    LayoutModule,
    LayoutPlan,
    ModuleImage,
    Section,
)
from barum.reference.presets import apply_preset, audience_hint, get_preset, preset_ids


def _plan(*kinds):
    return LayoutPlan(modules=[LayoutModule(kind=k, purpose="x") for k in kinds])


def _image_plan(*pairs):
    return ImagePlan(
        generation=ImageGenResult(),
        module_images=[
            ModuleImage(module_kind=k, status="generated", image_url=u) for k, u in pairs
        ],
    )


# ── 카드 조립 ──────────────────────────────────────────────────────────────


def test_모듈_순서대로_이미지와_문장을_짝짓는다():
    sections = [
        Section(kind="제품개요", text="하나", source="llm", module_kind="hero_intro"),
        Section(kind="사용법", text="둘", source="llm", module_kind="how_to_use"),
    ]
    cards = build_cards(
        sections,
        _plan("hero_intro", "how_to_use"),
        _image_plan(("hero_intro", "/generated/a"), ("how_to_use", "/generated/b")),
    )
    assert [c.module_kind for c in cards] == ["hero_intro", "how_to_use"]
    assert [c.order for c in cards] == [0, 1]
    assert [c.image_url for c in cards] == ["/generated/a", "/generated/b"]
    assert [c.text for c in cards] == ["하나", "둘"]


def test_module_kind가_kind와_다른_섹션도_짝지어진다():
    """위반소지 모듈의 내용은 인정문구가 채워서 kind가 '광고문구'로 나온다.

    kind로만 찾으면 히어로 카드가 통째로 비는데, 그게 제일 눈에 띄는 자리다.
    """
    sections = [
        Section(kind="광고문구", text="인정문구", source="approved_claim", module_kind="hero_intro")
    ]
    cards = build_cards(sections, _plan("hero_intro"), _image_plan(("hero_intro", "/generated/a")))
    assert len(cards) == 1
    assert cards[0].text == "인정문구"
    assert cards[0].text_source == "approved_claim"


def test_문장_없는_모듈은_카드로_안_낸다():
    """이미지만 있고 글이 없으면 화면에 빈 칸으로 보인다."""
    sections = [Section(kind="제품개요", text="하나", source="llm", module_kind="hero_intro")]
    cards = build_cards(
        sections,
        _plan("hero_intro", "lineup"),
        _image_plan(("hero_intro", "/a"), ("lineup", "/b")),
    )
    assert [c.module_kind for c in cards] == ["hero_intro"]


def test_이미지_없어도_문장만_있으면_카드로_낸다():
    """이미지 생성이 꺼져 있거나 실패한 경우다. 글은 여전히 쓸모가 있다."""
    sections = [Section(kind="제품개요", text="하나", source="llm", module_kind="hero_intro")]
    cards = build_cards(sections, _plan("hero_intro"), ImagePlan(generation=ImageGenResult()))
    assert len(cards) == 1
    assert cards[0].image_url is None
    assert cards[0].image_status == "skipped"


# ── 모듈 추리기 ────────────────────────────────────────────────────────────


def test_카드_수만큼_추리되_계획_순서는_유지한다():
    plan = _plan(
        "brand_story", "hero_intro", "lineup", "ingredient_highlight",
        "clinical_result", "bundle_suggestion", "how_to_use", "caution", "texture_visual",
    )
    kept, skipped = select_top_modules(plan)
    kinds = [m.kind for m in kept.modules]
    assert len(kinds) == CARD_LIMIT
    # 우선순위가 낮은 것부터 빠진다.
    assert {"brand_story", "lineup", "bundle_suggestion"} == {s.category for s in skipped}
    # 남은 것들의 순서는 원래 계획 순서 그대로다(우선순위 순으로 재배열하지 않는다).
    assert kinds == [k for k in [m.kind for m in plan.modules] if k in set(kinds)]


def test_내용이_붙은_모듈은_우선순위가_낮아도_안_버린다():
    """버리면 인정문구·실증자료 섹션이 갈 곳을 잃는다."""
    plan = _plan(
        "brand_story", "hero_intro", "lineup", "ingredient_highlight",
        "clinical_result", "how_to_use", "caution", "texture_visual",
    )
    kept, _ = select_top_modules(plan, protected=("brand_story",))
    assert "brand_story" in [m.kind for m in kept.modules]


def test_모듈이_이미_적으면_안_건드린다():
    plan = _plan("hero_intro", "how_to_use")
    kept, skipped = select_top_modules(plan)
    assert [m.kind for m in kept.modules] == ["hero_intro", "how_to_use"]
    assert skipped == []


def test_순번_붙은_모듈도_우선순위를_찾는다():
    """`_uniquify_kinds`가 clinical_result_2 같은 순번을 붙인다."""
    plan = _plan(
        "brand_story", "lineup", "bundle_suggestion", "full_ingredient_list",
        "efficacy_qna", "clinical_result_2", "hero_intro",
    )
    kept = [m.kind for m in select_top_modules(plan)[0].modules]
    assert "clinical_result_2" in kept
    assert "hero_intro" in kept


# ── 프리셋 ────────────────────────────────────────────────────────────────


def test_프리셋이_타겟팅과_톤을_채운다():
    req, preset = apply_preset(GenerateRequest(mode="create", preset="vivid_pop"))
    assert preset is not None
    assert req.targeting and req.layout_direction and req.color_tone and req.mood


def test_명시값이_프리셋을_이긴다():
    """color_tone·mood는 원래 인터뷰에서 직접 받던 값이다. 덮어쓰면 그 경로가 죽는다."""
    req, _ = apply_preset(
        GenerateRequest(mode="create", preset="vivid_pop", color_tone="내가 지정한 톤")
    )
    assert req.color_tone == "내가 지정한 톤"
    assert req.mood  # 안 준 값은 프리셋이 채운다


def test_모르는_프리셋_id는_요청을_막지_않는다():
    """프리셋은 표현 힌트다. 여기서 막으면 목록이 바뀔 때마다 생성이 통째로 실패한다."""
    req, preset = apply_preset(GenerateRequest(mode="create", preset="없는프리셋"))
    assert preset is None
    assert req.targeting is None  # 아무것도 안 채운다


def test_모든_프리셋이_필수_필드를_갖는다():
    for pid in preset_ids():
        p = get_preset(pid)
        for field in ("label", "targeting", "layout_direction", "color_tone", "mood", "font_tier"):
            assert p.get(field), f"{pid}에 {field}가 없다"


def test_텍스트_프롬프트에는_레이아웃_방향을_안_넣는다():
    """넣었더니 레이아웃 지시가 고객이 읽는 카피로 새어나왔다(2026-08-22 실측).

        "이미지: 드롭퍼 디테일, 텍스처 클로즈업... 설명: ..."
        "미세한 광택을 어둠 속 조명 아래 정교하게 포착했습니다"

    글은 누구에게 말하는지만 알면 된다. 배치는 이미지 프롬프트 몫이다.
    """
    req, _ = apply_preset(GenerateRequest(mode="create", preset="quiet_luxury"))
    hint = audience_hint(req)
    assert req.targeting in hint
    assert req.layout_direction not in hint
    assert "조명" not in hint
    assert audience_hint(GenerateRequest(mode="create")) == ""


# ── 헤드라인 분리 ─────────────────────────────────────────────────────────


def test_카드는_헤드라인과_본문을_쪼개서_준다():
    """"문장 1개"를 어디까지 지킬지 미정이라 프론트가 고를 수 있게 둘 다 준다."""
    from barum.generate.content import split_headline

    assert split_headline("가벼운 텍스처. 워터리한 제형이 퍼집니다.") == (
        "가벼운 텍스처.",
        "워터리한 제형이 퍼집니다.",
    )
    assert split_headline("피부의 미백에 도움을 준다.") == ("피부의 미백에 도움을 준다.", "")
    assert split_headline("헤드라인만\n본문 줄") == ("헤드라인만", "본문 줄")
    assert split_headline("") == ("", "")


def test_소수점은_문장_끝으로_안_본다():
    """"23.5% 개선"이 "…23." + "5% 개선"으로 쪼개지면 사업자 입력 수치가 왜곡된다.

    프론트에서 났던 결함(2026-08-20)을 백엔드로 옮기면서 같이 옮겨오지 않게 고정한다.
    """
    from barum.generate.content import split_headline

    head, body = split_headline("임상 결과 23.5% 개선되었습니다. 4주 사용 기준입니다.")
    assert head == "임상 결과 23.5% 개선되었습니다."
    assert body == "4주 사용 기준입니다."


def test_카드에_헤드라인이_실린다():
    sections = [
        Section(kind="제품개요", text="가벼운 텍스처. 워터리합니다.", source="llm", module_kind="hero_intro")
    ]
    card = build_cards(sections, _plan("hero_intro"), ImagePlan(generation=ImageGenResult()))[0]
    assert card.headline == "가벼운 텍스처."
    assert card.body == "워터리합니다."
    assert card.text == "가벼운 텍스처. 워터리합니다."  # 원문도 그대로 남는다


# ── 프리셋이 이미지 아트디렉션까지 닿는지 ────────────────────────────────


def test_프리셋의_레이아웃_방향이_이미지_톤에_실린다():
    """텍스트 프롬프트만 받고 이미지가 못 받으면 카드 글과 그림이 따로 논다."""
    from barum.generate.images import _resolve_tone

    req, _ = apply_preset(GenerateRequest(mode="create", preset="quiet_luxury"))
    tone = _resolve_tone(req, None)
    assert req.color_tone in tone
    assert req.layout_direction in tone


def test_레이아웃_방향이_없으면_톤만_낸다():
    """프리셋 없이 쓰던 기존 경로가 안 깨져야 한다."""
    from barum.generate.images import _resolve_tone

    tone = _resolve_tone(GenerateRequest(mode="create", color_tone="베이지 톤"), None)
    assert tone == "베이지 톤"


# ── create 모드 성분 데이터가 카피 프롬프트에 들어가는가 (2026-08-23) ─────────

def test_create_모드_성분이_카피_프롬프트에_들어간다():
    """**create 모드는 ingredients가 아니라 ingredient_amounts에 성분을 담는다.**

    그걸 안 보면 사업자가 성분을 입력했는데도 프롬프트엔 "(미상)"이 들어가고,
    LLM이 "전성분 표기는 제공되지 않습니다" 같은 사과문을 쓴다(2026-08-23 실측).
    """
    from barum.generate.content import _ingredients_for_prompt
    from barum.models import GenerateRequest, IngredientAmount

    req = GenerateRequest(
        mode="create",
        ingredient_amounts=[
            IngredientAmount(name="나이아신아마이드", amount="3%"),
            IngredientAmount(name="히알루론산", amount="1%"),
        ],
    )
    out = _ingredients_for_prompt(req)
    assert "나이아신아마이드" in out and "3%" in out
    assert "히알루론산" in out


def test_improve_모드_전성분이_우선한다():
    from barum.generate.content import _ingredients_for_prompt
    from barum.models import GenerateRequest, IngredientAmount

    req = GenerateRequest(
        content="x",
        ingredients="정제수, 글리세린",
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
    )
    assert _ingredients_for_prompt(req) == "정제수, 글리세린"


def test_성분이_아예_없으면_미상이다():
    """지어내지 않는다."""
    from barum.generate.content import _ingredients_for_prompt
    from barum.models import GenerateRequest

    assert _ingredients_for_prompt(GenerateRequest(content="x")) == "(미상)"


def test_모듈_프롬프트가_줄바꿈_분리를_요구한다():
    """줄바꿈이 없으면 split_headline이 첫 마침표까지 삼켜 헤드라인이 문장이 된다.

    실측(2026-08-23): 6장 중 4장의 헤드라인이 30자 넘는 문장이 되고 hero는 본문이
    비었다. 프롬프트가 "첫 문장은 20자 이내"만 요구하고 구분자를 안 정했던 탓이다.
    """
    from barum.generate.content import _MODULE_PROMPT

    assert "줄을 바꾼 뒤" in _MODULE_PROMPT
    assert "\\n" in _MODULE_PROMPT  # 예시에 줄바꿈 문자 표기가 들어 있다


def test_줄바꿈이_있으면_그게_헤드라인_경계다():
    """마침표보다 줄바꿈이 우선이라 긴 첫 문장도 안 삼킨다."""
    from barum.generate.content import split_headline

    head, body = split_headline("발림성부터 다릅니다\n젤-세럼 타입입니다. 끈적임이 없습니다.")
    assert head == "발림성부터 다릅니다"
    assert body.startswith("젤-세럼")


# ── 상품 스펙표가 카드로 나가는가 (2026-08-23) ──────────────────────────────

def test_스펙표_모듈은_카드_상한에_안_잘린다():
    """**PR #272에서 넣은 카드 상한이 스펙표를 잘랐다.**

    사업자가 직접 입력한 제형·용량을 그대로 옮기는 표라 우선순위가 낮게 잡혀
    있었는데, 상한에 걸려 계획에서 빠졌다. 그런데 섹션은 그대로 만들어져
    **갈 곳 없는 섹션**이 됐다(build_cards는 plan.modules를 돈다). 화면에서
    표가 통째로 사라졌다.
    """
    from barum.generate.layout import PRODUCT_SPEC_KIND, select_top_modules
    from barum.models import LayoutModule, LayoutPlan

    modules = [
        LayoutModule(kind=f"filler_{i}", purpose="x", layout_type="section_statement")
        for i in range(8)
    ]
    modules.append(LayoutModule(kind=PRODUCT_SPEC_KIND, purpose="스펙표", layout_type="table_info"))
    plan = LayoutPlan(modules=modules)

    trimmed, _ = select_top_modules(plan, protected=(PRODUCT_SPEC_KIND,))
    assert any(m.kind == PRODUCT_SPEC_KIND for m in trimmed.modules), "스펙표가 잘렸다"


def test_스펙표_데이터가_카드까지_간다():
    """섹션에 table_rows만 있고 카드가 없으면 화면엔 아무것도 안 나온다."""
    from barum.generate.content import build_cards, build_product_spec_section
    from barum.generate.layout import PRODUCT_SPEC_KIND
    from barum.models import GenerateRequest, ImagePlan, LayoutModule, LayoutPlan

    req = GenerateRequest(mode="create", formulation_type="크림", volume="50ml")
    spec = build_product_spec_section(req)
    assert spec.table_rows, "표 데이터 자체가 안 만들어졌다"

    plan = LayoutPlan(
        modules=[LayoutModule(kind=PRODUCT_SPEC_KIND, purpose="스펙표", layout_type="table_info")]
    )
    cards = build_cards([spec], plan, ImagePlan())
    assert cards, "표 데이터는 있는데 카드가 안 나왔다"
