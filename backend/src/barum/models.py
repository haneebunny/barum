"""I/O 계약 (Pydantic).

`POST /check`의 나오는 것(CheckReport)을 정의한다. 이 스키마가 판정 백엔드와
프론트가 공유하는 계약면이다. 넣는 것(요청)은 multipart라 Pydantic이 아니라
FastAPI Form/File로 받는다(→ api/app.py).

식별자는 영어 snake_case, 사용자 대면 값(위반유형·위험도)은 한국어 라벨을 그대로
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
    """화장품 광고 위반유형 (법 제13조 체계).

    화장품은 식품(1~5호)과 체계가 다르다. 3호는 삭제된 조항이라 없다.
    직렬화 값은 한국어 라벨(reference/cosmetic_kr 기준).
    """

    legal = "합법"
    type_1_drug_misperception = "1호_의약품오인"
    type_2_functional_misperception = "2호_기능성오인"
    type_4_falsity_deception = "4호_거짓과장기만"
    out_of_scope = "대상외"


class RiskLevel(str, Enum):
    """위험도. UI 색 매핑은 프론트가 하되, 데이터는 3단계로 표현한다."""

    high = "고"
    medium = "중"
    low = "저"


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
    risk: RiskLevel
    explanation: str  # 왜 위반인지 사람이 읽는 설명
    location: Location


class Summary(BaseModel):
    """리포트 상단 요약. 정책상 점수가 아니라 근거 개수로 표현한다."""

    region: Region
    n_sentences: int  # 판정에 투입된 문장 수
    n_findings: int  # 위반으로 지목된 건수(합법 제외)
    counts_by_type: dict[str, int] = Field(default_factory=dict)  # 위반유형별 건수


class CheckReport(BaseModel):
    """`POST /check` 응답. findings + summary."""

    findings: list[Finding]
    summary: Summary
