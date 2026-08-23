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
    from barum.reference.context import (
        build_regulation_chunks,
        build_regulation_context,
    )

    # 캐시는 조각 빌더가 들고 있다(문자열 렌더는 매번 새로 만든다).
    build_regulation_chunks.cache_clear()
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


# ── 근거 조각 id (인용 대조의 전제) ────────────────────────────────────────

def test_조각마다_고유_id가_붙는다():
    """모델이 근거를 인용하려면 조각을 가리킬 이름이 있어야 한다."""
    from barum.reference.context import build_judgment_chunks

    chunks = build_judgment_chunks()
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), f"id가 겹친다: {ids}"
    assert all(c.id for c in chunks), "id 없는 조각이 있다"


def test_규정은_L_사례는_C_접두사다():
    """규정과 사례는 근거의 성격이 달라 접두사로 갈라 둔다."""
    from barum.reference.context import build_judgment_chunks

    chunks = build_judgment_chunks()
    assert [c.id for c in chunks if c.id.startswith("L")], "규정 조각이 없다"
    assert [c.id for c in chunks if c.id.startswith("C")], "사례 조각이 없다"
    assert all(c.id[0] in "LC" for c in chunks)


def test_컨텍스트_문자열에_id가_노출된다():
    """프롬프트에 안 보이면 모델이 그 id로 인용할 수 없다."""
    from barum.reference.context import build_judgment_chunks, build_judgment_context

    ctx = build_judgment_context()
    for c in build_judgment_chunks():
        assert f"[{c.id}]" in ctx, f"{c.id}가 컨텍스트에 안 보인다"


def test_조각_원문이_컨텍스트에_그대로_실린다():
    """인용 대조는 '실제로 실린 문자열' 기준이라 조각 text와 어긋나면 안 된다."""
    from barum.reference.context import build_judgment_chunks, build_judgment_context

    ctx = build_judgment_context()
    for c in build_judgment_chunks():
        assert c.text in ctx, f"{c.id} 원문이 컨텍스트와 다르다"
