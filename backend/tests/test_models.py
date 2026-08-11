"""I/O 계약 모델 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_models.py -q
"""

from barum.models import (
    CheckReport,
    Finding,
    JudgmentFlag,
    Location,
    Region,
    StoredCheck,
    Summary,
    ViolationType,
)


def _empty_report() -> CheckReport:
    return CheckReport(
        findings=[], summary=Summary(region=Region.KR, n_sentences=0, n_findings=0)
    )


def test_check_report_result_id_defaults_none_and_serializes():
    """result_id는 선택 필드 — 기본 None(미저장), 저장되면 채워진다."""
    r = _empty_report()
    assert r.result_id is None
    r.result_id = "aBc-123"
    assert r.model_dump(mode="json")["result_id"] == "aBc-123"


def test_stored_check_wraps_report():
    """다시 보기 응답: 리포트를 감싸고 저장 메타(생성시각·이미지유무)를 얹는다."""
    sc = StoredCheck(
        result_id="rid",
        created_at="2026-08-11T00:00:00Z",
        region=Region.KR,
        image_available=True,
        report=_empty_report(),
    )
    d = sc.model_dump(mode="json")
    assert d["result_id"] == "rid"
    assert d["image_available"] is True
    assert d["report"]["findings"] == []


def test_violation_type_labels():
    """직렬화 값은 한국어 라벨(reference/cosmetic_kr 기준). 3호는 없다."""
    assert ViolationType.type_1_drug_misperception.value == "1호_의약품오인"
    assert ViolationType.type_2_functional_misperception.value == "2호_기능성오인"
    assert ViolationType.type_5_deception.value == "5호_거짓과장기만"
    assert {v.value for v in ViolationType} == {
        "합법",
        "1호_의약품오인",
        "2호_기능성오인",
        "5호_거짓과장기만",
        "대상외",
    }


def test_finding_json_serializes_korean():
    """finding을 JSON으로 덤프하면 위반유형·판정 플래그가 한국어 문자열로 나간다."""
    f = Finding(
        span="미백",
        sentence="멜라닌을 막아 미백에 도움",
        violation_type=ViolationType.type_2_functional_misperception,
        legal_basis="화장품법 제13조 제1항 제2호",
        flag=JudgmentFlag.needs_review,
        explanation="기능성 효능 주장",
        location=Location(tile="source_t00.png", order=0),
    )
    dumped = f.model_dump(mode="json")
    assert dumped["violation_type"] == "2호_기능성오인"
    assert dumped["flag"] == "검토필요"
    assert dumped["location"] == {"tile": "source_t00.png", "order": 0}


def test_check_report_roundtrips():
    """CheckReport가 조립·직렬화된다."""
    report = CheckReport(
        findings=[],
        summary=Summary(region=Region.KR, n_sentences=3, n_findings=0),
    )
    dumped = report.model_dump(mode="json")
    assert dumped["summary"]["region"] == "KR"
    assert dumped["summary"]["counts_by_type"] == {}
    assert dumped["findings"] == []


def test_judgment_flag_is_binary():
    """v1.8: 위험도(고/중/저) 폐지, 위반/검토필요 이진 플래그만 존재한다."""
    assert {v.value for v in JudgmentFlag} == {"위반", "검토필요"}


def test_summary_defaults_violation_and_review_counts_to_zero():
    s = Summary(region=Region.KR, n_sentences=1, n_findings=0)
    assert s.n_violation == 0
    assert s.n_needs_review == 0
    assert s.n_unjudged == 0
