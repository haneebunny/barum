"""RagJudge 규칙집 대조.

`judge_rules.json`(손 큐레이션)의 키워드와 광고 문장을 정확 조회로 대조해
판정 3갈래(위반/검토필요/합법확정) 중 하나를 낸다. 의미검색이 아니라 정규화
문자열 포함 검사라 임베딩 없이 충분하다(ingredients.py와 같은 방식).

규칙은 §3(규정 리서치로 검증된 1호 경계표현)을 encode한다. 규칙에 안 걸리는
문장은 여기서 판단하지 않고 None을 돌려 VLM(PromptJudge)에 위임한다.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

from barum.models import JudgmentFlag, ViolationType

_DATA_PATH = Path(__file__).resolve().parent / "data" / "judge_rules.json"
_SYNONYMS_PATH = Path(__file__).resolve().parent / "data" / "synonyms.json"


class RuleOutcome(Enum):
    """규칙 매칭의 네 갈래. 미매칭은 match_rule이 None을 낸다(VLM 위임)."""

    violation = "violation"  # 위반 확정
    needs_review = "needs_review"  # 실증대상 등 근거 약함 → 검토필요
    legal_allow = "legal_allow"  # 합법 확정(finding 없음, VLM에도 안 넘김)
    out_of_scope = "out_of_scope"  # 대상외(광고 문구 아님, finding 없음, VLM에도 안 넘김)


@dataclass
class RuleMatch:
    """규칙 매칭 결과.

    span = 걸린 키워드(문장 일부가 아니라 규칙 문구 자체). legal_allow면
    violation_type·flag는 없다(위반이 아니므로).
    """

    outcome: RuleOutcome
    span: str
    violation_type: ViolationType | None
    flag: JudgmentFlag | None


def _normalize(text: str) -> str:
    """대조용 정규화 — 공백·붙임표·가운뎃점을 지운다(ingredients와 동일)."""
    return re.sub(r"[\s·\-]", "", text)


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_synonyms() -> dict[str, list[str]]:
    """동의어 사전을 그대로 캐시(대표어 → 변형 목록)."""
    return json.loads(_SYNONYMS_PATH.read_text(encoding="utf-8"))["synonyms"]


@lru_cache(maxsize=1)
def _load_reverse_synonyms() -> dict[str, tuple[str, str]]:
    """동의어 사전을 역인덱스로 만든다: 정규화된 변형 → (대표어, 원본 변형어).

    원본 변형어를 같이 들고 있는 이유는 문맥예외를 변형 단위로 걸 수 있어야
    해서다(예: "힐링"). 대표어("치료") 단위로만 걸면, "힐링"에 준 예외가
    "치료" 직접 매칭까지 같이 느슨해진다(안전장치가 새는 경로가 된다).
    """
    reverse: dict[str, tuple[str, str]] = {}
    for canonical, variants in _load_synonyms().items():
        for v in variants:
            reverse[_normalize(v)] = (canonical, v)
    return reverse


_ASCII_WORD = re.compile(r"^[A-Za-z]+$")

# 근거 없는 비교수치("시중 대비 3배") — 시행규칙 별표5 "바"항(경쟁상품 비교는 대상·기준이
# 분명하고 객관적으로 확인 가능한 사항만 허용). 배수 표현은 숫자가 가변이라 키워드 나열이
# 아니라 정규식으로 잡는다(prohibited_expressions.md:59, cases.md:32 근거).
_MULTIPLIER_RE = re.compile(r"\d+(\.\d+)?배")
_COMPARISON_MARKERS = ("대비", "보다")


# 정밀 침투·흡수 메커니즘 주장. **팩이 "판정 기준은 단어가 아니라 메커니즘"이라고
# 못박아서**(prohibited_expressions.md:41) 단어 하나로 잡지 않고 동시출현으로 본다.
# 근거: type_1_drug_misperception.md:18이 "진피층·근막에 직접 전달 등 생리구조 영향
# 표현"을 1호로 들고, cases.md에 실제 적발 사례가 셋 있다(121·50·69행).
#
# **맨 "침투"·"흡수"를 키워드로 넣는 안은 실측으로 기각했다**(2026-08-23, 963셋):
# 매칭 17건 중 12건이 오탐이었다(합법 9·대상외 3). "면도로 생긴 상처를 통해 세균이
# 침투"처럼 제품 효능 주장이 아닌 용례가 많다. 깊이 표지가 같이 있어야 "정밀하게
# 파고든다"는 주장이 된다. 동시출현 조건은 963셋에서 오탐 0건이다.
_DEPTH_MARKERS = ("깊숙", "깊은", "깊이", "진피", "표피", "속까지", "층까지", "세포속")
_PENETRATION_MARKERS = ("침투", "흡수", "전달", "도달")


def _is_penetration_mechanism_claim(norm: str) -> bool:
    """깊이 표지와 침투·흡수 표현이 같은 문장에 있으면 메커니즘 주장으로 본다."""
    if not any(d in norm for d in _DEPTH_MARKERS):
        return False
    return any(m in norm for m in _PENETRATION_MARKERS)


def _is_unsubstantiated_comparison(norm: str) -> bool:
    """비교표지(대비/보다)와 배수(N배)가 같은 문장에 있으면 근거 없는 비교수치로 본다."""
    if not _MULTIPLIER_RE.search(norm):
        return False
    return any(marker in norm for marker in _COMPARISON_MARKERS)


# 근거 없는 검증방법 주장("임상시험으로 철저히 검증받은") — type_5_deception.md #38 근거
# (cases.md #38 실사례로 인용 재검증됨, 2026-08-19). 의도적으로 좁게: "효과로 증명합니다"
# 처럼 구체적 검증방법 언급 없는 막연한 자기주장형은 이 규칙 대상이 아니다(하니 재확인).
_VERIFICATION_METHOD_TERMS = ("임상시험", "인체적용시험", "인체외시험", "임상실험", "시험분석")
_VERIFICATION_CLAIM_MARKERS = ("검증", "입증")


def _is_unsubstantiated_verification_claim(norm: str) -> bool:
    """구체적 검증방법(임상시험 등)과 '검증/입증' 단정이 같이 있으면 근거 없는 주장으로 본다."""
    if not any(t in norm for t in _VERIFICATION_METHOD_TERMS):
        return False
    return any(m in norm for m in _VERIFICATION_CLAIM_MARKERS)


# 배타적 순위 최상급(NO.1·No.1·#1·1위) — 시행규칙 별표5 "바"항 근거, 비교광고와 같은 갈래.
# "#"·숫자가 섞여 `_keyword_present`의 영단어 우측경계 보호가 안 먹히는 키워드라(순수
# 영단어가 아님) 정규식으로 앞뒤 숫자 경계를 직접 본다. "11위"·"#123" 같은 상품코드·순위
# 표기에 부분일치로 안 걸리게 — "Pin"이 "Pintox"에 걸렸던 사고와 같은 클래스라 처음부터
# 경계를 둔다(2026-08-19).
_RANK_SUPERLATIVE_RE = re.compile(r"(?<!\d)(?:no\.?1|#1|1위)(?!\d)", re.IGNORECASE)


def _is_exclusive_rank_claim(norm: str) -> bool:
    """NO.1/No.1/#1/1위처럼 배타적 순위를 내세우는 표현인지 본다(숫자 경계 보호)."""
    return _RANK_SUPERLATIVE_RE.search(norm) is not None


def _keyword_present(kw: str, norm: str) -> bool:
    """정규화된 문장에 키워드가 있는지 본다.

    순수 영단어 키워드는 뒤에 다른 라틴 알파벳이 바로 붙으면 매칭하지 않는다
    (오른쪽 경계만 본다). "Pin"이 브랜드명 "Pintox"·색상명 "Pink" 안에 부분
    일치로 걸려 대상외 상품 4건을 오탐 내던 문제 때문이다(2026-08-18 실측,
    51번 미세침 표현 잡으려고 추가한 키워드가 부작용을 냄).

    한국어 키워드는 조사가 자연히 붙어("니들이") 오른쪽 경계를 볼 수 없으므로
    기존 부분일치 그대로 둔다.
    """
    kw_norm = _normalize(kw)
    if _ASCII_WORD.match(kw_norm):
        return re.search(re.escape(kw_norm) + r"(?![A-Za-z])", norm) is not None
    return kw_norm in norm


def _match_conditional_violation(norm: str, rules: dict) -> RuleMatch | None:
    """단어 자체로는 위반이 아니고, 맥락어가 같이 있을 때만 위반인 키워드를 본다.

    `context_exceptions`(기본은 위반, 예외 조건이면 빼줌)와 반대 방향이다. 여기는
    기본이 통과고, `requires_any_context` 중 하나라도 같이 있어야 위반으로 올린다.

    "리들"이 이 갈래다. 상표 등록·장기 미제재된 회피표기라 단어 자체로는 위반이
    아니지만("리들샷 앰플"), 침투·흡수 같은 메커니즘 서술이 붙으면 니들류와 같은
    효과를 표방하는 것이라 위반이다("리들샷으로 유효성분이 깊숙이 침투").
    """
    for kw, spec in rules.get("conditional_violation", {}).items():
        if not _keyword_present(kw, norm):
            continue
        contexts = spec.get("requires_any_context", [])
        if not any(_normalize(c) in norm for c in contexts):
            continue
        vtype = ViolationType(spec["violation_type"])
        return RuleMatch(RuleOutcome.violation, kw, vtype, JudgmentFlag.violation)
    return None


def _has_context_exception(norm: str, kw: str, rules: dict) -> bool:
    """kw의 위반 매칭이 `context_exceptions`에 걸린 문맥 예외인지 본다.

    두 극성을 지원한다(2026-08-18, 힐링 사례로 확장).

    **기본(엑소좀 패턴, polarity 생략)**: 단어 자체가 원래 위반이다. "식물 엑소좀"·
    "우유 엑소좀"처럼 원료 대분류 단어가 붙으면 예외(단, unsafe_markers가 같이
    있으면 예외를 취소하고 위반을 유지한다). adjacency="anywhere"가 아니면
    safe_qualifier가 kw 바로 앞에 붙어야만 예외로 친다(기존 동작 그대로).

    **safe_by_default(힐링 패턴)**: 단어 자체는 흔히 무해하게 쓰인다("힐링의 섬").
    unsafe_markers(예: "피부")가 같이 있을 때만 위반으로 올린다. 반대 극성이라
    safe_qualifiers·adjacency는 안 본다.

    (자동 합법 확정이 아니라 규칙 매칭만 건너뛰고 VLM에 위임 — VLM은 이미 RAG
    근거 문서에서 이 예외를 알고 있다, prohibited_expressions.md 참고.)
    """
    exc = rules.get("context_exceptions", {}).get(kw)
    if not exc:
        return False

    if exc.get("polarity") == "safe_by_default":
        return not any(_normalize(u) in norm for u in exc.get("unsafe_markers", []))

    if any(_normalize(u) in norm for u in exc.get("unsafe_markers", [])):
        return False
    if exc.get("adjacency") == "anywhere":
        return any(_normalize(q) in norm for q in exc.get("safe_qualifiers", []))
    return any(_normalize(q) + _normalize(kw) in norm for q in exc.get("safe_qualifiers", []))


def _match_synonyms(norm: str, rules: dict) -> RuleMatch | None:
    """동의어 역인덱스로 변형 표현을 검사한다. 변형이 걸리면 대표어의 규칙을 적용.

    문맥예외는 변형("힐링") 단위가 있으면 그걸 먼저 보고, 없으면 대표어("치료")
    단위로 본다. 변형 단위를 먼저 보는 이유는, 대표어 단위로만 걸면 "힐링"에
    준 예외가 "치료" 직접 매칭까지 같이 느슨해지기 때문이다.
    """
    reverse = _load_reverse_synonyms()
    for variant_norm, (canonical, variant_raw) in reverse.items():
        if variant_norm not in norm:
            continue
        exceptions = rules.get("context_exceptions", {})
        exc_key = variant_raw if variant_raw in exceptions else canonical
        # 대표어가 어느 갈래(violation/needs_review)에 속하는지 찾는다.
        for type_label, keywords in rules["violation"].items():
            if canonical in keywords:
                if _has_context_exception(norm, exc_key, rules):
                    continue
                vtype = ViolationType(type_label)
                return RuleMatch(RuleOutcome.violation, canonical, vtype, JudgmentFlag.violation)
        for type_label, keywords in rules["needs_review"].items():
            if canonical in keywords:
                vtype = ViolationType(type_label)
                return RuleMatch(
                    RuleOutcome.needs_review, canonical, vtype, JudgmentFlag.needs_review
                )
        if canonical in rules["legal_allow"]:
            return RuleMatch(RuleOutcome.legal_allow, canonical, None, None)
        if canonical in rules.get("out_of_scope", []):
            return RuleMatch(RuleOutcome.out_of_scope, canonical, None, None)
    return None


def _dedupe(matches: list[RuleMatch]) -> list[RuleMatch]:
    """같은 문장 안 중복 지적을 없앤다.

    두 가지를 지운다.
    1. 같은 (유형, span) 재등장.
    2. **다른 매칭 span에 포함되는 span.** "세포재생의 시작"은 `세포재생`과 `재생`에
       둘 다 걸리는데 같은 자리를 두 번 지적하는 셈이라 사용자에겐 노이즈다.
       긴 쪽(더 구체적인 쪽)을 남긴다.
    """
    seen: set[tuple] = set()
    out: list[RuleMatch] = []
    spans = [m.span for m in matches]
    for m in matches:
        key = (m.violation_type, m.span)
        if key in seen:
            continue
        # 다른(더 긴) span에 포함되면 버린다.
        if any(m.span != other and m.span in other for other in spans):
            continue
        seen.add(key)
        out.append(m)
    return out


def match_all_rules(sentence: str) -> list[RuleMatch]:
    """문장의 규칙 매칭을 **같은 갈래 안에서 전부** 낸다. 미매칭이면 빈 리스트.

    `match_rule`은 첫 매칭 하나만 냈다. 그래서 한 문장에 위반이 여러 개면 하나만
    지적됐다 — 122자 한 줄에 줄기세포·세포재생·진피층·재생이 다 있어도 지적은
    1건이었다(2026-08-23 실측). 미탐이 최우선 위험인 서비스에서 이건 그냥 놓친 것이다.

    **갈래를 넘나들며 모으지는 않는다.** violation이 하나라도 걸리면 violation만
    전부 내고 needs_review 이하는 안 본다. 갈래 우선순위는 경계표현 조합을 처리하는
    장치라("시술 후 진정"에서 시술이 진정보다 먼저 hit) 그걸 풀면 한 표현이
    위반과 검토필요로 동시에 잡히는 오탐이 생긴다.
    """
    norm = _normalize(sentence)
    rules = _load()

    if _is_unsubstantiated_comparison(norm):
        return [
            RuleMatch(
                RuleOutcome.violation, "비교수치", ViolationType.type_5_deception, JudgmentFlag.violation
            )
        ]

    if _is_unsubstantiated_verification_claim(norm):
        return [
            RuleMatch(
                RuleOutcome.violation, "검증방법단정", ViolationType.type_5_deception, JudgmentFlag.violation
            )
        ]

    violations: list[RuleMatch] = []
    for type_label, keywords in rules["violation"].items():
        vtype = ViolationType(type_label)
        for kw in keywords:
            if not _keyword_present(kw, norm):
                continue
            if _has_context_exception(norm, kw, rules):
                continue
            violations.append(RuleMatch(RuleOutcome.violation, kw, vtype, JudgmentFlag.violation))
    if violations:
        return _dedupe(violations)

    conditional = _match_conditional_violation(norm, rules)
    if conditional is not None:
        return [conditional]

    reviews: list[RuleMatch] = []
    for type_label, keywords in rules["needs_review"].items():
        vtype = ViolationType(type_label)
        for kw in keywords:
            if _keyword_present(kw, norm):
                reviews.append(
                    RuleMatch(RuleOutcome.needs_review, kw, vtype, JudgmentFlag.needs_review)
                )
    # 정밀 침투·흡수 메커니즘 주장. **검토필요 티어 안에 넣는다** — 따로 빼서 먼저
    # 반환하면 같은 문장의 다른 검토필요 키워드에 가려져 영원히 안 뜬다(실측: 정답셋
    # 유일 해당 문장이 "다크서클"에 먼저 걸려 이 규칙이 죽어 있었다).
    # 위반 단정은 안 한다 — 팩이 맥락 판단을 요구하고, 실증자료가 있으면 예외다.
    if _is_penetration_mechanism_claim(norm):
        reviews.append(
            RuleMatch(
                RuleOutcome.needs_review,
                "침투메커니즘",
                ViolationType.type_1_drug_misperception,
                JudgmentFlag.needs_review,
            )
        )
    if reviews:
        return _dedupe(reviews)

    if _is_exclusive_rank_claim(norm):
        return [
            RuleMatch(
                RuleOutcome.needs_review, "배타적순위", ViolationType.type_5_deception, JudgmentFlag.needs_review
            )
        ]


    # 합법·대상외는 "이 문장은 여기서 끝"이라는 확정이라 여러 건일 이유가 없다.
    for kw in rules["legal_allow"]:
        if not _keyword_present(kw, norm):
            continue
        if kw in rules.get("context_exceptions", {}) and not _has_context_exception(norm, kw, rules):
            continue
        return [RuleMatch(RuleOutcome.legal_allow, kw, None, None)]

    for kw in rules.get("out_of_scope", []):
        if _keyword_present(kw, norm):
            return [RuleMatch(RuleOutcome.out_of_scope, kw, None, None)]

    syn = _match_synonyms(norm, rules)
    return [syn] if syn is not None else []


def match_rule(sentence: str) -> RuleMatch | None:
    """문장의 첫 규칙 매칭 한 건. 미매칭이면 None.

    `match_all_rules`의 첫 건이다. 여러 건이 필요한 곳은 그쪽을 쓴다.

    가장 먼저 근거 없는 비교수치(정규식, "대비/보다"+"N배")와 근거 없는 검증방법 주장
    ("임상시험"+"검증" 공출현)을 본다. 그다음 키워드 갈래를 우선순위대로 스캔한다:
    violation > needs_review > legal_allow > out_of_scope.
    앞 갈래에서 먼저 걸리면 뒤는 안 본다. 이 순서가 경계표현 조합을 자연히
    처리한다(예: '시술'이 violation에 있어 '시술 후 진정'은 진정보다 시술이
    먼저 hit). 대표어로 안 걸리면 동의어 사전(synonyms.json)의 변형 표현도
    검사한다(최후순위. 그래서 동의어로만 표현된 위반은 legal_allow 같은
    단어가 같이 있으면 가려질 수 있다 — 2026-08-18에 '치유'로 실측, 별도
    이슈로 남겨둠. §2-1-5·PM 논의 참고).

    니들류(니들·마이크로니들·미세침·MTS·바늘·Pin·needle)는 예전엔 "단어+메커니즘
    서술 동반"일 때만 위반이었는데(conditional_violation), 2026-08-18 하니
    확정으로 폐지하고 단어 자체로 위반 처리한다(violation 플랫 키워드로 이동).

    "리들"은 니들과 갈래가 다르다. 상표 등록·장기 미제재된 회피표기라 단어 자체로는
    위반이 아니지만, 침투·흡수 같은 메커니즘 서술이 붙으면 위반이다(팀장 확정).
    2026-08-18에 니들류를 플랫으로 옮기면서 "리들"을 synonyms.json에서 통째로 뺐는데
    그때 "리들+침투" 조합을 잡던 경로까지 같이 사라진 회귀가 있었다(2026-08-19 실측).
    지금은 `conditional_violation`(judge_rules.json)으로 되살렸다.
    """
    matches = match_all_rules(sentence)
    return matches[0] if matches else None


# 2호(기능성오인) 표방을 가리키는 표지. judge_rules.json의 legal_allow 문맥예외
# (탄력·민감·예민)가 쓰는 unsafe_markers와 같은 목록이라 여기서 단일 출처로 둔다.
_FUNCTIONAL_MARKER_SOURCE = "탄력"


@lru_cache(maxsize=1)
def _functional_markers() -> tuple[str, ...]:
    exc = _load().get("context_exceptions", {}).get(_FUNCTIONAL_MARKER_SOURCE, {})
    return tuple(exc.get("unsafe_markers", ()))


def has_functional_claim(sentence: str) -> bool:
    """문장에 2호(미백·주름개선·자외선차단 등) 표방이 섞여 있는지 본다.

    규칙이 1호 경계표현으로 먼저 확정해 버리면 같은 문장의 2호 클레임이 평가될
    기회를 잃는다("진정에 도움을 주는 미백 크림" → needs_review(진정, 1호)에서 끝나
    미백이 안 보인다). 그때 VLM에도 같이 넘길지 판단하는 데 쓴다.
    """
    norm = _normalize(sentence)
    return any(_normalize(m) in norm for m in _functional_markers())


# 절대적·과장 수식어의 **어간**. `prohibited_expressions.md:85`("완벽한·최적의·파워·
# 탁월한·최고·최상 등 절대적·과장 표현은 객관적 근거 없으면 검토필요") 근거.
#
# **judge_rules.json의 5호 키워드보다 일부러 넓게 잡는다. 드리프트가 아니라 의도된 차이다**
# (2026-08-20 실측으로 폭을 정했다).
# - 규칙집(5호 키워드 + synonyms)은 **좁게**: 거기서 매칭되면 곧바로 finding이 생기므로,
#   어간까지 넓히면 "최적 온도에서 보관하세요"·"완벽 방수 파우치" 같은 배송·보관 안내가
#   검토필요로 잡힌다(실측 확인). 그래서 활용형만 동의어로 등록했다.
# - 여기(합법 강등 게이트)는 **넓게**: 이 함수는 VLM이 이미 2호로 판정하고 성분 대조까지
#   통과한 문장에만 돌아간다. 그런 문장이 "최적 온도 보관" 같은 문구일 가능성은 낮고,
#   틀리는 방향도 안전하다(강등을 막아 검토필요로 남길 뿐, 없는 위반을 만들지 않는다).
#   반대로 놓치면 과장이 통째로 새는 미탐이 된다 — 두 방향의 비용이 다르므로 폭도 다르다.
_EXAGGERATION_STEMS: tuple[str, ...] = (
    "완벽", "최적", "탁월", "최고", "최상", "유일", "파워", "기적",
)


def has_exaggeration(sentence: str) -> bool:
    """문장에 절대적·과장 수식어가 섞여 있는지 본다(어간 기준).

    2호 합법 강등의 안전장치로 쓴다. 한 문장에 라벨이 하나뿐이라, 성분 대조로 2호를
    합법으로 내리면 같은 문장의 과장 표현이 통째로 빠진다(누수 실측 확인, 상세는
    `judge/cosmetic.py:_functional_evidence`). `approved_efficacy_statements.md`
    "판정에 쓰는 법" 4항도 "인정문구를 벗어난 과장 표현이 붙으면 별개로 T5 판정 가능"
    이라고 안내한다 — 성분이 맞아도 과장은 따로 봐야 한다는 뜻이다.

    규칙집보다 넓게 잡는 이유는 위 `_EXAGGERATION_STEMS` 주석 참고.
    """
    norm = _normalize(sentence)
    return any(stem in norm for stem in _EXAGGERATION_STEMS)
