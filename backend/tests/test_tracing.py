"""LangSmith 수동 계측 (외부 호출 없음).

`wrappers.wrap_gemini`는 `client.models.generate_content`만 patch하는데 우리는
2026-08-20에 `client.interactions.create`로 이관했다. 그래서 래핑은 통과하지만
트레이스가 안 생긴다. 여기서 수동 계측이 살아 있는지 지킨다.
"""

from barum.vlm import GeminiImageGenerator, GeminiVLM, _trace_image_output, _trace_inputs


class _Model:
    model = "gemini-3.1-flash-lite-image"


def test_이미지_바이트는_트레이스에_안_싣는다():
    """원본을 실으면 트레이스가 수 MB가 되고 조회가 느려진다."""
    out = _trace_inputs({"self": _Model(), "prompt": "배경 생성", "images": [b"x" * 600_000]})
    assert out["prompt"] == "배경 생성"
    assert out["images"] == ["<image 600,000 bytes>"]
    assert not any(isinstance(v, (bytes, bytearray)) for v in out.values())


def test_프롬프트는_그대로_싣는다():
    """팀장이 프롬프트를 보려는 게 이 계측의 목적이다. 여기를 가리면 안 된다."""
    prompt = "세로로 아주 긴 화장품 상세페이지 배경. 글자 없음."
    assert _trace_inputs({"prompt": prompt, "images": []})["prompt"] == prompt


def test_생성_이미지도_바이트_대신_크기를_싣는다():
    assert _trace_image_output(b"y" * 527_757) == {"image_bytes": 527_757}
    assert _trace_image_output(None) == {"image_bytes": None}


def test_self는_트레이스에_안_들어간다():
    assert "self" not in _trace_inputs({"self": _Model(), "prompt": "x"})


def test_호출_메서드가_계측돼_있다():
    """데코레이터가 떨어지면 트레이스가 조용히 사라진다. 실행해도 안 보인다."""
    assert hasattr(GeminiVLM.generate_json, "__wrapped__"), "generate_json 계측이 빠졌다"
    assert hasattr(
        GeminiImageGenerator._generate_once, "__wrapped__"
    ), "_generate_once 계측이 빠졌다"


def test_모델명_태깅은_트레이스가_없어도_안_터진다():
    """관측 실패가 판정을 막으면 안 된다."""
    from barum.vlm import _tag_model

    _tag_model("gemini-3.1-flash-lite-image")  # 예외 없이 통과해야 한다
