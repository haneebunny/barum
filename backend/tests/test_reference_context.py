"""판정 근거 컨텍스트 로더(reference.context) 유닛테스트.

레퍼런스 md를 읽어 프롬프트 블록으로 합치는 순수 로직. VLM 없음.

    ./venv/bin/python -m pytest tests/test_reference_context.py -q
"""

from barum.reference.context import build_judgment_context


def test_context_includes_key_reference_content():
    """금지표현·판정기준·실사례 문서 내용이 컨텍스트에 다 들어간다."""
    ctx = build_judgment_context()
    assert isinstance(ctx, str) and ctx
    assert "아토피" in ctx  # 금지표현/1호 판정기준
    assert "실증대상" in ctx  # type_1 판정기준(진정 등 경계)
    assert "광고업무정지" in ctx  # cases.md 실제 적발 처분


def test_context_is_stable_across_calls():
    """같은 입력이면 같은 컨텍스트(캐시·결정론)."""
    assert build_judgment_context() == build_judgment_context()
