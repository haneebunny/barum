"""콘텐츠 생성 오케스트레이션(generate.content) 유닛테스트.

LLM은 가짜 주입, 판정은 StubJudge(오프라인 결정론). 실 LLM·재검증은 수동 스모크.

    ./venv/bin/python -m pytest tests/test_generate_content.py -q
"""

from barum.generate.content import (
    build_image_plan,
    generate_content,
    generate_sections,
)
from barum.judge.cosmetic import StubJudge
from barum.models import GenerateRequest, ImageGenRequest


class FakeVLM:
    """캔드 JSON을 돌려주는 가짜 LLM(섹션 생성용)."""

    def __init__(self, result):
        self._result = result

    def generate_json(self, prompt, images):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_generate_sections_from_llm():
    """LLM이 준 서술을 섹션으로 만든다(source=llm)."""
    vlm = FakeVLM({"제품개요": "담백한 데일리 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"})
    secs = generate_sections(GenerateRequest(content="x", product_name="테스트크림"), vlm)
    kinds = {s.kind for s in secs}
    assert {"제품개요", "사용법", "주의사항"} <= kinds
    assert all(s.source == "llm" for s in secs)


def test_generate_sections_falls_back_to_template_on_failure():
    """LLM 실패 시 템플릿 폴백(source=template) — 응답이 죽지 않게."""
    secs = generate_sections(GenerateRequest(content="x"), FakeVLM(ValueError("boom")))
    assert secs  # 비어있지 않음
    assert all(s.source == "template" for s in secs)


def test_build_image_plan_places_result_image_and_filters_gen():
    """result_id 이미지는 배치, 사칭 생성요청은 거부."""
    req = GenerateRequest(
        content="x", result_id="rid1",
        image_generation=ImageGenRequest(requested=True, prompt="의사가 추천하는 사진"),
    )
    plan = build_image_plan(req)
    assert plan.placed and plan.placed[0].image_url == "/reports/rid1/image"
    assert plan.generation.requested is True
    assert plan.generation.allowed is False
    assert plan.generation.reason


def test_generate_content_end_to_end_offline():
    """검사→치환→서술생성→PII→재검증 전체 조립(StubJudge+가짜LLM)."""
    req = GenerateRequest(
        content="재생 크림입니다. 문의 010-1234-5678", product_name="테스트크림"
    )
    vlm = FakeVLM({"제품개요": "담백한 크림", "사용법": "펴 바르세요", "주의사항": "이상 시 중단"})
    resp = generate_content(req, judge=StubJudge(), vlm=vlm)

    assert any(s.kind == "광고문구" for s in resp.sections)  # 개선된 원문
    assert any(s.source == "llm" for s in resp.sections)  # 생성 서술
    # "재생" → 조건표로 치환됨
    assert resp.replacements and resp.replacements[0].original == "재생"
    assert all("재생" not in s.text for s in resp.sections)
    # PII(전화번호) 제거·고지
    assert "전화번호" in resp.pii_removed
    assert all("010-1234-5678" not in s.text for s in resp.sections)
    # 재검증 요약 존재
    assert resp.recheck is not None
    assert resp.disclaimer
