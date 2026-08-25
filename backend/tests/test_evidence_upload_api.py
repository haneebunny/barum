"""POST /uploads/clinical · /uploads/survey 엔드포인트 유닛테스트 (오프라인).

파싱 로직의 세부 케이스는 tests/test_evidence_upload.py를 본다. 여기서는
HTTP 계약(상태 코드·응답 스키마·확장자 판별)만 확인한다.

    ./venv/bin/python -m pytest tests/test_evidence_upload_api.py -q
"""

import io

import openpyxl
from fastapi.testclient import TestClient

from barum.api import app as app_module

client = TestClient(app_module.app)

_CLINICAL_TXT = (
    "무엇을 개선했나(claim)\t결과 수치(value)\t시험기관명(institution)\t"
    "시험기간(period)\t피험자 수·조건 등(note)\n"
    "다크스팟 개선\t87%\t유어랩 피부과학연구소\t8주\t20명 대상\n"
).encode("utf-8")

# 헤더 없는 한 줄. 실제 제공된 `설문조사.txt` 원본 형태다.
_SURVEY_TXT = (
    "발림성 만족\t94%\t150명\t유어리서치\t2026년 3월\t온라인 자기기입식 설문\n"
).encode("utf-8")


def _clinical_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["claim", "value", "institution", "period", "note"])
    ws.append(["다크스팟 개선", "87%", "유어랩 피부과학연구소", "8주", "20명 대상"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── /uploads/clinical ─────────────────────────────────────────────────────


def test_임상_txt_업로드하면_rows와_warnings를_낸다():
    r = client.post(
        "/uploads/clinical",
        files={"file": ("임상실험.txt", _CLINICAL_TXT, "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [
        {
            "claim": "다크스팟 개선",
            "value": "87%",
            "institution": "유어랩 피부과학연구소",
            "period": "8주",
            "note": "20명 대상",
        }
    ]
    assert body["warnings"] == []


def test_임상_xlsx도_받는다():
    r = client.post(
        "/uploads/clinical",
        files={
            "file": (
                "임상.xlsx",
                _clinical_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200
    assert r.json()["rows"][0]["period"] == "8주"


def test_임상_지원하지_않는_확장자는_415():
    r = client.post(
        "/uploads/clinical",
        files={"file": ("성적서.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 415
    assert "지원하지 않는" in r.json()["detail"]


def test_임상_빈_파일은_422():
    r = client.post(
        "/uploads/clinical",
        files={"file": ("임상.txt", b"", "text/plain")},
    )
    assert r.status_code == 422


def test_임상_헤더만_있으면_422와_사람이_읽을_사유():
    only_header = (
        "무엇을 개선했나(claim)\t결과 수치(value)\t시험기관명(institution)\n"
    ).encode("utf-8")
    r = client.post(
        "/uploads/clinical",
        files={"file": ("임상.txt", only_header, "text/plain")},
    )
    assert r.status_code == 422
    assert "내용이 없습니다" in r.json()["detail"]


# ── /uploads/survey ───────────────────────────────────────────────────────


def test_설문_헤더_없는_한_줄도_읽고_추측했음을_알린다():
    """설문 원본에는 헤더가 없다. 읽되 어떻게 읽었는지 반드시 같이 낸다."""
    r = client.post(
        "/uploads/survey",
        files={"file": ("설문조사.txt", _SURVEY_TXT, "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [
        {
            "claim": "발림성 만족",
            "value": "94%",
            "sample_size": "150명",
            "institution": "유어리서치",
            "period": "2026년 3월",
            "method": "온라인 자기기입식 설문",
        }
    ]
    assert any("값의 형태로 열을 읽었습니다" in w for w in body["warnings"])


def test_설문_미완_행도_돌려주되_경고한다():
    partial = "발림성 만족\t94%\t150명\t유어리서치\n".encode("utf-8")
    r = client.post(
        "/uploads/survey",
        files={"file": ("설문조사.txt", partial, "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["method"] == ""
    assert any("6개 항목을 모두 채워야" in w for w in body["warnings"])


def test_설문_지원하지_않는_확장자는_415():
    r = client.post(
        "/uploads/survey",
        files={"file": ("설문.pptx", b"PK", "application/vnd.ms-powerpoint")},
    )
    assert r.status_code == 415
