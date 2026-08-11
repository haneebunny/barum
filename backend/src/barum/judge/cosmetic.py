"""화장품 판정 어댑터 (얇은 슬롯).

`CosmeticJudge` 프로토콜을 만족하는 구현체를 이 파일에 두고, 파이프라인은
프로토콜에만 의존한다.
- `StubJudge`: 규칙집 없이 계약을 시연하는 더미(키워드 매칭).
- `PromptJudge`: VLM 제로샷 판정. 규칙집(RAG) 없이도 실판정. score_eval과 같은
  프롬프트를 공유한다.
규칙집(레퍼런스팩)이 오면 `RagJudge`를 여기 추가해 슬롯만 갈아끼운다.
"""

from dataclasses import dataclass, field
from typing import Protocol

from barum.models import (
    Finding,
    Location,
    RiskLevel,
    UnjudgedSentence,
    ViolationType,
)
from barum.reference.ingredients import infer_category, match_ingredient
from barum.reference.mapping import legal_basis_for
from barum.vlm import VLM


@dataclass
class JudgeResult:
    """판정 결과 묶음.

    findings = 위반으로 지목된 것. unjudged = 판정 실패로 못 가린 것(미판정).
    미판정을 '합법'으로 삼키면 미탐이 숨으므로 분리해서 돌려준다(recall 우선).
    """

    findings: list[Finding] = field(default_factory=list)
    unjudged: list[UnjudgedSentence] = field(default_factory=list)


class CosmeticJudge(Protocol):
    """판정기가 지켜야 할 최소 인터페이스."""

    def judge(
        self,
        sentences: list[dict],
        region: str,
        ingredients: list[str] | None = None,
    ) -> JudgeResult:
        """문장 리스트를 받아 위반 findings + 미판정 목록을 낸다.

        입력 문장 dict: {order:int, tile:str|None, text:str} (파이프라인이 만든 형태).
        합법·대상외는 finding을 만들지 않는다(근거 개수 = 위반 건수).
        ingredients: 선택적 전성분 목록. 있으면 2호(기능성오인) 판정에 성분
        정합(고시원료 존재 여부) 대조를 덧붙인다.
        """
        ...


# 위반유형별 근거 조항은 reference.mapping이 단일 출처다(레퍼런스 팩과 드리프트 방지).
# 위험도. 프롬프트가 위험도를 주지 않아 유형별로 고정 매핑한다. recall 우선이라
# 위반은 최소 '중' 이상으로 둔다.
_RISK = {
    ViolationType.type_1_drug_misperception: RiskLevel.high,
    ViolationType.type_2_functional_misperception: RiskLevel.medium,
    ViolationType.type_5_deception: RiskLevel.medium,
}


def _loc(s: dict) -> Location:
    return Location(tile=s.get("tile"), order=s.get("order", 0))


# ── StubJudge (규칙집·VLM 없이 스키마 시연) ────────────────────────────────

# 키워드 → 위반유형. 앞에서부터 처음 걸리는 하나로 판정한다(결정론적, 테스트 가능).
# 진짜 판정 로직이 아니라 스키마를 그럴듯하게 채우는 더미 규칙일 뿐이다.
_KEYWORD_RULES: list[tuple[str, ViolationType]] = [
    ("재생", ViolationType.type_1_drug_misperception),
    ("치료", ViolationType.type_1_drug_misperception),
    ("염증", ViolationType.type_1_drug_misperception),
    ("미백", ViolationType.type_2_functional_misperception),
    ("주름", ViolationType.type_2_functional_misperception),
    ("자외선차단", ViolationType.type_2_functional_misperception),
    ("3배", ViolationType.type_5_deception),
    ("최고", ViolationType.type_5_deception),
    ("완벽", ViolationType.type_5_deception),
    ("100%", ViolationType.type_5_deception),
]


class StubJudge:
    """규칙집·VLM 없이 계약을 시연하는 더미 판정기.

    문장에 미리 정한 키워드가 있으면 해당 위반유형으로 finding을 만든다. 실제
    위반 여부와는 무관하다. 목적은 응답 스키마를 채워 프론트가 붙게 하는 것.
    VLM을 안 부르므로 오프라인·키 없는 개발/테스트에 쓴다. 미판정은 없다.
    """

    def judge(
        self,
        sentences: list[dict],
        region: str,
        ingredients: list[str] | None = None,
    ) -> JudgeResult:
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
                            legal_basis=legal_basis_for(vtype),
                            risk=_RISK[vtype],
                            explanation=f"(더미 판정) '{keyword}' 표현이 {vtype.value}에 해당할 소지가 있다.",
                            location=_loc(s),
                        )
                    )
                    break  # 한 문장당 첫 매칭 하나만
        return JudgeResult(findings=findings)


# ── PromptJudge (VLM 제로샷 판정) ──────────────────────────────────────────

# 라벨 문자열 → enum. 프롬프트가 뱉는 라벨을 그대로 매핑한다(reference/cosmetic_kr).
_LABEL_TO_TYPE = {
    "합법": ViolationType.legal,
    "1호_의약품오인": ViolationType.type_1_drug_misperception,
    "2호_기능성오인": ViolationType.type_2_functional_misperception,
    "5호_거짓과장기만": ViolationType.type_5_deception,
    "대상외": ViolationType.out_of_scope,
}
# 위반 아님(=finding 안 만듦)인 유형.
_NON_VIOLATION = {ViolationType.legal, ViolationType.out_of_scope}

# score_eval.py와 공유하는 판정 프롬프트. 여기가 원본이고 score_eval이 import한다.
JUDGE_PROMPT = """너는 한국 화장품 광고 문구가 화장품법 표시·광고 규정을 위반하는지 판정한다.
아래 문장 각각에 라벨 하나와 짧은 근거를 매겨라.

라벨(정확히 이 중 하나만):
- 합법 : 일반 보습·사용감·제형 설명 등 위반 소지 없음
- 1호_의약품오인 : 질병·치료·재생·염증 등 의학적/의약품 같은 효능 암시
- 2호_기능성오인 : 미백·주름개선·자외선차단 기능성 효능을 주장
- 5호_거짓과장기만 : 근거 없는 수치·최상급·비교우위·후기 단정·경쟁사 비방
- 대상외 : 광고 문구가 아님(성분명 나열, 거래·배송 안내, 인증서 표시, 단순 제품정보·브랜드명)

규칙:
- 한 문장에 여러 개 해당하면 가장 무거운 것 하나. 우선순위 1호 > 2호 > 5호 > 합법.
- 미탐(위반을 합법으로 놓침)이 제일 나쁘다. 애매하면 위반 쪽으로 판단한다.

문장:
{items}

JSON으로만 답하라: {{"results": [{{"n": 1, "label": "...", "reason": "..."}}]}}"""


def _ingredient_match_note(sentence: str, ingredients: list[str] | None) -> str | None:
    """2호(기능성오인) finding에 붙일 성분 정합 안내. 붙일 게 없으면 None.

    VLM은 '미백/주름/자외선차단을 표방했다'까지만 판정하고, 실제 전성분에 그
    기능의 고시원료가 있는지는 모른다. 이건 정확 조회 문제라 여기서 결정론적으로
    확인한다(functional_ingredients.md "판정에 쓰는 법"의 코드화).
    """
    if not ingredients:
        return "(전성분 미입력 — 성분 정합 확인 못 함)"
    category = infer_category(sentence)
    if category is None:
        return None  # 문구에서 기능성 카테고리를 못 정했으면 안내 생략
    row = match_ingredient(category, ingredients)
    if row is None:
        return f"(전성분 대조: {category} 고시원료가 전성분에 없음 — 위반 소지 큼)"
    함량 = row.get("기준 함량") or row.get("최대 함량", "")
    return f"(전성분 대조: {row['성분명']} 확인됨, 기준 {함량})"


class PromptJudge:
    """VLM 제로샷 판정기. 규칙집(RAG) 없이도 실판정을 낸다.

    문장을 배치로 묶어 한 번에 판정한다(과금·throttle 절감). 배치 호출이 실패하면
    재시도하지 않고(과금 호출) 그 배치 문장들을 미판정으로 남긴다. 모델이 특정
    문장 결과를 빠뜨리거나 규격 밖 라벨을 주면, '합법'으로 삼키지 않고 미판정 처리.
    """

    def __init__(self, vlm: VLM, batch_size: int = 12):
        self.vlm = vlm
        self.batch_size = batch_size

    def judge(
        self,
        sentences: list[dict],
        region: str,
        ingredients: list[str] | None = None,
    ) -> JudgeResult:
        result = JudgeResult()
        for start in range(0, len(sentences), self.batch_size):
            batch = sentences[start : start + self.batch_size]
            # 배치 안 문장에 전역 번호(start+j)를 매겨 결과를 되짚는다.
            numbered = "\n".join(
                f"{start + j}. {s['text']}" for j, s in enumerate(batch)
            )
            try:
                res = self.vlm.generate_json(JUDGE_PROMPT.format(items=numbered), [])
            except Exception as e:
                # 예상된 실패(429·타임아웃·빈 응답). 재시도 없이 배치 전체 미판정.
                print(
                    f"    [skip] judge 배치 {start}~{start + len(batch) - 1}: "
                    f"{type(e).__name__}: {e}"
                )
                for s in batch:
                    result.unjudged.append(
                        UnjudgedSentence(sentence=s["text"], location=_loc(s))
                    )
                continue

            by_n: dict[int, dict] = {}
            for item in res.get("results", []):
                try:
                    by_n[int(item["n"])] = item
                except (KeyError, ValueError, TypeError):
                    continue

            for j, s in enumerate(batch):
                item = by_n.get(start + j)
                label = (item or {}).get("label", "")
                label = label.strip() if isinstance(label, str) else ""
                vtype = _LABEL_TO_TYPE.get(label)
                if vtype is None:
                    # 결과 누락·규격 밖 라벨 → 미판정(안전으로 삼키지 않음).
                    result.unjudged.append(
                        UnjudgedSentence(sentence=s["text"], location=_loc(s))
                    )
                    continue
                if vtype in _NON_VIOLATION:
                    continue  # 합법·대상외 → finding 없음
                explanation = item.get("reason") or f"{vtype.value} 소지"
                if vtype == ViolationType.type_2_functional_misperception:
                    note = _ingredient_match_note(s["text"], ingredients)
                    if note:
                        explanation = f"{explanation} {note}"
                result.findings.append(
                    Finding(
                        span=s["text"],  # 이 프롬프트는 문장 단위 라벨 = span은 문장 전체
                        sentence=s["text"],
                        violation_type=vtype,
                        legal_basis=legal_basis_for(vtype),
                        risk=_RISK[vtype],
                        explanation=explanation,
                        location=_loc(s),
                    )
                )
        return result
