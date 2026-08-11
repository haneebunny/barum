"""파이프라인 조립 유닛테스트.

VLM은 가짜 객체(Protocol 충족, 네트워크 없음)로 주입하고, judge는 StubJudge를
쓴다. 외부 의존(진짜 Gemini)은 여기서 안 건드린다 = 수동 스모크로 별도 확인.

    venv/bin/python -m pytest tests/test_pipeline.py -q
"""

import io

from PIL import Image

from barum.judge.cosmetic import JudgeResult, StubJudge
from barum.pipeline import run_check


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
