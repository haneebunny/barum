"""레이아웃 레퍼런스 로더 (FR-11 create 모드, 모듈 구조 플래너용).

`data/layout_references/*.json`(디자이너 수집)은 실제 화장품 상세페이지의 **구조만**
담는다. 실제 카피·수치는 없고 모듈 종류(kind)·목적(purpose)·위반소지(has_claim_risk)만
있다. 플래너가 이걸 퓨샷 예시로 써서 "이번 상품엔 어떤 모듈을 어떤 순서로 넣을지"를 정한다.

상품 종류는 요청 스키마에 따로 없어서 상품명 키워드로 추측한다(하니 확정, 2026-08-18).
추측 실패는 실패가 아니다. 레퍼런스 없이 기존 방식으로 폴백하면 되므로 None을 낸다.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data" / "layout_references"

# 상품명 키워드 -> 레퍼런스의 product_type.
# 앰플->세럼은 데이터 근거가 있다(홀리추얼 앰플이 레퍼런스에 product_type="세럼"으로 적재됨).
# 에센스->세럼, 밤->크림은 업계 통용 등가 표현이라 묶었다.
# 매핑에 없는 종류(로션 등)는 억지로 끼워맞추지 않고 폴백시킨다.
_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("앰플", "세럼"),
    ("ampoule", "세럼"),
    ("세럼", "세럼"),
    ("serum", "세럼"),
    ("에센스", "세럼"),
    ("essence", "세럼"),
    ("토너", "토너"),
    ("toner", "토너"),
    ("스킨", "토너"),
    ("크림", "크림"),
    ("cream", "크림"),
    ("밤", "크림"),
    ("balm", "크림"),
)


@lru_cache(maxsize=1)
def load_layout_references() -> tuple[dict, ...]:
    """레이아웃 레퍼런스 json을 전부 읽는다. 파일명 순으로 고정(실행마다 순서가 흔들리지 않게).

    `_`로 시작하는 파일(`_vocabulary.json`)은 레퍼런스가 아니라 공용 어휘집이라 뺀다.
    안 빼면 modules 없는 항목이 하나 섞여 들어가 퓨샷 개수·정렬이 흔들린다.
    """
    refs = []
    for path in sorted(_DATA_DIR.glob("*.json")):
        if path.stem.startswith("_"):
            continue
        refs.append(json.loads(path.read_text(encoding="utf-8")))
    return tuple(refs)


@lru_cache(maxsize=1)
def load_layout_vocabulary() -> dict:
    """공용 레이아웃 어휘(`_vocabulary.json`)를 읽는다.

    layout_type 12종 카탈로그(설명)와 product_type별 컬러톤 기본값 후보
    (category_base_tone)를 담고 있다. 후자는 템플릿 색이 아니라
    `GenerateRequest.color_tone` 기본값 후보다(디디·팀장 확정, 2026-08-19).
    """
    return json.loads((_DATA_DIR / "_vocabulary.json").read_text(encoding="utf-8"))


def infer_product_type(product_name: str | None) -> str | None:
    """상품명에서 상품 종류를 추측한다. 못 찾으면 None(폴백 신호).

    예: "아누아 어성초 77 수딩 토너" -> "토너". 브랜드명만 있어 종류 단어가 없으면 None.
    """
    if not product_name:
        return None
    lowered = product_name.lower()
    for keyword, product_type in _TYPE_KEYWORDS:
        if keyword in lowered:
            return product_type
    return None


def _by_module_count(refs: list[dict]) -> list[dict]:
    """모듈 수가 많은 것부터 정렬한다.

    라로슈포제(히어로 1모듈)처럼 수집이 미완결인 레퍼런스를 퓨샷 앞자리에 두면
    플래너가 "1모듈짜리 상세페이지"를 흉내낼 수 있어서다.
    """
    return sorted(refs, key=lambda r: len(r.get("modules", [])), reverse=True)


def select_references(product_type: str | None, limit: int = 3) -> list[dict]:
    """퓨샷 예시로 쓸 레퍼런스를 고른다. 항상 최소 1건은 낸다.

    종류가 맞으면 같은 종류끼리 쓴다. 종류를 못 정했거나 맞는 게 없으면 스킨케어
    레퍼런스 아무거나 쓴다(하니 확정, 2026-08-18). 구조 자체는 스킨케어끼리 크게
    다르지 않아서, 예시가 아예 없는 것보다 대충이라도 있는 편이 낫다.
    """
    all_refs = list(load_layout_references())
    matched = [r for r in all_refs if r.get("product_type") == product_type] if product_type else []
    return _by_module_count(matched or all_refs)[:limit]
