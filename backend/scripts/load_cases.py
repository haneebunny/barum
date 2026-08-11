"""cases.md 실사례를 임베딩해 Supabase reference_cases에 적재 (배포 시 1회).

    ./venv/bin/python scripts/load_cases.py

선행: db/schema.sql이 Supabase에 적용돼 있어야 한다(reference_cases 테이블·pgvector).
멱등: 기존 사례를 지우고 새로 적재하므로 여러 번 돌려도 중복 안 쌓인다.
cases.md가 바뀌면(사례 추가 등) 이 스크립트를 다시 돌려 갱신한다.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from barum.reference.cases import extract_cases  # noqa: E402
from barum.storage.cases_store import build_case_rows, replace_cases  # noqa: E402
from barum.storage.client import get_supabase_client  # noqa: E402
from barum.storage.embeddings import embed_texts  # noqa: E402


def main() -> None:
    cases = extract_cases()
    print(f"cases.md 사례 {len(cases)}건 추출")
    if not cases:
        print("적재할 사례가 없다 — cases.md 표를 확인할 것")
        return

    vectors = embed_texts([c["text"] for c in cases])
    dim = len(vectors[0]) if vectors else 0
    print(f"임베딩 {len(vectors)}개 생성 (dim {dim}, text-embedding-3-small)")

    rows = build_case_rows(cases, vectors)
    n = replace_cases(get_supabase_client(), rows)
    print(f"Supabase reference_cases 적재 완료: {n}건")


if __name__ == "__main__":
    main()
