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
from barum.judge.evidence_verify import crop_band, verify_evidence
from barum.judge.us_sunscreen import DISCLAIMER, USSunscreenJudge
from barum.models import (
    CheckReport,
    Finding,
    JudgmentFlag,
    Region,
    Summary,
    USPreflightReport,
    USPreflightSummary,
    ViolationType,
)
from barum.preprocess.ocr import extract_product_sentences
from barum.reference.citations import build_regulatory_basis
from barum.reference.evidence_claim import claims_documentary_evidence
from barum.reference.scope import check_product_scope
from barum.vlm import VLM, get_vlm

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
    """OCR 문장 dict에 바운딩 박스 좌표(x_start, x_end, y_start, y_end)와 원본 크기를 붙인다.

    타일의 box_2d([ymin, xmin, ymax, xmax] 0~1000)를 원본 이미지 절대 픽셀 좌표로 환산한다.
    box_2d가 없거나 유효하지 않으면 타일 밴드 전체(x: 0~source_w, y: top~bot)로 fallback한다.
    """
    for s in sentences:
        band = band_by_tile.get(s.get("tile"))
        if band is not None:
            top, bot = band
            tile_h = max(1, bot - top)

            box_2d = s.get("box_2d")
            valid_box = False
            
            # 중첩 배열([[ymin, xmin, ymax, xmax]] 등)에서도 숫자 4개를 안전하게 추출
            nums: list[float] = []
            def _collect_nums(item):
                if isinstance(item, (int, float)):
                    nums.append(float(item))
                elif isinstance(item, (list, tuple)):
                    for sub in item:
                        _collect_nums(sub)

            _collect_nums(box_2d)

            if len(nums) >= 4:
                try:
                    ymin, xmin, ymax, xmax = nums[:4]
                    # 0~1000 scale 또는 0.0~1.0 scale 정규화
                    if any(v > 1.0 for v in (ymin, xmin, ymax, xmax)):
                        ymin, xmin, ymax, xmax = ymin / 1000.0, xmin / 1000.0, ymax / 1000.0, xmax / 1000.0

                    ymin, ymax = max(0.0, min(1.0, ymin)), max(0.0, min(1.0, ymax))
                    xmin, xmax = max(0.0, min(1.0, xmin)), max(0.0, min(1.0, xmax))

                    if ymax > ymin and xmax > xmin:
                        s["x_start"] = max(0, min(source_w, int(xmin * source_w)))
                        s["x_end"] = max(0, min(source_w, int(xmax * source_w)))
                        s["y_start"] = max(0, min(source_h, int(top + ymin * tile_h)))
                        s["y_end"] = max(0, min(source_h, int(top + ymax * tile_h)))
                        valid_box = True
                except (ValueError, TypeError):
                    valid_box = False

            if not valid_box:
                s["x_start"] = 0
                s["x_end"] = source_w
                s["y_start"] = top
                s["y_end"] = bot

            print(f"    [문장 좌표 변환 (order={s.get('order')})]: '{s.get('text', '')[:20]}' -> x=({s.get('x_start')}, {s.get('x_end')}), y=({s.get('y_start')}, {s.get('y_end')}) (valid_bbox={valid_box})")

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


def _verify_functional_evidence(
    findings: list[Finding],
    image_bytes: bytes | None,
    product_name: str | None,
    verbose: bool = False,
    vlm: VLM | None = None,
) -> list[Finding]:
    """2호(기능성오인) findings 중 증빙 문서를 내세우는 것만 원본 이미지로 재대조한다.

    에스코 위조 사례 대응(에이전틱 판정 2단계, 상세: judge/evidence_verify.py).
    문서가 제품·주장과 어긋나면(위조 의심) 위반으로 격상하고, 문서가 진짜로
    확인되면 finding을 빼 합법으로 강등한다(팀장 승인 2026-08-19,
    type_2_functional_misperception.md 근거). 그 외(unknown 포함)는 대조 없이
    돌린 것처럼 기존 판정을 그대로 둔다 — 강등은 위험한 방향이라 확정될 때만 한다.
    이미지가 없으면 대조할 원본이 없어 그대로 돌려준다.
    vlm: 테스트 주입용. 안 주면 첫 대조 필요 시점에 Gemini를 지연 생성한다.
    """
    if not image_bytes:
        return findings

    evidence_vlm: VLM | None = vlm
    kept: list[Finding] = []
    for f in findings:
        needs_check = (
            f.violation_type == ViolationType.type_2_functional_misperception
            and claims_documentary_evidence(f.sentence)
            and f.location.y_start is not None
            and f.location.y_end is not None
        )
        if not needs_check:
            kept.append(f)
            continue

        # 판정 기본 provider는 증빙서 잔글씨를 못 읽는다. 이 단계는 반드시
        # OCR provider(Gemini)로 호출한다(judge/evidence_verify.py 실측 확인).
        if evidence_vlm is None:
            evidence_vlm = get_vlm(provider="gemini")

        band = crop_band(image_bytes, f.location.y_start, f.location.y_end)
        verdict = verify_evidence(evidence_vlm, band, f.sentence, product_name)
        if verdict is None:
            kept.append(f)  # 대조 실패(예상된 실패) — 기존 판정 유지
            continue

        if verdict.is_verified:
            if verbose:
                print(f"    [evidence downgrade] 증빙 진짜 확인, 합법 강등: {f.sentence[:60]}")
            continue  # 강등 = finding 자체를 뺀다

        if verdict.is_mismatch and f.flag != JudgmentFlag.violation:
            if verbose:
                print(f"    [evidence upgrade] 증빙 불일치, 위반 격상: {f.sentence[:60]}")
            f = f.model_copy(update={
                "flag": JudgmentFlag.violation,
                "explanation": (
                    f"{f.explanation} (증빙 대조: 첨부 문서가 제품·주장과 불일치 — "
                    f"문서상 제품명 '{verdict.doc_product_name}', "
                    f"시험항목 '{verdict.doc_test_item}')"
                ),
            })
        kept.append(f)

    return kept


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

    # 상품 단위 대상외 게이트. 문장 판정 전에 한 번만 본다 — 짜개(도구)류 상품의
    # "짜개"라는 단어가 없는 다른 문장("흠집이 생기지 않아요")까지 효능주장으로
    # 오판되는 걸 막는다(cosmetic_scope.md). 애매하면 화장품 쪽으로 판단하므로
    # False(대상외 확정)일 때만 문장 판정을 건너뛴다.
    in_scope, oos_reason = check_product_scope([s["text"] for s in sentences])
    if not in_scope:
        summary = Summary(
            region=Region(region),
            n_sentences=len(sentences),
            n_findings=0,
            product_out_of_scope=True,
            out_of_scope_reason=oos_reason,
        )
        return CheckReport(
            findings=[],
            unjudged=[],
            summary=summary,
            basis=build_regulatory_basis(region),
        )

    ingredient_list = _split_ingredients(ingredients) if ingredients else None
    amount_list = _parse_ingredient_amounts(ingredient_amounts) if ingredient_amounts else None
    result = judge.judge(sentences, region, ingredients=ingredient_list, ingredient_amounts=amount_list)
    findings = _verify_functional_evidence(
        result.findings, image_bytes, product_name, verbose=verbose
    )

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
    return CheckReport(
        findings=findings,
        unjudged=result.unjudged,
        summary=summary,
        basis=build_regulatory_basis(region),
    )


def run_us_sunscreen_check(
    ad_text: str | None,
    image_bytes: bytes | None,
    image_filename: str | None,
    vlm: VLM | None,
    judge: USSunscreenJudge,
    ingredients: str | None = None,
    product_name: str | None = None,
    verbose: bool = False,
) -> USPreflightReport:
    """미국 프리플라이트(자외선차단 최소보장) 검사 한 건을 처리해 USPreflightReport를 만든다.

    국내 run_check()와 입력·OCR 흐름은 같지만(이미지 타일분할·OCR은 국가 무관 공용 로직),
    ingredient_amounts는 안 받는다 — 성분 대조가 함량이 아니라 "미국 승인 목록에 있나
    없나"만 보므로(`sunscreen_otc_classification.md` §1②). 판정기(judge)는 VLM을
    안 쓰지만, 이미지 OCR 자체는 여전히 VLM이 필요해 vlm 인자는 그대로 받는다.
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
    findings = judge.judge(sentences, ingredients=ingredient_list)

    counts: dict[str, int] = {}
    for f in findings:
        key = f.category.value
        counts[key] = counts.get(key, 0) + 1

    summary = USPreflightSummary(
        n_sentences=len(sentences),
        n_findings=len(findings),
        counts_by_category=counts,
    )
    return USPreflightReport(
        findings=findings,
        summary=summary,
        disclaimer=DISCLAIMER,
    )
