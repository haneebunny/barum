"""이미지 생성 어댑터 유닛테스트. 실제 API는 안 부른다(과금 호출은 수동 스모크).

응답 파싱·실패 처리만 검증한다. interactions API 응답 모양(steps/content)을 흉내낸
가짜 객체를 쓴다(2026-08-20 구 generate_content에서 이관).
"""

import base64
import threading

import pytest

from barum.vlm import GeminiImageGenerator, get_image_generator

PNG = b"PNGDATA"
B64 = base64.b64encode(PNG).decode()


class FakePart:
    """interactions 응답 파트. 이미지는 base64 문자열로 온다."""

    def __init__(self, type, data=None, text=None):
        self.type = type
        self.data = data
        self.text = text


class FakeStep:
    def __init__(self, content, type="model_output"):
        self.type = type
        self.content = content


class FakeInteraction:
    """steps[].content[] 구조를 흉내낸다."""

    def __init__(self, parts, total_tokens=10):
        self.steps = [FakeStep(parts)]
        self.usage = type("U", (), {"total_tokens": total_tokens})()


class FakeInteractions:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _generator(response) -> GeminiImageGenerator:
    """네트워크·인증을 타지 않고 어댑터를 만든다."""
    gen = GeminiImageGenerator.__new__(GeminiImageGenerator)
    gen.model = "gemini-3.1-flash-lite-image"
    gen.total_tokens = 0
    gen._min_interval = 0.0
    gen._last_call = 0.0
    # 병렬 호출 대비 락(2026-08-24) - __init__을 안 타는 테스트 생성자라 직접 채운다.
    gen._lock = threading.Lock()
    gen.client = type("Client", (), {"interactions": FakeInteractions(response)})()
    return gen


def test_이미지_바이트를_꺼낸다():
    gen = _generator(FakeInteraction([FakePart("image", data=B64)]))
    assert gen.generate_image("배경 이미지", []) == PNG


def test_텍스트_파트는_건너뛰고_이미지_파트를_찾는다():
    parts = [FakePart("text", text="설명"), FakePart("image", data=B64)]
    assert _generator(FakeInteraction(parts)).generate_image("x", []) == PNG


def test_토큰을_누적한다():
    gen = _generator(FakeInteraction([FakePart("image", data=B64)], total_tokens=42))
    gen.generate_image("x", [])
    assert gen.total_tokens == 42


def test_이미지가_없으면_예상된_실패로_올린다():
    # 안전필터 차단·빈 응답. 호출자가 스킵 처리할 수 있게 ValueError로 낸다.
    gen = _generator(FakeInteraction([FakePart("text", text="차단됨")]))
    with pytest.raises(ValueError, match="이미지를 반환하지 않았다"):
        gen.generate_image("x", [])


def test_스텝이_비어도_터지지_않고_예상된_실패가_된다():
    gen = _generator(FakeInteraction([]))
    with pytest.raises(ValueError):
        gen.generate_image("x", [])


def test_모델_출력이_아닌_스텝은_무시한다():
    # 도구 호출 등 다른 스텝이 섞여 와도 이미지 파트만 봐야 한다.
    it = FakeInteraction([FakePart("image", data=B64)])
    it.steps.insert(0, FakeStep([FakePart("image", data="쓰레기")], type="tool_call"))
    assert _generator(it).generate_image("x", []) == PNG


def test_호출_실패는_삼키지_않고_그대로_올린다():
    # 과금 호출이라 어댑터가 재시도하지 않는다. 스킵 여부는 호출자가 정한다.
    gen = _generator(RuntimeError("network down"))
    with pytest.raises(RuntimeError, match="network down"):
        gen.generate_image("x", [])


def test_이미지_모달리티로_요청한다():
    gen = _generator(FakeInteraction([FakePart("image", data=B64)]))
    gen.generate_image("배경", [b"ref"])
    sent = gen.client.interactions.calls[0]
    # interactions API는 모델명에 models/ 접두사를 요구한다.
    assert sent["model"] == "models/gemini-3.1-flash-lite-image"
    assert sent["response_modalities"] == ["image", "text"]
    # 프롬프트가 먼저, 참고 이미지가 뒤에 붙는다.
    assert [p["type"] for p in sent["input"]] == ["text", "image"]
    assert base64.b64decode(sent["input"][1]["data"]) == b"ref"


def test_모르는_provider는_거부한다():
    # 지원 목록에 없는 이름은 조용히 기본값으로 새지 않고 거부해야 한다.
    with pytest.raises(ValueError, match="지원하지 않는 provider"):
        get_image_generator("stability")


# ── 콘텐츠 필터 거부 재시도 (2026-08-20, 거부율 3.1% 실측 후 도입) ──


def test_콘텐츠_필터_거부는_1회_재시도한다():
    """거부는 과금이 없고(토큰 실측) 비결정적이라 재시도가 유효하다."""
    refusal = RuntimeError("400 Image generation blocked due to copyright/recitation.")
    gen = _generator(refusal)
    # 첫 호출은 거부, 두 번째는 성공하도록 응답을 갈아끼운다.
    calls = {"n": 0}

    def create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise refusal
        return FakeInteraction([FakePart("image", data=B64)])

    gen.client.interactions.create = create
    assert gen.generate_image("x", []) == PNG
    assert calls["n"] == 2


def test_재시도해도_거부되면_그대로_올린다():
    """무한 재시도하지 않는다. 1회만."""
    refusal = RuntimeError("Image generation blocked due to copyright/recitation")
    gen = _generator(refusal)
    calls = {"n": 0}

    def create(**kwargs):
        calls["n"] += 1
        raise refusal

    gen.client.interactions.create = create
    with pytest.raises(RuntimeError, match="copyright"):
        gen.generate_image("x", [])
    assert calls["n"] == 2


def test_거부가_아닌_실패는_재시도하지_않는다():
    """인증 실패·네트워크 오류를 재시도하면 같은 실패를 반복하며 시간만 쓴다."""
    gen = _generator(None)
    calls = {"n": 0}

    def create(**kwargs):
        calls["n"] += 1
        raise RuntimeError("401 UNAUTHENTICATED")

    gen.client.interactions.create = create
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        gen.generate_image("x", [])
    assert calls["n"] == 1, "과금 호출 재시도 금지 원칙은 이 경우엔 그대로 적용된다"


def test_기본_provider가_gemini다():
    """라벨 보존력 때문에 전환(2026-08-20 팀장 승인)."""
    import os

    from barum.vlm import GeminiImageGenerator as G

    prev = os.environ.pop("IMAGE_PROVIDER", None)
    try:
        os.environ["GEMINI_API_KEY"] = "k"
        assert isinstance(get_image_generator(), G)
    finally:
        if prev is not None:
            os.environ["IMAGE_PROVIDER"] = prev
