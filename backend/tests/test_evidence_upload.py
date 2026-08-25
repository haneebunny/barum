"""실증자료(임상)·설문조사 파일 파서 유닛테스트 (순수 로직, 외부 의존 없음).

    ./venv/bin/python -m pytest tests/test_evidence_upload.py -q

`_CLINICAL_SAMPLE`·`_SURVEY_SAMPLE`은 실제로 제공된 파일 그대로다. 이 둘이
설계의 출발점이었다(임상엔 헤더가 있고 설문엔 없다). 손대지 말 것.
"""

import io

import openpyxl
import pytest

from barum.preprocess.evidence_upload import (
    MAX_ROWS,
    EvidenceParseError,
    parse_clinical_upload,
    parse_survey_upload,
)

# 실제 제공된 `임상실험.txt` 원본. 탭 구분, 헤더 있음, 2행.
_CLINICAL_SAMPLE = (
    "무엇을 개선했나(claim)\t결과 수치(value)\t시험기관명(institution)\t"
    "시험기간(period)\t피험자 수·조건 등(note)\n"
    "다크스팟 개선\t87%\t유어랩 피부과학연구소\t8주\t20명 대상\n"
    "피부결 개선\t2.1배\t유어랩 피부과학연구소\t4주\t20명 대상\n"
)

# 실제 제공된 `설문조사.txt` 원본. 탭 구분, **헤더 없음**, 1행.
_SURVEY_SAMPLE = "발림성 만족\t94%\t150명\t유어리서치\t2026년 3월\t온라인 자기기입식 설문\n"


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def _make_xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── 실제 샘플 파일 ────────────────────────────────────────────────────────


def test_clinical_sample_file():
    """실제 제공된 임상 파일이 그대로 5칸 전부 들어간다."""
    rows, warnings = parse_clinical_upload(".txt", _b(_CLINICAL_SAMPLE))

    assert len(rows) == 2
    assert rows[0].claim == "다크스팟 개선"
    assert rows[0].value == "87%"
    assert rows[0].institution == "유어랩 피부과학연구소"
    assert rows[0].period == "8주"
    assert rows[0].note == "20명 대상"
    assert rows[1].claim == "피부결 개선"
    assert rows[1].value == "2.1배"
    assert rows[1].period == "4주"
    # 헤더로 다 잡혔으니 추측했다는 경고가 없어야 한다.
    assert warnings == []


def test_survey_sample_file():
    """실제 제공된 설문 파일은 **헤더가 없다.** 값의 형태만으로 6칸이 다 들어간다."""
    rows, warnings = parse_survey_upload(".txt", _b(_SURVEY_SAMPLE))

    assert len(rows) == 1
    row = rows[0]
    assert row.claim == "발림성 만족"
    assert row.value == "94%"
    assert row.sample_size == "150명"
    assert row.institution == "유어리서치"
    assert row.period == "2026년 3월"
    assert row.method == "온라인 자기기입식 설문"
    # 헤더 없이 추측했으면 반드시 알린다.
    assert any("값의 형태로 열을 읽었습니다" in w for w in warnings)


def test_survey_sample_single_row_not_eaten_as_header():
    """1행짜리 헤더 없는 파일이 헤더로 오인되면 결과가 0건이 된다.

    설문 샘플이 정확히 그 함정이다. 데이터 한 줄뿐이라 오인 = 전량 유실이고,
    사용자는 왜 비었는지 알 방법이 없다.
    """
    rows, _ = parse_survey_upload(".txt", _b(_SURVEY_SAMPLE))
    assert len(rows) == 1


# ── 헤더 없이 열 순서가 섞인 파일 ──────────────────────────────────────────


def test_clinical_shuffled_columns_without_header():
    """열 순서를 뒤집어도 값의 형태로 제자리를 찾는다."""
    text = (
        "유어랩 피부과학연구소\t8주\t87%\t20명 대상\t다크스팟 개선\n"
        "유어랩 피부과학연구소\t4주\t2.1배\t20명 대상\t피부결 개선\n"
    )
    rows, warnings = parse_clinical_upload(".txt", _b(text))

    assert len(rows) == 2
    assert rows[0].claim == "다크스팟 개선"
    assert rows[0].value == "87%"
    assert rows[0].institution == "유어랩 피부과학연구소"
    assert rows[0].period == "8주"
    assert rows[0].note == "20명 대상"
    assert any("값의 형태로 열을 읽었습니다" in w for w in warnings)


def test_survey_shuffled_columns_without_header():
    text = "온라인 설문\t유어리서치\t2026년 3월\t150명\t94%\t발림성 만족\n"
    rows, _ = parse_survey_upload(".txt", _b(text))

    assert len(rows) == 1
    row = rows[0]
    assert row.claim == "발림성 만족"
    assert row.value == "94%"
    assert row.sample_size == "150명"
    assert row.institution == "유어리서치"
    assert row.period == "2026년 3월"
    assert row.method == "온라인 설문"


def test_clinical_value_containing_period_does_not_steal_period_column():
    """`value="4주 후 2.1배"`는 실제 문서에 박힌 표기다(2026-08-24 실증자료 구조화).

    기간 판정기가 단독 표기("4주")만 잡게 앵커를 건 이유가 이것이다. 앵커가
    없으면 이 값이 period 열을 가로채고 진짜 기간이 밀린다.
    """
    text = "피부결 개선\t4주 후 2.1배\t유어랩 피부과학연구소\t4주\t20명 대상\n"
    rows, _ = parse_clinical_upload(".txt", _b(text))

    assert len(rows) == 1
    assert rows[0].value == "4주 후 2.1배"
    assert rows[0].period == "4주"
    assert rows[0].claim == "피부결 개선"


def test_survey_institution_containing_survey_word_wins_over_method():
    """기관명에 "조사"가 들어가도 기관으로 간다. 열은 먼저 잡은 필드가 가져간다."""
    text = "향에 만족\t96%\t200명\t한국갤럽조사연구소\t2026년 3월\t온라인 자기기입식\n"
    rows, _ = parse_survey_upload(".txt", _b(text))

    assert rows[0].institution == "한국갤럽조사연구소"
    assert rows[0].method == "온라인 자기기입식"


# ── 고정 순서 폴백 ────────────────────────────────────────────────────────


def test_clinical_fallback_when_shape_is_ambiguous_warns():
    """생김새로 못 잡는 값이 둘 이상이면 고정 순서로 채우고 반드시 경고한다."""
    # note가 "여성 30~50세"라 인원 패턴에 안 걸린다. claim과 함께 "나머지"가 둘.
    text = "다크스팟 개선\t87%\t유어랩 피부과학연구소\t8주\t여성 30~50세\n"
    rows, warnings = parse_clinical_upload(".txt", _b(text))

    assert len(rows) == 1
    assert rows[0].claim == "다크스팟 개선"
    assert rows[0].note == "여성 30~50세"
    assert any("확인해 주세요" in w for w in warnings)


def test_clinical_header_only_partial_falls_back_and_warns():
    """헤더가 일부 항목만 달고 있으면 나머지는 폴백하고 그 사실을 알린다."""
    text = (
        "claim\tvalue\t세 번째\t네 번째\t다섯 번째\n"
        "다크스팟 개선\t87%\t유어랩 피부과학연구소\t8주\t20명 대상\n"
    )
    rows, warnings = parse_clinical_upload(".txt", _b(text))

    assert len(rows) == 1
    assert rows[0].claim == "다크스팟 개선"
    assert rows[0].value == "87%"
    assert rows[0].institution == "유어랩 피부과학연구소"
    assert warnings  # 무엇을 어떻게 읽었는지 반드시 남는다


# ── 구분자·인코딩·형식 ────────────────────────────────────────────────────


def test_comma_separated_file():
    text = "다크스팟 개선,87%,유어랩 피부과학연구소,8주,20명 대상\n"
    rows, _ = parse_clinical_upload(".csv", _b(text))
    assert rows[0].institution == "유어랩 피부과학연구소"


def test_tab_wins_over_comma_inside_a_cell():
    """탭이 있으면 콤마는 구분자가 아니다. "2,500명"이 두 칸으로 안 쪼개진다."""
    text = "발림성 만족\t94%\t2,500명\t유어리서치\t2026년 3월\t온라인 설문\n"
    rows, _ = parse_survey_upload(".txt", _b(text))
    assert rows[0].sample_size == "2,500명"


def test_cp949_encoded_file():
    rows, _ = parse_clinical_upload(".txt", _CLINICAL_SAMPLE.encode("cp949"))
    assert rows[0].claim == "다크스팟 개선"


def test_xlsx_file():
    data = _make_xlsx(
        [
            ["무엇을 개선했나(claim)", "결과 수치(value)", "시험기관명(institution)",
             "시험기간(period)", "피험자 수·조건 등(note)"],
            ["다크스팟 개선", "87%", "유어랩 피부과학연구소", "8주", "20명 대상"],
        ]
    )
    rows, warnings = parse_clinical_upload(".xlsx", data)
    assert len(rows) == 1
    assert rows[0].period == "8주"
    assert warnings == []


def test_unsupported_extension_raises():
    with pytest.raises(EvidenceParseError):
        parse_clinical_upload(".pdf", b"whatever")


def test_empty_file_raises():
    with pytest.raises(EvidenceParseError):
        parse_clinical_upload(".txt", b"")


def test_header_only_file_raises():
    text = "무엇을 개선했나(claim)\t결과 수치(value)\t시험기관명(institution)\n"
    with pytest.raises(EvidenceParseError):
        parse_clinical_upload(".txt", _b(text))


def test_broken_xlsx_raises():
    with pytest.raises(EvidenceParseError):
        parse_clinical_upload(".xlsx", b"not a workbook")


# ── 행 단위 실패는 조용히 넘기지 않는다 ───────────────────────────────────


def test_row_missing_required_field_is_skipped_with_warning():
    text = (
        "무엇을 개선했나(claim)\t결과 수치(value)\t시험기관명(institution)\t"
        "시험기간(period)\t피험자 수·조건 등(note)\n"
        "다크스팟 개선\t87%\t유어랩 피부과학연구소\t8주\t20명 대상\n"
        "\t2.1배\t유어랩 피부과학연구소\t4주\t20명 대상\n"
        "피부결 개선\t\t유어랩 피부과학연구소\t4주\t20명 대상\n"
    )
    rows, warnings = parse_clinical_upload(".txt", _b(text))

    assert len(rows) == 1
    assert len(warnings) == 2
    assert any("3행" in w for w in warnings)
    assert any("4행" in w for w in warnings)


def test_survey_incomplete_row_is_kept_but_warned():
    """설문 6칸이 다 안 차도 버리지 않는다. 사용자가 폼에서 마저 채운다."""
    text = "발림성 만족\t94%\t150명\t유어리서치\n"
    rows, warnings = parse_survey_upload(".txt", _b(text))

    assert len(rows) == 1
    assert rows[0].claim == "발림성 만족"
    assert rows[0].method == ""
    assert any("6개 항목을 모두 채워야" in w for w in warnings)


def test_row_cap_warns_once():
    header = (
        "무엇을 개선했나(claim)\t결과 수치(value)\t시험기관명(institution)\t"
        "시험기간(period)\t피험자 수·조건 등(note)\n"
    )
    body = "".join(
        f"개선 {i}\t{i}%\t유어랩 피부과학연구소\t8주\t20명 대상\n"
        for i in range(MAX_ROWS + 5)
    )
    rows, warnings = parse_clinical_upload(".txt", _b(header + body))

    assert len(rows) == MAX_ROWS
    assert sum(1 for w in warnings if "넘는 입력은 읽지 않았습니다" in w) == 1
