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

import os
from functools import lru_cache
from pathlib import Path

# context.py: backend/src/barum/reference/context.py → parents[3] = backend.
_BACKEND = Path(__file__).resolve().parents[3]
_REF_DIR = _BACKEND.parent / "reference" / "cosmetic_kr"

# 규정·판정기준 문서(정본 md). 순서 = 프롬프트에 붙는 순서. 실사례(cases.md)는 별도.
# `approved_efficacy_statements.md`는 2026-08-20에 추가했다. 그 전까지 이 목록은 전부
# "무엇이 위반인가" 문서였고 **"무엇이 합법인가"를 알려주는 문서가 하나도 없었다.**
# 그 결과 식약처 인정문구("피부의 미백에 도움을 준다." 등 고시 제2023-61호 별표4)를
# 3개 다 2호 위반으로 찍었다(3회 반복 실측, 편차 없음). 법이 "이렇게 쓰라"고 정해준
# 문구를 의심스럽다고 판정하던 셈이다. 근거가 금지 쪽으로만 쏠려 있으면 모델 판단도
# 계통적으로 플래그 쪽으로 쏠린다(docs/result/2026-08-20_판정로직_고도화_로그.md ⑦).
_REGULATION_FILES: tuple[str, ...] = (
    "prohibited_expressions.md",
    "violation_types/type_1_drug_misperception.md",
    "violation_types/type_2_functional_misperception.md",
    "violation_types/type_5_deception.md",
    "functional_ingredients.md",
    "approved_efficacy_statements.md",
)
# 실사례. Phase1은 통째로, Phase3은 pgvector 검색 top-K로 대체한다.
_CASES_FILE = "cases.md"

# cases.md 안에 사례가 아니라 **규칙 표**가 하나 들어 있다 — KCA(대한화장품협회) 실증자료
# 구비서류 체크리스트. "○○ 원료 함유"·"원산지(○○산 원료)"처럼 어떤 광고 표현에 어떤 자료가
# 필요한지 정한 표라 사례 검색(Phase3 top-K)으로는 안 걸릴 수 있고, 그러면 모델이 그 기준을
# 아예 못 본다(⑥에서 인정문구가 컨텍스트에 없어 위반으로 찍히던 것과 같은 구조).
# **팩 파일은 안 고친다**(레퍼런스팩 변경은 승인 사안). 그 절만 읽어 규정 컨텍스트에 싣는다.
_CHECKLIST_SECTION = ("cases.md", "**KCA 실증자료 구비서류 체크리스트**")


def _read_block(rel: str) -> str:
    """근거 문서 하나를 읽어 헤더 붙인 블록으로. 없으면 FileNotFoundError(삼키지 않음)."""
    text = (_REF_DIR / rel).read_text(encoding="utf-8").strip()
    return f"### 근거 문서: {rel}\n{text}"


def _read_section(rel: str, marker: str) -> str:
    """문서에서 marker로 시작하는 절만 잘라낸다(다음 `---` 또는 `## ` 앞까지).

    팩 원문을 안 고치고 일부만 컨텍스트에 싣기 위한 것이다. marker가 없으면 조용히
    빈 문자열을 돌려주지 않고 **예외로 터뜨린다** — 팩이 개편돼 절 이름이 바뀌면
    grounding에서 이 기준이 소리 없이 사라지는데, 그건 실행해도 안 보인다.
    """
    text = (_REF_DIR / rel).read_text(encoding="utf-8")
    i = text.find(marker)
    if i < 0:
        raise ValueError(f"{rel}에서 '{marker}' 절을 못 찾았다 — 팩이 바뀌었는지 확인할 것")
    rest = text[i:]
    end = len(rest)
    for stop in ("\n---", "\n## "):
        j = rest.find(stop, len(marker))
        if j > 0:
            end = min(end, j)
    return f"### 근거 문서: {rel} ({marker})\n{rest[:end].strip()}"


@lru_cache(maxsize=1)
def build_regulation_context() -> str:
    """규정·판정기준 문서만 합친 컨텍스트(cases.md 제외).

    검색 경로(Phase3)는 여기에 '검색된 사례'만 덧붙인다(cases.md 통째 안 넣음).
    """
    blocks = [_read_block(rel) for rel in _REGULATION_FILES]
    # A/B 측정용 스위치. 끄고 켜서 이 블록의 효과를 잴 수 있게 남긴다(기본 켜짐).
    # 변형을 코드에 안 남기면 다음 세션이 재실행이 아니라 재구현을 하게 된다(⑲ 교훈).
    if os.getenv("BARUM_GROUNDING_CHECKLIST", "1") != "0":
        blocks.append(_read_section(*_CHECKLIST_SECTION))
    return "\n\n".join(blocks)


@lru_cache(maxsize=1)
def build_judgment_context() -> str:
    """규정 + 실사례(cases.md 통째)를 합친 컨텍스트(Phase1 기본 grounding).

    Phase3에서 사례를 pgvector 검색으로 바꾸면 이건 안 쓰이고 build_regulation_context
    + 검색결과 조합으로 넘어간다. 결과는 캐시(md는 런타임에 안 바뀜).
    """
    return build_regulation_context() + "\n\n" + _read_block(_CASES_FILE)
