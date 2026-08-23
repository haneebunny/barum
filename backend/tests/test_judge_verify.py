"""인용 대조 유닛테스트 (외부 호출 없음).

    ./venv/bin/python -m pytest tests/test_judge_verify.py -q
"""

from barum.judge.verify import normalize, verify_citation
from barum.reference.context import Chunk

_CHUNKS = (
    Chunk(id="L01", label="prohibited_expressions.md", text="아토피, 모낭충, 살균·소독, 해독"),
    Chunk(id="C01", label="과거 적발사례", text='"아토피 완화 크림" → T1 의약품 오인 / 광고업무정지'),
)
_SENTENCE = "이 크림은 아토피 완화에 도움을 줍니다"


def test_실재하는_인용은_통과한다():
    r = verify_citation("L01", "살균·소독", "아토피", _SENTENCE, _CHUNKS)
    assert r.ok and r.reason is None


def test_사례_조각도_인용할_수_있다():
    """사례에 id가 없으면 사례 인용은 전량 실패한다. 규정과 같은 자격이어야 한다."""
    r = verify_citation("C01", "T1 의약품 오인", "아토피", _SENTENCE, _CHUNKS)
    assert r.ok


def test_안_실린_조각을_인용하면_실패한다():
    """모델이 본 적 없는 문서를 지어내는 걸 잡는 게 핵심이다."""
    r = verify_citation("L09", "살균·소독", "아토피", _SENTENCE, _CHUNKS)
    assert not r.ok and "L09" in r.reason


def test_원문에_없는_문구를_인용하면_실패한다():
    r = verify_citation("L01", "이 문구는 팩에 없습니다", "아토피", _SENTENCE, _CHUNKS)
    assert not r.ok and "quote" in r.reason


def test_문장에_없는_span은_실패한다():
    """span은 문장에서 집어낸 부분이다. 문장에 없으면 지어낸 것이다."""
    r = verify_citation("L01", "살균·소독", "발모촉진", _SENTENCE, _CHUNKS)
    assert not r.ok and "span" in r.reason


def test_source_id가_없으면_실패한다():
    assert not verify_citation(None, "살균·소독", "아토피", _SENTENCE, _CHUNKS).ok
    assert not verify_citation("", "살균·소독", "아토피", _SENTENCE, _CHUNKS).ok


def test_너무_짧은_인용은_통과시키지_않는다():
    """'의'·'다' 같은 조각은 어느 문서에나 있어 대조가 아무것도 막지 못한다."""
    assert not verify_citation("L01", "해독", "아토피", _SENTENCE, _CHUNKS).ok
    assert not verify_citation("L01", None, "아토피", _SENTENCE, _CHUNKS).ok


def test_표기_차이는_통과시킨다():
    """팩은 사람이 읽는 문서라 가운뎃점·공백이 제각각이다. 좁게 잡으면 실제로 본
    인용을 '없다'고 판정한다."""
    assert verify_citation("L01", "살균 소독", "아토피", _SENTENCE, _CHUNKS).ok
    assert verify_citation("L01", "살균, 소독", "아토피", _SENTENCE, _CHUNKS).ok
    assert verify_citation(" L01 ", "살균·소독", "아토피", _SENTENCE, _CHUNKS).ok


def test_span_없이도_인용만_맞으면_통과한다():
    """규칙 경로처럼 span이 문장 일부가 아닌 경우가 있어 span은 선택 조건이다."""
    assert verify_citation("L01", "살균·소독", None, _SENTENCE, _CHUNKS).ok


def test_normalize는_구두점과_대소문자를_지운다():
    assert normalize("살균·소독") == normalize("살균 소독") == "살균소독"
    assert normalize("Pin") == "pin"


# ── 축약 인용 (2026-08-23 실측으로 필요성 확인) ────────────────────────────

_LONG = Chunk(
    id="L04",
    label="type_5_deception.md",
    text="**완벽한·최적의·파워·탁월한·최고·최상 등 절대적·과장 표현은 객관적 근거가 없으면 검토필요(위반후보), 있으면 예외.**",
)


def test_원문을_줄여_옮긴_인용은_통과한다():
    """실측 실패 4건이 전부 이 경우였다. 지어낸 게 아니라 조사·괄호를 뺀 축약이었다."""
    r = verify_citation(
        "L04",
        "완벽한·최적의·파워·탁월한·최고·최상 등 절대적·과장 표현은 객관적 근거 없으면 검토필요, 있으면 예외.",
        None,
        "문장",
        (_LONG,),
    )
    assert r.ok and r.mode == "partial"


def test_축자로_맞으면_exact로_구분된다():
    """두 경로를 갈라야 '지어냈다'와 '줄여 옮겼다'를 나눠 보고할 수 있다."""
    r = verify_citation("L04", "객관적 근거가 없으면 검토필요", None, "문장", (_LONG,))
    assert r.ok and r.mode == "exact"


def test_지어낸_인용은_축약_관용에도_안_걸린다():
    """관용이 너무 넓으면 게이트가 아무것도 막지 못한다."""
    r = verify_citation(
        "L04", "제13조 제7항에 따라 즉시 회수 대상으로 규정한다", None, "문장", (_LONG,)
    )
    assert not r.ok and "최장 일치" in r.reason


def test_짧게_겹치는_것만으로는_못_통과한다():
    """원문 어절 몇 개를 물고 나머지를 지어낸 인용은 막아야 한다.

    (축자로 들어맞는 짧은 인용은 통과한다 — 짧아도 원문에 실재하는 문자열이다.)
    """
    r = verify_citation("L04", "절대적·과장 표현은 즉시 회수 대상이다", None, "문장", (_LONG,))
    assert not r.ok and "최장 일치" in r.reason


def test_마크다운_강조는_대조를_방해하지_않는다():
    """팩은 md라 `**...**`로 강조가 붙는데 모델은 별표를 빼고 인용한다.

    실측에서 실제로 이 이유로 실재하는 인용이 실패했다(2026-08-23).
    """
    chunk = Chunk(id="L06", label="approved", text='- 효능·효과: **"피부의 미백에 도움을 준다."**')
    r = verify_citation("L06", '효능·효과: "피부의 미백에 도움을 준다."', None, "문장", (chunk,))
    assert r.ok and r.mode == "exact"


def test_실패는_항목별로_구분된다():
    """'0건'이라고 말하려면 무엇이 0건인지 드러나야 한다."""
    assert verify_citation(None, "살균·소독", None, _SENTENCE, _CHUNKS).category == "source"
    assert verify_citation("L09", "살균·소독", None, _SENTENCE, _CHUNKS).category == "source"
    assert verify_citation("L01", "없는 문구입니다 정말로", None, _SENTENCE, _CHUNKS).category == "quote"
    assert verify_citation("L01", "살균·소독", "발모", _SENTENCE, _CHUNKS).category == "span"
    assert verify_citation("L01", "살균·소독", "아토피", _SENTENCE, _CHUNKS).category is None
