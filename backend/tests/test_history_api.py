"""검사 이력 저장·조회·이미지 프록시 API 유닛테스트 (Supabase 가짜 주입).

이미지 POST는 OCR 실호출이라, 저장은 텍스트 입력으로 테스트하고 이미지 프록시는
사전 적재로 테스트한다(네트워크 없음). 판정은 stub.

    ./venv/bin/python -m pytest tests/test_history_api.py -q
"""

import os
from types import SimpleNamespace

os.environ["JUDGE_KIND"] = "stub"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from barum.api import app as app_module  # noqa: E402

client = TestClient(app_module.app)


class _FakeTable:
    def __init__(self, store):
        self._store = store
        self._insert = None
        self._eq_id = None
        self._eq_column = None

    def insert(self, row):
        self._insert = row
        return self

    def select(self, *a):
        return self

    def eq(self, col, val):
        self._eq_column = col
        self._eq_id = val
        return self

    def limit(self, n):
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        if self._insert is not None:
            self._store.rows[self._insert["id"]] = self._insert
            return SimpleNamespace(data=[self._insert])
        if self._eq_id is not None:
            if self._eq_column == "region":
                return SimpleNamespace(data=[row for row in self._store.rows.values() if row.get("region") == self._eq_id])
            row = self._store.rows.get(self._eq_id)
            return SimpleNamespace(data=[row] if row else [])
        return SimpleNamespace(data=list(self._store.rows.values()))


class _FakeBucket:
    def __init__(self, store):
        self._store = store

    def upload(self, path, data, opts):
        self._store.images[path] = data

    def download(self, path):
        return self._store.images[path]


class _FakeStorage:
    def __init__(self, store):
        self._store = store

    def list_buckets(self):
        return []

    def create_bucket(self, name, options=None):
        pass

    def from_(self, bucket):
        return _FakeBucket(self._store)


class FakeCheckClient:
    def __init__(self):
        self.rows = {}
        self.images = {}
        self.storage = _FakeStorage(self)

    def table(self, name):
        return _FakeTable(self)


@pytest.fixture
def fake(monkeypatch):
    c = FakeCheckClient()
    monkeypatch.setenv("CHECKS_PERSIST", "1")
    monkeypatch.setattr(app_module, "_checks_client", lambda: c)
    return c


def test_check_text_returns_result_id_and_saves(fake):
    """텍스트 검사도 저장되고 result_id가 응답에 실린다(이미지 필드는 null)."""
    r = client.post("/check", data={"region": "KR", "ad_text": "미백에 도움. 순한 보습."})
    assert r.status_code == 200
    rid = r.json()["result_id"]
    assert rid and len(rid) >= 32
    assert rid in fake.rows
    saved = fake.rows[rid]
    assert saved["region"] == "KR"
    assert saved["image_sha256"] is None  # 텍스트 입력이라 이미지 없음
    assert saved["report"]["summary"]["n_findings"] >= 1


def test_check_persists_input_snapshot_without_changing_check_response(fake):
    response = client.post(
        "/check",
        data={
            "region": "KR",
            "ad_text": "Moisturizes dry skin",
            "ingredients": "Water, Glycerin",
            "product_name": "Demo Cream",
            "domestic_category": "skincare",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "input_snapshot" not in body

    snapshot = fake.rows[body["result_id"]]["report"]["input_snapshot"]
    assert snapshot["source_report_id"] == body["result_id"]
    assert snapshot["source_region"] == "KR"
    assert snapshot["ad_text_raw"] == "Moisturizes dry skin"
    assert snapshot["normalized_ingredients"] == ["Water", "Glycerin"]
    assert snapshot["product_name"] == "Demo Cream"

    detail = client.get(f"/reports/{body['result_id']}")
    assert detail.status_code == 200
    assert detail.json()["input_snapshot"]["schema_version"] == "1"


def test_filename_only_ingredient_input_is_not_judged_as_an_ingredient(fake):
    response = client.post(
        "/check",
        data={"region": "KR", "ad_text": "Moisturizes dry skin", "ingredients": "ingredients.xlsx"},
    )
    assert response.status_code == 200
    snapshot = fake.rows[response.json()["result_id"]]["report"]["input_snapshot"]
    assert snapshot["ingredients_input_kind"] == "FILENAME_ONLY"
    assert snapshot["normalized_ingredients"] == []
    assert "ingredients_input_looks_like_filename" in snapshot["warnings"]


def test_domestic_report_list_and_us_rerun_require_explicit_category(fake):
    source = client.post(
        "/check",
        data={
            "region": "KR",
            "ad_text": "SPF 30 sun protection",
            "ingredients": "Water, Glycerin",
            "product_name": "Demo Sun Cream",
        },
    )
    assert source.status_code == 200
    source_id = source.json()["result_id"]

    history = client.get("/reports", params={"region": "KR"})
    assert history.status_code == 200
    item = next(item for item in history.json() if item["result_id"] == source_id)
    assert item["snapshot_available"] is True
    assert "ad_text" in item["input_materials"]
    assert "ingredients" in item["input_materials"]

    rerun = client.post(f"/reports/{source_id}/export-readiness")
    assert rerun.status_code == 422
    assert rerun.json()["detail"]["code"] == "DOMESTIC_CATEGORY_REQUIRED"


def test_domestic_report_us_rerun_accepts_snapshot_category(fake):
    source = client.post(
        "/check",
        data={
            "region": "KR",
            "ad_text": "SPF 30 sun protection",
            "ingredients": "Water, Glycerin",
            "product_name": "Demo Sun Cream",
            "domestic_category": "sun_care",
        },
    )
    assert source.status_code == 200
    source_id = source.json()["result_id"]

    rerun = client.post(f"/reports/{source_id}/export-readiness")
    assert rerun.status_code == 200
    report = rerun.json()
    assert report["report_type"] == "export_readiness"
    assert report["source_report_id"] == source_id
    assert report["product_snapshot"]["ingredients"] == ["Water", "Glycerin"]
    assert report["product_snapshot"]["claims"] == ["SPF 30 sun protection"]


def test_domestic_report_us_rerun_accepts_category_override(fake):
    source = client.post(
        "/check",
        data={
            "region": "KR",
            "ad_text": "SPF 30 sun protection",
            "ingredients": "Water, Glycerin",
            "product_name": "Demo Sun Cream",
        },
    )
    assert source.status_code == 200
    source_id = source.json()["result_id"]

    rerun = client.post(
        f"/reports/{source_id}/export-readiness",
        json={"domestic_category": "sun_care"},
    )
    assert rerun.status_code == 200
    report = rerun.json()
    assert report["report_type"] == "export_readiness"
    assert report["source_report_id"] == source_id
    assert report["product_snapshot"]["ingredients"] == ["Water", "Glycerin"]
    assert report["product_snapshot"]["claims"] == ["SPF 30 sun protection"]


def test_old_report_without_snapshot_returns_explicit_rerun_error(fake):
    fake.rows["legacy-rid"] = {
        "id": "legacy-rid",
        "created_at": "2026-08-11T00:00:00Z",
        "region": "KR",
        "report": {"findings": [], "unjudged": [], "summary": {"region": "KR", "n_sentences": 0, "n_findings": 0}},
        "image_sha256": None,
        "image_path": None,
    }
    response = client.post("/reports/legacy-rid/export-readiness")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INPUT_SNAPSHOT_UNAVAILABLE"


def test_get_report_returns_stored_check(fake):
    """저장된 검사를 다시 보기로 조회한다."""
    fake.rows["rid-abc"] = {
        "id": "rid-abc",
        "created_at": "2026-08-11T00:00:00Z",
        "region": "KR",
        "report": {"findings": [], "unjudged": [], "summary": {"region": "KR", "n_sentences": 0, "n_findings": 0}},
        "image_sha256": None,
        "image_path": None,
    }
    r = client.get("/reports/rid-abc")
    assert r.status_code == 200
    body = r.json()
    assert body["result_id"] == "rid-abc"
    assert body["image_available"] is False
    assert body["report"]["findings"] == []


def test_get_report_unknown_id_is_404(fake):
    assert client.get("/reports/does-not-exist").status_code == 404


def test_get_report_image_streams_bytes(fake):
    """이미지 입력이었던 검사는 프록시로 원본을 그대로 스트리밍한다."""
    fake.rows["rid-img"] = {
        "id": "rid-img",
        "created_at": "2026-08-11T00:00:00Z",
        "region": "KR",
        "report": {"findings": [], "unjudged": [], "summary": {"region": "KR", "n_sentences": 0, "n_findings": 0}},
        "image_sha256": "abc",
        "image_path": "rid-img.png",
    }
    fake.images["rid-img.png"] = b"\x89PNG\r\n\x1a\nFAKE"
    r = client.get("/reports/rid-img/image")
    assert r.status_code == 200
    assert r.content == b"\x89PNG\r\n\x1a\nFAKE"
    assert r.headers["content-type"] == "image/png"


def test_get_report_image_404_when_no_image(fake):
    fake.rows["rid-noimg"] = {
        "id": "rid-noimg",
        "created_at": "2026-08-11T00:00:00Z",
        "region": "KR",
        "report": {"findings": [], "unjudged": [], "summary": {"region": "KR", "n_sentences": 0, "n_findings": 0}},
        "image_sha256": None,
        "image_path": None,
    }
    assert client.get("/reports/rid-noimg/image").status_code == 404
