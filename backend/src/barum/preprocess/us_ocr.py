# -*- coding: utf-8 -*-
"""미국 프리플라이트 전용 OCR — 국내 OCR(preprocess/ocr.py)과 완전히 분리.

전성분(ingredients_raw) 필드를 얹은 프롬프트를 국내 파이프라인과 공유하면 국내 OCR
응답에도 그 필드가 섞여 나간다(안 쓰더라도). 국내 쪽에 어떤 영향도 안 가게, US
전용 프롬프트·함수로 따로 둔다(2026-08-24, 팀 결정).

측정 근거: scripts/ocr_ingredient_field_probe.py, scripts/ocr_ingredient_field_probe_focus.py
(상품 3개·표기방식 3종(문단형·스펙표형·영문 병사진형)에서 전성분 추출 6/6 성공,
같은 조건에서 문장 손실은 확인 안 됨. 문장 개수 흔들림은 있었으나 내용 대조 결과
전부 "병합"이지 "누락"은 아니었음 — 회귀 미확정, 이 프로젝트 기준 3회 미만은 증명 아님).
"""

import re
from pathlib import Path

from barum.vlm import VLM

US_OCR_PROMPT = """이 이미지는 한국 이커머스 상품 상세페이지의 일부다.
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

US_BATCH_PROMPT = """첨부된 이미지 {n}장은 한 상품 상세페이지를 위에서 아래로 자른 조각들이다.
**각 이미지마다 따로**, 보이는 모든 한국어 텍스트를 위에서 아래 순서로 읽어라.

규칙:
- 광고 문구를 **문장 단위**로 끊어서 배열에 담는다.
- 반드시 각 문장마다 해당 문구가 위치한 2D 사각 영역(Bounding Box: [ymin, xmin, ymax, xmax], 0~1000 정규화 정수 좌표)을 `box_2d` 필드에 반드시 포함하라.
- 줄바꿈은 문장 구분이 아니다. 디자인상 줄이 나뉜 한 문장은 하나로 합쳐라.
- 가격·배송·교환/반품 안내·회사 주소·사업자번호 같은 거래 안내 문구는 제외한다.
- 원문 그대로 옮긴다. 맞춤법을 고치거나 표현을 다듬지 마라.
  (붙여쓰기·특수문자·초성 같은 회피표기도 원문 그대로 둔다)
- 한국어가 전혀 없는 이미지는 빈 배열로 둔다.
- **이미지를 건너뛰지 마라.** 첨부 순서대로 {n}개 항목을 모두 반환한다.

추가로, 각 이미지에 **전성분 목록**(한국어 "전성분:" 표기, 영문 "Ingredients:" 표기,
또는 성분명이 쉼표로 길게 나열된 부분 어느 쪽이든)이 보이면 그 이미지 항목의
`ingredients_raw` 필드에 원문 그대로 쉼표로 구분해 옮긴다. 없으면 빈 문자열로 둔다.
**지어내지 마라.**

JSON 응답 형식 예시:
{{"images": [{{"i": 0, "sentences": [{{"text": "유어베리 세럼", "box_2d": [120, 200, 180, 800]}}], "ingredients_raw": ""}}, {{"i": 1, "sentences": [], "ingredients_raw": "정제수, 글리세린"}}]}}"""


def _normalize(s: str) -> str:
    """중복 판정용 정규화 — 공백·문장부호를 지운 형태로 비교한다."""
    return re.sub(r"[\s\W_]+", "", s)


def _ocr_batch_us(tiles: list[Path], vlm: VLM) -> list[dict]:
    """타일 여러 장을 한 번에 보내고 이미지별 {sentences, ingredients_raw}를 받는다."""
    if len(tiles) == 1:
        result = vlm.generate_json(US_OCR_PROMPT, [tiles[0].read_bytes()])
        print(f"    [US VLM OCR RAW 응답 (tile={tiles[0].name})]: {result}")
        return [{
            "sentences": result.get("sentences") or [],
            "ingredients_raw": (result.get("ingredients_raw") or "").strip(),
        }]

    result = vlm.generate_json(
        US_BATCH_PROMPT.format(n=len(tiles)), [t.read_bytes() for t in tiles]
    )
    print(f"    [US VLM BATCH OCR RAW 응답 ({len(tiles)}장)]: {result}")
    out: list[dict] = [{"sentences": [], "ingredients_raw": ""} for _ in tiles]
    for item in result.get("images", []):
        try:
            idx = int(item["i"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= idx < len(tiles):
            out[idx] = {
                "sentences": item.get("sentences") or [],
                "ingredients_raw": (item.get("ingredients_raw") or "").strip(),
            }
    return out


def extract_us_sentences(
    product_dir: Path, vlm: VLM, verbose: bool = True, batch_size: int = 3
) -> dict:
    """상품 하나의 타일 전체를 US 프롬프트로 OCR 해 문장·전성분을 만든다.

    반환: {product_id, sentences: [{order, tile, text, box_2d}], ingredients_raw,
    tiles_ok, tiles_failed}

    ingredients_raw: 여러 타일에서 비어있지 않은 값이 나오면 가장 긴 것을 쓴다.
    전성분 패널은 보통 한 타일에만 있지만, 타일 경계(겹침)에 걸쳐 있으면 양쪽에서
    부분적으로 잡힐 수 있다 — 그 경우 더 온전하게(길게) 읽힌 쪽이 더 정확할 가능성이
    높다는 가정이다(확정 근거는 아님, 실사용에서 더 잡히면 재검토).
    """
    tiles = sorted((product_dir / "tiles").glob("*.png"))
    sentences: list[dict] = []
    seen: set[str] = set()
    failed: list[str] = []
    ingredients_candidates: list[str] = []

    for start in range(0, len(tiles), batch_size):
        chunk = tiles[start:start + batch_size]
        try:
            per_tile = _ocr_batch_us(chunk, vlm)
        except Exception as e:
            # 예상된 실패(429·타임아웃·빈 응답). 과금 호출이라 재시도하지 않는다.
            print(f"    [skip] {chunk[0].name}~{chunk[-1].name}: "
                  f"{type(e).__name__}: {e}")
            failed += [t.name for t in chunk]
            continue

        for tile, raw in zip(chunk, per_tile):
            fresh = []
            for item in raw.get("sentences", []):
                if isinstance(item, dict):
                    text = (item.get("text") or "").strip()
                    box_2d = item.get("box_2d")
                else:
                    text = str(item or "").strip()
                    box_2d = None

                key = _normalize(text)
                if not key or key in seen:
                    continue
                seen.add(key)
                fresh.append({"text": text, "box_2d": box_2d})

            for s in fresh:
                sentences.append(
                    {
                        "order": len(sentences),
                        "tile": tile.name,
                        "text": s["text"],
                        "box_2d": s["box_2d"],
                    }
                )
            if verbose:
                print(f"    {tile.name}: +{len(fresh)}문장 (누적 {len(sentences)})")

            ing = raw.get("ingredients_raw") or ""
            if ing:
                ingredients_candidates.append(ing)

    ingredients_raw = max(ingredients_candidates, key=len, default="")

    return {
        "product_id": product_dir.name,
        "sentences": sentences,
        "ingredients_raw": ingredients_raw,
        "tiles_ok": len(tiles) - len(failed),
        "tiles_failed": failed,
    }
