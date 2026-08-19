"""rule_sweep.py의 순수 로직(요약 집계·diff 계산·태깅) 유닛테스트.

xlsx·match_rule 실호출은 안 한다(run_sweep은 스모크로 확인, backend/에서
`python scripts/rule_sweep.py diff --baseline <스냅샷>`).
"""

import sys

sys.path.insert(0, "scripts")
from rule_sweep import (  # noqa: E402
    _classify_change,
    compute_diff,
    summarize,
    swallowed_rows,
)


def test_위반_라벨_탐지_건수를_센다():
    sweep = {
        "01||문장A": ["위반", "violation", "치료"],
        "01||문장B": ["위반", "none", ""],
        "02||문장C": ["합법", "none", ""],
    }
    s = summarize(sweep)
    assert s == {"tp": 1, "total_violation": 2, "fp": 0, "swallowed": 0}


def test_판단필요_라벨이_legal_allow로_확정되면_증발로_센다():
    """legal_allow·out_of_scope는 finding도 안 만들고 VLM에도 안 넘긴다.

    tp(위반->violation)에도 fp(합법->violation)에도 안 잡혀 요약만 보면 안 보이던
    사각지대다. '애매'는 tp·fp 어느 정의에도 없는 라벨이라 특히 잘 숨는다.
    """
    sweep = {
        "01||문장A": ["검토필요", "legal_allow", "민감"],
        "02||문장B": ["애매", "legal_allow", "탄력"],
        "03||문장C": ["위반", "out_of_scope", "짜개"],
        "04||문장D": ["합법", "legal_allow", "탄력"],  # 합법은 증발이 아니라 정상 동작
        "05||문장E": ["검토필요", "none", ""],  # 미매칭은 VLM행이라 증발 아님
    }
    assert summarize(sweep)["swallowed"] == 3


def test_증발_내역을_뽑는다():
    sweep = {
        "01||문장A": ["검토필요", "legal_allow", "민감"],
        "02||문장B": ["합법", "legal_allow", "탄력"],
    }
    assert swallowed_rows(sweep) == [("01", "검토필요", "민감", "문장A")]


def test_합법_대상외에_violation_뜨면_규칙오탐으로_센다():
    sweep = {
        "01||문장A": ["합법", "violation", "재생"],
        "02||문장B": ["대상외", "violation", "여드름"],
        "03||문장C": ["검토필요", "violation", "치료"],  # 검토필요는 오탐 집계 대상 아님
    }
    s = summarize(sweep)
    assert s["fp"] == 2


def test_위반_신규포착은_개선으로_태깅한다():
    assert _classify_change("위반", "none", "violation") == "개선(위반 신규포착)"


def test_위반_놓침은_악화로_태깅한다():
    assert _classify_change("위반", "violation", "none") == "악화(위반 놓침)"


def test_합법_오탐_신규는_오탐신규로_태깅한다():
    assert _classify_change("합법", "none", "violation") == "오탐신규"


def test_대상외_오탐_해소는_오탐해소로_태깅한다():
    assert _classify_change("대상외", "violation", "none") == "오탐해소"


def test_검토필요_라벨은_태그가_없다():
    # 위반·합법·대상외만 개선/악화 판단 대상이다. 검토필요는 이 도구 범위 밖.
    assert _classify_change("검토필요", "none", "violation") == ""


def test_outcome이_같으면_diff에_안_잡힌다():
    baseline = {"01||문장A": ["위반", "violation", "치료"]}
    current = {"01||문장A": ["위반", "violation", "치료"]}
    assert compute_diff(baseline, current) == []


def test_outcome이_바뀐_문장만_diff에_잡힌다():
    baseline = {
        "01||문장A": ["위반", "none", ""],
        "02||문장B": ["합법", "none", ""],
    }
    current = {
        "01||문장A": ["위반", "violation", "치료"],
        "02||문장B": ["합법", "none", ""],
    }
    diff = compute_diff(baseline, current)
    assert len(diff) == 1
    assert diff[0]["nn"] == "01"
    assert diff[0]["tag"] == "개선(위반 신규포착)"


def test_정답셋이_바뀌어_한쪽에만_있는_문장은_무시한다():
    """이 도구는 규칙집 변경 영향만 본다. 정답셋 변경은 범위 밖이라 조용히 건너뛴다."""
    baseline = {"01||옛문장": ["위반", "none", ""]}
    current = {"01||새문장": ["위반", "violation", "치료"]}
    assert compute_diff(baseline, current) == []
