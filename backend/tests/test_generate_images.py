"""모듈별 이미지 생성 오케스트레이션 유닛테스트. 실제 생성기는 안 부른다(가짜 주입)."""

from barum.generate.images import _user_controlled_text, build_image_prompt, generate_module_images
from barum.models import GenerateRequest, LayoutModule, LayoutPlan


class FakeGenerator:
    """호출 순서대로 바이트를 내거나 예외를 던지는 가짜 이미지 생성기."""

    def __init__(self, *results):
        self._results = list(results)
        self.prompts: list[str] = []
        self.images_received: list[list] = []

    def generate_image(self, prompt, images):
        self.prompts.append(prompt)
        self.images_received.append(images)
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


# ── 제품 종류별 질감 (2026-08-19, 토너인데 크림 이미지 나오던 버그 회귀방지) ──
# layout_type을 명시한다. 질감 힌트는 사진성 유형에만 들어가는데, LayoutModule의
# 기본값이 section_statement(어휘집상 "배경색 블록", 질감 안 씀)라 안 적으면
# 힌트가 없는 게 정상이기 때문이다(2026-08-20).


def test_토너_프롬프트에는_크림이_없다():
    """팀장이 지적한 실제 사례: 토너 상품인데 흰 크림 덩어리가 그려짐."""
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입", layout_type="mood_macro"), _REQ, "토너")
    assert "크림" not in prompt
    assert "액체" in prompt or "물방울" in prompt


def test_크림_프롬프트에는_크림_질감이_들어간다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입", layout_type="mood_macro"), _REQ, "크림")
    assert "크림" in prompt


def test_세럼_프롬프트에는_액상_질감이_들어간다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입", layout_type="mood_macro"), _REQ, "세럼")
    assert "크림" not in prompt
    assert "액상" in prompt or "광택" in prompt


def test_product_type_모르면_제형을_특정하지_않는다():
    """폴백은 원료 클로즈업만 시키고 제형(크림·액상 등)을 못 박지 않는다."""
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입", layout_type="mood_macro"), _REQ, None)
    assert "크림" not in prompt
    assert "제품 제형은 특정하지 마라" in prompt


def test_product_type이_인자를_안_줘도_기본값으로_동작한다():
    """기존 호출부(인자 3개 생략)가 안 깨져야 한다."""
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "크림" not in prompt


def test_오케스트레이션이_plan의_product_type을_실제로_전달한다():
    """build_image_prompt만 고치고 호출부(generate_module_images)에서 안 넘기면
    소용없다. 실제로 전달되는지 end-to-end로 확인."""
    plan = LayoutPlan(
        modules=[LayoutModule(kind="hero_intro", purpose="도입")],
        product_type="토너",
        source="planner",
    )
    gen = FakeGenerator(b"A")
    generate_module_images(plan, _REQ, gen)
    assert "크림" not in gen.prompts[0]
    assert "토너" in gen.prompts[0]


# ── 컬러톤·분위기 (2026-08-19, 팀장 요청: 인터뷰 값 반영 + 6장 톤 통일) ──


def test_인터뷰_컬러톤이_프롬프트에_들어간다():
    req = GenerateRequest(mode="create", product_name="테스트", color_tone="베이지·아이보리")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req)
    assert "베이지·아이보리" in prompt


def test_인터뷰_분위기가_프롬프트에_들어간다():
    req = GenerateRequest(mode="create", product_name="테스트", mood="미니멀하고 차분한")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req)
    assert "미니멀하고 차분한" in prompt


def test_컬러톤_분위기_둘다_없으면_기본값으로_폴백한다():
    """product_type도 없을 때(어휘집 4종 밖) 쓰는 중립 기본값. 값이 비어 있어도
    프롬프트에 톤 지시 자체는 있어야 한다."""
    req = GenerateRequest(mode="create", product_name="테스트")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req)
    assert "컬러톤" in prompt
    assert "투명하고 깨끗한" in prompt


# ── 디디 확정 컬러톤 기본값 (2026-08-19, _vocabulary.json category_base_tone) ──


def test_세럼_기본톤은_민트_세이지다():
    req = GenerateRequest(mode="create", product_name="테스트")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req, "세럼")
    assert "민트" in prompt or "세이지" in prompt


def test_토너_기본톤은_워터블루_민트다():
    req = GenerateRequest(mode="create", product_name="테스트")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req, "토너")
    assert "워터 블루" in prompt or "민트" in prompt


def test_크림_기본톤은_아이보리_베이지다():
    req = GenerateRequest(mode="create", product_name="테스트")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req, "크림")
    assert "아이보리" in prompt or "베이지" in prompt


def test_앰플_기본톤은_딥그린_딥네이비다():
    req = GenerateRequest(mode="create", product_name="테스트")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req, "앰플")
    assert "딥그린" in prompt or "딥네이비" in prompt


def test_사용자_컬러톤_입력이_디디_기본값보다_우선한다():
    """인터뷰 값이 있으면 카테고리 기본값을 덮어써야 한다(기존 우선순위 유지)."""
    req = GenerateRequest(mode="create", product_name="테스트", color_tone="완전 다른 톤")
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req, "세럼")
    assert "완전 다른 톤" in prompt
    assert "민트" not in prompt


def test_같은_요청의_모든_모듈이_같은_톤_문구를_받는다():
    """이게 핵심이다. 6장이 제각각이던 문제(2026-08-19 팀장 지적)를
    "매번 같은 입력엔 같은 톤"으로 푼다. 모듈이 달라도 톤 줄은 동일해야 한다."""
    req = GenerateRequest(mode="create", product_name="테스트", mood="비비드하고 화사한")
    p1 = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), req, "세럼")
    p2 = build_image_prompt(LayoutModule(kind="ingredient_highlight", purpose="성분"), req, "세럼")

    def _tone_line(p):
        return next(line for line in p.splitlines() if "컬러톤" in line)

    assert _tone_line(p1) == _tone_line(p2)


def test_컬러톤_분위기도_사칭_가드_검사_대상이다():
    """자유서술 필드라 impersonation 가드가 이것도 봐야 한다."""
    req = GenerateRequest(mode="create", product_name="테스트", mood="의사 가운을 입은 전문가 느낌")
    text = _user_controlled_text(LayoutModule(kind="hero_intro", purpose="도입"), req)
    assert "의사" in text


def test_오케스트레이션에서도_모든_생성_이미지가_같은_톤을_받는다():
    plan = LayoutPlan(
        modules=[
            LayoutModule(kind="hero_intro", purpose="도입"),
            LayoutModule(kind="texture", purpose="제형"),
        ],
        product_type="크림",
        source="planner",
    )
    req = GenerateRequest(mode="create", product_name="테스트", color_tone="딥그린")
    gen = FakeGenerator(b"A", b"B")
    generate_module_images(plan, req, gen)
    assert "딥그린" in gen.prompts[0]
    assert "딥그린" in gen.prompts[1]


# ── 제품사진 업로드 → AI 합성 (2026-08-19, 팀장 승인 방식 A) ──


def test_참조사진_없으면_제품을_그리지_말라는_지시가_들어간다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "제품" in prompt and "그리지 마라" in prompt


def test_참조사진_있으면_합성_지시로_바뀐다():
    prompt = build_image_prompt(
        LayoutModule(kind="hero_intro", purpose="도입"), _REQ, has_product_photo=True
    )
    assert "참조로 첨부된" in prompt
    assert "그대로 유지" in prompt


def test_photo_resolver가_있고_product_photo_ids가_있으면_참조이미지를_생성기에_넘긴다():
    req = GenerateRequest(mode="create", product_name="테스트 세럼", product_photo_ids=["abc123"])
    resolver_calls = []

    def resolver(photo_ids):
        resolver_calls.append(photo_ids)
        return [b"PHOTO"]

    gen = FakeGenerator(b"A")
    generate_module_images(_plan("hero_intro"), req, gen, photo_resolver=resolver)
    assert resolver_calls == [["abc123"]]
    assert gen.images_received == [[b"PHOTO"]]
    assert "참조로 첨부된" in gen.prompts[0]


def test_product_photo_ids가_없으면_resolver를_안_부른다():
    resolver_calls = []

    def resolver(photo_ids):
        resolver_calls.append(photo_ids)
        return [b"PHOTO"]

    gen = FakeGenerator(b"A")
    generate_module_images(_plan("hero_intro"), _REQ, gen, photo_resolver=resolver)
    assert resolver_calls == []
    assert gen.images_received == [[]]


def test_resolver_실패해도_참조없이_생성을_계속한다():
    """사진 조회는 예상된 실패다. 배경 생성 자체를 막으면 안 된다."""
    req = GenerateRequest(mode="create", product_name="테스트", product_photo_ids=["abc123"])

    def resolver(photo_ids):
        raise RuntimeError("storage down")

    gen = FakeGenerator(b"A")
    results, blobs = generate_module_images(_plan("hero_intro"), req, gen, photo_resolver=resolver)
    assert results[0].status == "generated"
    assert gen.images_received == [[]]


# ── 모델샷 범위 (2026-08-19, 팀장 확정: 손·팔·뒷모습 허용, 얼굴은 계속 금지) ──


def test_얼굴은_여전히_금지다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "얼굴" in prompt
    assert "넣지 마라" in prompt


def test_손_팔_뒷모습은_허용_문구가_있다():
    """손 허용 layout_type(hero_fullbleed 등)에서만 나온다(구도 다양화 이후, 2026-08-19)."""
    prompt = build_image_prompt(
        LayoutModule(kind="hero_intro", purpose="도입", layout_type="hero_fullbleed"), _REQ
    )
    assert "손" in prompt and "팔" in prompt
    assert "넣어도 된다" in prompt


def test_실사용_후기_연출_금지가_명시된다():
    """별표5 사·아항(거짓·기만) 근거. 얼굴 유무와 무관하게 금지."""
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "사용 후기" in prompt or "체험담" in prompt


def test_의사_전문가_연상_금지는_그대로_유지된다():
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "의사" in prompt and "전문가" in prompt


# ── 구도 다양화 (2026-08-19, 팀장 지적: 6장 전부 "손으로 바르는 장면"으로 수렴) ──


def test_손_비허용_layout_type은_손_예시가_없다():
    """대부분의 layout_type은 손 자체를 금지해서 텍스처·추상 배경으로 갈리게 한다."""
    prompt = build_image_prompt(
        LayoutModule(kind="ingredient_highlight", purpose="성분", layout_type="image_text_split"), _REQ
    )
    assert "손으로 제품을 바르는 장면" not in prompt
    assert "넣지 마라" in prompt


def test_손_허용은_hero_fullbleed와_step_list뿐이다():
    for layout_type in ("section_statement", "image_text_split", "clinical_bar_compare", "icon_grid",
                          "card_list_repeat", "lineup_strip", "table_info", "banner_strip", "mood_macro",
                          "clinical_photo_compare"):
        prompt = build_image_prompt(
            LayoutModule(kind="x", purpose="x", layout_type=layout_type), _REQ
        )
        assert "손으로 제품을 바르는 장면" not in prompt, f"{layout_type}에 손 예시가 남아있음"


def test_기본_layout_type도_손을_강제하지_않는다():
    """layout_type을 안 정해도(모델 기본값 section_statement) 손으로 안 쏠려야 한다."""
    prompt = build_image_prompt(LayoutModule(kind="hero_intro", purpose="도입"), _REQ)
    assert "손으로 제품을 바르는 장면" not in prompt


def test_모듈마다_구도_지시가_달라_페이지_전체가_다양해진다():
    """이게 핵심 회귀 테스트다. hero_fullbleed 하나만 손을 받고 나머지는 다른
    구도를 강제받아야, 6장이 전부 같은 장면으로 수렴하던 버그가 재발하지 않는다."""
    hand_allowed = build_image_prompt(
        LayoutModule(kind="hero_intro", purpose="도입", layout_type="hero_fullbleed"), _REQ
    )
    hand_forbidden = build_image_prompt(
        LayoutModule(kind="texture", purpose="제형", layout_type="mood_macro"), _REQ
    )
    assert "넣어도 된다" in hand_allowed
    assert "넣지 마라" in hand_forbidden
    assert hand_allowed != hand_forbidden


# ── 구도 구체화 + 흐림 금지 (2026-08-20, 팀장 실측: "너무 추상적"·"전체적으로 뿌옇다") ──


def test_사진성_layout_type은_그라데이션만_금지한다():
    for layout_type in ("hero_fullbleed", "image_text_split", "mood_macro"):
        prompt = build_image_prompt(
            LayoutModule(kind="x", purpose="x", layout_type=layout_type), _REQ
        )
        assert "그라데이션" in prompt and ("안 된다" in prompt or "채우지 마라" in prompt)

def test_layout_type마다_구도_지시가_서로_다르다():
    hero = build_image_prompt(LayoutModule(kind="a", purpose="a", layout_type="hero_fullbleed"), _REQ)
    split = build_image_prompt(LayoutModule(kind="b", purpose="b", layout_type="image_text_split"), _REQ)
    macro = build_image_prompt(LayoutModule(kind="c", purpose="c", layout_type="mood_macro"), _REQ)
    assert len({hero, split, macro}) == 3


def test_선명함_지시가_모든_프롬프트에_들어간다():
    prompt = build_image_prompt(LayoutModule(kind="x", purpose="x"), _REQ)
    assert "선명" in prompt
    assert "뿌옇" in prompt or "흐림" in prompt


def test_clinical_비교_유형은_단색_배경만_지시한다():
    prompt = build_image_prompt(
        LayoutModule(kind="x", purpose="x", layout_type="clinical_bar_compare"), _REQ
    )
    assert "단색" in prompt


# ── 사진성 없는 유형은 이미지 생성 자체를 스킵 (2026-08-20, 팀장 승인) ──


def test_icon_grid_table_info_banner_strip은_이미지_생성을_스킵한다():
    for layout_type in ("icon_grid", "table_info", "banner_strip"):
        plan = _plan_with_layout_types([("x", layout_type)])
        gen = FakeGenerator(b"A")
        results, blobs = generate_module_images(plan, _REQ, gen)
        assert results[0].status == "skipped"
        assert "사진 배경이 필요없는" in results[0].reason
        assert blobs == {}
        assert gen.prompts == []  # 과금 호출 자체를 안 함


def test_스킵된_모듈은_상한을_소모하지_않는다():
    modules = [("a", "table_info"), ("b", "hero_fullbleed")]
    plan = _plan_with_layout_types(modules)
    gen = FakeGenerator(b"A")
    results, blobs = generate_module_images(plan, _REQ, gen, max_images=1)
    statuses = {r.module_kind: r.status for r in results}
    assert statuses["a"] == "skipped"
    assert statuses["b"] == "generated"


def _plan_with_layout_types(kind_layout_pairs):
    return LayoutPlan(
        modules=[
            LayoutModule(kind=k, purpose=f"{k} 목적", layout_type=lt)
            for k, lt in kind_layout_pairs
        ],
        product_type="세럼",
        source="planner",
    )


# ── layout_type별 구도 분화·변주 (2026-08-20, 제형 사진 3장 중복 버그 회귀방지) ──


def _prompt(layout_type: str, variation_index: int = 0) -> str:
    return build_image_prompt(
        LayoutModule(kind="m", purpose="p", layout_type=layout_type),
        _REQ,
        "세럼",
        variation_index=variation_index,
    )


def test_section_statement는_질감_클로즈업을_안_시킨다():
    """어휘집상 '이미지 없이(또는 최소), 배경색 블록'인데 제형 클로즈업을 받고 있었다."""
    prompt = _prompt("section_statement")
    assert "질감 클로즈업을 그리지 마라" in prompt
    assert "배경면" in prompt


def test_빠져있던_4종이_전부_고유한_구도를_받는다():
    """전부 _DEFAULT_COMPOSITION(제형 클로즈업)으로 새면 같은 사진이 반복된다."""
    prompts = {lt: _prompt(lt) for lt in ("section_statement", "card_list_repeat", "step_list", "lineup_strip")}
    assert len(set(prompts.values())) == 4, "구도 지시가 서로 겹친다"
    for lt, prompt in prompts.items():
        assert "이 제품 제형에 맞는 질감·소재의 클로즈업" not in prompt, f"{lt}이 범용 폴백을 탄다"


def test_같은_유형이_반복되면_변주_지시가_붙는다():
    first, second = _prompt("mood_macro", 0), _prompt("mood_macro", 1)
    assert first != second
    assert "반드시 다르게 그려라" not in first  # 첫 등장은 기존 동작 유지
    assert "반드시 다르게 그려라" in second


def test_변주_지시는_등장마다_달라진다():
    prompts = [_prompt("mood_macro", i) for i in range(4)]
    assert len(set(prompts)) == 4


def test_변주_index가_범위를_넘어도_터지지_않는다():
    # 같은 유형이 5번 이상 나와도 마지막 지시를 재사용하고 예외를 내지 않는다.
    assert "반드시 다르게 그려라" in _prompt("mood_macro", 99)


def test_같은_입력이면_프롬프트가_같다():
    """실행마다 흔들리면 재현·비교가 안 된다. 변주는 난수가 아니라 index로만 갈린다."""
    assert _prompt("mood_macro", 2) == _prompt("mood_macro", 2)


def _plan_with_types(*pairs):
    return LayoutPlan(
        modules=[LayoutModule(kind=k, purpose=f"{k} 목적", layout_type=lt) for k, lt in pairs],
        product_type="세럼",
        source="planner",
    )


def test_같은_유형_모듈들은_서로_다른_프롬프트를_받는다():
    """실제 버그 재현: section_statement 2개 + mood_macro 1개가 거의 같은 사진으로 나왔다."""
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("value_prop", "section_statement"),
        ("cause_explain", "section_statement"),
        ("texture_visual", "mood_macro"),
    )
    generate_module_images(plan, _REQ, gen)
    assert len(gen.prompts) == 3
    assert len(set(gen.prompts)) == 3, "같은 layout_type 모듈이 동일한 프롬프트를 받았다"
    # 두 번째 section_statement에만 변주 지시가 붙는다.
    assert "반드시 다르게 그려라" not in gen.prompts[0]
    assert "반드시 다르게 그려라" in gen.prompts[1]
    assert "반드시 다르게 그려라" not in gen.prompts[2]  # mood_macro는 첫 등장


def test_스킵된_모듈은_변주_순번을_소모하지_않는다():
    """화면에 안 나온 이미지는 '앞선 같은 유형 이미지'가 아니다."""
    gen = FakeGenerator(RuntimeError("생성 실패"), b"PNG")
    plan = _plan_with_types(
        ("a", "mood_macro"),  # 실패로 스킵
        ("b", "mood_macro"),  # 실제로는 첫 이미지라 변주 지시가 붙으면 안 된다
    )
    generate_module_images(plan, _REQ, gen)
    assert "반드시 다르게 그려라" not in gen.prompts[1]
