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
        # 캐시 적중 계측용. 판정은 근거 문서(2만자)를 배치마다 다시 실어 보내는데,
        # 그 앞부분이 매번 같아 자동 프롬프트 캐싱 대상이다. 실제로 먹고 있는지
        # 재려면 cached_tokens를 봐야 한다. `cache_report()`로 읽는다.
        self.prompt_tokens = 0
        self.cached_tokens = 0

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
            self.prompt_tokens += resp.usage.prompt_tokens or 0
            # 판정 프롬프트는 근거 문서(2만자)가 앞에 붙고 배치마다 그 앞부분이
            # 같다. 자동 프롬프트 캐싱이 실제로 먹는지 확인할 수단이 이것뿐이라
            # 따로 센다. 필드가 없는 모델·구버전 SDK도 있어 방어적으로 읽는다.
            details = getattr(resp.usage, "prompt_tokens_details", None)
            self.cached_tokens += getattr(details, "cached_tokens", None) or 0
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("OpenAI가 빈 응답을 반환했다")
        return _extract_json(text)

    def cache_report(self) -> dict[str, int | float]:
        """프롬프트 캐시 적중 현황. 계측용이라 판정 동작에는 영향이 없다.

        `hit_rate`는 입력 토큰 중 캐시로 처리된 비율이다. 이 값을 보고서야
        "이미 잘 되고 있다"인지 "프리픽스가 깨져 매번 새로 물고 있다"인지
        구분할 수 있다. 추정하지 말고 이 숫자를 쓸 것.
        """
        hit = self.cached_tokens / self.prompt_tokens if self.prompt_tokens else 0.0
        return {
            "prompt_tokens": self.prompt_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.total_tokens,
            "hit_rate": round(hit, 4),
        }


class ImageGenerator(Protocol):
    """이미지를 만들어내는 어댑터가 지켜야 할 최소 인터페이스.

    `VLM`(generate_json)과 따로 둔다. VLM은 JSON 텍스트를 받게 만들어져 있어
    (`response_mime_type="application/json"`) 이미지 바이트를 못 받기 때문이다.
    """

    def generate_image(self, prompt: str, images: list[bytes]) -> bytes:
        """프롬프트(+참고 이미지)로 이미지 1장을 만들어 PNG 바이트로 낸다."""
        ...


class GeminiImageGenerator(GeminiVLM):
    """Gemini 이미지 생성 어댑터.

    인증·클라이언트 초기화·throttle은 `GeminiVLM`에서 그대로 물려받고, 생성 경로만
    새로 만든다(응답 모달리티가 JSON이 아니라 IMAGE라 기존 메서드를 못 쓴다).

    텍스트는 이미지에 굽지 않는다. 프론트가 이미지 위에 얹는 구조라, 배경·연출만
    만들면 된다(하니·PM 확정, 2026-08-18).
    """

    def __init__(self, model: str | None = None, **kwargs):
        super().__init__(
            model=model or os.environ.get("IMAGE_MODEL_NAME", "gemini-2.5-flash-image"),
            **kwargs,
        )

    def generate_image(self, prompt: str, images: list[bytes]) -> bytes:
        """프롬프트로 이미지 1장을 만든다. 참고 이미지를 주면 그걸 편집·합성한다.

        호출 실패는 삼키지 않고 그대로 올려보낸다. 스킵 여부는 호출자가 정한다
        (과금 호출이라 재시도하지 않는다).
        """
        from google.genai import types

        self._throttle()

        parts = [types.Part.from_bytes(data=b, mime_type="image/png") for b in images]
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[*parts, prompt],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        if resp.usage_metadata:
            self.total_tokens += resp.usage_metadata.total_token_count or 0

        for part in _response_parts(resp):
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                return inline.data
        # 안전필터 차단·빈 응답은 '예상된 실패'로 본다. 호출자가 스킵 처리.
        raise ValueError("이미지 모델이 이미지를 반환하지 않았다")


def _response_parts(resp) -> list:
    """응답에서 파트 목록을 꺼낸다. 후보·콘텐츠가 비어도 터지지 않게 한다."""
    candidates = getattr(resp, "candidates", None) or []
    if not candidates:
        return []
    content = getattr(candidates[0], "content", None)
    return list(getattr(content, "parts", None) or [])


class CloudflareImageGenerator:
    """Cloudflare Workers AI 이미지 생성 어댑터 (FLUX.1 schnell).

    무료 티어가 매일 갱신돼서 골랐다(Gemini 이미지 모델은 무료 할당량이 0이라 결제
    없이는 못 쓴다, 2026-08-18 4개 모델 전부 limit:0 확인).

    **한계: 이 모델은 text-to-image 전용이라 참고 이미지를 못 받는다.** 요청 스키마에
    prompt와 steps밖에 없다. 지금 용도(모듈별 배경 생성)는 참고 이미지를 안 쓰므로
    문제없지만, 나중에 업로드 사진 편집·합성이 필요해지면 다른 모델로 갈아야 한다.
    그래서 이미지를 넘기면 조용히 버리지 않고 예외로 알린다.

    인증에 토큰과 계정ID 둘 다 필요하다(Gemini는 키 하나였다).
    """

    MODEL = "@cf/black-forest-labs/flux-1-schnell"
    _ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    def __init__(
        self,
        api_token: str | None = None,
        account_id: str | None = None,
        model: str | None = None,
        steps: int = 4,
        timeout: float = 60.0,
    ):
        load_dotenv()
        self.model = model or os.environ.get("CLOUDFLARE_IMAGE_MODEL", self.MODEL)
        self.api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
        self.account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        if not self.api_token or not self.account_id:
            raise RuntimeError(
                "CLOUDFLARE_API_TOKEN과 CLOUDFLARE_ACCOUNT_ID가 둘 다 필요하다. .env를 확인할 것."
            )
        # steps는 문서상 최대 8. 넘기면 400이 나므로 여기서 자른다.
        self.steps = max(1, min(int(steps), 8))
        self.timeout = timeout
        self.total_images = 0

    def generate_image(self, prompt: str, images: list[bytes]) -> bytes:
        """프롬프트로 이미지 1장을 만들어 PNG 바이트로 낸다.

        호출 실패는 삼키지 않고 그대로 올려보낸다. 스킵 여부는 호출자가 정한다.
        """
        import base64

        import httpx

        if images:
            raise ValueError(
                f"{self.model}은 참고 이미지를 못 받는다(text-to-image 전용). "
                "이미지 편집·합성이 필요하면 다른 모델을 써야 한다."
            )

        url = self._ENDPOINT.format(account_id=self.account_id, model=self.model)
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.api_token}"},
            json={"prompt": prompt, "steps": self.steps},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success", True):
            # 예상된 실패(할당량 초과·프롬프트 거부 등). 호출자가 스킵 처리.
            raise ValueError(f"Cloudflare 이미지 생성 실패: {body.get('errors')}")

        b64 = (body.get("result") or {}).get("image")
        if not b64:
            raise ValueError("Cloudflare가 이미지를 반환하지 않았다")
        self.total_images += 1
        return base64.b64decode(b64)


class OpenAIImageGenerator:
    """OpenAI gpt-image 어댑터.

    Cloudflare(FLUX.1 schnell)에서 갈아탄 이유는 **원본 제품 사진 편집·합성**이다.
    FLUX schnell은 text-to-image 전용이라 참고 이미지를 못 받는데, gpt-image는
    images.edit로 참고 이미지를 받아 합성한다(하니 재결정, 2026-08-18).

    참고 이미지가 없으면 images.generate, 있으면 images.edit로 자동 분기한다.

    **비용이 실제로 청구된다.** Gemini는 결제가 꺼져 있어 탐침이 무료였지만 이쪽은
    아니다. 시연용 최소 사용이 전제다(하니·PM 확정).

    기본 모델은 `gpt-image-1`(low, 1024x1024, 장당 $0.011). mini(장당 $0.005)에서
    올라온 이유는 가격이 아니라 품질: mini는 `images.edit` 합성에서 참조 이미지의
    라벨·형태를 못 지켜서(barum-photo-composite-fidelity-issue) 상위 모델로
    재검증하기로 함(2026-08-20, 팀장·PM 확정).
    """

    # 문서 기준 1024x1024 장당 단가(2026-08-18 확인). 비용 로그·상한 계산에 쓴다.
    PRICE_PER_IMAGE = {
        ("gpt-image-1-mini", "low"): 0.005,
        ("gpt-image-1-mini", "medium"): 0.011,
        ("gpt-image-1-mini", "high"): 0.036,
        ("gpt-image-2", "low"): 0.006,
        ("gpt-image-1", "low"): 0.011,
    }

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        quality: str | None = None,
        size: str | None = None,
    ):
        from openai import OpenAI

        load_dotenv()
        self.model = model or os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        self.quality = quality or os.environ.get("OPENAI_IMAGE_QUALITY", "low")
        self.size = size or os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY가 없다. .env를 확인할 것.")
        self.client = OpenAI(api_key=key)
        self.total_images = 0

    @property
    def estimated_cost_usd(self) -> float:
        """지금까지 생성한 장수의 추정 비용(달러). 단가표에 없으면 0을 낸다."""
        unit = self.PRICE_PER_IMAGE.get((self.model, self.quality), 0.0)
        return self.total_images * unit

    def generate_image(self, prompt: str, images: list[bytes]) -> bytes:
        """이미지 1장을 만들어 PNG 바이트로 낸다.

        참고 이미지를 주면 그걸 편집·합성한다(images.edit).
        과금 호출이라 재시도하지 않는다. 실패는 그대로 올리고 호출자가 스킵한다.
        """
        import base64
        import io

        common = dict(model=self.model, prompt=prompt, size=self.size, quality=self.quality, n=1)
        if images:
            files = []
            for i, blob in enumerate(images):
                buf = io.BytesIO(blob)
                # SDK가 확장자로 mime을 정하므로 이름을 붙여줘야 한다.
                buf.name = f"reference_{i}.png"
                files.append(buf)
            resp = self.client.images.edit(image=files, **common)
        else:
            resp = self.client.images.generate(**common)

        data = getattr(resp, "data", None) or []
        b64 = getattr(data[0], "b64_json", None) if data else None
        if not b64:
            # 안전필터 차단·빈 응답은 '예상된 실패'로 본다. 호출자가 스킵 처리.
            raise ValueError("OpenAI가 이미지를 반환하지 않았다")
        self.total_images += 1
        return base64.b64decode(b64)


def get_vlm(provider: str = "gemini", **kwargs) -> VLM:
    """provider 이름으로 어댑터를 만든다."""
    if provider == "gemini":
        return GeminiVLM(**kwargs)
    if provider == "openai":
        return OpenAIVLM(**kwargs)
    raise ValueError(f"모르는 provider: {provider}")


def get_image_generator(provider: str | None = None, **kwargs) -> ImageGenerator:
    """provider 이름으로 이미지 생성 어댑터를 만든다.

    기본값은 openai다. 원본 제품 사진 편집·합성이 필요해서 골랐다(FLUX schnell은
    text-to-image 전용이라 그게 안 되고, Gemini 이미지 모델은 무료 할당량이 0이다).
    Cloudflare·Gemini 어댑터는 나중에 다시 쓸 수 있게 남겨둔다.
    provider를 안 주면 IMAGE_PROVIDER 환경변수를 본다.
    """
    provider = provider or os.environ.get("IMAGE_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIImageGenerator(**kwargs)
    if provider == "cloudflare":
        return CloudflareImageGenerator(**kwargs)
    if provider == "gemini":
        return GeminiImageGenerator(**kwargs)
    raise ValueError(f"이미지 생성을 지원하지 않는 provider: {provider}")
