"""POST /generate 엔드포인트 유닛테스트 (오프라인: StubJudge + 가짜 섹션 LLM).

    ./venv/bin/python -m pytest tests/test_generate_api.py -q
"""

import os

os.environ["JUDGE_KIND"] = "stub"
os.environ["CHECKS_PERSIST"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from barum.api import app as app_module  # noqa: E402

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
    assert any(s["source"] == "llm" for s in body["sections"])
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
    monkeypatch.setattr(app_module, "get_image_generator", lambda: FakeImageGenerator())
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
    monkeypatch.setattr(app_module, "get_image_generator", lambda: FakeImageGenerator(b"PNGBYTES"))
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


def test_resolve_product_photos가_유효한_id만_내려받는다():
    client_fake = FakeBucketClient()
    client_fake.files["uploads/" + "a" * 32 + ".png"] = b"PHOTO"
    resolve = app_module._resolve_product_photos(client_fake)

    result = resolve(["a" * 32 + ".png", "not-a-valid-id", "b" * 32 + ".png"])
    assert result == [b"PHOTO"]  # 형식 안 맞는 id·조회 실패한 id는 건너뛴다


def test_generate가_업로드한_사진을_참조이미지로_생성기에_넘긴다(monkeypatch):
    """업로드 → /generate에서 photo_id 참조까지 end-to-end 배선 확인."""
    client_fake = FakeBucketClient()
    photo_id = "c" * 32 + ".png"
    client_fake.files[f"uploads/{photo_id}"] = b"PHOTOBYTES"

    fake_gen = FakeImageGenerator(b"PNGBYTES")
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "1")
    monkeypatch.setattr(app_module, "get_image_generator", lambda: fake_gen)
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
    assert body["image_plan"]["module_images"][0]["status"] == "generated"
    assert fake_gen.images_received == [[b"PHOTOBYTES"]]
