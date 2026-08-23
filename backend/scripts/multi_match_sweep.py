"""문장당 전체 매칭(match_all_rules) 도입 전후를 정답셋으로 잰다. **API 비용 0.**

무엇을 재나. 예전 `match_rule`은 문장당 첫 매칭 하나만 냈다. 한 문장에 위반이
여러 개면 하나만 지적됐다는 뜻이다(미탐). `match_all_rules`는 같은 갈래 안의
매칭을 전부 낸다. 이 스크립트는 그 변경이 **지적 건수**와 **오탐**에 각각 어떻게
작용하는지 정답셋 라벨별로 나눠 센다.

오탐이 핵심이다. 미탐을 줄이려다 합법·대상외 문장에 지적이 늘면 셈이 안 맞는다.

사용:
    cd backend && venv/bin/python scripts/multi_match_sweep.py --before /tmp/sweep_before.json
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

import compare_ocr  # noqa: E402

from barum.reference.rules import match_all_rules, match_rule  # noqa: E402

_DEFAULT_LABEL_XLSX = Path("11st_probe_cosmetic/read_test/label_worksheet_combined.xlsx")
# 지적이 뜨면 안 되는 라벨. 여기에 늘어난 건수가 곧 오탐 증가다.
_SAFE_LABELS = ("합법", "대상외")
_FLAGGING = ("violation", "needs_review")


def run(label_xlsx: Path, before_path: Path | None) -> dict:
    key = compare_ocr.load_answer_key(label_xlsx=label_xlsx)
    before = json.loads(before_path.read_text(encoding="utf-8")) if before_path else {}

    old_total = new_total = 0
    by_label_old: Counter = Counter()
    by_label_new: Counter = Counter()
    multi_by_label: Counter = Counter()
    span_changed: list[dict] = []
    examples: list[dict] = defaultdict(list)
    n_sentences = 0

    for nn, rows in key.items():
        for row in rows:
            sentence = (row.get("sentence") or "").strip()
            if not sentence:
                continue
            n_sentences += 1
            label = row.get("judgment") or "?"

            first = match_rule(sentence)
            allm = match_all_rules(sentence)
            # 지적이 되는 건 violation·needs_review뿐이다(합법·대상외는 finding 없음).
            old_n = 1 if first and first.outcome.value in _FLAGGING else 0
            new_n = sum(1 for m in allm if m.outcome.value in _FLAGGING)

            old_total += old_n
            new_total += new_n
            by_label_old[label] += old_n
            by_label_new[label] += new_n
            if new_n >= 2:
                multi_by_label[label] += 1
                if len(examples[label]) < 3:
                    examples[label].append(
                        {"sentence": sentence[:70], "spans": [m.span for m in allm]}
                    )

            # 기존 스냅샷과 대조해 outcome·span이 바뀐 문장을 잡는다.
            prev = before.get(f"{nn}||{sentence}")
            if prev:
                _, prev_outcome, prev_span = prev
                now_outcome = first.outcome.value if first else "none"
                now_span = first.span if first else ""
                if (prev_outcome, prev_span) != (now_outcome, now_span):
                    span_changed.append(
                        {
                            "sentence": sentence[:60],
                            "before": [prev_outcome, prev_span],
                            "after": [now_outcome, now_span],
                        }
                    )

    unsafe_old = sum(by_label_old[lab] for lab in _SAFE_LABELS)
    unsafe_new = sum(by_label_new[lab] for lab in _SAFE_LABELS)
    return {
        "n_sentences": n_sentences,
        "findings_before": old_total,
        "findings_after": new_total,
        "by_label_before": dict(by_label_old),
        "by_label_after": dict(by_label_new),
        "multi_match_sentences": dict(multi_by_label),
        # 합법·대상외에 붙은 지적 = 오탐. 이 수치가 늘면 변경을 재고해야 한다.
        "false_positive_before": unsafe_old,
        "false_positive_after": unsafe_new,
        "outcome_or_span_changed": span_changed,
        "examples": {k: v for k, v in examples.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label-xlsx", type=Path, default=_DEFAULT_LABEL_XLSX)
    ap.add_argument("--before", type=Path, default=None, help="rule_sweep snapshot(json)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    r = run(args.label_xlsx, args.before)
    print(f"문장 {r['n_sentences']}건")
    print(f"지적 건수: {r['findings_before']} → {r['findings_after']} "
          f"({r['findings_after'] - r['findings_before']:+d})")
    print(f"오탐(합법·대상외에 붙은 지적): {r['false_positive_before']} → {r['false_positive_after']} "
          f"({r['false_positive_after'] - r['false_positive_before']:+d})")
    print(f"매칭 2건 이상인 문장: {sum(r['multi_match_sentences'].values())}건 "
          f"{dict(r['multi_match_sentences'])}")
    print(f"outcome·span 바뀐 문장: {len(r['outcome_or_span_changed'])}건")
    print("\n라벨별 지적 건수")
    for lab in sorted(set(r["by_label_before"]) | set(r["by_label_after"])):
        b, a = r["by_label_before"].get(lab, 0), r["by_label_after"].get(lab, 0)
        mark = "  ←" if b != a else ""
        print(f"  {lab:6} {b:4} → {a:4}{mark}")

    if args.out:
        args.out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n저장: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
