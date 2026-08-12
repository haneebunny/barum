"""개인정보(PII) 자동 제거 (콘텐츠 생성 FR-11).

생성·개선된 콘텐츠에서 전화번호·이메일·주민등록번호 같은 개인정보를 정규식으로
찾아 마스킹한다. 어떤 종류가 제거됐는지 목록으로 돌려줘 사용자에게 고지한다.
의미검색이 아니라 형식 매칭이라 정규식으로 충분하다.
"""

import re

# 제거 순서 = 이 dict 순서. 긴 패턴(주민번호 13자리)을 전화번호보다 먼저 잡아
# 부분 매칭으로 잘리지 않게 한다.
_PATTERNS: dict[str, re.Pattern] = {
    "이메일": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "주민등록번호": re.compile(r"\d{6}[-\s]?\d{7}"),
    "전화번호": re.compile(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}"),
}
_MASK = "[개인정보 제거됨]"


def remove_pii(text: str) -> tuple[str, list[str]]:
    """텍스트에서 PII를 마스킹하고 (정리된 텍스트, 제거된 종류 목록)을 낸다.

    같은 종류가 여러 번 나와도 종류는 목록에 한 번만 담는다(고지용).
    """
    removed: list[str] = []
    for kind, pattern in _PATTERNS.items():
        if pattern.search(text):
            removed.append(kind)
            text = pattern.sub(_MASK, text)
    return text, removed
