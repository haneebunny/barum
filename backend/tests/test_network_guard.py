"""테스트에서 바깥으로 나가는 연결을 막는 가드 (conftest.py).

가드가 조용히 깨지면 그날부터 다시 돈이 샌다. 그래서 가드 자체를 테스트한다.

    ./venv/bin/python -m pytest tests/test_network_guard.py -q
"""

import os
import socket

import pytest

from tests.conftest import OutboundNetworkBlocked

# 실제로 안 풀리는 예약 주소만 쓴다. 가드가 못 막으면 진짜 어딘가에 붙는 대신
# 그냥 실패해야 하므로.
_UNRESOLVABLE_HOST = "barum-guard-selftest.invalid"
_RESERVED_IP = "192.0.2.1"  # TEST-NET-1, 문서용 예약 대역


def test_이름으로_나가는_연결을_막는다():
    with pytest.raises(OutboundNetworkBlocked):
        socket.getaddrinfo(_UNRESOLVABLE_HOST, 443)


def test_IP로_바로_붙는_경로도_막는다():
    """DNS를 안 거치고 붙는 클라이언트도 있다. 그쪽도 막혀야 한다."""
    sock = socket.socket()
    try:
        with pytest.raises(OutboundNetworkBlocked):
            sock.connect((_RESERVED_IP, 443))
    finally:
        sock.close()


def test_로컬은_막지_않는다():
    """TestClient와 임시 서버가 쓴다. 여기까지 막으면 스위트가 통째로 죽는다."""
    assert socket.getaddrinfo("127.0.0.1", 80)


def test_에러_메시지가_다음_사람에게_뭘_할지_알려준다():
    with pytest.raises(OutboundNetworkBlocked) as excinfo:
        socket.getaddrinfo(_UNRESOLVABLE_HOST, 443)
    message = str(excinfo.value)
    assert _UNRESOLVABLE_HOST in message, "어느 호스트인지 알려줘야 한다"
    assert "BARUM_TEST_ALLOW_NETWORK" in message, "수동 스모크 방법을 알려줘야 한다"


def test_유료_이미지생성은_기본으로_꺼져있다():
    """개발자 .env에 켜져 있어도 테스트에선 꺼져야 한다.

    이게 켜진 채로 새면 /generate를 부르는 테스트마다 실제 이미지 과금이 나간다
    (2026-08-24에 실제로 그랬다).
    """
    assert os.environ.get("IMAGE_GENERATION_ENABLED") == "0"
