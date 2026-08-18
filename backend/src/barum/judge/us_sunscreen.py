"""미국 프리플라이트 판정 — 자외선차단(선크림) 최소보장.

`sunscreen_otc_classification.md`의 판정 규칙을 코드화한다. 국내 RagJudge와 달리 VLM을
호출하지 않는다 — SPF/자외선차단 표현은 회피할 이유가 없는 명확한 표현이라 문서에서
"키워드 매칭으로 충분하다"고 확정했고(§1①), 성분 대조는 `us_ingredients.py`의 정확
조회로 충분하다(§1②). 위반/합법 판정이 아니라 "규제 카테고리 전환 안내"라 국내
`ViolationType`/`JudgmentFlag`도 쓰지 않는다(`USPreflightCategory`, models.py 참조).
"""

from barum.models import Location, USPreflightCategory, USPreflightFinding
from barum.reference.us_ingredients import check_sunscreen_ingredients

# 회피할 이유가 없는 명확한 표현이라 정규식·동의어 없이 단순 포함 검사로 충분하다(대소문자 무시).
_SPF_KEYWORDS: tuple[str, ...] = (
    "spf",
    "자외선차단",
    "uv차단",
    "선블록",
    "sunscreen",
    "sun protection",
)

_OTC_EXPLANATION = (
    "SPF·자외선차단 표현은 미국에서 화장품이 아니라 OTC(일반의약품)로 분류됩니다. "
    "Drug Facts 표시패널, FDA 시설등록 등 화장품과 다른 규제 요건이 적용될 수 있습니다."
)

# §4 컨펌: 확정 안 된 규제 변경 리스크는 finding이 아니라 리포트 각주로만 담는다.
DISCLAIMER = (
    "본 결과는 법적 자문이 아니며 전문가 확인이 필요합니다. "
    "미국 자외선차단 규정(OTC Monograph M020)은 검토 중인 개정안(OTC000008)이 있어 "
    "향후 승인성분 목록이 변동될 수 있습니다."
)


def _loc(s: dict) -> Location:
    """국내 judge/cosmetic.py의 _loc()와 동일한 변환. 문장 dict → Location."""
    return Location(
        tile=s.get("tile"),
        order=s.get("order", 0),
        y_start=s.get("y_start"),
        y_end=s.get("y_end"),
        source_h=s.get("source_h"),
        source_w=s.get("source_w"),
        source=s.get("source"),
    )


def _find_spf_span(text: str) -> str | None:
    """문장에서 트리거된 키워드 하나를 찾아 원문 표기 그대로 돌려준다(매칭은 대소문자 무시)."""
    lowered = text.lower()
    for kw in _SPF_KEYWORDS:
        idx = lowered.find(kw)
        if idx != -1:
            return text[idx : idx + len(kw)]
    return None


class USSunscreenJudge:
    """자외선차단 미국 프리플라이트 판정기. VLM 없이 결정론적으로 동작한다."""

    def judge(
        self,
        sentences: list[dict],
        ingredients: list[str] | None = None,
    ) -> list[USPreflightFinding]:
        """문장 리스트 + 선택적 전성분 목록을 받아 미국 프리플라이트 지적을 낸다.

        입력 문장 dict: {order:int, tile:str|None, text:str, ...} (파이프라인이 만든 형태,
        국내 judge와 동일 계약). SPF 표현이 한 건도 없으면 성분 대조 자체를 안 한다 —
        표현 트리거 없이 성분만 있는 경우는 대상이 아니다(§3 세 번째 예시, "촉촉한
        수분크림"+Zinc oxide는 경고 없음).
        """
        findings: list[USPreflightFinding] = []

        for s in sentences:
            text = s.get("text", "")
            span = _find_spf_span(text)
            if span is None:
                continue
            findings.append(
                USPreflightFinding(
                    span=span,
                    sentence=text,
                    category=USPreflightCategory.otc_reclassification,
                    explanation=_OTC_EXPLANATION,
                    location=_loc(s),
                )
            )

        if not findings:
            return findings

        ingredient_order = len(sentences)
        if ingredients is None:
            findings.append(
                USPreflightFinding(
                    span="(전성분 미입력)",
                    sentence="",
                    category=USPreflightCategory.ingredient_info_missing,
                    explanation="전성분 정보가 없어 미국 승인 성분 여부를 확인할 수 없습니다. 전성분을 추가해 주세요.",
                    location=Location(tile=None, order=ingredient_order, source="ingredients"),
                )
            )
            return findings

        result = check_sunscreen_ingredients(ingredients)
        for name in result["unapproved"]:
            findings.append(
                USPreflightFinding(
                    span=name,
                    sentence=", ".join(ingredients),
                    category=USPreflightCategory.unapproved_ingredient,
                    explanation=f"'{name}'은(는) 미국 FDA 승인 자외선차단 성분 목록에 없습니다.",
                    location=Location(tile=None, order=ingredient_order, source="ingredients"),
                )
            )

        return findings
