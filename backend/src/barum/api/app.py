"""FastAPI 앱: 판정 백엔드 골격.

`POST /check`가 CheckReport를 동기로 반환한다. 판정은 StubJudge(가짜)라 규칙집이
없어도 프론트가 바로 붙을 수 있다. VLM provider는 하드코딩하지 않고 env로 읽는다.
"""

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from barum.judge.cosmetic import StubJudge
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

    # 텍스트 전용 요청은 VLM이 필요 없다. 이미지가 있을 때만 어댑터를 만든다
    # (없으면 GOOGLE_API_KEY 없이도 글 검사가 된다).
    vlm = get_vlm(os.environ.get("OCR_PROVIDER", "gemini")) if image_bytes else None

    return run_check(
        region=region.value,
        ad_text=ad_text,
        image_bytes=image_bytes,
        image_filename=image.filename if image is not None else None,
        vlm=vlm,
        judge=StubJudge(),
    )
