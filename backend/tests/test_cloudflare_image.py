"""Cloudflare Workers AI 이미지 어댑터 유닛테스트. 실제 API는 안 부른다.

httpx.post를 가짜로 바꿔 요청 형태·응답 파싱·실패 처리만 검증한다.
"""

import base64

import pytest

from barum.vlm import CloudflareImageGenerator, get_image_generator

PNG = b"\x89PNG\r\n\x1a\nFAKE"
B64 = base64.b64encode(PNG).decode()


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _generator(**kw) -> CloudflareImageGenerator:
    return CloudflareImageGenerator(api_token="tok", account_id="acct", **kw)


def _patch_post(monkeypatch, response):
    """httpx.post를 가로채고 보낸 인자를 기록한다."""
    sent = {}

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent.update(kwargs)
        if isinstance(response, Exception):
            raise response
        return response

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    return sent


def test_base64_응답을_바이트로_디코딩한다(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({"success": True, "result": {"image": B64}}))
    assert _generator().generate_image("배경", []) == PNG


def test_요청_형태가_문서와_맞는다(monkeypatch):
    sent = _patch_post(monkeypatch, FakeResponse({"success": True, "result": {"image": B64}}))
    _generator(steps=4).generate_image("고요한 배경", [])

    assert sent["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/acct/ai/run/"
        "@cf/black-forest-labs/flux-1-schnell"
    )
    assert sent["headers"]["Authorization"] == "Bearer tok"
    assert sent["json"] == {"prompt": "고요한 배경", "steps": 4}


def test_steps는_문서상_최대_8로_자른다(monkeypatch):
    sent = _patch_post(monkeypatch, FakeResponse({"success": True, "result": {"image": B64}}))
    _generator(steps=99).generate_image("x", [])
    assert sent["json"]["steps"] == 8


def test_참고_이미지를_주면_조용히_버리지_않고_알린다():
    # FLUX.1 schnell은 text-to-image 전용이다. 조용히 무시하면 엉뚱한 결과가 나간다.
    with pytest.raises(ValueError, match="참고 이미지를 못 받는다"):
        _generator().generate_image("x", [b"reference"])


def test_success_false는_예상된_실패로_올린다(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({"success": False, "errors": [{"message": "quota"}]}))
    with pytest.raises(ValueError, match="Cloudflare 이미지 생성 실패"):
        _generator().generate_image("x", [])


def test_이미지가_비면_예상된_실패로_올린다(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({"success": True, "result": {}}))
    with pytest.raises(ValueError, match="이미지를 반환하지 않았다"):
        _generator().generate_image("x", [])


def test_HTTP_에러는_삼키지_않고_올린다(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({}, status=429))
    with pytest.raises(RuntimeError, match="HTTP 429"):
        _generator().generate_image("x", [])


def test_생성_장수를_센다(monkeypatch):
    _patch_post(monkeypatch, FakeResponse({"success": True, "result": {"image": B64}}))
    gen = _generator()
    gen.generate_image("a", [])
    gen.generate_image("b", [])
    assert gen.total_images == 2


def test_토큰이나_계정ID가_없으면_바로_알린다(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.setattr("barum.vlm.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="CLOUDFLARE_API_TOKEN"):
        CloudflareImageGenerator()


def test_기본_provider는_cloudflare다(monkeypatch):
    # Gemini 이미지 모델은 무료 할당량이 0이라 기본값이 될 수 없다.
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    assert isinstance(get_image_generator(), CloudflareImageGenerator)
