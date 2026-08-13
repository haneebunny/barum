"""VLM provider 어댑터.

모델 호출을 이 파일 하나로 격리한다(요구사항 FR-20). provider를 바꾸려면
`VLM` 프로토콜을 만족하는 클래스를 추가하고 `get_vlm()`에 등록하면 된다.
"""

import json
import os
import time
from typing import Protocol

from dotenv import load_dotenv


class VLM(Protocol):
    """비전 모델 어댑터가 지켜야 할 최소 인터페이스."""

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        """프롬프트 + 이미지들을 넣고 JSON 응답(dict)을 받는다."""
        ...


class GeminiVLM:
    """Google Gemini 어댑터.

    입력: 프롬프트 문자열 + PNG 바이트 리스트 / 출력: 파싱된 dict.
    호출 실패는 여기서 삼키지 않고 그대로 올려보낸다 — 스킵 여부는 호출자가 정한다.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        rpm: int = 15,
    ):
        from google import genai
        from langsmith import wrappers

        load_dotenv()
        self.model = model or os.environ.get("MODEL_NAME", "gemini-3.5-flash-lite")
        key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY가 없다. .env를 확인할 것.")
        raw_client = genai.Client(api_key=key)
        self.client = wrappers.wrap_gemini(raw_client)
        self.total_tokens = 0
        # 무료 티어는 분당 요청 수가 막혀 있다(기본 15 RPM). 초과하면 429로
        # 통째로 스킵되므로, 재시도 대신 호출 간격을 벌려 애초에 안 걸리게 한다.
        self._min_interval = 60.0 / rpm if rpm else 0.0
        self._last_call = 0.0

    def _throttle(self) -> None:
        """직전 호출로부터 최소 간격이 지나도록 기다린다."""
        if not self._min_interval:
            return
        wait = self._last_call + self._min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        from google.genai import types

        self._throttle()

        parts = [types.Part.from_bytes(data=b, mime_type="image/png") for b in images]
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[*parts, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if resp.usage_metadata:
            self.total_tokens += resp.usage_metadata.total_token_count or 0

        text = (resp.text or "").strip()
        if not text:
            # 안전필터 차단·빈 응답은 '예상된 실패'로 본다. 호출자가 스킵 처리.
            raise ValueError("VLM이 빈 응답을 반환했다")
        # 스키마 위반(JSON 아님)은 예상 못 한 실패 — 삼키지 않고 터뜨린다.
        return json.loads(text)


def _extract_json(text: str) -> dict:
    """응답에서 JSON을 뽑는다. 코드펜스·군더더기 텍스트가 붙어도 관대하게 파싱."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        i, j = text.find("{"), text.rfind("}")
        if i != -1 and j != -1:
            return json.loads(text[i:j + 1])
        raise


class OpenAIVLM:
    """OpenAI 어댑터. Gemini와 같은 generate_json 인터페이스.

    provider-agnostic 비교용. 텍스트 판정이 주 용도, 이미지는 base64로 첨부.
    모델별 파라미터 차이(추론 모델의 temperature 거부 등)를 피하려고
    temperature·max_tokens는 지정하지 않는다. response_format을 거부하는
    모델은 자동으로 없이 재시도한다.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI
        from langsmith import wrappers

        load_dotenv()
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5-mini")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY가 없다. .env를 확인할 것.")
        raw_client = OpenAI(api_key=key)
        self.client = wrappers.wrap_openai(raw_client)
        self.total_tokens = 0

    def generate_json(self, prompt: str, images: list[bytes]) -> dict:
        import base64

        if images:
            content: list = [{"type": "text", "text": prompt}]
            for b in images:
                uri = "data:image/png;base64," + base64.b64encode(b).decode()
                content.append({"type": "image_url", "image_url": {"url": uri}})
            msg = [{"role": "user", "content": content}]
        else:
            msg = [{"role": "user", "content": prompt}]

        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msg,
                response_format={"type": "json_object"})
        except Exception:
            # 일부 모델은 response_format을 거부한다 — 없이 재시도.
            resp = self.client.chat.completions.create(model=self.model, messages=msg)

        if resp.usage:
            self.total_tokens += resp.usage.total_tokens or 0
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("OpenAI가 빈 응답을 반환했다")
        return _extract_json(text)


def get_vlm(provider: str = "gemini", **kwargs) -> VLM:
    """provider 이름으로 어댑터를 만든다."""
    if provider == "gemini":
        return GeminiVLM(**kwargs)
    if provider == "openai":
        return OpenAIVLM(**kwargs)
    raise ValueError(f"모르는 provider: {provider}")
