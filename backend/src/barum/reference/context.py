"""판정 근거 컨텍스트 로더 (RAG grounding).

레퍼런스 팩의 판정 관련 md를 읽어 하나의 프롬프트 블록으로 합친다. 이 블록을
판정 프롬프트 앞에 붙여, LLM이 규정·판정기준·실사례를 실제로 참고해 판단하게 한다.
벡터 검색이 아니라 통째 인라인이다(코퍼스가 작아 충분, PM2 확정).

넣는 문서: 금지표현 목록·위반유형별 판정기준·기능성 성분표·실제 적발사례.
- 성분표는 코드(ingredients.py)가 정확 조회도 하지만, LLM이 기능성 표현을 규정
  맥락에서 이해하도록 프롬프트에도 함께 싣는다(PM2 지시).
- cases.md(실사례)는 Phase1에선 통째로 넣는다. 사례가 늘면 Phase3에서 pgvector
  유사검색 top-K로 교체할 지점이다(주입 지점 하나만 바꾸면 됨).

마크다운이 정본이라 여기서 파생 가공 없이 원문 그대로 이어 붙인다.
"""

from functools import lru_cache
from pathlib import Path

# context.py: backend/src/barum/reference/context.py → parents[3] = backend.
_BACKEND = Path(__file__).resolve().parents[3]
_REF_DIR = _BACKEND.parent / "reference" / "cosmetic_kr"

# 프롬프트에 실을 판정 근거 문서(정본 md). 순서 = 프롬프트에 붙는 순서.
_CONTEXT_FILES: tuple[str, ...] = (
    "prohibited_expressions.md",
    "violation_types/type_1_drug_misperception.md",
    "violation_types/type_2_functional_misperception.md",
    "violation_types/type_5_deception.md",
    "functional_ingredients.md",
    "cases.md",
)


@lru_cache(maxsize=1)
def build_judgment_context() -> str:
    """판정 근거 문서를 합쳐 프롬프트용 컨텍스트 블록을 만든다.

    문서가 없으면(레퍼런스 팩 누락) FileNotFoundError로 즉시 터뜨린다 — 예상 못 한
    실패라 삼키지 않는다. 결과는 캐시한다(md는 런타임에 안 바뀜).
    """
    blocks: list[str] = []
    for rel in _CONTEXT_FILES:
        text = (_REF_DIR / rel).read_text(encoding="utf-8").strip()
        blocks.append(f"### 근거 문서: {rel}\n{text}")
    return "\n\n".join(blocks)
