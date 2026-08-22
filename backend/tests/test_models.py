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
    assert dumped["location"] == {
        "tile": "source_t00.png",
        "order": 0,
        "x_start": None,
        "x_end": None,
        "y_start": None,
        "y_end": None,
        "source_h": None,
        "source_w": None,
        "source": None,
    }


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


def test_location_carries_band_coordinates():
    """이미지 입력이면 타일 밴드 좌표(y_start,y_end)와 원본 크기를 싣는다."""
    loc = Location(
        tile="source_t01.png", order=2, y_start=1400, y_end=2820,
        source_h=9000, source_w=1000,
    )
    d = loc.model_dump(mode="json")
    assert d["y_start"] == 1400
    assert d["y_end"] == 2820
    assert d["source_h"] == 9000
    assert d["source_w"] == 1000


def test_location_coordinates_default_none():
    """텍스트 입력엔 좌표가 없다 — 기본값 None(밴드 하이라이트 스킵 신호)."""
    loc = Location(tile=None, order=0)
    assert loc.y_start is None
    assert loc.y_end is None
    assert loc.source_h is None
    assert loc.source_w is None


def test_judgment_flag_is_binary():
    """v1.8: 위험도(고/중/저) 폐지, 위반/검토필요 이진 플래그만 존재한다."""
    assert {v.value for v in JudgmentFlag} == {"위반", "검토필요"}


def test_summary_defaults_violation_and_review_counts_to_zero():
    s = Summary(region=Region.KR, n_sentences=1, n_findings=0)
    assert s.n_violation == 0
    assert s.n_needs_review == 0
    assert s.n_unjudged == 0


def test_저장된_리포트를_다시_읽어도_대체표현이_남는다():
    """다시 보기 경로 계약. 리포트가 JSON으로 저장됐다 다시 뜨므로 대체표현도 같이 산다.

    이게 성립해야 "다시 보기는 LLM 호출 0회"가 참이 된다(2026-08-22).
    """
    from barum.models import CheckReport, Region, Replacement, Summary, ViolationType

    report = CheckReport(
        findings=[],
        summary=Summary(region=Region("KR"), n_sentences=1, n_findings=1),
        replacements=[
            Replacement(
                original="미백",
                replaced="피부 톤을 환하게 가꿔줍니다.",
                violation_type=ViolationType.type_2_functional_misperception,
                basis="합법 표기 틀(조건표) 기반 대체 표현",
                finding_index=0,
            )
        ],
    )
    revived = CheckReport(**report.model_dump())
    assert revived.replacements[0].finding_index == 0
    assert revived.replacements[0].replaced == "피부 톤을 환하게 가꿔줍니다."


def test_대체표현_필드_이전에_저장된_리포트도_읽힌다():
    """옛 리포트에는 replacements 키가 없다. 그것도 그대로 열려야 한다."""
    from barum.models import CheckReport

    old = {
        "findings": [],
        "summary": {"region": "KR", "n_sentences": 1, "n_findings": 0},
    }
    assert CheckReport(**old).replacements == []
