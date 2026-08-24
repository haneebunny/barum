"""전성분 파일 파서 유닛테스트 (순수 로직, 외부 의존 없음).

    ./venv/bin/python -m pytest tests/test_ingredient_upload.py -q
"""

import io

import openpyxl
import pytest

from barum.preprocess.ingredient_upload import (
    MAX_ROWS,
    IngredientParseError,
    parse_ingredient_upload,
)


def _make_xlsx(sheets: dict[str, list[list]]) -> bytes:
    """{시트명: [행, ...]} 로 워크북을 만든다. 행의 셀은 그대로 옮긴다."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pm_template_xlsx() -> bytes:
    """PM이 팀원 배포용으로 만든 양식과 같은 구조.

    시트 0_안내(헤더 없음) / 1_전성분·함량(순번·성분명·함량(%)·비고 + 예시행 +
    빈 행들) / 2_인정성분_기준표(참고)(진짜 성분표처럼 보이지만 참고용).
    """
    return _make_xlsx(
        {
            "0_안내": [["이 파일은 전성분·함량을 입력하는 양식입니다."]],
            "1_전성분·함량": [
                ["순번", "성분명", "함량(%)", "비고"],
                [1, "나이아신아마이드", "3%", "지우고 채우세요(예시)"],
                [None, None, None, None],
                [2, "히알루론산", "1%", None],
                [3, "판테놀", None, None],  # 함량 누락
                [4, None, "2%", None],  # 성분명 누락
                [None, None, None, None],
                [5, "세라마이드", "0.5%", None],
            ],
            "2_인정성분_기준표(참고)": [
                ["성분명", "함량기준"],
                ["나이아신아마이드", "2% 이상"],
                ["레티놀", "0.2% 이상"],
            ],
        }
    )


# ── xlsx ──────────────────────────────────────────────────────────────────


def test_참고_시트는_절대_안_읽는다():
    rows, _ = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    names = {r.name for r in rows}
    assert "레티놀" not in names, "참고용 기준표 시트를 읽으면 안 된다"


def test_전성분_시트를_이름으로_우선_고른다():
    rows, _ = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    names = {r.name for r in rows}
    assert "히알루론산" in names
    assert "세라마이드" in names


def test_예시행은_경고_없이_건너뛴다():
    rows, warnings = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    names = {r.name for r in rows}
    assert "나이아신아마이드" not in names, "예시행이 실제 입력처럼 들어가면 안 된다"
    assert not any("나이아신아마이드" in w for w in warnings), "예시행은 경고 대상이 아니다"


def test_빈_행은_조용히_건너뛴다():
    _, warnings = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    assert not any("3행" in w for w in warnings), "완전히 빈 행은 경고를 안 남긴다"


def test_함량_없는_행은_행번호와_함께_경고한다():
    _, warnings = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    assert any("함량이 비어" in w for w in warnings)
    assert any(w.startswith("5행") for w in warnings), "엑셀 실제 행 번호와 맞아야 한다"


def test_성분명_없는_행은_행번호와_함께_경고한다():
    _, warnings = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    assert any("성분명이 비어" in w for w in warnings)
    assert any(w.startswith("6행") for w in warnings)


def test_정상행_개수와_값이_정확하다():
    rows, _ = parse_ingredient_upload(".xlsx", _pm_template_xlsx())
    assert [(r.name, r.amount) for r in rows] == [
        ("히알루론산", "1%"),
        ("세라마이드", "0.5%"),
    ]


def test_열_순서가_바뀌어도_헤더_이름으로_찾는다():
    """비고·순번이 성분명·함량보다 앞에 와도 깨지면 안 된다."""
    data = _make_xlsx(
        {
            "성분표": [
                ["비고", "순번", "함량(%)", "성분명"],
                [None, 1, "5%", "글리세린"],
            ]
        }
    )
    rows, warnings = parse_ingredient_upload(".xlsx", data)
    assert rows == [type(rows[0])(name="글리세린", amount="5%")]
    assert warnings == []


def test_헤더를_못_찾으면_IngredientParseError():
    data = _make_xlsx({"시트1": [["아무", "관계없는", "표"], [1, 2, 3]]})
    with pytest.raises(IngredientParseError):
        parse_ingredient_upload(".xlsx", data)


def test_참고_시트만_있으면_IngredientParseError():
    data = _make_xlsx({"기준표(참고)": [["성분명", "함량기준"], ["레티놀", "0.2%"]]})
    with pytest.raises(IngredientParseError):
        parse_ingredient_upload(".xlsx", data)


def test_손상된_파일은_IngredientParseError():
    with pytest.raises(IngredientParseError):
        parse_ingredient_upload(".xlsx", b"not a real xlsx file")


def test_행_상한을_넘으면_경고하고_자른다():
    rows = [["순번", "성분명", "함량(%)", "비고"]]
    for i in range(MAX_ROWS + 10):
        rows.append([i, f"성분{i}", "1%", None])
    data = _make_xlsx({"1_전성분·함량": rows})
    result, warnings = parse_ingredient_upload(".xlsx", data)
    assert len(result) == MAX_ROWS
    assert any("200행" in w for w in warnings)


# ── csv / txt ────────────────────────────────────────────────────────────


def test_콤마_구분_csv():
    data = "성분명,함량\n나이아신아마이드,3%\n히알루론산,1%\n".encode("utf-8")
    rows, warnings = parse_ingredient_upload(".csv", data)
    assert [(r.name, r.amount) for r in rows] == [
        ("나이아신아마이드", "3%"),
        ("히알루론산", "1%"),
    ]
    assert warnings == []


def test_붙여쓴_txt_한줄():
    data = "나이아신아마이드 3%\n히알루론산 1%\n".encode("utf-8")
    rows, _ = parse_ingredient_upload(".txt", data)
    assert [(r.name, r.amount) for r in rows] == [
        ("나이아신아마이드", "3%"),
        ("히알루론산", "1%"),
    ]


def test_범위_함량도_받는다():
    data = "레티놀 0.2~0.5%\n".encode("utf-8")
    rows, _ = parse_ingredient_upload(".txt", data)
    assert rows[0].amount == "0.2~0.5%"


def test_단위_함량도_받는다():
    data = "비타민D 2,500 IU/g\n".encode("utf-8")
    rows, _ = parse_ingredient_upload(".txt", data)
    assert rows[0].name == "비타민D"
    assert rows[0].amount == "2,500 IU/g"


def test_탭_구분도_받는다():
    data = "나이아신아마이드\t3%\n".encode("utf-8")
    rows, _ = parse_ingredient_upload(".txt", data)
    assert rows == [type(rows[0])(name="나이아신아마이드", amount="3%")]


def test_빈_줄은_조용히_건너뛴다():
    data = "나이아신아마이드,3%\n\n\n히알루론산,1%\n".encode("utf-8")
    _, warnings = parse_ingredient_upload(".csv", data)
    assert warnings == []


def test_형식을_모르는_줄은_행번호와_함께_경고한다():
    data = "나이아신아마이드,3%\n이건그냥아무텍스트\n".encode("utf-8")
    _, warnings = parse_ingredient_upload(".csv", data)
    assert any(w.startswith("2행") for w in warnings)
    assert any("형식을" in w for w in warnings)


def test_cp949로_적힌_txt도_읽는다():
    """메모장 기본 저장 인코딩이 cp949일 때가 흔하다."""
    data = "나이아신아마이드,3%\n".encode("cp949")
    rows, _ = parse_ingredient_upload(".txt", data)
    assert rows[0].name == "나이아신아마이드"


def test_행_상한을_넘으면_경고하고_자른다_txt():
    lines = [f"성분{i},1%" for i in range(MAX_ROWS + 5)]
    data = "\n".join(lines).encode("utf-8")
    rows, warnings = parse_ingredient_upload(".txt", data)
    assert len(rows) == MAX_ROWS
    assert any("200행" in w for w in warnings)
