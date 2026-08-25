"""심사위원 데모용 고정 픽스처를 굽는다(유어베리 세럼, 검사·개선·신규생성 3종).

왜. 배포 사이트를 심사위원이 직접 만진다. 실시간 생성은 위험하다 — 이미지 생성
과금, 요청당 ~125초, 실행편차. 그래서 데모는 **한 번 구워 커밋한 고정 결과**를
프론트가 그대로 렌더한다(백엔드/Supabase 런타임 의존 0). 이 스크립트가 그 결과를
만든다.

무엇을 만드나(전부 저장소에 커밋되는 정적 파일):
  frontend/lib/demo/fixtures/report.json    검사 리포트(ReportEnvelope)
  frontend/lib/demo/fixtures/improve.json   개선 생성 결과(GenerateResponse)
  frontend/lib/demo/fixtures/create.json    신규 생성 결과(GenerateResponse)
  frontend/public/demo/generated/*.png      생성된 배경 이미지(정적)
  frontend/public/demo/yourberry_serum_detail.png  검사 입력 상세이미지(복사)

**과금 호출이다(이미지 생성 포함).** 팀장 전용 실행. IMAGE_GENERATION_ENABLED와
무관하게 image_generator를 직접 주입해 이미지까지 굽는다. .env(GEMINI/OPENAI 키)가
있어야 한다. 이 스크립트는 파일만 만든다 — 실행 여부는 사람이 정한다.

사용:
    cd backend && venv/bin/python scripts/bake_demo.py

굽고 나면 산출된 fixtures/*.json 과 public/demo/* 를 커밋하면 데모가 갱신된다.
"""

import json
import shutil
import sys
from pathlib import Path

# backend 루트와 src를 둘 다 올린다. pipeline._ocr_image가 backend 루트의 top-level
# 모듈 `tile_split`을 import하므로(conftest도 ROOT·ROOT/src 둘 다 넣는다) src만으론 부족.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR / "src"))
sys.path.insert(0, str(_BACKEND_DIR))

from barum.generate.content import generate_content  # noqa: E402
from barum.judge.cosmetic import RagJudge  # noqa: E402
from barum.models import ApprovedReplacement, GenerateRequest  # noqa: E402
from barum.pipeline import run_check  # noqa: E402
from barum.vlm import get_image_generator, get_vlm, role_model  # noqa: E402

# --- 경로 (backend/에서 실행한다고 가정) ---
_REPO = Path(__file__).resolve().parent.parent.parent  # backend/scripts/ -> repo root
_BACKEND = _REPO / "backend"
_FIXTURE_DIR = _REPO / "frontend" / "lib" / "demo" / "fixtures"
_PUBLIC_DEMO = _REPO / "frontend" / "public" / "demo"
_IMG_DIR = _PUBLIC_DEMO / "generated"
_DETAIL_SRC = _BACKEND / "data" / "demo" / "yourberry_serum_detail.png"

# 데모 식별자. 프론트 lib/demo/demo.ts의 상수와 반드시 같아야 한다.
DEMO_RESULT_ID = "demo-yourberry-serum"
DEMO_PRODUCT_NAME = "유어베리 글로우 리제너레이션 세럼"
# created_at은 고정한다. 매번 now()면 픽스처가 실행마다 바뀌어 diff가 지저분해진다.
DEMO_CREATED_AT = "2026-08-25T00:00:00+00:00"

# 검사 입력 텍스트(이미지 OCR이 주 경로지만, 참고·폴백용으로 남긴다).
DEMO_AD_TEXT = """YOURBERRY (유어베리) 유어베리 글로우 리제너레이션 세럼
줄기세포 배양 기술 안티에이징
세포재생의 시작 / 피부 재생 솔루션
손상된 피부 세포를 빠르게 재생하여
진피층까지 침투하여
콜라겐 밀도 38% 증가 (4주 사용시)
전국 약국 오프라인매장 입점!"""


def _file_sink(mode: str):
    """(module_kind, PNG바이트) -> '/demo/generated/{mode}_{kind}.png'. 파일로 떨군다."""
    _IMG_DIR.mkdir(parents=True, exist_ok=True)

    def sink(module_kind: str, data: bytes) -> str:
        # module_kind는 replacement_0·hero_intro·_canvas 등 파일명에 안전한 값들이다.
        name = f"{mode}_{module_kind.strip('_') or 'bg'}"
        (_IMG_DIR / f"{name}.png").write_bytes(data)
        return f"/demo/generated/{name}.png"

    return sink


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {path.relative_to(_REPO)}")


def main() -> int:
    if not _DETAIL_SRC.exists():
        print(f"[에러] 검사 상세이미지가 없다: {_DETAIL_SRC}")
        return 1

    vlm = get_vlm("openai")  # 판정·리라이터·문구 생성
    ocr_vlm = get_vlm("gemini", model=role_model("ocr"))
    image_gen = get_image_generator(model=role_model("image"))  # 이미지 생성기(과금)
    judge = RagJudge(vlm)

    image_bytes = _DETAIL_SRC.read_bytes()

    # 1) 검사(규제 검증) — 상세이미지 OCR로 실제 파이프라인을 태운다.
    print("[1/3] 검사(OCR+판정) 굽는 중 …")
    report = run_check(
        region="KR",
        ad_text=None,
        image_bytes=image_bytes,
        image_filename=_DETAIL_SRC.name,
        vlm=ocr_vlm,
        judge=judge,
        rewriter=vlm,  # report.replacements를 채워 개선 요청에 쓴다
    )
    report.result_id = DEMO_RESULT_ID
    envelope = {
        "result_id": DEMO_RESULT_ID,
        "created_at": DEMO_CREATED_AT,
        "region": "KR",
        "image_available": True,
        "product_name": DEMO_PRODUCT_NAME,
        "report": report.model_dump(mode="json"),
    }
    _dump(_FIXTURE_DIR / "report.json", envelope)
    print(f"  지적 {len(report.findings)}건 / 대체표현 {len(report.replacements or [])}건")

    # 2) 개선(improve) — 리포트의 대체표현을 전부 승인한 상태로 생성.
    print("[2/3] 개선 생성(이미지 포함) 굽는 중 …")
    approved = [
        ApprovedReplacement(
            original=r.original,
            replaced=r.replaced,
            violation_type=r.violation_type,
            finding_index=r.finding_index,
            note=r.note,
        )
        for r in (report.replacements or [])
    ]
    improve_req = GenerateRequest(
        mode="improve",
        content=DEMO_AD_TEXT,
        result_id=DEMO_RESULT_ID,
        product_name=DEMO_PRODUCT_NAME,
        approved_replacements=approved,
    )
    improve_resp = generate_content(
        improve_req, judge=judge, vlm=vlm, image_generator=image_gen, image_sink=_file_sink("improve")
    )
    _dump(_FIXTURE_DIR / "improve.json", improve_resp.model_dump(mode="json"))
    print(f"  카드 {len(improve_resp.cards or [])}장")

    # 3) 신규 생성(create) — 같은 제품을 무에서 상세페이지로.
    print("[3/3] 신규 생성(이미지 포함) 굽는 중 …")
    create_req = GenerateRequest(
        mode="create",
        product_name=DEMO_PRODUCT_NAME,
        certifications=[],
    )
    create_resp = generate_content(
        create_req, judge=judge, vlm=vlm, image_generator=image_gen, image_sink=_file_sink("create")
    )
    _dump(_FIXTURE_DIR / "create.json", create_resp.model_dump(mode="json"))
    print(f"  카드 {len(create_resp.cards or [])}장")

    # 검사 입력 이미지도 프론트 public으로 복사(inspect 프리필이 File로 로드).
    _PUBLIC_DEMO.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_DETAIL_SRC, _PUBLIC_DEMO / "yourberry_serum_detail.png")
    print(f"  copied {(_PUBLIC_DEMO / 'yourberry_serum_detail.png').relative_to(_REPO)}")

    print("\n완료. frontend/lib/demo/fixtures/*.json 과 frontend/public/demo/* 를 커밋하면 데모가 갱신된다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
