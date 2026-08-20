"""타일 이미지 → 문장 추출 (VLM 비전 OCR).

입력: `11st_output/details/{product_code}/tiles/*.png`
출력: 상품별 문장 리스트(순서 보존). 문맥 윈도우는 이 순서를 그대로 쓴다.
"""

import re
from pathlib import Path

from barum.vlm import VLM

BATCH_PROMPT = """첨부된 이미지 {n}장은 한 상품 상세페이지를 위에서 아래로 자른 조각들이다.
**각 이미지마다 따로**, 보이는 모든 한국어 텍스트를 위에서 아래 순서로 읽어라.

규칙:
- 광고 문구를 **문장 단위**로 끊어서 배열에 담는다.
- 각 문장마다 이미지 내에서의 2D 사각 영역(Bounding Box: [ymin, xmin, ymax, xmax], 0~1000 정규화 좌표)을 `box_2d`로 함께 반환한다.
- 줄바꿈은 문장 구분이 아니다. 디자인상 줄이 나뉜 한 문장은 하나로 합쳐라.
- 가격·배송·교환/반품 안내·회사 주소·사업자번호 같은 거래 안내 문구는 제외한다.
- 원문 그대로 옮긴다. 맞춤법을 고치거나 표현을 다듬지 마라.
  (붙여쓰기·특수문자·초성 같은 회피표기도 원문 그대로 둔다)
- 한국어가 전혀 없는 이미지는 빈 배열로 둔다.
- **이미지를 건너뛰지 마라.** 첨부 순서대로 {n}개 항목을 모두 반환한다.

JSON으로만 답하라:
{{"images": [{{"i": 0, "sentences": [{{"text": "문장1", "box_2d": [ymin, xmin, ymax, xmax]}}]}}, {{"i": 1, "sentences": []}}]}}"""

OCR_PROMPT = """이 이미지는 한국 이커머스 상품 상세페이지의 일부다.
이미지에 보이는 모든 한국어 텍스트를 위에서 아래 순서로 읽어라.

규칙:
- 광고 문구를 **문장 단위**로 끊어서 배열에 담는다.
- 각 문장마다 이미지 내에서의 2D 사각 영역(Bounding Box: [ymin, xmin, ymax, xmax], 0~1000 정규화 좌표)을 `box_2d`로 함께 반환한다.
- 줄바꿈은 문장 구분이 아니다. 디자인상 줄이 나뉜 한 문장은 하나로 합쳐라.
- 가격·배송·교환/반품 안내·회사 주소·사업자번호 같은 거래 안내 문구는 제외한다.
- 원문 그대로 옮긴다. 맞춤법을 고치거나 표현을 다듬지 마라.
  (붙여쓰기·특수문자·초성 같은 회피표기도 원문 그대로 둔다)
- 읽을 수 없는 글자는 그 문장을 통째로 빼지 말고 읽을 수 있는 부분만 담는다.
- 한국어가 전혀 없으면 빈 배열을 반환한다.

JSON으로만 답하라: {"sentences": [{"text": "문장1", "box_2d": [ymin, xmin, ymax, xmax]}, {"text": "문장2", "box_2d": [ymin, xmin, ymax, xmax]}]}"""


def _normalize(s: str) -> str:
    """중복 판정용 정규화 — 공백·문장부호를 지운 형태로 비교한다."""
    return re.sub(r"[\s\W_]+", "", s)


def _ocr_batch(tiles: list[Path], vlm: VLM) -> list[list[dict | str]]:
    """타일 여러 장을 한 번에 보내고 이미지별 문장 배열을 받는다.

    한 요청에 이미지를 몰아넣으면 모델이 뒤쪽을 빠뜨리기 쉬우므로, 응답 개수가
    모자라면 빈 배열로 채워 호출자가 어느 타일이 비었는지 알 수 있게 한다.
    """
    if len(tiles) == 1:
        result = vlm.generate_json(OCR_PROMPT, [tiles[0].read_bytes()])
        return [result.get("sentences") or []]

    result = vlm.generate_json(
        BATCH_PROMPT.format(n=len(tiles)), [t.read_bytes() for t in tiles]
    )
    out: list[list[dict | str]] = [[] for _ in tiles]
    for item in result.get("images", []):
        try:
            idx = int(item["i"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= idx < len(tiles):
            out[idx] = item.get("sentences") or []
    return out


def extract_product_sentences(
    product_dir: Path, vlm: VLM, verbose: bool = True, batch_size: int = 1
) -> dict:
    """상품 하나의 타일 전체를 OCR 해 문장 리스트를 만든다.

    같은 문구가 여러 번 잡힌다 — 타일 경계(80px 겹침)로도, 상세페이지가 같은
    슬로건을 반복해서도. 홀드아웃엔 유니크 문장만 필요하므로 상품 단위로 중복을 없앤다.

    반환: {product_id, sentences: [{order, tile, text, box_2d}], tiles_ok, tiles_failed}
    """
    tiles = sorted((product_dir / "tiles").glob("*.png"))
    sentences: list[dict] = []
    seen: set[str] = set()
    failed: list[str] = []

    for start in range(0, len(tiles), batch_size):
        chunk = tiles[start:start + batch_size]
        try:
            per_tile = _ocr_batch(chunk, vlm)
        except Exception as e:
            # 예상된 실패(429·타임아웃·빈 응답). 과금 호출이라 재시도하지 않는다.
            print(f"    [skip] {chunk[0].name}~{chunk[-1].name}: "
                  f"{type(e).__name__}: {e}")
            failed += [t.name for t in chunk]
            continue

        for tile, raw in zip(chunk, per_tile):
            fresh = []
            for item in raw:
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

    return {
        "product_id": product_dir.name,
        "sentences": sentences,
        "tiles_ok": len(tiles) - len(failed),
        "tiles_failed": failed,
    }


def with_context(sentences: list[dict], window: int = 2) -> list[dict]:
    """각 문장에 앞뒤 문맥(기본 2문장씩)을 붙인다. 학생 모델 입력 스키마와 동일."""
    texts = [s["text"] for s in sentences]
    out = []
    for i, s in enumerate(sentences):
        out.append(
            {
                **s,
                "context_before": " ".join(texts[max(0, i - window) : i]),
                "context_after": " ".join(texts[i + 1 : i + 1 + window]),
            }
        )
    return out
