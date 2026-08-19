"""prescreen_conflict_check.py 유닛테스트. 실제 VLM은 안 부른다(가짜 객체 주입)."""

import sys

sys.path.insert(0, "scripts")
from prescreen_conflict_check import run_prescreen  # noqa: E402


class FakeVlm:
    """generate_json이 정해진 값을 순서대로 내는 가짜 VLM."""

    def __init__(self, *results):
        self._results = list(results)

    def generate_json(self, prompt, images):
        r = self._results.pop(0) if self._results else {}
        if isinstance(r, Exception):
            raise r
        return r


def _sent(nn="01", text="문장"):
    return {"nn": nn, "text": text, "span": "kw", "label": "위반"}


def test_claim_true_false를_그대로_보존한다():
    vlm = FakeVlm({"results": [{"n": 0, "claim": True}, {"n": 1, "claim": False}]})
    out = run_prescreen(vlm, [_sent(text="치유하는 힘"), _sent(text="약국 입점")])
    assert out[0]["prescreen_claim"] is True
    assert out[1]["prescreen_claim"] is False
    assert all(not r["prescreen_failed"] for r in out)


def test_배치_실패는_실패로_기록하고_계속한다():
    vlm = FakeVlm(RuntimeError("429"))
    out = run_prescreen(vlm, [_sent()])
    assert out[0]["prescreen_claim"] is None
    assert out[0]["prescreen_failed"] is True


def test_n이_없거나_개수가_같으면_순서로_대응한다():
    # n 필드가 빠졌지만 결과 개수가 문장 수와 같으면 순서로 매칭한다(RagJudge와 동일 패턴).
    vlm = FakeVlm({"results": [{"claim": False}, {"claim": True}]})
    out = run_prescreen(vlm, [_sent(text="a"), _sent(text="b")])
    assert out[0]["prescreen_claim"] is False
    assert out[1]["prescreen_claim"] is True


def test_결과가_누락되면_미판정으로_남는다():
    vlm = FakeVlm({"results": []})
    out = run_prescreen(vlm, [_sent()])
    assert out[0]["prescreen_claim"] is None
    assert out[0]["prescreen_failed"] is True


def test_12개_넘으면_배치가_나뉜다():
    vlm = FakeVlm(
        {"results": [{"n": i, "claim": True} for i in range(12)]},
        {"results": [{"n": 12, "claim": False}]},
    )
    sentences = [_sent(text=f"문장{i}") for i in range(13)]
    out = run_prescreen(vlm, sentences)
    assert len(out) == 13
    assert out[12]["prescreen_claim"] is False


# ── 누적 로그 ──


import json as _json

from prescreen_conflict_check import _log_key, append_log, load_log  # noqa: E402


def _rec(nn="01", text="문장", claim=False):
    return {"nn": nn, "text": text, "span": "kw", "label": "위반",
            "prescreen_claim": claim, "prescreen_failed": False}


def test_로그가_없으면_빈_딕셔너리(tmp_path):
    assert load_log(tmp_path / "없는파일.jsonl") == {}


def test_기록하고_다시_읽으면_그대로_나온다(tmp_path):
    p = tmp_path / "log.jsonl"
    append_log(p, [_rec(text="약국 입점")])
    log = load_log(p)
    assert len(log) == 1
    assert log[_log_key(_rec(text="약국 입점"))]["prescreen_claim"] is False


def test_같은_문장을_다시_실행하면_최신값으로_덮어쓴다(tmp_path):
    """규칙이 안 바뀐 채 재실행해도 분모가 부풀면 안 된다."""
    p = tmp_path / "log.jsonl"
    append_log(p, [_rec(text="약국 입점", claim=False)])
    append_log(p, [_rec(text="약국 입점", claim=True)])  # 재실행, 결과가 바뀜
    log = load_log(p)
    assert len(log) == 1  # 문장 수는 그대로
    assert log[_log_key(_rec(text="약국 입점"))]["prescreen_claim"] is True  # 최신값


def test_새_문장은_누적에_더해진다(tmp_path):
    """06번 갈래 신설처럼 새 규칙 위반 문장이 생기면 로그가 늘어난다."""
    p = tmp_path / "log.jsonl"
    append_log(p, [_rec(text="약국 입점")])
    append_log(p, [_rec(text="시중 제품 대비 3배")])
    log = load_log(p)
    assert len(log) == 2


def test_observed_at이_각_기록에_붙는다(tmp_path):
    p = tmp_path / "log.jsonl"
    append_log(p, [_rec()])
    line = p.read_text(encoding="utf-8").strip()
    record = _json.loads(line)
    assert "observed_at" in record
