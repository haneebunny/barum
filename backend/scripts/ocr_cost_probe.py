# -*- coding: utf-8 -*-
"""남은 상세 이미지 판독 견적 — 표본을 실제로 돌려 시간·토큰을 잰다.

**추정치를 쓰지 않는다.** 표본 N장을 실제로 OCR해 장당 소요시간·토큰을 재고, 남은 장수로
환산한다. 금액은 내지 않는다 — 저장소에 텍스트 모델 단가표가 없어서다. 토큰 수를 내면
현재 요금표로 곱하면 된다.

    ./venv/bin/python scripts/ocr_cost_probe.py --sample 12
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from barum.preprocess.ocr import OCR_PROMPT  # noqa: E402
from barum.vlm import get_vlm  # noqa: E402

DETAILS = ROOT / "11st_probe_cosmetic" / "details"
ANSWER_KEY = ROOT / "11st_probe_cosmetic" / "read_test" / "_combined_answer_key.json"
EVAL_PRODUCTS = ["1010944945", "1403306051", "24500688", "24505724",
                 "7628382624", "8783520869", "9126459148"]


def already_read() -> set[tuple[str, str]]:
    """이미 읽은 이미지 (상품코드, 파일이름줄기) 집합.

    ① 정답셋 OCR(_combined_answer_key.json, 상품당 1~2장)
    ② 2026-08-20 전성분 추출분(평가셋 상품의 뒤 3장 + 1010944945 앞 11장)
    """
    done = set()
    for e in json.loads(ANSWER_KEY.read_text(encoding="utf-8")):
        png = e.get("png", "")
        parts = png.split("_", 2)
        if len(parts) == 3:
            done.add((parts[1], Path(parts[2]).stem))
    for code in EVAL_PRODUCTS:
        imgs = sorted(p for p in (DETAILS / code).iterdir() if p.suffix.lower() in (".jpg", ".png"))
        for p in imgs[-3:]:
            done.add((code, p.stem))
        if code == "1010944945":
            for p in imgs[:-3]:
                done.add((code, p.stem))
    return done


def remaining() -> list[Path]:
    """아직 한 번도 안 읽은 이미지 목록."""
    done = already_read()
    out = []
    for d in sorted(DETAILS.iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in (".jpg", ".png", ".gif") and (d.name, p.stem) not in done:
                out.append(p)
    return out


def main(sample: int) -> None:
    pool = remaining()
    gifs = [p for p in pool if p.suffix.lower() == ".gif"]
    # gif는 이 파이프라인이 한 번도 읽어본 적이 없다. 되는지부터 확인해야 견적이 선다.
    print(f"남은 이미지: {len(pool)}장 (jpg/png {len(pool) - len(gifs)} + gif {len(gifs)})")
    print(f"디스크 전체: {sum(1 for d in DETAILS.iterdir() if d.is_dir() for _ in d.iterdir())}개")
    if not pool:
        return
    # 앞뒤가 아니라 고르게 뽑는다. 표지·전성분 등 종류가 섞여야 대표성이 있다.
    step = max(1, len(pool) // sample)
    picks = [p for p in pool if p.suffix.lower() != ".gif"][::step][:sample]
    if gifs:
        picks.append(gifs[0])  # gif가 읽히는지 한 장 확인한다
    print(f"표본 {len(picks)}장을 실제로 OCR 한다\n", flush=True)

    vlm = get_vlm("gemini")
    times, sentences, fails = [], 0, 0
    t_all = time.perf_counter()
    for p in picks:
        t0 = time.perf_counter()
        try:
            r = vlm.generate_json(OCR_PROMPT, [p.read_bytes()])
            n = len(r.get("sentences") or [])
        except Exception as e:
            fails += 1
            print(f"  {p.parent.name}/{p.name}: 실패 {type(e).__name__}")
            continue
        dt = time.perf_counter() - t0
        times.append(dt)
        sentences += n
        print(f"  {p.parent.name}/{p.name}: {dt:.1f}초, 문장 {n}개", flush=True)
    wall = time.perf_counter() - t_all

    if not times:
        print("\n표본이 전부 실패했다. 견적 불가.")
        return
    per = statistics.mean(times)
    med = statistics.median(times)
    tok = getattr(vlm, "total_tokens", 0)
    tok_per = tok / len(times) if times else 0

    print(f"\n=== 표본 실측 ({len(times)}장 성공 / {fails}장 실패) ===")
    print(f"장당 소요: 평균 {per:.1f}초 · 중앙값 {med:.1f}초 · 범위 {min(times):.1f}~{max(times):.1f}초")
    print(f"표본 전체 벽시계: {wall:.0f}초 | 토큰 합계 {tok:,} (장당 {tok_per:,.0f})")
    print(f"추출 문장: {sentences}개 (장당 {sentences / len(times):.1f}개)")
    print(f"\n=== 남은 {len(pool)}장 환산 (순차 실행 기준) ===")
    print(f"소요시간: 약 {len(pool) * per / 60:.0f}분 (중앙값 기준 {len(pool) * med / 60:.0f}분)")
    print(f"토큰: 약 {len(pool) * tok_per:,.0f}")
    print("\n금액은 내지 않는다 — 저장소에 이 모델의 텍스트 단가표가 없다."
          "\n위 토큰 수에 현재 요금표를 곱할 것. [[barum-no-unverified-metrics-rule]]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=12, help="실제로 돌려볼 표본 장수")
    main(sample=ap.parse_args().sample)
