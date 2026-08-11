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

# 규정·판정기준 문서(정본 md). 순서 = 프롬프트에 붙는 순서. 실사례(cases.md)는 별도.
_REGULATION_FILES: tuple[str, ...] = (
    "prohibited_expressions.md",
    "violation_types/type_1_drug_misperception.md",
    "violation_types/type_2_functional_misperception.md",
    "violation_types/type_5_deception.md",
    "functional_ingredients.md",
)
# 실사례. Phase1은 통째로, Phase3은 pgvector 검색 top-K로 대체한다.
_CASES_FILE = "cases.md"


def _read_block(rel: str) -> str:
    """근거 문서 하나를 읽어 헤더 붙인 블록으로. 없으면 FileNotFoundError(삼키지 않음)."""
    text = (_REF_DIR / rel).read_text(encoding="utf-8").strip()
    return f"### 근거 문서: {rel}\n{text}"


@lru_cache(maxsize=1)
def build_regulation_context() -> str:
    """규정·판정기준 문서만 합친 컨텍스트(cases.md 제외).

    검색 경로(Phase3)는 여기에 '검색된 사례'만 덧붙인다(cases.md 통째 안 넣음).
    """
    return "\n\n".join(_read_block(rel) for rel in _REGULATION_FILES)


@lru_cache(maxsize=1)
def build_judgment_context() -> str:
    """규정 + 실사례(cases.md 통째)를 합친 컨텍스트(Phase1 기본 grounding).

    Phase3에서 사례를 pgvector 검색으로 바꾸면 이건 안 쓰이고 build_regulation_context
    + 검색결과 조합으로 넘어간다. 결과는 캐시(md는 런타임에 안 바뀜).
    """
    return build_regulation_context() + "\n\n" + _read_block(_CASES_FILE)
