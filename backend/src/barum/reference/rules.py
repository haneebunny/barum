"""RagJudge 규칙집 대조.

`judge_rules.json`(손 큐레이션)의 키워드와 광고 문장을 정확 조회로 대조해
판정 3갈래(위반/검토필요/합법확정) 중 하나를 낸다. 의미검색이 아니라 정규화
문자열 포함 검사라 임베딩 없이 충분하다(ingredients.py와 같은 방식).

규칙은 §3(규정 리서치로 검증된 1호 경계표현)을 encode한다. 규칙에 안 걸리는
문장은 여기서 판단하지 않고 None을 돌려 VLM(PromptJudge)에 위임한다.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

from barum.models import JudgmentFlag, ViolationType

_DATA_PATH = Path(__file__).resolve().parent / "data" / "judge_rules.json"


class RuleOutcome(Enum):
    """규칙 매칭의 세 갈래. 미매칭은 match_rule이 None을 낸다(VLM 위임)."""

    violation = "violation"  # 위반 확정
    needs_review = "needs_review"  # 실증대상 등 근거 약함 → 검토필요
    legal_allow = "legal_allow"  # 합법 확정(finding 없음, VLM에도 안 넘김)


@dataclass
class RuleMatch:
    """규칙 매칭 결과.

    span = 걸린 키워드(문장 일부가 아니라 규칙 문구 자체). legal_allow면
    violation_type·flag는 없다(위반이 아니므로).
    """

    outcome: RuleOutcome
    span: str
    violation_type: ViolationType | None
    flag: JudgmentFlag | None


def _normalize(text: str) -> str:
    """대조용 정규화 — 공백·붙임표·가운뎃점을 지운다(ingredients와 동일)."""
    return re.sub(r"[\s·\-]", "", text)


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def match_rule(sentence: str) -> RuleMatch | None:
    """문장을 규칙집과 대조해 첫 매칭 한 건을 낸다. 미매칭이면 None.

    우선순위대로 스캔한다: violation > needs_review > legal_allow. 앞 갈래에서
    먼저 걸리면 뒤는 안 본다. 이 순서가 경계표현 조합을 자연히 처리한다
    (예: '시술'이 violation에 있어 '시술 후 진정'은 진정보다 시술이 먼저 hit).
    """
    norm = _normalize(sentence)
    rules = _load()

    for type_label, keywords in rules["violation"].items():
        vtype = ViolationType(type_label)
        for kw in keywords:
            if _normalize(kw) in norm:
                return RuleMatch(RuleOutcome.violation, kw, vtype, JudgmentFlag.violation)

    for type_label, keywords in rules["needs_review"].items():
        vtype = ViolationType(type_label)
        for kw in keywords:
            if _normalize(kw) in norm:
                return RuleMatch(
                    RuleOutcome.needs_review, kw, vtype, JudgmentFlag.needs_review
                )

    for kw in rules["legal_allow"]:
        if _normalize(kw) in norm:
            return RuleMatch(RuleOutcome.legal_allow, kw, None, None)

    return None
