"""OCR 문장 리스트에서 전성분 블록을 찾아 뽑는다.

11번가 상세페이지 이미지는 보통 "전성분"/"성분"/"Ingredients" 같은 헤더 다음 줄에
콤마로 나열된 성분표가 온다(헤더와 내용이 한 줄에 붙어 있는 경우도 있다). 헤더가
아예 없이 "정제수, ..."로 바로 시작하는 레이아웃도 있어 첫 성분명으로도 잡는다.
"""

import re

_HEADER_KEYWORDS = r"전\s*성\s*분|성분명|표시\s*성분|성분|ingredients?"
_HEADER_ONLY_RE = re.compile(rf"^(?:{_HEADER_KEYWORDS})\s*[:：]?\s*$", re.IGNORECASE)
_INLINE_RE = re.compile(rf"^(?:{_HEADER_KEYWORDS})\s*[:：]?\s*(.+)$", re.IGNORECASE)
_FIRST_INGREDIENT_RE = re.compile(r"^(정제수|정제\s*수|water|aqua)\b", re.IGNORECASE)
_LOOKAHEAD_LINES = 2


def _looks_like_ingredient_list(text: str) -> bool:
    return text.count(",") >= 3 and len(text) > 15


def extract_ingredients_block(sentences: list[dict]) -> str | None:
    """OCR 문장 dict 리스트(`{"text": ...}`)에서 전성분 블록 텍스트를 찾는다.

    못 찾으면 None. 반환값은 `run_check(ingredients=...)`에 그대로 넘길 수 있는
    콤마 구분 문자열이다.
    """
    texts = [str(s.get("text", "")).strip() for s in sentences]
    for i, t in enumerate(texts):
        if not t:
            continue
        m = _INLINE_RE.match(t)
        if m and _looks_like_ingredient_list(m.group(1)):
            return m.group(1).strip()
        if _HEADER_ONLY_RE.match(t):
            for j in range(i + 1, min(i + 1 + _LOOKAHEAD_LINES, len(texts))):
                nxt = texts[j]
                if _looks_like_ingredient_list(nxt):
                    return nxt
        if not m and _looks_like_ingredient_list(t) and _FIRST_INGREDIENT_RE.match(t):
            return t
    return None
