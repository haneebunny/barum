"""법령·고시 인용 레지스트리 조회 (`citation_registry.json` 단일 소스).

프론트 푸터·`CheckReport.basis`가 규제 근거를 하드코딩하다 다른 도메인(식품) 고시번호를
잘못 섞어 쓴 사고(2026-08-13, "고시 2025-79호")가 있었다. 이후 비비가 구축한
`citation_registry.json`이 유일한 소스이고, 이 모듈은 그걸 구조화해서 내보내기만 한다
(다른 reference/*.py처럼 조회 전용, 판정 로직 없음).
"""

import json
from functools import lru_cache
from pathlib import Path

from barum.models import BasisCitation, Region, RegulatoryBasis

_DATA_PATH = Path(__file__).resolve().parent / "data" / "citation_registry.json"

# 검사·푸터에 보여줄 "일반 적용 기준"으로 고른 항목 id. 특정 위반유형에만 조건부로
# 붙는 고시(예: 2호 성분정합의 심사규정 제2023-61호)는 제외하고, 모든 검사에 공통으로
# 적용되는 최상위 근거만 고른다. US는 barum 판정에 아직 미사용이라(1단계 KR만)
# citation_registry.json에도 "참고용"으로 명시돼 있다 — 여기서도 표시만 하고 CheckReport.
# basis에는 안 실린다(judge가 region=KR만 실동작이라 pipeline.py에서 KR만 채움).
_KR_CORE_IDS = ("kr_law_art13", "kr_rule_appendix5", "kr_guideline_2025_08_14")
_US_CORE_IDS = ("us_mocra_2022", "us_fda_ftc_general")


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _entry_by_id(entry_id: str) -> dict:
    for e in _load()["entries"]:
        if e["id"] == entry_id:
            return e
    raise KeyError(f"citation_registry.json에 없는 id: {entry_id}")


def get_core_citations(jurisdiction: str) -> list[dict]:
    """검사·푸터에 보여줄 일반 적용 기준 목록을 raw dict로 낸다. jurisdiction: "KR"|"US"."""
    ids = _KR_CORE_IDS if jurisdiction == "KR" else _US_CORE_IDS
    return [_entry_by_id(i) for i in ids]


def build_regulatory_basis(jurisdiction: str) -> RegulatoryBasis:
    """`GET /reference/basis`·`CheckReport.basis`가 그대로 쓰는 Pydantic 모델을 만든다."""
    citations = [
        BasisCitation(
            id=e["id"],
            law_name=e["law_name"],
            citation_id=e.get("citation_id"),
            effective_date=e.get("effective_date"),
            source_url=e.get("source_url"),
        )
        for e in get_core_citations(jurisdiction)
    ]
    return RegulatoryBasis(jurisdiction=Region(jurisdiction), citations=citations)
