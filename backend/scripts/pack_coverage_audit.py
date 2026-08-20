# -*- coding: utf-8 -*-
"""레퍼런스팩이 명시한 금지표현 중 규칙집에 없는 것을 찾는다 (팩 기준 커버리지 감사).

## 왜 만들었나

그동안 규칙 후보를 **정답셋이 틀린 문장**에서 찾았다. 그러면 표본에 있는 표현만
방어하게 된다 — 팀장 지적(2026-08-20): "이런식으로 하나하나 키워드를 잡아주는 방식이면
우리가 갖고 있는 테스트에 맞춤으로 방어하는 거잖아. 이걸 고도화라고 할 수 있어?"

실제로 그랬다. 이번 세션에 넣은 키워드들의 정답셋 매칭이 1~4건이고, "탁월한"은 지표가
아예 안 움직였다(이미 다른 키워드로 잡히던 문장이라). "탁월한"이 빠져 있던 것도 우연히
발견한 것이지, 그런 누락이 몇 개 더 있는지는 아무도 몰랐다.

이 도구는 반대 방향으로 본다. **정답셋을 안 본다.** 팩(`prohibited_expressions.md`)이
명시한 표현을 전부 뽑아 규칙집(`judge_rules.json` + `synonyms.json`)과 대조해서,
팩에 있는데 규칙집에 없는 것을 나열한다. 표본과 무관하므로 과적합이 아니다.

VLM을 안 부른다(비용 0, 몇 초).

    ./venv/bin/python scripts/pack_coverage_audit.py

## 읽는 법

"미등재"로 나온다고 전부 규칙집에 넣어야 하는 건 아니다. 판단이 필요하다:
- 규칙집은 **키워드 매칭**이라 문맥이 필요한 표현은 애초에 VLM 영역이다
  (예: "기능성 심사된 효능효과 제외" 같은 조건부 표현).
- 일반 단어와 겹치는 표현은 오탐을 낸다(예: 맨 "모공"은 해부학적 서술에 걸린다).
- 그래서 이 목록은 **후보**지 할 일 목록이 아니다. 각 건은 여전히 rule_sweep으로
  오탐을 확인하고 채택/기각한다.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

from barum.reference.rules import _normalize  # noqa: E402

_PACK = Path(__file__).resolve().parents[2] / "reference" / "cosmetic_kr"
_PROHIBITED = _PACK / "prohibited_expressions.md"
_RULES = Path("src/barum/reference/data/judge_rules.json")
_SYNONYMS = Path("src/barum/reference/data/synonyms.json")

# 표현 셀에서 잘라낼 잡음. 괄호 주석·조건절은 표현 자체가 아니다.
_PAREN = re.compile(r"\([^)]*\)")
# "A·B·C" 가운뎃점과 "A, B" 콤마로 나열된다. 슬래시도 변형 구분자로 쓰인다.
_SPLIT = re.compile(r"[,·/]")


def _rule_terms() -> set[str]:
    """규칙집 + 동의어 사전에 등재된 모든 표현(정규화)."""
    terms: set[str] = set()
    rules = json.loads(_RULES.read_text(encoding="utf-8"))
    for bucket in ("violation", "needs_review", "legal_allow", "out_of_scope"):
        val = rules.get(bucket)
        if isinstance(val, dict):
            for kws in val.values():
                terms.update(kws)
        elif isinstance(val, list):
            terms.update(val)
    for canonical, variants in json.loads(
        _SYNONYMS.read_text(encoding="utf-8")
    )["synonyms"].items():
        terms.add(canonical)
        terms.update(variants)
    return {_normalize(t) for t in terms if t}


def _pack_expressions() -> list[tuple[str, str, str]]:
    """§1 표에서 (위반유형, 구분, 표현) 목록을 뽑는다.

    표 형식: | 위반유형 | 구분 | 금지표현/패턴 | 근거 | 비고·예외 |
    3번째 칸만 쓴다(비고·예외는 조건 설명이라 표현이 아니다).
    """
    out: list[tuple[str, str, str]] = []
    for line in _PROHIBITED.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("위반유형", "---"):
            continue
        vtype, kind, exprs = cells[0], cells[1], cells[2]
        if not vtype.startswith("T"):
            continue
        for raw in _SPLIT.split(_PAREN.sub("", exprs)):
            expr = raw.strip().strip("*").strip()
            # 너무 짧거나(조사 파편) 문장형(서술)인 건 키워드 후보가 아니다.
            if 2 <= len(expr) <= 20 and not expr.endswith("다"):
                out.append((vtype, kind, expr))
    return out


# 표에서 뽑히긴 하지만 **키워드 규칙 후보가 아닌** 것들. 표를 파싱해 얻은 조각이라
# 잡음이 섞인다 — 정제하지 않으면 "미등재 87건"이 실제보다 부풀어 보인다.
_PLACEHOLDER = re.compile(r"OO|○○|[nN]\s*[%감]")   # "OO 의사 개발" 같은 패턴형
_QUOTE_FRAGMENT = re.compile(r"['\"'']")            # "사용'" 처럼 따옴표에서 잘린 조각
# 위반유형 이름·설명어. 표현이 아니라 분류 라벨이다.
_CATEGORY_WORDS = {
    "그 밖의 거짓", "과장", "소비자 기만", "의약품 오인", "유기농 오인",
    "배타적 표현 등 세부 유형", "천연", "해결", "복구", "확대", "상처",
    "기타", "관절",
}


def _is_keyword_candidate(expr: str) -> bool:
    """키워드 규칙으로 넣어볼 만한 **구체 표현**인지 본다(정제).

    아닌 것: 플레이스홀더가 든 패턴("OO 병원 추천"), 따옴표에서 잘린 조각,
    위반유형 이름·설명어. 이런 건 규칙 키워드가 될 수 없거나 문맥 판단이 필요해
    VLM 영역이다. 이 판단은 보수적으로 한다 — 애매하면 후보로 남겨 사람이 본다.
    """
    if expr in _CATEGORY_WORDS:
        return False
    if _PLACEHOLDER.search(expr) or _QUOTE_FRAGMENT.search(expr):
        return False
    return True


def main() -> None:
    known = _rule_terms()
    exprs = _pack_expressions()
    missing_all = [(v, k, e) for v, k, e in exprs
                   if not any(_normalize(e) in t or t in _normalize(e) for t in known)]
    missing = [x for x in missing_all if _is_keyword_candidate(x[2])]
    filtered = [x for x in missing_all if not _is_keyword_candidate(x[2])]

    print(f"팩 §1에서 추출한 표현: {len(exprs)}건")
    print(f"규칙집·동의어에 등재됨: {len(exprs) - len(missing_all)}건")
    print(f"미등재(원): {len(missing_all)}건")
    print(f"  ├ 정제 제외(패턴형·조각·유형명): {len(filtered)}건")
    print(f"  └ **키워드 후보: {len(missing)}건** (할 일 목록이 아니다 — 아래 주의 참고)\n")

    by_type: dict[str, list[tuple[str, str]]] = {}
    for v, k, e in missing:
        by_type.setdefault(v, []).append((k, e))
    for vtype in sorted(by_type):
        print(f"[{vtype}] {len(by_type[vtype])}건")
        for kind, expr in by_type[vtype]:
            print(f"    {expr}   ({kind})")
        print()

    print("주의: 문맥이 필요한 표현은 규칙집이 아니라 VLM 영역이다. 일반 단어와 겹치면")
    print("오탐을 낸다(맨 '모공'이 해부학적 서술에 걸리던 사례). 각 건은 rule_sweep으로")
    print("오탐을 확인하고 채택/기각할 것.")


if __name__ == "__main__":
    main()
