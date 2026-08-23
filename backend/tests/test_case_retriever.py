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
    """사례 폭증 방지. 자리 수는 문장 수를 따라 늘되 cap의 2배가 상한이다.

    **2026-08-22에 계약이 바뀌었다.** 전엔 cap 고정이라 이 케이스가 정확히 2건이었다.
    cap이 고정이면 문장 수가 자리보다 많을 때 뒤쪽 문장이 무조건 굶어서, 자리를
    문장 수만큼(cap의 2배까지) 늘리도록 바꿨다.
    """

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
    # 문장 3개 → 자리 3칸(= max(cap, 문장수), 상한 cap*2=4).
    assert sum(f"사례{i}" in block for i in range(3)) == 3


# ── 배분 규칙 (2026-08-22 개편) ────────────────────────────────────────────
# 예전엔 배치 전체를 유사도 하나로 줄 세워 상위 cap개만 실었다. 문장이 굶고
# 유형이 쏠렸다. 아래가 그 두 가지의 회귀 방지다.


def _case(text, violation, sim):
    return {"text": text, "violation": violation, "disposition": "정지", "similarity": sim}


def test_유사도가_낮아도_문장마다_사례를_한_건은_받는다():
    """문장 기아 회귀 방지.

    예전 방식이면 문장A의 사례 3건이 유사도 상위를 독식해 cap을 다 먹고,
    문장B는 참고 사례 0건으로 판정됐다.
    """
    hits = {
        "A": [_case("A사례1", "T1", 0.99), _case("A사례2", "T1", 0.98), _case("A사례3", "T1", 0.97)],
        "B": [_case("B사례1", "T1", 0.10)],
    }
    order = ["A", "B"]
    calls = {"n": 0}

    def search(vec, k):
        s = hits[order[calls["n"]]]
        calls["n"] += 1
        return s

    r = CaseRetriever(embed_fn=lambda t: [[0.0] for _ in t], search_fn=search, k=3, cap=2)
    block = r.context_for(_sentences(["A", "B"]))
    assert "A사례1" in block
    assert "B사례1" in block  # 유사도 0.10인데도 자기 몫을 받는다


def test_한_유형이_남은_자리를_독식하지_못한다():
    """유형 쏠림 회귀 방지. 문장 1개가 자리 4칸을 채울 때 한 유형은 2건까지."""

    def search(vec, k):
        return [_case(f"T1사례{i}", "T1 의약품 오인", 0.99 - i * 0.01) for i in range(3)] + [
            _case(f"T5사례{i}", "T5 거짓·과장", 0.50 - i * 0.01) for i in range(3)
        ]

    r = CaseRetriever(embed_fn=lambda t: [[0.0] for _ in t], search_fn=search, k=6, cap=4)
    block = r.context_for(_sentences(["a"]))
    assert block.count("T1사례") == 2  # 상한 = (4+1)//2 = 2
    assert block.count("T5사례") == 2


def test_문장이_많으면_자리를_늘린다():
    """cap 고정이면 문장 12개짜리 배치에서 절반이 무조건 굶는다."""
    seq = {"n": 0}

    def search(vec, k):
        i = seq["n"]
        seq["n"] += 1
        return [_case(f"사례{i}", "T1", 0.9)]

    r = CaseRetriever(embed_fn=lambda t: [[0.0] for _ in t], search_fn=search, k=1, cap=6)
    block = r.context_for(_sentences([f"s{i}" for i in range(10)]))
    assert sum(f"사례{i}" in block for i in range(10)) == 10  # 10문장 전부 자기 사례를 받는다


def test_자리는_cap의_2배를_안_넘는다():
    """문장이 아무리 많아도 프롬프트가 무한정 커지진 않게."""
    seq = {"n": 0}

    def search(vec, k):
        i = seq["n"]
        seq["n"] += 1
        return [_case(f"사례{i}", "T1", 0.9)]

    r = CaseRetriever(embed_fn=lambda t: [[0.0] for _ in t], search_fn=search, k=1, cap=3)
    block = r.context_for(_sentences([f"s{i}" for i in range(20)]))
    assert sum(f"사례{i}" in block for i in range(20)) == 6  # cap 3의 2배


def test_유형_상한_때문에_자리를_비우지는_않는다():
    """상한은 골고루 먼저 담기 위한 것이지 빈 칸을 만들기 위한 게 아니다.

    창고에 T1 사례밖에 없으면 상한을 풀고 cap까지 채운다.
    """

    def search(vec, k):
        return [_case(f"T1사례{i}", "T1 의약품 오인", 0.9 - i * 0.1) for i in range(4)]

    r = CaseRetriever(embed_fn=lambda t: [[0.0] for _ in t], search_fn=search, k=4, cap=4)
    block = r.context_for(_sentences(["a"]))
    assert block.count("T1사례") == 4


def test_복합_꼬리표는_첫_유형코드를_대표로_센다():
    """`T2 기능성 오인 + T5 근거수치`처럼 자유서술이라 정규화 없이는 같은 유형이 갈린다."""
    from barum.reference.case_retriever import primary_type

    assert primary_type("T1 의약품 오인") == "T1"
    assert primary_type("T2 기능성 오인 + T5 근거수치") == "T2"
    assert primary_type("T6 천연·유기농 오인(별표5 나)") == "T6"
    assert primary_type("판정불명확") == "기타"
    assert primary_type(None) == "기타"


# ── 사례 조각 id (인용 대조의 전제) ────────────────────────────────────────

def _retriever_with(cases):
    return CaseRetriever(
        embed_fn=lambda texts: [[0.0, 0.1] for _ in texts],
        search_fn=lambda vec, k: cases,
        k=3,
    )


def _chunk_case(text, sim=0.9):
    return {
        "text": text,
        "violation": "T1 의약품 오인",
        "disposition": "광고업무정지 3개월",
        "similarity": sim,
    }


def test_검색된_사례마다_C_id가_붙는다():
    """사례도 규정과 똑같이 인용 대상이다. id가 없으면 대조할 수 없다."""
    r = _retriever_with([_chunk_case("아토피 완화 크림"), _chunk_case("발모 촉진 토닉", 0.8)])
    chunks = r.retrieve(_sentences(["문장1"]))

    assert [c.id for c in chunks] == ["C01", "C02"]
    assert all(c.id.startswith("C") for c in chunks)


def test_사례_조각_원문이_프롬프트_문자열과_같다():
    """프롬프트엔 처분까지 실리는데 조각엔 본문만 담으면, 처분을 인용했을 때
    실제로는 봤는데도 검증 실패로 나온다."""
    r = _retriever_with([_chunk_case("아토피 완화 크림")])
    sentences = _sentences(["문장1"])
    chunks = r.retrieve(sentences)
    block = r.context_for(sentences)

    for c in chunks:
        assert c.text in block
    assert "광고업무정지 3개월" in chunks[0].text


def test_검색_실패해도_빈_조각으로_degrade한다():
    """외부 호출 실패는 예상된 실패다. 판정은 규정만으로 계속 간다."""
    def boom(texts):
        raise RuntimeError("임베딩 실패")

    r = CaseRetriever(embed_fn=boom, search_fn=lambda v, k: [])
    assert r.retrieve(_sentences(["문장1"])) == ()
    assert r.context_for(_sentences(["문장1"])) == ""


def test_문장이_없으면_조각도_없다():
    r = _retriever_with([_chunk_case("아토피 완화 크림")])
    assert r.retrieve([]) == ()
