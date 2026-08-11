"""임베딩 래퍼(storage.embeddings) 유닛테스트 (OpenAI 가짜 주입, 네트워크 없음).

실제 임베딩 호출은 수동 스모크. 여기선 응답 파싱·형태만 본다.

    ./venv/bin/python -m pytest tests/test_embeddings.py -q
"""

from barum.storage.embeddings import embed_texts


class _Datum:
    def __init__(self, embedding):
        self.embedding = embedding


class _Resp:
    def __init__(self, data):
        self.data = data


class FakeEmbeddingsAPI:
    """OpenAI client.embeddings.create 흉내. 입력 개수만큼 캔드 벡터를 돌려준다."""

    def __init__(self):
        self.last_model = None
        self.last_input = None

    def create(self, model, input):
        self.last_model = model
        self.last_input = input
        return _Resp([_Datum([0.1, 0.2, 0.3]) for _ in input])


class FakeOpenAI:
    def __init__(self):
        self.embeddings = FakeEmbeddingsAPI()


def test_embed_texts_returns_one_vector_per_input():
    client = FakeOpenAI()
    vecs = embed_texts(["첫 문구", "둘째 문구"], client=client)
    assert vecs == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert client.embeddings.last_input == ["첫 문구", "둘째 문구"]


def test_embed_texts_uses_small_model_by_default():
    client = FakeOpenAI()
    embed_texts(["x"], client=client)
    assert client.embeddings.last_model == "text-embedding-3-small"
