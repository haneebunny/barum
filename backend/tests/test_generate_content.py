"""콘텐츠 생성 오케스트레이션(generate.content) 유닛테스트.

LLM은 가짜 주입, 판정은 StubJudge(오프라인 결정론). 실 LLM·재검증은 수동 스모크.

    ./venv/bin/python -m pytest tests/test_generate_content.py -q
"""

from barum.generate import content as content_module
from barum.generate.content import (
    build_approved_claim_sections,
    build_image_plan,
    generate_content,
    generate_sections,
)
from barum.judge.cosmetic import StubJudge
from barum.models import ClinicalEvidence, GenerateRequest, ImageGenRequest, IngredientAmount


class FakeVLM:
    """캔드 JSON을 돌려주는 가짜 LLM(섹션 생성용)."""

    def __init__(self, result):
        self._result = result

    def generate_json(self, prompt, images):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_generate_sections_from_llm():
    """LLM이 준 서술을 섹션으로 만든다(source=llm)."""
    vlm = FakeVLM({"제품개요": "담백한 데일리 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"})
    secs = generate_sections(GenerateRequest(content="x", product_name="테스트크림"), vlm)
    kinds = {s.kind for s in secs}
    assert {"제품개요", "사용법", "주의사항"} <= kinds
    assert all(s.source == "llm" for s in secs)


def test_generate_sections_falls_back_to_template_on_failure():
    """LLM 실패 시 템플릿 폴백(source=template) — 응답이 죽지 않게."""
    secs = generate_sections(GenerateRequest(content="x"), FakeVLM(ValueError("boom")))
    assert secs  # 비어있지 않음
    assert all(s.source == "template" for s in secs)


def test_build_image_plan_places_result_image_and_filters_gen():
    """result_id 이미지는 배치, 사칭 생성요청은 거부."""
    req = GenerateRequest(
        content="x", result_id="rid1",
        image_generation=ImageGenRequest(requested=True, prompt="의사가 추천하는 사진"),
    )
    plan = build_image_plan(req)
    assert plan.placed and plan.placed[0].image_url == "/reports/rid1/image"
    assert plan.generation.requested is True
    assert plan.generation.allowed is False
    assert plan.generation.reason


def test_generate_content_end_to_end_offline():
    """검사→치환→서술생성→PII→재검증 전체 조립(StubJudge+가짜LLM)."""
    req = GenerateRequest(
        content="재생 크림입니다. 문의 010-1234-5678", product_name="테스트크림"
    )
    vlm = FakeVLM({"제품개요": "담백한 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"})
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)

    assert any(s.kind == "광고문구" for s in resp.sections)  # 개선된 원문
    assert any(s.source == "llm" for s in resp.sections)  # 생성 서술
    # "재생" → 조건표로 치환됨
    assert resp.replacements and resp.replacements[0].original == "재생"
    assert all("재생" not in s.text for s in resp.sections)
    # PII(전화번호) 제거·고지
    assert "전화번호" in resp.pii_removed
    assert all("010-1234-5678" not in s.text for s in resp.sections)
    # 재검증 요약 존재
    assert resp.recheck is not None
    assert resp.disclaimer


def _stub_approved_claim(category, certifications):
    if category == "미백" and "미백 기능성 인증" in certifications:
        return "피부 미백에 도움을 줍니다."
    return None


def test_build_approved_claim_sections_generates_when_all_conditions_met(monkeypatch):
    monkeypatch.setattr(content_module, "match_approved_claim", _stub_approved_claim)
    req = GenerateRequest(
        mode="create",
        certifications=["미백 기능성 인증"],
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
    )
    sections, skipped = build_approved_claim_sections(req)
    assert sections and sections[0].source == "approved_claim"
    assert sections[0].text == "피부 미백에 도움을 줍니다."
    # 미백은 성공, 나머지 카테고리는 인증서 자체가 없어 스킵
    assert {s.category for s in skipped} == {"주름개선", "자외선차단"}


def test_build_approved_claim_sections_skips_when_ingredient_threshold_fails(monkeypatch):
    """인증서는 매칭돼도 함량 기준(알부틴 범위 상한 초과)을 못 채우면 문구를 안 만든다."""
    monkeypatch.setattr(content_module, "match_approved_claim", _stub_approved_claim)
    req = GenerateRequest(
        mode="create",
        certifications=["미백 기능성 인증"],
        ingredient_amounts=[IngredientAmount(name="알부틴", amount="10%")],
    )
    sections, skipped = build_approved_claim_sections(req)
    assert not sections
    reasons = {s.category: s.reason for s in skipped}
    assert "미백" in reasons and "함량" in reasons["미백"]


def test_generate_create_content_no_original_check_and_empty_replacements(monkeypatch):
    """create 모드는 원본 검사가 없어 replacements가 항상 빈 배열이다."""
    monkeypatch.setattr(content_module, "match_approved_claim", _stub_approved_claim)
    req = GenerateRequest(
        mode="create",
        product_name="테스트크림",
        certifications=["미백 기능성 인증"],
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
    )
    vlm = FakeVLM({"제품개요": "담백한 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"})
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)

    assert resp.replacements == []
    assert any(s.source == "approved_claim" for s in resp.sections)
    assert any(s.category == "주름개선" for s in resp.skipped_claims)
    assert resp.recheck is not None


# ── create 모드 모듈 구조 플래너 (FR-11 확장) ──


class SequenceVLM:
    """호출 순서대로 다른 JSON을 돌려주는 가짜 LLM.

    create 모드는 ① 모듈 구성 계획 ② 모듈별 서술 순으로 두 번 부른다.
    """

    def __init__(self, *results):
        self._results = list(results)
        self.calls = 0

    def generate_json(self, prompt, images):
        self.calls += 1
        return self._results.pop(0) if self._results else {}


_PLAN = {
    "modules": [
        {"kind": "hero_intro", "purpose": "도입부", "has_claim_risk": False},
        {"kind": "texture", "purpose": "제형", "has_claim_risk": False},
        {"kind": "clinical_result", "purpose": "개선율", "has_claim_risk": True},
    ]
}
_MODULE_TEXT = {
    "sections": [
        {"kind": "hero_intro", "text": "일상에 쓰기 좋은 제품입니다."},
        {"kind": "texture", "text": "부드럽게 발립니다."},
    ]
}


def test_create_모드가_레이아웃_계획을_응답에_싣는다():
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))

    assert resp.layout_plan is not None
    assert resp.layout_plan.product_type == "세럼"
    assert [m.kind for m in resp.layout_plan.modules] == ["hero_intro", "texture"]


def test_실증자료_없으면_임상모듈이_빠지고_사유가_남는다():
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))

    assert all(not m.kind.startswith("clinical") for m in resp.layout_plan.modules)
    assert any("실증자료" in s.reason for s in resp.skipped_claims)
    assert all(s.kind != "실증자료" for s in resp.sections)


def test_실증자료를_입력값_그대로_싣고_확인항목을_남긴다():
    req = GenerateRequest(
        mode="create",
        product_name="테스트 세럼",
        clinical_evidence=[
            ClinicalEvidence(claim="다크스팟 개선", value="87%", institution="OO시험기관", period="8주")
        ],
    )
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))

    # 임상 모듈이 살아남고, 수치는 LLM이 아니라 입력값 그대로다.
    assert any(m.kind == "clinical_result" for m in resp.layout_plan.modules)
    evidence_section = next(s for s in resp.sections if s.kind == "실증자료")
    assert evidence_section.source == "clinical_evidence"
    assert "87%" in evidence_section.text
    # 미검증이라는 사실이 확인항목·안내문구 양쪽에 드러나야 한다.
    assert any(r.id == "rc_clinical_evidence" for r in resp.risk_confirmations)
    assert "검증하지 않" in resp.disclaimer


def test_실증자료가_없으면_안내문구에_임상_문장이_안_붙는다():
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))
    assert "실증자료" not in resp.disclaimer
    assert all(r.id != "rc_clinical_evidence" for r in resp.risk_confirmations)


def test_종류를_못정해도_생성이_막히지_않는다():
    # 상품명에 종류 단어가 없어도 스킨케어 레퍼런스로 폴백해 계획이 나와야 한다.
    req = GenerateRequest(mode="create", product_name="아누아")
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))
    assert resp.layout_plan.product_type is None
    assert resp.layout_plan.modules
    assert resp.sections


def test_improve_모드는_레이아웃_계획을_안_만든다():
    req = GenerateRequest(mode="improve", content="촉촉한 크림", product_name="테스트크림")
    vlm = FakeVLM({"제품개요": "담백", "사용법": "펴 바르기", "주의사항": "이상 시 중단"})
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)
    assert resp.layout_plan is None


def test_계획에_남은_모듈은_전부_채울_내용이_있다():
    """계획엔 남았는데 내용이 빈 모듈이 없어야 한다(스모크에서 발견된 결함의 회귀 방지).

    모듈 종류별로 내용을 대는 곳이 다르다.
    안전 모듈은 LLM 서술, 임상 모듈은 실증자료 섹션, 그 외 위반소지 모듈은 인정문구 섹션.
    """
    req = GenerateRequest(
        mode="create",
        product_name="테스트 세럼",
        clinical_evidence=[ClinicalEvidence(claim="다크스팟 개선", value="87%")],
    )
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))

    section_kinds = {s.kind for s in resp.sections}
    has_evidence = any(s.source == "clinical_evidence" for s in resp.sections)
    has_claim = any(s.source == "approved_claim" for s in resp.sections)
    for module in resp.layout_plan.modules:
        if module.kind.startswith("clinical"):
            assert has_evidence, f"{module.kind}를 채울 실증자료 섹션이 없다"
        elif module.has_claim_risk:
            assert has_claim, f"{module.kind}를 채울 인정문구 섹션이 없다"
        else:
            assert module.kind in section_kinds, f"{module.kind}를 채울 서술이 없다"


# ── 모듈별 이미지 생성 연결 (FR-13 확장) ──


class FakeImageGenerator:
    def __init__(self, *results):
        self._results = list(results)

    def generate_image(self, prompt, images):
        r = self._results.pop(0) if self._results else b"PNG"
        if isinstance(r, Exception):
            raise r
        return r


def test_생성기를_안_주면_이미지를_안_만든다():
    """모델 확정 전까지 기본 비활성이라, 안 주면 과금 호출이 아예 없어야 한다."""
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    resp = generate_content(req, judge=StubJudge(), vlm=SequenceVLM(_PLAN, _MODULE_TEXT))
    assert resp.image_plan.module_images == []


def test_생성기를_주면_모듈마다_이미지를_만들고_URL을_채운다():
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    saved = {}

    def sink(kind, data):
        saved[kind] = data
        return f"/generated/{kind}.png"

    resp = generate_content(
        req,
        judge=StubJudge(),
        vlm=SequenceVLM(_PLAN, _MODULE_TEXT),
        image_generator=FakeImageGenerator(b"A", b"B"),
        image_sink=sink,
    )
    images = resp.image_plan.module_images
    assert [i.status for i in images] == ["generated", "generated"]
    assert all(i.image_url for i in images)
    assert saved  # 바이트가 싱크로 실제 전달됐다


def test_싱크가_없으면_보관못했다는_사실을_남긴다():
    """과금해서 만든 이미지를 조용히 버리면 '생성됨'만 보고 못 쓰는 상태가 된다."""
    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    resp = generate_content(
        req,
        judge=StubJudge(),
        vlm=SequenceVLM(_PLAN, _MODULE_TEXT),
        image_generator=FakeImageGenerator(b"A", b"B"),
        image_sink=None,
    )
    images = resp.image_plan.module_images
    assert all(i.image_url is None for i in images)
    assert all("보관하지 못했" in (i.reason or "") for i in images)


def test_싱크가_터져도_응답은_살아있다():
    def broken_sink(kind, data):
        raise RuntimeError("storage down")

    req = GenerateRequest(mode="create", product_name="테스트 세럼")
    resp = generate_content(
        req,
        judge=StubJudge(),
        vlm=SequenceVLM(_PLAN, _MODULE_TEXT),
        image_generator=FakeImageGenerator(b"A", b"B"),
        image_sink=broken_sink,
    )
    images = resp.image_plan.module_images
    assert all(i.image_url is None for i in images)
    assert all("저장에 실패" in (i.reason or "") for i in images)
    assert resp.sections  # 콘텐츠 자체는 정상적으로 나온다


def test_improve_모드는_이미지_생성을_안_한다():
    req = GenerateRequest(mode="improve", content="촉촉한 크림", product_name="테스트크림")
    resp = generate_content(
        req,
        judge=StubJudge(),
        vlm=FakeVLM({"제품개요": "담백", "사용법": "펴 바르기", "주의사항": "이상 시 중단"}),
        image_generator=FakeImageGenerator(b"A"),
    )
    assert resp.image_plan.module_images == []
