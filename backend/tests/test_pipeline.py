"""파이프라인 조립 유닛테스트.

VLM은 가짜 객체(Protocol 충족, 네트워크 없음)로 주입하고, judge는 StubJudge를
쓴다. 외부 의존(진짜 Gemini)은 여기서 안 건드린다 = 수동 스모크로 별도 확인.

    venv/bin/python -m pytest tests/test_pipeline.py -q
"""

import io

from PIL import Image

from barum.judge.cosmetic import JudgeResult, StubJudge
from barum.models import Finding, JudgmentFlag, Location, ViolationType
from barum.pipeline import _attach_bands, _verify_functional_evidence, run_check


def test_attach_bands_sets_coordinates_by_tile():
    """타일 이름으로 밴드를 찾아 문장에 y_start/y_end·원본 크기를 붙인다."""
    sents = [
        {"order": 0, "tile": "s_t00.png", "text": "a"},
        {"order": 1, "tile": "s_t01.png", "text": "b"},
    ]
    bands = {"s_t00.png": (0, 1480), "s_t01.png": (1400, 2900)}
    _attach_bands(sents, bands, source_w=1000, source_h=9000)
    assert (sents[0]["y_start"], sents[0]["y_end"]) == (0, 1480)
    assert (sents[1]["y_start"], sents[1]["y_end"]) == (1400, 2900)
    assert all(s["source_w"] == 1000 and s["source_h"] == 9000 for s in sents)


def test_attach_bands_unknown_tile_leaves_band_absent():
    """밴드 맵에 없는 타일이면 좌표를 안 넣는다(잘못된 밴드 대신 없음이 안전)."""
    sents = [{"order": 0, "tile": "unknown.png", "text": "a"}]
    _attach_bands(sents, {"s_t00.png": (0, 100)}, source_w=1000, source_h=9000)
    assert "y_start" not in sents[0]
    assert sents[0]["source_w"] == 1000  # 원본 크기는 그래도 실린다


class FakeVLM:
    """OCR 호출을 가로채 캔드 문장을 돌려주는 가짜 어댑터."""

    def __init__(self, sentences: list[str]):
        self._sentences = sentences

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        # 단일 타일 경로(len(tiles)==1)는 {"sentences": [...]}를 기대한다.
        return {"sentences": self._sentences}


def _tiny_png() -> bytes:
    """tile_split이 1타일로 통과시키는 작은 정사각 이미지."""
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(buf, "PNG")
    return buf.getvalue()


def test_text_only_path():
    """글 입력 → 문장 분리 → StubJudge. VLM 없이 동작한다."""
    report = run_check(
        region="KR",
        ad_text="멜라닌을 막아 미백에 도움. 순한 보습감.",
        image_bytes=None,
        image_filename=None,
        vlm=None,
        judge=StubJudge(),
    )
    assert report.summary.n_sentences == 2
    # "미백" 문장 1건만 위반, "순한 보습감"은 합법(finding 없음).
    assert report.summary.n_findings == 1
    assert report.findings[0].violation_type.value == "2호_기능성오인"
    assert report.findings[0].location.tile is None


def test_image_path_uses_ocr():
    """이미지 → tile_split → 가짜 OCR → StubJudge."""
    fake = FakeVLM(["피부 재생 효과", "촉촉한 사용감"])
    report = run_check(
        region="KR",
        ad_text=None,
        image_bytes=_tiny_png(),
        image_filename="ad.png",
        vlm=fake,
        judge=StubJudge(),
    )
    assert report.summary.n_sentences == 2
    assert report.summary.n_findings == 1
    f = report.findings[0]
    assert f.violation_type.value == "1호_의약품오인"  # "재생"
    assert f.location.tile is not None  # 타일에서 왔다
    # 타일 밴드 좌표·원본 크기가 실린다(200x200 통짜 → 밴드 0~200).
    assert f.location.y_start == 0
    assert f.location.y_end == 200
    assert f.location.source_h == 200
    assert f.location.source_w == 200


def test_text_path_has_no_band_coordinates():
    """텍스트 입력엔 타일이 없으니 밴드 좌표도 None."""
    report = run_check(
        region="KR",
        ad_text="미백에 도움을 줍니다.",
        image_bytes=None,
        image_filename=None,
        vlm=None,
        judge=StubJudge(),
    )
    loc = report.findings[0].location
    assert loc.tile is None
    assert loc.y_start is None
    assert loc.y_end is None
    assert loc.source_h is None
    assert loc.source_w is None


def test_both_inputs_concatenate():
    """이미지·글 둘 다 오면 문장이 이어 붙고 order가 이어진다."""
    fake = FakeVLM(["주름개선 도움"])
    report = run_check(
        region="KR",
        ad_text="시중 대비 3배 효과.",
        image_bytes=_tiny_png(),
        image_filename="ad.png",
        vlm=fake,
        judge=StubJudge(),
    )
    assert report.summary.n_sentences == 2
    orders = sorted(s for s in [f.location.order for f in report.findings])
    assert orders == [0, 1]  # 이미지 문장 order=0, 글 문장 order=1
    assert report.summary.counts_by_type == {"2호_기능성오인": 1, "5호_거짓과장기만": 1}


class RecordingJudge:
    """judge에 뭐가 넘어오는지 기록만 하는 가짜 판정기(전달 배선 검증용)."""

    def __init__(self):
        self.received_ingredients = "not called"
        self.received_ingredient_amounts = "not called"

    def judge(self, sentences, region, ingredients=None, ingredient_amounts=None):
        self.received_ingredients = ingredients
        self.received_ingredient_amounts = ingredient_amounts
        return JudgeResult()


def test_ingredients_string_is_split_and_passed_to_judge():
    """콤마로 나열된 전성분 문자열이 리스트로 쪼개져 judge에 전달된다."""
    judge = RecordingJudge()
    run_check(
        region="KR",
        ad_text="촉촉한 보습감.",
        image_bytes=None,
        image_filename=None,
        vlm=None,
        judge=judge,
        ingredients="정제수, 나이아신아마이드,글리세린",
    )
    assert judge.received_ingredients == ["정제수", "나이아신아마이드", "글리세린"]


def test_no_ingredients_passes_none_to_judge():
    judge = RecordingJudge()
    run_check(
        region="KR",
        ad_text="촉촉한 보습감.",
        image_bytes=None,
        image_filename=None,
        vlm=None,
        judge=judge,
    )
    assert judge.received_ingredients is None
    assert judge.received_ingredient_amounts is None


def test_ingredient_amounts_string_is_parsed_and_passed_to_judge():
    """"성분:함량" 콤마 문자열이 (이름,함량) 튜플 목록으로 쪼개져 judge에 전달된다."""
    judge = RecordingJudge()
    run_check(
        region="KR",
        ad_text="촉촉한 보습감.",
        image_bytes=None,
        image_filename=None,
        vlm=None,
        judge=judge,
        ingredient_amounts="나이아신아마이드:3%, 알부틴:10%",
    )
    assert judge.received_ingredient_amounts == [("나이아신아마이드", "3%"), ("알부틴", "10%")]


def test_ingredient_amounts_skips_entries_without_colon():
    """":" 없는 항목(함량 미표기)은 건너뛴다 — 그 성분은 기존처럼 이름만 대조된다."""
    judge = RecordingJudge()
    run_check(
        region="KR",
        ad_text="촉촉한 보습감.",
        image_bytes=None,
        image_filename=None,
        vlm=None,
        judge=judge,
        ingredient_amounts="정제수, 나이아신아마이드:3%",
    )
    assert judge.received_ingredient_amounts == [("나이아신아마이드", "3%")]


class FakeEvidenceVLM:
    """증빙 대조 호출을 가로채 고정 응답을 돌려주는 가짜 어댑터(네트워크 없음)."""

    def __init__(self, response: dict):
        self._response = response

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        return self._response


def _functional_finding(**overrides) -> Finding:
    base = dict(
        span="미백 주름개선 2중 기능성",
        sentence="에스코 제주 시카 카밍 세럼은 미백 주름개선 2중 기능성을 보고한 제품입니다",
        violation_type=ViolationType.type_2_functional_misperception,
        legal_basis="화장품법 제13조 제1항 제2호",
        legal_basis_text=None,
        flag=JudgmentFlag.needs_review,
        explanation="근거 문서 확인 안 됨",
        location=Location(
            tile="s_t00.png", order=0, y_start=0, y_end=200, source_h=200, source_w=200
        ),
    )
    base.update(overrides)
    return Finding(**base)


def test_verify_functional_evidence_skips_without_image():
    """이미지가 없으면 대조할 원본이 없다 — findings를 그대로 돌려준다."""
    f = _functional_finding()
    assert _verify_functional_evidence([f], image_bytes=None, product_name="p") == [f]


def test_verify_functional_evidence_skips_non_target_findings():
    """2호가 아니거나 증빙 표지어가 없는 문장은 VLM 호출 없이 그대로 통과한다."""
    not_type2 = _functional_finding(
        violation_type=ViolationType.type_1_drug_misperception, sentence="피부 재생 효과"
    )
    no_evidence_term = _functional_finding(sentence="미백에 좋아요")
    out = _verify_functional_evidence(
        [not_type2, no_evidence_term], image_bytes=_tiny_png(), product_name="p"
    )
    assert out == [not_type2, no_evidence_term]


def test_verify_functional_evidence_upgrades_on_mismatch():
    """제품명·시험항목이 광고와 어긋나면(위조 의심) needs_review여도 violation으로 격상한다."""
    f = _functional_finding(flag=JudgmentFlag.needs_review)
    fake = FakeEvidenceVLM({
        "has_document": True,
        "doc_product_name": "에스코 로즈 PDRN 리페어 앰플",
        "doc_test_item": "피부 첩포에 의한 일차자극 인체적용시험",
        "product_match": False,
        "claim_match": False,
    })
    out = _verify_functional_evidence(
        [f], image_bytes=_tiny_png(), product_name="에스코 제주 시카 카밍 세럼", vlm=fake
    )
    assert len(out) == 1
    assert out[0].flag == JudgmentFlag.violation
    assert "PDRN" in out[0].explanation


def test_verify_functional_evidence_downgrades_on_verified():
    """제품명·시험항목이 광고와 둘 다 확정 일치하면 finding 자체를 빼 합법으로 강등한다."""
    f = _functional_finding(flag=JudgmentFlag.violation)
    fake = FakeEvidenceVLM({
        "has_document": True,
        "doc_product_name": "에스코 제주 시카 카밍 세럼",
        "doc_test_item": "미백 주름개선 2중 기능성 심사",
        "product_match": True,
        "claim_match": True,
    })
    out = _verify_functional_evidence(
        [f], image_bytes=_tiny_png(), product_name="에스코 제주 시카 카밍 세럼", vlm=fake
    )
    assert out == []


def test_verify_functional_evidence_keeps_on_unknown():
    """읽지 못해 unknown이면 확정된 게 없으니 기존 판정을 그대로 둔다(강등은 위험한 방향)."""
    f = _functional_finding(flag=JudgmentFlag.needs_review)
    fake = FakeEvidenceVLM({
        "has_document": True,
        "doc_product_name": "unknown",
        "doc_test_item": "unknown",
        "product_match": "unknown",
        "claim_match": "unknown",
    })
    out = _verify_functional_evidence(
        [f], image_bytes=_tiny_png(), product_name="p", vlm=fake
    )
    assert out == [f]


def test_attach_bands_converts_bbox_to_source_coords():
    """타일의 box_2d가 원본 이미지 기준 절대 픽셀 좌표(x_start, x_end, y_start, y_end)로 환산된다."""
    from barum.pipeline import _attach_bands

    sentences = [
        {
            "order": 0,
            "tile": "tile_00.png",
            "text": "피부 재생 세럼",
            "box_2d": [100, 200, 300, 800],  # ymin, xmin, ymax, xmax (0~1000)
        },
        {
            "order": 1,
            "tile": "tile_00.png",
            "text": "좌표 없는 문장",
            "box_2d": None,
        },
    ]
    # 타일은 top=500, bot=1500 (높이 1000px), 원본 너비 1000px, 원본 높이 3000px
    band_by_tile = {"tile_00.png": (500, 1500)}
    res = _attach_bands(sentences, band_by_tile, source_w=1000, source_h=3000)

    # 1번째 문장: 정밀 bbox
    assert res[0]["x_start"] == 200
    assert res[0]["x_end"] == 800
    assert res[0]["y_start"] == 500 + 100  # 600
    assert res[0]["y_end"] == 500 + 300    # 800

    # 2번째 문장: fallback 타일 전체 폭 및 밴드
    assert res[1]["x_start"] == 0
    assert res[1]["x_end"] == 1000
    assert res[1]["y_start"] == 500
    assert res[1]["y_end"] == 1500



def test_ocr_실패_타일_수가_리포트에_실린다(monkeypatch):
    """실패가 응답에 안 실리면 "아무것도 못 읽음"이 "문제없음"과 구분되지 않는다.

    2026-08-20 시연 점검에서 실제로 관측했다. OCR이 깨진 JSON을 뱉어 문장 0개·
    finding 0건이 나왔는데 응답에는 아무 흔적이 없어, 위반이 있는 광고가 깨끗하게
    통과한 것처럼 보였다.
    """
    from barum import pipeline as pl

    monkeypatch.setattr(pl, "_ocr_image", lambda *a, **k: ([], 2))
    monkeypatch.setattr(pl, "check_product_scope", lambda _s: (True, None))

    report = pl.run_check("KR", None, b"fake-image", "x.png", vlm=None, judge=StubJudge())

    assert report.summary.n_ocr_failed_tiles == 2
    assert report.summary.n_sentences == 0


def test_글만_검사하면_ocr_실패는_0이다():
    """이미지가 없으면 OCR을 아예 안 한다. 카운터가 안 잡히면 여기서 NameError가 난다."""
    from barum import pipeline as pl

    report = pl.run_check("KR", "수분 공급에 도움을 줍니다", None, None, vlm=None, judge=StubJudge())
    assert report.summary.n_ocr_failed_tiles == 0
