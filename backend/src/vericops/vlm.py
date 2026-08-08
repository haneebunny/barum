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

        load_dotenv()
        self.model = model or os.environ.get("MODEL_NAME", "gemini-3.5-flash-lite")
        key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY가 없다. .env를 확인할 것.")
        self.client = genai.Client(api_key=key)
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


def get_vlm(provider: str = "gemini", **kwargs) -> VLM:
    """provider 이름으로 어댑터를 만든다."""
    if provider == "gemini":
        return GeminiVLM(**kwargs)
    raise ValueError(f"모르는 provider: {provider}")
