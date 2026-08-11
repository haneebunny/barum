"""유사 적발사례 검색 → 판정 프롬프트용 사례 블록 (Phase3).

새 광고 문장과 비슷한 과거 적발사례를 pgvector로 찾아, 그 사례들만 프롬프트에
넣는다(cases.md 통째 인라인을 대체). 사례가 늘어도 관련된 것만 들어가 판단이 안
흐려진다(PM2 취지).

embed_fn·search_fn을 주입받아 Supabase·OpenAI에 직접 의존하지 않는다(테스트는 가짜).
- embed_fn(texts) -> 벡터 리스트(입력당 1개)
- search_fn(vector, k) -> 유사 사례 dict 리스트({text, violation, disposition, similarity})
"""

from collections.abc import Callable


class CaseRetriever:
    """배치 문장들에 대해 유사 사례를 모아 하나의 근거 블록으로 만든다.

    문장마다 top-K를 뽑되, 배치 전체에서 중복 제거하고 유사도순 상위 cap개만 싣는다.
    문장 단위 정밀 매칭 대신 배치 단위 union이라 프롬프트는 배치당 1개로 유지된다.
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]],
        search_fn: Callable[[list[float], int], list[dict]],
        k: int = 3,
        cap: int = 6,
    ):
        self._embed = embed_fn
        self._search = search_fn
        self._k = k
        self._cap = cap

    def context_for(self, sentences: list[dict]) -> str:
        """문장들과 유사한 사례를 찾아 근거 블록 문자열로. 없으면 빈 문자열."""
        texts = [s["text"] for s in sentences]
        if not texts:
            return ""

        # 임베딩·검색은 외부(OpenAI·Supabase) 호출이라 실패할 수 있다. 실패해도
        # 판정 자체는 살아야 하므로(규정만으로 grounding) 빈 블록으로 degrade한다.
        try:
            vectors = self._embed(texts)
            # 배치 전체에서 사례 dedupe(문구 기준), 같은 사례면 더 높은 유사도를 남긴다.
            by_text: dict[str, dict] = {}
            for vec in vectors:
                for case in self._search(vec, self._k):
                    key = case["text"]
                    prev = by_text.get(key)
                    if prev is None or case.get("similarity", 0) > prev.get(
                        "similarity", 0
                    ):
                        by_text[key] = case
        except Exception as e:
            print(f"    [skip] 사례 검색 실패 — 규정만으로 판정: {type(e).__name__}: {e}")
            return ""

        if not by_text:
            return ""
        ranked = sorted(
            by_text.values(), key=lambda c: c.get("similarity", 0), reverse=True
        )[: self._cap]
        return self._format(ranked)

    @staticmethod
    def _format(cases: list[dict]) -> str:
        lines = ["### 유사 과거 적발사례 (유사도순, 참고용)"]
        for c in cases:
            v = c.get("violation", "")
            d = c.get("disposition", "")
            lines.append(f'- "{c["text"]}" → {v} / {d}')
        return "\n".join(lines)
