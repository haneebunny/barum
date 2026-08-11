"""score_eval.judge_batch 파싱 유닛테스트 (순수 로직, VLM 가짜 주입).

실채점은 xlsx·실 VLM이 필요해 수동으로 돌린다. 여기선 응답 파싱만 테스트한다.

    ./venv/bin/python -m pytest tests/test_score_eval.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import score_eval  # noqa: E402


class ListVLM:
    """dict 대신 통짜 리스트를 뱉는 VLM(실모델이 가끔 이런다)."""

    def generate_json(self, prompt, images):
        return [{"n": 0, "label": "합법"}]


class DictVLM:
    """정상적으로 {"results": [...]}를 뱉는 VLM."""

    def generate_json(self, prompt, images):
        return {"results": [{"n": 0, "label": "1호_의약품오인", "reason": "재생"}]}


def test_judge_batch_survives_list_response():
    """VLM이 dict 대신 리스트를 뱉어도 배치가 안 터지고 빈 결과를 낸다.

    이게 안 되면 판정 도중 한 배치만 리스트를 뱉어도 채점 전체가 500으로 죽는다.
    """
    out = score_eval.judge_batch(ListVLM(), [{"n": 0, "text": "피부 재생"}])
    assert out == {}


def test_judge_batch_parses_dict_response():
    """정상 dict 응답은 번호→(라벨,근거)로 파싱한다(회귀 방지)."""
    out = score_eval.judge_batch(DictVLM(), [{"n": 0, "text": "피부 재생"}])
    assert out == {0: ("1호_의약품오인", "재생")}
