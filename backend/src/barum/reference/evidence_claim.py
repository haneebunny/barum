"""증빙 문서를 내세우는 문장 탐지 (에이전틱 판정 1단계, 순수 로직).

광고가 "인증받았다"·"시험 완료"·"기능성 보고" 같은 **문서 증빙**을 내세우면, 그
문서가 실제로 그 제품·그 주장과 맞는지는 텍스트만으론 못 가린다. 에스코 사례가
그 증거다(`docs/result/2026-08-15_확장정답셋_인용검증_보고서.md` §2): 광고에 붙은
"결과확인서"가 **완전히 다른 제품의 피부자극 패치테스트 결과지**였는데, 독립된 두
LLM(luna·gpt-5)이 텍스트만 보고 둘 다 못 잡았다. 하나는 "근거 이미지 제시됨"이라며
합법으로까지 판정했다.

**문서가 존재한다는 것과 그 문서가 해당 제품·해당 주장과 일치한다는 것은 별개다.**

이 모듈은 그 확인이 필요한 문장을 **고르기만** 한다. 실제 대조(이미지 재조회)는
비용이 드는 VLM 호출이라 별도 단계에서 하고, 여기서 좁게 걸러 호출 횟수를 줄인다.
비비가 자동확정 705건을 16건으로 좁힐 때 쓴 키워드 축을 그대로 코드화한 것이다.
"""

import re

# 증빙 문서를 내세우는 표지. 비비가 705건 -> 16건으로 좁힐 때 쓴 축
# ("인증·시험·심사·보고·확인서·등록·임상·검사")을 그대로 코드화했다.
_EVIDENCE_TERMS: tuple[str, ...] = (
    "인증",
    "시험",
    "심사",
    "보고",
    "확인서",
    "등록",
    "임상",
    "검사",
    "특허",
    "결과지",
    "성적서",
)


def _normalize(text: str) -> str:
    """대조용 정규화 — 공백·붙임표·가운뎃점을 지운다(rules.py와 같은 방식)."""
    return re.sub(r"[\s·\-]", "", text)


def claims_documentary_evidence(sentence: str) -> bool:
    """문장이 문서 증빙(인증서·시험성적서 등)을 내세우는지 본다.

    여기서 True라고 위반이 아니다. "이 문장은 첨부 문서와 대조해 볼 가치가 있다"는
    뜻일 뿐이다. 실제 판정은 이미지 대조 단계가 한다.
    """
    norm = _normalize(sentence)
    return any(t in norm for t in _EVIDENCE_TERMS)


def select_for_verification(sentences: list[dict]) -> list[dict]:
    """증빙 대조가 필요한 문장만 추린다.

    입력은 파이프라인의 문장 dict 리스트({order, tile, text, ...}).
    이미지에서 온 문장만 대상이다 — 대조할 원본 이미지가 없으면 확인할 방법이 없다
    (텍스트로만 입력된 광고는 애초에 첨부 문서가 없다).
    """
    out = []
    for s in sentences:
        if not claims_documentary_evidence(s.get("text", "")):
            continue
        if s.get("tile") is None:
            continue  # 이미지 유래가 아니면 대조 대상 없음
        out.append(s)
    return out
