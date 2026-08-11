"""검사 이력 저장/조회 + 증거 이미지 (Supabase checks 테이블 + Storage 버킷).

- 검사 결과(CheckReport)를 통째로 저장하고, 추측불가 result_id로 다시 조회한다(FR-8).
- 이미지 입력이면 원본을 private 버킷에 두고 sha256을 남긴다(증거 보존, FR-1).

실제 쿼리·업로드는 Supabase 클라이언트가 하고, 여기선 얇은 래퍼다(테스트는 가짜 주입).
"""

import hashlib
import secrets

_TABLE = "checks"
_BUCKET = "evidence"  # 증거 이미지 버킷(private)


def sha256_hex(data: bytes) -> str:
    """바이트의 sha256 16진 해시(증거 무결성·중복 판별용)."""
    return hashlib.sha256(data).hexdigest()


def new_result_id() -> str:
    """추측불가 result_id. 로그인 없이 이 URL 자체가 접근권(capability token)."""
    return secrets.token_urlsafe(32)


def build_check_row(
    result_id: str,
    region: str,
    report: dict,
    image_sha256: str | None = None,
    image_path: str | None = None,
) -> dict:
    """checks 테이블 insert 로우를 만든다. report는 CheckReport를 dict로 덤프한 것."""
    return {
        "id": result_id,
        "region": region,
        "report": report,
        "image_sha256": image_sha256,
        "image_path": image_path,
    }


def save_check(client, row: dict) -> None:
    """checks에 한 건 저장."""
    client.table(_TABLE).insert(row).execute()


def get_check(client, result_id: str) -> dict | None:
    """result_id로 저장된 검사 한 건을 조회. 없으면 None."""
    resp = client.table(_TABLE).select("*").eq("id", result_id).limit(1).execute()
    rows = resp.data or []
    return rows[0] if rows else None


# ── 증거 이미지 (Storage) ──────────────────────────────────────────────────


def ensure_bucket(client, name: str = _BUCKET) -> None:
    """private 버킷이 없으면 만든다(멱등). 이미 있으면 조용히 넘어간다."""
    try:
        existing = {getattr(b, "name", b) for b in (client.storage.list_buckets() or [])}
    except Exception:
        existing = set()
    if name not in existing:
        # 이미 있으면 예외가 날 수 있다(경쟁) — 예상된 실패로 흡수.
        try:
            client.storage.create_bucket(name, options={"public": False})
        except Exception as e:
            print(f"    [info] 버킷 생성 스킵({name}): {type(e).__name__}: {e}")


def upload_image(client, path: str, data: bytes, content_type: str) -> None:
    """원본 이미지를 버킷에 올린다. 같은 경로면 덮어쓴다(upsert)."""
    client.storage.from_(_BUCKET).upload(
        path,
        data,
        {"content-type": content_type, "upsert": "true"},
    )


def download_image(client, path: str) -> bytes:
    """버킷에서 원본 이미지 바이트를 읽는다(프록시 엔드포인트가 그대로 스트리밍)."""
    return client.storage.from_(_BUCKET).download(path)
