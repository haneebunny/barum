"""API 스켈레톤 유닛테스트 (TestClient, 네트워크 없음).

이미지 없는 경로만 테스트한다 = VLM을 안 부른다. 진짜 이미지 OCR은 수동 스모크.

    venv/bin/python -m pytest tests/test_api.py -q
"""

import os

# 기본 judge는 RagJudge(VLM 호출)라, API 테스트는 오프라인 stub로 고정한다.
os.environ["JUDGE_KIND"] = "stub"
# 이력 저장은 Supabase(네트워크)라 기본 테스트에선 끈다. 저장 경로는 test_history_api가 가짜로 검증.
os.environ["CHECKS_PERSIST"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from barum.api.app import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_build_judge_rag_returns_rag_judge(monkeypatch):
    """JUDGE_KIND=rag면 RagJudge를 만든다(VLM은 가짜 주입, 키 불필요)."""
    from barum.api import app as app_module
    from barum.judge.cosmetic import RagJudge

    monkeypatch.setattr(app_module, "get_vlm", lambda provider, model=None: object())
    monkeypatch.setenv("JUDGE_KIND", "rag")
    assert isinstance(app_module._build_judge(), RagJudge)


def test_build_judge_defaults_to_rag(monkeypatch):
    """JUDGE_KIND 미설정이면 RagJudge다(2026-08-19 정정).

    원래 기본은 PromptJudge라 규칙집도 grounding도 안 붙은 채로 돌았다. 저장소
    어디에도 JUDGE_KIND=rag를 설정하는 곳이 없어서(.env·run_api.py·launch.json),
    손으로 안 주면 규칙 작업 전체가 서버에 안 닿았다. 이 테스트가 그 회귀를 막는다.
    """
    from barum.api import app as app_module
    from barum.judge.cosmetic import RagJudge

    monkeypatch.setattr(app_module, "get_vlm", lambda provider, model=None: object())
    monkeypatch.setattr(app_module, "_maybe_case_retriever", lambda: None)
    monkeypatch.delenv("JUDGE_KIND", raising=False)
    assert isinstance(app_module._build_judge(), RagJudge)


def test_build_judge_prompt_still_available(monkeypatch):
    """JUDGE_KIND=prompt로 제로샷 판정기를 계속 쓸 수 있다(비교실험·회귀 확인용)."""
    from barum.api import app as app_module
    from barum.judge.cosmetic import PromptJudge

    monkeypatch.setattr(app_module, "get_vlm", lambda provider, model=None: object())
    monkeypatch.setenv("JUDGE_KIND", "prompt")
    assert isinstance(app_module._build_judge(), PromptJudge)


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


def test_remediate_endpoint():
    """/remediate POST 엔드포인트가 올바르게 작동하는지 검증."""
    r = client.post(
        "/remediate",
        json={
            "sentence": "피부 재생을 도와 주름을 개선합니다.",
            "violation_type": "1호_의약품오인",
            "span": "피부 재생",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sentence"] == "피부 재생을 도와 주름을 개선합니다."
    assert body["violation_type"] == "1호_의약품오인"
    assert body["span"] == "피부 재생"
    assert isinstance(body["suggestions"], list)
    # 조건표 후보를 전부 내려주지 않고 안전한 것 하나만 고른다(2026-08-20).
    assert len(body["suggestions"]) == 1
    assert "극건성 피부용 보습" not in body["suggestions"]  # 재생 매칭 suggestions
    # **이 단정은 예전엔 "피부 장벽 강화"였다.** 그게 조건표 1순위인데, 같은 세션의
    # 판정기가 검토필요로 잡는 표현이라 화면에 모순이 보였다(카드 하나는 문제 삼고
    # 다른 카드는 추천). first_safe가 규칙에 안 걸리는 뒤 후보를 고르게 바뀌었다.
    assert body["suggestions"] == ["피부 생기 부여"]
    assert "disclaimer" in body


def test_remediate가_검토필요_표현을_추천하지_않는다():
    """리포트 화면 모순 회귀방지(2026-08-20 팀장 발견).

    같은 화면에서 `진정`을 검토필요로 잡아놓고 대체표현으로 `피부 진정`을 추천했다.
    조건표 1순위가 검토필요여도 뒤에 깨끗한 후보가 있으면 그쪽을 골라야 한다.
    """
    import sys

    sys.path.insert(0, "src")
    from barum.reference.rules import RuleOutcome, match_rule

    for sentence, span in [("항염 효과가 뛰어납니다.", "항염"), ("염증을 완화합니다.", "염증")]:
        r = client.post(
            "/remediate",
            json={"sentence": sentence, "violation_type": "1호_의약품오인", "span": span},
        )
        assert r.status_code == 200
        for suggestion in r.json()["suggestions"]:
            m = match_rule(suggestion)
            assert m is None or m.outcome is not RuleOutcome.violation, (
                f"위반 표현을 추천했다: {suggestion}"
            )
            assert m is None or m.outcome is not RuleOutcome.needs_review, (
                f"검토필요 표현을 추천했다: {suggestion} (더 안전한 후보가 있는데도)"
            )


def test_remediate_endpoint_validation():
    """/remediate POST 엔드포인트 필드 누락 시 422 반환 검증."""
    r = client.post(
        "/remediate",
        json={
            "sentence": "문구",
            # violation_type 누락
        },
    )
    assert r.status_code == 422



def test_stub_판정기면_대체표현_재작성기를_안_만든다(monkeypatch):
    """stub은 "외부 호출 없이 돈다"는 뜻이다. 유닛테스트가 과금 호출을 내면 안 된다.

    2026-08-22 회귀: /check에 재작성기를 무조건 물렸더니 테스트 4건이 28초를
    실제 LLM 호출에 썼다.
    """
    from barum.api.app import _replacement_rewriter

    monkeypatch.setenv("JUDGE_KIND", "stub")
    assert _replacement_rewriter() is None


def test_대체표현_재작성기는_OCR용_VLM과_별개다(monkeypatch):
    """이미지 없이 글로만 검사해도 재작성기는 있어야 한다.

    2026-08-22 스모크: OCR용 VLM을 재사용했더니 글 검사에서 rewriter가 None이 돼
    대체표현이 조용히 조건표 문구(`피부 생기 부여`)로 떨어졌다.
    """
    from barum.api.app import _replacement_rewriter

    monkeypatch.setenv("JUDGE_KIND", "rag")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert _replacement_rewriter() is not None


# ── 지금 도는 서버가 어느 코드인지 (2026-08-23) ────────────────────────────

def test_version_엔드포인트가_sha와_시작시각을_준다():
    """오늘 두 번, 머지된 코드가 안 도는 상태에서 원인을 엉뚱한 데서 찾았다.
    두 번 다 openapi.json 필드 유무로 역추적했는데 그건 우회다."""
    from fastapi.testclient import TestClient

    from barum.api import app as app_module

    r = TestClient(app_module.app).get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["sha"]
    assert body["started_at"]


def test_sha를_못_읽어도_서버는_뜬다():
    """관측용 값 하나 때문에 서버가 안 뜨면 안 된다."""
    from barum.api.app import _git_sha

    assert isinstance(_git_sha(), str)


def test_reload_감시에_레퍼런스_팩이_들어간다():
    """**팩(backend/reference/)도 감시 대상에 넣는다.**

    팩을 읽는 함수들이 전부 lru_cache라, 감시를 안 걸면 팩을 고쳐도 서버가
    옛 규정으로 계속 판정한다. 조용히, 무기한으로. (2026-08-24: 팩이 저장소
    루트에 있어 Railway가 backend만 배포할 때 빠지면서 create 판정이 500 났다.
    backend 안으로 옮겨 배포에 포함시켰고, 감시 경로도 backend/reference가 됐다.)
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts" / "run_api.py").read_text(
        encoding="utf-8"
    )
    assert "reload_dirs" in src
    assert 'ROOT / "reference"' in src


def test_앱을_띄울_때_env를_읽는다():
    """**갓 뜬 프로세스의 첫 요청이 .env를 못 보던 버그.**

    지금까지는 VLM 어댑터들이 각자 load_dotenv를 불렀다. 그래서 어댑터가 하나라도
    만들어지기 전에는 app.py의 env 읽기가 전부 빈손이었고, `/generate`가 판정기보다
    먼저 IMAGE_GENERATION_ENABLED를 읽는 바람에 플래그가 켜져 있는데도 이미지가
    0장 나갔다. 두 번째 요청부터는 정상이라 간헐적으로 보였다.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src" / "barum" / "api" / "app.py").read_text(
        encoding="utf-8"
    )
    # 모듈 최상위에서 부른다(함수 안이 아니라).
    assert "\nload_dotenv()\n" in src
