"""소비자 설문조사 처리 유닛테스트.

핵심 불변식 두 개:
1. 설문은 실증자료가 아니다 -> 임상 모듈을 열지 못한다.
2. 피부 변화(효능) 주장은 설문으로 못 받친다 -> 빼되 사유를 남긴다.
"""

import pytest

from barum.generate.content import _usable_surveys
from barum.generate.layout import filter_risky_modules
from barum.models import GenerateRequest, LayoutModule, LayoutPlan, SurveyEvidence
from barum.reference.survey import is_efficacy_survey, survey_sentence


def _survey(claim: str) -> SurveyEvidence:
    return SurveyEvidence(
        claim=claim,
        value="96%",
        sample_size="200명",
        institution="OO리서치",
        period="2026년 3월",
        method="온라인 자기기입식 설문",
    )


# ── 효능형 판별 ──


@pytest.mark.parametrize(
    "claim",
    [
        "주름이 개선되었다",
        "피부가 촉촉해졌다",
        "피부톤이 밝아졌다",
        "미백 효과를 느꼈다",
        "수분감이 좋아졌다",
        "피부결이 정돈되었다",
        "탄력이 개선되었다",
        "모공이 줄어들었다",
    ],
)
def test_피부_변화_주장은_전부_효능으로_본다(claim):
    """팀장 확정(2026-08-20): 기능성 3종만이 아니라 피부 변화 전부가 효능이다."""
    assert is_efficacy_survey(claim) is True


@pytest.mark.parametrize(
    "claim",
    ["향에 만족", "발림성에 만족", "용기 디자인에 만족", "재구매 의향 있음", "가격에 만족"],
)
def test_피부와_무관한_항목은_쓸_수_있다(claim):
    assert is_efficacy_survey(claim) is False


def test_띄어쓰기가_달라도_잡는다():
    assert is_efficacy_survey("피부 톤이 밝아졌다") is True


# ── 선별 ──


def test_효능형_설문은_빼고_사유를_남긴다():
    req = GenerateRequest(
        mode="create",
        survey_evidence=[_survey("주름이 개선되었다"), _survey("향에 만족")],
    )
    usable, skipped = _usable_surveys(req)
    assert [s.claim for s in usable] == ["향에 만족"]
    assert len(skipped) == 1
    assert "설문조사로는 쓸 수 없습니다" in skipped[0].reason
    assert "별표2" in skipped[0].reason


def test_설문이_없으면_아무_일도_없다():
    usable, skipped = _usable_surveys(GenerateRequest(mode="create"))
    assert usable == []
    assert skipped == []


# ── 실증자료와 섞이지 않음 (핵심 불변식) ──


def test_설문만으로는_임상_모듈이_안_열린다():
    """설문은 [별표2]의 실증 수단이 아니다. 열리면 barum이 위반을 만들어주는 셈이다."""
    plan = LayoutPlan(
        modules=[LayoutModule(kind="clinical_result", purpose="수치", has_claim_risk=True)],
        product_type="세럼",
        source="planner",
    )
    # 설문이 아무리 많아도 has_clinical_evidence는 False로 들어가야 한다.
    filtered, skipped = filter_risky_modules(
        plan, has_approved_claim=True, has_clinical_evidence=False
    )
    assert filtered.modules == []
    assert len(skipped) == 1
    assert "실증자료" in skipped[0].reason


# ── 문장 조립 ──


def test_문장에_방법_표본_시기_기관이_전부_들어간다():
    """판정기가 5호 사유로 "설문방법·표본·시기·출처 미제시"를 든다. 다 적어야 해소된다."""
    text = survey_sentence(_survey("향에 만족"))
    for part in ("향에 만족", "96%", "200명", "OO리서치", "2026년 3월", "온라인 자기기입식 설문"):
        assert part in text


def test_메타데이터는_필수라_빠지면_거부된다():
    """선택 필드로 두면 수치만 있고 출처 없는 문구를 우리가 만들어주게 된다."""
    with pytest.raises(Exception):
        SurveyEvidence(claim="향에 만족", value="96%")
