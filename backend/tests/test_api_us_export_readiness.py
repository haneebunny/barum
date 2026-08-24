"""미국 수출 준비도 MVP API·결정적 규칙 테스트 (외부 네트워크 없음)."""

import json

import pytest
from fastapi.testclient import TestClient

from barum.api import app as app_module
from barum.api.app import app
from barum.judge.us_export_readiness import build_us_export_readiness_report
from barum.models import ExportProduct, ExportProfile, ExportReadinessStatus


client = TestClient(app)


def test_empty_readiness_request_returns_safe_not_assessed_checklist(monkeypatch):
    monkeypatch.setenv("CHECKS_PERSIST", "0")
    response = client.post("/export-readiness/us-sunscreen", data={})

    assert response.status_code == 200
    body = response.json()
    assert body["report_type"] == "us_export_readiness"
    assert body["summary"]["total"] == 7
    assert len(body["items"]) == 7
    assert body["summary"]["overall_status"] == "NOT_ASSESSED"
    assert all(item["status"] == "NOT_ASSESSED" for item in body["items"])


def test_sunscreen_readiness_has_all_categories_and_does_not_auto_compliant_bemotrizinol(
    monkeypatch,
):
    monkeypatch.setenv("CHECKS_PERSIST", "0")
    response = client.post(
        "/export-readiness/us-sunscreen",
        data={
            "ad_text": "SPF50 broad spectrum sunscreen",
            "ingredients": "Zinc oxide, Bemotrizinol",
            "product_name": "Demo Sunscreen",
            "product": json.dumps(
                {
                    "intended_use": "sunscreen",
                    "spf_test_report": True,
                    "broad_spectrum_test_report": True,
                    "water_resistance_test_report": True,
                    "drug_facts_ready": True,
                    "claims_reviewed": True,
                }
            ),
            "profile": json.dumps(
                {
                    "legal_manufacturer": "Demo Co.",
                    "manufacturing_site": "Busan Site",
                    "us_agent_name": "US Agent",
                    "importer_name": "US Importer",
                    "registration_status": "registered",
                    "cgmp_ready": True,
                    "drug_listing_status": "ready",
                }
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert {item["category"] for item in body["items"]} == {
        "CLASSIFICATION",
        "FORMULA",
        "TESTING",
        "LABELING",
        "CLAIMS",
        "ESTABLISHMENT",
        "LISTING_IMPORT",
    }
    formula = next(item for item in body["items"] if item["category"] == "FORMULA")
    assert formula["status"] == "VERIFICATION_REQUIRED"
    assert "Bemotrizinol" in formula["summary"]
    assert body["summary"]["overall_status"] == "VERIFICATION_REQUIRED"


def test_m020_uncovered_active_is_blocker_without_calling_it_banned():
    report = build_us_export_readiness_report(
        ad_text="SPF50 sunscreen",
        ingredients="드로메트리졸",
        product_name="Demo",
        product=ExportProduct(intended_use="sunscreen"),
        profile=ExportProfile(),
        created_at="2026-08-24T00:00:00+00:00",
    )
    formula = next(item for item in report.items if item.category.value == "FORMULA")

    assert formula.status == ExportReadinessStatus.BLOCKER
    assert "금지" not in formula.summary
    assert "M020" in formula.summary


def test_invalid_readiness_json_is_rejected(monkeypatch):
    monkeypatch.setenv("CHECKS_PERSIST", "0")
    response = client.post(
        "/export-readiness/us-sunscreen",
        data={"product": "not-json"},
    )

    assert response.status_code == 422
    assert "product" in response.json()["detail"]


def test_storage_failure_keeps_readiness_response_alive(monkeypatch):
    monkeypatch.setenv("CHECKS_PERSIST", "1")

    def fail_client():
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(app_module, "_checks_client", fail_client)
    response = client.post("/export-readiness/us-sunscreen", data={})

    assert response.status_code == 200
    assert response.json()["result_id"] is None


def test_get_readiness_restores_discriminator_report(monkeypatch):
    report = build_us_export_readiness_report(
        ad_text=None,
        ingredients=None,
        product_name="Saved demo",
        product=ExportProduct(),
        profile=ExportProfile(legal_manufacturer="Demo Co."),
        created_at="2026-08-24T00:00:00+00:00",
    )

    class Query:
        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return type("Result", (), {"data": [{
                "id": "saved-readiness",
                "region": "US",
                "created_at": report.created_at,
                "report": report.model_dump(mode="json"),
            }]})()

    class FakeClient:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(app_module, "_checks_client", lambda: FakeClient())
    response = client.get("/reports/saved-readiness/readiness")

    assert response.status_code == 200
    assert response.json()["report_type"] == "us_export_readiness"
    assert response.json()["result_id"] == "saved-readiness"
