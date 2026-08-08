"""수집된 타일에서 문장을 추출해 JSONL로 쌓는다 (홀드아웃 원재료).

실행: venv/bin/python scripts/run_ocr.py --max-products 40
이미 처리한 상품은 건너뛰므로 중단 후 이어서 돌려도 된다.
"""

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vericops.preprocess.ocr import extract_product_sentences  # noqa: E402
from vericops.vlm import get_vlm  # noqa: E402

DETAILS_DIR = Path("11st_output/details")
OUT_PATH = Path("data/ocr_sentences.jsonl")

# 식품이 아닌 상품(운동기구 등)은 부당광고 판정 대상이 아니라 제외한다.
NON_FOOD_KEYWORDS = [
    # 운동기구
    "점프박스", "워킹머신", "러닝머신", "스텝퍼", "홈트", "덤벨", "줄넘기",
    "마사지", "롤러", "복대", "벨트", "체중계", "훌라후프", "역도", "그립",
    # 주방·잡화 (검색어 "붓기차"·"체중감량 차"가 끌어옴)
    "거름망", "드립퍼", "냄비", "접시", "주전자", "티팟", "커피 메이커",
    "카트리지", "필터", "트레이", "글라스",
    # 서적 (검색어 "위고비"·"GLP-1"이 끌어옴)
    "요리책", "가이드 및", "상담 -",
]


def load_product_meta() -> dict[str, dict]:
    """매니페스트들에서 상품코드 → {name, seller} 를 모은다."""
    meta = {}
    for f in glob.glob("11st_output/11st_details_*.json"):
        for p in json.load(open(f)).get("products", []):
            meta[p["product_code"]] = {
                "product_name": p.get("product_name", ""),
                "seller": p.get("seller", ""),
            }
    return meta


def select_products(meta: dict, max_products: int, per_seller: int) -> list[str]:
    """타일이 있는 식품 상품을 셀러별로 고르게 뽑는다.

    같은 셀러의 상품은 상세페이지가 비슷해 문장이 겹치므로 셀러당 상한을 둔다.
    """
    codes = sorted(
        c for c in (p.name for p in DETAILS_DIR.iterdir() if p.is_dir())
        if (DETAILS_DIR / c / "tiles").is_dir()
    )
    picked, by_seller = [], defaultdict(int)
    skipped_nonfood = []

    for code in codes:
        name = meta.get(code, {}).get("product_name", "")
        if any(k in name for k in NON_FOOD_KEYWORDS):
            skipped_nonfood.append(f"{code} {name[:40]}")
            continue
        seller = meta.get(code, {}).get("seller", "?")
        if by_seller[seller] >= per_seller:
            continue
        by_seller[seller] += 1
        picked.append(code)
        if len(picked) >= max_products:
            break

    if skipped_nonfood:
        print(f"[제외] 식품 아님 {len(skipped_nonfood)}건")
        for s in skipped_nonfood:
            print(f"  - {s}")
    return picked


def load_existing(all_shards: bool = False) -> dict[str, dict]:
    """기존 JSONL을 상품코드 → 레코드로 읽는다(같은 상품이 여러 번이면 마지막 것).

    all_shards=True면 병렬 실행으로 갈라진 `ocr_sentences*.jsonl`을 모두 읽는다.
    """
    paths = (
        sorted(Path("data").glob("ocr_sentences*.jsonl")) if all_shards
        else ([OUT_PATH] if OUT_PATH.exists() else [])
    )
    out = {}
    for path in paths:
        with open(path) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    # 문장이 있는 결과를 빈 결과로 덮어쓰지 않는다.
                    prev = out.get(rec["product_id"])
                    if prev and prev["sentences"] and not rec["sentences"]:
                        continue
                    out[rec["product_id"]] = rec
    return out


def compact(records: dict[str, dict]) -> None:
    """append로 쌓인 중복 레코드를 상품당 1줄로 정리해 다시 쓴다."""
    with open(OUT_PATH, "w") as f:
        for code in sorted(records):
            f.write(json.dumps(records[code], ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-products", type=int, default=40)
    ap.add_argument("--per-seller", type=int, default=3)
    ap.add_argument("--codes", nargs="*", help="특정 상품코드만 처리")
    ap.add_argument("--rpm", type=int, default=15, help="분당 요청 상한(무료 티어 15)")
    ap.add_argument("--model", help="모델 오버라이드(.env MODEL_NAME 대신)")
    ap.add_argument("--out", help="출력 JSONL 경로(병렬 실행 시 분리)")
    ap.add_argument("--shard", type=int, default=0, help="대상 목록을 나눌 때 이 조각만 처리")
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--batch", type=int, default=4,
                    help="한 요청에 넣을 타일 수(1이면 타일당 1회 호출)")
    args = ap.parse_args()

    global OUT_PATH
    if args.out:
        OUT_PATH = Path(args.out)

    meta = load_product_meta()
    # 타일이 하나라도 실패한 상품은 '완료'로 치지 않는다 — 429로 통째로 비었을 수 있다.
    existing = load_existing(all_shards=True)
    done = {c for c, e in existing.items() if not e["tiles_failed"]}
    if existing:
        print(f"[이어하기] 완료 {len(done)}개 / 재처리 대상 {len(existing) - len(done)}개")

    targets = args.codes or select_products(meta, args.max_products, args.per_seller)
    targets = [c for c in targets if c not in done]
    if args.shards > 1:
        targets = targets[args.shard::args.shards]
    print(f"\n=== OCR 대상 상품 {len(targets)}개 ===\n", flush=True)

    vlm = get_vlm("gemini", model=args.model, rpm=args.rpm)
    print(f"모델: {vlm.model} (throttle {args.rpm} RPM)\n", flush=True)

    OUT_PATH.parent.mkdir(exist_ok=True)
    total_sent = 0
    for i, code in enumerate(targets, 1):
        info = meta.get(code, {})
        print(f"[{i}/{len(targets)}] {code} — {info.get('product_name','')[:50]}")
        result = extract_product_sentences(
            DETAILS_DIR / code, vlm, batch_size=args.batch)
        result.update(info)
        with open(OUT_PATH, "a") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
        total_sent += len(result["sentences"])
        print(f"  → {len(result['sentences'])}문장 "
              f"(타일 {result['tiles_ok']}장 성공, {len(result['tiles_failed'])}장 실패)\n")

    compact(load_existing())  # 자기 샤드 파일만 정리(다른 샤드와 섞지 않는다)
    print(f"=== 완료: 상품 {len(targets)}개 / 문장 {total_sent}개 ===")
    print(f"누적 토큰: {vlm.total_tokens:,}")
    print(f"출력: {OUT_PATH}")


if __name__ == "__main__":
    main()
