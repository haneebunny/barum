"""규칙집 키워드가 레퍼런스팩 원문에 근거를 갖는지 감사한다.

`judge_rules.json`의 violation·needs_review 키워드마다 팩(`reference/cosmetic_kr/`)
어디에 근거가 있는지 문자열로 대조해 위치를 찾는다. 못 찾은 키워드는 **판정 근거를
사용자에게 보여줄 수 없는 지적**을 만든다.

왜 필요한가. 2026-08-20에 팩 §1 별표1에서 38개를 일괄 추가했다가 오탐으로 5개를
되돌린 적이 있다. 그때 문제는 "팩에 있는가"를 사람이 눈으로 확인했다는 것이다.
이 스크립트는 그 확인을 기계가 하게 만든다.

**정적 감사다.** 규칙 키워드와 팩은 런타임에 안 바뀌므로 판정 때마다 돌 필요가 없다.
CI/테스트에서 돌려 회귀만 막으면 된다.

사용:
    python -m scripts.rule_evidence_audit          # 사람이 읽는 리포트
    python -m scripts.rule_evidence_audit --json   # 기계용(테스트가 읽는다)
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_REF_DIR = _BACKEND.parent / "reference" / "cosmetic_kr"
_RULES_PATH = _BACKEND / "src" / "barum" / "reference" / "data" / "judge_rules.json"

# 근거로 인정하는 팩 문서. 순서 = 근거 우선순위(앞이 더 강한 근거).
# prohibited_expressions.md가 정본이고, 위반유형별 문서는 그 해설이다.
_EVIDENCE_FILES: tuple[str, ...] = (
    "prohibited_expressions.md",
    "violation_types/type_1_drug_misperception.md",
    "violation_types/type_2_functional_misperception.md",
    "violation_types/type_5_deception.md",
    "functional_ingredients.md",
    "cases.md",
)

# 대조용 정규화. rules.py의 `_normalize`(공백·붙임표·가운뎃점)보다 넓게 지운다.
# 팩은 사람이 읽는 표라 "세포·유전자(DNA) 활성화"처럼 괄호·쉼표가 섞여 있어서,
# 좁게 잡으면 팩이 실제로 덮는 표현까지 "근거 없음"으로 나온다.
_STRIP = re.compile(r"[\s·,\.\-—()\[\]'\"·:;/]+")


def _norm(text: str) -> str:
    """대조용 정규화 — 구두점·공백을 지우고 소문자로."""
    return _STRIP.sub("", unicodedata.normalize("NFKC", text)).lower()


def _sections(rel: str) -> list[tuple[str, str]]:
    """문서를 절 단위로 쪼갠다 → [(절 라벨, 정규화 본문)].

    `## ` 헤딩을 경계로 삼는다. 헤딩 앞 도입부는 "머리말"로 둔다. 절 단위로 쪼개는
    이유는 "팩 어딘가에 있다"가 아니라 **어느 조항이 근거인가**까지 알아야
    사용자에게 보여줄 수 있어서다.
    """
    text = (_REF_DIR / rel).read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    parts = re.split(r"^(##+ .*)$", text, flags=re.M)
    head = parts[0]
    if head.strip():
        out.append((f"{rel} 머리말", _norm(head)))
    for i in range(1, len(parts), 2):
        label = parts[i].lstrip("# ").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out.append((f"{rel} {label}", _norm(parts[i] + body)))
    return out


def find_evidence(keyword: str, index: list[tuple[str, str]]) -> str | None:
    """키워드의 근거 절 라벨을 찾는다. 없으면 None(삼키지 않고 호출부가 보고)."""
    needle = _norm(keyword)
    if not needle:
        return None
    for label, body in index:
        if needle in body:
            return label
    return None


def _hint(keyword: str) -> list[str]:
    """근거를 못 찾은 키워드에 대해 팩에서 비슷한 줄을 찾아 보여준다.

    "콜라겐증가"는 팩에 없지만 팩은 "콜라겐·효소 증가·감소·활성화"로 덮고 있다.
    열거형 표기라 문자열 대조로는 안 잡히는 것뿐이다. 근거가 진짜 없는 것과
    표기만 다른 것은 조치가 완전히 다르므로(전자는 규칙 제거, 후자는 근거 매핑),
    사람이 즉시 가릴 수 있게 후보 줄을 같이 낸다.
    """
    # 키워드 앞 2글자를 단서로 쓴다. "약국판매" → "약국", "콜라겐증가" → "콜라"
    stem = keyword[:2]
    if len(stem) < 2:
        return []
    hits: list[str] = []
    for rel in _EVIDENCE_FILES:
        for line in (_REF_DIR / rel).read_text(encoding="utf-8").splitlines():
            if stem in line and len(hits) < 2:
                hits.append(f"{rel}: {line.strip()[:110]}")
    return hits


def audit() -> dict:
    """규칙 키워드 전수를 감사해 결과 dict를 낸다."""
    index: list[tuple[str, str]] = []
    for rel in _EVIDENCE_FILES:
        index.extend(_sections(rel))

    rules = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    missing: list[dict] = []

    for bucket in ("violation", "needs_review"):
        for vtype, keywords in rules.get(bucket, {}).items():
            for kw in keywords:
                label = find_evidence(kw, index)
                key = f"{bucket}/{vtype}/{kw}"
                if label is None:
                    missing.append(
                        {
                            "bucket": bucket,
                            "type": vtype,
                            "keyword": kw,
                            "hints": _hint(kw),
                        }
                    )
                else:
                    found[key] = label

    total = len(found) + len(missing)
    return {"total": total, "found": found, "missing": missing}


def main() -> int:
    result = audit()
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    total, missing = result["total"], result["missing"]
    print(f"규칙 키워드 {total}건 감사 (근거 문서 {len(_EVIDENCE_FILES)}종)")
    print(f"  근거 확인: {total - len(missing)}건")
    print(f"  근거 없음: {len(missing)}건")
    if missing:
        print("\n[근거 없음] 이 키워드로 잡힌 지적은 사용자에게 보여줄 원문이 없다:")
        for m in missing:
            print(f"  - {m['bucket']}/{m['type']}: {m['keyword']}")
            for h in m["hints"]:
                print(f"      팩 후보 | {h}")
            if not m["hints"]:
                print("      팩 후보 | 없음 (근거가 진짜 없을 가능성)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
