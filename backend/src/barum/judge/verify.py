"""판정이 인용한 근거가 실재하는지 대조한다.

모델이 "규정에 따르면 위반입니다"라고만 답하면 그 말이 맞는지 확인할 방법이 없다.
그래서 판정할 때 **어느 조각을 봤는지(source_id)**와 **거기서 무엇을 읽었는지(quote)**를
같이 받고, 여기서 그 인용이 진짜인지 문자열로 대조한다.

**외부 호출이 없다. 문자열 비교뿐이라 비용 0원이고 결정론적이다.**

세 가지를 본다.
  a. `source_id`가 실제로 프롬프트에 실린 조각인가
  b. `quote`가 그 조각 원문에 있는가
  c. `span`이 판정 대상 문장에 있는가

**검증에 실패해도 지적은 안 버린다**(`judge/cosmetic.py`가 그렇게 쓴다). 컴플라이언스
도구에서 진짜 위반이 설명 검증 실패로 사라지면 그게 더 위험하다. 설명만 떼고 지적은
남긴다. 파싱 실패를 합법으로 삼키지 않고 분리해 두는 기존 원칙과 같다.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..reference.context import Chunk

# 대조용 정규화. 팩은 사람이 읽는 문서라 같은 표현도 공백·가운뎃점·괄호가 다르게 붙는다.
# 좁게 잡으면 실제로 본 인용을 "없다"고 판정한다.
# **마크다운 기호를 반드시 포함해야 한다.** 팩은 md 문서라 강조가 `**...**`로 붙는데,
# 모델은 사람이 읽는 형태로 인용해서 별표를 빼고 옮긴다. 이걸 안 지우면 실재하는
# 인용이 대조에 실패한다(2026-08-23 실측: 실패 4건 중 1건이 이 이유였다. 팩
# `- 효능·효과: **"피부의 미백에 도움을 준다."**`를 모델이 별표 없이 옮긴 것).
_STRIP = re.compile(r"[\s·,\.\-—()\[\]'\"“”‘’:;/|*_`>#~+→]+")

# 인용이 이 길이보다 짧으면 대조가 의미 없다. "다"·"의" 같은 조각은 어느 문서에나 있다.
_MIN_QUOTE = 4

# 축약 인용을 통과시키는 최소 연속 일치 길이(정규화 후 글자 수).
#
# **왜 필요한지는 실측으로 확인했다**(2026-08-23, 60문장). 대조 실패 4건이 전부
# 지어낸 인용이 아니라 **실재하는 원문을 축약한 것**이었다. 예를 들어 팩 원문
# "객관적 근거가 없으면 검토필요(위반후보), 있으면 예외."를 모델이
# "객관적 근거 없으면 검토필요, 있으면 예외."로 조사·괄호를 빼고 옮겼다.
# 출처 조각 id는 4건 다 맞았다. 축자 일치만 보면 이런 걸 전부 할루시네이션으로
# 세게 되고, 그러면 수치가 실제보다 나쁘게 나올 뿐 아니라 멀쩡한 지적의 설명이
# 떨어져 나간다.
#
# 20자로 잡은 근거: 지어낸 인용은 원문과 이만큼 길게 연속으로 겹치기 어렵고,
# 축약 인용은 앞부분이 통째로 남아 쉽게 넘는다. 실측 4건은 30자 이상 겹쳤다.
_MIN_ANCHOR = 20


@dataclass(frozen=True)
class VerifyResult:
    """인용 대조 결과. 실패면 왜 실패했는지 남긴다(측정에서 사유별로 세야 한다)."""

    ok: bool
    reason: str | None = None
    # 어느 항목에서 걸렸는지. "source"=주입 안 된 조각 인용, "quote"=원문에 없는 인용,
    # "span"=문장에 없는 span. 통과하면 None. 항목별로 세야 "0건"이 무엇의 0건인지
    # 드러난다.
    category: str | None = None
    # 어떻게 통과했는지. "exact"=축자 일치, "partial"=축약 인용(연속 일치로 확인).
    # 두 경로를 갈라 세야 "지어냈다"와 "줄여 옮겼다"를 구분해 보고할 수 있다.
    mode: str | None = None


def normalize(text: str) -> str:
    """대조용 정규화 — 공백·구두점을 지우고 소문자로."""
    return _STRIP.sub("", unicodedata.normalize("NFKC", text or "")).lower()


def verify_citation(
    source_id: str | None,
    quote: str | None,
    span: str | None,
    sentence: str,
    chunks: tuple[Chunk, ...],
) -> VerifyResult:
    """인용 한 건을 대조한다. 통과하면 ok=True.

    chunks는 **그 판정에 실제로 실린 조각들**이어야 한다. 전체 팩을 넘기면 모델이
    안 본 문서의 문장을 인용해도 통과해서, 대조가 아무것도 막지 못한다.
    """
    if not source_id:
        return VerifyResult(False, "source_id 없음", category="source")

    by_id = {c.id: c for c in chunks}
    chunk = by_id.get(source_id.strip())
    if chunk is None:
        return VerifyResult(False, f"주입 안 된 조각 인용: {source_id}", category="source")

    if not quote or len(normalize(quote)) < _MIN_QUOTE:
        return VerifyResult(False, "quote 없음/너무 짧음", category="quote")

    nq, nt = normalize(quote), normalize(chunk.text)
    mode = "exact"
    if nq not in nt:
        # 축자로 안 맞아도 원문과 길게 연속으로 겹치면 축약 인용으로 본다.
        match = SequenceMatcher(None, nq, nt, autojunk=False).find_longest_match(
            0, len(nq), 0, len(nt)
        )
        if match.size < _MIN_ANCHOR:
            return VerifyResult(
                False,
                f"{source_id} 원문에 없는 quote(최장 일치 {match.size}자)",
                category="quote",
            )
        mode = "partial"

    # span은 모델이 문장에서 집어낸 부분이다. 문장에 없으면 지어낸 것이다.
    if span and normalize(span) not in normalize(sentence):
        return VerifyResult(False, "span이 문장에 없음", category="span")

    return VerifyResult(True, mode=mode)
