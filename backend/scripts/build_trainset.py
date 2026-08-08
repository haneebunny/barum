"""prescreen 결과에서 학생 DL 학습셋을 만든다.

prescreen의 keep=true 문장과 VLM hint 라벨에, 원 OCR에서 주변 문맥을 붙여
학습셋 jsonl을 만든다. 평가 홀드아웃 상품은 제외한다(데이터 누수 방지).

입력: data/prescreen.jsonl, data/ocr_sentences*.jsonl, data/holdout_master_v1.jsonl
출력: data/trainset.jsonl (학생 KoELECTRA 학습 입력)
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRESCREEN = DATA / "prescreen.jsonl"
HOLDOUT = DATA / "holdout_master_v1.jsonl"
OUT = DATA / "trainset.jsonl"

LABELS = {
    "합법", "1호_질병표방", "2호_의약품오인", "3호_건기식오인",
    "4호_거짓과장", "5호_소비자기만", "대상외",
}


def load_holdout_products() -> set[str]:
    """평가 홀드아웃에 쓰인 상품 id. 학습셋에서 빼야 누수가 없다."""
    ids = set()
    for line in HOLDOUT.open(encoding="utf-8"):
        line = line.strip()
        if line:
            ids.add(str(json.loads(line)["product_id"]))
    return ids


def load_ocr_by_product() -> dict[str, dict[int, str]]:
    """상품별 전체 OCR 문장(order → text). 문맥 윈도우 구성용.

    OCR은 샤드로 갈라져 있어 모두 읽고, 비어 있지 않은 레코드를 우선한다.
    """
    by_prod: dict[str, dict[int, str]] = {}
    for p in sorted(DATA.glob("ocr_sentences*.jsonl")):
        for line in p.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            pid = str(o["product_id"])
            sents = o.get("sentences") or []
            if sents and (pid not in by_prod or not by_prod[pid]):
                by_prod[pid] = {s["order"]: s["text"] for s in sents}
    return by_prod


def build():
    """prescreen을 학습셋 jsonl로 변환하고 클래스 분포를 출력한다."""
    holdout = load_holdout_products()
    ocr = load_ocr_by_product()

    n = 0
    excluded_products = set()
    dist = Counter()
    with OUT.open("w", encoding="utf-8") as out:
        for line in PRESCREEN.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            pid = str(rec["product_id"])
            if pid in holdout:
                excluded_products.add(pid)
                continue
            order_map = ocr.get(pid, {})
            for s in rec.get("sentences", []):
                label = s.get("hint")
                if label not in LABELS:
                    label = "합법"  # 힌트 없거나 이상하면 합법(보수적)
                order = s.get("order")
                ctx_b = order_map.get(order - 1) if order is not None else None
                ctx_a = order_map.get(order + 1) if order is not None else None
                out.write(json.dumps({
                    "product_id": pid,
                    "sentence": s["text"],
                    "context_before": ctx_b,
                    "context_after": ctx_a,
                    "label": label,
                    "source": "vlm_hint",
                }, ensure_ascii=False) + "\n")
                n += 1
                dist[label] += 1

    print(f"학습셋 문장: {n}  (holdout 상품 {len(excluded_products)}개 제외)")
    print("클래스 분포:")
    for label, cnt in dist.most_common():
        print(f"  {label:14}: {cnt:>5}  ({cnt / n * 100:.1f}%)")
    print(f"출력: {OUT}")


if __name__ == "__main__":
    build()
