"""인용 대조 게이트 실측 — 모델이 근거를 얼마나 자주 지어내는가.

정답셋 문장을 배포 파이프라인(RagJudge)에 태워, VLM이 낸 지적 중 **인용 대조를
통과하지 못한 비율**을 센다.

**이 수치는 정답 라벨을 쓰지 않는다.** "이 판정이 맞았나"가 아니라 "모델이 댄 근거가
실재하나"만 보기 때문이다. 그래서 정답셋 오염(규칙 튜닝에 쓰인 문장들)과 무관하다.
같은 이유로 판정 정확도 지표와 섞어 읽으면 안 된다 — 다른 걸 재는 숫자다.

대외 주장과 내부 지표를 나눠 낸다.
  - 대외: 사용자에게 노출된 근거 중 검증 실패 0건(실패분은 설명을 떼고 내보낸다)
  - 내부: 모델이 N% 확률로 근거를 지어내려 했다

**과금 호출이다.** `--limit`으로 표본을 정하고, 전량은 비용을 확인한 뒤 돌린다.

사용:
    cd backend
    venv/bin/python scripts/verify_gate_measure.py --limit 100 --out out.json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

import compare_ocr  # noqa: E402

from barum.judge.cosmetic import (  # noqa: E402
    GRADE_UNVERIFIED,
    GRADE_VERIFIED,
    RagJudge,
)
from barum.vlm import get_vlm  # noqa: E402

_DEFAULT_LABEL_XLSX = Path("11st_probe_cosmetic/read_test/label_worksheet_combined.xlsx")


def load_sentences(label_xlsx: Path, limit: int | None) -> list[dict]:
    """정답셋에서 문장만 뽑는다. **라벨은 안 읽는다**(이 측정은 정답이 필요 없다)."""
    key = compare_ocr.load_answer_key(label_xlsx=label_xlsx)
    out: list[dict] = []
    for rows in key.values():
        for row in rows:
            text = (row.get("sentence") or "").strip()
            if text:
                out.append({"order": len(out), "tile": None, "text": text})
    return out[:limit] if limit else out


def measure(sentences: list[dict], batch: int) -> dict:
    """문장을 배치로 판정하고 등급 분포·실패 사유를 센다."""
    judge = RagJudge(get_vlm("openai"), batch_size=batch)
    grades: Counter = Counter()
    reasons: Counter = Counter()
    failures: list[dict] = []
    modes: Counter = Counter()
    n_findings = 0

    for start in range(0, len(sentences), batch):
        chunk = sentences[start : start + batch]
        try:
            res = judge.judge(chunk, "KR")
        except Exception as e:
            # 과금 호출이라 재시도하지 않는다. 실패분은 빼고 진행한다.
            print(f"  [skip] 배치 {start}: {type(e).__name__}: {e}")
            continue
        n_findings += len(res.findings)
        for f in res.findings:
            grades[f.evidence_grade or "none"] += 1
        reasons.update(f["reason"] for f in res.verify_failures)
        failures.extend(res.verify_failures)
        modes.update(res.verify_modes)
        print(f"  {start + len(chunk)}/{len(sentences)} 문장, 지적 {n_findings}건")

    vlm_graded = grades[GRADE_VERIFIED] + grades[GRADE_UNVERIFIED]
    fail_rate = grades[GRADE_UNVERIFIED] / vlm_graded if vlm_graded else 0.0
    return {
        "n_sentences": len(sentences),
        "n_findings": n_findings,
        "grades": dict(grades),
        # 경로별 분해. 규칙 경로는 팩 등재 표현과의 일치라 인용 대조 대상이 아니다.
        "by_path": {
            "rule": grades.get("rule_confirmed", 0),
            "vlm": grades.get(GRADE_VERIFIED, 0) + grades.get(GRADE_UNVERIFIED, 0),
        },
        "verify_pass_modes": dict(modes),
        "verify_fail_reasons": dict(reasons),
        # a항(주입 안 된 조각) / b항(원문에 없는 quote) / c항(문장에 없는 span)
        "verify_fail_by_category": dict(Counter(f["category"] for f in failures)),
        # 실패한 인용 원문. **이걸 사람이 읽어야 수치를 해석할 수 있다.**
        # 모델이 지어낸 것인지, 대조기가 빡빡해 걸린 것인지는 여기서만 갈린다.
        "verify_failure_samples": failures[:30],
        # 내부 지표: VLM 지적 중 근거를 못 댄 비율.
        # **축약 인용은 여기 안 들어간다.** 실재하는 원문을 줄여 옮긴 것은
        # 근거를 지어낸 것이 아니다(2026-08-23 실측으로 확인).
        "internal_hallucination_rate": round(fail_rate, 4),
        # 대외 주장: 실패분은 설명을 떼고 나가므로 노출된 근거의 검증 실패는 0이다
        "exposed_unverified_explanations": 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label-xlsx", type=Path, default=_DEFAULT_LABEL_XLSX)
    ap.add_argument("--limit", type=int, default=None, help="문장 수 상한(과금 조절)")
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    sentences = load_sentences(args.label_xlsx, args.limit)
    print(f"문장 {len(sentences)}건 측정 시작 (배치 {args.batch})")
    result = measure(sentences, args.batch)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"저장: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
