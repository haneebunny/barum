"""근거 등급(evidence_grade)과 인용 대조 게이트 동작.

    ./venv/bin/python -m pytest tests/test_evidence_grade.py -q
"""

import pytest

from barum.judge.cosmetic import (
    GRADE_RULE,
    GRADE_UNVERIFIED,
    GRADE_VERIFIED,
    PromptJudge,
    RagJudge,
)
from barum.reference.context import Chunk

_CHUNKS = (
    Chunk(id="L01", label="prohibited_expressions.md", text="아토피, 모낭충, 살균·소독, 해독"),
)


class OneShotVLM:
    """캔드 판정 결과 하나를 돌려주는 가짜 LLM."""

    def __init__(self, item):
        self._item = item

    def generate_json(self, prompt, images):
        return {"results": [dict(self._item, n=0)]}


def _sentences(texts):
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


def _judge_one(item, chunks=_CHUNKS):
    res = PromptJudge(OneShotVLM(item), chunks=chunks).judge(
        _sentences(["아토피 걱정 없는 크림"]), "KR"
    )
    assert res.findings, "finding이 안 나왔다"
    return res.findings[0]


def test_인용이_맞으면_확인_등급이_붙는다():
    f = _judge_one(
        {"label": "1호_의약품오인", "reason": "질병명 표방", "source_id": "L01", "quote": "아토피, 모낭충"}
    )
    assert f.evidence_grade == GRADE_VERIFIED
    assert f.explanation == "질병명 표방"


def test_안_실린_조각을_인용하면_설명을_떼고_지적은_남긴다():
    """컴플라이언스 도구에서 진짜 위반이 설명 검증 실패로 사라지면 그게 더 위험하다."""
    f = _judge_one(
        {"label": "1호_의약품오인", "reason": "지어낸 근거", "source_id": "L99", "quote": "없는 조항"}
    )
    assert f.evidence_grade == GRADE_UNVERIFIED
    assert "지어낸 근거" not in f.explanation
    assert f.violation_type.value == "1호_의약품오인"  # 지적 자체는 살아 있다
    assert f.flag is not None


def test_인용을_아예_안_하면_미확인이다():
    f = _judge_one({"label": "1호_의약품오인", "reason": "감으로 판정"})
    assert f.evidence_grade == GRADE_UNVERIFIED
    assert "감으로 판정" not in f.explanation


def test_근거_조각이_없으면_대조를_안_한다():
    """제로샷 경로엔 근거 조각 자체가 없다. 없는 걸 못 맞췄다고 벌주면 안 된다."""
    f = _judge_one({"label": "1호_의약품오인", "reason": "질병명 표방"}, chunks=())
    assert f.evidence_grade is None
    assert f.explanation == "질병명 표방"


def test_게이트를_끄면_대조를_안_한다(monkeypatch):
    """A/B 측정용 스위치. 끄면 모델 설명이 그대로 나가고 등급도 안 붙는다."""
    monkeypatch.setenv("BARUM_VERIFY_GATE", "0")
    f = _judge_one({"label": "1호_의약품오인", "reason": "지어낸 근거", "source_id": "L99"})
    assert f.evidence_grade is None
    assert f.explanation == "지어낸 근거"


def test_성분표_대조_근거는_인용_실패에도_남는다():
    """코드가 계산한 근거는 모델 설명이 아니다. 같이 지우면 가장 단단한 근거를 잃는다."""
    vlm = OneShotVLM(
        {"label": "2호_기능성오인", "reason": "미백 주장", "source_id": "L99", "quote": "없음"}
    )
    res = PromptJudge(vlm, chunks=_CHUNKS).judge(
        _sentences(["멜라닌 억제해 미백에 도움"]), "KR", ingredients=["정제수", "알부틴"]
    )
    f = res.findings[0]
    assert f.evidence_grade == GRADE_UNVERIFIED
    assert "미백 주장" not in f.explanation
    assert "전성분 대조" in f.explanation  # 코드가 확인한 근거는 남아 있다


def test_규칙_경로는_항상_확정_등급이다():
    """규칙 매칭은 팩 등재 표현과의 일치다. 전건 근거 보유는 CI가 지킨다."""

    class NeverCalledVLM:
        def generate_json(self, prompt, images):
            raise AssertionError("규칙이 확정한 문장은 VLM에 안 가야 한다")

    res = RagJudge(NeverCalledVLM()).judge(_sentences(["아토피 치료에 좋은 크림"]), "KR")
    assert res.findings
    rule_findings = [f for f in res.findings if f.source == "rule"]
    assert rule_findings
    assert all(f.evidence_grade == GRADE_RULE for f in rule_findings)


@pytest.mark.parametrize("grade", [GRADE_RULE, GRADE_VERIFIED, GRADE_UNVERIFIED])
def test_등급값은_영어_슬러그다(grade):
    """프론트 라벨 테이블이 이 값에 매달린다. 한글로 바꾸면 표시 문구를 못 고친다."""
    assert grade.isascii() and grade.islower() and " " not in grade
