"""I/O 계약 (Pydantic).

`POST /check`의 나오는 것(CheckReport)을 정의한다. 이 스키마가 판정 백엔드와
프론트가 공유하는 계약면이다. 넣는 것(요청)은 multipart라 Pydantic이 아니라
FastAPI Form/File로 받는다(→ api/app.py).

식별자는 영어 snake_case, 사용자 대면 값(위반유형·판정 플래그)은 한국어 라벨을 그대로
직렬화한다. reference/cosmetic_kr·score_eval.py의 라벨 문자열과 일치시켜, 프론트가
따로 한↔영 매핑표를 들지 않아도 되게 한다.
"""

from enum import Enum
from typing import Literal, Union

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

    VLM 비전 OCR에서 문구/단어 단위의 정밀 사각 좌표(x_start~x_end, y_start~y_end)를
    원본 이미지 픽셀 좌표로 실어, 프론트가 원본 위에 정밀한 하이라이트 박스를 칠 수 있게 한다.
    좌표가 없거나 밴드만 있는 경우 x_start/x_end는 None 또는 이미지 전체 폭이 될 수 있다.

    이미지 입력만 좌표가 있다. 텍스트 입력(이미지 없음)이면 tile과 좌표 모두 None.
    source_h/source_w는 원본 이미지 크기라 프론트가 밴드 및 bbox를 원본 축척에 맞춘다.
    """

    tile: str | None = None
    order: int
    x_start: int | None = None  # 바운딩 박스 좌측(원본 이미지 x좌표)
    x_end: int | None = None  # 바운딩 박스 우측(원본 이미지 x좌표)
    y_start: int | None = None  # 바운딩 박스 상단(원본 이미지 y좌표)
    y_end: int | None = None  # 바운딩 박스 하단(원본 이미지 y좌표)
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
    # OCR이 못 읽은 타일 수. 0이 아니면 **이 리포트는 이미지 일부를 못 본 상태**다.
    # 이게 없으면 "읽었는데 문제없음"과 "아무것도 못 읽음"이 응답에서 구분되지 않아,
    # 실패가 깨끗한 결과처럼 보인다(2026-08-20 시연 점검에서 실제로 관측: OCR이 깨진
    # JSON을 뱉어 문장 0개·finding 0개가 나왔는데 응답에는 아무 흔적이 없었다).
    n_ocr_failed_tiles: int = 0
    counts_by_type: dict[str, int] = Field(default_factory=dict)  # 위반유형별 건수
    product_out_of_scope: bool = False  # True면 화장품법 적용 대상 아님(도구·부자재 등), 문장 판정 자체를 안 함
    out_of_scope_reason: str | None = None  # 대상외로 걸린 키워드. 화면에 사유 표시용


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
    # 지적별 대체표현. **판정할 때 배치로 한 번에 만들어 여기 싣는다**(팀장 지시,
    # 2026-08-22). 전에는 리포트 화면이 카드를 펼칠 때마다 /remediate를 1건씩
    # 불러서 카드당 5~8초가 걸렸고, 다시 보기로 열면 또 불렀다. 판정에 이미 LLM이
    # 붙는 구간이라 거기서 같이 만들면 호출이 지적 N건당 1회로 줄고, 리포트에
    # 실려 저장되니 다시 보기는 호출 0회다.
    # 만들다 실패하면 빈 리스트로 둔다(리포트 자체는 나가야 한다).
    replacements: list["Replacement"] = Field(default_factory=list)


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
    report: Union[CheckReport, USPreflightReport]


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


class TableRow(BaseModel):
    """table_info 레이아웃 슬롯 한 줄(label→value). 예: "제형"→"액상"."""

    label: str
    value: str


class Section(BaseModel):
    """생성된 콘텐츠 한 섹션. 화면은 섹션 카드로 렌더한다."""

    kind: str  # 제품개요 | 사용법 | 주의사항 | 광고문구
    text: str
    source: str  # llm(생성) | remediation(조건표 치환) | template(표준문구) | approved_claim(인증서-인정문구 매칭, create 모드) | product_spec(구조화 상품정보, create 모드)
    table_rows: list[TableRow] | None = Field(
        None, description="table_info layout_type 모듈용 구조화 데이터. 없으면 text만 쓰는 일반 섹션"
    )
    module_kind: str | None = Field(
        None,
        description="이 섹션이 채우는 layout_plan 모듈의 kind. 프론트가 모듈 이미지를 "
        "찾을 때 쓴다. kind와 다를 수 있다 — 위반소지 모듈(hero_intro 등)의 내용은 "
        "LLM이 아니라 인정문구·실증자료가 채우므로 kind가 '광고문구'·'실증자료'로 나온다.",
    )


class Replacement(BaseModel):
    """위반 문구 → 안전 표현 치환 내역(조건표 기반). '이렇게 고쳤어요' 대조용."""

    original: str
    replaced: str
    violation_type: ViolationType
    basis: str  # 합법 표기 틀 근거
    # 어느 finding에서 나온 대체표현인지. 리포트 화면이 카드와 짝지을 때 쓴다.
    # original만으로는 못 짝짓는다 - 조건표 경로는 span(단어), LLM 경로는 문장 전체가
    # 들어가서 키가 경로마다 달라진다. /generate 경로는 안 쓰므로 None 허용.
    finding_index: int | None = None
    # 대체표현 자체가 실증대상일 때 붙이는 고지. 안 붙이면 사용자가 위반에서 벗어난
    # 줄 알고 그대로 써서, 우리가 검토필요를 만들어주는 셈이 된다(2026-08-20 팀장 지시).
    note: str | None = None


# CheckReport가 Replacement를 앞선 위치에서 문자열로 참조한다(정의 순서 때문).
# 여기서 한 번 굳혀둔다.
CheckReport.model_rebuild()


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


class ModuleImage(BaseModel):
    """계획된 모듈 하나에 대한 이미지 생성 결과.

    텍스트는 굽지 않는다. 배경·연출만 만들고 문구는 프론트가 위에 얹는다.
    실패·거부도 조용히 빠지지 않게 status와 reason으로 남긴다.
    """

    module_kind: str
    status: str  # generated(생성됨) | skipped(실패·거부·한도초과)
    reason: str | None = None
    image_url: str | None = None


class ModulePlacement(BaseModel):
    """모듈 하나가 긴 배경 위 어디에 어떤 바탕으로 앉는지 (레이어 구조 2단계).

    **좌표는 픽셀이 아니라 배경 세로 대비 비율이다.** 배경 크기가 생성마다 달라지고
    (비율을 프롬프트로만 지시한다), export HTML은 컨테이너 폭에 맞춰 스케일된다.
    퍼센트라야 둘 다에 안 깨진다. VLM bbox 하이라이트가 이미 같은 관례를 쓴다
    (`design/mockups/long-canvas-placement-rules.md` §1).

    `background_mode`는 **`layout_type`으로 결정된다. 밝기 계산이 아니다.**
    처음엔 "quiet zone의 대비 여유"로 가르자는 안이 있었는데 성립하지 않는다.
    스크림 `rgba(0,0,0,.6)`은 PR #208에서 **최악 조건(순백 배경)으로 역산한 값**이라
    어떤 배경에서도 AA를 넘긴다(순백 5.74:1, 어두울수록 더 올라감). 밝기를 아무리
    재도 답이 항상 `image_scrim`이라 `solid_plate`가 죽은 코드가 된다.

    실제 기준은 어휘집 12종의 성격이다(디디 §4):
    - 사진 위에 문구를 직접 겹치는 건 `hero_fullbleed`·`mood_macro` **둘뿐**
    - 나머지는 완전 평면이거나 이미지·텍스트 분리형이라 `solid_plate`가 **기본값**이지
      안전지대를 못 찾아 쓰는 폴백이 아니다
    """

    module_kind: str
    y_start_pct: float = Field(..., ge=0.0, le=1.0)
    y_end_pct: float = Field(..., ge=0.0, le=1.0)
    background_mode: str = Field(
        "solid_plate",
        description="image_scrim(사진 위 스크림) | solid_plate(불투명 플레이트). layout_type으로 정해진다.",
    )
    status: str = Field("placed", description="placed(배치됨) | skipped(배치 실패)")
    reason: str | None = Field(
        None, description="skipped 사유. 조용히 빠지지 않게 남긴다(CLAUDE.md §E)."
    )


class CanvasBackground(BaseModel):
    """상세페이지 전체에 깔리는 긴 배경 이미지 1장 (레이어 구조 1단계).

    구조: 이 배경 위에 모듈 이미지·표·설문 결과·문구가 얹힌다(팀장 확정, 2026-08-20).
    모듈 이미지를 **대신하지 않는다** — 둘 다 쓰인다.

    `placements`가 비어 있으면 프론트는 기존 방식(모듈마다 자기 이미지를 쓰는 렌더)으로
    폴백한다. 배경 분석에 실패해도 생성 전체를 실패시키지 않기 위한 경로다.
    """

    status: str  # generated(생성됨) | skipped(실패·거부·미요청)
    reason: str | None = None
    image_url: str | None = None
    placements: list[ModulePlacement] = Field(
        default_factory=list,
        description="모듈별 배치 좌표. 비면 프론트가 기존 렌더로 폴백한다.",
    )


class ImagePlan(BaseModel):
    """이미지 배치 + 생성 가드레일 결과(FR-13)."""

    placed: list[PlacedImage] = Field(default_factory=list)
    generation: ImageGenResult = Field(default_factory=ImageGenResult)
    module_images: list[ModuleImage] = Field(
        default_factory=list, description="create 모드 모듈별 이미지 생성 결과"
    )
    canvas: CanvasBackground | None = Field(
        None,
        description="긴 배경 이미지 1장(옵트인). None이면 요청 안 했거나 생성기가 없다는 뜻.",
    )


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
    canvas_requested: bool = Field(
        False,
        description="긴 배경 이미지 1장을 추가로 만들지(레이어 구조 1단계). "
        "모듈 이미지를 대신하지 않고 더해지므로 이미지가 한 장 늘고 과금도 는다. "
        "그래서 기본은 꺼져 있다.",
    )


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


class SurveyEvidence(BaseModel):
    """create 모드 전용: 사업자가 입력한 **소비자 설문조사** 결과.

    **`ClinicalEvidence`와 절대 섞지 않는다.** 관리지침 [별표2]가 인정하는 실증
    수단은 인체적용시험·인체외시험·시험분석·기능성심사 자료뿐이고 **설문조사는
    목록에 없다.** 그래서 이 값이 아무리 많아도 임상 계열 모듈(clinical_*)은
    열리지 않는다(2026-08-20 팀장 확정).

    쓸 수 있는 건 효능이 아닌 항목뿐이다(향·발림성·용기·재구매의향 등). 피부
    변화를 말하는 순간 효능 주장이라 설문으로는 못 받친다. 판별은
    `reference.survey.is_efficacy_survey`가 한다.

    메타데이터를 전부 필수로 받는 이유: 판정기가 "사용자 96% 만족"을 5호(거짓·과장)
    검토필요로 잡으면서 사유를 이렇게 냈다 — "설문방법·표본·시기·출처 등 근거
    제시가 없어 객관적 확인 필요"(2026-08-20 실측). 수치만 있고 출처가 없으면
    그 자체로 위반 소지라, 선택 필드로 두면 위반 소지 문구를 우리가 만들어주게 된다.

    **다만 메타데이터를 다 넣어도 5호 검토필요는 해소되지 않는다**(2026-08-20 실측으로
    확인, 처음엔 해소될 거라 봤으나 틀렸다). 판정기는 조사기관·시기·표본이 있어도
    원자료(조사방법·무작위성·질문 문항)를 봐야 한다고 본다. 그래서 이 필드들은
    "합법으로 만들어주는 장치"가 아니라 **검토 범위를 좁히고 사용자에게 무엇을
    준비해야 하는지 알려주는 장치**다. 그 사실은 `risk_confirmations`로 고지한다.
    """

    claim: str = Field(..., description='무엇에 대한 응답인지, 예: "향에 만족"')
    value: str = Field(..., description='결과 수치 원문 표기, 예: "96%"')
    sample_size: str = Field(..., description='표본 수, 예: "200명"')
    institution: str = Field(..., description="조사기관명")
    period: str = Field(..., description='조사 시기, 예: "2026년 3월"')
    method: str = Field(..., description='조사 방법, 예: "온라인 자기기입식 설문"')


class LayoutModule(BaseModel):
    """상세페이지 한 모듈. `data/layout_references/*.json` 스키마를 그대로 따른다."""

    kind: str  # hero_intro | ingredient_highlight | clinical_result | texture 등
    purpose: str
    has_claim_risk: bool = False
    layout_type: str = "section_statement"  # 어휘집 12종 카탈로그 중 하나. 프론트 템플릿 선택용


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
    survey_evidence: list[SurveyEvidence] | None = Field(
        None,
        description="사업자 입력 소비자 설문조사 결과(create 모드 전용). "
        "**실증자료가 아니다** — 임상 모듈을 열지 못하고, 피부 변화(효능) 주장은 거부된다.",
    )
    notes: str | None = Field(None, description="설문/추가 제품정보 자유서술")
    color_tone: str | None = Field(
        None, description="인터뷰에서 받은 컬러톤(create 모드, 이미지 생성용). 예: '베이지·아이보리 톤'"
    )
    mood: str | None = Field(
        None, description="인터뷰에서 받은 분위기(create 모드, 이미지 생성용). 예: '미니멀하고 차분한'"
    )
    product_photo_ids: list[str] | None = Field(
        None,
        description="`POST /uploads/product-photo`로 먼저 올린 제품사진 ID 목록(create 모드). "
        "있으면 배경 이미지 생성 시 합성 참조 이미지로 쓴다(AI 배경·연출 합성, 팀장 승인).",
    )
    formulation_type: str | None = Field(
        None, description="인터뷰에서 받은 제형(create 모드, table_info 상품정보 모듈용). 예: '액상', '크림'"
    )
    volume: str | None = Field(
        None, description="인터뷰에서 받은 용량·중량(create 모드, table_info 상품정보 모듈용). 예: '50ml'"
    )
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
