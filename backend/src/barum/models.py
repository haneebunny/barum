"""I/O 계약 (Pydantic).

`POST /check`의 나오는 것(CheckReport)을 정의한다. 이 스키마가 판정 백엔드와
프론트가 공유하는 계약면이다. 넣는 것(요청)은 multipart라 Pydantic이 아니라
FastAPI Form/File로 받는다(→ api/app.py).

식별자는 영어 snake_case, 사용자 대면 값(위반유형·판정 플래그)은 한국어 라벨을 그대로
직렬화한다. reference/cosmetic_kr·score_eval.py의 라벨 문자열과 일치시켜, 프론트가
따로 한↔영 매핑표를 들지 않아도 되게 한다.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Region(str, Enum):
    """검사 대상 국가. 지금은 국내(KR)만 실동작, 미국(US)은 2단계."""

    KR = "KR"
    US = "US"


class ViolationType(str, Enum):
    """화장품 광고 위반유형 (법 제13조 체계, 개정법 기준).

    화장품은 식품(1~5호)과 체계가 다르다. 3호는 삭제된 조항이라 없다.
    거짓·과장·기만은 현행법상 4호이나, 2026.11.27 시행 개정법에서 AI 생성물로
    전문가 보증을 오인시키는 광고 금지가 신설 4호로 들어오며 5호로 밀린다.
    시행 임박(발표 3주 뒤)이라 개정법 기준(5호)으로 미리 맞춘다. 신설 4호(AI)는
    문구 판정 라벨이 아니라 콘텐츠 생성 가드레일(FR-13) 영역이라 이 enum엔 없다.
    직렬화 값은 한국어 라벨(reference/cosmetic_kr 기준).
    """

    legal = "합법"
    type_1_drug_misperception = "1호_의약품오인"
    type_2_functional_misperception = "2호_기능성오인"
    type_5_deception = "5호_거짓과장기만"
    out_of_scope = "대상외"


class JudgmentFlag(str, Enum):
    """판정 확정도. v1.8: 위험도(고/중/저) 등급 폐지 → 위반/검토필요 이진화.

    '근거 있으면 위반, 근거 없으면 검토필요'(FR-5). RagJudge 이전엔 대부분
    유형에 규칙집 대조 수단이 없어 잠정적으로 위반으로 둔다(recall 우선).
    2호(기능성오인)만 예외 — 성분 정합이 실제 근거 대조라 그 결과를 쓴다.
    """

    violation = "위반"
    needs_review = "검토필요"


class Location(BaseModel):
    """문구가 잡힌 위치.

    OCR은 글자 좌표(bbox)를 주지 않는다. 우리가 확보하는 위치 정보는 어느 타일의
    몇 번째 문장이냐까지다. 텍스트 입력(이미지 없음)이면 tile은 None.
    """

    tile: str | None = None
    order: int


class Finding(BaseModel):
    """문구 하나에 대한 판정 결과. 리포트에 한 줄로 렌더된다."""

    span: str  # 위반으로 지목된 표현(문장 일부 또는 전체)
    sentence: str  # span이 속한 원문 문장
    violation_type: ViolationType
    legal_basis: str  # 근거 조항(예: "화장품법 제13조 제1항 제2호")
    flag: JudgmentFlag  # 위반(근거 확인) | 검토필요(근거 약함·불명)
    explanation: str  # 왜 위반인지 사람이 읽는 설명
    location: Location


class UnjudgedSentence(BaseModel):
    """판정하지 못한 문장.

    VLM 호출 실패(429·빈응답 등)로 위반 여부를 못 가린 문장. 정책상 recall 우선이라
    이걸 '합법'으로 삼키면 미탐이 숨는다. 그래서 findings에도 합법에도 넣지 않고
    별도로 남겨 '미판정(재검사 필요)'으로 드러낸다.
    """

    sentence: str
    location: Location


class Summary(BaseModel):
    """리포트 상단 요약. 정책상 점수가 아니라 근거 개수로 표현한다.

    n_findings = n_violation + n_needs_review(합법·대상외 제외). n_unjudged는
    별개 개념(판정 자체를 못함, VLM 호출 실패) — 검토필요(판정은 했으나 근거
    약함)와 혼동하지 않는다.
    """

    region: Region
    n_sentences: int  # 판정에 투입된 문장 수
    n_findings: int  # findings 총 건수(위반+검토필요, 합법·대상외 제외)
    n_violation: int = 0  # flag=위반 건수
    n_needs_review: int = 0  # flag=검토필요 건수
    n_unjudged: int = 0  # 판정 실패로 미판정된 문장 수(검토필요와 다른 개념)
    counts_by_type: dict[str, int] = Field(default_factory=dict)  # 위반유형별 건수


class CheckReport(BaseModel):
    """`POST /check` 응답. findings + unjudged + summary."""

    findings: list[Finding]
    unjudged: list[UnjudgedSentence] = Field(default_factory=list)
    summary: Summary
