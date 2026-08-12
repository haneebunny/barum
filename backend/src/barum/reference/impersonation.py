"""이미지 생성 사칭 가드레일 (FR-13).

이미지 생성 요청 프롬프트에 전문가·의료진 사칭 소지가 있으면 생성을 거부한다.
개정법 신설 4호(AI 생성물로 전문가 보증 오인)의 콘텐츠 생성 시점 방어선이다.
짧은 이미지 프롬프트 대상이라 키워드 매칭으로 충분하다(오탐 관측 시 조정).

reference: prohibited_expressions T5의 "의사 추천·병원" 계열과 정합.
"""

# 사칭 소지 키워드: 의료진·전문가·의료기관 묘사·보증 암시.
_IMPERSONATION_KEYWORDS: tuple[str, ...] = (
    "의사",
    "의료진",
    "약사",
    "한의사",
    "병원",
    "피부과",
    "의료기관",
    "전문가",
    "임상",
    "흰 가운",
    "가운 입은",
    "청진기",
    "처방",
    "백의",
)


def check_impersonation(prompt: str) -> tuple[bool, str | None]:
    """이미지 생성 프롬프트를 검사해 (허용여부, 거부사유)를 낸다.

    사칭 키워드가 있으면 (False, 사유), 없으면 (True, None). 통과분만 실제 생성으로
    넘어가고(이번 MVP는 생성 자체는 폴백), 거부분은 사유를 사용자에게 안내한다.
    """
    for kw in _IMPERSONATION_KEYWORDS:
        if kw in prompt:
            return (
                False,
                f"'{kw}' 표현은 전문가·의료진 사칭 소지가 있어 이미지 생성이 거부됩니다.",
            )
    return True, None
