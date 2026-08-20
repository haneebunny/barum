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
  counts_by_type: z.record(ViolationTypeSchema, z.number()),
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

export const CheckReportSchema = z.object({
  findings: z.array(FindingSchema),
  unjudged: z.array(UnjudgedSchema),
  summary: SummarySchema,
  result_id: z.string().nullable(),
  // 검사 시점에 적용된 기준 스냅샷. 구버전 저장 리포트엔 없을 수 있어 optional
  basis: RegulatoryBasisSchema.nullable().optional(),
});
export type CheckReport = z.infer<typeof CheckReportSchema>;

// GET /reports/{result_id} 응답 (다시 보기)
export const ReportEnvelopeSchema = z.object({
  result_id: z.string(),
  created_at: z.string(),
  region: RegionSchema,
  image_available: z.boolean(),
  report: CheckReportSchema,
});
export type ReportEnvelope = z.infer<typeof ReportEnvelopeSchema>;

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

export const ReplacementSchema = z.object({
  original: z.string(),
  replaced: z.string(),
  violation_type: ViolationTypeSchema,
  basis: z.string(),
});
export type Replacement = z.infer<typeof ReplacementSchema>;

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

export const GenerateResponseSchema = z.object({
  sections: z.array(SectionSchema),
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
