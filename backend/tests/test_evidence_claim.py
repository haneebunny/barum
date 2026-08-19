"""증빙 주장 탐지 유닛테스트 (에이전틱 판정 1단계).

순수 로직만. 이미지 대조(VLM 호출)는 여기서 안 한다.

    venv/bin/python -m pytest tests/test_evidence_claim.py -q
"""

from barum.reference.evidence_claim import (
    claims_documentary_evidence,
    select_for_verification,
)


def test_에스코_원문이_대조_대상으로_걸린다():
    """실제 위조가 발견된 문장(48/49번 #9). 이게 안 걸리면 이 기능의 의미가 없다."""
    assert claims_documentary_evidence(
        "에스코 제주 시카 카밍 세럼은 미백 주름개선 2중 기능성을 보고한 제품입니다"
    )


def test_시험_인증_계열이_걸린다():
    for s in [
        "인체적용시험 완료",
        "비건인증 완료",
        "식약처 심사 완료",
        "특허 등록 제10-XXXXXXX호",
        "임상시험 결과지 첨부",
    ]:
        assert claims_documentary_evidence(s), s


def test_테스트완료_단독은_대조_대상이_아니다():
    """'피부과 테스트 완료'는 증빙 문서를 내세우는 게 아니라 주장만 하는 형태다.

    실제로 La Nieve 사례가 이랬다 — 원형 배지 텍스트만 있고 첨부 증빙 문서 자체가
    없어서 대조할 대상이 없었다(인용검증 보고서 §3). 이런 문장은 별도 규칙이
    이미 needs_review로 잡으므로(judge_rules.json '테스트완료') 여기선 제외한다.
    """
    assert not claims_documentary_evidence("피부과 테스트 완료")


def test_증빙_언급_없는_일반_문구는_안_걸린다():
    for s in ["촉촉하고 산뜻한 데일리 로션", "정제수, 글리세린", "1STEP"]:
        assert not claims_documentary_evidence(s), s


def test_이미지에서_온_문장만_대조_대상이다():
    """대조할 원본 이미지가 없으면 확인할 방법이 없다. 텍스트 입력은 제외."""
    sents = [
        {"order": 0, "tile": "t1.png", "text": "인체적용시험 완료"},
        {"order": 1, "tile": None, "text": "인체적용시험 완료"},  # 텍스트 입력
        {"order": 2, "tile": "t1.png", "text": "촉촉한 로션"},  # 증빙 언급 없음
    ]
    picked = select_for_verification(sents)
    assert [s["order"] for s in picked] == [0]


def test_정규화로_띄어쓰기_변형도_잡는다():
    assert claims_documentary_evidence("인체 적용 시험 완료")
