"""화장품 판정 어댑터 (얇은 슬롯).

`CosmeticJudge` 프로토콜을 만족하는 구현체를 이 파일에 두고, 파이프라인은
프로토콜에만 의존한다. 지금은 규칙집(레퍼런스팩)이 없어 `StubJudge`(가짜 findings)만
있다. 규칙집이 오면 `RagJudge`를 여기 추가해 슬롯만 갈아끼우고, 나머지 코드
(파이프라인·API·모델)는 건드리지 않는다. vlm.py의 provider 어댑터 패턴과 같다.
"""

from typing import Protocol

from barum.models import Finding, Location, RiskLevel, ViolationType


class CosmeticJudge(Protocol):
    """판정기가 지켜야 할 최소 인터페이스."""

    def judge(self, sentences: list[dict], region: str) -> list[Finding]:
        """문장 리스트를 받아 위반 findings를 낸다.

        입력 문장 dict: {order:int, tile:str|None, text:str} (파이프라인이 만든 형태).
        합법 문장은 finding을 만들지 않는다(근거 개수 = 위반 건수).
        """
        ...


# 위반유형별 시연용 근거 조항. 규칙집이 오면 RagJudge가 실제 조항·성분정합으로 채운다.
_LEGAL_BASIS = {
    ViolationType.type_1_drug_misperception: "화장품법 제13조 제1항 제1호 (의약품 오인)",
    ViolationType.type_2_functional_misperception: "화장품법 제13조 제1항 제2호 (기능성 오인)",
    ViolationType.type_4_falsity_deception: "화장품법 제13조 제1항 제4호 (거짓·과장·기만)",
}

_RISK = {
    ViolationType.type_1_drug_misperception: RiskLevel.high,
    ViolationType.type_2_functional_misperception: RiskLevel.medium,
    ViolationType.type_4_falsity_deception: RiskLevel.medium,
}

# 키워드 → 위반유형. 앞에서부터 처음 걸리는 하나로 판정한다(결정론적, 테스트 가능).
# 이건 진짜 판정 로직이 아니라 스키마를 그럴듯하게 채우는 더미 규칙일 뿐이다.
_KEYWORD_RULES: list[tuple[str, ViolationType]] = [
    ("재생", ViolationType.type_1_drug_misperception),
    ("치료", ViolationType.type_1_drug_misperception),
    ("염증", ViolationType.type_1_drug_misperception),
    ("미백", ViolationType.type_2_functional_misperception),
    ("주름", ViolationType.type_2_functional_misperception),
    ("자외선차단", ViolationType.type_2_functional_misperception),
    ("3배", ViolationType.type_4_falsity_deception),
    ("최고", ViolationType.type_4_falsity_deception),
    ("완벽", ViolationType.type_4_falsity_deception),
    ("100%", ViolationType.type_4_falsity_deception),
]


class StubJudge:
    """규칙집 없이 계약을 시연하는 더미 판정기.

    문장에 미리 정한 키워드가 있으면 해당 위반유형으로 finding을 만든다. 실제
    위반 여부와는 무관하다. 목적은 응답 스키마를 채워 프론트가 붙게 하는 것.
    """

    def judge(self, sentences: list[dict], region: str) -> list[Finding]:
        findings: list[Finding] = []
        for s in sentences:
            text = s.get("text", "")
            for keyword, vtype in _KEYWORD_RULES:
                if keyword in text:
                    findings.append(
                        Finding(
                            span=keyword,
                            sentence=text,
                            violation_type=vtype,
                            legal_basis=_LEGAL_BASIS[vtype],
                            risk=_RISK[vtype],
                            explanation=f"(더미 판정) '{keyword}' 표현이 {vtype.value}에 해당할 소지가 있다.",
                            location=Location(tile=s.get("tile"), order=s.get("order", 0)),
                        )
                    )
                    break  # 한 문장당 첫 매칭 하나만
        return findings
