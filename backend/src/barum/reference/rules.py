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
_SYNONYMS_PATH = Path(__file__).resolve().parent / "data" / "synonyms.json"


class RuleOutcome(Enum):
    """규칙 매칭의 네 갈래. 미매칭은 match_rule이 None을 낸다(VLM 위임)."""

    violation = "violation"  # 위반 확정
    needs_review = "needs_review"  # 실증대상 등 근거 약함 → 검토필요
    legal_allow = "legal_allow"  # 합법 확정(finding 없음, VLM에도 안 넘김)
    out_of_scope = "out_of_scope"  # 대상외(광고 문구 아님, finding 없음, VLM에도 안 넘김)


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


@lru_cache(maxsize=1)
def _load_synonyms() -> dict[str, list[str]]:
    """동의어 사전을 그대로 캐시(대표어 → 변형 목록)."""
    return json.loads(_SYNONYMS_PATH.read_text(encoding="utf-8"))["synonyms"]


@lru_cache(maxsize=1)
def _load_reverse_synonyms() -> dict[str, tuple[str, str]]:
    """동의어 사전을 역인덱스로 만든다: 정규화된 변형 → (대표어, 원본 변형어).

    원본 변형어를 같이 들고 있는 이유는 문맥예외를 변형 단위로 걸 수 있어야
    해서다(예: "힐링"). 대표어("치료") 단위로만 걸면, "힐링"에 준 예외가
    "치료" 직접 매칭까지 같이 느슨해진다(안전장치가 새는 경로가 된다).
    """
    reverse: dict[str, tuple[str, str]] = {}
    for canonical, variants in _load_synonyms().items():
        for v in variants:
            reverse[_normalize(v)] = (canonical, v)
    return reverse


_ASCII_WORD = re.compile(r"^[A-Za-z]+$")


def _keyword_present(kw: str, norm: str) -> bool:
    """정규화된 문장에 키워드가 있는지 본다.

    순수 영단어 키워드는 뒤에 다른 라틴 알파벳이 바로 붙으면 매칭하지 않는다
    (오른쪽 경계만 본다). "Pin"이 브랜드명 "Pintox"·색상명 "Pink" 안에 부분
    일치로 걸려 대상외 상품 4건을 오탐 내던 문제 때문이다(2026-08-18 실측,
    51번 미세침 표현 잡으려고 추가한 키워드가 부작용을 냄).

    한국어 키워드는 조사가 자연히 붙어("니들이") 오른쪽 경계를 볼 수 없으므로
    기존 부분일치 그대로 둔다.
    """
    kw_norm = _normalize(kw)
    if _ASCII_WORD.match(kw_norm):
        return re.search(re.escape(kw_norm) + r"(?![A-Za-z])", norm) is not None
    return kw_norm in norm


def _has_context_exception(norm: str, kw: str, rules: dict) -> bool:
    """kw의 위반 매칭이 `context_exceptions`에 걸린 문맥 예외인지 본다.

    두 극성을 지원한다(2026-08-18, 힐링 사례로 확장).

    **기본(엑소좀 패턴, polarity 생략)**: 단어 자체가 원래 위반이다. "식물 엑소좀"·
    "우유 엑소좀"처럼 원료 대분류 단어가 붙으면 예외(단, unsafe_markers가 같이
    있으면 예외를 취소하고 위반을 유지한다). adjacency="anywhere"가 아니면
    safe_qualifier가 kw 바로 앞에 붙어야만 예외로 친다(기존 동작 그대로).

    **safe_by_default(힐링 패턴)**: 단어 자체는 흔히 무해하게 쓰인다("힐링의 섬").
    unsafe_markers(예: "피부")가 같이 있을 때만 위반으로 올린다. 반대 극성이라
    safe_qualifiers·adjacency는 안 본다.

    (자동 합법 확정이 아니라 규칙 매칭만 건너뛰고 VLM에 위임 — VLM은 이미 RAG
    근거 문서에서 이 예외를 알고 있다, prohibited_expressions.md 참고.)
    """
    exc = rules.get("context_exceptions", {}).get(kw)
    if not exc:
        return False

    if exc.get("polarity") == "safe_by_default":
        return not any(_normalize(u) in norm for u in exc.get("unsafe_markers", []))

    if any(_normalize(u) in norm for u in exc.get("unsafe_markers", [])):
        return False
    if exc.get("adjacency") == "anywhere":
        return any(_normalize(q) in norm for q in exc.get("safe_qualifiers", []))
    return any(_normalize(q) + _normalize(kw) in norm for q in exc.get("safe_qualifiers", []))


def _match_synonyms(norm: str, rules: dict) -> RuleMatch | None:
    """동의어 역인덱스로 변형 표현을 검사한다. 변형이 걸리면 대표어의 규칙을 적용.

    문맥예외는 변형("힐링") 단위가 있으면 그걸 먼저 보고, 없으면 대표어("치료")
    단위로 본다. 변형 단위를 먼저 보는 이유는, 대표어 단위로만 걸면 "힐링"에
    준 예외가 "치료" 직접 매칭까지 같이 느슨해지기 때문이다.
    """
    reverse = _load_reverse_synonyms()
    for variant_norm, (canonical, variant_raw) in reverse.items():
        if variant_norm not in norm:
            continue
        exceptions = rules.get("context_exceptions", {})
        exc_key = variant_raw if variant_raw in exceptions else canonical
        # 대표어가 어느 갈래(violation/needs_review)에 속하는지 찾는다.
        for type_label, keywords in rules["violation"].items():
            if canonical in keywords:
                if _has_context_exception(norm, exc_key, rules):
                    continue
                vtype = ViolationType(type_label)
                return RuleMatch(RuleOutcome.violation, canonical, vtype, JudgmentFlag.violation)
        for type_label, keywords in rules["needs_review"].items():
            if canonical in keywords:
                vtype = ViolationType(type_label)
                return RuleMatch(
                    RuleOutcome.needs_review, canonical, vtype, JudgmentFlag.needs_review
                )
        if canonical in rules["legal_allow"]:
            return RuleMatch(RuleOutcome.legal_allow, canonical, None, None)
        if canonical in rules.get("out_of_scope", []):
            return RuleMatch(RuleOutcome.out_of_scope, canonical, None, None)
    return None


def match_rule(sentence: str) -> RuleMatch | None:
    """문장을 규칙집과 대조해 첫 매칭 한 건을 낸다. 미매칭이면 None.

    우선순위대로 스캔한다: violation > needs_review > legal_allow > out_of_scope.
    앞 갈래에서 먼저 걸리면 뒤는 안 본다. 이 순서가 경계표현 조합을 자연히
    처리한다(예: '시술'이 violation에 있어 '시술 후 진정'은 진정보다 시술이
    먼저 hit). 대표어로 안 걸리면 동의어 사전(synonyms.json)의 변형 표현도
    검사한다(최후순위. 그래서 동의어로만 표현된 위반은 legal_allow 같은
    단어가 같이 있으면 가려질 수 있다 — 2026-08-18에 '치유'로 실측, 별도
    이슈로 남겨둠. §2-1-5·PM 논의 참고).

    니들류(니들·마이크로니들·미세침·MTS·바늘·Pin·needle)는 예전엔 "단어+메커니즘
    서술 동반"일 때만 위반이었는데(conditional_violation), 2026-08-18 하니
    확정으로 폐지하고 단어 자체로 위반 처리한다(violation 플랫 키워드로 이동).
    "리들"은 상표 등록·장기 미제재된 회피표기라 예외(synonyms.json에서 뺐다).
    """
    norm = _normalize(sentence)
    rules = _load()

    for type_label, keywords in rules["violation"].items():
        vtype = ViolationType(type_label)
        for kw in keywords:
            if not _keyword_present(kw, norm):
                continue
            if _has_context_exception(norm, kw, rules):
                continue
            return RuleMatch(RuleOutcome.violation, kw, vtype, JudgmentFlag.violation)

    for type_label, keywords in rules["needs_review"].items():
        vtype = ViolationType(type_label)
        for kw in keywords:
            if _keyword_present(kw, norm):
                return RuleMatch(
                    RuleOutcome.needs_review, kw, vtype, JudgmentFlag.needs_review
                )

    for kw in rules["legal_allow"]:
        if _keyword_present(kw, norm):
            return RuleMatch(RuleOutcome.legal_allow, kw, None, None)

    for kw in rules.get("out_of_scope", []):
        if _keyword_present(kw, norm):
            return RuleMatch(RuleOutcome.out_of_scope, kw, None, None)

    # 대표어로 안 걸렸으면 동의어 변형으로 재시도
    return _match_synonyms(norm, rules)
