"""판정 근거 컨텍스트 로더(reference.context) 유닛테스트.

레퍼런스 md를 읽어 프롬프트 블록으로 합치는 순수 로직. VLM 없음.

    ./venv/bin/python -m pytest tests/test_reference_context.py -q
"""

from barum.reference.context import (
    build_judgment_context,
    build_regulation_context,
)


def test_regulation_context_excludes_cases():
    """규정 전용 컨텍스트는 규정·판정기준은 넣되 cases.md(실사례)는 뺀다.

    검색 경로(Phase3)는 규정 + '검색된' 사례만 넣으므로, cases.md 통째는 안 들어간다.
    """
    reg = build_regulation_context()
    assert "아토피" in reg  # 규정·판정기준
    assert "실증대상" in reg
    assert "광고업무정지" not in reg  # cases.md의 실제 처분 문구는 빠짐


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
