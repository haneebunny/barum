# -*- coding: utf-8 -*-
"""1차 필터 A/B 도구의 라벨 매핑 테스트.

이 매핑이 틀리면 양방향 지표가 통째로 틀어지는데, 실행해도 그럴듯한 숫자가 나와서
눈으로는 안 보인다. 순수 함수라 오프라인으로 잠근다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prescreen_ab import expect_for  # noqa: E402

PROBE = ROOT / "tests" / "fixtures" / "prescreen_probe.json"


def test_위반과_검토필요는_판정기가_봐야_한다():
    assert expect_for("위반", "5호_거짓과장기만") == "pass"
    assert expect_for("검토필요", "") == "pass"
    # 963셋은 검토필요 대부분에 유형을 안 매긴다. 유형이 비어도 통과 대상이다.
    assert expect_for("검토필요", None) == "pass"


def test_대상외는_걸러야_한다():
    assert expect_for("", "대상외") == "drop"


def test_합법은_채점에서_뺀다():
    # 버려도 최종 판정이 미플래그로 같다. 채점에 넣으면 "합법을 많이 버렸다"가
    # 개선처럼 보인다.
    assert expect_for("", "합법") == "skip"


def test_애매는_채점_대상이_아니다():
    assert expect_for("", "애매") is None
    assert expect_for(None, None) is None


def test_탐침셋은_양방향이다():
    """한 방향만 있는 탐침셋은 오탐을 못 잡는다(2026-08-20 회고 규칙 6)."""
    d = json.loads(PROBE.read_text(encoding="utf-8"))
    assert d["must_pass"] and d["must_drop"], "양방향 둘 다 있어야 한다"
    for key in ("must_pass", "must_drop"):
        for item in d[key]:
            assert item.get("근거"), f"{key}: 출처 없는 탐침은 넣지 않는다 — {item['text']}"


def test_탐침_문장이_겹치지_않는다():
    d = json.loads(PROBE.read_text(encoding="utf-8"))
    texts = [i["text"] for k in ("must_pass", "must_drop", "borderline") for i in d[k]]
    assert len(texts) == len(set(texts))


def test_채택안이_운영_프롬프트와_같다():
    """측정한 것과 배포된 것이 어긋나면 실행해도 안 보인다.

    2026-08-20 프롬프트 A/B에서 변형이 코드에 안 남아 재실행이 아니라 재구현을
    해야 했던 이력이 있다. 기준안(A)과 기각안(B)도 스크립트에 리터럴로 남긴다.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from barum.judge.cosmetic import PRESCREEN_PROMPT

    from prescreen_ab import ADOPTED, VARIANTS

    assert PRESCREEN_PROMPT == VARIANTS[ADOPTED]
    assert VARIANTS["A"] != VARIANTS["C"], "기준안이 채택안으로 덮이면 A/B를 다시 못 돌린다"
