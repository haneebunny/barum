# -*- coding: utf-8 -*-
"""OCR 1차 추출 단계에 전성분 필드를 얹으면 어떻게 되는지 실측.

지금 `preprocess/ocr.py`의 OCR_PROMPT는 "광고 문구 문장"만 뽑는다. 전성분 패널은
문장 추출 대상도 아니고 별도 필드도 없어서, 이미지에 전성분표가 있어도
US 프리플라이트·국내 2호 판정 양쪽 다 "성분 정보 없음"으로 남는다(2026-08-24 발견).

1차 실측(상품 1개, n=1)에서 방향은 맞다는 신호가 나왔다. 이번엔 표기 방식이 서로
다른 상품 3개(문단형·스펙표형·영문 병사진형)로 넓히고, 조건당 2회씩 반복해 편차를
같이 본다. **n=2라 확정 근거는 아니다** — 이 프로젝트 규율상 3회 미만은 "관찰",
"증명"이 아니다.

이 스크립트는 파이프라인에 연결하지 않는다. **측정만** 한다(API 비용 발생).

    ./venv/bin/python scripts/ocr_ingredient_field_probe.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from barum.preprocess.ocr import OCR_PROMPT  # noqa: E402  (현재 프로덕션 프롬프트, 베이스라인)
from barum.vlm import get_vlm  # noqa: E402

DETAILS = ROOT / "11st_probe_cosmetic" / "details"
REPS = 2

# 후보 프롬프트: 현재 OCR_PROMPT 그대로 + ingredients 필드 추가.
# 성분 추출 문구는 scripts/extract_eval_ingredients.py의 검증된 표현을 그대로 가져왔다
# (2026-08-20 실측: 평가셋 상품 7개 중 6개에서 성분 복구 성공).
CANDIDATE_PROMPT = """이 이미지는 한국 이커머스 상품 상세페이지의 일부다.
이미지에 보이는 모든 한국어 텍스트를 위에서 아래 순서로 읽어라.

규칙:
- 광고 문구를 **문장 단위**로 끊어서 배열에 담는다.
- 반드시 각 문장마다 해당 문구가 위치한 2D 사각 영역(Bounding Box: [ymin, xmin, ymax, xmax], 0~1000 정규화 정수 좌표)을 `box_2d` 필드에 반드시 포함하라.
- 줄바꿈은 문장 구분이 아니다. 디자인상 줄이 나뉜 한 문장은 하나로 합쳐라.
- 가격·배송·교환/반품 안내·회사 주소·사업자번호 같은 거래 안내 문구는 제외한다.
- 원문 그대로 옮긴다. 맞춤법을 고치거나 표현을 다듬지 마라.
  (붙여쓰기·특수문자·초성 같은 회피표기도 원문 그대로 둔다)
- 읽을 수 없는 글자는 그 문장을 통째로 빼지 말고 읽을 수 있는 부분만 담는다.
- 한국어가 전혀 없으면 빈 배열을 반환한다.

추가로, 이미지에 **전성분 목록**(한국어 "전성분:" 표기, 영문 "Ingredients:" 표기,
또는 성분명이 쉼표로 길게 나열된 부분 어느 쪽이든)이 보이면 `ingredients_raw` 필드에
원문 그대로 쉼표로 구분해 옮긴다(문장 배열에는 넣지 않는다). 병 사진에 작게 인쇄된
경우도 포함한다. 없으면 빈 문자열로 둔다. **지어내지 마라.**

JSON 응답 형식 예시:
{"sentences": [{"text": "피부 깊숙이, 세포재생의 시작", "box_2d": [750, 150, 850, 850]}],
 "ingredients_raw": "정제수, 글리세린, 나이아신아마이드"}"""

CASES = [
    ("24500688/detail_003.jpg", "24500688/detail_010.jpg", "문단형(한글)"),
    ("1403306051/detail_005.jpg", "1403306051/detail_030.jpg", "스펙표형(한글, 라벨:값)"),
    ("24505724/detail_013.jpg", "24505724/detail_006.jpg", "영문 병사진형(작은 글씨)"),
]


def run(image_path: Path, prompt: str, vlm) -> dict:
    return vlm.generate_json(prompt, [image_path.read_bytes()])


def summarize_sentences(sentences: list) -> list[str]:
    return [s.get("text", "").strip() for s in sentences if isinstance(s, dict)]


def probe_tile(path: Path, vlm, reps: int) -> list[dict]:
    """한 이미지에 베이스라인·후보 프롬프트를 reps회씩 돌려 결과 리스트를 낸다."""
    runs = []
    for rep in range(1, reps + 1):
        try:
            base = run(path, OCR_PROMPT, vlm)
            base_sentences = summarize_sentences(base.get("sentences") or [])
        except Exception as e:
            print(f"    [skip] 베이스라인 rep{rep} 실패: {type(e).__name__}: {e}")
            base_sentences = None
        try:
            cand = run(path, CANDIDATE_PROMPT, vlm)
            cand_sentences = summarize_sentences(cand.get("sentences") or [])
            ingredients_raw = (cand.get("ingredients_raw") or "").strip()
        except Exception as e:
            print(f"    [skip] 후보 rep{rep} 실패: {type(e).__name__}: {e}")
            cand_sentences, ingredients_raw = None, None
        runs.append({
            "rep": rep,
            "base_n": len(base_sentences) if base_sentences is not None else None,
            "cand_n": len(cand_sentences) if cand_sentences is not None else None,
            "base_sentences": base_sentences,
            "cand_sentences": cand_sentences,
            "ingredients_len": len(ingredients_raw) if ingredients_raw is not None else None,
            "ingredients_raw": ingredients_raw,
        })
    return runs


def main() -> None:
    vlm = get_vlm("gemini")
    all_results = []

    for sentence_rel, ingredient_rel, label in CASES:
        print(f"\n{'#' * 70}\n{label}\n{'#' * 70}")

        print(f"\n--- 회귀 확인용 (전성분 없음): {sentence_rel} ---")
        sruns = probe_tile(DETAILS / sentence_rel, vlm, REPS)
        for r in sruns:
            print(f"  rep{r['rep']}: 베이스라인 {r['base_n']}문장 / 후보 {r['cand_n']}문장"
                  f" / ingredients_raw {r['ingredients_len']}자")
        base_ns = [r["base_n"] for r in sruns if r["base_n"] is not None]
        cand_ns = [r["cand_n"] for r in sruns if r["cand_n"] is not None]
        print(f"  요약: 베이스라인 문장수 범위 {min(base_ns)}~{max(base_ns)} / "
              f"후보 문장수 범위 {min(cand_ns)}~{max(cand_ns)}")

        print(f"\n--- 전성분 추출 확인용: {ingredient_rel} ---")
        iruns = probe_tile(DETAILS / ingredient_rel, vlm, REPS)
        for r in iruns:
            print(f"  rep{r['rep']}: 베이스라인 {r['base_n']}문장 / 후보 {r['cand_n']}문장"
                  f" / ingredients_raw {r['ingredients_len']}자")
            if r["ingredients_raw"]:
                print(f"    -> {r['ingredients_raw'][:150]}...")
        got_ingredients = [r for r in iruns if (r["ingredients_len"] or 0) > 0]
        print(f"  요약: {len(got_ingredients)}/{len(iruns)}회 성분 추출 성공")

        all_results.append({
            "label": label,
            "regression_runs": sruns,
            "ingredient_runs": iruns,
        })

    print(f"\n\n{'=' * 70}\n전체 요약 ({REPS}회 반복, n={REPS}이라 방향 확인용)\n{'=' * 70}")
    for r in all_results:
        ir = r["ingredient_runs"]
        success = sum(1 for x in ir if (x["ingredients_len"] or 0) > 0)
        print(f"- {r['label']}: 전성분 추출 {success}/{len(ir)}회 성공")


if __name__ == "__main__":
    main()
