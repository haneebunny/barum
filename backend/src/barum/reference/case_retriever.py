"""유사 적발사례 검색 → 판정 프롬프트용 사례 블록 (Phase3).

새 광고 문장과 비슷한 과거 적발사례를 pgvector로 찾아, 그 사례들만 프롬프트에
넣는다(cases.md 통째 인라인을 대체). 사례가 늘어도 관련된 것만 들어가 판단이 안
흐려진다(PM2 취지).

embed_fn·search_fn을 주입받아 Supabase·OpenAI에 직접 의존하지 않는다(테스트는 가짜).
- embed_fn(texts) -> 벡터 리스트(입력당 1개)
- search_fn(vector, k) -> 유사 사례 dict 리스트({text, violation, disposition, similarity})

**뽑는 방식(2026-08-22 개편).** 예전엔 배치 전체의 검색 결과를 유사도 하나로 줄
세워 상위 cap개만 실었다. 두 가지가 샜다.

1. **문장 기아.** 문장 10개가 6칸을 두고 경쟁해서, 어떤 문장은 참고 사례가 0건인
   채로 판정됐다. 미백 문장이 6칸을 다 가져가면 아토피 문장 몫이 없다.
2. **유형 쏠림.** 사례에 붙은 위반유형 꼬리표(`violation`)를 뽑을 때 전혀 안 봤다.
   T1만 6칸을 채워도 막을 게 없었다. 창고 분포는 골고루인데(2026-08-22 실측:
   T1 21건, T6 22건, T5 20건, T2 9건) 뽑기가 한쪽으로 쏠릴 조건이 있었다.

그래서 문장별로 돌아가며 한 건씩 뽑고(기아 방지), 한 유형이 자리의 절반을 넘게
차지하지 못하게 상한을 둔다(쏠림 방지). 상한 때문에 자리가 남으면 상한을 풀고
채운다. 즉 상한은 "골고루 먼저", 빈 칸을 만들지는 않는다.

**꼬리표를 검색 전 필터로 쓰지 않는 이유.** 여기까지 오는 문장은 규칙집이 유형을
확정하지 못한 것들뿐이다(`RagJudge.judge`가 규칙 확정분을 먼저 걷어낸다). 어느
유형을 찾을지 모르는 상태라 `where violation = ?`를 걸 수가 없다. 그래서 꼬리표는
검색을 좁히는 데가 아니라 **결과를 담을 때의 배분 기준**으로 쓴다.
"""

import re
from collections import Counter
from collections.abc import Callable

# 사례 꼬리표에서 유형코드를 뽑는다. 값이 자유서술이라("T2 기능성 오인 + T5 근거수치")
# 정규화 없이 문자열 그대로 비교하면 같은 유형이 다른 유형으로 세어진다.
_TYPE_CODE = re.compile(r"T\d+")
_UNKNOWN_TYPE = "기타"


def primary_type(violation: str | None) -> str:
    """사례 꼬리표의 대표 유형코드. 여러 개면 첫 번째, 없으면 '기타'.

    복합 라벨(`T1 의약품 오인 + T5 근거수치`)은 첫 코드를 대표로 삼는다. 배분에
    쓰는 값이라 정확한 다중 라벨링보다 예측 가능한 한 개 값이 낫다.
    """
    codes = _TYPE_CODE.findall(violation or "")
    return codes[0] if codes else _UNKNOWN_TYPE


class CaseRetriever:
    """배치 문장들에 대해 유사 사례를 모아 하나의 근거 블록으로 만든다.

    문장마다 top-K를 뽑고, 문장별로 돌아가며 한 건씩 담아 상위 cap개를 싣는다.
    프롬프트는 배치당 1개로 유지된다.
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
            # 문장별 후보를 따로 들고 있는다. 여기서 합쳐버리면 어느 문장이 찾아온
            # 사례인지 잃어버려 문장별 배분을 할 수 없다.
            per_sentence = [
                sorted(
                    self._search(vec, self._k),
                    key=lambda c: c.get("similarity", 0),
                    reverse=True,
                )
                for vec in vectors
            ]
        except Exception as e:
            print(f"    [skip] 사례 검색 실패 — 규정만으로 판정: {type(e).__name__}: {e}")
            return ""

        chosen = self._select(per_sentence, self._effective_cap(len(per_sentence)))
        if not chosen:
            return ""
        # 담는 순서는 배분이 정하지만 보여주는 순서는 유사도순이 읽기 좋다.
        chosen.sort(key=lambda c: c.get("similarity", 0), reverse=True)
        return self._format(chosen)

    def _effective_cap(self, n_sentences: int) -> int:
        """이 배치에서 실을 사례 수. 문장이 많으면 자리를 늘린다.

        cap이 6으로 고정이면 문장 12개짜리 배치에서 절반은 무조건 굶는다. 사례 한 줄은
        50~80자라, 이미 규정 md를 통째로 싣는 프롬프트에서 몇 줄 더 붙는 비용은 작다.
        무한정 늘지는 않게 cap의 2배를 상한으로 둔다.
        """
        return min(max(self._cap, n_sentences), self._cap * 2)

    def _select(self, per_sentence: list[list[dict]], cap: int) -> list[dict]:
        """문장별로 돌아가며 한 건씩 담아 cap개까지 고른다.

        순서가 중요하다.
        1. **문장마다 한 건씩**(유형 상한 없이). 기아 방지가 최우선이라 여기에 상한을
           걸면 안 된다. 실제로 걸어봤더니, 두 문장의 최적 사례가 같은 유형일 때
           상한이 둘째 문장 몫을 막아 고치려던 기아를 그대로 다시 만들었다.
        2. 남은 자리는 유형 상한을 지키며 채운다(쏠림 방지).
        3. 상한 때문에 자리가 남으면 상한을 풀고 채운다. 상한은 "골고루 먼저"를
           위한 것이지 빈 칸을 만들기 위한 게 아니다.
        """
        chosen: list[dict] = []
        seen: set[str] = set()
        by_type: Counter = Counter()
        # 자리의 절반까지만 한 유형에 준다. cap=6이면 유형당 3건.
        type_cap = max(1, (cap + 1) // 2)

        def take(c: dict) -> None:
            chosen.append(c)
            seen.add(c.get("text"))
            by_type[primary_type(c.get("violation"))] += 1

        # 1. 문장마다 한 건씩.
        for cands in per_sentence:
            if len(chosen) >= cap:
                break
            for c in cands:
                if c.get("text") not in seen:
                    take(c)
                    break

        # 2~3. 남은 자리 채우기. enforce=True는 유형 상한을 지키고, False는 푼다.
        for enforce in (True, False):
            while len(chosen) < cap:
                took_any = False
                for cands in per_sentence:
                    if len(chosen) >= cap:
                        break
                    for c in cands:
                        if c.get("text") in seen:
                            continue
                        if enforce and by_type[primary_type(c.get("violation"))] >= type_cap:
                            continue
                        take(c)
                        took_any = True
                        break  # 이 문장 몫은 한 건. 다음 문장으로 넘어간다
                if not took_any:
                    break  # 더 담을 게 없다
        return chosen

    @staticmethod
    def _format(cases: list[dict]) -> str:
        lines = ["### 유사 과거 적발사례 (유사도순, 참고용)"]
        for c in cases:
            v = c.get("violation", "")
            d = c.get("disposition", "")
            lines.append(f'- "{c["text"]}" → {v} / {d}')
        return "\n".join(lines)
