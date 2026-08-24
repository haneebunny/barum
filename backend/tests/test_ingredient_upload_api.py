"""POST /uploads/ingredients 엔드포인트 유닛테스트 (오프라인, 외부 호출 없음).

파싱 로직 자체의 세부 케이스는 tests/test_ingredient_upload.py를 본다. 여기서는
HTTP 계약(상태 코드·스키마·확장자 판별)만 확인한다.

    ./venv/bin/python -m pytest tests/test_ingredient_upload_api.py -q
"""

import io

import openpyxl
from fastapi.testclient import TestClient

from barum.api import app as app_module

client = TestClient(app_module.app)


def _xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "1_전성분·함량"
    ws.append(["성분명", "함량(%)"])
    ws.append(["나이아신아마이드", "3%"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_업로드하면_rows와_warnings를_낸다():
    r = client.post(
        "/uploads/ingredients",
        files={
            "file": (
                "성분표.xlsx",
                _xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [{"name": "나이아신아마이드", "amount": "3%"}]
    assert body["warnings"] == []


def test_csv_업로드도_받는다():
    csv_bytes = "성분명,함량\n히알루론산,1%\n".encode("utf-8")
    r = client.post(
        "/uploads/ingredients",
        files={"file": ("성분표.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["rows"] == [{"name": "히알루론산", "amount": "1%"}]


def test_txt_업로드도_받는다():
    r = client.post(
        "/uploads/ingredients",
        files={"file": ("성분표.txt", "판테놀 2%\n".encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["rows"] == [{"name": "판테놀", "amount": "2%"}]


def test_지원하지_않는_확장자는_415():
    r = client.post(
        "/uploads/ingredients",
        files={"file": ("성분표.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 415


def test_빈_파일은_422():
    r = client.post(
        "/uploads/ingredients",
        files={"file": ("성분표.txt", b"", "text/plain")},
    )
    assert r.status_code == 422


def test_헤더_없는_xlsx는_422():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["아무", "표"])
    buf = io.BytesIO()
    wb.save(buf)

    r = client.post(
        "/uploads/ingredients",
        files={
            "file": (
                "성분표.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 422


def test_손상된_xlsx는_422():
    r = client.post(
        "/uploads/ingredients",
        files={
            "file": (
                "성분표.xlsx",
                b"not a real xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 422


def test_확장자_없는_파일은_415():
    r = client.post(
        "/uploads/ingredients",
        files={"file": ("성분표", b"data", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_너무_큰_파일은_413(monkeypatch):
    import barum.api.app as app_module_ref

    monkeypatch.setattr(app_module_ref, "_MAX_INGREDIENT_FILE_BYTES", 10)
    r = client.post(
        "/uploads/ingredients",
        files={"file": ("성분표.txt", b"0123456789012345", "text/plain")},
    )
    assert r.status_code == 413
