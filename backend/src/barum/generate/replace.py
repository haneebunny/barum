"""위반 문구 → 안전 표현 치환 (조건표 재사용, 순수).

효능·기능 표현은 자유창작 없이 조건표(remediation_rules)로 결정적 치환한다
(FR-11 "FR-14와 같은 원칙"). VLM 없이 돌아가는 결정적 로직이라 순수 유닛테스트.
"""

from barum.models import Finding, Replacement
from barum.reference.remediation import get_remediation
from barum.reference.rules import RuleOutcome, match_rule

_BASIS = "합법 표기 틀(조건표) 기반 대체 표현"


def _first_safe(suggestions: list[str]) -> str | None:
    """조건표 후보 중 규칙집에서 위반으로 안 걸리는 첫 번째를 고른다.

    **왜 필요한가**: 조건표(`remediation_rules.json`)는 손으로 쓰는 JSON이고,
    거기 실린 대체표현이 그 자체로 위반인지 아무도 대조하지 않았다.
    2026-08-20 실사고로 5호 규칙이 '줄기세포'를 잡아 **'줄기세포 배양액 함유'**를
    대체표현으로 내보내고 있었다. 위반 문구를 위반 문구로 바꿔주고 있던 셈이다.

    데이터를 고치는 것만으로는 재발을 못 막는다. 조건표에 규칙이 추가될 때마다
    같은 실수가 가능하므로 코드가 마지막 방어선이 된다. `match_rule`은 규칙집
    정확조회라 API 비용이 0이다.

    **검토필요(needs_review)는 막지 않고 뒤로 미룬다.** 그 표현들은 팩이 §3 실증대상으로
    명시한 것이라(`피부 진정` → §3 "진정", `피부 저자극 테스트 완료` → §3 "시험·검사 표현"),
    금지하면 팩이 "자료 있으면 써도 된다"고 한 표현을 우리가 막는 셈이 된다. 대신 규칙에
    아예 안 걸리는 후보가 뒤에 있으면 그쪽을 먼저 고른다. 조건표에는 1순위가 검토필요인데
    2순위가 깨끗한 규칙이 실제로 있다(`피부 진정` 뒤의 `자극 완화` 등, 2026-08-20 도도3 리뷰).
    """
    fallback = None  # 위반은 아니지만 검토필요인 후보. 더 나은 게 없을 때만 쓴다.
    for s in suggestions:
        m = match_rule(s)
        if m is not None and m.outcome is RuleOutcome.violation:
            continue
        if m is None or m.outcome is not RuleOutcome.needs_review:
            return s  # 규칙 미매칭이거나 합법 확정 = 가장 안전
        if fallback is None:
            fallback = s
    return fallback


def build_replacements(findings: list[Finding]) -> list[Replacement]:
    """위반 finding마다 조건표에서 안전표현을 뽑아 Replacement 목록을 만든다.

    get_remediation은 키워드 매칭 실패 시에도 유형별 fallback을 주므로 대개 후보가 있다.
    다만 후보가 전부 위반으로 걸리면 **치환하지 않고 건너뛴다**. 위반 문구를 다른
    위반 문구로 바꾸느니 원문을 그대로 두고 사용자에게 위반으로 남겨 보이는 편이 낫다.
    치환 대상(original)은 span 우선, 없으면 문장 전체.
    """
    reps: list[Replacement] = []
    for f in findings:
        suggestions, _ = get_remediation(
            sentence=f.sentence, violation_type=f.violation_type, span=f.span
        )
        if not suggestions:
            continue
        safe = _first_safe(suggestions)
        if safe is None:
            # 조건표가 이 유형에 안전한 대체표현을 못 낸다. 치환 없이 남긴다.
            print(
                f"[replace] 안전한 대체표현 없음, 치환 건너뜀: "
                f"type={f.violation_type} span={f.span!r}"
            )
            continue
        reps.append(
            Replacement(
                original=f.span or f.sentence,
                replaced=safe,
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
