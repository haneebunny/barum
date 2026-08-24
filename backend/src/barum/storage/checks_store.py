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
    product_name: str | None = None,
    cache_key: str | None = None,
) -> dict:
    """checks 테이블 insert 로우를 만든다. report는 CheckReport를 dict로 덤프한 것.

    cache_key: 이 검사를 만든 캐시 키(입력값+로직버전 조합). report JSONB 안에
    `_cache_key`로 심는다. 스키마에 컬럼을 새로 파지 않고 2차 캐시 복원 때 정확 대조를
    하기 위해서다. `_cache_key`는 예약 키라 CheckReport/USPreflightReport 모델이
    무시한다(extra="ignore" 기본값), API 응답에는 안 샌다.
    """
    if cache_key is not None:
        # report는 model_dump 결과 dict라 여기서 예약 키를 얹어도 모델 검증엔 영향 없다.
        report = {**report, "_cache_key": cache_key}
    row = {
        "id": result_id,
        "region": region,
        "report": report,
        "image_sha256": image_sha256,
        "image_path": image_path,
    }
    if product_name:
        row["product_name"] = product_name
    return row


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


# ── 이미지 결과 캐시 (메모리 + Supabase 2차 조회) ───────────────────────────

_IMAGE_CACHE: dict[str, object] = {}


def clear_image_cache() -> None:
    """메모리 캐시를 초기화한다(테스트/격리용)."""
    _IMAGE_CACHE.clear()


# 캐시 로직 버전. **판정·OCR·전성분추출 등 결과에 영향을 주는 로직이 바뀌면 올린다.**
# 올리면 캐시 키가 통째로 바뀌어 옛 캐시(메모리·Supabase 둘 다)가 자동 무효화된다.
# 안 올리면 코드를 고쳐도 옛 결과가 계속 나온다(2026-08-24 실제 사고: 미국 프리플라이트
# 전성분 OCR을 고쳤는데 고치기 전 캐시가 계속 "전성분 미입력"을 돌려줬다).
_CACHE_LOGIC_VERSION = "2"


def build_cache_key(
    image_sha256: str,
    region_or_country: str,
    ad_text: str | None = None,
    ingredients: str | None = None,
    ingredient_amounts: str | None = None,
    product_name: str | None = None,
) -> str:
    """이미지 검사 입력값 조합 + 로직 버전으로 고유 캐시 키를 만든다."""
    raw = f"{_CACHE_LOGIC_VERSION}:{image_sha256}:{region_or_country}:{ad_text or ''}:{ingredients or ''}:{ingredient_amounts or ''}:{product_name or ''}"
    return sha256_hex(raw.encode("utf-8"))


def get_check_by_sha256(client, image_sha256: str) -> dict | None:
    """image_sha256으로 저장된 최근 검사 한 건을 조회. 없으면 None."""
    try:
        resp = (
            client.table(_TABLE)
            .select("*")
            .eq("image_sha256", image_sha256)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as e:
        print(f"    [info] Supabase sha256 조회 스킵/실패: {type(e).__name__}: {e}")
        return None


def get_cached_check(client, cache_key: str, image_sha256: str | None = None) -> object | None:
    """캐시된 검사 리포트를 가져온다. 1차 메모리 캐시, 2차 Supabase 조회."""
    if cache_key in _IMAGE_CACHE:
        cached = _IMAGE_CACHE[cache_key]
        if hasattr(cached, "findings"):
            # 메모리 캐시도 bbox 없으면 무효화
            if any(getattr(f.location, "tile", None) and getattr(f.location, "x_start", None) in (None, 0) and getattr(f.location, "x_end", None) == getattr(f.location, "source_w", None) for f in cached.findings):
                del _IMAGE_CACHE[cache_key]
            else:
                return cached
        else:
            return cached

    # 2차: Supabase DB에 동일 image_sha256으로 저장된 레코드가 있는지 확인
    if client is not None and image_sha256:
        row = get_check_by_sha256(client, image_sha256)
        if row and "report" in row:
            try:
                from barum.models import CheckReport, USPreflightReport

                report_dict = row["report"]
                result_id = row.get("id")

                # 저장된 cache_key가 지금 요청 키와 정확히 같을 때만 복원한다.
                # get_check_by_sha256은 image_sha256만 보고 최신 한 건을 주므로, 같은
                # 이미지라도 광고문구·전성분이 다르거나(입력 불일치) 판정 로직이 바뀐 뒤면
                # (버전 불일치) 엉뚱한 옛 결과가 나온다. cache_key엔 입력값과 로직버전이
                # 다 들어 있어 이 한 번의 대조로 두 경우를 모두 막는다.
                # 옛 레코드는 `_cache_key`가 없어(None) 항상 불일치 -> 재검사한다.
                if report_dict.get("_cache_key") != cache_key:
                    print("    [info] 2차 캐시 키 불일치(입력 변경 또는 로직 버전 상향) -> 신규 검사")
                    return None

                if (
                    "disclaimer" in report_dict
                    and "summary" in report_dict
                    and "n_sentences" in report_dict["summary"]
                ):
                    report = USPreflightReport(**report_dict)
                else:
                    # 구버전/전체 밴드 캐시 검사: 이미지 입력인데 정밀 bbox가 없으면 캐시 무효화
                    findings_data = report_dict.get("findings", [])
                    has_invalid_bbox = any(
                        isinstance(f.get("location"), dict)
                        and f["location"].get("tile") is not None
                        and (
                            f["location"].get("x_start") is None
                            or (
                                f["location"].get("x_start") == 0
                                and f["location"].get("x_end") == f["location"].get("source_w")
                            )
                        )
                        for f in findings_data
                    )
                    if has_invalid_bbox:
                        print("    [info] 정밀 bbox 없는 캐시 감지 -> 신규 VLM 검사 수행")
                        return None

                    report = CheckReport(**report_dict)
                    if result_id:
                        report.result_id = result_id

                _IMAGE_CACHE[cache_key] = report
                return report
            except Exception as e:
                print(f"    [info] 캐시 리포트 복원 실패: {type(e).__name__}: {e}")

    return None


def save_cached_check(cache_key: str, report: object) -> None:
    """리포트를 메모리 캐시에 저장한다."""
    _IMAGE_CACHE[cache_key] = report

