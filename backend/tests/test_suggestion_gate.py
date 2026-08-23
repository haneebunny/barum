"""대체표현 게이트 회귀 테스트 (외부 호출 없음).

과거 사고가 다시 나면 여기서 깨진다. 상세는 scripts/suggestion_gate_audit.py 참고.
"""

from barum.reference.case_phrases import reuses_sanctioned_phrase
from scripts.suggestion_gate_audit import audit


def test_과거_사고_문구가_전부_막힌다():
    r = audit()
    assert not r["leaked"], f"제안으로 새어나가는 문구가 있다: {r['leaked']}"


def test_정상_문구는_안_막힌다():
    """게이트가 과하게 조이면 사업자 실증 수치까지 지워진다."""
    r = audit()
    assert not r["over_blocked"], f"과차단: {r['over_blocked']}"


def test_적발사례_축자_재사용을_잡는다():
    assert reuses_sanctioned_phrase("피부 깊숙이 침투하여 흡수되는 포뮬러")
    assert not reuses_sanctioned_phrase("산뜻하게 발리는 제형")


def test_원문에서_물려받은_조각은_새_위험으로_안_센다():
    """다시 쓴 문장이 원문 수치를 정당하게 유지하는 경우가 있다.

    물려받은 위험까지 막으면 사업자가 측정한 값을 우리가 지우게 된다.
    """
    original = "진피층까지 침투하여 콜라겐 밀도 38% 증가"
    assert reuses_sanctioned_phrase("피부 깊숙이 침투하는 포뮬러", original)
    # 원문에 이미 있던 조각만 겹치면 새 위험이 아니다.
    assert not reuses_sanctioned_phrase(original, original)


def test_우리_상용구는_위험_신호가_아니다():
    """재작성 프롬프트가 붙이라고 지시하는 문구가 우리 게이트에 걸리면 안 된다."""
    assert not reuses_sanctioned_phrase("4주 사용 시 콜라겐 밀도 38% 증가 (인체적용시험 결과)")


def test_사례_인용_추출이_표_메타데이터를_안_먹는다():
    """닫는 따옴표와 다음 행 여는 따옴표가 짝지어지면 출처 파일명까지 색인된다."""
    from barum.reference.case_phrases import _case_grams, _norm

    grams = _case_grams()
    assert _norm("표시광고위반사례pdf")[:7] not in grams
