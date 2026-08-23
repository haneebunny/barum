"""콘텐츠 생성 I/O 계약 모델 유닛테스트 (FR-11/13).

    ./venv/bin/python -m pytest tests/test_generate_models.py -q
"""

import pytest
from pydantic import ValidationError

from barum.models import (
    GenerateRequest,
    GenerateResponse,
    ImageGenResult,
    ImagePlan,
    IngredientAmount,
    RecheckSummary,
    Replacement,
    RiskConfirmation,
    Section,
    ViolationType,
)


def test_generate_request_requires_content_only():
    """개선(improve) 입력은 원본 content가 필수, 나머지는 선택."""
    req = GenerateRequest(content="아토피 완화에 좋은 크림")
    assert req.content == "아토피 완화에 좋은 크림"
    assert req.result_id is None
    assert req.certifications == []


def test_generate_request_improve_mode_rejects_missing_content():
    """mode='improve'(기본값)인데 content가 없으면 검증 에러."""
    with pytest.raises(ValidationError):
        GenerateRequest(product_name="테스트크림")


def test_generate_request_create_mode_allows_missing_content():
    """create 모드는 원본 없이 제품정보만으로 성립한다."""
    req = GenerateRequest(
        mode="create",
        product_name="테스트크림",
        certifications=["미백 기능성 인증"],
        ingredient_amounts=[IngredientAmount(name="나이아신아마이드", amount="3%")],
    )
    assert req.content is None
    assert req.ingredient_amounts[0].amount == "3%"


def test_generate_response_serializes_full_shape():
    resp = GenerateResponse(
        sections=[Section(kind="제품개요", text="순한 데일리 보습 크림", source="llm")],
        replacements=[
            Replacement(
                original="아토피 완화",
                replaced="건조함으로 인한 가려움 완화",
                violation_type=ViolationType.type_1_drug_misperception,
                basis="합법 표기 틀",
            )
        ],
        image_plan=ImagePlan(),
        pii_removed=["전화번호"],
        risk_confirmations=[
            RiskConfirmation(id="rc_1", text="병원 추천 문구", reason="의료기관 오인")
        ],
        recheck=RecheckSummary(safe=True, n_findings=0),
        disclaimer="생성물은 참고용입니다.",
    )
    d = resp.model_dump(mode="json")
    assert d["sections"][0]["source"] == "llm"
    assert d["replacements"][0]["violation_type"] == "1호_의약품오인"
    assert d["risk_confirmations"][0]["id"] == "rc_1"
    assert d["recheck"]["safe"] is True
    assert d["image_plan"]["generation"]["requested"] is False


def test_image_gen_result_defaults():
    g = ImageGenResult()
    assert g.requested is False
    assert g.allowed is None
    assert g.ai_labeled is False


# ── 재검증 결과를 개수만이 아니라 지적 단위로 준다 (2026-08-23) ──────────────

def test_재검증_요약이_남은_지적을_그대로_싣는다():
    """개수만 주면 화면이 '재검증 실패' 하나로 뭉뚱그린다.

    실측(2026-08-23)에서 남은 6건 중 3건이 검토필요였다. 그건 실증자료를 요구하는
    정상 동작인데 실패로 물들고 있었다.
    """
    from barum.generate.content import _recheck
    from barum.judge.cosmetic import StubJudge
    from barum.models import GenerateRequest, Section

    sections = [Section(kind="광고문구", text="아토피 치료에 좋은 크림", source="template")]
    recheck, risks = _recheck(sections, GenerateRequest(content="x"), StubJudge())

    assert recheck.n_findings == len(recheck.findings)
    if recheck.findings:
        # flag가 있어야 프론트가 검토필요를 걸러낼 수 있다.
        assert all(f.flag is not None for f in recheck.findings)
        assert all(f.span for f in recheck.findings)


def test_재검증_지적이_없으면_목록도_비어_있다():
    from barum.generate.content import _recheck
    from barum.judge.cosmetic import StubJudge
    from barum.models import GenerateRequest, Section

    sections = [Section(kind="광고문구", text="촉촉한 사용감의 데일리 로션", source="template")]
    recheck, _ = _recheck(sections, GenerateRequest(content="x"), StubJudge())
    assert recheck.findings == [] or recheck.n_findings == len(recheck.findings)
