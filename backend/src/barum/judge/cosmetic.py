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
from barum.reference.ingredients import (
    check_amount_threshold,
    find_amount_for,
    infer_category,
    match_ingredient,
)
from barum.reference.mapping import legal_basis_for, legal_basis_text_for
from barum.reference.rules import (
    RuleOutcome,
    has_exaggeration,
    has_functional_claim,
    match_rule,
)
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
        ingredient_amounts: list[tuple[str, str]] | None = None,
    ) -> JudgeResult:
        """문장 리스트를 받아 위반 findings + 미판정 목록을 낸다.

        입력 문장 dict: {order:int, tile:str|None, text:str} (파이프라인이 만든 형태).
        합법·대상외는 finding을 만들지 않는다(근거 개수 = 위반 건수).
        ingredients: 선택적 전성분 목록. 있으면 2호(기능성오인) 판정에 성분
        정합(고시원료 존재 여부) 대조를 덧붙인다.
        ingredient_amounts: 선택적 (성분명, 함량) 목록. 있으면 성분 정합에 함량기준
        충족 여부까지 더해 판정을 더 정확히 가른다(이름만 있고 함량이 없거나
        미달이면 위반 쪽으로, 이름+함량 다 맞아도 등록 여부는 확인 못 해 검토필요 유지).
        """
        ...


# 위반유형별 근거 조항은 reference.mapping이 단일 출처다(레퍼런스 팩과 드리프트 방지).


def _loc(s: dict) -> Location:
    """문장 dict → Location. 밴드/bbox 좌표·원본 크기는 이미지 입력에만 실린다.

    _ocr_image가 문장 dict에 넣어 준 x_start/x_end/y_start/y_end/source_h/source_w를
    그대로 옮긴다. 텍스트 입력엔 이 키들이 없어 None으로 남는다(하이라이트 스킵).
    """
    return Location(
        tile=s.get("tile"),
        order=s.get("order", 0),
        x_start=s.get("x_start"),
        x_end=s.get("x_end"),
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
        ingredient_amounts: list[tuple[str, str]] | None = None,
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
                            legal_basis_text=legal_basis_text_for(vtype),
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


def _parse_flag(raw: object) -> JudgmentFlag:
    """모델이 답한 확정도를 JudgmentFlag로 바꾼다. 못 읽으면 위반(recall 우선).

    누락·오타·구버전 응답(flag 필드 자체가 없음)은 전부 위반으로 떨어뜨린다.
    검토필요로 잘못 내리면 위험을 낮게 보여주는 미탐 쪽 실수가 되므로, 모르면
    무거운 쪽으로 둔다.
    """
    if not isinstance(raw, str):
        return JudgmentFlag.violation
    return (
        JudgmentFlag.needs_review
        if raw.strip() == JudgmentFlag.needs_review.value
        else JudgmentFlag.violation
    )

# score_eval.py와 공유하는 판정 프롬프트. 여기가 원본이고 score_eval이 import한다.
JUDGE_PROMPT = """너는 한국 화장품 광고 문구가 화장품법 표시·광고 규정을 위반하는지 판정한다.
아래 문장 각각에 라벨 하나와 짧은 근거를 매겨라.

라벨(정확히 이 중 하나만):
- 합법 : 일반 보습·사용감·제형 설명 등 위반 소지 없음
- 1호_의약품오인 : 질병·치료·재생·염증 등 의학적/의약품 같은 효능 암시
- 2호_기능성오인 : 미백·주름개선·자외선차단 기능성 효능을 주장
- 5호_거짓과장기만 : 근거 없는 수치·최상급·비교우위·후기 단정·경쟁사 비방
- 대상외 : 광고 문구가 아님(성분명 나열, 거래·배송 안내, 인증서 표시, 단순 제품정보·브랜드명)

확정도(label이 1호·2호·5호일 때만. 합법·대상외면 "위반"으로 두고 무시된다):
- 위반 : 근거에 비추어 위반이 분명하다.
- 검토필요 : 위반일 수 있으나 단정하려면 확인이 필요하다. 아래에 하나라도 해당하면 이쪽이다.
  · 근거 문서 §3 "실증대상" 목록에 해당한다(실증자료가 있으면 쓸 수 있는 표현).
  · 기능성(미백·주름개선·자외선차단) 표방이라 심사·보고 여부를 확인해야 한다.
  · 객관적 근거를 제시했는지에 따라 합법·위반이 갈리는 표현이다(최상급·수치 등).
  근거 문서가 "실증 자료 확인 필요"·"검토필요"라고 안내하는 표현은 위반으로 단정하지 마라.

규칙:
- 한 문장에 여러 개 해당하면 가장 무거운 것 하나. 우선순위 1호 > 2호 > 5호 > 합법.
- 미탐(위반을 합법으로 놓침)이 제일 나쁘다. **애매하면 합법이 아니라, 유형을 붙이고
  확정도를 "검토필요"로 하라.** 합법으로 흘리는 것이 가장 나쁜 실수다.
- label에 "검토필요"를 쓰지 마라. 검토필요는 label이 아니라 flag다.

문장:
{items}

JSON으로만 답하라: {{"results": [{{"n": 1, "label": "...", "flag": "위반|검토필요", "reason": "..."}}]}}"""


def _functional_evidence(
    sentence: str,
    ingredients: list[str] | None,
    ingredient_amounts: list[tuple[str, str]] | None = None,
) -> tuple[str | None, JudgmentFlag | None]:
    """2호(기능성오인) finding의 근거를 성분표로 확인해 (안내문, 플래그)를 낸다.

    VLM은 '미백/주름/자외선차단을 표방했다'까지만 판정하고, 실제 전성분에 그
    기능의 고시원료가 있는지, 함량이 기준을 채우는지는 모른다. 이건 정확 조회
    문제라 여기서 결정론적으로 확인한다(functional_ingredients.md "판정에 쓰는
    법"의 코드화).

    **플래그가 None이면 "합법 확정, finding을 만들지 마라"는 뜻이다**(호출부가 건너뛴다).

    - 전성분 미입력/카테고리 불명 → 대조 근거 자체가 없다 → 검토필요.
    - 고시원료 없음 → 표방한 기능의 근거가 없다는 확증 → 위반.
    - 고시원료 있음 + 함량 미입력 → 이름만으론 기준충족을 못 봄 → 검토필요.
    - 고시원료 있음 + 함량 기준 미달 → 정식 심사 대상인데 안 밟았다는 근거 → 위반.
    - 고시원료 있음 + 함량 기준 충족 → **합법(None)**.

    마지막 분기는 2026-08-20에 검토필요에서 합법으로 바꿨다(팀장 결정). 그 전 논리는
    "이름+함량이 맞아도 실제 심사·보고 등록 여부를 모르니 합법까진 못 간다"였는데,
    그 기준이면 **완전히 정상적인 기능성화장품 광고도 영원히 검토필요를 벗어날 수 없다**.
    등록 여부는 우리 입력에 애초에 없는 정보라 아무리 갖춰도 해소가 안 되기 때문이다.
    실제로 식약처 인정문구("피부의 미백에 도움을 준다.", 고시 제2023-61호 별표4)까지
    플래그가 붙고 있었다(2026-08-20 실측, 3회 반복 편차 없음).
    전성분·함량이라는 확인 가능한 근거가 다 맞으면 합법으로 보고, 확인이 안 되면
    검토필요로 남긴다 — 판단 기준을 "우리가 볼 수 있는 것"에 맞춘 것이다.
    (상세: docs/result/2026-08-20_판정로직_고도화_로그.md ⑦·⑧)
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

    기준 = row.get("기준 함량") or row.get("최대 함량", "")
    given_amount = find_amount_for(row, ingredient_amounts or [])
    if given_amount is None:
        note = f"(전성분 대조: {row['성분명']} 확인됨, 기준 {기준}, 함량 미입력이라 기준충족 여부 확인 못 함. 등록 여부도 불명이라 단정 못 함)"
        return note, JudgmentFlag.needs_review
    if not check_amount_threshold(category, row, given_amount):
        note = f"(전성분 대조: {row['성분명']} 확인됐으나 함량 {given_amount}이 고시 기준({기준}) 미달, 정식 심사 대상인데 안 밟은 것으로 보여 위반 소지 큼)"
        return note, JudgmentFlag.violation
    # 확인 가능한 근거(고시원료 + 기준함량)가 다 맞았다 → 합법. 단, 같은 문장에 과장
    # 표현이 섞여 있으면 강등하지 않는다. 한 문장에 라벨이 하나뿐이라 여기서 합법으로
    # 내리면 그 과장이 통째로 빠지기 때문이다 — "단 3일만에 완벽하게 미백되는 기적의
    # 크림"이 성분만 맞으면 미플래그로 나오던 것을 실측으로 확인했다(3회 반복, 편차
    # 없음). `approved_efficacy_statements.md` 4항도 "인정문구를 벗어난 과장 표현이
    # 붙으면 별개로 T5 판정 가능"이라 성분 정합과 과장은 따로 봐야 한다.
    if has_exaggeration(sentence):
        note = (
            f"(전성분 대조: {row['성분명']} {given_amount} 확인됨, 고시 기준({기준}) 충족. "
            f"다만 같은 문장에 절대적·과장 표현이 있어 그 부분은 별도 확인 필요)"
        )
        return note, JudgmentFlag.needs_review
    return None, None


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
        ingredient_amounts: list[tuple[str, str]] | None = None,
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
                # 확정도는 모델이 직접 답한다(2026-08-19). 예전엔 1호·5호를 무조건
                # 위반으로 고정했는데, 근거 문서는 §3 실증대상을 "검토필요, 위반 단정
                # 금지"로 안내하는 반면 답변 라벨엔 그 선택지가 없어 모델이 합법(미탐)
                # 아니면 위반(과잉)으로 몰렸다. 파싱 실패·누락은 위반으로 둔다(recall 우선).
                flag = _parse_flag(item.get("flag"))
                if vtype == ViolationType.type_2_functional_misperception:
                    # 2호는 성분 정합이라는 실제 근거 대조 수단이 있다. 모델의 자기
                    # 판단보다 대조 결과를 우선한다.
                    note, flag = _functional_evidence(s["text"], ingredients, ingredient_amounts)
                    if flag is None:
                        # 고시원료·기준함량이 다 맞음 = 합법 확정. finding을 안 만든다.
                        continue
                    if note:
                        explanation = f"{explanation} {note}"
                result.findings.append(
                    Finding(
                        span=s["text"],  # 이 프롬프트는 문장 단위 라벨 = span은 문장 전체
                        sentence=s["text"],
                        violation_type=vtype,
                        legal_basis=legal_basis_for(vtype),
                        legal_basis_text=legal_basis_text_for(vtype),
                        flag=flag,
                        explanation=explanation,
                        location=_loc(s),
                    )
                )
        return result


# ── 1차 필터: 효능/효과 주장 여부 사전분류 ─────────────────────────────────

# 질문을 "효능 주장인가"에서 "판정 대상인가"로 넓혔다(2026-08-19, 팀장 승인).
# 약국입점·니들표기·순위표현 같은 위반은 애초에 효능 주장이 아니라, 옛 질문은 위반
# 유형 절반에 안 맞았다. 실측으로 규칙 위반확정 문장의 43%(누적 7건 중 3건)를
# "효능주장 아님"으로 버리고 있었다. 그 문장들이 안전했던 건 규칙이 먼저 잡아 여기
# 안 왔기 때문이고, 규칙이 못 잡는 같은 성격 문장은 조용히 사라졌다.
#
# A/B 실측(각 3회, 정답셋 40문장): 판정기가 봐야 할 문장 통과 15.0 -> 18.7/20
# (범위 14~16 -> 18~19, 겹치지 않음). 걸러야 할 대상외 차단은 18.7 -> 18.3으로
# 사실상 불변(범위 17~20 vs 17~19)이라 필터의 비용 절감 가치는 유지된다.
# 질문을 넓히면 미탐은 줄지만 다 통과해서 필터가 무의미해질 수 있어 양방향으로 쟀다.
#
# 2026-08-20 2차 정비: 비대상 정의가 팩이 갈라 놓은 것을 뭉뚱그리고 있었다.
# 팩 §1-84는 기능성 고시원료가 언급되면 검토필요(심사·함량 확인)로, §1-91은 성분
# 함량 표시를 광고로 본다. §1-90(2025.1.21 지침 개정)은 광고 제목명도 판단 대상으로
# 본다. 그런데 프롬프트는 "성분명 나열"·"브랜드명 단독 표기" 두 줄로 이걸 다 버렸다.
# 실측(홀드아웃 119문장, 각 3회. `scripts/prescreen_ab.py`):
#   판정 대상 문장 통과  51~55 -> 62/65  (범위 안 겹침)
#   비대상 차단        21~22 -> 22~23/24 (겹침, 차단력은 안 잃었다)
#   합법 통과(비용)      20 -> 18~19/30  (오히려 덜 통과)
# 판정기로 넘어가는 문장은 74~78 -> 81~83건으로 늘고, 늘어난 몫은 전부 판정 대상
# 문장이다. 성분 갈래만 고친 안(B)은 통과 57~60에 그쳐 제품명 갈래까지 넣은 안을
# 채택했다(B는 `prescreen_ab.py`에 기각안으로 남아 있다).
#
# 2026-08-20 3차: 천연·유기농 축 추가(변형 D). 팩 §1 T5(안내서 부적합 제품의 '천연'·
# '유기농')와 §3(ISO 천연·유기농 지수)이 근거 — 적합 여부를 우리가 모르니 확인이 필요하고,
# 그러면 판정기가 봐야 한다. 실측(홀드아웃 119문장 각 3회):
#   판정 대상 통과  62 -> 63~65/65  (범위 안 겹침)
#   비대상 차단     22~23 -> 21~22/24 (겹침, 유의한 악화 미입증)
# 대가가 하나 있다. 탐침셋에서 "천연가죽 파우치를 사은품으로 드립니다"가 2/3 통과한다.
# 효능과 무관한 '천연' 언급까지 판정기로 넘어간다는 뜻이다. 판정기가 미플래그를 내면
# 최종 결과는 같고 비용만 조금 는다. 걸리면 안 되는 문장을 같이 재서 확인한 값이다.
PRESCREEN_PROMPT = """아래 문장 각각이 화장품법 표시·광고 판정 대상인지 판단하라.

판정 대상(YES) = 아래 중 하나라도 해당:
- 피부·모발·체형에 대한 변화·개선·치료·예방을 표방하는 문구
- 의약품·의료기기·시술을 연상시키는 표현(약국·병원·니들·시술기기 등)
- 근거 없는 수치·최상급·순위·비교우위 주장(N배, 1위, 최고 등)
- 성분에 함량·비율 수치가 붙은 문구(N%, Nppm, IU, 고함량, 원액 N% 등)
- 기능성 고시원료를 내세운 문구(나이아신아마이드·알부틴·닥나무추출물·아데노신·
  레티놀·에칠헥실트리아존 등 미백·주름개선·자외선차단 고시원료)
- 성분과 효과를 연결한 문구(예: "OO추출물이 진정에 도움")
- 천연·유기농·오가닉을 내세운 문구(안내서 적합 여부를 확인해야 한다)
- 제품명·상품명·제목에 효능 표현이 들어간 문구(예: "OO 안티링클 아이크림", "OO 화이트닝 크림")
- 그 밖에 소비자를 오인시킬 소지가 있는 광고 문구

비대상(NO) = 함량 수치도 효능 연결도 없는 단순 성분 목록(전성분·표시성분 표기), 용량·가격, 거래·배송 안내, 목차·번호·구획 표시,
단순 사용법 설명, 효능 표현이 없는 브랜드명·제품명 단독 표기.

**성분 목록이어도 기능성 고시원료가 들어 있거나 함량 수치가 붙으면 YES다.**
**효능 주장이 아니어도 위 다른 항목에 해당하면 YES다.** 애매하면 YES(미탐 방지).

문장:
{items}

JSON으로만 답하라: {{"results": [{{"n": 1, "claim": true/false}}]}}
claim = true(판정 대상이다), false(아니다)."""


# ── RagJudge (규칙집 우선 + 1차 필터 + VLM fallback) ─────────────────────


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
        # 직전 judge()에서 1차 필터가 버린 문장. 판정기가 못 본 문장이라 미탐이
        # 여기서 샐 수 있어 관측용으로 남긴다(판정 동작에는 안 쓴다).
        self.last_dropped: list[dict] = []

    def _context_for(self, remaining: list[dict]) -> str:
        """fallback LLM에 실을 grounding 컨텍스트를 만든다.

        retriever 없으면 Phase1(규정 + cases.md 통째). 있으면 규정 + 검색된 유사 사례.
        """
        if self._retriever is None:
            return build_judgment_context()
        cases_block = self._retriever.context_for(remaining)
        reg = build_regulation_context()
        return f"{reg}\n\n{cases_block}" if cases_block else reg

    def _prescreen(self, sentences: list[dict]) -> list[dict]:
        """1차 필터: 효능/효과 주장인 문장만 골라낸다 (RAG 없는 싼 VLM 호출).

        VLM이 "이 문장이 효능/효과를 주장하는가?"만 이진 분류한다.
        NO(비효능)인 문장은 대상외로 버리고, YES인 문장만 리턴한다.
        실패 시 안전하게 전부 YES로 간주한다(미탐 방지).

        **버린 문장은 경고로 남긴다(2026-08-19).** 여기서 버려지면 판정기가 그 문장을
        볼 기회 자체가 없어지는데, 지금까지 무엇이 버려졌는지 아무 기록이 없었다.
        옛 질문("효능 주장인가")은 규칙이 위반으로 확정한 문장의 43%를 "아님"으로 버렸다.
        약국 입점·니들 표기·순위 표현 같은 위반은 애초에 효능 주장이 아니어서다.
        2026-08-19에 질문을 "판정 대상인가"로 넓혀 그 갭을 메웠다(PRESCREEN_PROMPT
        주석의 A/B 실측 참고). 그래도 여기서 버려지면 판정기가 못 보는 건 같으므로
        기록은 계속 남긴다.

        판정 동작은 안 바꾼다(veto 아님, 버리는 기준 그대로). 관측만 붙인다.
        버린 목록은 `last_dropped`로도 남겨 오프라인 분석에서 집계할 수 있게 한다.
        """
        claims: list[dict] = []
        dropped: list[dict] = []
        for start in range(0, len(sentences), self._batch_size):
            batch = sentences[start : start + self._batch_size]
            numbered = "\n".join(
                f"{start + j}. {s['text']}" for j, s in enumerate(batch)
            )
            try:
                res = self._vlm.generate_json(
                    PRESCREEN_PROMPT.format(items=numbered), []
                )
                raw = res.get("results", [])
            except Exception as e:
                print(
                    f"    [prescreen skip] 배치 {start}~{start + len(batch) - 1}: "
                    f"{type(e).__name__}: {e}"
                )
                claims.extend(batch)
                continue

            by_n: dict[int, dict] = {}
            for item in raw:
                try:
                    by_n[int(item["n"])] = item
                except (KeyError, ValueError, TypeError):
                    continue

            for j, s in enumerate(batch):
                item = by_n.get(start + j)
                if item is None and len(raw) == len(batch):
                    item = raw[j]
                is_claim = (item or {}).get("claim")
                if is_claim is not False:
                    claims.append(s)
                else:
                    dropped.append(s)

        self.last_dropped = dropped
        if dropped:
            # 판정기가 못 본 문장이다. 미탐이 여기서 새면 흔적이 이 로그뿐이다.
            print(f"    [prescreen drop] 판정 대상 아님으로 제외 {len(dropped)}건")
            for s in dropped:
                print(f"      - {s['text'][:60]}")

        return claims

    def judge(
        self,
        sentences: list[dict],
        region: str,
        ingredients: list[str] | None = None,
        ingredient_amounts: list[tuple[str, str]] | None = None,
    ) -> JudgeResult:
        result = JudgeResult()
        remaining: list[dict] = []  # 규칙 미확정 → 1차 필터로 넘길 문장

        for s in sentences:
            match = match_rule(s["text"])
            if match is None:
                remaining.append(s)
                continue
            if match.outcome in (RuleOutcome.legal_allow, RuleOutcome.out_of_scope):
                # 합법 확정 또는 대상외. finding도 없고 VLM에도 안 넘긴다.
                continue
            result.findings.append(
                Finding(
                    span=match.span,
                    sentence=s["text"],
                    violation_type=match.violation_type,
                    legal_basis=legal_basis_for(match.violation_type),
                    legal_basis_text=legal_basis_text_for(match.violation_type),
                    flag=match.flag,
                    explanation=_rule_explanation(
                        match.outcome, match.span, match.violation_type
                    ),
                    location=_loc(s),
                )
            )
            # 규칙이 실증대상(검토필요)으로 확정했는데 같은 문장에 2호 표방까지
            # 섞여 있으면 VLM에도 함께 넘긴다. 안 넘기면 "진정에 도움을 주는 미백
            # 크림"이 needs_review(진정, 1호)에서 끝나 미백 클레임이 평가될 기회를
            # 잃는다. 유형이 1호로만 보고돼 legal_basis가 어긋나고, 2호 성분 대조
            # (_functional_evidence)도 안 돈다(전성분에 고시원료가 없으면 위반이어야
            # 하는데 검토필요로 고정된다).
            #
            # 규칙 finding을 빼고 VLM에 넘기는 방식은 안 쓴다. VLM이 합법이라고 하면
            # 통째로 놓치기 때문이다. 규칙 판정은 그대로 두고 VLM 판정을 더한다
            # (한 문장에 실제로 두 갈래 위반이 있으니 둘 다 보고하는 게 맞다).
            if match.outcome == RuleOutcome.needs_review and has_functional_claim(
                s["text"]
            ):
                remaining.append(s)

        if remaining:
            # 1차 필터: 효능/효과 주장인 문장만 골라낸다(RAG 없는 싼 VLM 호출).
            efficacy_claims = self._prescreen(remaining)

            if efficacy_claims:
                # 2차 판정: 효능 주장인 것만 RAG + VLM으로 판정.
                prompt_judge = PromptJudge(
                    self._vlm,
                    self._batch_size,
                    context=self._context_for(efficacy_claims),
                )
                vlm_result = prompt_judge.judge(
                    efficacy_claims, region, ingredients, ingredient_amounts
                )
                result.findings.extend(vlm_result.findings)
                result.unjudged.extend(vlm_result.unjudged)

        return result
