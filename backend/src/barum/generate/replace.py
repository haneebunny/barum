"""위반 문구 → 안전 표현 치환.

조건표(remediation_rules)가 방향을 정하고, LLM이 문장을 다듬는다.

**왜 조건표만으로는 안 되나**(2026-08-20 실측). 조건표는 위반 span 자리에 표현을
그대로 끼워넣는다. 그런데 규칙 경로에서 오는 span은 `치료`·`진정` 같은 **단어 하나**라
(`RagJudge`가 `span=match.span`을 넣는다), 명사구를 그 자리에 넣으면 문장이 깨진다.

    상처를 치료하는 연고    -> 상처를 피부 보호하는 연고     (품사 불일치)
    피부 진정, 케어가 고민   -> 피부 피부 보호, 케어가 고민   (앞 어절과 중복)

게다가 문장에 남은 다른 위반 요소(`상처`·`연고`)를 안 건드려서 의약품 오인이 유지된다.
조건표에 표현을 더 넣어도 안 풀린다. 단어를 명사구로 바꾸는 방식 자체의 한계다.

그래서 LLM을 한 번 거친다(팀장 지시). 다만 **만드는 쪽이 누구든 검증 없이 내보내면
안 된다.** 조건표에서 배운 그대로다. LLM이 낸 문구도 규칙집을 다시 통과시킨다.
"""

import re

from barum.models import Finding, JudgmentFlag, Replacement, ViolationType
from barum.reference.remediation import get_remediation
from barum.reference.rules import RuleOutcome, match_rule

_BASIS = "합법 표기 틀(조건표) 기반 대체 표현"
_BASIS_LLM = "합법 표기 틀(조건표) + 문장 다듬기"

# 대체표현이 실증대상 표현일 때 붙인다. 팩 §3에 실린 표현은 자료가 있으면 쓸 수 있고
# 없으면 못 쓴다. 그 구분을 안 알려주면 사용자는 위반을 벗어난 줄 안다.
_EVIDENCE_NOTE = "이 표현은 실증자료가 있어야 쓸 수 있습니다. 자료가 없으면 검토필요로 남습니다."
# 수치가 들어간 제안은 그 수치의 근거를 요구한다. 수치를 지우는 대신 자료를 받는 쪽이
# 사업자에게 유리하다(2026-08-20 팀장 지시).
_EVIDENCE_NOTE_WITH_NUMBER = (
    "제안에 포함된 수치는 실증자료가 있어야 쓸 수 있습니다. "
    "인체적용시험 결과나 시험성적서를 함께 등록해 주세요."
)
_NUMBER_PATTERN = re.compile(r"\d")


def first_safe(suggestions: list[str]) -> str | None:
    """조건표 후보 중 규칙집에서 위반으로 안 걸리는 첫 번째를 고른다.

    **공개 함수다.** `/remediate` 엔드포인트(리포트 화면 대체표현 카드)도 이걸 쓴다.
    예전엔 그 경로가 조건표 원본 배열을 그대로 내려줘서, 판정기가 검토필요로 잡은
    표현(`피부 진정`)을 대체표현으로 추천하는 모순이 화면에 보였다(2026-08-20 팀장 발견).

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


def _note_for(text: str, original: str, *, source_flag) -> str | None:
    """대체표현에 붙일 고지 문구. 없으면 None.

    **판단 기준은 다시 쓴 결과의 재매칭이 아니라 원본 finding의 flag다**
    (2026-08-20 도도3 리뷰). 처음엔 "다시 쓴 문장을 규칙에 재매칭해서 needs_review면
    고지"로 했는데, 규칙 키워드가 붙여쓰기('콜라겐증가')라 띄어 쓴 원문('콜라겐 밀도
    38% 증가')을 규칙이 못 잡는 경우가 있었다. 그 문장이 검토필요였던 건 규칙이
    아니라 VLM이 잡은 것이었다. 규칙 표현과 안 맞는 원본은 전부 이 구멍에 걸린다.

    판정기가 이미 원본을 검토필요로 봤다면 그 판정을 신뢰한다. 다시 쓴 문장이
    같은 의미를 옮긴 것이라면 그 실증 필요성도 그대로 옮겨간다.

    **한계(2026-08-20 도도3 리뷰로 알고 남김).** LLM이 주장 자체를 빼버려도
    원본이 검토필요였으면 고지가 그대로 붙는다("지속 사용 시 피부 보호에 도움이
    될 수 있습니다"에도 실증 고지가 달린다). 틀린 안내는 아니지만 노이즈다.
    반대(필요한데 안 붙는 것)가 훨씬 나쁘므로 과하게 붙는 쪽을 그대로 둔다.

    **알려진 좁은 구멍(수정은 다음으로 미룸).** 수치 검사는 span과 제안을 비교하는데
    LLM 경로에서 실제로 치환되는 건 문장 전체다. 그래서 위반 원본에서 span엔 숫자가
    없고(예: span='아토피') 문장 다른 자리엔 숫자가 있는 경우('아토피 개선율 87%'),
    다시 쓴 문장이 그 숫자를 지켜도 고지가 안 붙을 수 있다. 위반 원본 + span에 숫자
    없음 + 문장에 숫자 있음이 겹칠 때만 나는 좁은 경우라 이번엔 손대지 않았다.

    수치가 살아 있으면(원문에도 제안에도 숫자가 있으면) 그 수치의 근거를 요구한다.
    **수치를 지우는 대신 자료를 받는다.** 사업자가 실제로 측정한 값일 수 있고,
    실증자료가 있으면 쓸 수 있는 표현이라 임의로 빼면 사업자가 가진 근거를
    우리가 없애는 셈이 된다.
    """
    has_number = _NUMBER_PATTERN.search(original) and _NUMBER_PATTERN.search(text)
    if source_flag is JudgmentFlag.needs_review:
        return _EVIDENCE_NOTE_WITH_NUMBER if has_number else _EVIDENCE_NOTE
    if has_number:
        return _EVIDENCE_NOTE_WITH_NUMBER
    m = match_rule(text)
    if m is not None and m.outcome is RuleOutcome.needs_review:
        return _EVIDENCE_NOTE
    return None


def _accept(text: str) -> bool:
    """대체표현으로 내보내도 되는지. 위반으로 걸리면 안 내보낸다."""
    m = match_rule(text)
    return not (m is not None and m.outcome is RuleOutcome.violation)


_REWRITE_PROMPT = """너는 화장품 광고 문구를 화장품법에 맞게 고쳐 주는 도우미다.

아래 각 항목은 위반으로 지목된 광고 문구다. 항목마다 **대체 문구를 제안할 수 있는지
먼저 판단하고**, 가능할 때만 제안하라.

**제안하지 말아야 할 경우 (can_suggest=false):**
- 효능·효과 주장이 아닌 문구. 판매처·유통 채널·가격·배송·이벤트 안내 등
  (예: "전국 약국 오프라인매장 입점!" → 어디서 파는지에 대한 사실 진술이라
   바꿀 효능 표현이 없다. 억지로 효능 문구를 넣으면 근거 없는 주장을 새로 만드는 것이다)
- 제품명·브랜드명 그 자체 (예: "안나홀츠 안티링클 아이크림")
  제품명은 문구를 바꾸는 게 아니라 제품명 자체를 바꿔야 하는 문제다
- 원문 의미를 지키면서 합법으로 만들 방법이 없는 경우

**제안할 경우 (can_suggest=true):**
- 원문의 의미와 어조를 최대한 지킬 것. 없던 효과를 새로 넣지 마라
- **문장 전체를 자연스러운 한국어로 다시 써라.** 단어만 갈아끼우지 마라
- 참고 표현(reference)이 있으면 방향으로 삼되 그대로 넣을 필요는 없다
- 의학적 효능(치료·재생·항염 등), 기능성 심사 대상 표현(미백·주름개선·자외선차단),
  절대적 표현(완벽·최고·100%)을 새로 넣지 마라
- **원문에 있는 수치는 지우지 마라.** "38% 증가", "4주 사용", "1000ppm" 같은 값은
  사업자가 실제로 측정한 것일 수 있고, 실증자료가 있으면 쓸 수 있다. 임의로 빼면
  사업자가 가진 근거를 우리가 없애는 셈이다. 수치는 그대로 두고 표현만 다듬어라
  (예: "임상 시험 결과 4주 사용 시 콜라겐 밀도 38% 증가" →
        "4주 사용 시 콜라겐 밀도 38% 증가 (인체적용시험 결과)")

항목:
{items}

JSON으로만 답하라. 설명 문장을 덧붙이지 마라.
{{"items": [{{"index": 0, "can_suggest": true, "suggestion": "다시 쓴 문장", "reason": "판단 근거"}}]}}
can_suggest가 false면 suggestion은 넣지 마라."""


def _build_prompt(entries: list[dict]) -> str:
    """LLM에 넘길 배치 프롬프트. 항목마다 원문·위반부분·유형·참고표현을 준다."""
    lines = []
    for e in entries:
        lines.append(
            f"[{e['index']}] 원문: {e['sentence']}\n"
            f"     위반으로 지목된 부분: {e['span']}\n"
            f"     위반 유형: {e['violation_type']}\n"
            f"     참고 표현: {e['reference'] or '(없음)'}"
        )
    return _REWRITE_PROMPT.format(items="\n".join(lines))


def rewrite_one(sentence: str, *, violation_type, span: str | None, rewriter) -> str | None:
    """문구 하나에 대한 대체표현을 LLM으로 다듬어 낸다. 못 만들면 None.

    `/remediate`(리포트 화면 카드)용 단건 경로다. `build_replacements`가 배치로 하는 일을
    한 건만 한다.

    **조건표 문구를 그대로 내면 같은 입력에 늘 같은 답이 나온다**(팀장 지적, 2026-08-20).
    `자극 완화`·`피부 생기 부여`처럼 좁고 뻔한 문구가 반복된다. LLM에 문장을 다시
    쓰게 하되, **나온 결과를 규칙집에 다시 태워 위반이면 버린다**(`_accept`). 만드는
    쪽이 누구든 검증 없이 내보내면 위반을 위반으로 바꿔주게 된다.

    조건표 후보는 버리지 않고 `reference`로 넘겨 방향으로만 쓴다. LLM이 실패하거나
    제안 불가로 판단하면 호출자가 조건표 결과로 폴백한다(응답은 항상 나가게).
    """
    suggestions, _ = get_remediation(sentence=sentence, violation_type=violation_type, span=span)
    entry = {
        "index": 0,
        "sentence": sentence,
        "span": span or sentence,
        "violation_type": _vtype_value(violation_type),
        "reference": first_safe(suggestions) if suggestions else None,
    }
    rewritten, _dropped = _rewrite(rewriter, [entry])
    return rewritten.get(0)


def build_replacements(findings: list[Finding], *, rewriter=None) -> list[Replacement]:
    """위반 finding마다 대체표현을 만든다. 못 만들면 그 finding은 건너뛴다.

    `rewriter`(VLM 프로토콜)를 주면 조건표 후보를 방향으로 삼아 LLM이 문장을 다듬는다.
    안 주면 조건표 결과를 그대로 쓴다(하위호환·오프라인 테스트용).

    **제안할 수 없으면 제안하지 않는다**(2026-08-20 팀장 지시). 유통 채널 안내처럼
    바꿀 효능 표현이 없는 문구에 억지로 대체표현을 붙이면, 근거 없는 효과 주장을
    새로 넣으라고 권하는 셈이 된다. 실제로 5호 fallback `우수한 효과`가 약국 입점
    안내 3건에 그대로 붙고 있었다.
    """
    entries = []
    for i, f in enumerate(findings):
        suggestions, _ = get_remediation(
            sentence=f.sentence, violation_type=f.violation_type, span=f.span
        )
        entries.append(
            {
                "index": i,
                "finding": f,
                "sentence": f.sentence,
                "span": f.span or f.sentence,
                "violation_type": _vtype_value(f.violation_type),
                "reference": first_safe(suggestions) if suggestions else None,
            }
        )

    rewritten: dict[int, str] = {}
    dropped: set[int] = set()
    if rewriter is not None and entries:
        rewritten, dropped = _rewrite(rewriter, entries)

    reps: list[Replacement] = []
    for e in entries:
        if e["index"] in dropped:
            continue  # LLM이 "대체할 수 없다"고 판단한 문구
        text = rewritten.get(e["index"]) or e["reference"]
        if text is None:
            print(f"[replace] 안전한 대체표현 없음, 치환 건너뜀: span={e['span']!r}")
            continue
        reps.append(
            Replacement(
                # **치환 단위는 경로마다 다르다.** LLM은 문장 전체를 다시 쓰므로
                # 갈아끼울 대상도 문장이어야 한다. span(단어 하나)으로 두면
                # 그 자리에 문장이 통째로 박혀 원문이 깨진다(2026-08-20 도도3 리뷰).
                #   '피부 깊숙이, 세포재생의 시작'
                #     -> '피부 깊숙이, 세포<문장 전체>의 시작'
                # 조건표 경로는 단어 대 단어라 span 그대로 둔다.
                original=e["sentence"] if e["index"] in rewritten else e["span"],
                replaced=text,
                violation_type=e["finding"].violation_type,
                basis=_BASIS_LLM if e["index"] in rewritten else _BASIS,
                note=_note_for(text, e["span"], source_flag=e["finding"].flag),
            )
        )
    return reps


def _vtype_value(vtype) -> str:
    return vtype.value if isinstance(vtype, ViolationType) else str(vtype)


def _rewrite(rewriter, entries: list[dict]) -> tuple[dict[int, str], set[int]]:
    """LLM에 배치로 한 번 물어 (다듬은 문구, 제안 불가 인덱스)를 낸다.

    **실패하면 조건표 결과로 돌아간다.** 과금 호출이라 재시도하지 않는다(CLAUDE.md §E).
    LLM이 낸 문구는 규칙집에 다시 태워 위반이면 버린다. 만드는 쪽이 누구든
    검증 없이 내보내면 위반을 위반으로 바꿔주게 된다.
    """
    try:
        res = rewriter.generate_json(_build_prompt(entries), [])
    except Exception as exc:  # 과금 호출이라 재시도 없이 조건표로 폴백
        print(f"[replace] 문장 다듬기 실패, 조건표 결과로 진행: {exc}")
        return {}, set()

    rewritten: dict[int, str] = {}
    dropped: set[int] = set()
    for item in (res or {}).get("items", []):
        idx = item.get("index")
        if not isinstance(idx, int):
            continue
        if not item.get("can_suggest"):
            dropped.add(idx)
            continue
        text = (item.get("suggestion") or "").strip()
        if not text:
            dropped.add(idx)
            continue
        if not _accept(text):
            # LLM이 위반 문구를 냈다. 조건표로 되돌리지 않고 제안 자체를 뺀다.
            print(f"[replace] 다듬은 문구가 위반으로 걸림, 제안 제외: {text!r}")
            dropped.add(idx)
            continue
        rewritten[idx] = text
    return rewritten, dropped


def apply_replacements(content: str, reps: list[Replacement]) -> str:
    """원문에서 각 위반 표현(original)을 안전표현(replaced)으로 치환한 텍스트를 낸다."""
    for r in reps:
        content = content.replace(r.original, r.replaced)
    return content
