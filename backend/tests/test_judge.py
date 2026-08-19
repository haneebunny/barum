"""PromptJudge 유닛테스트.

VLM은 가짜 객체(캔드 results 반환/예외)를 주입한다. 진짜 판정 호출은 수동 스모크.

    venv/bin/python -m pytest tests/test_judge.py -q
"""

from barum.judge.cosmetic import JUDGE_PROMPT, JudgeResult, PromptJudge, StubJudge, _loc
from barum.models import JudgmentFlag, ViolationType


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
    assert f.explanation == "미백 주장 (전성분 미입력, 성분 정합 확인 못 함)"


def test_result_matched_by_position_when_n_is_offset():
    """모델이 1-based n(0-based 항목에 n=1)을 줘도, 개수가 맞으면 순서로 매칭한다.

    grounded 긴 프롬프트에서 모델이 출력 예시(n:1)를 따라 1-indexing하는 일이 있다.
    그때 n 조회가 빗나가 미판정으로 흘리지 않게, 결과 수 = 문장 수면 순서로 대응한다.
    """
    vlm = FakeVLM([{"n": 1, "label": "5호_거짓과장기만", "reason": "과장"}])
    res = PromptJudge(vlm).judge(_sentences(["무조건 안전한 제품"]), "KR")
    assert len(res.findings) == 1
    assert res.findings[0].violation_type.value == "5호_거짓과장기만"
    assert res.unjudged == []


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


def test_ingredient_amount_meets_threshold_stays_needs_review_with_registration_note():
    """이름+함량 다 맞아도 등록 여부는 확인 못 해 검토필요 유지, 안내문에 등록 필요성 명시."""
    vlm = FakeVLM([{"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"}])
    res = PromptJudge(vlm).judge(
        _sentences(["멜라닌 억제해 미백에 도움"]),
        "KR",
        ingredients=["정제수", "나이아신아마이드"],
        ingredient_amounts=[("나이아신아마이드", "3%")],
    )
    f = res.findings[0]
    assert f.flag == JudgmentFlag.needs_review
    assert "고시 기준" in f.explanation and "충족" in f.explanation
    assert "등록" in f.explanation and "확인 불가" in f.explanation


def test_ingredient_amount_below_threshold_is_violation():
    """이름은 있는데 함량이 고시 기준 미달이면 위반 확정(정식 심사 대상인데 안 밟은 근거)."""
    vlm = FakeVLM([{"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"}])
    res = PromptJudge(vlm).judge(
        _sentences(["멜라닌 억제해 미백에 도움"]),
        "KR",
        ingredients=["정제수", "알부틴"],
        ingredient_amounts=[("알부틴", "10%")],  # 기준함량 2~5% 범위 초과
    )
    f = res.findings[0]
    assert f.flag == JudgmentFlag.violation
    assert "함량" in f.explanation and "미달" in f.explanation


def test_ingredient_amount_not_given_keeps_existing_needs_review_message():
    """함량 정보 자체를 안 주면 기존 동작(이름만 대조) 그대로, 회귀 없음."""
    vlm = FakeVLM([{"n": 0, "label": "2호_기능성오인", "reason": "미백 주장"}])
    res = PromptJudge(vlm).judge(
        _sentences(["멜라닌 억제해 미백에 도움"]),
        "KR",
        ingredients=["정제수", "나이아신아마이드"],
        # ingredient_amounts 생략
    )
    f = res.findings[0]
    assert f.flag == JudgmentFlag.needs_review
    assert "나이아신아마이드 확인됨" in f.explanation
    assert "등록 여부도 불명" in f.explanation


# ── 1호 의약품오인 규칙 보강 (2026-08-18, §2-1-5 못 잡은 위반 대응) ──


def test_치유_표현을_위반으로_잡는다():
    """`치유`는 동의어 사전에 `치료`의 변형으로 있었지만 실전에서 안 걸렸다.

    동의어는 legal_allow보다 뒤에 검사돼서, "예민한 피부를 치유하는"처럼 합법 단어가
    같이 있으면 legal_allow가 먼저 반환돼 가려졌다(2026-08-18 실측). 대표어로 직접
    넣어 순서와 무관하게 잡히게 했다.
    """
    from barum.reference.rules import RuleOutcome, match_rule

    m = match_rule("예민한 피부를 치유하는 힘을 가진 제주산 천연 병풀추출물이 80% 함유되어")
    assert m is not None
    assert m.outcome is RuleOutcome.violation


def test_약국_입점_표현을_위반으로_잡는다():
    """`약국용`·`약국전용`은 있었는데 `약국 입점`이 없어 놓쳤다. 같은 갈래 변형 확장."""
    from barum.reference.rules import RuleOutcome, match_rule

    for s in ["약국 입점 화장품", "약국 판매 제품", "약국 납품 화장품"]:
        m = match_rule(s)
        assert m is not None, s
        assert m.outcome is RuleOutcome.violation, s


def test_공백이_있어도_약국_변형이_잡힌다():
    """정규화가 공백을 지우므로 띄어쓰기가 달라도 걸려야 한다."""
    from barum.reference.rules import RuleOutcome, match_rule

    for s in ["약국입점 화장품", "약국  입점 화장품"]:
        assert match_rule(s).outcome is RuleOutcome.violation, s


# ── 확정도(flag)를 모델이 직접 답한다 — 2026-08-19 ────────────────────────────
# 예전엔 1호·5호를 무조건 위반으로 고정했는데, 근거 문서는 §3 실증대상을 "검토필요,
# 위반 단정 금지"로 안내하는 반면 답변 라벨엔 그 선택지가 없어서 모델이 합법(미탐)
# 아니면 위반(과잉)으로 몰렸다. 이제 유형과 확정도를 각각 답하게 한다.


class _FlagVLM:
    """지정한 label·flag를 그대로 돌려주는 가짜."""

    def __init__(self, label: str, flag=None):
        self._item = {"n": 0, "label": label, "reason": "사유"}
        if flag is not None:
            self._item["flag"] = flag

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        return {"results": [self._item]}


def _one(text="문구"):
    return [{"order": 0, "tile": None, "text": text}]


def test_model_can_mark_type_1_as_needs_review():
    """1호도 검토필요로 내려갈 수 있다(예전엔 무조건 위반이었다)."""
    res = PromptJudge(_FlagVLM("1호_의약품오인", "검토필요")).judge(_one(), "KR")
    assert len(res.findings) == 1
    assert res.findings[0].flag == JudgmentFlag.needs_review


def test_model_can_mark_type_5_as_needs_review():
    """5호도 마찬가지."""
    res = PromptJudge(_FlagVLM("5호_거짓과장기만", "검토필요")).judge(_one(), "KR")
    assert res.findings[0].flag == JudgmentFlag.needs_review


def test_explicit_violation_flag_stays_violation():
    res = PromptJudge(_FlagVLM("1호_의약품오인", "위반")).judge(_one(), "KR")
    assert res.findings[0].flag == JudgmentFlag.violation


def test_missing_flag_defaults_to_violation():
    """flag가 없는 구버전 응답은 위반으로 둔다(recall 우선, 회귀 방지)."""
    res = PromptJudge(_FlagVLM("1호_의약품오인")).judge(_one(), "KR")
    assert res.findings[0].flag == JudgmentFlag.violation


def test_garbage_flag_defaults_to_violation():
    """오타·규격 밖 값도 위반으로 떨어뜨린다. 모르면 무거운 쪽."""
    res = PromptJudge(_FlagVLM("5호_거짓과장기만", "몰라요")).judge(_one(), "KR")
    assert res.findings[0].flag == JudgmentFlag.violation


def test_type_2_ignores_model_flag_and_uses_ingredient_evidence():
    """2호는 성분 정합이라는 실제 대조 수단이 있다. 모델의 자기 판단보다 대조 결과가
    우선한다 — 모델이 검토필요라고 해도 고시원료가 전성분에 없으면 위반이다."""
    res = PromptJudge(_FlagVLM("2호_기능성오인", "검토필요")).judge(
        _one("미백에 도움을 줍니다"), "KR", ingredients=["정제수", "글리세린"]
    )
    assert res.findings[0].flag == JudgmentFlag.violation


def test_needs_review_label_is_not_a_valid_type():
    """'검토필요'는 label이 아니라 flag다. label로 오면 유형을 못 정하니 미판정으로
    남긴다(안전으로 삼키지 않는다)."""
    res = PromptJudge(_FlagVLM("검토필요", "검토필요")).judge(_one(), "KR")
    assert res.findings == []
    assert len(res.unjudged) == 1


def test_prompt_asks_for_flag_field():
    """프롬프트가 flag를 요구하는지 못박는다(프롬프트 회귀 방지)."""
    assert "검토필요" in JUDGE_PROMPT
    assert "flag" in JUDGE_PROMPT


# ── 캐시 계측 (2026-08-19) ────────────────────────────────────────────────────
# 판정은 근거 문서(2만자)를 배치마다 다시 실어 보낸다. 앞부분이 매번 같아 자동
# 프롬프트 캐싱 대상인데, 적중 여부를 재는 수단이 없어 최적화 판단을 못 했다.


def test_cache_report_computes_hit_rate():
    """cached/prompt 비율을 낸다. 이 숫자를 보고서야 최적화 필요 여부를 말할 수 있다."""
    from barum.vlm import OpenAIVLM

    vlm = OpenAIVLM.__new__(OpenAIVLM)  # 네트워크·키 없이 계측 로직만 본다
    vlm.prompt_tokens, vlm.cached_tokens, vlm.total_tokens = 10_000, 7_500, 12_000
    rep = vlm.cache_report()
    assert rep["hit_rate"] == 0.75
    assert rep["cached_tokens"] == 7_500


def test_cache_report_handles_zero_calls():
    """호출 전에도 0으로 나눠 터지지 않는다."""
    from barum.vlm import OpenAIVLM

    vlm = OpenAIVLM.__new__(OpenAIVLM)
    vlm.prompt_tokens, vlm.cached_tokens, vlm.total_tokens = 0, 0, 0
    assert vlm.cache_report()["hit_rate"] == 0.0


# ── 1차 필터가 버린 문장 관측 (2026-08-19) ────────────────────────────────────
# prescreen에서 버려지면 판정기가 그 문장을 볼 기회 자체가 없는데, 지금까지 무엇이
# 버려졌는지 기록이 없었다. 판정 동작은 안 바꾸고(veto 아님) 관측만 붙인다.


class _PrescreenVLM:
    """1차 필터 응답을 지정한 대로 돌려주는 가짜. 판정 호출은 빈 결과."""

    def __init__(self, claims: list[bool]):
        self._claims = claims
        self.calls = 0

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        self.calls += 1
        if "효능/효과를 주장하는지" in prompt:  # 1차 필터 호출
            return {"results": [{"n": i, "claim": c} for i, c in enumerate(self._claims)]}
        return {"results": []}  # 판정 호출


# 주의: 규칙에 걸리는 문장("15㎛ Pin"·"약국 입점 화장품")은 애초에 prescreen에 안 간다
# (RagJudge가 규칙 미매칭분만 넘김). 그래서 여기선 규칙 미매칭 문장을 쓴다.
def _sents(texts):
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


def test_rag_judge_records_prescreen_dropped_sentences():
    """버린 문장이 last_dropped에 남는다."""
    from barum.judge.cosmetic import RagJudge

    vlm = _PrescreenVLM([True, False, False])
    judge = RagJudge(vlm)
    judge.judge(_sents(["촉촉한 사용감", "대용량 200ml 구성", "국내 자체 공장에서 생산"]), "KR")
    dropped = [s["text"] for s in judge.last_dropped]
    assert dropped == ["대용량 200ml 구성", "국내 자체 공장에서 생산"]


def test_prescreen_drop_is_logged(capsys):
    """버린 문장은 경고로 출력된다. 미탐이 여기서 새면 흔적이 이 로그뿐이다."""
    from barum.judge.cosmetic import RagJudge

    judge = RagJudge(_PrescreenVLM([False]))
    judge.judge(_sents(["대용량 200ml 구성"]), "KR")
    out = capsys.readouterr().out
    assert "prescreen drop" in out
    assert "대용량 200ml 구성" in out


def test_prescreen_drop_does_not_change_judgment():
    """관측만 붙인 것이라 버리는 기준·판정 결과는 그대로다(veto 아님)."""
    from barum.judge.cosmetic import RagJudge

    judge = RagJudge(_PrescreenVLM([False, False]))
    res = judge.judge(_sents(["대용량 200ml 구성", "국내 자체 공장에서 생산"]), "KR")
    # 전부 버려졌으니 판정 호출도 없고 finding도 없다(기존 동작 그대로).
    assert res.findings == []
    assert len(judge.last_dropped) == 2


def test_last_dropped_resets_between_runs():
    """직전 실행 기록이 다음 실행에 남지 않는다."""
    from barum.judge.cosmetic import RagJudge

    judge = RagJudge(_PrescreenVLM([False]))
    judge.judge(_sents(["대용량 200ml 구성"]), "KR")
    assert len(judge.last_dropped) == 1
    judge._vlm = _PrescreenVLM([True])
    judge.judge(_sents(["촉촉한 사용감"]), "KR")
    assert judge.last_dropped == []


# ── needs_review 확정 + 2호 표방 동반 → VLM에도 넘긴다 (2026-08-19) ───────────
# 규칙이 1호 경계표현으로 먼저 확정하면 같은 문장의 2호 클레임이 평가될 기회를 잃던
# 문제. PR#142에서 고친 legal_allow 삼킴과 같은 계열인데, 이쪽은 finding은 나오므로
# 규칙 판정을 빼지 않고 VLM 판정을 "더한다".


class _RecordingVLM:
    """1차 필터는 전부 통과시키고, 판정 호출에 넘어온 문장을 기록한다."""

    def __init__(self, label="2호_기능성오인", flag="검토필요"):
        self.judged_prompts = []
        self._label, self._flag = label, flag

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        if "효능/효과를 주장하는지" in prompt:
            return {"results": [{"n": i, "claim": True} for i in range(20)]}
        self.judged_prompts.append(prompt)
        return {"results": [{"n": 0, "label": self._label,
                             "flag": self._flag, "reason": "미백 표방"}]}


def test_needs_review_with_functional_claim_also_goes_to_vlm():
    """'진정에 도움을 주는 미백 크림'은 규칙(진정)으로 끝나지 않고 VLM에도 간다."""
    from barum.judge.cosmetic import RagJudge

    vlm = _RecordingVLM()
    judge = RagJudge(vlm)
    res = judge.judge(_sents(["진정에 도움을 주는 미백 크림"]), "KR")
    assert vlm.judged_prompts, "2호 표방이 섞였는데 VLM에 안 넘어갔다"
    types = {f.violation_type for f in res.findings}
    assert ViolationType.type_1_drug_misperception in types  # 규칙 판정 유지
    assert ViolationType.type_2_functional_misperception in types  # VLM이 2호 추가


def test_needs_review_without_functional_claim_stays_rule_only():
    """2호 표방이 없으면 기존대로 규칙에서 끝난다(불필요한 VLM 호출 안 늘린다)."""
    from barum.judge.cosmetic import RagJudge

    vlm = _RecordingVLM()
    judge = RagJudge(vlm)
    res = judge.judge(_sents(["진정에 도움을 주는 크림"]), "KR")
    assert vlm.judged_prompts == []
    assert len(res.findings) == 1
    assert res.findings[0].violation_type == ViolationType.type_1_drug_misperception


def test_violation_rule_with_functional_claim_stays_rule_only():
    """위반 확정(needs_review 아님)은 그대로 규칙에서 끝낸다. 이미 무거운 판정이라
    VLM을 더 부를 이유가 없다."""
    from barum.judge.cosmetic import RagJudge

    vlm = _RecordingVLM()
    judge = RagJudge(vlm)
    judge.judge(_sents(["상처를 치료하는 미백 크림"]), "KR")
    assert vlm.judged_prompts == []
