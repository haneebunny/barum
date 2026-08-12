"""파이프라인 배선: 입력 → 문장 → 판정 → 리포트.

흐름(이미지): 바이트 → tile_split → OCR(vlm) → 문장 리스트 → judge → CheckReport.
흐름(텍스트): ad_text → 문장 분리 → judge → CheckReport.
규칙집이 없어도 OCR까지는 실동작한다. 판정만 stub이다.
"""

import re
import tempfile
from pathlib import Path

from PIL import Image

from barum.judge.cosmetic import CosmeticJudge
from barum.models import CheckReport, JudgmentFlag, Region, Summary
from barum.preprocess.ocr import extract_product_sentences
from barum.vlm import VLM

# 문장 분리: 줄바꿈과 문장부호(한/영) 기준. 광고 카피라 완벽한 분리보다 단순·안정을 택한다.
_SENT_SPLIT = re.compile(r"[\n。.!?！？]+")


def _split_ingredients(text: str) -> list[str]:
    """전성분 문자열을 성분명 리스트로 쪼갠다. 전성분표는 보통 콤마로 나열된다."""
    return [s.strip() for s in re.split(r"[,\n]+", text) if s.strip()]


def _parse_ingredient_amounts(text: str) -> list[tuple[str, str]]:
    """"성분:함량" 콤마 구분 문자열을 (성분명, 함량) 목록으로 쪼갠다.

    예: "나이아신아마이드:3%,알부틴:10%". ":" 없는 항목(함량 미표기)은 그냥 건너뛴다
    — 함량 대조는 명시된 성분에만 붙는다(안 준 건 기존처럼 검토필요로 남는다).
    """
    out: list[tuple[str, str]] = []
    for part in re.split(r"[,\n]+", text):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, amount = part.split(":", 1)
        name, amount = name.strip(), amount.strip()
        if name and amount:
            out.append((name, amount))
    return out


def _split_text_to_sentences(ad_text: str, source: str | None = None) -> list[dict]:
    """글 입력을 문장 dict 리스트로 쪼갠다. 이미지가 없으니 tile은 None."""
    out: list[dict] = []
    for part in _SENT_SPLIT.split(ad_text):
        part = part.strip()
        if part:
            out.append({"order": len(out), "tile": None, "text": part, "source": source})
    return out


def _attach_bands(
    sentences: list[dict],
    band_by_tile: dict[str, tuple[int, int]],
    source_w: int,
    source_h: int,
) -> list[dict]:
    """OCR 문장 dict에 타일 밴드 좌표(y_start,y_end)와 원본 크기를 붙인다.

    타일 이름으로 밴드를 찾는다. 같은 문구가 여러 타일에 겹쳐 잡혀도 dedup으로 첫
    타일 하나만 남으므로 그 타일 밴드를 쓴다(밴드 하이라이트엔 충분). 밴드 맵에 없는
    타일이면 좌표를 안 넣는다, 잘못된 밴드를 다는 것보다 없는 게 안전하다.
    """
    for s in sentences:
        band = band_by_tile.get(s.get("tile"))
        if band is not None:
            s["y_start"], s["y_end"] = band
        s["source_w"] = source_w
        s["source_h"] = source_h
    return sentences


def _ocr_image(
    image_bytes: bytes, filename: str | None, vlm: VLM, verbose: bool = False
) -> list[dict]:
    """이미지 바이트를 타일 분할·OCR 해 문장 dict 리스트를 만든다.

    OCR 재사용 코드는 `product_dir/tiles/*.png` 구조를 기대하므로, 임시 폴더에 그
    구조를 그대로 만든 뒤 기존 함수를 호출한다. 임시 폴더는 요청이 끝나면 지운다.
    split_image가 돌려준 (타일, top, bot)로 밴드 맵을 만들어, OCR 문장에 원본 좌표를
    실어 준다(리포트가 원본 위에 밴드를 하이라이트할 수 있게).
    """
    from tile_split import split_image  # top-level 모듈(backend 루트)

    suffix = Path(filename).suffix if filename else ".png"
    with tempfile.TemporaryDirectory() as tmp:
        product_dir = Path(tmp)
        source = product_dir / f"source{suffix}"
        source.write_bytes(image_bytes)

        # tiles/ 하위에 타일 저장 → extract_product_sentences가 여기서 글롭한다.
        tiles = split_image(source, product_dir / "tiles")
        band_by_tile = {path.name: (top, bot) for path, top, bot in tiles}
        with Image.open(source) as im:
            source_w, source_h = im.size

        record = extract_product_sentences(product_dir, vlm, verbose=verbose)

    return _attach_bands(record["sentences"], band_by_tile, source_w, source_h)


def run_check(
    region: str,
    ad_text: str | None,
    image_bytes: bytes | None,
    image_filename: str | None,
    vlm: VLM,
    judge: CosmeticJudge,
    ingredients: str | None = None,
    ingredient_amounts: str | None = None,
    product_name: str | None = None,
    verbose: bool = False,
) -> CheckReport:
    """한 번의 검사 요청을 처리해 CheckReport를 만든다.

    이미지·글 둘 다 오면 이미지 문장 뒤에 글 문장을 이어 붙인다. 둘 다 없으면
    빈 리포트(호출 전 API가 422로 막는다).
    product_name: 상품명/광고 제목. 있으면 판정 대상 문장에 포함된다.
    ingredients: 선택적 전성분 문자열(콤마 구분). 있으면 2호(기능성오인) 판정에
    성분 정합 대조가 붙는다(judge가 지원하는 경우).
    ingredient_amounts: 선택적 "성분:함량" 콤마구분 문자열(예: "나이아신아마이드:3%").
    명시된 성분만 함량기준 대조까지 더해진다. 안 주면 기존처럼 이름만 대조한다.
    """
    sentences: list[dict] = []

    if product_name and product_name.strip():
        sentences.append({
            "order": 0,
            "tile": None,
            "text": product_name.strip(),
            "source": "product_name",
        })

    if image_bytes:
        base = len(sentences)
        for s in _ocr_image(image_bytes, image_filename, vlm, verbose=verbose):
            sentences.append({**s, "order": base + s.get("order", 0)})

    if ad_text:
        base = len(sentences)
        for s in _split_text_to_sentences(ad_text, source="ad_text"):
            sentences.append({**s, "order": base + s["order"]})

    ingredient_list = _split_ingredients(ingredients) if ingredients else None
    amount_list = _parse_ingredient_amounts(ingredient_amounts) if ingredient_amounts else None
    result = judge.judge(sentences, region, ingredients=ingredient_list, ingredient_amounts=amount_list)
    findings = result.findings

    counts: dict[str, int] = {}
    for f in findings:
        key = f.violation_type.value
        counts[key] = counts.get(key, 0) + 1

    n_violation = sum(1 for f in findings if f.flag == JudgmentFlag.violation)
    n_needs_review = sum(1 for f in findings if f.flag == JudgmentFlag.needs_review)

    summary = Summary(
        region=Region(region),
        n_sentences=len(sentences),
        n_findings=len(findings),
        n_violation=n_violation,
        n_needs_review=n_needs_review,
        n_unjudged=len(result.unjudged),
        counts_by_type=counts,
    )
    return CheckReport(findings=findings, unjudged=result.unjudged, summary=summary)
