"""상품 단위 적용범위(대상외) 판단.

문장 단위가 아니라 요청 전체(상품명+본문 다 합친 텍스트)를 한 번 보고 "이 상품이
화장품법 적용 대상인가"를 정한다(`cosmetic_scope.md` 근거). 짜개(도구)·퍼프(부자재)
같은 상품이 문장 단위 판정을 받던 문제 때문에 만들었다 — "짜개"라는 단어가 든
문장은 기존 문장 단위 `out_of_scope`로도 걸러지지만, 같은 상품의 다른 문장("아무리
긁어도 흠집이 생기지 않아요")은 그 단어가 없어서 효능 주장처럼 오판된다.

지금은 규칙(키워드)만 있고 VLM 보완은 없다(judge_rules.json의 out_of_scope 재사용,
정답셋 교차검증된 확실한 사례만).

**애매하면 화장품 쪽으로 판단한다(recall 우선).** 이 게이트가 잘못 걸리면 그 상품의
위반 문장을 통째로 놓치는 미탐이 된다 — 이 프로젝트에서 제일 나쁜 실패 유형이라,
정답셋 53장 전체에서 다른 상품과 안 겹치는 게 확인된 키워드만 쓴다.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "judge_rules.json"


def _normalize(text: str) -> str:
    """대조용 정규화 — 공백·붙임표·가운뎃점을 지운다(rules.py·ingredients.py와 동일 방식)."""
    return re.sub(r"[\s·\-]", "", text)


@lru_cache(maxsize=1)
def _out_of_scope_keywords() -> tuple[str, ...]:
    data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return tuple(data.get("out_of_scope", []))


def check_product_scope(texts: list[str]) -> tuple[bool, str | None]:
    """상품 전체 텍스트(제목+본문)를 합쳐 화장품법 적용 대상인지 정한다.

    반환: (in_scope, matched_keyword). in_scope=False면 대상외 확정(화장품법 적용
    대상 아님). matched_keyword는 화면에 사유를 보여줄 때 쓴다. 텍스트가 비어있거나
    키워드가 하나도 안 걸리면 화장품으로 본다(모르면 화장품 쪽, recall 우선).
    """
    joined = _normalize(" ".join(t for t in texts if t))
    if not joined:
        return True, None
    for kw in _out_of_scope_keywords():
        if _normalize(kw) in joined:
            return False, kw
    return True, None
