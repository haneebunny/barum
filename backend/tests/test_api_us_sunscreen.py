"""POST /check/us-sunscreen API 유닛테스트 (TestClient, 네트워크 없음).

텍스트만 넣는 경로만 테스트한다 = VLM(OCR)을 안 부른다. 판정기(USSunscreenJudge)
자체가 VLM을 안 쓰므로, 이미지 없는 경로는 완전히 오프라인으로 검증된다.

    venv/bin/python -m pytest tests/test_api_us_sunscreen.py -q
"""

import os

os.environ.setdefault("CHECKS_PERSIST", "0")

from fastapi.testclient import TestClient  # noqa: E402

from barum.api.app import app  # noqa: E402

client = TestClient(app)


def test_requires_input():
    """이미지·글 둘 다 없으면 422."""
    r = client.post("/check/us-sunscreen", data={"country": "US"})
    assert r.status_code == 422


def test_rejects_non_us_country():
    """1차 대상국은 미국만 지원(팀 확정) — 다른 값은 400."""
    r = client.post("/check/us-sunscreen", data={"country": "EU", "ad_text": "SPF50"})
    assert r.status_code == 400


def test_country_defaults_to_us():
    """country를 안 주면 기본값 US로 통과한다(팀 확정)."""
    r = client.post("/check/us-sunscreen", data={"ad_text": "촉촉한 수분크림"})
    assert r.status_code == 200


def test_spf_text_flags_otc_reclassification():
    r = client.post(
        "/check/us-sunscreen",
        data={"country": "US", "ad_text": "SPF50+ 자외선차단"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["n_findings"] >= 1
    categories = {f["category"] for f in body["findings"]}
    assert "OTC의약품_분류전환" in categories
    assert body["disclaimer"]  # 각주 문구가 항상 실려 있어야 한다


def test_spf_text_with_korea_only_ingredient_flags_unapproved():
    r = client.post(
        "/check/us-sunscreen",
        data={
            "country": "US",
            "ad_text": "SPF50+ 자외선차단",
            "ingredients": "정제수,드로메트리졸",
        },
    )
    assert r.status_code == 200
    body = r.json()
    unapproved = [f for f in body["findings"] if f["category"] == "미국_미승인_성분"]
    assert len(unapproved) == 1
    assert unapproved[0]["span"] == "드로메트리졸"


def test_no_spf_text_returns_no_findings():
    r = client.post("/check/us-sunscreen", data={"country": "US", "ad_text": "촉촉한 수분크림"})
    assert r.status_code == 200
    assert r.json()["summary"]["n_findings"] == 0
