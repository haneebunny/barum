"""기능성 고시원료 정합 조회.

`functional_ingredients.md`에서 뽑은 `data/functional_ingredients.json`을 읽어
"광고 문구가 표방한 기능(미백/주름개선/자외선차단)의 고시원료가 전성분에
있는가"를 정확 조회한다. 의미검색이 아니라 정확한 이름 대조라 임베딩 없이
정규화 문자열 비교로 충분하다(functional_ingredients.md "판정에 쓰는 법" 그대로).
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "functional_ingredients.json"

# 문구에 이 키워드가 있으면 해당 기능성 카테고리를 표방한 것으로 본다.
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "미백": ("미백", "화이트닝", "whitening"),
    "주름개선": ("주름",),
    "자외선차단": ("자외선", "UV차단", "SPF"),
}


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def infer_category(sentence: str) -> str | None:
    """문구가 표방하는 기능성 카테고리를 키워드로 추정한다. 못 찾으면 None."""
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in sentence for kw in keywords):
            return category
    return None


def _normalize(name: str) -> str:
    """대조용 정규화 — 공백·붙임표·가운뎃점을 지운다."""
    return re.sub(r"[\s·\-]", "", name)


def match_ingredient(category: str, ingredient_names: list[str]) -> dict | None:
    """전성분 목록에서 해당 카테고리 고시원료를 찾는다. 있으면 표 행 하나, 없으면 None."""
    table = _load()["categories"].get(category, [])
    normalized_input = {_normalize(n) for n in ingredient_names}
    for row in table:
        if _normalize(row["성분명"]) in normalized_input:
            return row
    return None
