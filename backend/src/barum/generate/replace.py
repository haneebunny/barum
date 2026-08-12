"""위반 문구 → 안전 표현 치환 (조건표 재사용, 순수).

효능·기능 표현은 자유창작 없이 조건표(remediation_rules)로 결정적 치환한다
(FR-11 "FR-14와 같은 원칙"). VLM 없이 돌아가는 결정적 로직이라 순수 유닛테스트.
"""

from barum.models import Finding, Replacement
from barum.reference.remediation import get_remediation

_BASIS = "합법 표기 틀(조건표) 기반 대체 표현"


def build_replacements(findings: list[Finding]) -> list[Replacement]:
    """위반 finding마다 조건표에서 안전표현을 뽑아 Replacement 목록을 만든다.

    get_remediation은 키워드 매칭 실패 시에도 유형별 fallback을 주므로 항상 대체가 있다.
    치환 대상(original)은 span 우선, 없으면 문장 전체.
    """
    reps: list[Replacement] = []
    for f in findings:
        suggestions, _ = get_remediation(
            sentence=f.sentence, violation_type=f.violation_type, span=f.span
        )
        if not suggestions:
            continue
        reps.append(
            Replacement(
                original=f.span or f.sentence,
                replaced=suggestions[0],
                violation_type=f.violation_type,
                basis=_BASIS,
            )
        )
    return reps


def apply_replacements(content: str, reps: list[Replacement]) -> str:
    """원문에서 각 위반 표현(original)을 안전표현(replaced)으로 치환한 텍스트를 낸다."""
    for r in reps:
        content = content.replace(r.original, r.replaced)
    return content
