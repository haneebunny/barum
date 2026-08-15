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
export const SectionSchema = z.object({
  kind: z.string(),
  text: z.string(),
  source: z.string(),
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

export const ImagePlanSchema = z.object({
  placed: z.array(PlacedImageSchema).default([]),
  generation: ImageGenResultSchema.default({
    requested: false,
    ai_labeled: false,
  }),
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

export const GenerateRequestSchema = z.object({
  mode: z.enum(["improve", "create"]).default("improve"),
  content: z.string().nullable().optional(),
  result_id: z.string().nullable().optional(),
  product_name: z.string().nullable().optional(),
  ingredients: z.string().nullable().optional(),
  ingredient_amounts: z.array(IngredientAmountSchema).nullable().optional(),
  certifications: z.array(z.string()).default([]),
  notes: z.string().nullable().optional(),
  image_generation: ImageGenRequestSchema.nullable().optional(),
});
export type GenerateRequest = z.infer<typeof GenerateRequestSchema>;

export const SkippedClaimSchema = z.object({
  category: z.string(),
  reason: z.string(),
});
export type SkippedClaim = z.infer<typeof SkippedClaimSchema>;

export const GenerateResponseSchema = z.object({
  sections: z.array(SectionSchema),
  replacements: z.array(ReplacementSchema),
  image_plan: ImagePlanSchema,
  pii_removed: z.array(z.string()).default([]),
  risk_confirmations: z.array(RiskConfirmationSchema).default([]),
  skipped_claims: z.array(SkippedClaimSchema).default([]),
  recheck: RecheckSummarySchema,
  disclaimer: z.string(),
});
export type GenerateResponse = z.infer<typeof GenerateResponseSchema>;
