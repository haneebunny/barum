"""RagJudge(규칙 우선 + VLM fallback) 유닛테스트.

규칙집 대조는 실제 데이터(judge_rules.json)를 쓰고, VLM은 가짜를 주입한다.
규칙 확정분이 VLM에 안 넘어가는지(과금 절감)를 특히 못박는다.

    ./venv/bin/python -m pytest tests/test_rag_judge.py -q
"""

from barum.judge.cosmetic import JudgeResult, RagJudge
from barum.models import JudgmentFlag, ViolationType


def _sentences(texts: list[str]) -> list[dict]:
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


class RecordingVLM:
    """호출 횟수·프롬프트를 기록하는 가짜 VLM. 미리 정한 results를 돌려준다."""

    def __init__(self, results: list[dict] | None = None):
        self.calls = 0
        self.prompts: list[str] = []
        self._results = results or []

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        self.calls += 1
        self.prompts.append(prompt)
        return {"results": self._results}


class BoomVLM:
    """항상 실패하는 VLM(429·빈응답 흉내)."""

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        raise ValueError("VLM이 빈 응답을 반환했다")


def test_rule_violation_becomes_finding_without_vlm():
    """규칙에 걸린 위반은 VLM 없이 finding이 된다(VLM 호출 0회)."""
    vlm = RecordingVLM()
    res = RagJudge(vlm).judge(_sentences(["아토피 완화 크림"]), "KR")
    assert isinstance(res, JudgeResult)
    assert len(res.findings) == 1
    f = res.findings[0]
    assert f.violation_type == ViolationType.type_1_drug_misperception
    assert f.flag == JudgmentFlag.violation
    assert f.span == "아토피"
    assert f.sentence == "아토피 완화 크림"
    assert f.legal_basis.startswith("화장품법 제13조")
    assert vlm.calls == 0


def test_rule_needs_review_becomes_finding_without_vlm():
    """실증대상(진정)은 검토필요 finding, VLM 안 부름."""
    vlm = RecordingVLM()
    res = RagJudge(vlm).judge(_sentences(["피부를 진정시켜 줍니다"]), "KR")
    assert len(res.findings) == 1
    f = res.findings[0]
    assert f.flag == JudgmentFlag.needs_review
    assert f.violation_type == ViolationType.type_1_drug_misperception
    assert "실증대상" in f.explanation
    assert vlm.calls == 0


def test_legal_allow_makes_no_finding_and_skips_vlm():
    """합법 확정(탄력)은 finding도 없고 VLM에도 안 넘긴다."""
    vlm = RecordingVLM()
    res = RagJudge(vlm).judge(_sentences(["피부에 탄력을 더해 줍니다"]), "KR")
    assert res.findings == []
    assert res.unjudged == []
    assert vlm.calls == 0


def test_unmatched_sentence_delegates_to_vlm():
    """규칙 미매칭 문장은 VLM에 넘겨 그 판정을 그대로 싣는다."""
    vlm = RecordingVLM([{"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"}])
    res = RagJudge(vlm).judge(_sentences(["멜라닌 억제해 미백에 도움"]), "KR")
    assert vlm.calls == 1
    assert len(res.findings) == 1
    assert (
        res.findings[0].violation_type == ViolationType.type_2_functional_misperception
    )


def test_rule_confirmed_sentence_excluded_from_vlm_prompt():
    """규칙 확정분은 VLM 프롬프트에서 빠지고 미확정분만 넘어간다(과금 절감·핵심).

    규정 근거(context)에도 '아토피'가 들어 있어 프롬프트 통짜 substring 검사는 못 쓴다.
    판정 대상 문장이 담기는 '문장:' 이후 items 블록만 떼어 확인한다.
    """
    vlm = RecordingVLM([{"n": 0, "label": "합법"}])
    res = RagJudge(vlm).judge(_sentences(["아토피 완화", "촉촉한 보습감"]), "KR")
    assert vlm.calls == 1
    items_block = vlm.prompts[0].split("문장:\n")[-1]  # 판정 투입 문장만
    assert "아토피" not in items_block  # 규칙 확정분은 판정 대상에서 빠짐
    assert "보습감" in items_block  # 미확정분만 판정 대상
    assert len(res.findings) == 1
    assert res.findings[0].span == "아토피"


def test_rag_fallback_prompt_includes_regulation_context():
    """규칙 미매칭 문장은 규정·판정기준·실사례 근거가 실린 프롬프트로 LLM에 간다."""
    vlm = RecordingVLM([{"n": 0, "label": "합법"}])
    RagJudge(vlm).judge(_sentences(["촉촉하고 산뜻한 데일리 로션"]), "KR")
    assert vlm.calls == 1
    assert "판정 근거" in vlm.prompts[0]  # grounding 블록 헤더
    assert "광고업무정지" in vlm.prompts[0]  # cases.md 실제 적발 처분


def test_rag_with_retriever_uses_regulation_plus_retrieved_cases():
    """retriever 주입 시 규정 + '검색된' 사례를 넣고, cases.md 통째는 안 넣는다."""

    class FakeRetriever:
        def context_for(self, sentences):
            return '### 유사 과거 적발사례\n- "검색된사례XYZ" → T1 / 정지'

    vlm = RecordingVLM([{"n": 0, "label": "합법"}])
    RagJudge(vlm, case_retriever=FakeRetriever()).judge(
        _sentences(["촉촉하고 산뜻한 데일리 로션"]), "KR"
    )
    p = vlm.prompts[0]
    assert "검색된사례XYZ" in p  # 검색된 사례가 프롬프트에 들어감
    assert "아토피" in p  # 규정(build_regulation_context)도 들어감
    assert "트리플 특허" not in p  # cases.md 통째의 사례는 안 들어감(검색 경로)


def test_rule_findings_survive_vlm_failure():
    """VLM이 미확정분에서 실패해도 규칙 확정 finding은 남고 실패분은 unjudged."""
    res = RagJudge(BoomVLM()).judge(_sentences(["아토피 완화", "일반적인 사용감"]), "KR")
    assert len(res.findings) == 1  # 아토피(규칙)
    assert res.findings[0].span == "아토피"
    assert len(res.unjudged) == 1  # 일반 문장(VLM 실패 → 미판정)
    assert res.unjudged[0].sentence == "일반적인 사용감"
