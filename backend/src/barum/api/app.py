"""FastAPI 앱: 판정 백엔드 골격.

`POST /check`가 CheckReport를 동기로 반환한다. 판정은 StubJudge(가짜)라 규칙집이
없어도 프론트가 바로 붙을 수 있다. VLM provider는 하드코딩하지 않고 env로 읽는다.
"""

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from barum.judge.cosmetic import CosmeticJudge, PromptJudge, StubJudge
from barum.models import CheckReport, Region
from barum.pipeline import run_check
from barum.vlm import get_vlm

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
    """
    if os.environ.get("JUDGE_KIND", "prompt") == "stub":
        return StubJudge()
    return PromptJudge(get_vlm(os.environ.get("JUDGE_PROVIDER", "gemini")))


@app.get("/health")
def health() -> dict:
    """헬스체크."""
    return {"status": "ok"}


@app.post("/check", response_model=CheckReport)
async def check(
    region: Region = Form(...),
    ad_text: str | None = Form(None),
    image: UploadFile | None = File(None),
) -> CheckReport:
    """광고(이미지/글 + 나라)를 받아 문구별 위반 findings를 반환한다.

    이미지·글 중 최소 하나는 있어야 한다. 없으면 422.
    """
    image_bytes = await image.read() if image is not None else None
    if not ad_text and not image_bytes:
        raise HTTPException(
            status_code=422, detail="ad_text 또는 image 중 최소 하나는 필요하다."
        )

    # OCR용 VLM은 이미지가 있을 때만 만든다. 판정용 VLM은 judge가 내부에 든다.
    ocr_vlm = get_vlm(os.environ.get("OCR_PROVIDER", "gemini")) if image_bytes else None

    return run_check(
        region=region.value,
        ad_text=ad_text,
        image_bytes=image_bytes,
        image_filename=image.filename if image is not None else None,
        vlm=ocr_vlm,
        judge=_build_judge(),
    )
