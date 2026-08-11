"""Supabase 클라이언트 생성 (env 기반, 단일 지점).

`SUPABASE_URL`·`SUPABASE_KEY`를 backend/.env에서 읽어 클라이언트를 만든다. 키는
하드코딩하지 않는다(vlm.py와 같은 방식). 실제 연결·쿼리는 이 클라이언트를 받는
어댑터들이 하고, 여기선 생성·자격검증만 한다.

키는 anon/publishable가 아니라 secret key(구 service_role)를 써야 서버에서
테이블·스토리지에 쓸 수 있다. 권한 에러가 나면 이 키 종류부터 의심한다.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv


def _normalize_url(url: str) -> str:
    """Supabase 베이스 URL로 정규화한다.

    클라이언트는 베이스(`https://<ref>.supabase.co`)만 받고 `/rest/v1`을 스스로
    붙인다. 하지만 대시보드에서 REST 엔드포인트 전체(`.../rest/v1/`)를 복사해 넣는
    실수가 잦아 경로가 이중으로 깨진다(PGRST125). 끝 슬래시와 `/rest/v1`을 떼어 방어한다.
    """
    u = url.strip().rstrip("/")
    if u.endswith("/rest/v1"):
        u = u[: -len("/rest/v1")]
    return u


def _require_credentials(url: str | None, key: str | None) -> tuple[str, str]:
    """URL·KEY가 다 있으면 (url, key)를 낸다. 하나라도 없으면 어느 게 빈지 알려주고 터뜨린다."""
    if not url:
        raise RuntimeError("SUPABASE_URL이 없다. backend/.env를 확인할 것.")
    if not key:
        raise RuntimeError(
            "SUPABASE_KEY가 없다. backend/.env 확인. anon/publishable 말고 "
            "secret key(구 service_role)인지도 확인할 것."
        )
    return url, key


@lru_cache(maxsize=1)
def get_supabase_client():
    """Supabase 클라이언트를 만든다(1회 생성 후 캐시).

    env가 없으면 _require_credentials가 명확한 메시지로 터뜨린다. 실제 네트워크
    연결은 첫 쿼리 시점이라, 생성 자체는 키가 있으면 성공한다.
    """
    load_dotenv()
    url, key = _require_credentials(
        os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    )
    from supabase import create_client

    return create_client(_normalize_url(url), key)
