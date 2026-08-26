"""모듈별 이미지 생성 오케스트레이션 유닛테스트. 실제 생성기는 안 부른다(가짜 주입)."""

import threading

from barum.generate.images import _user_controlled_text, build_image_prompt, generate_module_images
from barum.models import GenerateRequest, LayoutModule, LayoutPlan


class FakeGenerator:
    """호출 순서대로 바이트를 내거나 예외를 던지는 가짜 이미지 생성기.

    **`generate_module_images`가 파도 단위로 병렬 호출한다(2026-08-24).** 한
    파도에 여러 모듈이 있으면 어느 스레드가 먼저 `generate_image`를 부르는지는
    실행마다 갈린다 - `prompts`/`images_received`에 쌓이는 순서, 그리고 여러 값을
    섞어 넣었을 때(`FakeGenerator(RuntimeError(...), b"B")`) 어느 모듈이 어느 값을
    받는지는 더 이상 "부른 순서"로 예측할 수 없다. 락은 리스트 추가·pop 자체의
    경합만 막고(안전), 어떤 모듈이 어떤 값을 받는지는 여전히 안 정해진다 - 그
    지점을 확인하는 테스트는 값이 아니라 개수/집합으로 검증한다.
    """

    def __init__(self, *results):
        self._results = list(results)
        self.prompts: list[str] = []
        self.images_received: list[list] = []
        self._lock = threading.Lock()

    def generate_image(self, prompt, images):
        with self._lock:
            self.prompts.append(prompt)
            self.images_received.append(images)
            result = self._results.pop(0) if self._results else b"PNG"
        if isinstance(result, Exception):
            raise result
        return result


def _prompt_containing(gen: FakeGenerator, needle: str) -> str:
    """`gen.prompts`에서 `needle`을 담은 프롬프트 하나를 찾는다.

    병렬 호출이라 `gen.prompts[i]`가 "i번째로 만든 모듈"이라는 보장이 없다
    (위 FakeGenerator docstring). 프롬프트 자체가 담은 내용(purpose 등)으로 찾는다.
    """
    matches = [p for p in gen.prompts if needle in p]
    assert len(matches) == 1, f"{needle!r}을 담은 프롬프트가 {len(matches)}개(1개여야 함)"
    return matches[0]


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
    # 같은 파도에서 병렬 호출이라 어느 모듈이 A를 받고 B를 받는지는 안 정해진다
    # (FakeGenerator docstring 참고) - 각자 자기 몫의 실제 값을 받았는지만 본다.
    assert set(blobs) == {"hero_intro", "texture"}
    assert set(blobs.values()) == {b"A", b"B"}


def test_한_모듈이_실패해도_나머지는_계속_만든다():
    # 과금 호출이라 재시도 없이 그 모듈만 스킵한다. 병렬 호출이라 hero_intro·texture
    # 중 누가 실패를 받을지는 안 정해진다(같은 파도) - "격리가 되는지"만 본다.
    gen = FakeGenerator(RuntimeError("safety block"), b"B")
    results, blobs = generate_module_images(_plan("hero_intro", "texture"), _REQ, gen)
    statuses = [r.status for r in results]
    assert statuses.count("skipped") == 1
    assert statuses.count("generated") == 1
    failed = next(r for r in results if r.status == "skipped")
    assert "RuntimeError" in failed.reason
    assert len(blobs) == 1


def test_생성기가_없으면_사유를_남기고_안_만든다():
    """**조용히 빈 목록을 내지 않는다.**

    사용자가 이미지를 요청했는데 결과에 아무 흔적이 없으면 왜 안 나왔는지 알 방법이
    없다(2026-08-23: module_images=[] · reason=null 로 나가 원인 추적에 시간을 썼다).
    """
    results, blobs = generate_module_images(_plan("hero_intro"), _REQ, None)
    assert blobs == {}
    assert len(results) == 1
    assert results[0].status == "skipped"
    assert results[0].reason and "IMAGE_GENERATION_ENABLED" in results[0].reason


def test_상한을_넘으면_사유를_남기고_건너뛴다():
    # 조용히 자르면 "다 만들었다"로 오해된다.
    results, blobs = generate_module_images(
        _plan("a", "b", "c"), _REQ, FakeGenerator(), max_images=2
    )
    assert [r.status for r in results] == ["generated", "generated", "skipped"]
    assert "상한" in results[2].reason
    assert len(blobs) == 2


def test_실패한_모듈은_상한을_소모하지_않는다():
    # 실패분까지 상한에 세면 만들 수 있는 이미지가 부당하게 줄어든다. a·b가 같은
    # 파도라 누가 실패를 받을지는 안 정해지지만, 실패해도 상한(2)만큼은 다음 파도의
    # c가 이어받아 채워야 한다.
    gen = FakeGenerator(RuntimeError("boom"), b"B", b"C")
    results, blobs = generate_module_images(_plan("a", "b", "c"), _REQ, gen, max_images=2)
    statuses = [r.status for r in results]
    assert statuses.count("generated") == 2
    assert statuses.count("skipped") == 1
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


def test_photo_resolver가_있으면_req를_통째로_받고_참조이미지를_생성기에_넘긴다():
    """photo_resolver는 (product_photo_ids)가 아니라 (req)를 받는다(2026-08-24) -
    create·improve가 서로 다른 필드(product_photo_ids/result_id)로 참조를 찾아서,
    어느 쪽인지는 콜백 내부가 정한다. 여기선 create처럼 product_photo_ids를 쓰는
    콜백을 흉내낸다."""
    req = GenerateRequest(mode="create", product_name="테스트 세럼", product_photo_ids=["abc123"])
    resolver_calls = []

    def resolver(r):
        resolver_calls.append(r.product_photo_ids)
        return [b"PHOTO"]

    gen = FakeGenerator(b"A")
    generate_module_images(_plan("hero_intro"), req, gen, photo_resolver=resolver)
    assert resolver_calls == [["abc123"]]
    assert gen.images_received == [[b"PHOTO"]]
    assert "참조로 첨부된" in gen.prompts[0]


def test_resolver가_빈_목록을_주면_참조없이_생성한다():
    """product_photo_ids도 result_id도 없는 요청이면 콜백이 빈 목록을 준다(실제
    콜백은 api/app.py `_resolve_reference_photos`). generate_module_images는 부를지
    말지를 안 정한다 - photo_resolver가 있으면 항상 부르고, 참조가 없다는 판단은
    콜백에 맡긴다(2026-08-24, 예전엔 product_photo_ids 없으면 아예 안 불렀다)."""
    resolver_calls = []

    def resolver(r):
        resolver_calls.append(r)
        return []

    gen = FakeGenerator(b"A")
    generate_module_images(_plan("hero_intro"), _REQ, gen, photo_resolver=resolver)
    assert resolver_calls == [_REQ]
    assert gen.images_received == [[]]


def test_resolver_실패해도_참조없이_생성을_계속한다():
    """사진 조회는 예상된 실패다. 배경 생성 자체를 막으면 안 된다."""
    req = GenerateRequest(mode="create", product_name="테스트", product_photo_ids=["abc123"])

    def resolver(r):
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
    assert "질감 클로즈업은 그리지 마라" in prompt
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
    """실제 버그 재현: section_statement 2개 + mood_macro 1개가 거의 같은 사진으로 나왔다.

    병렬 호출이라 gen.prompts의 도착 순서가 실행마다 갈린다(FakeGenerator docstring) -
    "몇 번째로 도착했나"가 아니라 "그 모듈의 프롬프트에 뭐가 담겼나"로 찾는다.
    """
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("value_prop", "section_statement"),
        ("cause_explain", "section_statement"),
        ("texture_visual", "mood_macro"),
    )
    generate_module_images(plan, _REQ, gen)
    assert len(gen.prompts) == 3
    assert len(set(gen.prompts)) == 3, "같은 layout_type 모듈이 동일한 프롬프트를 받았다"
    # 우선순위 순서(=plan 순서, 전부 tier가 같음)상 먼저 오는 value_prop이 첫
    # section_statement, cause_explain이 두 번째라 변주 지시를 받는다. 이 배정은
    # 순차로 이뤄지므로(파도 진입 전 for문) 실행마다 안 흔들린다 - 병렬인 건 실제
    # generate_image 호출과 그 도착 순서뿐이다.
    assert "반드시 다르게 그려라" not in _prompt_containing(gen, "value_prop 목적")
    assert "반드시 다르게 그려라" in _prompt_containing(gen, "cause_explain 목적")
    assert "반드시 다르게 그려라" not in _prompt_containing(gen, "texture_visual 목적")  # mood_macro는 첫 등장


def test_변주_순번은_시도_순서_기준이다():
    """**병렬화로 의도적으로 바뀐 동작(2026-08-24).** 예전엔 "성공한 것만" 셌지만,
    병렬 호출은 같은 파도 안에서 어느 게 먼저 "성공"하는지가 실행마다 흔들려서 그
    성질을 그대로 재현할 수 없다 - 이제 "시도한"(=합성해 파도에 넣은) 순서로 미리
    배정한다. 실패해도 그 순번은 그대로 소모된다. 영향은 변주 문구 한 줄뿐이고
    사진 성패·모듈 짝짓기는 무관하다(images.py `generate_module_images` docstring).
    """
    gen = FakeGenerator(RuntimeError("생성 실패"), b"PNG")
    plan = _plan_with_types(
        ("a", "mood_macro"),  # 실패하지만 변주 순번은 소모한다
        ("b", "mood_macro"),  # 그래서 두 번째 취급 - 변주 지시를 받는다
    )
    generate_module_images(plan, _REQ, gen)
    assert "반드시 다르게 그려라" in _prompt_containing(gen, "b 목적")


def test_임상_모듈이_여러개면_이미지도_여러장_만든다():
    """자료 1건=섹션 1장으로 바뀌어(content.py) 두 번째 임상 모듈도 얹힐 자리가 있다.

    예전 게이트를 그대로 뒀더니 두 번째 임상 카드가 글만 있고 이미지가 빈 채로
    나왔다(2026-08-24 실측). 데모 골든셋이 실증자료 2건이라 시연에서 바로 보인다.
    """
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("clinical_intro", "section_statement"),
        ("clinical_result", "clinical_bar_compare"),
        ("clinical_result_2", "clinical_photo_compare"),
    )
    results, blobs = generate_module_images(plan, _REQ, gen)
    made = [r for r in results if r.status == "generated"]
    assert [r.module_kind for r in made] == [
        "clinical_intro",
        "clinical_result",
        "clinical_result_2",
    ], "임상 모듈마다 이미지가 나와야 한다"


def test_임상_모듈도_상한을_넘지는_않는다():
    """게이트를 없앤 대신 상한은 그대로 걸려야 한다(과금 폭주 방지)."""
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("clinical_intro", "section_statement"),
        ("clinical_result", "clinical_bar_compare"),
        ("clinical_result_2", "clinical_photo_compare"),
    )
    results, _ = generate_module_images(plan, _REQ, gen, max_images=2)
    assert len([r for r in results if r.status == "generated"]) == 2


def test_임상이_아닌_모듈은_상한까지_계속_만든다():
    """임상 제한이 다른 모듈에 새면 안 된다."""
    gen = FakeGenerator()
    plan = _plan_with_types(("a", "mood_macro"), ("b", "mood_macro"), ("c", "mood_macro"))
    results, _ = generate_module_images(plan, _REQ, gen)
    assert len([r for r in results if r.status == "generated"]) == 3


# ── 참조 제품사진이 있을 때 글자 규칙 (2026-08-23) ──────────────────────────

def _prompt_with(has_photo: bool) -> str:
    from barum.generate.images import build_image_prompt
    from barum.models import GenerateRequest, LayoutModule

    module = LayoutModule(kind="hero_intro", purpose="제품 소개", layout_type="full_bleed_photo")
    req = GenerateRequest(mode="create", product_name="리쥬랩 리페어 크림")
    return build_image_prompt(module, req, product_type="크림", has_product_photo=has_photo)


def test_참조사진이_없으면_글자를_전부_금지한다():
    """모델이 그리는 라벨은 뭉개진 가짜 글자가 된다(39b2b54)."""
    p = _prompt_with(False)
    assert "글자가 단 하나도 없어야 한다" in p
    assert "인쇄된 라벨 전부 포함" in p


def test_참조사진이_있으면_라벨_금지와_충돌하지_않는다():
    """**이게 실제 버그였다.** 합성 지시는 "라벨을 유지하라"인데 최우선 규칙은
    "인쇄된 라벨 포함 금지"라, 최우선 쪽이 이겨서 라벨 없는 빈 병이 나왔다.
    """
    p = _prompt_with(True)
    assert "인쇄된 라벨 전부 포함" not in p, "라벨 금지 규칙이 합성 지시와 충돌한다"
    assert "그대로 유지하라" in p  # 합성 지시는 살아 있다
    assert "용기 표면에 인쇄된 것" in p


def test_참조사진의_배경_카피는_옮겨_그리지_않게_한다():
    """두 갈래(남길 것/새로 만들 것)로만 나누면 참조 페이지의 광고 카피까지
    따라 그린다 — 모델 입장에선 그것도 "새로 쓴 글자"가 아니라서다(2026-08-23 실측).
    """
    p = _prompt_with(True)
    assert "옮겨 그리지 말 것" in p
    assert "광고 문구" in p


def test_참조사진_유무에_따라_글자_규칙이_갈린다():
    assert _prompt_with(True) != _prompt_with(False)


# ── 이미지가 실제 카피를 알게 한다 (2026-08-23) ────────────────────────────

def test_카피를_주면_프롬프트에_실린다():
    """전엔 플래너가 정한 한 줄 목적만 보고 그려서 배경이 카피와 겉돌았다.
    텍스트가 이미지보다 먼저 만들어지는데 그냥 안 넘기고 있었다."""
    from barum.generate.images import build_image_prompt
    from barum.models import GenerateRequest, LayoutModule

    module = LayoutModule(kind="texture_visual", purpose="제형 질감", layout_type="mood_macro")
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    prompt = build_image_prompt(module, req, copy_text="가볍게 흐르는 젤-세럼\n부드럽게 퍼집니다.")
    assert "가볍게 흐르는 젤-세럼" in prompt


def test_카피를_글자로_쓰지_말라고_같이_못박는다():
    """**방어 없이 넣으면 그 문장이 이미지에 구워진다.** 맨 위 글자 금지 규칙과
    정면으로 충돌하는 입력이라 반드시 같이 가야 한다."""
    from barum.generate.images import build_image_prompt
    from barum.models import GenerateRequest, LayoutModule

    module = LayoutModule(kind="texture_visual", purpose="제형 질감", layout_type="mood_macro")
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    prompt = build_image_prompt(module, req, copy_text="가볍게 흐르는 젤-세럼")
    assert "글자로 쓰지 마라" in prompt


def test_카피가_없으면_프롬프트가_안_바뀐다():
    """기존 동작 회귀 없음."""
    from barum.generate.images import build_image_prompt
    from barum.models import GenerateRequest, LayoutModule

    module = LayoutModule(kind="texture_visual", purpose="제형 질감", layout_type="mood_macro")
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    assert "이 자리에 실릴 카피" not in build_image_prompt(module, req)
    assert "이 자리에 실릴 카피" not in build_image_prompt(module, req, copy_text="   ")


def test_섹션에서_모듈별_카피를_뽑는다():
    from barum.generate.content import _copy_by_module
    from barum.models import Section

    secs = [
        Section(kind="광고문구", text="인정문구다.", source="approved_claim", module_kind="hero_intro"),
        Section(kind="texture_visual", text="가벼운 제형", source="llm", module_kind="texture_visual"),
        Section(kind="how_to_use", text="이렇게 쓰세요", source="llm"),  # module_kind 없음 → kind로
    ]
    out = _copy_by_module(secs)
    assert out["hero_intro"] == "인정문구다."
    assert out["texture_visual"] == "가벼운 제형"
    assert out["how_to_use"] == "이렇게 쓰세요"
    assert _copy_by_module(None) == {}


# ── 이미지 상한 배분 우선순위 (2026-08-24) ──────────────────────────────────
#
# 계획 순서대로 상한을 채우면 자유생성 카피가 앞에 몰릴 때 사업자가 낸 실증자료
# 카드가 이미지를 못 받았다. 같은 골든 입력을 세 번 돌렸더니 임상 카드가 각각
# 2장·1장·0장씩 이미지를 받았다(실측). 실행마다 달라져 시연에서 터지는 유형이다.


def test_자유생성_카피가_상한을_다_먹어도_실증자료가_이미지를_받는다():
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("hero_intro", "hero_fullbleed"),
        ("cause_explain", "section_statement"),
        ("ingredient_highlight", "image_text_split"),
        ("texture_visual", "mood_macro"),
        ("how_to_use", "step_list"),
        ("bundle_suggestion", "card_list_repeat"),
        ("clinical_intro", "section_statement"),
        ("clinical_result", "clinical_bar_compare"),
    )
    results, _ = generate_module_images(plan, _REQ, gen, max_images=6)
    made = {r.module_kind for r in results if r.status == "generated"}
    assert "clinical_intro" in made, "사업자가 낸 자료가 자유생성 카피에 밀리면 안 된다"
    assert "clinical_result" in made
    assert len(made) == 6, "상한 자체는 그대로여야 한다(누가 먼저 가져가는지만 바뀐다)"


def test_히어로는_실증자료보다도_먼저_받는다():
    """맨 위 큰 자리가 비면 제일 티가 난다."""
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("hero_intro", "hero_fullbleed"),
        ("clinical_intro", "section_statement"),
        ("clinical_result", "clinical_bar_compare"),
    )
    results, _ = generate_module_images(plan, _REQ, gen, max_images=1)
    made = [r.module_kind for r in results if r.status == "generated"]
    assert made == ["hero_intro"]


def test_설문도_사업자_자료로_보호된다():
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("hero_intro", "hero_fullbleed"),
        ("cause_explain", "section_statement"),
        ("survey_result", "section_statement"),
    )
    results, _ = generate_module_images(plan, _REQ, gen, max_images=2)
    made = {r.module_kind for r in results if r.status == "generated"}
    assert made == {"hero_intro", "survey_result"}


def test_결과는_계획_순서로_돌아온다():
    """생성은 우선순위 순서지만 읽는 사람 기준은 화면 순서다."""
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("hero_intro", "hero_fullbleed"),
        ("cause_explain", "section_statement"),
        ("clinical_intro", "section_statement"),
    )
    results, _ = generate_module_images(plan, _REQ, gen, max_images=6)
    assert [r.module_kind for r in results] == ["hero_intro", "cause_explain", "clinical_intro"]


def test_배경없는_유형은_상한을_안_먹는다():
    """table_info는 원래 셀 자격이 없다. 회귀 방지."""
    gen = FakeGenerator()
    plan = _plan_with_types(
        ("full_ingredient_list", "table_info"),
        ("product_spec", "table_info"),
        ("hero_intro", "hero_fullbleed"),
        ("clinical_intro", "section_statement"),
    )
    results, _ = generate_module_images(plan, _REQ, gen, max_images=2)
    made = {r.module_kind for r in results if r.status == "generated"}
    assert made == {"hero_intro", "clinical_intro"}
