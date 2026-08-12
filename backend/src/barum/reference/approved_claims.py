"""인증서 → 인정문구 매칭 (create 모드, FR-11 신규 생성).

`data/approved_efficacy_statements.json`(비비 적재, `reference/cosmetic_kr/
approved_efficacy_statements.md`가 근거)에서 카테고리별 인정문구를 읽어, 사용자가
입력한 certifications가 해당 카테고리를 가리키면 문구를 낸다.

데이터가 `status: "draft"`인 동안은 별표4 고시 원문 대조가 안 끝난 상태라(비비
노트: "원문 대조 전까지 실제 광고 문구 생성에 쓰지 말 것") 절대 문구를 내지 않는다.
대조가 끝나 status가 바뀌면 코드 변경 없이 자동으로 살아난다.
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
    """인증서가 카테고리를 가리키고, 데이터가 원문 대조 완료(status != draft) 상태면 인정문구를 낸다.

    원문 대조 전(status=draft)이거나 인증서 매칭이 없으면 None(문구를 지어내지 않음).
    """
    data = _load()
    if data.get("status") == "draft":
        return None
    if not _certification_claims_category(category, certifications):
        return None
    statements = data["categories"].get(category, {}).get("statements") or []
    return statements[0] if statements else None
