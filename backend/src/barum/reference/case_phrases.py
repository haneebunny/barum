"""적발 사례 문구 재사용 차단 (대체표현 게이트 3층).

`cases.md`에 실린 **실제로 적발된 광고 문구**를 조각으로 쪼개 두고, 우리가 제안하는
대체표현이 그 조각을 그대로 담고 있으면 거부한다.

왜 필요한가. 규칙집 키워드는 팩을 전부 못 덮는다(근거 감사 결론). 그래서 규칙에 없는
표현이 제안으로 나가는 구멍이 있었다 — `깊숙이 침투`가 그렇게 나갔는데, 정작 그
문구는 `cases.md`에 적발 사례로 세 건이나 있었다. 우리가 가진 자료를 안 보고 있었다.

**한계를 분명히 적어 둔다. 이 층은 좁다.**
적발된 문구를 **그대로 다시 쓰는 것만** 막는다. 패러프레이즈는 못 잡는다
(`"피부 속 깊이 전달되는 앰플"`은 cases.md에 그 표기가 없어 안 걸린다).
넓은 방어는 규칙 게이트(2층)가 담당한다. **이 층이 있으니 안전하다고 읽으면 안 된다.**

비용: 외부 호출 0회, 건당 0.002ms 수준(순수 문자열 대조).
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]
_CASES = _BACKEND.parent / "reference" / "cosmetic_kr" / "cases.md"

# 사례 표에서 인용부호로 묶인 광고 문구를 뽑는다. 너무 짧은 건 흔한 말이라 뺀다.
#
# **`|`와 줄바꿈을 제외하는 게 중요하다.** 안 그러면 닫는 따옴표와 **다음 행의 여는
# 따옴표**가 짝지어져 그 사이 표 메타데이터(출처 파일명·처분 내역)까지 광고 문구로
# 색인된다. 실제로 그래서 "인체적용시험결과_표시광고위반사례.pdf" 같은 파일명이
# 위험 조각이 돼 있었다(2026-08-23 발견).
_QUOTED = re.compile(r'["“]([^"“”|\n]{6,120})["”]')
_STRIP = re.compile(r"[\s·,\.\-—()\[\]'\"“”‘’:;/|*_`>#~+→!?]+")

# 조각 길이. **6이 실효 하한이다**(2026-08-23 실측).
# 8 이상으로 키우면 `깊숙이 침투` 계열이 하나도 안 걸린다. 6에서 조건표 후보 85건
# 오차단 0건을 확인했다(우리가 실제로 제안하는 문구가 이 게이트의 진짜 대상이다).
_GRAM = 7

# **우리 시스템이 스스로 붙이는 상용구.** 위험 신호에서 뺀다.
# 재작성 프롬프트가 "(인체적용시험 결과)"를 붙이라고 예시로 지시하는데, 같은 문구가
# 사례 표에도 있어서 우리 제안이 우리 게이트에 걸렸다. 우리가 내보내라고 정한 말은
# 적발 문구의 재사용이 아니다.
_OWN_BOILERPLATE = (
    "인체적용시험 결과",
    "실증자료",
    "시험분석 결과",
    "인체외시험 결과",
)


def _norm(text: str) -> str:
    return _STRIP.sub("", unicodedata.normalize("NFKC", text or "")).lower()


@lru_cache(maxsize=1)
def _case_grams() -> frozenset[str]:
    """적발 사례 문구를 n-gram 집합으로. md는 런타임에 안 바뀌므로 캐시한다."""
    def _grams(s: str) -> set[str]:
        n = _norm(s)
        return {n[i : i + _GRAM] for i in range(len(n) - _GRAM + 1)}

    text = _CASES.read_text(encoding="utf-8")
    grams: set[str] = set()
    for quoted in _QUOTED.findall(text):
        grams |= _grams(quoted)
    for own in _OWN_BOILERPLATE:
        grams -= _grams(own)
    return frozenset(grams)


def reuses_sanctioned_phrase(text: str, original: str | None = None) -> bool:
    """제안 문구가 적발 사례 문구 조각을 그대로 담고 있으면 True.

    `original`(원본 광고 문구)을 주면 **원본에 이미 있던 조각은 빼고 본다.**
    다시 쓴 문장이 원문의 수치·표현을 정당하게 물려받는 경우가 있어서다. 물려받은
    위험까지 여기서 막으면 사업자가 실제로 측정한 수치를 우리가 지우게 된다
    (팀 결정: "수치를 지우는 대신 자료를 받는다"). 새로 생긴 위험만 막는다.
    """
    n = _norm(text)
    hits = {
        n[i : i + _GRAM]
        for i in range(len(n) - _GRAM + 1)
        if n[i : i + _GRAM] in _case_grams()
    }
    if original:
        o = _norm(original)
        hits -= {o[i : i + _GRAM] for i in range(len(o) - _GRAM + 1)}
    return bool(hits)
