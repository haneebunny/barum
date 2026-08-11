"""I/O 계약 모델 유닛테스트 (외부 의존 없음).

    venv/bin/python -m pytest tests/test_models.py -q
"""

from barum.models import (
    CheckReport,
    Finding,
    Location,
    Region,
    RiskLevel,
    Summary,
    ViolationType,
)


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
    """finding을 JSON으로 덤프하면 위반유형·위험도가 한국어 문자열로 나간다."""
    f = Finding(
        span="미백",
        sentence="멜라닌을 막아 미백에 도움",
        violation_type=ViolationType.type_2_functional_misperception,
        legal_basis="화장품법 제13조 제1항 제2호",
        risk=RiskLevel.medium,
        explanation="기능성 효능 주장",
        location=Location(tile="source_t00.png", order=0),
    )
    dumped = f.model_dump(mode="json")
    assert dumped["violation_type"] == "2호_기능성오인"
    assert dumped["risk"] == "중"
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
