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
    JudgmentFlag,
    Location,
    UnjudgedSentence,
    ViolationType,
)
from barum.reference.context import (
    build_judgment_context,
    build_regulation_context,
)
from barum.reference.ingredients import infer_category, match_ingredient
from barum.reference.mapping import legal_basis_for
from barum.reference.rules import RuleOutcome, match_rule
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


def _loc(s: dict) -> Location:
    """문장 dict → Location. 밴드 좌표·원본 크기는 이미지 입력에만 실린다.

    _ocr_image가 문장 dict에 넣어 준 y_start/y_end/source_h/source_w를 그대로
    옮긴다. 텍스트 입력엔 이 키들이 없어 None으로 남는다(밴드 하이라이트 스킵).
    """
    return Location(
        tile=s.get("tile"),
        order=s.get("order", 0),
        y_start=s.get("y_start"),
        y_end=s.get("y_end"),
        source_h=s.get("source_h"),
        source_w=s.get("source_w"),
        source=s.get("source"),
    )


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
                            flag=JudgmentFlag.violation,  # 데모용, 근거 인프라 없음
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


def _functional_evidence(
    sentence: str, ingredients: list[str] | None
) -> tuple[str | None, JudgmentFlag]:
    """2호(기능성오인) finding의 근거를 성분표로 확인해 (안내문, 플래그)를 낸다.

    VLM은 '미백/주름/자외선차단을 표방했다'까지만 판정하고, 실제 전성분에 그
    기능의 고시원료가 있는지는 모른다. 이건 정확 조회 문제라 여기서 결정론적으로
    확인한다(functional_ingredients.md "판정에 쓰는 법"의 코드화).

    - 전성분 미입력/카테고리 불명 → 대조 근거 자체가 없다 → 검토필요.
    - 고시원료 없음 → 표방한 기능의 근거가 없다는 확증 → 위반.
    - 고시원료 있음 → 원료는 있으나 그 제품이 실제 기능성 심사·등록을 받았는지는
      알 수 없다(우리 입력엔 등록 여부가 없다) → 단정 못 하고 검토필요.
    """
    if not ingredients:
        return "(전성분 미입력, 성분 정합 확인 못 함)", JudgmentFlag.needs_review
    category = infer_category(sentence)
    if category is None:
        return None, JudgmentFlag.needs_review  # 카테고리도 못 정함, 안내는 생략
    row = match_ingredient(category, ingredients)
    if row is None:
        note = f"(전성분 대조: {category} 고시원료가 전성분에 없음, 위반 소지 큼)"
        return note, JudgmentFlag.violation
    함량 = row.get("기준 함량") or row.get("최대 함량", "")
    note = f"(전성분 대조: {row['성분명']} 확인됨, 기준 {함량}, 등록 여부 불명이라 단정 못 함)"
    return note, JudgmentFlag.needs_review


class PromptJudge:
    """VLM 제로샷 판정기. 규칙집(RAG) 없이도 실판정을 낸다.

    문장을 배치로 묶어 한 번에 판정한다(과금·throttle 절감). 배치 호출이 실패하면
    재시도하지 않고(과금 호출) 그 배치 문장들을 미판정으로 남긴다. 모델이 특정
    문장 결과를 빠뜨리거나 규격 밖 라벨을 주면, '합법'으로 삼키지 않고 미판정 처리.

    context: 선택적 판정 근거 블록(규정·판정기준·사례). 주면 판정 프롬프트 앞에
    붙어 LLM이 규정을 실제로 참고하게 한다(RagJudge가 채운다). 안 주면 기존 제로샷
    프롬프트 그대로라 score_eval·기존 동작에 영향 없다.
    """

    def __init__(self, vlm: VLM, batch_size: int = 12, context: str = ""):
        self.vlm = vlm
        self.batch_size = batch_size
        self.context = context

    def _build_prompt(self, numbered: str) -> str:
        """판정 프롬프트를 만든다. context가 있으면 근거 블록을 앞에 붙인다."""
        base = JUDGE_PROMPT.format(items=numbered)
        if not self.context:
            return base
        return (
            "아래 [판정 근거]는 화장품법 규정·판정기준·실제 적발사례다. "
            "반드시 이 근거에 비추어 판정하라.\n\n"
            f"[판정 근거]\n{self.context}\n\n"
            f"[판정 지시]\n{base}"
        )

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
                res = self.vlm.generate_json(self._build_prompt(numbered), [])
                # res가 dict가 아니면(가끔 모델이 {"results":[...]} 대신 통짜 리스트를
                # 뱉는다) .get()이 AttributeError를 던진다. 이것도 예상된 실패로 본다.
                raw_results = res.get("results", [])
            except Exception as e:
                # 예상된 실패(429·타임아웃·빈 응답·형식불일치). 재시도 없이 배치 전체 미판정.
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
            for item in raw_results:
                try:
                    by_n[int(item["n"])] = item
                except (KeyError, ValueError, TypeError):
                    continue

            for j, s in enumerate(batch):
                item = by_n.get(start + j)
                # n이 빗나가도(모델이 1-based 등) 결과 수 = 문장 수면 순서로 대응한다.
                # 개수가 다르면(누락·중복) 위치를 못 믿으니 fallback 안 함 → 미판정.
                if item is None and len(raw_results) == len(batch):
                    item = raw_results[j]
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
                # 근거 대조 수단이 있는 유형(2호)만 검토필요로 내려갈 수 있다.
                # 1호·5호는 RagJudge 붙기 전엔 대조 수단이 없어 잠정 위반(recall 우선).
                flag = JudgmentFlag.violation
                if vtype == ViolationType.type_2_functional_misperception:
                    note, flag = _functional_evidence(s["text"], ingredients)
                    if note:
                        explanation = f"{explanation} {note}"
                result.findings.append(
                    Finding(
                        span=s["text"],  # 이 프롬프트는 문장 단위 라벨 = span은 문장 전체
                        sentence=s["text"],
                        violation_type=vtype,
                        legal_basis=legal_basis_for(vtype),
                        flag=flag,
                        explanation=explanation,
                        location=_loc(s),
                    )
                )
        return result


# ── RagJudge (규칙집 우선 + VLM fallback) ──────────────────────────────────


def _rule_explanation(outcome: RuleOutcome, span: str, vtype: ViolationType) -> str:
    """규칙 매칭 finding의 사람용 설명을 만든다.

    검토필요(실증대상)와 위반은 왜 그 판정인지가 다르므로 문구를 갈라 준다.
    """
    if outcome == RuleOutcome.needs_review:
        return (
            f"규칙집 대조: '{span}'은 실증대상 표현이다. "
            f"실증자료가 있으면 합법, 없으면 {vtype.value}. 확인 필요."
        )
    return f"규칙집 대조: '{span}' 표현이 {vtype.value}에 해당한다(금지표현 확정)."


class RagJudge:
    """규칙집 우선 + VLM fallback 하이브리드 판정기.

    규칙집(reference.rules)으로 확정 가능한 문장(§3에서 규정 리서치로 검증된 1호
    경계표현)은 규칙이 먼저 판정한다. 규칙에 안 걸린 문장만 PromptJudge(VLM)에
    위임한다. 규칙 확정분은 VLM을 안 부르므로 과금과 과잉판정을 함께 줄인다
    (Gemini가 진정·탄력을 1호로 과잉판정하던 문제를 규칙이 원천 차단).

    슬롯 구조: PromptJudge를 내부에 합성해 fallback으로 쓴다. StubJudge·PromptJudge는
    안 건드린다. fallback LLM에는 규정·판정기준·사례를 프롬프트에 실어(grounding)
    "규정 보고 판단"하게 한다. 규칙이 이미 확정한 문장은 애초에 LLM에 안 가므로,
    규칙의 결정론적 판정은 grounding과 무관하게 그대로 유지된다.

    case_retriever: 있으면 실사례를 pgvector로 검색해 규정 + '유사 사례'만 넣는다
    (Phase3). 없으면 규정 + cases.md 통째를 넣는다(Phase1 기본). 검색은 판정할 문장에
    따라 달라지므로 context를 judge()마다 만들어 PromptJudge를 그때 구성한다.
    """

    def __init__(self, vlm: VLM, batch_size: int = 12, case_retriever=None):
        self._vlm = vlm
        self._batch_size = batch_size
        self._retriever = case_retriever

    def _context_for(self, remaining: list[dict]) -> str:
        """fallback LLM에 실을 grounding 컨텍스트를 만든다.

        retriever 없으면 Phase1(규정 + cases.md 통째). 있으면 규정 + 검색된 유사 사례.
        """
        if self._retriever is None:
            return build_judgment_context()
        cases_block = self._retriever.context_for(remaining)
        reg = build_regulation_context()
        return f"{reg}\n\n{cases_block}" if cases_block else reg

    def judge(
        self,
        sentences: list[dict],
        region: str,
        ingredients: list[str] | None = None,
    ) -> JudgeResult:
        result = JudgeResult()
        remaining: list[dict] = []  # 규칙 미확정 → VLM에 넘길 문장

        for s in sentences:
            match = match_rule(s["text"])
            if match is None:
                remaining.append(s)
                continue
            if match.outcome == RuleOutcome.legal_allow:
                # 합법 확정. finding도 없고 VLM에도 안 넘긴다(과잉판정 차단).
                continue
            result.findings.append(
                Finding(
                    span=match.span,  # 규칙은 걸린 키워드가 span
                    sentence=s["text"],
                    violation_type=match.violation_type,
                    legal_basis=legal_basis_for(match.violation_type),
                    flag=match.flag,
                    explanation=_rule_explanation(
                        match.outcome, match.span, match.violation_type
                    ),
                    location=_loc(s),
                )
            )

        # 규칙 미확정분만 VLM 위임(2호 성분정합 등은 PromptJudge가 그대로 처리).
        # context는 판정할 문장(remaining)에 따라 달라지므로 여기서 구성한다.
        if remaining:
            prompt_judge = PromptJudge(
                self._vlm, self._batch_size, context=self._context_for(remaining)
            )
            vlm_result = prompt_judge.judge(remaining, region, ingredients)
            result.findings.extend(vlm_result.findings)
            result.unjudged.extend(vlm_result.unjudged)

        return result
