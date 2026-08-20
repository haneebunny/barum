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


def test_kca_체크리스트가_규정_컨텍스트에_실린다():
    """사례 검색(top-K)으로는 안 걸릴 수 있는 규칙 표라 규정 쪽에 싣는다.

    컨텍스트에 없으면 모델은 그 기준을 아예 못 본다(⑥에서 인정문구가 안 실려 위반으로
    찍히던 것과 같은 구조).
    """
    from barum.reference.context import build_regulation_context

    build_regulation_context.cache_clear()
    ctx = build_regulation_context()
    assert "KCA 실증자료 구비서류 체크리스트" in ctx
    assert "○○ 원료 함유" in ctx
    assert "원산지증명서" in ctx


def test_절을_못_찾으면_조용히_넘어가지_않는다():
    """팩이 개편돼 절 이름이 바뀌면 grounding에서 소리 없이 사라진다 — 그건 실행해도 안 보인다."""
    import pytest

    from barum.reference.context import _read_section

    with pytest.raises(ValueError):
        _read_section("cases.md", "**있을 리 없는 절 제목**")
