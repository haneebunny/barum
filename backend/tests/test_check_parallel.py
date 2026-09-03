"""/check 배치 병렬화가 결과 순서·내용을 바꾸지 않는지 못박는다.

OCR·1차필터·판정은 배치를 동시에 보내되 결과는 입력 순서대로 되짚어야 한다.
가짜 VLM이 **뒤 배치일수록 먼저 답하게** 지연을 줘, 순서가 완료 순이 아니라
입력 순인지 확인한다.

    ./venv/bin/python -m pytest tests/test_check_parallel.py -q
"""
import re
import time
from pathlib import Path

from barum.judge.cosmetic import PromptJudge, RagJudge
from barum.parallel import run_in_order
from barum.preprocess.ocr import extract_product_sentences


def _sentences(texts: list[str]) -> list[dict]:
    return [{"order": i, "tile": None, "text": t} for i, t in enumerate(texts)]


def _numbered_lines(prompt: str) -> list[tuple[int, str]]:
    """프롬프트 안의 'N. 문장' 줄을 (N, 문장)으로 뽑는다."""
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"^(\d+)\. (.+)$", prompt, re.M)]


# ── run_in_order ──────────────────────────────────────────────────────────

def test_run_in_order_returns_input_order_and_keeps_exceptions_in_place():
    def slow_reverse(i: int) -> int:
        time.sleep((5 - i) * 0.01)  # 뒤 항목이 먼저 끝난다
        if i == 2:
            raise ValueError("boom")
        return i * 10

    out = run_in_order(slow_reverse, range(5), workers=5)
    assert [o if not isinstance(o, Exception) else "ERR" for o in out] == [0, 10, "ERR", 30, 40]
    assert isinstance(out[2], ValueError)


def test_run_in_order_single_worker_matches_parallel():
    assert run_in_order(lambda x: x + 1, [1, 2, 3], workers=1) == [2, 3, 4]
    assert run_in_order(lambda x: x + 1, [1, 2, 3], workers=3) == [2, 3, 4]


# ── PromptJudge ───────────────────────────────────────────────────────────

class LaterBatchesAnswerFirstVLM:
    """문장 번호로 라벨을 정하고, 앞 배치일수록 늦게 답하는 가짜 판정 VLM."""

    def __init__(self, labels: dict[str, str], fail_text: str | None = None):
        self._labels = labels
        self._fail_text = fail_text
        self.calls = 0

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        self.calls += 1
        lines = _numbered_lines(prompt)
        first_n = lines[0][0]
        time.sleep(max(0, 4 - first_n) * 0.02)
        if self._fail_text and any(self._fail_text == t for _, t in lines):
            raise ValueError("VLM이 빈 응답을 반환했다")
        return {"results": [{"n": n, "label": self._labels[t], "reason": t} for n, t in lines]}


def test_prompt_judge_findings_follow_input_order_not_completion_order():
    texts = ["피부 재생 A", "보습 B", "주름 개선 C", "여드름 치료 D", "미백 E"]
    labels = {
        "피부 재생 A": "1호_의약품오인",
        "보습 B": "합법",
        "주름 개선 C": "2호_기능성오인",
        "여드름 치료 D": "1호_의약품오인",
        "미백 E": "2호_기능성오인",
    }
    vlm = LaterBatchesAnswerFirstVLM(labels)
    res = PromptJudge(vlm, batch_size=1).judge(_sentences(texts), "KR")

    assert vlm.calls == 5
    assert [f.sentence for f in res.findings] == ["피부 재생 A", "주름 개선 C", "여드름 치료 D", "미백 E"]
    assert [f.location.order for f in res.findings] == [0, 2, 3, 4]
    assert res.unjudged == []


def test_prompt_judge_failed_batch_is_unjudged_others_survive():
    texts = ["피부 재생 A", "보습 B", "주름 개선 C"]
    labels = {"피부 재생 A": "1호_의약품오인", "보습 B": "합법", "주름 개선 C": "2호_기능성오인"}
    vlm = LaterBatchesAnswerFirstVLM(labels, fail_text="보습 B")
    res = PromptJudge(vlm, batch_size=1).judge(_sentences(texts), "KR")

    assert [f.sentence for f in res.findings] == ["피부 재생 A", "주름 개선 C"]
    assert [u.sentence for u in res.unjudged] == ["보습 B"]


# ── 1차필터 ───────────────────────────────────────────────────────────────

class LaterBatchesAnswerFirstPrescreenVLM:
    def __init__(self, drop: set[str]):
        self._drop = drop
        self.calls = 0

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        self.calls += 1
        lines = _numbered_lines(prompt)
        time.sleep(max(0, 4 - lines[0][0]) * 0.02)
        return {"results": [{"n": n, "claim": t not in self._drop} for n, t in lines]}


def test_prescreen_keeps_claim_and_dropped_order():
    texts = ["문장0", "문장1", "문장2", "문장3", "문장4"]
    vlm = LaterBatchesAnswerFirstPrescreenVLM(drop={"문장1", "문장3"})
    judge = RagJudge(vlm, batch_size=1)
    claims = judge._prescreen(_sentences(texts))

    assert vlm.calls == 5
    assert [c["text"] for c in claims] == ["문장0", "문장2", "문장4"]
    assert [d["text"] for d in judge.last_dropped] == ["문장1", "문장3"]


# ── OCR ───────────────────────────────────────────────────────────────────

class LaterTilesAnswerFirstOCRVLM:
    """타일 바이트에 적힌 이름으로 문장을 만들고, 앞 배치일수록 늦게 답한다."""

    def __init__(self, fail_tile: str | None = None):
        self._fail_tile = fail_tile
        self.calls = 0

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        self.calls += 1
        names = [b.decode() for b in images]
        idx = int(names[0][1:3])
        time.sleep(max(0, 6 - idx) * 0.02)
        if self._fail_tile in names:
            raise ValueError("429")
        if len(images) == 1:
            return {"sentences": [f"{names[0]} 문장"]}
        return {"images": [{"i": i, "sentences": [f"{n} 문장", "공통 슬로건"]} for i, n in enumerate(names)]}


def _make_tiles(tmp_path: Path, n: int) -> Path:
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    for i in range(n):
        (tiles / f"t{i:02d}.png").write_bytes(f"t{i:02d}".encode())
    return tmp_path


def test_ocr_sentences_follow_tile_order_and_dedup_keeps_first(tmp_path):
    product = _make_tiles(tmp_path, 7)  # 3장씩 3배치(3,3,1)
    vlm = LaterTilesAnswerFirstOCRVLM()
    rec = extract_product_sentences(product, vlm, verbose=False, batch_size=3)

    assert vlm.calls == 3
    assert [s["text"] for s in rec["sentences"]] == [
        "t00 문장", "공통 슬로건", "t01 문장", "t02 문장", "t03 문장", "t04 문장", "t05 문장", "t06 문장",
    ]
    assert [s["order"] for s in rec["sentences"]] == list(range(8))
    assert rec["sentences"][1]["tile"] == "t00.png"  # 중복은 처음 나온 타일 것만 남는다
    assert rec["tiles_failed"] == []


def test_ocr_failed_batch_is_skipped_others_keep_order(tmp_path):
    product = _make_tiles(tmp_path, 6)
    vlm = LaterTilesAnswerFirstOCRVLM(fail_tile="t01")
    rec = extract_product_sentences(product, vlm, verbose=False, batch_size=3)

    assert rec["tiles_failed"] == ["t00.png", "t01.png", "t02.png"]
    assert [s["text"] for s in rec["sentences"]] == ["t03 문장", "공통 슬로건", "t04 문장", "t05 문장"]
    assert rec["tiles_ok"] == 3
