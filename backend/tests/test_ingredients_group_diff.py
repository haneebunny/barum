"""ingredients_group_diff.py의 순수 로직(그룹 필터·집계) 유닛테스트.

xlsx 실호출은 안 한다(스모크는 backend/에서
`python scripts/ingredients_group_diff.py --baseline ... --current ...`).
"""

import sys

sys.path.insert(0, "scripts")
from ingredients_group_diff import _in_group, group_rate  # noqa: E402


def _row(nn, hit, review_kind="", label="검토필요"):
    return {"nn": nn, "sentence": "x", "label": label, "hit": hit, "review_kind": review_kind}


def test_그룹_필터가_소속_이미지만_고른다():
    in_a = _in_group({"01", "02"})
    assert in_a(_row("01", True)) is True
    assert in_a(_row("03", True)) is False


def test_그룹_필터_반전이_대조군을_고른다():
    not_a = _in_group({"01", "02"}, invert=True)
    assert not_a(_row("01", True)) is False
    assert not_a(_row("03", True)) is True


def test_group_rate가_정탐과_전체를_센다():
    rows = [
        _row("01", True, "정보부족형"),
        _row("01", False, "정보부족형"),
        _row("02", True, "위반의심형"),
    ]
    in_a = _in_group({"01"})
    result = group_rate(rows, lambda r: r["review_kind"] == "정보부족형", in_a)
    assert result == (1, 2)


def test_group_rate는_다른_review_kind를_안_센다():
    """오탐 행(사람 판정=합법/대상외)은 review_kind가 빈 문자열이라 안 잡혀야 한다.

    같은 텍스트가 정탐(검토필요)·오탐(합법/대상외)으로 두 번 나오는 실제 사례
    (2026-08-18, 이미지26 "HAS2..." 발견)의 회귀 방지용이다.
    """
    rows = [
        _row("01", True, review_kind="정보부족형", label="검토필요"),
        _row("01", False, review_kind="", label="합법/대상외"),  # 우연히 텍스트 겹친 오탐 행
    ]
    in_a = _in_group({"01"})
    result = group_rate(rows, lambda r: r["review_kind"] == "정보부족형", in_a)
    assert result == (1, 1)  # 오탐 행은 분모에도 안 들어가야 한다


def test_해당하는_문장이_없으면_None():
    rows = [_row("01", True, "정보부족형")]
    in_b = _in_group({"01"}, invert=True)
    assert group_rate(rows, lambda r: r["review_kind"] == "정보부족형", in_b) is None


def test_위반_라벨은_review_kind_없이_label로_직접_거른다():
    rows = [_row("01", True, label="위반"), _row("01", False, label="위반")]
    in_a = _in_group({"01"})
    result = group_rate(rows, lambda r: r["label"] == "위반", in_a)
    assert result == (1, 2)
