"""텍스트 임베딩 (OpenAI text-embedding-3-small).

사례·문장을 벡터로 만들어 pgvector 유사검색에 쓴다. 판정 provider가 이미
OpenAI라 임베딩도 OpenAI로 통일한다(provider 하나 더 안 늘림, PM2 확정).
-3-small은 1536차원, 비용 ~$0.02/1M토큰이라 사례 수십 건·문장당 1회면 사실상 0.

client를 주입할 수 있어 유닛테스트는 가짜로 돌린다(네트워크 없음).
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536  # -3-small 차원(스키마 vector(1536)와 일치)


@lru_cache(maxsize=1)
def _default_client():
    """OpenAI 클라이언트(1회 생성). 키는 env에서 읽는다(하드코딩 금지)."""
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 없다. backend/.env를 확인할 것.")
    from openai import OpenAI
    from langsmith import wrappers

    raw_client = OpenAI(api_key=key)
    return wrappers.wrap_openai(raw_client)


def embed_texts(texts: list[str], client=None, model: str = EMBED_MODEL) -> list[list[float]]:
    """텍스트 리스트를 임베딩 벡터 리스트로. 입력 1개당 벡터 1개.

    client 미지정이면 기본 OpenAI 클라이언트를 만든다(과금 호출). 배치로 한 번에
    보낸다(호출 수 절감). 응답 순서는 입력 순서와 같다(OpenAI 계약).
    """
    client = client or _default_client()
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]
