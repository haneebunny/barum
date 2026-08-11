"""사례 임베딩 적재·유사검색 어댑터 (Supabase reference_cases).

적재(load)는 배포 시 1회 스크립트(scripts/load_cases.py)가 부른다. 검색(search)은
판정 때 문장마다 부른다. 실제 쿼리는 Supabase 클라이언트가 하고, 여기선 그 위의
얇은 래퍼다(테스트는 가짜 클라이언트 주입).
"""

_TABLE = "reference_cases"
_MATCH_RPC = "match_reference_cases"


def build_case_rows(cases: list[dict], embeddings: list[list[float]]) -> list[dict]:
    """사례 dict + 임베딩을 reference_cases insert 로우로 합친다.

    개수가 안 맞으면 임베딩·사례 대응이 깨진 것이라 즉시 터뜨린다(예상 못 한 실패).
    """
    if len(cases) != len(embeddings):
        raise ValueError(
            f"사례 {len(cases)}건과 임베딩 {len(embeddings)}개 수가 안 맞는다"
        )
    return [
        {
            "text": c["text"],
            "violation": c.get("violation"),
            "disposition": c.get("disposition"),
            "source": c.get("source"),
            "embedding": emb,
        }
        for c, emb in zip(cases, embeddings)
    ]


def replace_cases(client, rows: list[dict]) -> int:
    """reference_cases를 통째로 갈아끼운다(기존 삭제 후 새로 적재). 적재 건수 반환.

    적재 스크립트는 멱등이어야 한다(여러 번 돌려도 중복 안 쌓이게). id는 bigserial이라
    항상 양수 → neq('id', 0)로 전체 삭제.
    """
    client.table(_TABLE).delete().neq("id", 0).execute()
    if rows:
        client.table(_TABLE).insert(rows).execute()
    return len(rows)


def search_similar_cases(client, embedding: list[float], k: int = 3) -> list[dict]:
    """유사 사례 top-K를 match_reference_cases RPC로 조회한다. 없으면 빈 리스트."""
    resp = client.rpc(
        _MATCH_RPC, {"query_embedding": embedding, "match_count": k}
    ).execute()
    return resp.data or []


def build_case_retriever(k: int = 3, cap: int = 6):
    """프로덕션 CaseRetriever를 만든다(실 OpenAI 임베딩 + 실 Supabase 검색).

    클라이언트 생성은 지연 연결이라 여기선 네트워크를 안 탄다. env(SUPABASE_*)가
    없으면 get_supabase_client가 터지므로, 호출부(app.py)에서 감싸 실패 시 None으로
    떨어뜨린다(그럼 RagJudge는 규정만으로 grounding). 검색 실패는 CaseRetriever가
    이미 빈 블록으로 degrade한다.
    """
    from barum.reference.case_retriever import CaseRetriever
    from barum.storage.client import get_supabase_client
    from barum.storage.embeddings import embed_texts

    client = get_supabase_client()
    return CaseRetriever(
        embed_fn=embed_texts,
        search_fn=lambda vec, kk: search_similar_cases(client, vec, kk),
        k=k,
        cap=cap,
    )
