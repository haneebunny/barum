"""파이프라인 조립 유닛테스트.

VLM은 가짜 객체(Protocol 충족, 네트워크 없음)로 주입하고, judge는 StubJudge를
쓴다. 외부 의존(진짜 Gemini)은 여기서 안 건드린다 = 수동 스모크로 별도 확인.

    venv/bin/python -m pytest tests/test_pipeline.py -q
"""

import io

from PIL import Image

from barum.judge.cosmetic import JudgeResult, StubJudge
from barum.pipeline import _attach_bands, run_check


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

    def judge(self, sentences, region, ingredients=None):
        self.received_ingredients = ingredients
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
