"""미국 자외선차단 승인성분 정합 조회.

`sunscreen_active_ingredients.md`에서 뽑은 `data/us_sunscreen_ingredients.json`(미국 승인
17종)과 `data/us_sunscreen_synonyms.json`(INCI명↔CFR 공식명 매핑)을 읽어, 전성분 목록 중
자외선차단 성분이 미국에서 승인됐는지 정확 조회한다. 국내 `ingredients.py`와 같은 방식
(정규화 문자열 비교, 임베딩 없음).

"자외선차단 성분인지"는 미국 목록뿐 아니라 국내 `functional_ingredients.json`의 자외선차단
고시원료(27종)까지 합쳐 판단한다 — 한국에만 있고 미국엔 없는 성분(예: 드로메트리졸)도
"자외선차단 성분인데 미국은 미승인"으로 잡아내야 하기 때문이다
(`sunscreen_otc_classification.md` §3 참조).
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_US_DATA_PATH = Path(__file__).resolve().parent / "data" / "us_sunscreen_ingredients.json"
_SYNONYMS_PATH = Path(__file__).resolve().parent / "data" / "us_sunscreen_synonyms.json"
_KR_DATA_PATH = Path(__file__).resolve().parent / "data" / "functional_ingredients.json"


def _normalize(name: str) -> str:
    """대조용 정규화 — 공백·붙임표·가운뎃점을 지우고 소문자화(ingredients.py + 영문 대소문자)."""
    return re.sub(r"[\s·\-]", "", name).lower()


@lru_cache(maxsize=1)
def _load_us() -> dict:
    return json.loads(_US_DATA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_kr() -> dict:
    return json.loads(_KR_DATA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_synonym_reverse() -> dict[str, str]:
    """INCI명 등 변형 → CFR 공식명(대표어) 역인덱스. 대표어 자기 자신도 포함한다."""
    data = json.loads(_SYNONYMS_PATH.read_text(encoding="utf-8"))
    reverse: dict[str, str] = {}
    for canonical, entry in data["synonyms"].items():
        reverse[_normalize(canonical)] = canonical
        for variant in entry["variants"]:
            reverse[_normalize(variant)] = canonical
    return reverse


def canonical_name(name: str) -> str:
    """전성분 표기(INCI명 등)를 CFR 공식명으로 정규화한다. 매핑에 없으면 입력 그대로 돌려준다."""
    return _load_synonym_reverse().get(_normalize(name), name)


@lru_cache(maxsize=1)
def _us_approved_names() -> set[str]:
    return {_normalize(row["성분명"]) for row in _load_us()["categories"]["자외선차단"]}


@lru_cache(maxsize=1)
def _known_uv_filter_names() -> set[str]:
    """자외선차단 성분으로 알려진 이름 전체(정규화됨). 미국 승인 17종 + 국내 고시원료 27종 합집합.

    미국 목록만 쓰면, 한국엔 있지만 미국 목록엔 없는 성분(드로메트리졸 등)이 "자외선차단과
    무관한 일반 성분"으로 오인돼 아예 검사 대상에서 빠진다. 그래서 국내 목록까지 합쳐
    "자외선차단 성분이라는 것 자체는 알려져 있다"를 판단한다.
    """
    kr_rows = _load_kr()["categories"].get("자외선차단", [])
    kr_names = {_normalize(row["성분명"]) for row in kr_rows}
    return _us_approved_names() | kr_names


def is_us_approved(ingredient_name: str) -> bool:
    """이 성분(INCI명 포함)이 미국 승인 자외선차단 성분표에 있는지 확인한다."""
    canonical = canonical_name(ingredient_name)
    return _normalize(canonical) in _us_approved_names()


def is_known_uv_filter(ingredient_name: str) -> bool:
    """이 성분이 (한국·미국 어느 쪽 기준으로든) 자외선차단 성분으로 알려져 있는지 확인한다."""
    canonical = canonical_name(ingredient_name)
    return _normalize(canonical) in _known_uv_filter_names()


def check_sunscreen_ingredients(ingredient_names: list[str]) -> dict[str, list[str]]:
    """전성분 목록을 미국 승인 자외선차단 성분표와 대조한다.

    자외선차단 성분으로 알려진 것만 골라 승인/미승인으로 나눈다(정제수 같은 무관한 일반
    성분은 `is_known_uv_filter`가 False라 대상에서 빠진다). 입력 순서를 보존한다.

    반환: {"approved": [...], "unapproved": [...]} (입력 표기 그대로, 정규화 안 된 원문)
    """
    approved: list[str] = []
    unapproved: list[str] = []
    for name in ingredient_names:
        if not is_known_uv_filter(name):
            continue
        (approved if is_us_approved(name) else unapproved).append(name)
    return {"approved": approved, "unapproved": unapproved}


@lru_cache(maxsize=1)
def _us_active_details() -> dict[str, dict]:
    """정규화된 공식 성분명 → M020 데이터 레코드."""
    return {
        _normalize(row["성분명"]): row
        for row in _load_us()["categories"]["자외선차단"]
    }


def sunscreen_active_details(ingredient_name: str) -> dict | None:
    """성분의 M020 데이터 레코드를 반환한다(없으면 None)."""
    canonical = canonical_name(ingredient_name)
    return _us_active_details().get(_normalize(canonical))
