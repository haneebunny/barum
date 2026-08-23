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
