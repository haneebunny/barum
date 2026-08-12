"""인증서 → 인정문구 매칭 (create 모드, FR-11 신규 생성).

`data/approved_efficacy_statements.json`(비비 적재, `reference/cosmetic_kr/
approved_efficacy_statements.md`가 근거)에서 카테고리별 인정문구를 읽어, 사용자가
입력한 certifications가 해당 카테고리를 가리키면 문구를 낸다.

**게이트는 카테고리 단위**(`categories[카테고리]["status"]`)다. 원문 대조가 안 끝난
카테고리(status != "confirmed", 예: 자외선차단의 "needs_confirmation")는 그
카테고리만 막힌다 — 최상위 status를 보면 안 된다(카테고리마다 대조 완료 시점이
다르므로 하나가 confirmed돼도 다른 카테고리가 그걸 같이 풀어버리면 위험).
`candidate_statement`(미확정 후보문구)는 절대 안 읽는다, `statements`만 읽는다.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "approved_efficacy_statements.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _certification_claims_category(category: str, certifications: list[str]) -> bool:
    """인증서 문자열 중 하나가 이 카테고리를 가리키는지 본다(예: "미백 기능성 인증")."""
    return any(category in cert for cert in certifications)


def match_approved_claim(category: str, certifications: list[str]) -> str | None:
    """인증서가 카테고리를 가리키고, 그 카테고리가 원문 대조 완료(status=confirmed)면 인정문구를 낸다.

    카테고리별 status가 confirmed가 아니거나(미대조·미확정) 인증서 매칭이 없으면
    None(문구를 지어내지 않음).
    """
    if not _certification_claims_category(category, certifications):
        return None
    entry = _load()["categories"].get(category, {})
    if entry.get("status") != "confirmed":
        return None
    statements = entry.get("statements") or []
    return statements[0] if statements else None
