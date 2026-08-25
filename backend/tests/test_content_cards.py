"""모듈 기준 카드 산출물 + 프리셋 (2026-08-22 팀장 확정).

긴 스크롤 상세페이지를 대체한다. 카드 한 장 = 이미지 1장 + 문장 1개.

    venv/bin/python -m pytest tests/test_content_cards.py -q
"""

from barum.generate.content import build_cards
from barum.generate.layout import CARD_LIMIT, select_top_modules
from barum.models import (
    ClinicalEvidence,
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
    # 우선순위가 낮은 것부터 빠진다. (스킵 사유의 category는 화면에 뜨는 값이라
    # 2026-08-23부터 kind가 아니라 한글 purpose를 담는다. 여기선 kept로 확인한다.)
    assert {"brand_story", "lineup", "bundle_suggestion"}.isdisjoint(kinds)
    assert len(skipped) == 3
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


# ── 인정문구가 자리를 못 찾을 때 (2026-08-23) ──────────────────────────────

def test_자리_못_찾은_인정문구가_조용히_사라지지_않는다():
    """**create 모드의 존재 이유가 사라지는 유실이다.**

    인정문구는 계획에 `has_claim_risk` 모듈이 있어야 거기 붙는다. 플래너가 그런
    모듈을 하나도 안 내면 module_kind가 None으로 남고, build_cards는 plan.modules를
    돌기 때문에 카드가 안 생긴다. 검증된 법정 문구가 흔적도 없이 빠진다.
    """
    from barum.generate.content import _unplaced_claim_skips
    from barum.models import Section

    claim = Section(kind="광고문구", text="피부의 미백에 도움을 준다.", source="approved_claim")
    skips = _unplaced_claim_skips([claim])
    assert len(skips) == 1
    assert "피부의 미백에 도움을 준다." in skips[0].reason


def test_모듈에_붙은_인정문구는_스킵이_아니다():
    from barum.generate.content import _unplaced_claim_skips
    from barum.models import Section

    claim = Section(
        kind="광고문구", text="피부의 미백에 도움을 준다.",
        source="approved_claim", module_kind="efficacy_explain",
    )
    assert _unplaced_claim_skips([claim]) == []


def test_위험모듈이_없으면_인정문구가_히어로에_붙는다():
    """2026-08-23 팀장 확정 (가). 전엔 붙을 자리가 없어 조용히 사라졌다."""
    from barum.generate.content import _link_risky_module_sections, build_cards
    from barum.models import ImagePlan, LayoutModule, LayoutPlan, Section

    claim = Section(kind="광고문구", text="피부의 미백에 도움을 준다.", source="approved_claim")
    hero = Section(kind="hero_intro", text="데일리 크림\n가벼운 텍스처", source="llm", module_kind="hero_intro")
    plan = LayoutPlan(
        modules=[LayoutModule(kind="hero_intro", purpose="소개", layout_type="hero_fullbleed")]
    )
    sections = [claim, hero]
    _link_risky_module_sections(sections, plan)

    assert claim.module_kind == "hero_intro"
    cards = build_cards(sections, plan, ImagePlan())
    # 검증된 문구가 생성 카피를 이긴다(build_cards는 setdefault, 인정문구가 앞에 있다).
    assert [c.text_source for c in cards] == ["approved_claim"]
    assert cards[0].headline == "피부의 미백에 도움을 준다."


def test_위험모듈이_있으면_거기_붙고_히어로는_그대로다():
    """히어로 폴백은 마지막 수단이다. 원래 자리가 있으면 그쪽이 우선이다."""
    from barum.generate.content import _link_risky_module_sections
    from barum.models import LayoutModule, LayoutPlan, Section

    claim = Section(kind="광고문구", text="피부의 미백에 도움을 준다.", source="approved_claim")
    plan = LayoutPlan(
        modules=[
            LayoutModule(kind="hero_intro", purpose="소개", layout_type="hero_fullbleed"),
            LayoutModule(
                kind="efficacy_explain", purpose="효능", layout_type="section_statement",
                has_claim_risk=True,
            ),
        ]
    )
    _link_risky_module_sections([claim], plan)
    assert claim.module_kind == "efficacy_explain"


def test_히어로도_없으면_스킵으로_남는다():
    """자리가 정말 없을 때는 조용히 사라지지 않고 사유가 남아야 한다."""
    from barum.generate.content import _link_risky_module_sections, _unplaced_claim_skips
    from barum.models import LayoutModule, LayoutPlan, Section

    claim = Section(kind="광고문구", text="피부의 미백에 도움을 준다.", source="approved_claim")
    plan = LayoutPlan(
        modules=[LayoutModule(kind="how_to_use", purpose="사용법", layout_type="step_list")]
    )
    _link_risky_module_sections([claim], plan)
    assert claim.module_kind is None
    assert _unplaced_claim_skips([claim])


# ── 자유생성 카피도 게이트를 통과해야 한다 (2026-08-23) ────────────────────

def test_생성_카피에_위반이_있으면_교체한다():
    """**프롬프트 지시만으론 안 막힌다.**

    `_MODULE_PROMPT`가 "효능·질병 표현을 쓰지 마라"라고 하지만 그건 지시일 뿐이고
    뒤에 아무 장치가 없었다. 특히 사용자 자유서술(notes)에 위반 문구가 들어 있으면
    모델이 그걸 그대로 옮긴다(재현 확인). 재검증은 잡았지만 아무것도 안 고쳤다.
    """
    from barum.generate.content import _sanitize_generated
    from barum.models import Section

    class Rewriter:
        def generate_json(self, prompt, images):
            return {"items": [{"index": 0, "can_suggest": True, "suggestion": "산뜻하게 발리는 제형"}]}

    secs = [Section(kind="ingredient_highlight", text="줄기세포 배양 기반 성분입니다.", source="llm")]
    out = _sanitize_generated(secs, Rewriter())
    assert "줄기세포" not in out[0].text


def test_위반이_없으면_손대지_않는다():
    """탐지는 규칙 매칭이라 과금이 없다. 안 걸리면 재작성 호출도 안 나간다."""
    from barum.generate.content import _sanitize_generated
    from barum.models import Section

    class NeverCalled:
        def generate_json(self, prompt, images):
            raise AssertionError("위반이 없는데 재작성을 불렀다")

    text = "산뜻하게 발리는 가벼운 제형입니다."
    out = _sanitize_generated([Section(kind="texture_visual", text=text, source="llm")], NeverCalled())
    assert out[0].text == text


def test_섹션이_비어도_안_터진다():
    from barum.generate.content import _sanitize_generated
    from barum.models import Section

    class NeverCalled:
        def generate_json(self, prompt, images):
            raise AssertionError("부르면 안 된다")

    assert _sanitize_generated([], NeverCalled()) == []
    out = _sanitize_generated([Section(kind="x", text="", source="llm")], NeverCalled())
    assert out[0].text == ""


# ── 재검증에 성분을 제대로 넘긴다 (2026-08-23) ─────────────────────────────

def test_판정용_전성분은_이름만_넘긴다():
    """**함량을 이름 칸에 붙이면 성분표 대조가 이름을 못 찾는다.**

    "나이아신아마이드 3%"로 넘기면 대조가 실패해 "고시원료가 전성분에 없음"으로
    읽고, 검토필요를 **위반으로 격상**시킨다(실측). 함량은 별도 인자로 간다.
    """
    from barum.generate.content import _amounts_for_judge, _ingredients_for_judge
    from barum.models import GenerateRequest, IngredientAmount

    req = GenerateRequest(
        mode="create",
        ingredient_amounts=[
            IngredientAmount(name="나이아신아마이드", amount="3%"),
            IngredientAmount(name="히알루론산", amount="1%"),
        ],
    )
    assert _ingredients_for_judge(req) == "나이아신아마이드, 히알루론산"
    assert _amounts_for_judge(req) == "나이아신아마이드:3%,히알루론산:1%"


def test_성분이_없으면_None이지_미상이_아니다():
    """**'(미상)'을 판정기에 넘기면 그걸 성분명으로 읽는다.**

    그러면 "고시원료가 전성분에 없음"이 되어 검토필요가 위반으로 격상된다.
    없으면 없다고 해야 판정기가 "확인 못 함"으로 정직하게 남긴다.
    """
    from barum.generate.content import (
        _amounts_for_judge,
        _ingredients_for_judge,
        _ingredients_for_prompt,
    )
    from barum.models import GenerateRequest

    req = GenerateRequest(content="x")
    assert _ingredients_for_judge(req) is None
    assert _amounts_for_judge(req) is None
    # 프롬프트는 사람이 읽는 것이라 자리표시자가 맞다.
    assert _ingredients_for_prompt(req) == "(미상)"


def test_프롬프트용은_함량을_같이_보여준다():
    from barum.generate.content import _ingredients_for_prompt
    from barum.models import GenerateRequest, IngredientAmount

    req = GenerateRequest(
        mode="create",
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
    )
    assert _ingredients_for_prompt(req) == "나이아신아마이드 3%"


def test_improve_전성분이_판정에서도_우선한다():
    from barum.generate.content import _ingredients_for_judge
    from barum.models import GenerateRequest, IngredientAmount

    req = GenerateRequest(
        content="x",
        ingredients="정제수, 글리세린",
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
    )
    assert _ingredients_for_judge(req) == "정제수, 글리세린"


# ── 헤드라인만 길고 본문이 비는 것을 막는다 (2026-08-23) ────────────────────

def test_긴_한_덩어리는_본문으로_돌린다():
    """**프롬프트 지시만으론 100%가 안 된다.**

    #311로 줄바꿈을 요구했는데도 모델이 가끔 안 지킨다. 그러면 긴 한 문장이 통째로
    헤드라인이 되고 본문이 빈다. 화면에서는 그 칸이 짧아지면서 **옆 이미지까지
    26px로 찌그러진다**(실측).
    """
    from barum.generate.content import split_headline

    long_one = "주요 성분인 나이아신아마이드와 히알루론산을 균형 있게 담아 데일리 루틴에 어울립니다."
    head, body = split_headline(long_one)
    assert head == ""
    assert body == long_one


def test_짧은_한_마디는_헤드라인으로_둔다():
    """라벨 같은 짧은 문구는 헤드라인만 있는 게 맞다."""
    from barum.generate.content import split_headline

    head, body = split_headline("주요 성분")
    assert head == "주요 성분"
    assert body == ""


def test_인정문구는_길어도_헤드라인_자리를_지킨다():
    """**법으로 정해진 문구다.** 자외선차단 인정문구는 39자라 길이로는 LLM 카피와
    못 가른다. 부르는 쪽이 출처를 보고 정해준다."""
    from barum.generate.content import split_headline

    claim = "피부를 곱게 태워주거나 자외선으로부터 피부를 보호하는 데 도움을 준다."
    head, body = split_headline(claim, allow_long_headline=True)
    assert head == claim
    assert body == ""


def test_줄바꿈이_있으면_그대로_쪼갠다():
    from barum.generate.content import split_headline

    head, body = split_headline("발림성부터 다릅니다\n젤-세럼 타입입니다. 끈적임이 없습니다.")
    assert head == "발림성부터 다릅니다"
    assert body.startswith("젤-세럼")


def test_카드가_인정문구만_헤드라인_예외를_준다():
    """LLM 카피에까지 예외를 주면 원래 문제로 돌아간다."""
    from barum.generate.content import build_cards
    from barum.models import ImagePlan, LayoutModule, LayoutPlan, Section

    long_one = "주요 성분인 나이아신아마이드와 히알루론산을 균형 있게 담아 데일리 루틴에 어울립니다."
    plan = LayoutPlan(
        modules=[
            LayoutModule(kind="hero_intro", purpose="소개", layout_type="hero_fullbleed"),
            LayoutModule(kind="ingredient_highlight", purpose="성분", layout_type="image_text_split"),
        ]
    )
    sections = [
        Section(kind="광고문구", text="피부를 곱게 태워주거나 자외선으로부터 피부를 보호하는 데 도움을 준다.",
                source="approved_claim", module_kind="hero_intro"),
        Section(kind="ingredient_highlight", text=long_one, source="llm",
                module_kind="ingredient_highlight"),
    ]
    cards = {c.module_kind: c for c in build_cards(sections, plan, ImagePlan())}
    assert cards["hero_intro"].headline  # 인정문구는 헤드라인 유지
    assert cards["ingredient_highlight"].headline == ""  # LLM 카피는 본문으로
    assert cards["ingredient_highlight"].body == long_one


# ── 자료를 다 싣는다 (2026-08-23 팀장 지시) ────────────────────────────────

def _mod(kind, purpose="목적", risk=False, lt="section_statement"):
    from barum.models import LayoutModule

    return LayoutModule(kind=kind, purpose=purpose, has_claim_risk=risk, layout_type=lt)


def test_보호_모듈은_카드_상한을_안_센다():
    """**보호 모듈이 상한을 먹으면 자료를 넉넉히 넣을수록 카피가 잘린다.**

    실측(2026-08-23): 보호 6장이 상한을 다 먹어 자유생성 카피가 0장이 됐다.
    자료가 많을수록 페이지가 풍성해져야지 빈약해지면 안 된다.
    """
    from barum.generate.layout import CARD_LIMIT, PRODUCT_SPEC_KIND, select_top_modules
    from barum.models import LayoutPlan

    safe = [_mod(f"m{i}") for i in range(8)]
    protected = [_mod(PRODUCT_SPEC_KIND, lt="table_info"), _mod("clinical_result", risk=True)]
    kept, _ = select_top_modules(
        LayoutPlan(modules=safe + protected),
        protected=(PRODUCT_SPEC_KIND, "clinical_result"),
    )
    kinds = [m.kind for m in kept.modules]
    assert PRODUCT_SPEC_KIND in kinds and "clinical_result" in kinds
    # 자유생성 카피도 상한만큼 살아남는다.
    assert len([k for k in kinds if k.startswith("m")]) == CARD_LIMIT


def test_절대_상한은_있다():
    """무제한이면 이미지 과금과 화면 길이가 같이 는다."""
    from barum.generate.layout import HARD_CARD_LIMIT, select_top_modules
    from barum.models import LayoutPlan

    many = [_mod(f"p{i}") for i in range(20)]
    kept, _ = select_top_modules(
        LayoutPlan(modules=many), protected=tuple(m.kind for m in many)
    )
    assert len(kept.modules) == HARD_CARD_LIMIT


def test_스킵_사유가_한글로_나간다():
    """`clinical_intro` 같은 내부 식별자가 화면에 그대로 떴다(팀장 지적)."""
    from barum.generate.layout import select_top_modules
    from barum.models import LayoutPlan

    mods = [_mod(f"m{i}", purpose=f"설명{i}") for i in range(9)]
    _, skipped = select_top_modules(LayoutPlan(modules=mods))
    assert skipped
    assert all(s.category.startswith("설명") for s in skipped)


def test_실증자료가_여러_건이면_섹션도_여러_개():
    """2026-08-20엔 한 섹션에 묶었다. 그러면 임상 모듈이 여러 개여도 채울 섹션이
    하나뿐이라 나머지가 '자료 부족'으로 드롭됐다. 팀장 지시로 뒤집었다."""
    from barum.generate.content import _generate_create_content  # noqa: F401
    from barum.generate.layout import clinical_sections_text
    from barum.models import ClinicalEvidence

    ev = [
        ClinicalEvidence(claim="다크스팟 개선", value="87%"),
        ClinicalEvidence(claim="피부결 개선", value="2.1배"),
    ]
    per = [clinical_sections_text([e]) for e in ev]
    assert len(per) == 2
    assert "87%" in per[0] and "2.1배" in per[1]


def test_전성분_섹션은_LLM을_안_태운다():
    """화장품법상 의무 표시사항이라 지어낼 여지를 두면 안 된다."""
    from barum.generate.content import build_full_ingredient_section
    from barum.models import GenerateRequest, IngredientAmount

    sec = build_full_ingredient_section(
        GenerateRequest(mode="create", ingredient_amounts=[
            IngredientAmount(name="나이아신아마이드", amount="3%"),
        ])
    )
    assert sec.source == "full_ingredient"
    assert sec.table_rows and sec.table_rows[0].label == "나이아신아마이드"


def test_설문은_전용_자리를_받는다():
    """자리가 없으면 섹션만 만들어지고 카드가 안 생겨 화면에서 사라진다."""
    from barum.generate.layout import SURVEY_KIND, ensure_survey_module
    from barum.models import GenerateRequest, LayoutPlan, SurveyEvidence

    req = GenerateRequest(mode="create", survey_evidence=[
        SurveyEvidence(claim="발림성 만족", value="94%", sample_size="150명",
                       institution="유어리서치", period="2026년 3월", method="온라인 설문"),
    ])
    out = ensure_survey_module(LayoutPlan(modules=[]), req)
    assert any(m.kind == SURVEY_KIND for m in out.modules)
    # 설문이 없으면 안 만든다.
    assert ensure_survey_module(LayoutPlan(modules=[]), GenerateRequest(content="x")).modules == []


# ── 실증자료 구조화 (2026-08-24) ────────────────────────────────────────────
#
# 프론트가 수치를 강조하려면 문장을 도로 파싱해야 했다. "4주 후 2.1배" 같은 표기에서
# 그 파싱이 깨지고, 깨진 자리를 지어낸 값으로 메우면 바름이 잡으려는 바로 그 행위가
# 된다. 그래서 입력 객체를 그대로 카드까지 흘린다.


def test_실증자료_카드에_원본_입력값이_그대로_실린다():
    ev = ClinicalEvidence(
        claim="다크스팟 개선", value="87%", period="4주", institution="OO시험", note="20명"
    )
    sections = [
        Section(
            kind="실증자료",
            text="다크스팟 개선 87% (4주), OO시험 시험. 20명",
            source="clinical_evidence",
            module_kind="clinical_result",
            clinical_stat=ev,
        )
    ]
    cards = build_cards(sections, _plan("clinical_result"), ImagePlan(generation=ImageGenResult()))
    assert cards[0].clinical_stat == ev, "입력값을 그대로 넘겨야 지어낼 여지가 없다"
    assert cards[0].text, "구버전 프론트용 문장도 그대로 남아야 한다"


def test_실증자료가_아닌_카드엔_수치가_안_붙는다():
    sections = [Section(kind="제품개요", text="하나", source="llm", module_kind="hero_intro")]
    cards = build_cards(sections, _plan("hero_intro"), ImagePlan(generation=ImageGenResult()))
    assert cards[0].clinical_stat is None


def test_실증자료_두건이면_카드마다_다른_수치가_붙는다():
    """자료 1건=카드 1장이므로 두 카드가 서로 다른 값을 들어야 한다."""
    a = ClinicalEvidence(claim="다크스팟 개선", value="87%")
    b = ClinicalEvidence(claim="피부결 개선", value="4주 후 2.1배")
    sections = [
        Section(kind="실증자료", text="a", source="clinical_evidence",
                module_kind="clinical_intro", clinical_stat=a),
        Section(kind="실증자료", text="b", source="clinical_evidence",
                module_kind="clinical_result", clinical_stat=b),
    ]
    cards = build_cards(
        sections, _plan("clinical_intro", "clinical_result"), ImagePlan(generation=ImageGenResult())
    )
    assert [c.clinical_stat.value for c in cards] == ["87%", "4주 후 2.1배"]


def test_대체표현_카드는_소재가_다양하게_layout_type을_순환한다():
    """improve 배경 이미지가 전부 image_text_split(원료=잎)이라 "나뭇잎만" 나왔다
    (2026-08-25 팀장 실측). 카드마다 layout_type을 순환해 원료·연출·질감이 섞이게 한다.
    카드 렌더는 이미지 있으면 layout_type과 무관하게 균일하므로 카드 모양은 안 바뀐다.
    """
    from barum.generate.content import (
        _replacement_image_modules,
        _REPLACEMENT_IMAGE_LAYOUT_TYPES,
    )
    from barum.models import Replacement, ViolationType

    reps = [
        Replacement(
            original=f"위반{i}",
            replaced=f"안전{i}",
            violation_type=ViolationType.type_5_deception,
            basis="조건표",
        )
        for i in range(4)
    ]
    modules = _replacement_image_modules(reps)
    types = [m.layout_type for m in modules]

    assert len(modules) == 4
    assert len(set(types)) > 1, "전부 같은 소재(잎)면 안 된다"
    # index 순으로 결정적으로 순환한다(같은 입력 -> 같은 결과).
    assert types == [
        _REPLACEMENT_IMAGE_LAYOUT_TYPES[i % len(_REPLACEMENT_IMAGE_LAYOUT_TYPES)]
        for i in range(4)
    ]
