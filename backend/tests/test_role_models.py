"""역할별 모델명 오버라이드.

기본 동작이 안 바뀌는 것이 제일 중요하다. 아무것도 안 정하면 지금과 100% 같아야 한다.

    ./venv/bin/python -m pytest tests/test_role_models.py -q
"""

import re
from pathlib import Path

import pytest

from barum.vlm import _ROLE_MODEL_ENV, role_model

_ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_미설정이면_None이라_기존_기본값이_산다(monkeypatch):
    """None을 어댑터에 넘기면 어댑터가 기존 환경변수로 폴백한다."""
    for env in _ROLE_MODEL_ENV.values():
        monkeypatch.delenv(env, raising=False)
    assert all(role_model(role) is None for role in _ROLE_MODEL_ENV)


def test_빈_문자열도_미설정으로_본다(monkeypatch):
    """`JUDGE_MODEL=`처럼 비워 둔 줄이 빈 모델명으로 넘어가면 호출이 깨진다."""
    monkeypatch.setenv("JUDGE_MODEL", "")
    assert role_model("judge") is None


def test_설정하면_그_값을_쓴다(monkeypatch):
    monkeypatch.setenv("PRESCREEN_MODEL", "gpt-5-nano")
    assert role_model("prescreen") == "gpt-5-nano"


def test_모르는_역할은_조용히_넘어가지_않는다():
    """오타난 역할명이 None으로 떨어지면 기본값이 쓰여 아무도 못 알아챈다."""
    with pytest.raises(ValueError):
        role_model("judgee")


def test_다섯_역할이_다_있다():
    assert set(_ROLE_MODEL_ENV) == {"judge", "prescreen", "ocr", "generate", "image"}


def test_1차_필터는_안_주면_판정_VLM을_쓴다():
    """모델을 안 나누면 호출기도 하나만 만든다(불필요한 클라이언트 생성 회피)."""
    from barum.judge.cosmetic import RagJudge

    sentinel = object()
    judge = RagJudge(sentinel)
    assert judge._prescreen_vlm is None
    assert (judge._prescreen_vlm or judge._vlm) is sentinel


def test_1차_필터를_나누면_그걸_쓴다():
    from barum.judge.cosmetic import RagJudge

    judge_vlm, prescreen = object(), object()
    judge = RagJudge(judge_vlm, prescreen_vlm=prescreen)
    assert (judge._prescreen_vlm or judge._vlm) is prescreen


def test_env_example이_역할별_변수를_다_적어둔다():
    """문서화 안 된 스위치는 없는 것과 같다. 낡은 .env.example이 실제 사고를 냈다."""
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    for env in _ROLE_MODEL_ENV.values():
        assert env in text, f"{env}가 .env.example에 없다"


def test_env_example이_동작_스위치를_다_적어둔다():
    """코드가 읽는 BARUM_*·*_ENABLED 스위치는 예시 파일에 다 나와야 한다."""
    src = Path(__file__).resolve().parents[1] / "src"
    used = set()
    for path in src.rglob("*.py"):
        used |= set(
            re.findall(
                r'os\.(?:environ\.get|getenv)\(\s*"((?:BARUM_|IMAGE_|CHECK)[A-Z0-9_]*)"',
                path.read_text(encoding="utf-8"),
            )
        )
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    missing = sorted(e for e in used if e not in text)
    assert not missing, f".env.example에 빠진 스위치: {missing}"
