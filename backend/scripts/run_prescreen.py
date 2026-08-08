"""OCR 결과를 선별한다 — 정제 + product_type + 유형 힌트.

실행: venv/bin/python scripts/run_prescreen.py
출력: data/prescreen.jsonl (내부용 — 라벨러에게 주지 않는다)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vericops.judge.prescreen import prescreen_product  # noqa: E402
from vericops.vlm import get_vlm  # noqa: E402

IN_PATH = Path("data/ocr_sentences.jsonl")
OUT_PATH = Path("data/prescreen.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpm", type=int, default=14)
    ap.add_argument("--model", help="모델 오버라이드(2차 재판정용 다른 모델)")
    ap.add_argument("--out", help="출력 경로")
    args = ap.parse_args()

    global OUT_PATH
    if args.out:
        OUT_PATH = Path(args.out)

    # OCR은 샤드로 갈라져 실행되므로 ocr_sentences*.jsonl을 모두 읽는다.
    merged: dict[str, dict] = {}
    for path in sorted(Path("data").glob("ocr_sentences*.jsonl")):
        for line in open(path):
            if line.strip():
                rec = json.loads(line)
                prev = merged.get(rec["product_id"])
                if prev and prev["sentences"] and not rec["sentences"]:
                    continue
                merged[rec["product_id"]] = rec
    records = [r for r in merged.values() if r["sentences"]]

    done = set()
    if OUT_PATH.exists():
        done = {json.loads(l)["product_id"] for l in open(OUT_PATH) if l.strip()}
        print(f"[이어하기] 이미 선별된 상품 {len(done)}개")
    todo = [r for r in records if r["product_id"] not in done]

    vlm = get_vlm("gemini", model=args.model, rpm=args.rpm)
    print(f"=== 선별 대상 {len(todo)}개 상품 (모델 {vlm.model}) ===\n", flush=True)

    for i, rec in enumerate(todo, 1):
        try:
            out = prescreen_product(rec, vlm)
        except Exception as e:
            # 예상된 실패는 상품 단위로 스킵. 재시도하지 않는다.
            print(f"[{i}/{len(todo)}] {rec['product_id']} [skip] "
                  f"{type(e).__name__}: {str(e)[:120]}", flush=True)
            continue
        with open(OUT_PATH, "a") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(todo)}] {out['product_id']} — {out['product_type']} "
              f"| {out['n_input']}→{out['n_kept']}문장 "
              f"| {out['product_type_evidence'][:50]}", flush=True)

    print(f"\n=== 완료. 누적 토큰 {vlm.total_tokens:,} → {OUT_PATH} ===")


if __name__ == "__main__":
    main()
