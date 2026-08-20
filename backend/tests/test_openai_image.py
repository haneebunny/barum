"""OpenAI gpt-image 어댑터 유닛테스트. 실제 API는 안 부른다(과금 호출이라 수동 스모크)."""

import base64

import pytest

from barum.vlm import OpenAIImageGenerator, get_image_generator

PNG = b"\x89PNG\r\n\x1a\nFAKE"
B64 = base64.b64encode(PNG).decode()


class FakeImages:
    """generate/edit 호출을 기록하는 가짜 SDK 리소스."""

    def __init__(self, payload):
        self._payload = payload
        self.generate_calls = []
        self.edit_calls = []

    def _respond(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return type("Resp", (), {"data": self._payload})()

    def generate(self, **kw):
        self.generate_calls.append(kw)
        return self._respond()

    def edit(self, **kw):
        self.edit_calls.append(kw)
        return self._respond()


def _generator(payload=None, **kw):
    gen = OpenAIImageGenerator.__new__(OpenAIImageGenerator)
    gen.model = kw.get("model", "gpt-image-1-mini")
    gen.quality = kw.get("quality", "low")
    gen.size = kw.get("size", "1024x1024")
    gen.total_images = 0
    if payload is None:
        payload = [type("D", (), {"b64_json": B64})()]
    gen.client = type("C", (), {"images": FakeImages(payload)})()
    return gen


def test_참고_이미지가_없으면_generate를_쓴다():
    gen = _generator()
    assert gen.generate_image("배경", []) == PNG
    assert len(gen.client.images.generate_calls) == 1
    assert gen.client.images.edit_calls == []


def test_참고_이미지가_있으면_edit로_합성한다():
    # 이 능력 때문에 Cloudflare에서 갈아탔다. generate로 새면 참고 이미지가 버려진다.
    gen = _generator()
    assert gen.generate_image("합성", [b"ref1", b"ref2"]) == PNG
    assert gen.client.images.generate_calls == []
    sent = gen.client.images.edit_calls[0]
    assert len(sent["image"]) == 2
    # SDK가 확장자로 mime을 정하므로 이름이 붙어 있어야 한다.
    assert all(f.name.endswith(".png") for f in sent["image"])


def test_기본값을_그대로_SDK_호출에_보낸다():
    gen = _generator()
    gen.generate_image("x", [])
    sent = gen.client.images.generate_calls[0]
    assert sent["model"] == gen.model
    assert sent["quality"] == "low"
    assert sent["size"] == "1024x1024"
    assert sent["n"] == 1


def test_실제_기본_모델은_gpt_image_1이다(monkeypatch):
    # mini는 images.edit 합성에서 라벨을 못 지켜 상위 모델로 올림(2026-08-20).
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
    monkeypatch.setattr("barum.vlm.load_dotenv", lambda *a, **k: None)
    gen = OpenAIImageGenerator()
    assert gen.model == "gpt-image-1"
    assert gen.quality == "low"


def test_비용을_누적_추정한다():
    gen = _generator()
    gen.generate_image("a", [])
    gen.generate_image("b", [])
    assert gen.total_images == 2
    assert gen.estimated_cost_usd == pytest.approx(0.010)


def test_단가표에_없는_조합은_비용을_0으로_둔다():
    # 모르는 값을 지어내지 않는다.
    gen = _generator(model="gpt-image-2", quality="high")
    gen.generate_image("x", [])
    assert gen.estimated_cost_usd == 0.0


def test_빈_응답은_예상된_실패로_올린다():
    gen = _generator(payload=[])
    with pytest.raises(ValueError, match="이미지를 반환하지 않았다"):
        gen.generate_image("x", [])


def test_b64가_비어도_예상된_실패로_올린다():
    gen = _generator(payload=[type("D", (), {"b64_json": None})()])
    with pytest.raises(ValueError, match="이미지를 반환하지 않았다"):
        gen.generate_image("x", [])


def test_호출_실패는_삼키지_않고_올린다():
    # 과금 호출이라 어댑터가 재시도하지 않는다.
    gen = _generator(payload=RuntimeError("rate limit"))
    with pytest.raises(RuntimeError, match="rate limit"):
        gen.generate_image("x", [])


def test_키가_없으면_바로_알린다(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("barum.vlm.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIImageGenerator()


def test_기본_provider는_openai다(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    assert isinstance(get_image_generator(), OpenAIImageGenerator)
