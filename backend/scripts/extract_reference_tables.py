"""레퍼런스 팩의 표를 JSON으로 구조화 추출.

    ./venv/bin/python scripts/extract_reference_tables.py

`functional_ingredients.md`(성분표)·`prohibited_expressions.md`(금지표현표)는
판정기가 "정확 조회"해야 하는 표다(의미검색이 아니라 존재·함량 대조). 마크다운
표는 사람이 읽기엔 좋지만 코드가 매번 파싱하긴 부정확·비효율이라, 여기서 한 번
JSON으로 뽑아 `src/barum/reference/data/`에 둔다. 레퍼런스 md가 바뀌면 이 스크립트를
다시 돌려 JSON을 갱신한다(마크다운이 정본, JSON은 파생 산출물).

금지표현 표의 "금지표현/패턴" 셀은 쉼표(,)와 가운뎃점(·)이 섞여 쓰여
("살균·소독"처럼 가운뎃점이 한 단어를 묶기도, "無 스테로이드·無 벤조피렌"처럼
여러 단어를 묶기도 함) 자동으로 개별 문구로 쪼개면 잘못 잘릴 위험이 크다.
그래서 행(row) 단위까지만 구조화하고, 셀 안 문구 리스트는 원문 그대로 남긴다.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT.parent / "reference" / "cosmetic_kr"
OUT_DIR = ROOT / "src" / "barum" / "reference" / "data"


def _sections(text: str) -> dict[str, str]:
    """'## ' 헤딩 기준으로 절을 나눈다. {헤딩 텍스트: 본문}."""
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    out: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        out[parts[i].strip()] = parts[i + 1]
    return out


def _parse_table(block: str) -> list[dict]:
    """마크다운 파이프 표 하나를 [{헤더: 값}] 리스트로 파싱. 표 없으면 빈 리스트."""
    lines = [ln for ln in block.strip().splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []
    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    rows = []
    for line in lines[2:]:  # lines[1]은 --- 구분선
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue  # 표 형식이 아닌 줄(각주 등)은 건너뜀
        rows.append(dict(zip(header, cells)))
    return rows


def extract_functional_ingredients() -> dict:
    """미백·주름개선·자외선차단 3개 표 → 카테고리별 성분 리스트."""
    text = (REF_DIR / "functional_ingredients.md").read_text(encoding="utf-8")
    secs = _sections(text)

    def find(keyword: str) -> list[dict]:
        for heading, body in secs.items():
            if keyword in heading:
                return _parse_table(body)
        raise ValueError(f"'{keyword}' 절을 찾을 수 없다 — 레퍼런스 md 구조가 바뀌었을 수 있다")

    return {
        "source": "reference/cosmetic_kr/functional_ingredients.md",
        "citation": "기능성화장품 심사에 관한 규정(고시 제2023-61호) 별표4",
        "categories": {
            "미백": find("미백"),
            "주름개선": find("주름"),
            "자외선차단": find("자외선"),
        },
    }


def extract_prohibited_expressions() -> dict:
    """§1 금지표현 목록 표 → 행 리스트(위반유형·구분·금지표현/패턴·근거·비고)."""
    text = (REF_DIR / "prohibited_expressions.md").read_text(encoding="utf-8")
    secs = _sections(text)
    for heading, body in secs.items():
        if "§1" in heading and "금지표현" in heading:
            rows = _parse_table(body)
            return {
                "source": "reference/cosmetic_kr/prohibited_expressions.md",
                "citation": "화장품 표시·광고 관리 지침(민원인 안내서, 2025.8.14) [별표1]",
                "note": "금지표현/패턴 셀은 원문 그대로(쉼표·가운뎃점 혼용이라 자동 분리 안 함)",
                "rows": rows,
            }
    raise ValueError("§1 금지표현 목록 절을 찾을 수 없다 — 레퍼런스 md 구조가 바뀌었을 수 있다")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fi = extract_functional_ingredients()
    fi_path = OUT_DIR / "functional_ingredients.json"
    fi_path.write_text(json.dumps(fi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {k: len(v) for k, v in fi["categories"].items()}
    print(f"저장: {fi_path.relative_to(ROOT)}  (성분 {counts})")

    pe = extract_prohibited_expressions()
    pe_path = OUT_DIR / "prohibited_expressions.json"
    pe_path.write_text(json.dumps(pe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"저장: {pe_path.relative_to(ROOT)}  (행 {len(pe['rows'])}개)")


if __name__ == "__main__":
    main()
