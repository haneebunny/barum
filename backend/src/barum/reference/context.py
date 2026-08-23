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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Chunk:
    """프롬프트에 실리는 근거 조각 하나.

    `id`는 모델이 근거를 인용할 때 쓰는 짧은 꼬리표다(규정 `L01`, 사례 `C01`).
    판정이 돌아온 뒤 이 id로 원문을 되찾아 인용이 진짜인지 대조한다(judge/verify.py).
    id가 없으면 모델이 "규정에 따르면"이라고만 답해도 확인할 방법이 없다.
    """

    id: str
    label: str  # 사람이 읽는 출처 표기(파일명·절 이름)
    text: str  # 원문. 인용 대조의 기준이 되므로 가공하지 않는다


def _read_block(rel: str) -> Chunk:
    """근거 문서 하나를 조각으로 읽는다. 없으면 FileNotFoundError(삼키지 않음)."""
    text = (_REF_DIR / rel).read_text(encoding="utf-8").strip()
    return Chunk(id="", label=rel, text=text)


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
    return Chunk(id="", label=f"{rel} ({marker})", text=rest[:end].strip())


def _numbered(chunks: list[Chunk], prefix: str) -> tuple[Chunk, ...]:
    """조각에 순번 id를 매긴다(L01, L02 …). 순서는 프롬프트에 붙는 순서 그대로."""
    return tuple(
        Chunk(id=f"{prefix}{i:02d}", label=c.label, text=c.text)
        for i, c in enumerate(chunks, start=1)
    )


def render_chunks(chunks: tuple[Chunk, ...]) -> str:
    """조각들을 프롬프트 블록 문자열로. 헤더에 id를 노출해 모델이 인용할 수 있게 한다."""
    return "\n\n".join(f"### [{c.id}] 근거 문서: {c.label}\n{c.text}" for c in chunks)


@lru_cache(maxsize=1)
def build_regulation_chunks() -> tuple[Chunk, ...]:
    """규정·판정기준 조각들(cases.md 제외). id는 L01부터.

    검색 경로(Phase3)는 여기에 '검색된 사례'만 덧붙인다(cases.md 통째 안 넣음).
    """
    blocks = [_read_block(rel) for rel in _REGULATION_FILES]
    # A/B 측정용 스위치. 끄고 켜서 이 블록의 효과를 잴 수 있게 남긴다(기본 켜짐).
    # 변형을 코드에 안 남기면 다음 세션이 재실행이 아니라 재구현을 하게 된다(⑲ 교훈).
    if os.getenv("BARUM_GROUNDING_CHECKLIST", "1") != "0":
        blocks.append(_read_section(*_CHECKLIST_SECTION))
    return _numbered(blocks, "L")


def build_regulation_context() -> str:
    """규정 컨텍스트 문자열. 조각 id가 헤더에 붙는다."""
    return render_chunks(build_regulation_chunks())


@lru_cache(maxsize=1)
def build_judgment_chunks() -> tuple[Chunk, ...]:
    """규정 + 실사례(cases.md 통째) 조각들(Phase1 기본 grounding).

    Phase3에서 사례를 pgvector 검색으로 바꾸면 이건 안 쓰이고 규정 조각 +
    검색결과 조합으로 넘어간다. 결과는 캐시(md는 런타임에 안 바뀜).

    cases.md는 통째로 실리므로 조각 하나(`C01`)다. 검색 경로는 사례마다 조각을
    쪼개므로 C01, C02 …로 늘어난다.
    """
    cases = _numbered([_read_block(_CASES_FILE)], "C")
    return build_regulation_chunks() + cases


def build_judgment_context() -> str:
    """규정 + 실사례 컨텍스트 문자열(Phase1 기본 grounding)."""
    return render_chunks(build_judgment_chunks())


# ── 대체표현 재작성용 컨텍스트 (0층 grounding) ──────────────────────────────
#
# **재작성기는 지금까지 규칙문서를 한 번도 못 봤다**(2026-08-23 발견). 판정기는
# 팩 44,857자를 받는데 재작성기는 원문·span·유형·조항취지 400자와 프롬프트에
# 하드코딩된 금지어 몇 개가 전부였다. 그 상태로 "알아서 합법으로 써봐"를 요구받으니
# 목록에 없는 위반 표현이 나왔다(`깊숙이 침투`가 그렇게 나왔다).
#
# 출력만 거르는 층(게이트·사례대조)은 필요하지만, 입력이 빠진 채로 거르면 거를 게
# 계속 나온다. 애초에 덜 틀리도록 근거를 준다. **추가 LLM 호출은 없다** — 같은
# 배치 호출의 입력 토큰만 늘어난다.
_APPROVED_FILE = "approved_efficacy_statements.md"
_TYPE_DOC = {
    "1호_의약품오인": "violation_types/type_1_drug_misperception.md",
    "2호_기능성오인": "violation_types/type_2_functional_misperception.md",
    "5호_거짓과장기만": "violation_types/type_5_deception.md",
}
# 유형별로 실을 적발 사례 수. "이렇게 쓴 게 실제로 적발됐다"가 금지 목록보다 강하다.
_CASES_PER_TYPE = 4
_T_CODE = {"1호_의약품오인": "T1", "2호_기능성오인": "T2", "5호_거짓과장기만": "T5"}


@lru_cache(maxsize=8)
def _case_lines_for(t_code: str) -> str:
    """cases.md에서 해당 유형 적발 사례 줄을 몇 개 뽑는다."""
    text = (_REF_DIR / _CASES_FILE).read_text(encoding="utf-8")
    hits = [
        line.strip()
        for line in text.splitlines()
        if line.startswith("|") and t_code in line and "위반유형" not in line
    ]
    return "\n".join(hits[:_CASES_PER_TYPE])


@lru_cache(maxsize=16)
def build_rewrite_context(violation_types: tuple[str, ...]) -> str:
    """대체표현 재작성기에 실을 근거. 이 배치에 나온 유형만 좁혀 싣는다.

    전체 팩(45KB)을 넣지 않는 이유는 필요가 없어서다. 재작성기가 알아야 할 건
    ① 무엇을 써도 되는가(인정문구) ② 이 유형에서 무엇이 금지인가 ③ 실제로 뭐가
    적발됐는가, 셋이다. 배치에 1호만 있으면 2호·5호 문서는 안 싣는다.
    """
    blocks = [_read_block(_APPROVED_FILE)]
    for vtype in violation_types:
        rel = _TYPE_DOC.get(vtype)
        if rel:
            blocks.append(_read_block(rel))
    out = [f"### 근거 문서: {c.label}\n{c.text}" for c in blocks]
    for vtype in violation_types:
        code = _T_CODE.get(vtype)
        lines = _case_lines_for(code) if code else ""
        if lines:
            out.append(f"### 실제 적발 사례 ({code}) — 이렇게 쓰면 적발된다\n{lines}")
    return "\n\n".join(out)
