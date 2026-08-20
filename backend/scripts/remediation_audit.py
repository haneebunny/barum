# -*- coding: utf-8 -*-
"""대체표현 조건표 자가감사. 조건표가 내놓는 제안을 규칙집에 대조한다.

정답셋을 안 본다. 조건표(`remediation_rules.json`)와 규칙집(`judge_rules.json`)만
대조하므로 API 비용이 0이고 in-sample 문제가 없다. `pack_coverage_audit.py`와 같은 계열.

    ./venv/bin/python scripts/remediation_audit.py

낸다:
  1) 위반으로 걸리는 제안 (코드 게이트가 막지만 조건표에서 빼는 게 맞다)
  2) 검토필요로 걸리는 제안 (막을지 말지 판단 필요, 지금은 통과시킨다)
  3) 자기 트리거 키워드를 품은 제안 (치환해도 그 키워드가 원문에 남는다)
"""

import json
from pathlib import Path

from barum.reference.remediation import DATA_PATH
from barum.reference.rules import RuleOutcome, match_rule


def main() -> None:
    data = json.loads(Path(DATA_PATH).read_text(encoding="utf-8"))

    entries = []  # (출처, 유형, 키워드들, 순번, 제안)
    for rule in data["rules"]:
        for i, sug in enumerate(rule["suggestions"]):
            entries.append(("rule", rule["violation_type"], rule["keywords"], i, sug))
    for vtype, sugs in data["fallbacks"].items():
        for i, sug in enumerate(sugs):
            entries.append(("fallback", vtype, [], i, sug))

    violations, needs_review, self_trigger = [], [], []
    for src, vtype, kws, i, sug in entries:
        # 실제로 치환에 쓰이는 건 게이트를 통과한 첫 후보다. 순번을 같이 보여준다.
        used = "  <- 1순위 후보" if i == 0 else ""
        m = match_rule(sug)
        if m is not None:
            if m.outcome is RuleOutcome.violation:
                violations.append(f"[{vtype}] {sug!r}{used}")
            elif m.outcome is RuleOutcome.needs_review:
                needs_review.append(f"[{vtype}] {sug!r}{used}")
        hit = [k for k in kws if k in sug]
        if hit:
            self_trigger.append(f"[{vtype}] {sug!r} ⊇ {hit}{used}")

    print(f"조건표 대체표현 {len(entries)}개 감사\n")

    print(f"1) 위반으로 걸리는 제안: {len(violations)}건")
    for line in violations:
        print(f"   {line}")
    print("   (코드 게이트가 막지만 조건표에서 빼는 게 맞다)\n")

    print(f"2) 검토필요로 걸리는 제안: {len(needs_review)}건")
    for line in needs_review:
        print(f"   {line}")
    print("   (실증자료가 있으면 합법이 되는 표현이라 지금은 통과시킨다. 막을지는 판단 필요)\n")

    print(f"3) 자기 트리거 키워드를 품은 제안: {len(self_trigger)}건")
    for line in self_trigger:
        print(f"   {line}")
    print("   (치환해도 그 키워드가 원문에 남아 같은 규칙에 다시 걸릴 수 있다)")


if __name__ == "__main__":
    main()
