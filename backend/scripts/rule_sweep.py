# -*- coding: utf-8 -*-
"""규칙집(judge_rules.json·synonyms.json) 변경의 영향을 정답셋 전체로 스윕한다.

`match_rule()`만 반복 호출하는 순수 로컬 연산이라 VLM을 안 부른다. 몇 초 안에
끝나고 API 비용이 0이다. 규칙집을 고칠 때마다 이 도구로 "기준 대비 뭐가
바뀌었는지"를 확인한다 — 스윕 없이 커밋했으면 "Pin"이 브랜드명 "Pintox"에
부분일치로 걸려 낸 오탐 4건을 아무도 몰랐을 것이다(2026-08-18, 실제 사고).

사용법(backend/에서):
  # 1. 규칙집을 고치기 "전" 상태를 기준선으로 저장한다.
  python scripts/rule_sweep.py snapshot --out /tmp/baseline.json

  # 2. judge_rules.json·synonyms.json을 고친다.

  # 3. 기준선과 비교해 뭐가 바뀌었는지 본다.
  python scripts/rule_sweep.py diff --baseline /tmp/baseline.json

정답셋은 기본으로 label_worksheet_combined.xlsx(H열 '제외사유' 반영 후 963문장)를 쓴다.
--label-file로 바꿀 수 있다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from barum.reference.rules import match_rule  # noqa: E402

sys.path.insert(0, "scripts")
import compare_ocr  # noqa: E402

_DEFAULT_LABEL_XLSX = Path("11st_probe_cosmetic/read_test/label_worksheet_combined.xlsx")

# compare_with_answer_key(compare_ocr.py)와 같은 정의. "위반"만 핵심지표,
# 나머지(합법·대상외)에 violation이 뜨면 규칙 오탐이다.
_VIOLATION_LABEL = "위반"
_SAFE_LABELS = ("합법", "대상외")

# 규칙이 legal_allow·out_of_scope로 확정하면 finding도 안 만들고 VLM에도 안 넘긴다
# (judge/cosmetic.py). 그래서 판단이 필요한 라벨이 여기 걸리면 통째로 사라지는데,
# tp(위반->violation)에도 fp(합법->violation)에도 안 잡혀 요약만 보면 안 보인다.
# "애매"는 tp·fp 어느 쪽 정의에도 안 들어가는 라벨이라 특히 잘 숨는다.
_SWALLOWING_OUTCOMES = ("legal_allow", "out_of_scope")
_NEEDS_JUDGMENT_LABELS = ("위반", "검토필요", "애매")


def run_sweep(label_xlsx: Path) -> dict[str, list]:
    """정답셋 전체에 match_rule을 돌린다.

    반환: {"이미지||문장": [정답라벨, 시스템outcome, 매칭span]}. outcome은
    RuleOutcome.value 문자열이거나 미매칭이면 "none".
    """
    key = compare_ocr.load_answer_key(label_xlsx=label_xlsx)
    out: dict[str, list] = {}
    for nn, rows in key.items():
        for row in rows:
            sentence = row["sentence"]
            if not sentence:
                continue
            m = match_rule(sentence)
            out[f"{nn}||{sentence}"] = [
                row["judgment"],
                m.outcome.value if m else "none",
                m.span if m else "",
            ]
    return out


def summarize(sweep: dict[str, list]) -> dict[str, int]:
    """정탐(위반->violation)·규칙오탐(합법/대상외->violation)·증발 건수를 센다.

    `tp`는 **규칙 단독 커버리지**다. 시스템 recall이 아니다 — 미매칭(`none`)은 증발이
    아니라 프리스크린·VLM으로 정상 위임되므로(judge/cosmetic.py), 여기 안 잡힌 위반을
    VLM이 잡을 수 있다. 시스템 성능은 RagJudge를 태워서 따로 재야 한다.

    `swallowed`는 판단이 필요한 라벨(위반·검토필요·애매)이 legal_allow·out_of_scope로
    확정돼 VLM에도 안 넘어간 건수다. tp에도 fp에도 안 잡히는 사각지대라 따로 센다.
    """
    tp = sum(1 for lab, out, _ in sweep.values() if lab == _VIOLATION_LABEL and out == "violation")
    total_violation = sum(1 for lab, _, _ in sweep.values() if lab == _VIOLATION_LABEL)
    fp = sum(1 for lab, out, _ in sweep.values() if lab in _SAFE_LABELS and out == "violation")
    swallowed = sum(
        1
        for lab, out, _ in sweep.values()
        if lab in _NEEDS_JUDGMENT_LABELS and out in _SWALLOWING_OUTCOMES
    )
    return {"tp": tp, "total_violation": total_violation, "fp": fp, "swallowed": swallowed}


def swallowed_rows(sweep: dict[str, list]) -> list[tuple[str, str, str, str]]:
    """증발한 문장을 (이미지, 정답라벨, 매칭span, 문장)으로 뽑는다. 요약 숫자의 내역."""
    rows = []
    for k, (lab, out, span) in sweep.items():
        if lab in _NEEDS_JUDGMENT_LABELS and out in _SWALLOWING_OUTCOMES:
            nn, sentence = k.split("||", 1)
            rows.append((nn, lab, span, sentence))
    return sorted(rows)


def compute_diff(baseline: dict[str, list], current: dict[str, list]) -> list[dict]:
    """두 스윕 결과를 비교해 outcome이 바뀐 문장만 뽑는다.

    문장 자체가 baseline/current 한쪽에만 있으면(정답셋이 바뀐 경우) 무시한다 —
    이 도구는 규칙집 변경의 영향만 본다, 정답셋 변경은 범위 밖이다.
    """
    changed = []
    for key, (lab, out1, span1) in baseline.items():
        if key not in current:
            continue
        _, out2, span2 = current[key]
        if out1 == out2:
            continue
        nn, sentence = key.split("||", 1)
        tag = _classify_change(lab, out1, out2)
        changed.append({
            "nn": nn, "sentence": sentence, "label": lab,
            "before": out1, "before_span": span1,
            "after": out2, "after_span": span2,
            "tag": tag,
        })
    return changed


def _classify_change(label: str, before: str, after: str) -> str:
    """바뀐 방향이 개선인지 악화인지 사람이 한눈에 보게 태그를 단다."""
    was_violation, is_violation = before == "violation", after == "violation"
    if label == _VIOLATION_LABEL:
        if is_violation and not was_violation:
            return "개선(위반 신규포착)"
        if was_violation and not is_violation:
            return "악화(위반 놓침)"
    elif label in _SAFE_LABELS:
        if is_violation and not was_violation:
            return "오탐신규"
        if was_violation and not is_violation:
            return "오탐해소"
    return ""


def cmd_snapshot(args: argparse.Namespace) -> None:
    sweep = run_sweep(Path(args.label_file))
    Path(args.out).write_text(json.dumps(sweep, ensure_ascii=False), encoding="utf-8")
    s = summarize(sweep)
    print(f"스냅샷 저장: {args.out} ({len(sweep)}문장)")
    print(f"  규칙 단독 위반탐지: {s['tp']}/{s['total_violation']} (시스템 recall 아님, 미매칭은 VLM행)")
    print(f"  규칙 오탐: {s['fp']}건")
    print(f"  증발(VLM에도 안 감): {s['swallowed']}건")
    if args.show_swallowed:
        for nn, lab, span, sentence in swallowed_rows(sweep):
            print(f"    [{nn}] 정답={lab} <- {span}: {sentence[:60]}")


def cmd_diff(args: argparse.Namespace) -> None:
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    current = run_sweep(Path(args.label_file))
    changed = compute_diff(baseline, current)

    sb, sc = summarize(baseline), summarize(current)
    print(f"규칙 단독 위반탐지: {sb['tp']}/{sb['total_violation']} -> {sc['tp']}/{sc['total_violation']}")
    print(f"규칙 오탐: {sb['fp']}건 -> {sc['fp']}건")
    print(f"증발(VLM에도 안 감): {sb['swallowed']}건 -> {sc['swallowed']}건")
    print(f"판정 바뀐 문장: {len(changed)}건\n")
    for c in changed:
        tag = f"  <== {c['tag']}" if c["tag"] else ""
        print(f"[{c['nn']}] 정답={c['label']:6} {c['before']}({c['before_span']}) "
              f"-> {c['after']}({c['after_span']}){tag}")
        print(f"      {c['sentence'][:70]}")

    if args.out:
        Path(args.out).write_text(
            json.dumps({"summary_before": sb, "summary_after": sc, "changed": changed},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n상세 결과 저장: {args.out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label-file", default=str(_DEFAULT_LABEL_XLSX), help="정답셋 xlsx 경로")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="현재 규칙집 상태를 스냅샷으로 저장")
    p_snap.add_argument("--out", required=True, help="스냅샷 저장 경로(json)")
    p_snap.add_argument("--show-swallowed", action="store_true",
                        help="증발한 문장 내역을 같이 출력")
    p_snap.set_defaults(func=cmd_snapshot)

    p_diff = sub.add_parser("diff", help="스냅샷 대비 지금 상태를 비교")
    p_diff.add_argument("--baseline", required=True, help="비교 기준 스냅샷 경로(json)")
    p_diff.add_argument("--out", default=None, help="상세 결과 저장 경로(선택, json)")
    p_diff.set_defaults(func=cmd_diff)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
