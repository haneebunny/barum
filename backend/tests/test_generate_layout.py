"""모듈 구조 플래너·위반소지 가드 유닛테스트. LLM은 가짜 객체로 대체(오프라인)."""


from barum.generate.layout import (
    _format_examples,
    clinical_sections_text,
    filter_risky_modules,
    plan_layout,
)
from barum.models import ClinicalEvidence, GenerateRequest, LayoutModule, LayoutPlan


class FakeVlm:
    """generate_json이 정해진 값을 내는 가짜 LLM."""

    def __init__(self, result=None, raises=False):
        self._result = result
        self._raises = raises

    def generate_json(self, prompt, images):
        if self._raises:
            raise RuntimeError("boom")
        return self._result


REFS = [
    {
        "product_type": "세럼",
        "modules": [
            {"kind": "hero_intro", "purpose": "도입부", "has_claim_risk": False},
            {"kind": "clinical_result", "purpose": "개선율", "has_claim_risk": True},
        ],
    }
]


def _req(**kw):
    return GenerateRequest(mode="create", product_name="테스트 세럼", **kw)


# ── 플래너 ──


def test_LLM_계획을_LayoutPlan으로_변환한다():
    vlm = FakeVlm({"modules": [{"kind": "hero_intro", "purpose": "도입", "has_claim_risk": False}]})
    plan = plan_layout(_req(), REFS, "세럼", vlm)
    assert plan.source == "planner"
    assert plan.product_type == "세럼"
    assert [m.kind for m in plan.modules] == ["hero_intro"]


def test_LLM_실패하면_폴백_플랜으로_간다():
    plan = plan_layout(_req(), REFS, "세럼", FakeVlm(raises=True))
    assert plan.source == "fallback"
    assert plan.modules
    # 폴백은 근거 없이도 안전해야 하므로 위반소지 모듈이 없어야 한다.
    assert all(not m.has_claim_risk for m in plan.modules)


def test_LLM이_빈_응답을_줘도_폴백한다():
    plan = plan_layout(_req(), REFS, "세럼", FakeVlm({"modules": []}))
    assert plan.source == "fallback"


def test_kind가_비면_그_모듈은_버린다():
    vlm = FakeVlm({"modules": [{"kind": "  ", "purpose": "x"}, {"kind": "texture", "purpose": "제형"}]})
    plan = plan_layout(_req(), REFS, "세럼", vlm)
    assert [m.kind for m in plan.modules] == ["texture"]


def test_레퍼런스가_없으면_LLM을_안_부른다():
    # 부르면 raises=True라 예외가 나겠지만, 안 부르므로 폴백으로 조용히 간다.
    plan = plan_layout(_req(), [], None, FakeVlm(raises=True))
    assert plan.source == "fallback"


# ── layout_type (2026-08-19, 냐냐·PM 확인, PR #181 어휘집 연동) ──


def test_폴백_플랜의_모든_모듈이_layout_type을_받는다():
    """LLM을 안 타는 경로에서도 프론트가 항상 layout_type을 받아야 한다."""
    plan = plan_layout(_req(), [], None, FakeVlm(raises=True))
    assert all(m.layout_type for m in plan.modules)


def test_LLM이_카탈로그_안의_layout_type을_주면_그대로_쓴다():
    vlm = FakeVlm(
        {"modules": [{"kind": "hero_intro", "purpose": "도입", "layout_type": "hero_fullbleed"}]}
    )
    plan = plan_layout(_req(), REFS, "세럼", vlm)
    assert plan.modules[0].layout_type == "hero_fullbleed"


def test_LLM이_카탈로그_밖_layout_type을_주면_기본값으로_바뀐다():
    vlm = FakeVlm(
        {"modules": [{"kind": "hero_intro", "purpose": "도입", "layout_type": "존재하지않는유형"}]}
    )
    plan = plan_layout(_req(), REFS, "세럼", vlm)
    assert plan.modules[0].layout_type == "section_statement"


def test_LLM이_layout_type을_빠뜨리면_기본값으로_채운다():
    vlm = FakeVlm({"modules": [{"kind": "hero_intro", "purpose": "도입"}]})
    plan = plan_layout(_req(), REFS, "세럼", vlm)
    assert plan.modules[0].layout_type == "section_statement"


def test_퓨샷_예시에_layout_type이_들어간다():
    refs = [
        {
            "product_type": "세럼",
            "modules": [
                {"kind": "hero_intro", "purpose": "도입", "has_claim_risk": False, "layout_type": "hero_fullbleed"}
            ],
        }
    ]
    assert "layout_type=hero_fullbleed" in _format_examples(refs)


# ── 위반소지 가드 ──


def _plan(*modules):
    return LayoutPlan(modules=list(modules), product_type="세럼", source="planner")


SAFE = LayoutModule(kind="texture", purpose="제형", has_claim_risk=False)
CLINICAL = LayoutModule(kind="clinical_result", purpose="개선율", has_claim_risk=True)
CLAIM = LayoutModule(kind="value_prop", purpose="핵심가치", has_claim_risk=True)


def test_안전한_모듈은_근거없이도_통과한다():
    kept, skipped = filter_risky_modules(_plan(SAFE), has_approved_claim=False, has_clinical_evidence=False)
    assert [m.kind for m in kept.modules] == ["texture"]
    assert skipped == []


def test_임상모듈은_실증자료_없으면_빠진다():
    kept, skipped = filter_risky_modules(_plan(CLINICAL), has_approved_claim=True, has_clinical_evidence=False)
    assert kept.modules == []
    assert len(skipped) == 1
    assert "실증자료" in skipped[0].reason


def test_임상모듈은_인증서만으론_못_통과한다():
    # "미백 기능성 인증"은 "다크스팟 87% 개선" 수치의 근거가 아니다.
    kept, _ = filter_risky_modules(_plan(CLINICAL), has_approved_claim=True, has_clinical_evidence=False)
    assert kept.modules == []


def test_임상모듈은_실증자료_있으면_통과한다():
    kept, skipped = filter_risky_modules(_plan(CLINICAL), has_approved_claim=False, has_clinical_evidence=True)
    assert [m.kind for m in kept.modules] == ["clinical_result"]
    assert skipped == []


def test_일반_위반소지_모듈은_인정문구로_통과한다():
    kept, skipped = filter_risky_modules(_plan(CLAIM), has_approved_claim=True, has_clinical_evidence=False)
    assert [m.kind for m in kept.modules] == ["value_prop"]
    assert skipped == []


def test_일반_위반소지_모듈은_실증자료만으론_못_통과한다():
    """실증자료는 임상 수치의 근거일 뿐 일반 효능 주장의 근거가 아니다.

    통과시키면 계획엔 남았는데 채울 내용이 없는 빈 모듈이 생긴다(실제 있었던 결함).
    """
    kept, skipped = filter_risky_modules(_plan(CLAIM), has_approved_claim=False, has_clinical_evidence=True)
    assert kept.modules == []
    assert "인정문구" in skipped[0].reason


def test_근거가_아무것도_없으면_위반소지_모듈은_전부_빠진다():
    kept, skipped = filter_risky_modules(
        _plan(SAFE, CLAIM, CLINICAL), has_approved_claim=False, has_clinical_evidence=False
    )
    assert [m.kind for m in kept.modules] == ["texture"]
    assert len(skipped) == 2


def test_가드는_계획의_메타정보를_보존한다():
    kept, _ = filter_risky_modules(_plan(SAFE), has_approved_claim=False, has_clinical_evidence=False)
    assert kept.product_type == "세럼"
    assert kept.source == "planner"


# ── 실증자료 문장화 ──


def test_실증자료를_입력값_그대로_문장화한다():
    text = clinical_sections_text(
        [ClinicalEvidence(claim="다크스팟 개선", value="87%", institution="OO시험기관", period="8주")]
    )
    assert "다크스팟 개선" in text
    assert "87%" in text
    assert "8주" in text
    assert "OO시험기관" in text


def test_선택항목이_없어도_문장이_나온다():
    text = clinical_sections_text([ClinicalEvidence(claim="보습력 개선", value="2.1배")])
    assert text == "보습력 개선 2.1배"
