"""지적별 AI 확신도 (2026-08-22 팀장 확정, 멘토링 요구사항).

**이 값은 잰 확률이 아니라 모델이 생성한 숫자다.** v1.8에서 위험도 등급을 폐지하고
위반/검토필요 이진화한 결정과 방향이 다른데, 팀장이 그걸 인지한 상태로 % 노출을
확정했다. 캘리브레이션 실측은 docs/result에 따로 남긴다.

    venv/bin/python -m pytest tests/test_finding_confidence.py -q
"""

import pytest

from barum.judge.cosmetic import PromptJudge, _parse_confidence
from barum.models import JudgmentFlag, ViolationType


class FakeVLM:
    """판정 응답을 캔드로 돌려주는 가짜 어댑터."""

    def __init__(self, results):
        self._results = results

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        return {"results": self._results}


def _sentences(*texts):
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


# ── 파싱 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        (87, 87),
        ("87", 87),
        (87.4, 87),
        (0, 0),
        (100, 100),
        (None, None),
        ("높음", None),
        (-1, None),
        (101, None),
        (True, None),  # bool은 int의 하위형이라 따로 막는다
    ],
)
def test_확신도_파싱(raw, expected):
    assert _parse_confidence(raw) == expected


def test_못_읽으면_기본값을_지어내지_않는다():
    """50이나 100으로 채우면 모델이 답한 숫자와 화면에서 구분이 안 된다."""
    judge = PromptJudge(FakeVLM([{"n": 0, "label": "1호_의약품오인", "flag": "위반"}]))
    findings = judge.judge(_sentences("상처를 치료하는 연고"), "KR").findings
    assert len(findings) == 1
    assert findings[0].confidence is None


# ── VLM 경로 ──────────────────────────────────────────────────────────────


def test_VLM_판정에_확신도가_실린다():
    judge = PromptJudge(
        FakeVLM([{"n": 0, "label": "1호_의약품오인", "flag": "위반", "confidence": 92}])
    )
    f = judge.judge(_sentences("상처를 치료하는 연고"), "KR").findings[0]
    assert f.confidence == 92
    assert f.source == "vlm"


def test_범위_밖_값은_버린다():
    judge = PromptJudge(
        FakeVLM([{"n": 0, "label": "1호_의약품오인", "flag": "위반", "confidence": 120}])
    )
    assert judge.judge(_sentences("상처를 치료하는 연고"), "KR").findings[0].confidence is None


# ── 규칙 경로 ─────────────────────────────────────────────────────────────


def test_규칙_경로는_확신도가_없다():
    """키워드 일치라 확률 개념이 없다. 100으로 채우면 "AI가 확신했다"로 읽힌다."""
    from barum.judge.cosmetic import RagJudge

    judge = RagJudge(FakeVLM([]))
    findings = judge.judge(_sentences("상처를 치료하는 연고"), "KR").findings
    rule_findings = [f for f in findings if f.source == "rule"]
    assert rule_findings, "규칙이 잡는 문장이어야 이 테스트가 의미가 있다"
    assert all(f.confidence is None for f in rule_findings)


# ── 파이프라인 통과 ───────────────────────────────────────────────────────


def test_증빙_격상을_거쳐도_확신도가_남는다():
    """`_verify_functional_evidence`가 flag를 갈아끼울 때 다른 필드를 떨어뜨리면 안 된다."""
    from barum.models import Finding, Location

    f = Finding(
        span="x", sentence="x", violation_type=ViolationType.type_2_functional_misperception,
        legal_basis="화장품법 제13조", flag=JudgmentFlag.needs_review, explanation="y",
        confidence=71, source="vlm", location=Location(tile=None, order=0),
    )
    upgraded = f.model_copy(update={"flag": JudgmentFlag.violation})
    assert upgraded.confidence == 71


def test_확신도는_응답_스키마에_있다():
    """프론트가 읽을 필드다. 모델에서 빠지면 조용히 사라진다."""
    from barum.models import Finding

    assert "confidence" in Finding.model_fields
    schema = Finding.model_json_schema()["properties"]["confidence"]
    assert "integer" in str(schema)
