"""API 스켈레톤 유닛테스트 (TestClient, 네트워크 없음).

이미지 없는 경로만 테스트한다 = VLM을 안 부른다. 진짜 이미지 OCR은 수동 스모크.

    venv/bin/python -m pytest tests/test_api.py -q
"""

import os

# 기본 judge는 PromptJudge(VLM 호출)라, API 테스트는 오프라인 stub로 고정한다.
os.environ["JUDGE_KIND"] = "stub"

from fastapi.testclient import TestClient  # noqa: E402

from barum.api.app import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_build_judge_rag_returns_rag_judge(monkeypatch):
    """JUDGE_KIND=rag면 RagJudge를 만든다(VLM은 가짜 주입, 키 불필요)."""
    from barum.api import app as app_module
    from barum.judge.cosmetic import RagJudge

    monkeypatch.setattr(app_module, "get_vlm", lambda provider: object())
    monkeypatch.setenv("JUDGE_KIND", "rag")
    assert isinstance(app_module._build_judge(), RagJudge)


def test_check_requires_input():
    """이미지·글 둘 다 없으면 422."""
    r = client.post("/check", data={"region": "KR"})
    assert r.status_code == 422


def test_check_text_only_returns_report():
    """글만 넣어도 CheckReport가 나온다(VLM 불필요)."""
    r = client.post(
        "/check",
        data={"region": "KR", "ad_text": "멜라닌 억제로 미백 개선"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["region"] == "KR"
    assert body["summary"]["n_findings"] >= 1
    assert body["findings"][0]["violation_type"] == "2호_기능성오인"


def test_check_rejects_bad_region():
    """region enum 밖 값은 422(FastAPI 검증)."""
    r = client.post("/check", data={"region": "JP", "ad_text": "미백"})
    assert r.status_code == 422


def test_check_accepts_optional_ingredients_field():
    """ingredients는 선택 필드라, 없어도 있어도 요청이 통과한다.

    StubJudge는 성분 정합을 안 하므로 여기선 요청 형태(shape)만 확인한다.
    실제 정합 동작은 test_judge.py가 PromptJudge로 검증.
    """
    r = client.post(
        "/check",
        data={
            "region": "KR",
            "ad_text": "미백에 도움",
            "ingredients": "정제수, 나이아신아마이드",
        },
    )
    assert r.status_code == 200
