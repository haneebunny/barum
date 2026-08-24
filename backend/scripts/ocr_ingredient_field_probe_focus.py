# -*- coding: utf-8 -*-
"""문단형 회귀 타일(24500688/detail_003.jpg) 집중 반복 측정.

ocr_ingredient_field_probe.py 1·2차 측정에서 이 타일만 흔들렸다:
  1차(n=1): 베이스라인 13 / 후보 13 (일치)
  2차(n=2): 베이스라인 13·(파싱실패) / 후보 11·12 (후보가 낮게 나옴)
편차인지 진짜 효과인지 3회 더 돌려 범위로 판단한다. 이번엔 문장 개수뿐 아니라
**어떤 문장이 빠지는지**까지 diff해서 원인을 본다.

    ./venv/bin/python scripts/ocr_ingredient_field_probe_focus.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barum.vlm import get_vlm  # noqa: E402
from ocr_ingredient_field_probe import (  # noqa: E402
    CANDIDATE_PROMPT,
    DETAILS,
    run,
    summarize_sentences,
)
from barum.preprocess.ocr import OCR_PROMPT  # noqa: E402

TILE = DETAILS / "24500688" / "detail_003.jpg"
REPS = 3

# 앞선 1·2차 측정에서 이미 확보한 값(재호출 안 함, 그대로 합산).
PRIOR_BASE = [13, 13]  # 1차 rep1=13, 2차 rep1=13 (2차 rep2는 파싱실패라 값 없음)
PRIOR_CAND = [13, 11, 12]  # 1차 rep1=13, 2차 rep1=11, rep2=12


def main() -> None:
    vlm = get_vlm("gemini")
    base_runs: list[list[str]] = []
    cand_runs: list[list[str]] = []

    for rep in range(1, REPS + 1):
        print(f"\n--- rep {rep} ---")
        try:
            base = run(TILE, OCR_PROMPT, vlm)
            base_s = summarize_sentences(base.get("sentences") or [])
            base_runs.append(base_s)
            print(f"베이스라인 {len(base_s)}문장")
        except Exception as e:
            print(f"  [skip] 베이스라인 실패: {type(e).__name__}: {e}")

        try:
            cand = run(TILE, CANDIDATE_PROMPT, vlm)
            cand_s = summarize_sentences(cand.get("sentences") or [])
            cand_runs.append(cand_s)
            print(f"후보 {len(cand_s)}문장")
        except Exception as e:
            print(f"  [skip] 후보 실패: {type(e).__name__}: {e}")

    print(f"\n{'=' * 70}\n종합 (1·2차 기존 측정값 포함)\n{'=' * 70}")
    all_base_n = PRIOR_BASE + [len(s) for s in base_runs]
    all_cand_n = PRIOR_CAND + [len(s) for s in cand_runs]
    print(f"베이스라인 문장수 전체: {all_base_n} (n={len(all_base_n)}, "
          f"범위 {min(all_base_n)}~{max(all_base_n)})")
    print(f"후보 문장수 전체:     {all_cand_n} (n={len(all_cand_n)}, "
          f"범위 {min(all_cand_n)}~{max(all_cand_n)})")

    overlap = not (max(all_base_n) < min(all_cand_n) or max(all_cand_n) < min(all_base_n))
    print(f"범위 겹침: {'예 (효과 미입증)' if overlap else '아니오 (효과 있음 가능성)'}")

    # 이번 3회 중 가장 짧은 후보 결과와 베이스라인 하나를 골라 실제로 뭐가 빠졌는지 본다.
    if base_runs and cand_runs:
        b = set(base_runs[0])
        c = set(cand_runs[-1])
        print(f"\n[내용 대조] 이번 rep1 베이스라인 vs 이번 마지막 후보")
        print(f"베이스라인에만 있음({len(b - c)}건):")
        for t in b - c:
            print(f"  - {t}")
        print(f"후보에만 있음({len(c - b)}건):")
        for t in c - b:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
