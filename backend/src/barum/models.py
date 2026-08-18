"""I/O 계약 (Pydantic).

`POST /check`의 나오는 것(CheckReport)을 정의한다. 이 스키마가 판정 백엔드와
프론트가 공유하는 계약면이다. 넣는 것(요청)은 multipart라 Pydantic이 아니라
FastAPI Form/File로 받는다(→ api/app.py).

식별자는 영어 snake_case, 사용자 대면 값(위반유형·판정 플래그)은 한국어 라벨을 그대로
직렬화한다. reference/cosmetic_kr·score_eval.py의 라벨 문자열과 일치시켜, 프론트가
따로 한↔영 매핑표를 들지 않아도 되게 한다.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    2호(기능성오인)만 예외다. 성분 정합이 실제 근거 대조라 그 결과를 쓴다.
    """

    violation = "위반"
    needs_review = "검토필요"


class Location(BaseModel):
    """문구가 잡힌 위치.

    OCR은 글자 좌표(bbox)를 주지 않는다. 우리가 확보하는 위치 정보는 어느 타일의
    몇 번째 문장이냐까지다. 타일 단위 세로 밴드(y_start~y_end)를 원본 이미지
    좌표로 실어, 프론트가 원본 위에 밴드를 하이라이트할 수 있게 한다. 문장 단위
    정밀 좌표는 없다(OCR이 bbox를 안 주므로 타일 밴드가 최선).

    이미지 입력만 좌표가 있다. 텍스트 입력(이미지 없음)이면 tile과 좌표 모두 None.
    source_h/source_w는 원본 이미지 크기라 프론트가 밴드를 원본 축척에 맞춘다.
    """

    tile: str | None = None
    order: int
    y_start: int | None = None  # 타일 밴드 상단(원본 이미지 y좌표)
    y_end: int | None = None  # 타일 밴드 하단(원본 이미지 y좌표)
    source_h: int | None = None  # 원본 이미지 높이(px)
    source_w: int | None = None  # 원본 이미지 너비(px)
    source: str | None = None  # 입력 출처("product_name" | "ad_text" | None=이미지OCR)


class Finding(BaseModel):
    """문구 하나에 대한 판정 결과. 리포트에 한 줄로 렌더된다."""

    span: str  # 위반으로 지목된 표현(문장 일부 또는 전체)
    sentence: str  # span이 속한 원문 문장
    violation_type: ViolationType
    legal_basis: str  # 근거 조항(예: "화장품법 제13조 제1항 제2호")
    legal_basis_text: str | None = None  # 그 조항의 원문 전체(없으면 None, 지어내지 않음)
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
    별개 개념이다(판정 자체를 못함, VLM 호출 실패). 검토필요(판정은 했으나 근거
    약함)와 혼동하지 않는다.
    """

    region: Region
    n_sentences: int  # 판정에 투입된 문장 수
    n_findings: int  # findings 총 건수(위반+검토필요, 합법·대상외 제외)
    n_violation: int = 0  # flag=위반 건수
    n_needs_review: int = 0  # flag=검토필요 건수
    n_unjudged: int = 0  # 판정 실패로 미판정된 문장 수(검토필요와 다른 개념)
    counts_by_type: dict[str, int] = Field(default_factory=dict)  # 위반유형별 건수


class BasisCitation(BaseModel):
    """규제 근거 인용 하나. `citation_registry.json` 항목을 API 응답용으로 축약한다.

    2026-08-13 프론트 푸터가 화장품과 무관한 식품 도메인 고시번호("2025-79호")를
    하드코딩해 표시한 사고가 있었다. 그 뒤로 규제 근거 문자열은 어디서도 하드코딩
    하지 않고 전부 이 레지스트리(`citation_registry.json`)에서 읽는다.
    """

    id: str
    law_name: str
    citation_id: str | None = None
    effective_date: str | None = None
    source_url: str | None = None


class RegulatoryBasis(BaseModel):
    """한 관할(jurisdiction)의 적용 기준. `GET /reference/basis`와 `CheckReport.basis`가 같이 쓴다."""

    jurisdiction: Region
    citations: list[BasisCitation]


class CheckReport(BaseModel):
    """`POST /check` 응답. findings + unjudged + summary.

    result_id: 이 검사가 저장됐으면 그 추측불가 id(다시 보기 URL). 저장 안 됐으면
    (JUDGE_KIND=stub·DB 미설정·저장 실패) None. 프론트는 있으면 다시 보기 링크를 건다.
    basis: 검사 시점에 실제 적용된 규제 근거 스냅샷. 나중에 레지스트리가 갱신돼도
    이 리포트를 다시 볼 때는 검사 당시 값 그대로 보여야 해서 결과에 박아 보낸다.
    """

    findings: list[Finding]
    unjudged: list[UnjudgedSentence] = Field(default_factory=list)
    summary: Summary
    result_id: str | None = None
    basis: RegulatoryBasis | None = None


# ── 미국 프리플라이트 (자외선차단 최소보장, 기획서 v1.6) ──────────────────────


class USPreflightCategory(str, Enum):
    """미국 프리플라이트 지적 갈래. 국내 ViolationType/JudgmentFlag와 다른 개념이다 —
    법 위반이 아니라 화장품→OTC의약품 규제 카테고리 전환 안내다(팀 확정 2026-08-18,
    reference/cosmetic_us/sunscreen_otc_classification.md §0).
    """

    otc_reclassification = "OTC의약품_분류전환"  # SPF/자외선차단 표현 자체가 트리거
    unapproved_ingredient = "미국_미승인_성분"  # 성분이 미국 승인 목록에 없음
    ingredient_info_missing = "성분정보_확인불가"  # 전성분 정보가 없어 성분 대조를 못함


class USPreflightFinding(BaseModel):
    """미국 프리플라이트 지적 하나. 국내 Finding과 필드는 비슷하지만 violation_type/flag
    대신 category를 쓴다(위반이 아니므로). 국내 Finding과 절대 섞지 않는다.
    """

    span: str  # 지목된 표현(SPF 문구) 또는 성분명
    sentence: str  # span이 속한 원문 문장. 성분 트리거는 전성분 원문 표기 그대로
    category: USPreflightCategory
    explanation: str  # 왜 이 카테고리로 잡혔는지 사람이 읽는 설명
    location: Location


class USPreflightSummary(BaseModel):
    """미국 프리플라이트 리포트 상단 요약."""

    n_sentences: int
    n_findings: int
    counts_by_category: dict[str, int] = Field(default_factory=dict)


class USPreflightReport(BaseModel):
    """미국 프리플라이트 검사 응답. 국내 CheckReport와 별도 엔드포인트·별도 스키마(팀 확정).

    disclaimer: 리포트 하단 각주. 확정 안 된 규제 변경 리스크(OTC000008 등)는 개별
    finding으로 안 만들고 여기 각주로만 담기로 확정함(sunscreen_otc_classification.md §4).
    """

    findings: list[USPreflightFinding]
    summary: USPreflightSummary
    result_id: str | None = None
    disclaimer: str


class StoredCheck(BaseModel):
    """`GET /reports/{result_id}` 응답 (다시 보기).

    저장된 CheckReport를 감싸고 저장 메타를 얹는다. 리포트 자체는 그대로라 프론트가
    "방금 결과"와 "다시 보기"를 같은 컴포넌트로 렌더할 수 있다. 원본 이미지는
    별도 프록시(`GET /reports/{id}/image`)로 받는다(image_available이 true일 때).
    """

    result_id: str
    created_at: str
    region: Region
    image_available: bool
    product_name: str | None = None
    report: CheckReport


class RemediationRequest(BaseModel):
    """수정 권고안 생성 요청."""

    sentence: str = Field(..., description="탐지된 위반 문구 전체")
    violation_type: ViolationType = Field(..., description="위반유형 라벨")
    span: str | None = Field(None, description="위반으로 지목된 세부 표현 (생략 시 sentence 전체)")


class RemediationResponse(BaseModel):
    """수정 권고안 생성 응답."""

    sentence: str
    violation_type: ViolationType
    span: str
    suggestions: list[str] = Field(..., description="대체 표현 후보들")
    disclaimer: str = Field(..., description="권고 사항 고지 안내 문구")


# ── 콘텐츠 생성 (FR-11/13) ──────────────────────────────────────────────────


class Section(BaseModel):
    """생성된 콘텐츠 한 섹션. 화면은 섹션 카드로 렌더한다."""

    kind: str  # 제품개요 | 사용법 | 주의사항 | 광고문구
    text: str
    source: str  # llm(생성) | remediation(조건표 치환) | template(표준문구) | approved_claim(인증서-인정문구 매칭, create 모드)


class Replacement(BaseModel):
    """위반 문구 → 안전 표현 치환 내역(조건표 기반). '이렇게 고쳤어요' 대조용."""

    original: str
    replaced: str
    violation_type: ViolationType
    basis: str  # 합법 표기 틀 근거


class PlacedImage(BaseModel):
    """초안 레이아웃에 배치된 업로드 이미지."""

    slot: str  # hero | body 등
    image_url: str  # 예: /reports/{result_id}/image


class ImageGenResult(BaseModel):
    """이미지 생성 요청 처리 결과(FR-13). 이번 MVP는 실제 생성 안 함(가드레일만).

    requested=True인데 allowed=False면 사칭 필터에 걸린 것(reason에 사유).
    allowed=True여도 ai_labeled/생성물은 없다(생성기 미도입, 폴백).
    """

    requested: bool = False
    allowed: bool | None = None
    reason: str | None = None
    ai_labeled: bool = False


class ImagePlan(BaseModel):
    """이미지 배치 + 생성 가드레일 결과(FR-13)."""

    placed: list[PlacedImage] = Field(default_factory=list)
    generation: ImageGenResult = Field(default_factory=ImageGenResult)


class RiskConfirmation(BaseModel):
    """자동으로 못 고쳐 남은 위험 항목. 사용자가 확인해야 생성 확정(체크리스트 UI)."""

    id: str  # 체크 상태 추적용
    text: str
    reason: str
    requires_confirmation: bool = True


class RecheckSummary(BaseModel):
    """생성물을 /check로 재검증한 요약. safe=False면 화면이 빨강 경고 배지."""

    safe: bool
    n_findings: int
    n_violation: int = 0
    n_needs_review: int = 0


class ImageGenRequest(BaseModel):
    """이미지 생성 요청 입력(선택). requested=True일 때 prompt를 필터링한다."""

    requested: bool = False
    prompt: str | None = None


class IngredientAmount(BaseModel):
    """create 모드 전용: 성분명 + 함량(원문 표기 그대로, 예 "2%"·"2,500 IU/g").

    기존 `ingredients`(콤마 성분명 문자열)는 함량이 없어 인정문구 함량기준
    대조에 못 쓴다. improve 모드는 이 필드를 쓰지 않는다(회귀 없음).
    """

    name: str
    amount: str = Field(..., description='함량 원문 표기, 예: "2%", "2~5%", "2,500 IU/g"')


class ClinicalEvidence(BaseModel):
    """create 모드 전용: 사업자가 직접 입력한 실증자료(인체적용시험 결과 등).

    **barum은 이 자료의 진위를 검증하지 않는다.** 기능성 인증서(`certifications`)와
    달리 대조할 레퍼런스팩이 없어서, 사업자 입력을 그대로 신뢰하고 그대로 싣는다.
    그래서 ① 응답 안내문구에 미검증임을 명시하고 ② `risk_confirmations`에 진위
    확인 항목을 넣는다(하니·PM 확정, 2026-08-18).

    이 값이 하나라도 있으면 임상 계열 모듈(clinical_result 등)이 계획에 허용된다.
    수치는 LLM이 쓰지 않고 여기 입력값을 그대로 쓴다(지어낼 여지를 없앤다).
    """

    claim: str = Field(..., description='무엇을 개선했는지, 예: "다크스팟 개선"')
    value: str = Field(..., description='결과 수치 원문 표기, 예: "87%", "4주 후 2.1배"')
    institution: str | None = Field(None, description="시험기관명")
    period: str | None = Field(None, description='시험기간, 예: "4주", "8주"')
    note: str | None = Field(None, description="피험자 수·조건 등 부연")


class LayoutModule(BaseModel):
    """상세페이지 한 모듈. `data/layout_references/*.json` 스키마를 그대로 따른다."""

    kind: str  # hero_intro | ingredient_highlight | clinical_result | texture 등
    purpose: str
    has_claim_risk: bool = False


class LayoutPlan(BaseModel):
    """이번 상품 상세페이지의 모듈 구성·순서(플래너 산출물)."""

    modules: list[LayoutModule] = Field(default_factory=list)
    product_type: str | None = Field(None, description="추측된 상품 종류. None이면 레퍼런스 없이 폴백")
    source: str = Field("fallback", description="planner(LLM 계획) | fallback(고정 플랜)")


class GenerateRequest(BaseModel):
    """`POST /generate` 요청. `mode`로 improve(개선)/create(신규 생성) 분기.

    improve: content(원본 광고 텍스트) 필수. 저장된 검사엔 위반 문장만 있고
    원문 전체가 없어, 개선하려면 프론트가 원본 텍스트를 넘긴다(하니 승인).
    create: content 없이 product_name·ingredient_amounts·certifications만으로
    인증서 매칭 인정문구를 조립한다(효능표현 자유창작 금지, 조건표 대신
    인증서-인정문구 매칭이 소스).
    """

    mode: Literal["improve", "create"] = "improve"
    content: str | None = Field(None, description="개선 대상 원본 광고 텍스트(improve 모드 필수)")
    result_id: str | None = Field(None, description="검사 결과 참조(이미지·맥락)")
    product_name: str | None = None
    ingredients: str | None = Field(None, description="전성분(콤마 구분, improve 모드용)")
    ingredient_amounts: list[IngredientAmount] | None = Field(
        None, description="성분명+함량(create 모드 전용, 인정문구 함량기준 대조에 씀)"
    )
    certifications: list[str] = Field(default_factory=list)
    clinical_evidence: list[ClinicalEvidence] | None = Field(
        None,
        description="사업자 입력 실증자료(create 모드 전용). barum은 진위를 검증하지 않는다.",
    )
    notes: str | None = Field(None, description="설문/추가 제품정보 자유서술")
    image_generation: ImageGenRequest | None = None

    @model_validator(mode="after")
    def _content_required_for_improve(self) -> "GenerateRequest":
        if self.mode == "improve" and not self.content:
            raise ValueError("mode='improve'는 content(원본 광고 텍스트)가 필수입니다")
        return self


class SkippedClaim(BaseModel):
    """create 모드에서 조건 미충족으로 생성하지 않은 인정문구 카테고리. 조용히 빠지지 않게 명시."""

    category: str
    reason: str


class GenerateResponse(BaseModel):
    """`POST /generate` 응답. 구조화 콘텐츠 + 치환내역 + 이미지계획 + 재검증."""

    sections: list[Section]
    replacements: list[Replacement]
    image_plan: ImagePlan
    pii_removed: list[str] = Field(default_factory=list)
    risk_confirmations: list[RiskConfirmation] = Field(default_factory=list)
    skipped_claims: list[SkippedClaim] = Field(default_factory=list)
    layout_plan: LayoutPlan | None = Field(
        None, description="create 모드 모듈 구성·순서. improve 모드는 None"
    )
    recheck: RecheckSummary
    disclaimer: str
