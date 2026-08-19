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
