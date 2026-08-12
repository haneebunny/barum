"""POST /generate 엔드포인트 유닛테스트 (오프라인: StubJudge + 가짜 섹션 LLM).

    ./venv/bin/python -m pytest tests/test_generate_api.py -q
"""

import os

os.environ["JUDGE_KIND"] = "stub"
os.environ["CHECKS_PERSIST"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from barum.api import app as app_module  # noqa: E402

client = TestClient(app_module.app)


class FakeVLM:
    def generate_json(self, prompt, images):
        return {"제품개요": "담백한 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"}


@pytest.fixture(autouse=True)
def _fake_section_vlm(monkeypatch):
    monkeypatch.setattr(app_module, "_section_vlm", lambda: FakeVLM())


def test_generate_endpoint_returns_structured_content():
    r = client.post(
        "/generate",
        json={"content": "재생 크림입니다. 문의 010-1234-5678", "product_name": "테스트크림"},
    )
    assert r.status_code == 200
    body = r.json()
    assert any(s["kind"] == "광고문구" for s in body["sections"])
    assert any(s["source"] == "llm" for s in body["sections"])
    assert body["replacements"][0]["original"] == "재생"
    assert "전화번호" in body["pii_removed"]
    assert body["recheck"] is not None
    assert body["disclaimer"]


def test_generate_requires_content():
    """content 없으면 422(pydantic 검증)."""
    r = client.post("/generate", json={"product_name": "x"})
    assert r.status_code == 422
