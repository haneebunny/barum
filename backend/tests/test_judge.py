"""PromptJudge 유닛테스트.

VLM은 가짜 객체(캔드 results 반환/예외)를 주입한다. 진짜 판정 호출은 수동 스모크.

    venv/bin/python -m pytest tests/test_judge.py -q
"""

from barum.judge.cosmetic import JUDGE_PROMPT, JudgeResult, PromptJudge, StubJudge, _loc
from barum.models import JudgmentFlag


class CapturingVLM:
    """VLM에 넘어간 프롬프트를 붙잡아 두는 가짜(문법 검증용)."""

    def __init__(self):
        self.prompt = None

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        self.prompt = prompt
        return {"results": [{"n": 0, "label": "합법"}]}


def test_prompt_judge_prepends_context_to_prompt():
    """context를 주면 판정 프롬프트 앞에 붙어 VLM에 전달된다."""
    vlm = CapturingVLM()
    PromptJudge(vlm, context="[규정컨텍스트마커]").judge(
        [{"order": 0, "tile": None, "text": "문구"}], "KR"
    )
    assert "[규정컨텍스트마커]" in vlm.prompt
    assert "라벨" in vlm.prompt  # 기존 판정 지시도 그대로


def test_prompt_judge_without_context_is_exactly_base_prompt():
    """context 미지정이면 기존 JUDGE_PROMPT 그대로(회귀 방지)."""
    vlm = CapturingVLM()
    PromptJudge(vlm).judge([{"order": 0, "tile": None, "text": "문구"}], "KR")
    assert vlm.prompt == JUDGE_PROMPT.format(items="0. 문구")


def test_loc_carries_coordinates_from_sentence():
    """이미지 문장 dict의 밴드 좌표·원본 크기를 Location에 싣는다."""
    loc = _loc(
        {
            "order": 3,
            "tile": "t01.png",
            "y_start": 1400,
            "y_end": 2820,
            "source_h": 9000,
            "source_w": 1000,
        }
    )
    assert loc.tile == "t01.png"
    assert loc.order == 3
    assert loc.y_start == 1400
    assert loc.y_end == 2820
    assert loc.source_h == 9000
    assert loc.source_w == 1000


def test_loc_defaults_coordinates_none_for_text():
    """좌표 없는(텍스트 입력) 문장 dict는 Location 좌표가 None."""
    loc = _loc({"order": 0, "tile": None})
    assert loc.y_start is None
    assert loc.y_end is None
    assert loc.source_h is None
    assert loc.source_w is None


def _sentences(texts: list[str]) -> list[dict]:
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


class FakeVLM:
    """미리 정한 results(번호→라벨/근거)를 돌려주는 가짜 판정 VLM."""

    def __init__(self, results: list[dict]):
        self._results = results

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        return {"results": self._results}


class BoomVLM:
    """항상 실패하는 VLM(429·빈응답 흉내)."""

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        raise ValueError("VLM이 빈 응답을 반환했다")


def test_maps_labels_to_findings():
    """위반 라벨은 finding으로, 합법·대상외는 무시."""
    vlm = FakeVLM(
        [
            {"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"},
            {"n": 1, "label": "합법", "reason": ""},
            {"n": 2, "label": "대상외", "reason": "성분명"},
        ]
    )
    res = PromptJudge(vlm).judge(
        _sentences(["멜라닌 막아 미백", "촉촉한 보습감", "정제수, 글리세린"]), "KR"
    )
    assert isinstance(res, JudgeResult)
    assert len(res.findings) == 1
    assert len(res.unjudged) == 0
    f = res.findings[0]
    assert f.violation_type.value == "2호_기능성오인"
    # ingredients 미입력 → 대조 근거가 없어 검토필요.
    assert f.flag == JudgmentFlag.needs_review
    assert f.legal_basis.startswith("화장품법 제13조")
    assert f.span == "멜라닌 막아 미백"  # 문장 단위 = span은 문장 전체
    # ingredients 미입력이면 원 근거 뒤에 '성분 정합 확인 못 함' 안내가 붙는다.
    assert f.explanation == "미백 주장 (전성분 미입력 — 성분 정합 확인 못 함)"


def test_missing_or_bad_label_becomes_unjudged():
    """모델이 결과를 빠뜨리거나 규격 밖 라벨을 주면 '합법'이 아니라 미판정."""
    vlm = FakeVLM(
        [
            {"n": 0, "label": "이상한라벨", "reason": ""},
            # n=1 결과 누락
        ]
    )
    res = PromptJudge(vlm).judge(_sentences(["문구 A", "문구 B"]), "KR")
    assert res.findings == []
    assert {u.sentence for u in res.unjudged} == {"문구 A", "문구 B"}


def test_batch_failure_marks_all_unjudged():
    """배치 호출 실패는 재시도 없이 그 배치 전체를 미판정으로 남긴다."""
    res = PromptJudge(BoomVLM(), batch_size=12).judge(
        _sentences(["가", "나", "다"]), "KR"
    )
    assert res.findings == []
    assert len(res.unjudged) == 3


def test_batches_span_multiple_calls():
    """batch_size보다 많으면 여러 배치로 나눠 전역 번호로 되짚는다."""
    vlm = FakeVLM(
        [
            {"n": 0, "label": "합법"},
            {"n": 1, "label": "1호_의약품오인", "reason": "재생"},
            {"n": 2, "label": "합법"},
        ]
    )
    # batch_size=1이면 배치가 3번 도는데, FakeVLM은 매번 같은 results를 준다.
    # 각 배치의 전역 번호(0,1,2)와 매칭되는 항목만 살아남는다.
    res = PromptJudge(vlm, batch_size=1).judge(
        _sentences(["보습", "피부 재생", "사용감"]), "KR"
    )
    assert len(res.findings) == 1
    assert res.findings[0].violation_type.value == "1호_의약품오인"
    assert res.findings[0].flag == JudgmentFlag.violation  # 1호는 대조수단 없어 잠정 위반
    assert res.findings[0].location.order == 1


def test_stub_judge_returns_judge_result():
    """StubJudge도 JudgeResult 계약을 지킨다(unjudged 없음)."""
    res = StubJudge().judge(_sentences(["완벽한 보습", "순한 사용감"]), "KR")
    assert isinstance(res, JudgeResult)
    assert len(res.findings) == 1  # "완벽" → 5호
    assert res.findings[0].flag == JudgmentFlag.violation  # StubJudge는 항상 위반
    assert res.unjudged == []


def test_stub_judge_accepts_ingredients_param_and_ignores_it():
    """StubJudge는 성분 정합을 안 하지만 인터페이스(ingredients 파라미터)는 지킨다."""
    res = StubJudge().judge(
        _sentences(["미백에 도움"]), "KR", ingredients=["나이아신아마이드"]
    )
    assert isinstance(res, JudgeResult)


def test_ingredient_match_found_is_needs_review():
    """전성분에 고시원료가 있어도 등록 여부는 모르니 단정 못 하고 검토필요."""
    vlm = FakeVLM([{"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"}])
    res = PromptJudge(vlm).judge(
        _sentences(["멜라닌 억제해 미백에 도움"]),
        "KR",
        ingredients=["정제수", "나이아신아마이드", "글리세린"],
    )
    assert len(res.findings) == 1
    f = res.findings[0]
    assert f.flag == JudgmentFlag.needs_review
    assert "나이아신아마이드 확인됨" in f.explanation


def test_ingredient_match_missing_is_violation():
    """전성분에 해당 기능 고시원료가 없으면 근거로 확증된 위반."""
    vlm = FakeVLM([{"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"}])
    res = PromptJudge(vlm).judge(
        _sentences(["멜라닌 억제해 미백에 도움"]),
        "KR",
        ingredients=["정제수", "글리세린"],  # 미백 고시원료 없음
    )
    f = res.findings[0]
    assert f.flag == JudgmentFlag.violation
    assert "고시원료가 전성분에 없음" in f.explanation


def test_ingredient_category_unclear_is_needs_review_without_note():
    """카테고리를 못 정하면(문구에 미백/주름/자외선 키워드 없음) 검토필요, 안내문은 생략."""
    vlm = FakeVLM([{"n": 0, "label": "2호_기능성오인", "reason": "기능성 표방"}])
    res = PromptJudge(vlm).judge(
        _sentences(["피부에 좋은 효과"]),  # 카테고리 키워드 없음
        "KR",
        ingredients=["정제수", "나이아신아마이드"],
    )
    f = res.findings[0]
    assert f.flag == JudgmentFlag.needs_review
    assert f.explanation == "기능성 표방"  # 안내 안 붙음


def test_ingredient_match_skipped_for_non_functional_violation():
    """1호·5호는 성분표 대조 대상이 아니라 항상 위반, 안내도 안 붙는다."""
    vlm = FakeVLM([{"n": 0, "label": "1호_의약품오인", "reason": "재생 효과"}])
    res = PromptJudge(vlm).judge(
        _sentences(["피부 재생 효과"]), "KR", ingredients=["정제수"]
    )
    f = res.findings[0]
    assert f.flag == JudgmentFlag.violation
    assert f.explanation == "재생 효과"  # 안내 안 붙음
