# -*- coding: utf-8 -*-
"""평가셋 상품의 전성분·기능성 표시를 상세 이미지에서 뽑는다.

**새로 크롤하지 않는다.** `11st_probe_cosmetic/details/`에 이미 받아둔 이미지 301장 중
OCR된 건 53장뿐이고 248장은 한 번도 읽은 적이 없다(로그 ㉑-2). 전성분 라벨은 보통 상세
페이지 끝에 있어 뒤쪽부터 훑는다.

    ./venv/bin/python scripts/extract_eval_ingredients.py --last 3
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from barum.vlm import get_vlm  # noqa: E402

DETAILS = ROOT / "11st_probe_cosmetic" / "details"
OUT = ROOT / "data" / "eval_ingredients.json"

# 평가셋(ver2 골드셋 42문장)이 나온 상품 7개.
EVAL_PRODUCTS = ["1010944945", "1403306051", "24500688", "24505724",
                 "7628382624", "8783520869", "9126459148"]

PROMPT = """이 이미지는 한국 화장품 상품 상세페이지의 일부다. 아래 세 가지만 찾아라.

1. **전성분 목록** — "전성분:" 또는 성분명이 쉼표로 길게 나열된 부분. 원문 그대로,
   쉼표로 구분해 순서대로 옮긴다. 읽기 어려운 글자는 건너뛰지 말고 읽을 수 있는 만큼 옮긴다.
2. **성분 함량 표기** — 성분명 옆 괄호나 표에 %가 붙은 것(예: "약모밀추출물(77%)").
3. **기능성화장품 표시** — "기능성화장품", "주름개선", "미백", "자외선차단" 표기,
   효능·효과 문장, 효능성분, 심사·보고 관련 서류 이미지의 내용.

없으면 빈 값으로 둔다. **지어내지 마라.**

JSON으로만 답하라:
{"ingredients_raw": "전성분 원문 전체 또는 빈 문자열",
 "amounts": [{"name": "성분명", "amount": "77%"}],
 "functional": "기능성 관련 표기를 한 줄로 요약, 없으면 빈 문자열"}"""


def main(last: int) -> None:
    vlm = get_vlm("gemini")
    print(f"OCR provider=gemini model={getattr(vlm, 'model', '?')} | 상품당 뒤에서 {last}장", flush=True)
    out = {}
    if OUT.exists():
        out = json.loads(OUT.read_text(encoding="utf-8"))

    for code in EVAL_PRODUCTS:
        d = DETAILS / code
        imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in (".jpg", ".png"))
        targets = imgs[-last:]
        found = out.get(code, {"ingredients_raw": "", "amounts": [], "functional": "", "sources": []})
        print(f"\n[{code}] 이미지 {len(imgs)}장 중 뒤 {len(targets)}장 확인", flush=True)
        for p in targets:
            try:
                r = vlm.generate_json(PROMPT, [p.read_bytes()])
            except Exception as e:
                # 과금 호출은 재시도하지 않는다. 실패로 기록하고 넘어간다.
                print(f"  {p.name}: 실패 {type(e).__name__}: {e}", flush=True)
                continue
            raw = (r.get("ingredients_raw") or "").strip()
            fn = (r.get("functional") or "").strip()
            amts = r.get("amounts") or []
            mark = []
            if len(raw) > len(found["ingredients_raw"]):
                found["ingredients_raw"] = raw; mark.append(f"전성분 {len(raw)}자")
            if amts and not found["amounts"]:
                found["amounts"] = amts; mark.append(f"함량 {len(amts)}건")
            if fn and len(fn) > len(found["functional"]):
                found["functional"] = fn; mark.append("기능성표시")
            if mark:
                found.setdefault("sources", []).append(p.name)
            print(f"  {p.name}: {', '.join(mark) if mark else '해당 없음'}", flush=True)
        out[code] = found

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    have = sum(1 for v in out.values() if v.get("ingredients_raw"))
    print(f"\n저장: {OUT}")
    print(f"전성분 확보: {have}/{len(EVAL_PRODUCTS)} 상품")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=3, help="상품당 뒤에서 몇 장을 볼지")
    main(last=ap.parse_args().last)
