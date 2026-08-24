"""generic 수출 준비도 v2 API·rule-pack 분기 테스트 (외부 네트워크 없음)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from barum.api import app as app_module
from barum.api.app import app


client = TestClient(app)


def _request(**overrides) -> dict:
    payload = {
        "destination_country": "US",
        "domestic_category": "skincare",
        "product_name": "Demo Cream",
        "intended_use": "moisturizing",
        "claims": ["Moisturizes dry skin"],
        "ingredients": ["Water", "Glycerin"],
    }
    payload.update(overrides)
    return payload


def _post(monkeypatch, payload: dict):
    monkeypatch.setenv("CHECKS_PERSIST", "0")
    return client.post("/export-readiness", json=payload)


def test_us_skincare_applies_only_basic_pack_and_has_no_sunscreen_questions(monkeypatch):
    response = _post(monkeypatch, _request())

    assert response.status_code == 200
    body = response.json()
    assert body["report_type"] == "export_readiness"
    assert body["schema_version"] == "2"
    assert body["destination_country"] == "US"
    assert body["domestic_category"] == "skincare"
    assert [p["rule_pack_id"] for p in body["applied_rule_packs"]] == [
        "US_COSMETIC_BASIC"
    ]
    assert not any(item["rule_pack_id"] == "US_SUNSCREEN_OTC" for item in body["items"])
    assert not any(item["id"].startswith("us_sunscreen_") for item in body["items"])
    assert body["regulatory_route"]["code"] == "COSMETIC_ONLY_CANDIDATE"


def test_us_sun_care_adds_sunscreen_pack(monkeypatch):
    response = _post(
        monkeypatch,
        _request(domestic_category="sun_care", claims=[], intended_use="sun care"),
    )

    assert response.status_code == 200
    body = response.json()
    assert [p["rule_pack_id"] for p in body["applied_rule_packs"]] == [
        "US_COSMETIC_BASIC",
        "US_SUNSCREEN_OTC",
    ]
    assert any(item["id"] == "us_sunscreen_route_review" for item in body["items"])
    assert body["regulatory_route"]["code"] == "DRUG_COSMETIC_CANDIDATE"


def test_spf_claim_triggers_sunscreen_pack_outside_sun_care(monkeypatch):
    response = _post(
        monkeypatch,
        _request(domestic_category="makeup", claims=["Foundation with SPF 30 sun protection"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert "US_SUNSCREEN_OTC" in {
        pack["rule_pack_id"] for pack in body["applied_rule_packs"]
    }
    route_item = next(item for item in body["items"] if item["id"] == "us_sunscreen_route_review")
    assert route_item["status"] == "VERIFICATION_REQUIRED"


@pytest.mark.parametrize(
    ("claim", "item_suffix"),
    [
        ("Treats acne and blackheads", "acne"),
        ("Controls dandruff", "dandruff"),
        ("Promotes hair regrowth", "hair_growth"),
        ("Skin lightening for hyperpigmentation", "skin_lightening"),
        ("Increases collagen to remove wrinkles", "structure_function"),
        ("Antiperspirant that reduces perspiration", "antiperspirant"),
        ("Anticavity toothpaste prevents cavities", "anticaries"),
    ],
)
def test_high_risk_claims_only_create_verification_alert(
    monkeypatch,
    claim: str,
    item_suffix: str,
):
    response = _post(monkeypatch, _request(claims=[claim]))

    assert response.status_code == 200
    body = response.json()
    assert "HIGH_RISK_CLAIM_REVIEW" in {
        pack["rule_pack_id"] for pack in body["applied_rule_packs"]
    }
    item = next(item for item in body["items"] if item["id"] == f"high_risk_claim_{item_suffix}")
    assert item["status"] == "VERIFICATION_REQUIRED"
    assert item["user_state"] == "PROVIDED"
    assert body["support_level"] == "REVIEW_ONLY"


def test_user_input_states_remain_distinct(monkeypatch):
    response = _post(
        monkeypatch,
        _request(
            label_evidence={
                "statement_of_identity": {"input_state": "PROVIDED", "value": "Face cream"},
                "net_quantity": {"input_state": "NOT_AVAILABLE"},
                "business_name_address": {"input_state": "UNKNOWN"},
                "ingredient_declaration": {"input_state": "NOT_ENTERED"},
            }
        ),
    )

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items["us_basic_label_identity"]["user_state"] == "PROVIDED"
    assert items["us_basic_label_net_quantity"]["user_state"] == "NOT_AVAILABLE"
    assert items["us_basic_label_business"]["user_state"] == "UNKNOWN"
    assert items["us_basic_label_ingredients"]["user_state"] == "NOT_ENTERED"
    assert items["us_basic_label_net_quantity"]["status"] == "REQUIRED_CHANGE"
    assert items["us_basic_label_business"]["status"] == "VERIFICATION_REQUIRED"
    assert items["us_basic_label_ingredients"]["status"] == "NOT_ASSESSED"


def test_profile_snapshot_and_priority_actions(monkeypatch):
    response = _post(
        monkeypatch,
        _request(
            profile={
                "legal_manufacturer": "Demo Co.",
                "manufacturing_site": "Busan Site",
                "registration_status": "registered",
            },
            label_evidence={
                "statement_of_identity": {"input_state": "NOT_AVAILABLE"},
                "net_quantity": {"input_state": "NOT_AVAILABLE"},
                "business_name_address": {"input_state": "NOT_AVAILABLE"},
                "ingredient_declaration": {"input_state": "NOT_AVAILABLE"},
            },
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile_status"] == "PROVIDED"
    assert body["profile_snapshot"]["legal_manufacturer"] == "Demo Co."
    assert len(body["priority_actions"]) == 3
    assert all(action["status"] == "REQUIRED_CHANGE" for action in body["priority_actions"])


def test_destination_country_is_open_string_but_unsupported_rules_return_400(monkeypatch):
    response = _post(monkeypatch, _request(destination_country="JP"))

    assert response.status_code == 400
    assert "미국(US)만 지원" in response.json()["detail"]


class _Table:
    def __init__(self, rows):
        self.rows = rows
        self.inserted = None
        self.eq_id = None

    def insert(self, row):
        self.inserted = row
        return self

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, _column, value):
        self.eq_id = value
        return self

    def limit(self, _value):
        return self

    def execute(self):
        if self.inserted is not None:
            row = dict(self.inserted)
            row.setdefault("created_at", "2026-08-24T00:00:00+00:00")
            self.rows[row["id"]] = row
            self.inserted = None
            return SimpleNamespace(data=[row])
        row = self.rows.get(self.eq_id)
        return SimpleNamespace(data=[row] if row else [])


class _FakeClient:
    def __init__(self):
        self.rows = {}

    def table(self, _name):
        return _Table(self.rows)


def test_generic_report_is_saved_and_restored_by_discriminator(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setenv("CHECKS_PERSIST", "1")
    monkeypatch.setattr(app_module, "_checks_client", lambda: fake)

    created = client.post("/export-readiness", json=_request())
    assert created.status_code == 200
    result_id = created.json()["result_id"]
    assert result_id in fake.rows

    restored = client.get(f"/reports/{result_id}/readiness")
    assert restored.status_code == 200
    assert restored.json()["report_type"] == "export_readiness"
    assert restored.json()["result_id"] == result_id

    envelope = client.get(f"/reports/{result_id}")
    assert envelope.status_code == 200
    assert envelope.json()["report"]["report_type"] == "export_readiness"


def test_existing_us_sunscreen_check_response_contract_still_works(monkeypatch):
    monkeypatch.setenv("CHECKS_PERSIST", "0")
    response = client.post(
        "/check/us-sunscreen",
        data={"country": "US", "ad_text": "SPF50 sunscreen"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"findings", "summary", "result_id", "disclaimer"}
    assert body["summary"]["n_findings"] >= 1
    assert body.get("report_type") is None
