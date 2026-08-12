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


# 순수 숫자(또는 범위) + 단위만 있는 표기만 파싱한다. "산으로 10%"·"25% (자외선차단성분으로서)"
# 처럼 주석이 붙은 값은 일부러 걸러낸다 — create 모드는 함량기준을 결정론적으로 확인 못 하면
# 안전하게 스킵하는 게 원칙이라, 애매한 표기를 억지로 해석하지 않는다.
_AMOUNT_RE = re.compile(
    r"^(?P<low>\d+(?:,\d{3})*(?:\.\d+)?)"
    r"(?:~(?P<high>\d+(?:,\d{3})*(?:\.\d+)?))?"
    r"\s*(?P<unit>%|IU/g)$"
)


def parse_amount(value: str) -> tuple[float, float, str] | None:
    """"2%"·"2~5%"·"2,500 IU/g" 같은 표기를 (하한, 상한, 단위)로 파싱한다.

    범위가 아니면 하한=상한. 단위 불명·주석 섞인 값은 None(비교 불가 → 호출부가 스킵 처리).
    """
    m = _AMOUNT_RE.match(value.strip())
    if not m:
        return None
    low = float(m.group("low").replace(",", ""))
    high = float(m.group("high").replace(",", "")) if m.group("high") else low
    return low, high, m.group("unit")


# 카테고리별 기준 방향. 미백·주름개선은 "기준 함량"(자료제출 생략 허용구간, 범위 안이어야
# 함) 이상, 자외선차단은 "최대 함량" 이하. 필드명이 카테고리마다 다르다.
_THRESHOLD_FIELD = {"미백": "기준 함량", "주름개선": "기준 함량", "자외선차단": "최대 함량"}


def check_amount_threshold(category: str, row: dict, amount: str) -> bool:
    """입력 함량이 해당 카테고리 고시원료 기준을 충족하는지 결정론적으로 확인한다.

    - 기준 함량이 범위(예 "2~5%")면 그 구간 안에 있어야 통과(범위 밖은 정식 심사
      대상이라 이 카테고리로는 조건 미충족). 단일값이면 "이상"이면 통과.
    - 최대 함량은 항상 "이하"면 통과.
    - 단위가 다르거나(% vs IU/g) 어느 한쪽이라도 파싱 실패하면 비교 불가 → False.
    """
    field = _THRESHOLD_FIELD.get(category)
    if field is None or field not in row:
        return False
    target = parse_amount(row[field])
    given = parse_amount(amount)
    if target is None or given is None:
        return False
    t_low, t_high, t_unit = target
    g_low, g_high, g_unit = given
    if t_unit != g_unit or g_low != g_high:  # 입력은 범위가 아닌 단일값만 지원
        return False
    if field == "기준 함량":
        return (t_low == t_high and g_low >= t_low) or (t_low != t_high and t_low <= g_low <= t_high)
    return g_low <= t_high  # 최대 함량: 이하면 통과


def match_ingredient_strict(category: str, ingredient_amounts: list[tuple[str, str]]) -> dict | None:
    """성분명 매칭 + 함량 명시 + 함량 기준 충족을 모두 확인한다(create 모드 전용).

    improve 모드의 `match_ingredient`(성분명만 대조)와 달리, 여기선 셋 중
    하나라도 실패하면 None — 능동적으로 새 효능 주장을 만드는 거라 더 엄격하다.
    """
    table = _load()["categories"].get(category, [])
    normalized = {_normalize(name): amount for name, amount in ingredient_amounts}
    for row in table:
        amount = normalized.get(_normalize(row["성분명"]))
        if amount is not None and check_amount_threshold(category, row, amount):
            return row
    return None
