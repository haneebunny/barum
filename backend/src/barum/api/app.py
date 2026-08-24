"""FastAPI 앱: 판정 백엔드 골격.

`POST /check`가 CheckReport를 동기로 반환한다. 판정은 StubJudge(가짜)라 규칙집이
없어도 프론트가 바로 붙을 수 있다. VLM provider는 하드코딩하지 않고 env로 읽는다.
"""

import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from barum.judge.cosmetic import CosmeticJudge, PromptJudge, RagJudge, StubJudge
from barum.judge.us_sunscreen import USSunscreenJudge
from barum.models import (
    CheckReport,
    GenerateRequest,
    GenerateResponse,
    Region,
    RegulatoryBasis,
    RemediationRequest,
    RemediationResponse,
    StoredCheck,
    USPreflightReport,
)
from barum.generate.content import generate_content
from barum.generate.replace import first_safe
from barum.reference.citations import build_regulatory_basis
from barum.reference.remediation import get_remediation
from barum.pipeline import run_check, run_us_sunscreen_check
from barum.storage.checks_store import (
    build_cache_key,
    build_check_row,
    download_image,
    ensure_bucket,
    get_cached_check,
    get_check,
    new_result_id,
    save_cached_check,
    save_check,
    sha256_hex,
    upload_image,
)
from barum.storage.generate_cache import (
    build_generate_cache_key,
    get_cached_generate,
    put_cached_generate,
)
from barum.vlm import get_image_generator, get_vlm, role_model

# 이미지 content-type ↔ 확장자(증거 파일 경로·프록시 응답용). 모르면 옥텟 스트림.
_CT_TO_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_EXT_TO_CT = {v: k for k, v in _CT_TO_EXT.items()}

# **여기서 .env를 읽는다.** 지금까지는 VLM 어댑터들이 각자 `load_dotenv()`를 불렀는데,
# 그러면 어댑터가 하나라도 만들어지기 전까지 이 파일의 env 읽기가 전부 빈손이 된다.
#
# 갓 뜬 프로세스의 **첫 요청**이 그 상태였다. `/generate`가 판정기(→어댑터)보다 먼저
# `IMAGE_GENERATION_ENABLED`를 읽어서, 플래그가 켜져 있는데도 생성기를 안 만들고
# **이미지가 0장 나갔다**(2026-08-23 재현). 두 번째 요청부터는 어댑터가 dotenv를
# 이미 불러놔서 정상 동작해 — 그래서 간헐적으로 보였다.
#
# 같은 함정이 CHECKS_PERSIST·IMAGE_CACHE_ENABLED·JUDGE_KIND 등 이 파일의 다른
# env 읽기에도 그대로 있었다. 앱을 띄울 때 한 번 읽어 그 창을 없앤다.
load_dotenv()


def _git_sha() -> str:
    """지금 체크아웃된 커밋. 못 읽으면 'unknown'(서버는 계속 뜬다)."""
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


_GIT_SHA = _git_sha()
_STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

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

    기본은 RagJudge(규칙집 우선 + 규정 grounding + VLM fallback)다. 검증된 경계표현은
    규칙이 확정하고 나머지만 VLM에 위임한다. 키가 없거나 오프라인에서 돌릴 땐
    JUDGE_KIND=stub로 StubJudge를 쓴다(VLM 호출 없음). JUDGE_KIND=prompt면 규칙집·
    grounding 없는 제로샷 PromptJudge로 내려간다(비교실험·회귀 확인용).

    **기본값 정정(2026-08-19).** 원래 기본은 PromptJudge였다. RagJudge가 없던 시절에
    정해진 값인데, RagJudge가 배포 파이프라인이 된 뒤에도 기본값만 안 따라왔다.
    그래서 `JUDGE_KIND=rag`를 손으로 안 주면 규칙집도 grounding도 안 붙은 채로 돌았다.
    저장소 어디에도 그 값을 설정하는 곳이 없었다(.env·run_api.py·launch.json 전부).
    ROADMAP·평가 문서가 "배포 파이프라인 = RagJudge"로 서술하고 지표도 전부 RagJudge로
    쟀으므로, 코드 기본값을 문서화된 의도에 맞춘다.

    RagJudge는 Supabase가 없어도 죽지 않는다(`_maybe_case_retriever`가 None으로
    degrade, 규정 grounding만 사용). 그래서 기본으로 둬도 안전하다.

    기본 provider = openai(gpt-5-mini). 43문장 평가셋 비교(2026-08-11)에서
    Gemini는 미탐 4건(52.5% 일치)으로 recall 우선 정책에 제일 안 맞았고,
    gpt-5-mini는 미탐 1건(65.0% 일치)에 비용도 무시할 수준이라 하니 승인 하에
    전환(ROADMAP.md §3). OCR_PROVIDER는 안 건드림 — 이 비교는 판정 정확도에
    대한 것이지 OCR 품질에 대한 게 아니다.
    """
    kind = os.environ.get("JUDGE_KIND", "rag")
    if kind == "stub":
        return StubJudge()
    provider = os.environ.get("JUDGE_PROVIDER", "openai")
    vlm = get_vlm(provider, model=role_model("judge"))
    if kind == "prompt":
        return PromptJudge(vlm)
    # 1차 필터는 이진 분류라 더 싼 모델로 나눌 수 있다. PRESCREEN_MODEL을 안 주면
    # None이라 판정 VLM을 그대로 쓴다(클라이언트도 하나만 만든다).
    prescreen_name = role_model("prescreen")
    prescreen_vlm = (
        get_vlm(os.environ.get("PRESCREEN_PROVIDER", provider), model=prescreen_name)
        if prescreen_name
        else None
    )
    return RagJudge(
        vlm, case_retriever=_maybe_case_retriever(), prescreen_vlm=prescreen_vlm
    )


def _maybe_case_retriever():
    """사례 pgvector 검색기를 만든다. Supabase 설정이 없거나 실패하면 None.

    None이면 RagJudge는 규정만으로 grounding(사례는 cases.md 통째 대신 없음). 판정
    자체는 Supabase 없이도 돌아간다 — 사례 검색은 부가 근거일 뿐이라 없어도 죽지 않게.
    """
    try:
        from barum.storage.cases_store import build_case_retriever

        return build_case_retriever()
    except Exception as e:
        print(f"[warn] 사례 검색 비활성(규정 grounding만 사용): {type(e).__name__}: {e}")
        return None


def _checks_client():
    """검사 이력·이미지 저장용 Supabase 클라이언트. 테스트는 이걸 가짜로 갈아낀다."""
    from barum.storage.client import get_supabase_client

    return get_supabase_client()


def _maybe_checks_client():
    """CHECKS_PERSIST가 꺼져 있거나 클라이언트 생성 실패 시 None을 돌려준다."""
    if os.environ.get("CHECKS_PERSIST", "1") == "0":
        return None
    try:
        return _checks_client()
    except Exception:
        return None



def _persist_check(
    report: CheckReport,
    region: str,
    image_bytes: bytes | None,
    content_type: str | None,
    product_name: str | None = None,
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
            result_id, region, report.model_dump(mode="json"), image_sha256, image_path,
            product_name=product_name,
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


@app.get("/reference/basis", response_model=dict[str, RegulatoryBasis])
def get_reference_basis() -> dict[str, RegulatoryBasis]:
    """지금 시점 적용 기준(프론트 푸터용). `{"kr": ..., "us": ...}`.

    `CheckReport.basis`와 같은 소스(citation_registry.json)에서 읽지만, 이건 항상
    "지금" 기준이고 검사 시점 스냅샷이 아니다. 리포트 화면은 `report.basis`를 쓰고,
    검사와 무관한 화면(홈·검사 시작 전)은 이 엔드포인트를 쓴다.
    """
    return {
        "kr": build_regulatory_basis("KR"),
        "us": build_regulatory_basis("US"),
    }


@app.get("/reports/{result_id}", response_model=StoredCheck)
def get_report(result_id: str) -> StoredCheck:
    """저장된 검사를 다시 본다. 추측불가 result_id가 접근권이라 못 찾으면 404."""
    row = get_check(_checks_client(), result_id)
    if row is None:
        raise HTTPException(status_code=404, detail="해당 검사 이력을 찾을 수 없습니다.")
    
    region = Region(row["region"])
    if region == Region.US:
        report = USPreflightReport(**row["report"])
    else:
        report = CheckReport(**row["report"])

    return StoredCheck(
        result_id=row["id"],
        created_at=str(row["created_at"]),
        region=region,
        image_available=bool(row.get("image_path")),
        product_name=row.get("product_name"),
        report=report,
    )


@app.get("/reports/{result_id}/image")
def get_report_image(result_id: str) -> Response:
    """저장된 원본 이미지를 백엔드가 그대로 스트리밍(버킷 private, 서명 URL 없음)."""
    row = get_check(_checks_client(), result_id)
    if row is None or not row.get("image_path"):
        raise HTTPException(status_code=404, detail="해당 검사에 첨부된 원본 이미지가 없습니다.")
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
    ingredient_amounts: str | None = Form(
        None,
        description='"성분:함량" 콤마구분(예: "나이아신아마이드:3%,알부틴:10%"). '
        "명시된 성분만 함량기준 대조까지 더해져 2호 판정이 더 정확해진다.",
    ),
    product_name: str | None = Form(
        None, description="상품명 또는 광고 제목. 있으면 판정 대상에 포함된다."
    ),
) -> CheckReport:
    """광고(이미지/글 + 나라)를 받아 문구별 위반 findings를 반환한다.

    이미지·글 중 최소 하나는 있어야 한다. 없으면 422. ingredients, ingredient_amounts,
    product_name은 선택.
    """
    image_bytes = await image.read() if image is not None else None
    if not ad_text and not image_bytes:
        raise HTTPException(
            status_code=422,
            detail="광고 문구(ad_text) 또는 광고 이미지(image) 중 최소 하나는 입력해야 합니다.",
        )

    cache_key = None
    if image_bytes and os.environ.get("IMAGE_CACHE_ENABLED", "1") != "0":
        image_sha256 = sha256_hex(image_bytes)
        cache_key = build_cache_key(
            image_sha256=image_sha256,
            region_or_country=region.value,
            ad_text=ad_text,
            ingredients=ingredients,
            ingredient_amounts=ingredient_amounts,
            product_name=product_name,
        )
        cached_report = get_cached_check(_maybe_checks_client(), cache_key, image_sha256)
        if cached_report is not None and isinstance(cached_report, CheckReport):
            print(f"    [info] 이미지 동일, 캐시된 리포트 사용 (sha256={image_sha256[:8]})")
            return cached_report

    # OCR용 VLM은 이미지가 있을 때만 만든다. 판정용 VLM은 judge가 내부에 든다.
    ocr_vlm = (
        get_vlm(os.environ.get("OCR_PROVIDER", "gemini"), model=role_model("ocr"))
        if image_bytes
        else None
    )

    report = run_check(
        region=region.value,
        ad_text=ad_text,
        image_bytes=image_bytes,
        image_filename=image.filename if image is not None else None,
        vlm=ocr_vlm,
        judge=_build_judge(),
        ingredients=ingredients,
        ingredient_amounts=ingredient_amounts,
        product_name=product_name,
        rewriter=_replacement_rewriter(),
    )
    # 결과·증거 저장(실패해도 응답은 살아있게). 저장되면 result_id를 응답에 싣는다.
    report.result_id = _persist_check(
        report, region.value, image_bytes, image.content_type if image else None,
        product_name=product_name,
    )
    if cache_key:
        save_cached_check(cache_key, report)
    return report


@app.post("/check/us-sunscreen", response_model=USPreflightReport)
async def check_us_sunscreen(
    country: str = Form(
        "US", description="대상국. 1차 대상국은 미국만 지원(팀 확정). 다른 값은 400."
    ),
    ad_text: str | None = Form(None),
    image: UploadFile | None = File(None),
    ingredients: str | None = Form(
        None, description="전성분(콤마 구분). 있으면 미국 승인 자외선차단 성분 대조가 붙는다."
    ),
    product_name: str | None = Form(
        None, description="상품명 또는 광고 제목. 있으면 판정 대상에 포함된다."
    ),
) -> USPreflightReport:
    """미국 프리플라이트(자외선차단 최소보장) 검사. 국내 `/check`와 별도 엔드포인트(팀 확정).

    위반/합법 판정이 아니라 "화장품→OTC의약품 분류전환" 안내다(USPreflightCategory 참조).
    country는 프론트가 넘기되 지금은 미국만 실동작(`sunscreen_otc_classification.md` 스코프).
    이미지·글 중 최소 하나는 있어야 한다.
    """
    if country != "US":
        raise HTTPException(
            status_code=400,
            detail=f"현재는 미국(US) 프리플라이트만 지원합니다. 받은 값: {country!r}",
        )

    image_bytes = await image.read() if image is not None else None
    if not ad_text and not image_bytes:
        raise HTTPException(
            status_code=422,
            detail="광고 문구(ad_text) 또는 광고 이미지(image) 중 최소 하나는 입력해야 합니다.",
        )

    cache_key = None
    if image_bytes and os.environ.get("IMAGE_CACHE_ENABLED", "1") != "0":
        image_sha256 = sha256_hex(image_bytes)
        cache_key = build_cache_key(
            image_sha256=image_sha256,
            region_or_country=country,
            ad_text=ad_text,
            ingredients=ingredients,
            product_name=product_name,
        )
        cached_report = get_cached_check(_maybe_checks_client(), cache_key, image_sha256)
        if cached_report is not None and isinstance(cached_report, USPreflightReport):
            print(f"    [info] 이미지 동일, 캐시된 US 리포트 사용 (sha256={image_sha256[:8]})")
            return cached_report

    ocr_vlm = (
        get_vlm(os.environ.get("OCR_PROVIDER", "gemini"), model=role_model("ocr"))
        if image_bytes
        else None
    )

    report = run_us_sunscreen_check(
        ad_text=ad_text,
        image_bytes=image_bytes,
        image_filename=image.filename if image is not None else None,
        vlm=ocr_vlm,
        judge=USSunscreenJudge(),
        ingredients=ingredients,
        product_name=product_name,
    )
    report.result_id = _persist_check(
        report,
        region="US",
        image_bytes=image_bytes,
        content_type=image.content_type if image is not None else None,
        product_name=product_name,
    )
    if cache_key:
        save_cached_check(cache_key, report)
    return report


@app.post("/remediate", response_model=RemediationResponse)
def remediate(req: RemediationRequest) -> RemediationResponse:
    """위반 문구(sentence)와 유형(violation_type)을 입력받아 대체 표현을 제안한다.

    **조건표 후보를 그대로 내려주지 않고 안전한 것 하나만 고른다.**

    예전엔 `get_remediation()`이 낸 배열을 그대로 돌려줬고 프론트가 그걸 쉼표로
    이어 붙여 보여줬다. 그래서 리포트 화면에 모순이 보였다(2026-08-20 팀장 발견):
    같은 화면 카드 #3에서 `진정`이 검토필요로 걸리는데, 카드 #9의 대체표현 제안이
    "피부 진정, 자극 완화"였다. 우리가 방금 문제 삼은 표현을 우리가 추천한 것이다.

    `first_safe()`는 위반 후보를 버리고 검토필요 후보를 뒤로 미룬다(`generate/replace.py`).
    조건표에는 1순위가 검토필요인데 2순위가 깨끗한 규칙이 실제로 있다.

    **LLM 재작성은 여기서 안 한다.** 카드를 펼칠 때마다 실시간 호출이라 건당 5~8초가
    붙었다. 다듬은 대체표현은 이제 판정할 때 배치로 한 번에 만들어 `CheckReport.
    replacements`에 실려 온다(`pipeline._build_replacements_for_report`, 2026-08-22
    팀장 지시). 리포트 화면은 그걸 읽으므로 이 엔드포인트를 부를 일이 없다.

    그래도 남겨둔다. replacements가 비어 있는 경우(생성 실패, 이 필드 이전에 저장된
    옛 리포트)에 즉시 답할 폴백이 필요하고, 조건표 경로는 과금도 지연도 0이다.
    """
    span = req.span if req.span is not None else req.sentence
    suggestions, disclaimer = get_remediation(
        sentence=req.sentence,
        violation_type=req.violation_type,
        span=req.span,
    )
    safe = first_safe(suggestions) if suggestions else None
    return RemediationResponse(
        sentence=req.sentence,
        violation_type=req.violation_type,
        span=span,
        suggestions=[safe] if safe else [],
        disclaimer=disclaimer,
    )


def _section_vlm():
    """저위험 서술 생성용 LLM. 테스트는 이걸 가짜로 갈아낀다.

    GENERATE_PROVIDER로 따로 지정 가능, 없으면 판정 provider(gpt-5-mini) 재사용.
    """
    return get_vlm(
        os.environ.get("GENERATE_PROVIDER", os.environ.get("JUDGE_PROVIDER", "openai")),
        model=role_model("generate"),
    )


def _replacement_rewriter():
    """대체표현 문장 다듬기용 LLM. 저위험 서술과 같은 provider를 쓴다.

    OCR용 VLM을 재사용하면 안 된다. 그건 이미지가 있을 때만 만들어져서, 글로만
    검사하면 None이 되고 대체표현이 조용히 조건표 문구로 떨어진다.

    **JUDGE_KIND=stub이면 None.** stub은 "외부 호출 없이 돈다"는 뜻이고 유닛테스트가
    그 모드로 /check를 부른다. 여기서 재작성기를 쥐여주면 테스트가 과금 호출을 낸다
    (실제로 그랬다, 2026-08-22: 테스트 4건이 28초를 실호출에 썼다).
    """
    if os.environ.get("JUDGE_KIND", "rag") == "stub":
        return None
    return _section_vlm()


def _image_generator():
    """모듈별 배경 이미지 생성기. `IMAGE_GENERATION_ENABLED=1`일 때만 켠다.

    기본 비활성이다(이미지 모델이 아직 확정 전이라는 안전장치, 2026-08-18 팀장·PM
    확정). 켜면 `/generate` 요청마다(create 모드 + 이미지 생성 체크박스 켰을 때)
    실제 과금(OpenAI gpt-image 계열)이 나간다. None을 내면 build_image_plan이
    이미지 생성 경로를 아예 안 탄다(content.py 쪽 안전장치, 여기 안 건드림).
    """
    if os.environ.get("IMAGE_GENERATION_ENABLED", "0") != "1":
        return None
    return get_image_generator(model=role_model("image"))


def _image_sink(client):
    """생성된 모듈 이미지를 private 버킷에 올리고, 스트리밍 프록시 경로를 낸다.

    `/reports/{result_id}/image`와 같은 이유로 직접 버킷 URL을 안 준다(서명 URL
    안 씀, 버킷 자체가 private). 검사 이미지는 result_id로 찾지만 생성 이미지는
    딸린 검사 레코드가 없어서, 이미지 하나하나를 UUID로 주소를 매긴다.
    """
    def sink(module_kind: str, data: bytes) -> str | None:
        image_id = uuid4().hex
        ensure_bucket(client)
        upload_image(client, f"generated/{image_id}.png", data, "image/png")
        return f"/generated/{image_id}"
    return sink


# UUID hex(32자 16진수)만 받는다. path traversal 방지(경로 그대로 스토리지 조회에 씀).
_IMAGE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@app.get("/generated/{image_id}")
def get_generated_image(image_id: str) -> Response:
    """`_image_sink`가 저장한 생성 이미지를 스트리밍한다(버킷 private, 서명 URL 없음)."""
    if not _IMAGE_ID_RE.match(image_id):
        raise HTTPException(status_code=404, detail="잘못된 이미지 id입니다.")
    try:
        data = download_image(_checks_client(), f"generated/{image_id}.png")
    except Exception:
        raise HTTPException(status_code=404, detail="해당 생성 이미지를 찾을 수 없습니다.")
    return Response(content=data, media_type="image/png")


# uuid hex(32자) + 확장자(png/jpg/webp)만 받는다. 확장자를 id에 포함시켜서(업로드
# 원본 포맷을 그대로 보관), 저장 경로도 그대로 재구성한다(path traversal 방지,
# 화이트리스트 확장자 외엔 전부 거부).
_PHOTO_ID_RE = re.compile(r"^[0-9a-f]{32}\.(?:png|jpg|webp)$")


@app.post("/uploads/product-photo")
async def upload_product_photo(photo: UploadFile = File(...)) -> dict:
    """판매자가 올리는 제품사진을 저장하고 photo_id를 낸다(create 모드, AI 합성 참조용).

    `/generate`는 복잡한 JSON 바디(ingredient_amounts 등 중첩 리스트)라 통째로
    multipart로 바꾸지 않고, `/generated/{image_id}`와 같은 "먼저 올려 id를 받고
    나중에 그 id로 참조" 패턴을 그대로 따른다(냐냐·PM과 확정, 2026-08-19).
    응답의 photo_id를 `GenerateRequest.product_photo_ids`에 담아 `/generate`로 보낸다.
    """
    ext = _CT_TO_EXT.get(photo.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=415, detail=f"지원하지 않는 이미지 형식입니다: {photo.content_type!r}"
        )
    data = await photo.read()
    if not data:
        raise HTTPException(status_code=422, detail="빈 파일입니다.")
    photo_id = f"{uuid4().hex}{ext}"
    client = _checks_client()
    ensure_bucket(client)
    upload_image(client, f"uploads/{photo_id}", data, photo.content_type)
    return {"photo_id": photo_id}


def _resolve_reference_photos(client):
    """`GenerateRequest` → 참조 이미지 바이트 목록. `generate_content`에 주입한다.

    create·improve가 참조를 서로 다른 곳에서 찾는다(2026-08-24, PM 요청으로 improve
    까지 확장). create는 `product_photo_ids`(별도 업로드, `uploads/{id}`), improve는
    `result_id`로 찾는 원본 검사 이미지(`row["image_path"]`) - 저장 키 체계가 달라
    조회 경로를 가른다. 둘 다 없으면 빈 목록(참조 없이 배경만 생성).

    id 형식이 안 맞거나 조회에 실패한 사진은 예상된 실패라 건너뛴다(전체 요청을
    막지 않는다. 참조 없이 배경만 생성되는 쪽으로 계속 진행).

    **`product_photo_ids`가 있는데 전부 실패해도 `result_id`로는 안 내려간다**
    (베베 리뷰, 2026-08-24). 지금은 문제가 안 된다 - create는 이 용도로 result_id를
    안 보내고 improve는 product_photo_ids를 안 보낸다(둘 다 있는 요청이 없다). 두
    필드가 실제로 같이 오는 흐름이 생기면 그때 폴백 방향을 정할 것 - 지금 스펙 없이
    추측으로 넣지 않는다.
    """
    def resolve(req) -> list[bytes]:
        if req.product_photo_ids:
            images: list[bytes] = []
            for photo_id in req.product_photo_ids:
                if not _PHOTO_ID_RE.match(photo_id):
                    print(f"    [skip] 잘못된 photo_id 형식: {photo_id!r}")
                    continue
                try:
                    images.append(download_image(client, f"uploads/{photo_id}"))
                except Exception as e:
                    print(f"    [skip] 제품사진 조회 실패({photo_id}): {type(e).__name__}: {e}")
            return images
        if req.result_id:
            row = get_check(client, req.result_id)
            if row is None or not row.get("image_path"):
                return []
            try:
                return [download_image(client, row["image_path"])]
            except Exception as e:
                print(f"    [skip] 리포트 이미지 조회 실패({req.result_id}): {type(e).__name__}: {e}")
        return []
    return resolve


@app.get("/version")
def version() -> dict:
    """지금 도는 서버가 **어느 코드인지** 알려준다.

    오늘 두 번, 머지된 코드가 안 도는 상태에서 결과를 보고 원인을 엉뚱한 데서
    찾았다(낡은 프로세스 / 캐시 의심). 두 번 다 `/openapi.json`에 특정 필드가
    있는지로 역추적했는데 그건 우회다. 한 줄로 확정할 수 있게 노출한다.

        curl -s localhost:8000/version
    """
    return {"sha": _GIT_SHA, "started_at": _STARTED_AT}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """검사된 광고를 안전 버전으로 생성·개선한다(FR-11/13, improve+create).

    위반 문구는 조건표로 결정적 치환, 저위험 서술은 LLM 생성, 생성물은 재검증한다.
    create 모드의 모듈별 배경 이미지 생성은 `IMAGE_GENERATION_ENABLED=1`일 때만
    실제로 돈다(기본 비활성). 꺼져 있으면 image_generator=None이라 이미지 관련
    인자를 안 만들고 그대로 통과한다(불필요한 Supabase 클라이언트 생성 회피).
    """
    # 같은 입력이면 다시 만들지 않는다. 이미지를 켜면 한 번에 125초가 걸려서,
    # 시연 준비처럼 같은 입력을 반복할 때 그 시간과 과금을 매번 다시 쓸 이유가 없다.
    cache_key = build_generate_cache_key(req)
    cached = get_cached_generate(cache_key)
    if cached is not None:
        print(f"    [info] 동일 입력, 캐시된 생성 결과 사용 (key={cache_key[:8]})")
        return cached

    image_gen = _image_generator()
    client = _checks_client() if image_gen else None
    resp = generate_content(
        req,
        judge=_build_judge(),
        vlm=_section_vlm(),
        image_generator=image_gen,
        image_sink=_image_sink(client) if client else None,
        photo_resolver=_resolve_reference_photos(client) if client else None,
    )
    put_cached_generate(cache_key, resp)
    return resp
