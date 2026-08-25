"""POST /generate 엔드포인트 유닛테스트 (오프라인: StubJudge + 가짜 섹션 LLM).

    ./venv/bin/python -m pytest tests/test_generate_api.py -q
"""

import os

os.environ["JUDGE_KIND"] = "stub"
os.environ["CHECKS_PERSIST"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from barum.api import app as app_module  # noqa: E402
from barum.models import GenerateRequest  # noqa: E402

client = TestClient(app_module.app)


class FakeVLM:
    def generate_json(self, prompt, images):
        return {"제품개요": "담백한 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"}


@pytest.fixture(autouse=True)
def _fake_section_vlm(monkeypatch):
    monkeypatch.setattr(app_module, "_section_vlm", lambda: FakeVLM())


def test_generate_endpoint_returns_structured_content():
    r = client.post(
        "/generate",
        json={"content": "재생 크림입니다. 문의 010-1234-5678", "product_name": "테스트크림"},
    )
    assert r.status_code == 200
    body = r.json()
    assert any(s["kind"] == "광고문구" for s in body["sections"])
    # 개선 모드는 저위험 서술을 LLM으로 만들지 않는다(2026-08-24, 사유는
    # test_generate_content.py 같은 이름 테스트 주석 참고). 대체표현 섹션이 그 자리다.
    assert any((s["module_kind"] or "").startswith("replacement_") for s in body["sections"])
    assert body["replacements"][0]["original"] == "재생"
    assert "전화번호" in body["pii_removed"]
    assert body["recheck"] is not None
    assert body["disclaimer"]


def test_generate_requires_content():
    """content 없으면 422(pydantic 검증)."""
    r = client.post("/generate", json={"product_name": "x"})
    assert r.status_code == 422


# ── create 모드 이미지 생성 배선 (2026-08-18, 냐냐 발견 버그 수정) ──────────────


class FakeImageGenerator:
    def __init__(self, *results):
        self._results = list(results)
        self.images_received: list[list] = []

    def generate_image(self, prompt, images):
        self.images_received.append(images)
        r = self._results.pop(0) if self._results else b"PNG"
        if isinstance(r, Exception):
            raise r
        return r


class FakeBucketClient:
    """ensure_bucket·upload_image·download_image가 기대하는 최소 Storage 인터페이스."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.storage = self

    def list_buckets(self):
        return []

    def create_bucket(self, name, options=None):
        return None

    def from_(self, bucket):
        return self

    def upload(self, path, data, opts):
        self.files[path] = data

    def download(self, path):
        if path not in self.files:
            raise RuntimeError("not found")
        return self.files[path]


_PLAN = {
    "modules": [
        {"kind": "hero_intro", "purpose": "도입", "has_claim_risk": False},
    ]
}
_MODULE_TEXT = {"sections": [{"kind": "hero_intro", "text": "일상에 쓰기 좋은 제품입니다."}]}


class SequenceVLM:
    def __init__(self, *results):
        self._results = list(results)

    def generate_json(self, prompt, images):
        return self._results.pop(0) if self._results else {}


def test_이미지생성_기본값은_비활성이다(monkeypatch):
    """IMAGE_GENERATION_ENABLED 안 주면 image_generator가 None이라 module_images가 빈 배열."""
    monkeypatch.delenv("IMAGE_GENERATION_ENABLED", raising=False)
    assert app_module._image_generator() is None


def test_이미지생성_활성화하면_생성기를_만든다(monkeypatch):
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "1")
    monkeypatch.setattr(app_module, "get_image_generator", lambda model=None: FakeImageGenerator())
    assert app_module._image_generator() is not None


def test_image_sink이_버킷에_올리고_프록시_경로를_낸다():
    client_fake = FakeBucketClient()
    sink = app_module._image_sink(client_fake)
    url = sink("hero_intro", b"PNGDATA")
    assert url.startswith("/generated/")
    image_id = url.removeprefix("/generated/")
    assert client_fake.files[f"generated/{image_id}.png"] == b"PNGDATA"


def test_generated_이미지_라우트가_스트리밍한다(monkeypatch):
    client_fake = FakeBucketClient()
    monkeypatch.setattr(app_module, "_checks_client", lambda: client_fake)
    sink = app_module._image_sink(client_fake)
    url = sink("hero_intro", b"PNGDATA")

    r = client.get(url)
    assert r.status_code == 200
    assert r.content == b"PNGDATA"
    assert r.headers["content-type"] == "image/png"


def test_generated_이미지_없으면_404(monkeypatch):
    monkeypatch.setattr(app_module, "_checks_client", lambda: FakeBucketClient())
    r = client.get("/generated/" + "0" * 32)
    assert r.status_code == 404


def test_generated_이미지_id_형식_아니면_404():
    r = client.get("/generated/not-a-valid-id")
    assert r.status_code == 404


def test_create_모드_실제로_켜면_module_images에_URL이_채워진다(monkeypatch):
    """냐냐가 발견한 버그의 회귀 테스트: 라우트가 image_generator·image_sink를
    실제로 안 넘겨서 module_images가 항상 빈 배열이었다."""
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "1")
    monkeypatch.setattr(app_module, "get_image_generator", lambda model=None: FakeImageGenerator(b"PNGBYTES"))
    monkeypatch.setattr(app_module, "_checks_client", lambda: FakeBucketClient())
    monkeypatch.setattr(app_module, "_build_judge", lambda: __import__(
        "barum.judge.cosmetic", fromlist=["StubJudge"]
    ).StubJudge())
    monkeypatch.setattr(app_module, "_section_vlm", lambda: SequenceVLM(_PLAN, _MODULE_TEXT))

    r = client.post("/generate", json={"mode": "create", "product_name": "테스트 세럼"})
    assert r.status_code == 200
    body = r.json()
    images = body["image_plan"]["module_images"]
    assert images, "module_images가 비어있으면 배선이 여전히 끊긴 것"
    assert images[0]["status"] == "generated"
    assert images[0]["image_url"].startswith("/generated/")


# ── 제품사진 업로드 → AI 합성 (2026-08-19, 팀장 승인 방식 A) ──────────────────


def test_제품사진_업로드하면_photo_id를_낸다(monkeypatch):
    client_fake = FakeBucketClient()
    monkeypatch.setattr(app_module, "_checks_client", lambda: client_fake)

    r = client.post(
        "/uploads/product-photo",
        files={"photo": ("product.png", b"PNGDATA", "image/png")},
    )
    assert r.status_code == 200
    photo_id = r.json()["photo_id"]
    assert photo_id.endswith(".png")
    assert client_fake.files[f"uploads/{photo_id}"] == b"PNGDATA"

    # 스트리밍 조회 확인
    get_r = client.get(f"/uploads/{photo_id}")
    assert get_r.status_code == 200
    assert get_r.content == b"PNGDATA"
    assert get_r.headers["content-type"] == "image/png"


def test_업로드_사진_조회_잘못된_id는_404(monkeypatch):
    monkeypatch.setattr(app_module, "_checks_client", lambda: FakeBucketClient())
    r = client.get("/uploads/invalid-id")
    assert r.status_code == 404


def test_지원하지_않는_형식은_415(monkeypatch):
    monkeypatch.setattr(app_module, "_checks_client", lambda: FakeBucketClient())
    r = client.post(
        "/uploads/product-photo",
        files={"photo": ("product.gif", b"GIFDATA", "image/gif")},
    )
    assert r.status_code == 415


def test_빈_파일은_422(monkeypatch):
    monkeypatch.setattr(app_module, "_checks_client", lambda: FakeBucketClient())
    r = client.post(
        "/uploads/product-photo",
        files={"photo": ("product.png", b"", "image/png")},
    )
    assert r.status_code == 422


def test_resolve_reference_photos는_product_photo_ids면_유효한_id만_내려받는다():
    client_fake = FakeBucketClient()
    client_fake.files["uploads/" + "a" * 32 + ".png"] = b"PHOTO"
    resolve = app_module._resolve_reference_photos(client_fake)

    req = GenerateRequest(
        mode="create",
        product_photo_ids=["a" * 32 + ".png", "not-a-valid-id", "b" * 32 + ".png"],
    )
    result = resolve(req)
    assert result == [b"PHOTO"]  # 형식 안 맞는 id·조회 실패한 id는 건너뛴다


class FakeChecksClient(FakeBucketClient):
    """FakeBucketClient(Storage) + get_check가 기대하는 최소 테이블 조회 인터페이스.

    test_image_cache.py의 FakeQuery/FakeClient와 같은 idiom(체이닝 no-op +
    execute()가 SimpleNamespace(data=...))을 따른다.
    """

    def __init__(self, rows_by_id: dict[str, dict] | None = None):
        super().__init__()
        self._rows_by_id = rows_by_id or {}
        self._eq_value = None

    def table(self, name):
        return self

    def select(self, *a, **k):
        return self

    def eq(self, field, value):
        self._eq_value = value
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        from types import SimpleNamespace

        row = self._rows_by_id.get(self._eq_value)
        return SimpleNamespace(data=[row] if row else [])


def test_resolve_reference_photos는_result_id로는_참조를_안_만든다():
    """**리포트 원본 이미지는 참조로 쓰지 않는다**(팀장 결정, 2026-08-24).

    한때 썼다(#346, "원본 상품사진이 리포트에 있으니 라벨보존 합성 효과를 improve도
    받자"). 그런데 그 이미지는 제품 컷이 아니라 **상세페이지 통짜 스크린샷**이다
    (실측 480x2161). "참조 속 제품의 형태·라벨을 유지하라"는 지시와 만나면 모델이
    페이지 전체(헤더·가격·표)를 글자까지 재현하고, 참조의 세로로 긴 비율까지
    물려받는다. 원인을 없앤다.
    """
    client_fake = FakeChecksClient({"rid1": {"image_path": "checks/rid1/original.png"}})
    client_fake.files["checks/rid1/original.png"] = b"REPORT_PHOTO"
    resolve = app_module._resolve_reference_photos(client_fake)

    req = GenerateRequest(mode="improve", content="x", result_id="rid1")
    assert resolve(req) == []


def test_resolve_reference_photos는_리포트에_이미지가_없으면_빈_목록():
    client_fake = FakeChecksClient({"rid1": {"image_path": None}})
    resolve = app_module._resolve_reference_photos(client_fake)

    req = GenerateRequest(mode="improve", content="x", result_id="rid1")
    assert resolve(req) == []


def test_generate가_업로드한_사진을_히어로_원본으로_쓰고_참조로는_안_넘긴다(monkeypatch):
    """제품 원본은 히어로 카드에 그대로 쓰고(is_original), 나노바나나 참조로는
    넘기지 않는다(팀장 결정 2026-08-24).

    한때 제품사진을 참조로 넘겨 배경과 합성했는데, 재합성이 라벨을 뭉개고
    (YOURBERRY→YOUARFRAY) 비용도 들었다. 원본을 그대로 쓰면 라벨이 완벽하고
    히어로 배경 생성이 스킵돼 과금이 준다. 배경은 제품 없이 순수 생성한다.
    """
    client_fake = FakeBucketClient()
    photo_id = "c" * 32 + ".png"
    client_fake.files[f"uploads/{photo_id}"] = b"PHOTOBYTES"

    fake_gen = FakeImageGenerator(b"PNGBYTES")
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "1")
    monkeypatch.setattr(app_module, "get_image_generator", lambda model=None: fake_gen)
    monkeypatch.setattr(app_module, "_checks_client", lambda: client_fake)
    monkeypatch.setattr(app_module, "_build_judge", lambda: __import__(
        "barum.judge.cosmetic", fromlist=["StubJudge"]
    ).StubJudge())
    monkeypatch.setattr(app_module, "_section_vlm", lambda: SequenceVLM(_PLAN, _MODULE_TEXT))

    r = client.post(
        "/generate",
        json={"mode": "create", "product_name": "테스트 세럼", "product_photo_ids": [photo_id]},
    )
    assert r.status_code == 200
    body = r.json()
    # 참조로 안 넘김: 생성기가 받은 참조 이미지가 전부 비어 있다(제품 재합성 안 함).
    assert all(imgs == [] for imgs in fake_gen.images_received)
    # 히어로 카드는 제품 원본을 그대로 쓴다(재합성이 아니라 업로드 원본).
    hero = body["cards"][0]
    assert hero["is_original"] is True
    assert hero["image_url"] == f"/uploads/{photo_id}"


def test_improve_모드는_리포트_이미지를_참조로_넘기지_않는다(monkeypatch):
    """**참조 없이 배경만 만든다**(팀장 결정, 2026-08-24).

    한때 result_id로 원본 검사 이미지를 참조로 넘겼는데(#346), 그 이미지는 제품
    컷이 아니라 상세페이지 통짜 스크린샷(480x2161)이라 모델이 페이지 전체를
    글자까지 재현했다. 이미지는 여전히 생성하되 참조는 안 준다.
    """
    client_fake = FakeChecksClient({"rid1": {"image_path": "checks/rid1/original.png"}})
    client_fake.files["checks/rid1/original.png"] = b"REPORT_PHOTO"

    fake_gen = FakeImageGenerator(b"PNGBYTES")
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "1")
    monkeypatch.setattr(app_module, "get_image_generator", lambda model=None: fake_gen)
    monkeypatch.setattr(app_module, "_checks_client", lambda: client_fake)
    monkeypatch.setattr(app_module, "_build_judge", lambda: __import__(
        "barum.judge.cosmetic", fromlist=["StubJudge"]
    ).StubJudge())

    r = client.post(
        "/generate",
        json={
            "mode": "improve",
            "content": "완치됩니다",
            "product_name": "테스트크림",
            "result_id": "rid1",
            "approved_replacements": [{"original": "완치됩니다", "replaced": "사용감이 편안합니다"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    images = body["image_plan"]["module_images"]
    assert images and images[0]["status"] == "generated"
    # 이미지는 만들되 참조는 빈 목록이다(원본 페이지 스크린샷을 안 넘긴다).
    assert fake_gen.images_received == [[]]


# ── 승인 대체표현이 HTTP 경로로 실제로 들어오는지 (2026-08-23) ────────────────
#
# 모델·오케스트레이션은 유닛테스트로 덮여 있지만, **엔드포인트가 이 필드를 실제로
# 받아 넘기는지는 별개 문제다.** 출력만 보거나 우회 실행하면 배관이 안 통해도
# 통과할 수 있어서 실제 HTTP 경로로 확인한다.

def test_승인_대체표현이_엔드포인트로_들어와_치환된다():
    r = client.post(
        "/generate",
        json={
            "mode": "improve",
            "content": "줄기세포 배양 기술로 관리합니다",
            "product_name": "테스트크림",
            "approved_replacements": [
                {"original": "줄기세포 배양 기술", "replaced": "고농축 배합", "finding_index": 0}
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    text = " ".join(s["text"] for s in body["sections"])
    assert "고농축 배합" in text
    assert "줄기세포" not in text
    assert body["replacements"][0]["finding_index"] == 0


def test_엔드포인트로_들어온_위반_문구도_게이트에서_걸린다():
    """HTTP 경계에서도 게이트가 살아 있어야 한다. 여기가 뚫리면 4층이 무의미해진다."""
    r = client.post(
        "/generate",
        json={
            "mode": "improve",
            "content": "줄기세포 배양 기술로 관리합니다",
            "approved_replacements": [
                {"original": "줄기세포 배양 기술", "replaced": "아토피 치료에 좋은 크림"}
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    text = " ".join(s["text"] for s in body["sections"])
    assert "아토피 치료" not in text, "게이트를 우회해 위반 문구가 들어갔다"
    assert "아토피 치료에 좋은 크림" in body["unapplied_replacements"]


def test_응답_스키마에_새_필드가_실제로_실린다():
    """프론트가 읽을 필드가 응답 JSON에 있어야 한다(schema.ts 계약)."""
    r = client.post("/generate", json={"content": "재생 크림입니다", "product_name": "테스트크림"})
    body = r.json()
    assert "unapplied_replacements" in body
    assert "findings" in body["recheck"]


def test_openapi에_승인_대체표현_스키마가_노출된다():
    """프론트 타입 생성·계약 확인의 출처다."""
    spec = client.get("/openapi.json").json()
    props = spec["components"]["schemas"]["GenerateRequest"]["properties"]
    assert "approved_replacements" in props
    assert "ApprovedReplacement" in spec["components"]["schemas"]
