"""파이프라인 배선: 입력 → 문장 → 판정 → 리포트.

흐름(이미지): 바이트 → tile_split → OCR(vlm) → 문장 리스트 → judge → CheckReport.
흐름(텍스트): ad_text → 문장 분리 → judge → CheckReport.
규칙집이 없어도 OCR까지는 실동작한다. 판정만 stub이다.
"""

import re
import tempfile
from pathlib import Path

from barum.judge.cosmetic import CosmeticJudge
from barum.models import CheckReport, Region, Summary
from barum.preprocess.ocr import extract_product_sentences
from barum.vlm import VLM

# 문장 분리: 줄바꿈과 문장부호(한/영) 기준. 광고 카피라 완벽한 분리보다 단순·안정을 택한다.
_SENT_SPLIT = re.compile(r"[\n。.!?！？]+")


def _split_text_to_sentences(ad_text: str) -> list[dict]:
    """글 입력을 문장 dict 리스트로 쪼갠다. 이미지가 없으니 tile은 None."""
    out: list[dict] = []
    for part in _SENT_SPLIT.split(ad_text):
        part = part.strip()
        if part:
            out.append({"order": len(out), "tile": None, "text": part})
    return out


def _ocr_image(
    image_bytes: bytes, filename: str | None, vlm: VLM, verbose: bool = False
) -> list[dict]:
    """이미지 바이트를 타일 분할·OCR 해 문장 dict 리스트를 만든다.

    OCR 재사용 코드는 `product_dir/tiles/*.png` 구조를 기대하므로, 임시 폴더에 그
    구조를 그대로 만든 뒤 기존 함수를 호출한다. 임시 폴더는 요청이 끝나면 지운다.
    """
    from tile_split import split_image  # top-level 모듈(backend 루트)

    suffix = Path(filename).suffix if filename else ".png"
    with tempfile.TemporaryDirectory() as tmp:
        product_dir = Path(tmp)
        source = product_dir / f"source{suffix}"
        source.write_bytes(image_bytes)

        # tiles/ 하위에 타일 저장 → extract_product_sentences가 여기서 글롭한다.
        split_image(source, product_dir / "tiles")
        record = extract_product_sentences(product_dir, vlm, verbose=verbose)

    return record["sentences"]


def run_check(
    region: str,
    ad_text: str | None,
    image_bytes: bytes | None,
    image_filename: str | None,
    vlm: VLM,
    judge: CosmeticJudge,
    verbose: bool = False,
) -> CheckReport:
    """한 번의 검사 요청을 처리해 CheckReport를 만든다.

    이미지·글 둘 다 오면 이미지 문장 뒤에 글 문장을 이어 붙인다. 둘 다 없으면
    빈 리포트(호출 전 API가 422로 막는다).
    """
    sentences: list[dict] = []

    if image_bytes:
        sentences.extend(_ocr_image(image_bytes, image_filename, vlm, verbose=verbose))

    if ad_text:
        base = len(sentences)
        for s in _split_text_to_sentences(ad_text):
            sentences.append({**s, "order": base + s["order"]})

    findings = judge.judge(sentences, region)

    counts: dict[str, int] = {}
    for f in findings:
        key = f.violation_type.value
        counts[key] = counts.get(key, 0) + 1

    summary = Summary(
        region=Region(region),
        n_sentences=len(sentences),
        n_findings=len(findings),
        counts_by_type=counts,
    )
    return CheckReport(findings=findings, summary=summary)
