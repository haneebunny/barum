"""이미지 생성 어댑터 유닛테스트. 실제 API는 안 부른다(과금 호출은 수동 스모크).

응답 파싱·실패 처리만 검증한다. Gemini SDK 응답 모양을 흉내낸 가짜 객체를 쓴다.
"""

import pytest

from barum.vlm import GeminiImageGenerator, get_image_generator


class FakeBlob:
    def __init__(self, data):
        self.data = data


class FakePart:
    def __init__(self, inline_data=None, text=None):
        self.inline_data = inline_data
        self.text = text


class FakeResponse:
    """candidates[0].content.parts 구조를 흉내낸다."""

    def __init__(self, parts, total_tokens=10):
        self.candidates = [type("C", (), {"content": type("Ct", (), {"parts": parts})()})()]
        self.usage_metadata = type("U", (), {"total_token_count": total_tokens})()


class FakeModels:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _generator(response) -> GeminiImageGenerator:
    """네트워크·인증을 타지 않고 어댑터를 만든다."""
    gen = GeminiImageGenerator.__new__(GeminiImageGenerator)
    gen.model = "gemini-2.5-flash-image"
    gen.total_tokens = 0
    gen._min_interval = 0.0
    gen._last_call = 0.0
    gen.client = type("Client", (), {"models": FakeModels(response)})()
    return gen


def test_이미지_바이트를_꺼낸다():
    gen = _generator(FakeResponse([FakePart(inline_data=FakeBlob(b"PNGDATA"))]))
    assert gen.generate_image("배경 이미지", []) == b"PNGDATA"


def test_텍스트_파트는_건너뛰고_이미지_파트를_찾는다():
    parts = [FakePart(text="설명"), FakePart(inline_data=FakeBlob(b"PNGDATA"))]
    assert _generator(FakeResponse(parts)).generate_image("x", []) == b"PNGDATA"


def test_토큰을_누적한다():
    gen = _generator(FakeResponse([FakePart(inline_data=FakeBlob(b"X"))], total_tokens=42))
    gen.generate_image("x", [])
    assert gen.total_tokens == 42


def test_이미지가_없으면_예상된_실패로_올린다():
    # 안전필터 차단·빈 응답. 호출자가 스킵 처리할 수 있게 ValueError로 낸다.
    gen = _generator(FakeResponse([FakePart(text="차단됨")]))
    with pytest.raises(ValueError, match="이미지를 반환하지 않았다"):
        gen.generate_image("x", [])


def test_후보가_비어도_터지지_않고_예상된_실패가_된다():
    gen = _generator(FakeResponse([]))
    with pytest.raises(ValueError):
        gen.generate_image("x", [])


def test_호출_실패는_삼키지_않고_그대로_올린다():
    # 과금 호출이라 어댑터가 재시도하지 않는다. 스킵 여부는 호출자가 정한다.
    gen = _generator(RuntimeError("network down"))
    with pytest.raises(RuntimeError, match="network down"):
        gen.generate_image("x", [])


def test_이미지_모달리티로_요청한다():
    gen = _generator(FakeResponse([FakePart(inline_data=FakeBlob(b"X"))]))
    gen.generate_image("배경", [b"ref"])
    sent = gen.client.models.calls[0]
    assert sent["model"] == "gemini-2.5-flash-image"
    assert sent["config"].response_modalities == ["IMAGE"]
    # 참고 이미지가 프롬프트보다 앞에 붙는다(기존 generate_json과 같은 순서).
    assert len(sent["contents"]) == 2


def test_모르는_provider는_거부한다():
    # 지원 목록에 없는 이름은 조용히 기본값으로 새지 않고 거부해야 한다.
    with pytest.raises(ValueError, match="지원하지 않는 provider"):
        get_image_generator("stability")
