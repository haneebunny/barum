# -*- coding: utf-8 -*-
"""수정 권고안 생성 모듈.

위반 광고 문구와 위반 유형을 입력받아 대체 표현 조건표(JSON)에 따라
매칭되는 대체 표현 리스트와 면책 고지(disclaimer)를 반환한다.
"""

import json
from pathlib import Path
from barum.models import ViolationType

DATA_PATH = Path(__file__).parent / "data" / "remediation_rules.json"

_RULES_CACHE = None


def _load_rules():
    global _RULES_CACHE
    if _RULES_CACHE is None:
        if not DATA_PATH.exists():
            raise RuntimeError(f"Remediation rules JSON file not found: {DATA_PATH}")
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _RULES_CACHE = json.load(f)
    return _RULES_CACHE


def get_remediation(
    sentence: str,
    violation_type: ViolationType | str,
    span: str | None = None,
) -> tuple[list[str], str]:
    """위반 문구에 대해 대체 표현 추천 리스트와 고정 면책 고지 문구를 반환한다.

    1. span 또는 sentence 내에 정의된 키워드가 포함되는지 대조한다.
    2. 매칭되는 키워드 규칙이 있고 유형이 맞을 경우 해당 대체 표현을 사용한다.
    3. 키워드 매칭이 없을 경우, 해당 violation_type의 fallback 대체 표현을 사용한다.
    """
    vtype_val = (
        violation_type.value
        if isinstance(violation_type, ViolationType)
        else violation_type
    )

    # span이 제공되면 span을 우선 검색 대상으로 삼고, 없으면 sentence를 사용한다.
    target_text = span if span is not None else sentence
    if not target_text:
        target_text = ""

    rules_data = _load_rules()

    matched_suggestions = None
    for rule in rules_data.get("rules", []):
        if rule.get("violation_type") == vtype_val:
            for kw in rule.get("keywords", []):
                if kw in target_text:
                    matched_suggestions = rule.get("suggestions")
                    break
        if matched_suggestions is not None:
            break

    if matched_suggestions is None:
        fallbacks = rules_data.get("fallbacks", {})
        matched_suggestions = fallbacks.get(vtype_val, [])

    disclaimer = (
        "본 대체 표현은 화장품법 및 식약처 가이드라인에 따른 일반적인 권고안이며, "
        "실제 광고 적용 시 법적 책임이나 심사 승인을 보장하지 않습니다. "
        "광고 심사/보고 여부 및 인체적용시험 실증 자료 구비 여부에 따라 표현 가능 범위가 달라질 수 있습니다."
    )

    return matched_suggestions, disclaimer
