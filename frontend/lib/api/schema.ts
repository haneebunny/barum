import { z } from "zod";

// docs/api/README.md 의 CheckReport 계약과 1:1. 바뀌면 이 파일도 같이 갱신.

export const RegionSchema = z.enum(["KR", "US"]);
export type Region = z.infer<typeof RegionSchema>;

export const ViolationTypeSchema = z.enum([
  "합법",
  "1호_의약품오인",
  "2호_기능성오인",
  "5호_거짓과장기만",
  "대상외",
]);
export type ViolationType = z.infer<typeof ViolationTypeSchema>;

export const FlagSchema = z.enum(["위반", "검토필요"]);
export type Flag = z.infer<typeof FlagSchema>;

export const LocationSchema = z.object({
  tile: z.string().nullable(),
  order: z.number(),
  x_start: z.number().nullable().optional(),
  x_end: z.number().nullable().optional(),
  y_start: z.number().nullable().optional(),
  y_end: z.number().nullable().optional(),
  source_h: z.number().nullable().optional(),
  source_w: z.number().nullable().optional(),
  source: z.string().nullable().optional(),
});
export type Location = z.infer<typeof LocationSchema>;

export const FindingSchema = z.object({
  span: z.string(),
  sentence: z.string(),
  violation_type: ViolationTypeSchema,
  legal_basis: z.string(),
  // 조문 원문 전체. 백엔드가 원문을 확보한 유형만 채움(없으면 null, 구버전 리포트엔 필드 자체가 없을 수 있음)
  legal_basis_text: z.string().nullable().optional(),
  flag: FlagSchema,
  explanation: z.string(),
  // 모델이 스스로 답한 확신도(0~100, 검증 불가한 자기신고). evidence_grade로 대체됐다
  // (팀장 승인, 2026-08-23) - 화면엔 더 이상 안 띄우고 재캘리브레이션용으로만 남긴다.
  confidence: z.number().nullable().optional(),
  // 어느 층이 이 판정을 냈는지(rule|vlm). 예전 저장 리포트엔 없어 optional.
  source: z.string().nullable().optional(),
  // 이 판정의 근거가 규칙문서/원문에서 얼마나 확인됐는지(코드가 결정론적으로 계산,
  // 3단). 정확한 값 목록은 백엔드 확정 전 - 확정되면 EVIDENCE_GRADE 매핑 테이블
  // (ReportClient.tsx)만 갈아끼우면 된다. 구버전 리포트엔 필드 자체가 없어 optional.
  evidence_grade: z.string().nullable().optional(),
  location: LocationSchema,
});
export type Finding = z.infer<typeof FindingSchema>;

export const UnjudgedSchema = z.object({
  sentence: z.string(),
  location: LocationSchema,
});
export type Unjudged = z.infer<typeof UnjudgedSchema>;

export const SummarySchema = z.object({
  region: RegionSchema,
  n_sentences: z.number(),
  n_findings: z.number(),
  n_violation: z.number(),
  n_needs_review: z.number(),
  n_unjudged: z.number(),
  // OCR이 못 읽은 타일 수(백엔드 PR #259). 0보다 크면 이 리포트는 이미지 일부를
  // 못 본 상태다 - "읽었는데 문제없음"과 구분해서 화면에 알려야 한다. 이 필드
  // 이전에 저장된 옛 리포트엔 없을 수 있어 default(0).
  n_ocr_failed_tiles: z.number().default(0),
  // 백엔드는 0건인 유형의 키를 아예 안 보낸다(Counter 기반이라 자연스러운 형태,
  // 2026-08-23 zod 실측으로 확인). partialRecord라 값 없는 키는 허용하되, 키
  // 자체가 유효한 위반유형인지는 계속 검증한다(오타 유형명은 여전히 잡힘).
  counts_by_type: z.partialRecord(ViolationTypeSchema, z.number()),
});
export type Summary = z.infer<typeof SummarySchema>;

// 규제 근거 인용 (citation_registry 단일 소스에서 옴. 프론트 하드코딩 금지)
export const BasisCitationSchema = z.object({
  id: z.string(),
  law_name: z.string(),
  citation_id: z.string().nullable(),
  effective_date: z.string().nullable(),
  source_url: z.string().nullable(),
});
export type BasisCitation = z.infer<typeof BasisCitationSchema>;

export const RegulatoryBasisSchema = z.object({
  jurisdiction: RegionSchema,
  citations: z.array(BasisCitationSchema),
});
export type RegulatoryBasis = z.infer<typeof RegulatoryBasisSchema>;

export const ReplacementSchema = z.object({
  original: z.string(),
  replaced: z.string(),
  violation_type: ViolationTypeSchema,
  basis: z.string(),
  // 이 대체표현이 어느 finding에서 나왔는지(findings 배열 인덱스). 리포트 화면이
  // 카드와 짝지을 때 쓴다. original만으로는 못 짝짓는다 - 조건표 경로는 span(단어),
  // LLM 경로는 문장 전체가 들어가 키가 경로마다 달라진다. /generate 응답엔 없어 optional.
  finding_index: z.number().nullable().optional(),
  // 대체표현 자체가 실증대상일 때 붙는 고지. 없으면 null.
  note: z.string().nullable().optional(),
});
export type Replacement = z.infer<typeof ReplacementSchema>;

export const CheckReportSchema = z.object({
  findings: z.array(FindingSchema),
  unjudged: z.array(UnjudgedSchema),
  summary: SummarySchema,
  result_id: z.string().nullable(),
  // 검사 시점에 적용된 기준 스냅샷. 구버전 저장 리포트엔 없을 수 있어 optional
  basis: RegulatoryBasisSchema.nullable().optional(),
  // 지적별 대체표현. 판정할 때 배치로 같이 만들어 실려온다(PR #265). 이 필드
  // 이전에 저장된 옛 리포트엔 없을 수 있어 default([])로 받는다.
  replacements: z.array(ReplacementSchema).default([]),
});
export type CheckReport = z.infer<typeof CheckReportSchema>;



// POST /remediate 요청/응답
export const RemediationRequestSchema = z.object({
  sentence: z.string(),
  violation_type: ViolationTypeSchema,
  span: z.string().nullable().optional(),
});
export type RemediationRequest = z.infer<typeof RemediationRequestSchema>;

export const RemediationResponseSchema = z.object({
  sentence: z.string(),
  violation_type: ViolationTypeSchema,
  span: z.string(),
  suggestions: z.array(z.string()),
  disclaimer: z.string(),
});
export type RemediationResponse = z.infer<typeof RemediationResponseSchema>;

// POST /generate 관련
export const TableRowSchema = z.object({
  label: z.string(),
  value: z.string(),
});
export type TableRow = z.infer<typeof TableRowSchema>;

export const SectionSchema = z.object({
  kind: z.string(),
  text: z.string(),
  source: z.string(),
  // table_info layout_type 모듈용 구조화 데이터(제형·용량). 베베 배선 전 구버전 응답엔 없을 수 있어 optional
  table_rows: z.array(TableRowSchema).nullable().optional(),
  // 이 섹션이 채우는 layout_plan 모듈의 kind. kind와 다를 수 있다 — 위반소지 모듈
  // (hero_intro 등)의 내용은 인정문구·실증자료가 채워서 섹션 kind가 "광고문구"·"실증자료"로
  // 나온다. 이미지·layout_type은 이 값으로 먼저 찾아야 한다(구버전 응답엔 없어 optional).
  module_kind: z.string().nullable().optional(),
});
export type Section = z.infer<typeof SectionSchema>;


export const PlacedImageSchema = z.object({
  slot: z.string(),
  image_url: z.string(),
});
export type PlacedImage = z.infer<typeof PlacedImageSchema>;

export const ImageGenResultSchema = z.object({
  requested: z.boolean().default(false),
  allowed: z.boolean().nullable().optional(),
  reason: z.string().nullable().optional(),
  ai_labeled: z.boolean().default(false),
});
export type ImageGenResult = z.infer<typeof ImageGenResultSchema>;

// create 모드 모듈별 배경 이미지 생성 결과(FR-13). 텍스트는 안 굽고 프론트가 위에 얹는다.
export const ModuleImageSchema = z.object({
  module_kind: z.string(),
  status: z.enum(["generated", "skipped"]),
  reason: z.string().nullable().optional(),
  image_url: z.string().nullable().optional(),
});
export type ModuleImage = z.infer<typeof ModuleImageSchema>;

export const ImagePlanSchema = z.object({
  placed: z.array(PlacedImageSchema).default([]),
  generation: ImageGenResultSchema.default({
    requested: false,
    ai_labeled: false,
  }),
  module_images: z.array(ModuleImageSchema).default([]),
});
export type ImagePlan = z.infer<typeof ImagePlanSchema>;

export const RiskConfirmationSchema = z.object({
  id: z.string(),
  text: z.string(),
  reason: z.string(),
  requires_confirmation: z.boolean().default(true),
});
export type RiskConfirmation = z.infer<typeof RiskConfirmationSchema>;

export const RecheckSummarySchema = z.object({
  safe: z.boolean(),
  n_findings: z.number(),
  n_violation: z.number().default(0),
  n_needs_review: z.number().default(0),
});
export type RecheckSummary = z.infer<typeof RecheckSummarySchema>;

export const IngredientAmountSchema = z.object({
  name: z.string(),
  amount: z.string(),
});
export type IngredientAmount = z.infer<typeof IngredientAmountSchema>;

export const ImageGenRequestSchema = z.object({
  requested: z.boolean().default(false),
  prompt: z.string().nullable().optional(),
});
export type ImageGenRequest = z.infer<typeof ImageGenRequestSchema>;

// create 모드 전용: 사업자 입력 실증자료. barum은 진위를 검증하지 않는다(하니·PM 확정).
export const ClinicalEvidenceSchema = z.object({
  claim: z.string(),
  value: z.string(),
  institution: z.string().nullable().optional(),
  period: z.string().nullable().optional(),
  note: z.string().nullable().optional(),
});
export type ClinicalEvidence = z.infer<typeof ClinicalEvidenceSchema>;

// create 모드 전용: 사업자 입력 소비자 설문조사. 실증자료가 아니라 임상 모듈을 못 열고,
// 피부 변화(효능) 주장은 서버에서 거부되어 skipped_claims로 남는다(2026-08-20 팀장 확정).
// 6개 필드 전부 필수. 선택으로 두면 수치만 있고 출처 없는 문구를 만들어주게 된다.
export const SurveyEvidenceSchema = z.object({
  claim: z.string(),
  value: z.string(),
  sample_size: z.string(),
  institution: z.string(),
  period: z.string(),
  method: z.string(),
});
export type SurveyEvidence = z.infer<typeof SurveyEvidenceSchema>;

export const GenerateRequestSchema = z.object({
  mode: z.enum(["improve", "create"]).default("improve"),
  content: z.string().nullable().optional(),
  result_id: z.string().nullable().optional(),
  product_name: z.string().nullable().optional(),
  ingredients: z.string().nullable().optional(),
  ingredient_amounts: z.array(IngredientAmountSchema).nullable().optional(),
  certifications: z.array(z.string()).default([]),
  clinical_evidence: z.array(ClinicalEvidenceSchema).nullable().optional(),
  survey_evidence: z.array(SurveyEvidenceSchema).nullable().optional(),
  notes: z.string().nullable().optional(),
  image_generation: ImageGenRequestSchema.nullable().optional(),
  // create 모드 이미지 생성 프롬프트에 반영되는 색상톤/분위기(둘 다 선택, 자유 텍스트)
  color_tone: z.string().nullable().optional(),
  mood: z.string().nullable().optional(),
  // /uploads/product-photo로 먼저 올려 받은 photo_id들(AI 합성 참조용)
  product_photo_ids: z.array(z.string()).nullable().optional(),
  // 콘텐츠 프리셋 id(create 모드). 타겟팅·레이아웃 방향·색/무드·폰트단을 한 세트로
  // 먹인다(백엔드 content_presets.json). targeting·layout_direction을 같이 보내면
  // 그쪽이 프리셋보다 우선한다.
  preset: z.string().nullable().optional(),
  targeting: z.string().nullable().optional(),
  layout_direction: z.string().nullable().optional(),
  // 상품 스펙표(table_info 모듈)용. 둘 다 없으면 백엔드가 표 모듈 자체를 안 만든다
  // (ensure_product_spec_module) - 이 필드가 프론트에 없어서 아무도 정상 입력
  // 경로를 테스트한 적이 없었다(표 카드가 화면에서 사라지는 버그의 원인 중 하나,
  // 2026-08-23 베베 확인).
  formulation_type: z.string().nullable().optional(),
  volume: z.string().nullable().optional(),
});
export type GenerateRequest = z.infer<typeof GenerateRequestSchema>;

export const SkippedClaimSchema = z.object({
  category: z.string(),
  reason: z.string(),
});
export type SkippedClaim = z.infer<typeof SkippedClaimSchema>;

// create 모드 상세페이지 모듈 구성 계획(플래너 산출물)
export const LayoutModuleSchema = z.object({
  kind: z.string(),
  purpose: z.string(),
  has_claim_risk: z.boolean().default(false),
  // _vocabulary.json의 layout_type 12종 중 하나. 베베 배선 전 구버전 응답엔 없을 수 있어 optional
  layout_type: z.string().nullable().optional(),
});
export type LayoutModule = z.infer<typeof LayoutModuleSchema>;

export const LayoutPlanSchema = z.object({
  modules: z.array(LayoutModuleSchema).default([]),
  product_type: z.string().nullable().optional(),
  source: z.string().default("fallback"),
  // alternation | single_accent | image_led. 마찬가지로 optional(구버전 대응)
  color_system: z.string().nullable().optional(),
});
export type LayoutPlan = z.infer<typeof LayoutPlanSchema>;

// 산출물 카드 한 장. 이미지 1장 + 문장 1개(팀장 확정 2026-08-22, PR #272).
// sections·image_plan·layout_plan을 module_kind로 짝짓던 걸 백엔드가 대신 해서
// 이걸로 준다. 이 필드가 없는(길이 0) 옛 응답은 프론트가 기존 매칭 경로로 폴백한다.
export const ContentCardSchema = z.object({
  order: z.number(),
  module_kind: z.string(),
  layout_type: z.string().default("section_statement"),
  headline: z.string(),
  body: z.string().default(""),
  text: z.string(),
  text_source: z.string(),
  image_url: z.string().nullable().default(null),
  image_status: z.string().default("skipped"),
  // 실증자료 필요 고지. 있으면 화면에 반드시 같이 노출한다(빠뜨리면 사용자가
  // 위반에서 벗어난 줄 안다, 2026-08-20 팀장 지시와 같은 이유).
  note: z.string().nullable().default(null),
  // 표 카드(상품 스펙표)의 행. 문장이 아니라 표로만 이뤄진 카드가 있다 -
  // headline·body가 비어 있고 이 필드만 채워진다(PR #314, 베베). 문장 카드와
  // 같은 틀로 그리면 빈 카드처럼 보이니 렌더링에서 따로 분기해야 한다.
  table_rows: z.array(TableRowSchema).nullable().default(null),
});
export type ContentCard = z.infer<typeof ContentCardSchema>;

export const GenerateResponseSchema = z.object({
  sections: z.array(SectionSchema),
  cards: z.array(ContentCardSchema).default([]),
  replacements: z.array(ReplacementSchema),
  image_plan: ImagePlanSchema,
  pii_removed: z.array(z.string()).default([]),
  risk_confirmations: z.array(RiskConfirmationSchema).default([]),
  skipped_claims: z.array(SkippedClaimSchema).default([]),
  // create 모드 전용 모듈 구성 계획. improve 모드는 null
  layout_plan: LayoutPlanSchema.nullable().optional(),
  recheck: RecheckSummarySchema,
  disclaimer: z.string(),
});
export type GenerateResponse = z.infer<typeof GenerateResponseSchema>;

// ── 미국 프리플라이트 (POST /check/us-sunscreen) ──────────────────────────

export const USPreflightCategorySchema = z.enum([
  "OTC의약품_분류전환",
  "미국_미승인_성분",
  "성분정보_확인불가",
]);
export type USPreflightCategory = z.infer<typeof USPreflightCategorySchema>;

export const USPreflightFindingSchema = z.object({
  span: z.string(),
  sentence: z.string(),
  category: USPreflightCategorySchema,
  explanation: z.string(),
  location: LocationSchema,
});
export type USPreflightFinding = z.infer<typeof USPreflightFindingSchema>;

export const USPreflightSummarySchema = z.object({
  n_sentences: z.number(),
  n_findings: z.number(),
  counts_by_category: z.record(z.string(), z.number()),
});
export type USPreflightSummary = z.infer<typeof USPreflightSummarySchema>;

export const USPreflightReportSchema = z.object({
  findings: z.array(USPreflightFindingSchema),
  summary: USPreflightSummarySchema,
  result_id: z.string().nullable().optional(),
  disclaimer: z.string(),
});
export type USPreflightReport = z.infer<typeof USPreflightReportSchema>;

// GET /reports/{result_id} 응답 (다시 보기)
export const ReportEnvelopeSchema = z.object({
  result_id: z.string(),
  created_at: z.string(),
  region: RegionSchema,
  image_available: z.boolean(),
  report: z.union([CheckReportSchema, USPreflightReportSchema]),
});
export type ReportEnvelope = z.infer<typeof ReportEnvelopeSchema>;
