"""테스트 공통 설정.

**`/generate` 응답 캐시를 테스트마다 격리한다.** 안 하면 두 가지가 같이 깨진다.

1. *테스트가 개발자 캐시를 지운다.* `clear_generate_cache()`가 `_CACHE_FILE.unlink()`
   를 하는데, 경로가 실제 `backend/.cache/generate_cache.json`이면 돈 주고 만들어둔
   생성 결과가 날아간다(2026-08-24에 실제로 날렸다. 같은 입력을 다시 넣으면
   이미지가 재생성돼 과금된다).
2. *캐시가 테스트 결과를 뒤바꾼다.* `/generate`를 부르는 테스트가 앞선 실행이 남긴
   응답을 그대로 받아서, 가짜 생성기가 호출되지 않는다. 그래서 "캐시를 켜면 A·B가
   깨지고 끄면 C·D가 깨지는" 재현 안 되는 실패가 났다(2026-08-24 실측).

경로를 임시 폴더로 돌리고 매 테스트 전후로 비운다. 테스트는 자기 캐시만 본다.
"""

import os
import socket
import traceback
from collections import defaultdict

# ── 개발자 .env가 테스트로 새는 걸 막는다 (2026-08-24) ───────────────────────
#
# **barum 코드는 여기저기서 `load_dotenv()`를 부른다**(vlm.py 4곳, storage, api).
# 그래서 `pytest`를 돌리면 개발자 `.env`의 값이 그대로 테스트 설정이 된다.
# 실제로 `.env`에 `IMAGE_GENERATION_ENABLED=1`이 있어서, `/generate`를 부르는
# 테스트가 **진짜 유료 이미지 생성을 호출했다**(2026-08-24 스택으로 확인:
# `_generate_improve_content` → `build_image_plan` → `generate_module_images`
# → `vlm.py:355 client.interactions.create`).
#
# 그래서 테스트 결과가 **누구 기계에서 돌리느냐에 따라 달라졌다.** `.env`에 플래그를
# 켜둔 사람은 돈을 쓰고, 안 켜둔 사람은 안 쓴다. `JUDGE_KIND="stub"`을 넣어도
# 판정기만 가짜가 되지 이미지 생성은 그대로 나갔다.
#
# `load_dotenv()`는 기본이 `override=False`라, **여기서 먼저 넣어두면 .env가 못 덮는다.**
# barum을 임포트하기 전에 넣어야 해서 이 블록이 임포트보다 위에 있다.
_TEST_ENV_DEFAULTS = {
    # 과금 이미지 생성. 진짜로 켜서 확인하는 테스트는 monkeypatch.setenv로 켜고
    # get_image_generator를 가짜로 갈아낀다(test_generate_api.py 참고).
    "IMAGE_GENERATION_ENABLED": "0",
    # 트레이싱도 바깥으로 나간다. 테스트 결과와 무관한데 매번 붙는다.
    "LANGSMITH_TRACING": "false",
    "LANGCHAIN_TRACING_V2": "false",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ[_key] = _value

import pytest  # noqa: E402

import barum.storage.generate_cache as generate_cache  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_generate_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "generate_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(generate_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(generate_cache, "_CACHE_FILE", cache_dir / "generate_cache.json")
    generate_cache._CACHE.clear()
    yield
    generate_cache._CACHE.clear()


# ── 테스트에서 바깥으로 나가는 연결 차단 (2026-08-24) ────────────────────────
#
# **`pytest tests/`가 실제 유료 API를 불렀다.** 캐시 테스트 3개만으로 Gemini에
# 5회 나갔고, 이미지 캐시 테스트는 진짜 OCR을 태우다 크레딧 소진(429)을 찍었다.
# 테스트를 한 번 돌릴 때마다 돈이 나가고, 크레딧이 마르면 그 다음 `/check`가
# "위반 0건"으로 조용히 잘못된 답을 낸다.
#
# **`JUDGE_KIND="stub"`만으론 못 막는다.** `test_generate_cache.py`는 이미 모듈
# 상단에서 그 값을 넣는데도 5번 나갔다(실측). 판정기만 가짜로 바꿔도 이미지 생성·
# OCR·저장소·트레이싱이 각자 자기 클라이언트를 만든다. 그래서 진입점 하나를
# 막는 대신 **나가는 소켓 자체**를 막는다.
#
# 조용히 통과시키지 않고 **실패**시킨다. 실수로 과금 API를 부르는 테스트는 그
# 자리에서 터져야 다음 사람이 안 밟는다.
#
# 진짜 외부 호출이 필요한 수동 스모크는 `BARUM_TEST_ALLOW_NETWORK=1`로 푼다
# (CLAUDE.md: 크롤·VLM은 목킹하지 않고 수동 스모크로 확인한다).

_ALLOW_NETWORK = os.environ.get("BARUM_TEST_ALLOW_NETWORK") == "1"
# 막힌 호출의 출처를 찾을 때 쓴다. 예외를 삼키는 코드(예상된 실패 처리)를 지나면
# 스택이 안 남아서, 어느 줄이 불렀는지 알 방법이 없다.
#   BARUM_TEST_TRACE_NETWORK=1 venv/bin/python -m pytest tests/test_x.py
_TRACE_NETWORK = os.environ.get("BARUM_TEST_TRACE_NETWORK") == "1"

# 로컬은 그대로 둔다. TestClient·임시 서버가 쓴다.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", ""})

_orig_getaddrinfo = socket.getaddrinfo
_orig_connect = socket.socket.connect

# {호스트: {테스트 노드아이디}} - 세션 끝에 명단을 낸다.
_blocked_attempts: dict[str, set[str]] = defaultdict(set)
_current_test = {"id": "<수집 단계>"}


class OutboundNetworkBlocked(RuntimeError):
    """테스트가 바깥으로 나가려 했다. 목킹하거나 픽스처로 대체할 것."""


def _is_local(host: str) -> bool:
    return host in _LOCAL_HOSTS or host.startswith("127.")


def _is_selftest(host: str) -> bool:
    """가드 자가 테스트가 쓰는 주소. 막기는 하되 유출 명단엔 안 넣는다.

    `.invalid`는 절대 안 풀리는 예약 TLD고, 192.0.2.0/24는 문서용 예약 대역이라
    실수로 진짜 어딘가에 붙을 일이 없다.
    """
    return host.endswith(".invalid") or host.startswith("192.0.2.")


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    name = str(host)
    if not _ALLOW_NETWORK and not _is_local(name):
        if not _is_selftest(name):
            _blocked_attempts[name].add(_current_test["id"])
        if _TRACE_NETWORK:
            print(f"\n--- {name} 호출 출처 ({_current_test['id']}) ---")
            # SDK 내부 프레임은 걷어내고 우리 코드만 남긴다.
            ours = [f for f in traceback.format_stack() if "/barum/" in f and "site-packages" not in f]
            print("".join(ours[-6:]))
        raise OutboundNetworkBlocked(
            f"테스트가 외부 연결을 시도했다: {name}:{port}\n"
            f"  테스트: {_current_test['id']}\n"
            "  유료 API·저장소는 테스트에서 부르지 않는다. 가짜 객체로 주입할 것.\n"
            "  수동 스모크로 진짜 호출이 필요하면 BARUM_TEST_ALLOW_NETWORK=1."
        )
    return _orig_getaddrinfo(host, port, *args, **kwargs)


def _guarded_connect(self, address):
    # getaddrinfo를 안 거치고 IP로 바로 붙는 경로(예: 이미 캐시된 주소)도 막는다.
    host = address[0] if isinstance(address, tuple) and address else ""
    if not _ALLOW_NETWORK and isinstance(host, str) and not _is_local(host):
        if not _is_selftest(host):
            _blocked_attempts[host].add(_current_test["id"])
        raise OutboundNetworkBlocked(
            f"테스트가 외부 연결을 시도했다: {host}\n  테스트: {_current_test['id']}"
        )
    return _orig_connect(self, address)


socket.getaddrinfo = _guarded_getaddrinfo
socket.socket.connect = _guarded_connect


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """차단 기록에 어느 테스트인지 남기려고 현재 테스트를 추적한다."""
    _current_test["id"] = item.nodeid
    return None


def pytest_terminal_summary(terminalreporter):
    """막힌 시도를 호스트별로 모아 보여준다. 조용히 지나가면 다음에 또 샌다."""
    if not _blocked_attempts:
        return
    terminalreporter.write_sep("=", "외부 연결 차단됨", red=True)
    for host in sorted(_blocked_attempts):
        tests = sorted(_blocked_attempts[host])
        terminalreporter.write_line(f"{host}  ({len(tests)}개 테스트)")
        for nodeid in tests:
            terminalreporter.write_line(f"    {nodeid}")
