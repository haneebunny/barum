"""실제 적발사례 추출 (cases.md → 구조화).

`cases.md` §1 행정처분 확정 사례 표를 {text, violation, disposition, source}
리스트로 뽑는다. 이 사례들을 임베딩해 Supabase에 적재하고(Phase3 적재 스크립트),
새 광고 문구와 유사한 사례를 검색해 판정 프롬프트에 넣는다.

문구(요지) 열을 임베딩 대상(text)으로 쓴다. 요지가 실제 카피 대신 요약("의약품
오인 우려")인 행도 있는데, 그런 행은 실제 카피 질의에 유사도가 낮게 나와 자연히
top-K에서 밀린다. 그래서 별도 필터 없이 표 전체를 그대로 담는다.
"""

from functools import lru_cache
from pathlib import Path

# cases.py: backend/src/barum/reference/cases.py → parents[3] = backend.
_BACKEND = Path(__file__).resolve().parents[3]
_CASES_MD = _BACKEND / "reference" / "cosmetic_kr" / "cases.md"


def _find_column(header: list[str], keyword: str) -> str:
    """헤더에서 keyword를 포함하는 열 이름을 찾는다(열 순서·공백 변화에 견디게)."""
    for h in header:
        if keyword in h:
            return h
    raise ValueError(f"'{keyword}' 열을 못 찾음 — cases.md 표 헤더가 바뀌었을 수 있다: {header}")


def _parse_disposition_rows(md: str) -> list[dict]:
    """'문구'를 헤더에 가진 첫 파이프 표를 행 dict 리스트로 파싱한다."""
    lines = md.splitlines()
    head_i = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("|") and "문구" in ln),
        None,
    )
    if head_i is None:
        raise ValueError("cases.md에서 '문구' 열을 가진 표를 못 찾음")
    header = [c.strip() for c in lines[head_i].strip().strip("|").split("|")]
    rows: list[dict] = []
    for ln in lines[head_i + 2 :]:  # +1은 --- 구분선
        s = ln.strip()
        if not s.startswith("|"):
            break  # 표 끝
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


@lru_cache(maxsize=1)
def extract_cases() -> list[dict]:
    """cases.md §1 표 → [{text, violation, disposition, source}]."""
    md = _CASES_MD.read_text(encoding="utf-8")
    rows = _parse_disposition_rows(md)
    header = list(rows[0].keys())
    text_col = _find_column(header, "문구")
    violation_col = _find_column(header, "위반")
    disposition_col = _find_column(header, "처분")
    source_col = _find_column(header, "출처")
    return [
        {
            "text": r[text_col],
            "violation": r[violation_col],
            "disposition": r[disposition_col],
            "source": r[source_col],
        }
        for r in rows
        if r[text_col]
    ]
