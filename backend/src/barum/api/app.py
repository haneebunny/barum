"""FastAPI 앱: 판정 백엔드 골격.

`POST /check`가 CheckReport를 동기로 반환한다. 판정은 StubJudge(가짜)라 규칙집이
없어도 프론트가 바로 붙을 수 있다. VLM provider는 하드코딩하지 않고 env로 읽는다.
"""

import os

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from barum.judge.cosmetic import CosmeticJudge, PromptJudge, StubJudge
from barum.models import CheckReport, Region, StoredCheck
from barum.pipeline import run_check
from barum.storage.checks_store import (
    build_check_row,
    download_image,
    ensure_bucket,
    get_check,
    new_result_id,
    save_check,
    sha256_hex,
    upload_image,
)
from barum.vlm import get_vlm

# 이미지 content-type ↔ 확장자(증거 파일 경로·프록시 응답용). 모르면 옥텟 스트림.
_CT_TO_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_EXT_TO_CT = {v: k for k, v in _CT_TO_EXT.items()}

app = FastAPI(title="barum 판정 백엔드", version="0.1.0")

# 개발 편의: 프론트 dev 서버(다른 포트)에서 호출할 수 있게 CORS를 연다.
# 서비스화 단계에서 허용 오리진을 좁힌다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_judge() -> CosmeticJudge:
    """판정기를 만든다.

    기본은 PromptJudge(VLM 제로샷, JUDGE_PROVIDER). 키가 없거나 오프라인에서
    돌릴 땐 JUDGE_KIND=stub로 StubJudge를 쓴다(VLM 호출 없음).

    기본 provider = openai(gpt-5-mini). 43문장 평가셋 비교(2026-08-11)에서
    Gemini는 미탐 4건(52.5% 일치)으로 recall 우선 정책에 제일 안 맞았고,
    gpt-5-mini는 미탐 1건(65.0% 일치)에 비용도 무시할 수준이라 하니 승인 하에
    전환(ROADMAP.md §3). OCR_PROVIDER는 안 건드림 — 이 비교는 판정 정확도에
    대한 것이지 OCR 품질에 대한 게 아니다.
    """
    if os.environ.get("JUDGE_KIND", "prompt") == "stub":
        return StubJudge()
    return PromptJudge(get_vlm(os.environ.get("JUDGE_PROVIDER", "openai")))


def _checks_client():
    """검사 이력·이미지 저장용 Supabase 클라이언트. 테스트는 이걸 가짜로 갈아낀다."""
    from barum.storage.client import get_supabase_client

    return get_supabase_client()


def _persist_check(
    report: CheckReport,
    region: str,
    image_bytes: bytes | None,
    content_type: str | None,
) -> str | None:
    """검사 결과·증거를 저장하고 result_id를 낸다. 저장 못 하면 None(응답은 계속).

    저장은 부가 기능이라(증거 보존·다시 보기) Supabase가 없거나 실패해도 판정 응답
    자체는 살아야 한다. 그래서 예상된 실패는 삼켜 None을 돌려준다(FR: 예상된 실패 스킵).
    CHECKS_PERSIST=0이면 저장을 아예 건너뛴다(오프라인·테스트).
    """
    if os.environ.get("CHECKS_PERSIST", "1") == "0":
        return None
    try:
        client = _checks_client()
        result_id = new_result_id()
        image_sha256 = image_path = None
        if image_bytes:
            image_sha256 = sha256_hex(image_bytes)
            ensure_bucket(client)
            ext = _CT_TO_EXT.get(content_type or "", ".bin")
            image_path = f"{result_id}{ext}"
            upload_image(client, image_path, image_bytes, content_type or "application/octet-stream")
        row = build_check_row(
            result_id, region, report.model_dump(mode="json"), image_sha256, image_path
        )
        save_check(client, row)
        return result_id
    except Exception as e:
        print(f"[warn] 검사 저장 실패(result_id 없이 응답): {type(e).__name__}: {e}")
        return None


@app.get("/health")
def health() -> dict:
    """헬스체크."""
    return {"status": "ok"}


@app.get("/reports/{result_id}", response_model=StoredCheck)
def get_report(result_id: str) -> StoredCheck:
    """저장된 검사를 다시 본다. 추측불가 result_id가 접근권이라 못 찾으면 404."""
    row = get_check(_checks_client(), result_id)
    if row is None:
        raise HTTPException(status_code=404, detail="해당 검사를 찾을 수 없다.")
    return StoredCheck(
        result_id=row["id"],
        created_at=str(row["created_at"]),
        region=Region(row["region"]),
        image_available=bool(row.get("image_path")),
        report=CheckReport(**row["report"]),
    )


@app.get("/reports/{result_id}/image")
def get_report_image(result_id: str) -> Response:
    """저장된 원본 이미지를 백엔드가 그대로 스트리밍(버킷 private, 서명 URL 없음)."""
    row = get_check(_checks_client(), result_id)
    if row is None or not row.get("image_path"):
        raise HTTPException(status_code=404, detail="이미지가 없다.")
    path = row["image_path"]
    data = download_image(_checks_client(), path)
    ext = path[path.rfind(".") :] if "." in path else ""
    return Response(content=data, media_type=_EXT_TO_CT.get(ext, "application/octet-stream"))


@app.post("/check", response_model=CheckReport)
async def check(
    region: Region = Form(...),
    ad_text: str | None = Form(None),
    image: UploadFile | None = File(None),
    ingredients: str | None = Form(
        None, description="전성분(콤마 구분). 있으면 2호 판정에 성분 정합 대조가 붙는다."
    ),
) -> CheckReport:
    """광고(이미지/글 + 나라)를 받아 문구별 위반 findings를 반환한다.

    이미지·글 중 최소 하나는 있어야 한다. 없으면 422. ingredients는 선택.
    """
    image_bytes = await image.read() if image is not None else None
    if not ad_text and not image_bytes:
        raise HTTPException(
            status_code=422, detail="ad_text 또는 image 중 최소 하나는 필요하다."
        )

    # OCR용 VLM은 이미지가 있을 때만 만든다. 판정용 VLM은 judge가 내부에 든다.
    ocr_vlm = get_vlm(os.environ.get("OCR_PROVIDER", "gemini")) if image_bytes else None

    report = run_check(
        region=region.value,
        ad_text=ad_text,
        image_bytes=image_bytes,
        image_filename=image.filename if image is not None else None,
        vlm=ocr_vlm,
        judge=_build_judge(),
        ingredients=ingredients,
    )
    # 결과·증거 저장(실패해도 응답은 살아있게). 저장되면 result_id를 응답에 싣는다.
    report.result_id = _persist_check(
        report, region.value, image_bytes, image.content_type if image else None
    )
    return report
