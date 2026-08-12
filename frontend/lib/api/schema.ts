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

export const CheckReportSchema = z.object({
  findings: z.array(FindingSchema),
  unjudged: z.array(UnjudgedSchema),
  summary: SummarySchema,
  result_id: z.string().nullable(),
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
