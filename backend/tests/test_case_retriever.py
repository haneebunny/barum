"""CaseRetriever 유닛테스트 (embed·search 함수 주입, 네트워크 없음).

    ./venv/bin/python -m pytest tests/test_case_retriever.py -q
"""

from barum.reference.case_retriever import CaseRetriever


def _sentences(texts):
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


def test_context_for_empty_sentences_is_empty():
    r = CaseRetriever(embed_fn=lambda t: [], search_fn=lambda v, k: [])
    assert r.context_for([]) == ""


def test_embeds_all_texts_once_and_formats_cases():
    """문장 텍스트를 한 번에 임베딩하고, 검색된 사례를 블록으로 만든다."""
    embed_calls = []

    def embed(texts):
        embed_calls.append(list(texts))
        return [[0.0, 0.1] for _ in texts]

    def search(vec, k):
        return [
            {
                "text": "아토피 완화 크림",
                "violation": "T1 의약품 오인",
                "disposition": "광고업무정지 3개월",
                "similarity": 0.9,
            }
        ]

    r = CaseRetriever(embed_fn=embed, search_fn=search, k=3)
    block = r.context_for(_sentences(["문장1", "문장2"]))

    assert embed_calls == [["문장1", "문장2"]]  # 배치 임베딩 1회
    assert "유사" in block and "적발사례" in block  # 사례 블록 헤더
    assert "아토피 완화 크림" in block
    assert "T1 의약품 오인" in block
    # 두 문장이 같은 사례를 반환해도 사례는 한 번만(dedupe).
    assert block.count("아토피 완화 크림") == 1


def test_degrades_to_empty_when_retrieval_fails():
    """임베딩·검색이 실패해도(예: Supabase 다운) 판정이 죽지 않게 빈 블록으로 degrade."""

    def embed(texts):
        return [[0.0] for _ in texts]

    def boom_search(vec, k):
        raise RuntimeError("supabase down")

    r = CaseRetriever(embed_fn=embed, search_fn=boom_search)
    assert r.context_for(_sentences(["a"])) == ""


def test_caps_total_cases():
    """배치 전체에서 상위 cap개까지만 싣는다(사례 폭증 방지)."""

    def embed(texts):
        return [[0.0] for _ in texts]

    def search(vec, k):
        # 매 문장마다 서로 다른 사례 3건
        return [
            {"text": f"사례{i}", "violation": "T1", "disposition": "정지", "similarity": 0.9 - i * 0.1}
            for i in range(3)
        ]

    r = CaseRetriever(embed_fn=embed, search_fn=search, k=3, cap=2)
    block = r.context_for(_sentences(["a", "b", "c"]))
    # 서로 다른 사례가 여러 건 나와도 cap=2까지만.
    assert sum(f"사례{i}" in block for i in range(3)) == 2
