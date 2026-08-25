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
  // 재검증에서 남은 지적 원본(PR #300, 백엔드). 개수만으로는 "재검증 실패"를
  // 정확히 못 그린다 - 검토필요는 정상 동작(실증자료 요구)인데 위반과 뭉치면
  // 안 낸 위반까지 실패로 물든다(2026-08-23 팀장 실측). flag로 위반/검토필요를
  // 바로 걸러 쓴다. 예전 응답엔 없을 수 있어 default([]).
  findings: z.array(FindingSchema).default([]),
});
export type RecheckSummary = z.infer<typeof RecheckSummarySchema>;

export const IngredientAmountSchema = z.object({
  name: z.string(),
  amount: z.string(),
});
export type IngredientAmount = z.infer<typeof IngredientAmountSchema>;

// POST /uploads/ingredients 응답(엑셀·CSV·txt 파싱, 베베 계약). rows·warnings
// 둘 다 빠짐없이 넣는다 - 스키마에 필드 하나라도 빠지면 zod가 조용히 버려서
// 응답에 값이 와도 화면엔 안 뜬다(2026-08-24 나뭇잎 사진 사건과 같은 함정).
export const IngredientUploadResponseSchema = z.object({
  rows: z.array(IngredientAmountSchema).default([]),
  warnings: z.array(z.string()).default([]),
});
export type IngredientUploadResponse = z.infer<typeof IngredientUploadResponseSchema>;

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

// POST /uploads/clinical · /uploads/survey 응답. IngredientUploadResponse와 같은
// 모양이지만 warnings의 무게가 다르다 - 헤더 없는 파일은 값의 형태로 열을
// 추측해서 읽고, 어느 열을 무엇으로 읽었는지가 여기 담겨 온다. 화면에 안 띄우면
// 시험기관 자리에 시험기간이 들어가도 아무도 모른다.
// rows·warnings 둘 다 빠짐없이 넣는다(위 IngredientUploadResponseSchema 주석 참조).
export const ClinicalUploadResponseSchema = z.object({
  rows: z.array(ClinicalEvidenceSchema).default([]),
  warnings: z.array(z.string()).default([]),
});
export type ClinicalUploadResponse = z.infer<typeof ClinicalUploadResponseSchema>;

export const SurveyUploadResponseSchema = z.object({
  rows: z.array(SurveyEvidenceSchema).default([]),
  warnings: z.array(z.string()).default([]),
});
export type SurveyUploadResponse = z.infer<typeof SurveyUploadResponseSchema>;

// 리포트에서 사용자가 수용한 대체표현(models.py ApprovedReplacement). improve
// 모드에 이걸 실어 보내지 않으면 백엔드가 판정을 처음부터 다시 돌리고(비용 2배)
// 검출된 모든 위반을 치환한다 - 사용자가 리포트에서 고른 항목이 무시되고 생성
//마다 결과가 흔들린다(2026-08-23 베베 감사로 발견, 이 필드는 정확히 이 문제를
// 막으려고 설계돼 있었는데 프론트가 안 씀).
export const ApprovedReplacementSchema = z.object({
  original: z.string(),
  replaced: z.string(),
  finding_index: z.number().nullable().optional(),
  violation_type: ViolationTypeSchema.nullable().optional(),
  note: z.string().nullable().optional(),
});
export type ApprovedReplacement = z.infer<typeof ApprovedReplacementSchema>;

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
  // improve 모드 전용. 리포트에서 수용한 대체표현을 그대로 실어 보낸다 - 안
  // 보내면(None) 백엔드가 하위호환 경로로 판정을 처음부터 다시 돌린다.
  approved_replacements: z.array(ApprovedReplacementSchema).nullable().optional(),
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
  image_status: z.string().default("skipped"), // generated | skipped | placed
  // 판매자가 올린 제품사진 원본을 그대로 쓴 카드(나노바나나 재합성이 아님).
  // true면 "AI 생성" 캡션을 안 붙이고 원본으로 표시한다 - 원본은 AI가 만든 게
  // 아니라 법적 고지 대상도 아니다(PR #379, 팀장 지시 2026-08-24: 재합성이
  // 라벨을 뭉갰다 - YOURBERRY→YOUARFRAY).
  is_original: z.boolean().default(false),
  // 실증자료 필요 고지. 있으면 화면에 반드시 같이 노출한다(빠뜨리면 사용자가
  // 위반에서 벗어난 줄 안다, 2026-08-20 팀장 지시와 같은 이유).
  note: z.string().nullable().default(null),
  // 표 카드(상품 스펙표)의 행. 문장이 아니라 표로만 이뤄진 카드가 있다 -
  // headline·body가 비어 있고 이 필드만 채워진다(PR #314, 베베). 문장 카드와
  // 같은 틀로 그리면 빈 카드처럼 보이니 렌더링에서 따로 분기해야 한다.
  table_rows: z.array(TableRowSchema).nullable().default(null),
  // 실증자료 카드의 원본 입력값(Section.clinical_stat 그대로). 있으면 수치강조
  // 카드로 그린다 - layout_type이 아니라 이 필드 유무로 분기해야 한다(베베 계약,
  // models.py ContentCard.clinical_stat 참고).
  clinical_stat: ClinicalEvidenceSchema.nullable().default(null),
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

// ── 미국 수출 준비도 MVP (POST /export-readiness/us-sunscreen) ─────────────

export const ExportReadinessStatusSchema = z.enum([
  "COMPLIANT",
  "REQUIRED_CHANGE",
  "VERIFICATION_REQUIRED",
  "NOT_ASSESSED",
  "BLOCKER",
]);
export type ExportReadinessStatus = z.infer<typeof ExportReadinessStatusSchema>;

export const ExportReadinessCategorySchema = z.enum([
  "CLASSIFICATION",
  "FORMULA",
  "TESTING",
  "LABELING",
  "CLAIMS",
  "ESTABLISHMENT",
  "LISTING_IMPORT",
]);
export type ExportReadinessCategory = z.infer<typeof ExportReadinessCategorySchema>;

// 프로필·제품 입력은 MVP에서 다음 필드를 확장할 수 있도록 백엔드가 extra를
// 허용한다. 응답 스냅샷은 현재 계약 필드를 검증하되 확장 필드는 보존한다.
export const ExportProfileSchema = z.object({
  legal_manufacturer: z.any().nullable().optional(),
  manufacturer_name: z.any().nullable().optional(),
  manufacturing_site: z.any().nullable().optional(),
  manufacturing_site_address: z.any().nullable().optional(),
  contract_manufacturer: z.any().nullable().optional(),
  us_agent_name: z.any().nullable().optional(),
  us_agent_contact: z.any().nullable().optional(),
  importer_name: z.any().nullable().optional(),
  importer_contact: z.any().nullable().optional(),
  fda_establishment_registration: z.any().nullable().optional(),
  fda_establishment_registration_number: z.any().nullable().optional(),
  registration_status: z.any().nullable().optional(),
  registration_renewal_date: z.any().nullable().optional(),
  cgmp_ready: z.boolean().nullable().optional(),
  cgmp_readiness: z.any().nullable().optional(),
  drug_listing_status: z.any().nullable().optional(),
  ndc_or_listing_number: z.any().nullable().optional(),
}).passthrough();
export type ExportProfile = z.infer<typeof ExportProfileSchema>;

export const ExportProductSchema = z.object({
  intended_use: z.string().nullable().optional(),
  spf_value: z.number().nullable().optional(),
  spf_displayed: z.boolean().nullable().optional(),
  broad_spectrum: z.boolean().nullable().optional(),
  water_resistant: z.boolean().nullable().optional(),
  water_resistance_minutes: z.number().nullable().optional(),
  spf_test_report: z.boolean().nullable().optional(),
  broad_spectrum_test_report: z.boolean().nullable().optional(),
  water_resistance_test_report: z.boolean().nullable().optional(),
  spf_test_available: z.boolean().nullable().optional(),
  broad_spectrum_test_available: z.boolean().nullable().optional(),
  water_resistance_test_available: z.boolean().nullable().optional(),
  drug_facts_ready: z.boolean().nullable().optional(),
  us_label_ready: z.boolean().nullable().optional(),
  claims_reviewed: z.boolean().nullable().optional(),
  drug_listing_ready: z.boolean().nullable().optional(),
  ingredient_amounts: z.any().nullable().optional(),
  bemotrizinol_evidence_provided: z.boolean().nullable().optional(),
  bemotrizinol_confirmed_ineligible: z.boolean().nullable().optional(),
}).passthrough();
export type ExportProduct = z.infer<typeof ExportProductSchema>;

export const ReadinessItemSchema = z.object({
  id: z.string(),
  category: ExportReadinessCategorySchema,
  status: ExportReadinessStatusSchema,
  title: z.string(),
  summary: z.string(),
  next_action: z.string(),
  evidence: z.array(z.string()).default([]),
  rule_id: z.string().nullable(),
  source_id: z.string().nullable(),
  profile_based: z.boolean().default(false),
});
export type ReadinessItem = z.infer<typeof ReadinessItemSchema>;

export const ReadinessSummarySchema = z.object({
  overall_status: ExportReadinessStatusSchema,
  total: z.number(),
  counts_by_status: z.record(ExportReadinessStatusSchema, z.number()),
});
export type ReadinessSummary = z.infer<typeof ReadinessSummarySchema>;

export const USExportReadinessReportSchema = z.object({
  report_type: z.literal("us_export_readiness"),
  result_id: z.string().nullable(),
  created_at: z.string(),
  product_name: z.string().nullable(),
  profile_snapshot: ExportProfileSchema,
  product_snapshot: ExportProductSchema,
  summary: ReadinessSummarySchema,
  items: z.array(ReadinessItemSchema),
  disclaimer: z.string(),
});
export type USExportReadinessReport = z.infer<typeof USExportReadinessReportSchema>;

// ── 범용 수출 준비도 v2 (POST /export-readiness) ──────────────────────────
export const ReadinessInputStateSchema = z.enum(["PROVIDED", "NOT_AVAILABLE", "UNKNOWN", "NOT_ENTERED"]);
export type ReadinessInputState = z.infer<typeof ReadinessInputStateSchema>;

export const DomesticProductCategorySchema = z.enum([
  "skincare", "sun_care", "cleansing", "makeup", "mask_pack", "haircare", "bodycare", "fragrance", "other",
]);
export type DomesticProductCategory = z.infer<typeof DomesticProductCategorySchema>;

export const ReadinessEvidenceInputSchema = z.object({
  input_state: ReadinessInputStateSchema.default("NOT_ENTERED"),
  value: z.unknown().nullable().optional(),
  evidence: z.array(z.string()).default([]),
}).passthrough();
export type ReadinessEvidenceInput = z.infer<typeof ReadinessEvidenceInputSchema>;

export const GenericLabelEvidenceSchema = z.object({
  statement_of_identity: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  net_quantity: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  business_name_address: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  ingredient_declaration: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  english_required_information: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  adverse_event_contact: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
});
export type GenericLabelEvidence = z.infer<typeof GenericLabelEvidenceSchema>;

export const GenericProductEvidenceSchema = z.object({
  facility_registration: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  product_listing: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  safety_substantiation: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  color_additives: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  spf_test: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  broad_spectrum_test: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  water_resistance_test: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
  drug_facts_label: ReadinessEvidenceInputSchema.default({ input_state: "NOT_ENTERED", evidence: [] }),
});
export type GenericProductEvidence = z.infer<typeof GenericProductEvidenceSchema>;

export const GenericReadinessItemSchema = z.object({
  id: z.string(), category: z.string(), status: ExportReadinessStatusSchema,
  user_state: ReadinessInputStateSchema, title: z.string(), summary: z.string(),
  why_it_matters: z.string(), what_document: z.string(), how_to_find: z.string(), next_action: z.string(),
  evidence: z.array(z.string()).default([]), rule_pack_id: z.string(), source_id: z.string(), profile_based: z.boolean().default(false),
});
export type GenericReadinessItem = z.infer<typeof GenericReadinessItemSchema>;

export const ExportReadinessReportSchema = z.object({
  report_type: z.literal("export_readiness"), schema_version: z.literal("2"), result_id: z.string().nullable(), source_report_id: z.string().nullable().optional(), created_at: z.string(),
  destination_country: z.string(), domestic_category: DomesticProductCategorySchema, domestic_subcategory: z.string().nullable(), product_name: z.string().nullable(),
  product_snapshot: z.object({ intended_use: z.string().nullable().optional(), claims: z.array(z.string()).default([]), ingredients: z.array(z.string()).default([]) }).passthrough(),
  profile_status: ReadinessInputStateSchema, profile_snapshot: ExportProfileSchema,
  regulatory_route: z.object({ code: z.string(), label: z.string(), support_level: z.string(), reasons: z.array(z.string()).default([]) }),
  applied_rule_packs: z.array(z.object({ rule_pack_id: z.string(), version: z.string(), support_level: z.string() })), support_level: z.string(),
  summary: ReadinessSummarySchema,
  priority_actions: z.array(z.object({ item_id: z.string(), title: z.string(), status: ExportReadinessStatusSchema, next_action: z.string() })).max(3).default([]),
  items: z.array(GenericReadinessItemSchema), disclaimer: z.string(),
});
export type ExportReadinessReport = z.infer<typeof ExportReadinessReportSchema>;

// 국내 검사 결과에서 미국 재분석에 재사용하는 원본 입력 스냅샷
export const InputAssetSchema = z.object({
  role: z.string(),
  original_filename: z.string().nullable().optional(),
  content_type: z.string().nullable().optional(),
  sha256: z.string().nullable().optional(),
  size_bytes: z.number().nullable().optional(),
  storage_ref: z.string().nullable().optional(),
}).passthrough();
export type InputAsset = z.infer<typeof InputAssetSchema>;

export const InputSentenceSchema = z.object({
  text: z.string(),
  source: z.string(),
  order: z.number(),
  tile: z.string().nullable().optional(),
  x_start: z.number().nullable().optional(),
  x_end: z.number().nullable().optional(),
  y_start: z.number().nullable().optional(),
  y_end: z.number().nullable().optional(),
}).passthrough();
export type InputSentence = z.infer<typeof InputSentenceSchema>;

export const SnapshotIngredientAmountSchema = z.object({
  ingredient: z.string(),
  amount: z.string(),
});
export type SnapshotIngredientAmount = z.infer<typeof SnapshotIngredientAmountSchema>;

export const InputExtractionSchema = z.object({
  ocr_status: z.enum(["NOT_RUN", "COMPLETE", "PARTIAL", "FAILED"]).default("NOT_RUN"),
  ocr_failed_tiles: z.number().default(0),
}).passthrough();
export type InputExtraction = z.infer<typeof InputExtractionSchema>;

export const DomesticInputSnapshotSchema = z.object({
  schema_version: z.literal("1").default("1"),
  source_report_id: z.string().nullable().optional(),
  source_endpoint: z.string().default("/check"),
  source_region: RegionSchema.default("KR"),
  captured_at: z.string(),
  product_name: z.string().nullable().optional(),
  domestic_category: z.string().nullable().optional(),
  domestic_subcategory: z.string().nullable().optional(),
  ad_text_raw: z.string().nullable().optional(),
  ocr_sentences: z.array(InputSentenceSchema).default([]),
  ingredients_raw: z.string().nullable().optional(),
  ingredients_input_kind: z.enum(["TEXT", "FILENAME_ONLY", "MISSING"]).default("MISSING"),
  normalized_ingredients: z.array(z.string()).default([]),
  ingredient_amounts: z.array(SnapshotIngredientAmountSchema).default([]),
  assets: z.array(InputAssetSchema).default([]),
  extraction: InputExtractionSchema.default({ ocr_status: "NOT_RUN", ocr_failed_tiles: 0 }),
  warnings: z.array(z.string()).default([]),
}).passthrough();
export type DomesticInputSnapshot = z.infer<typeof DomesticInputSnapshotSchema>;

export const ReportListItemSchema = z.object({
  result_id: z.string(),
  created_at: z.string(),
  region: RegionSchema,
  product_name: z.string().nullable().optional(),
  image_available: z.boolean().default(false),
  snapshot_available: z.boolean().default(false),
  input_materials: z.array(z.string()).default([]),
}).passthrough();
export type ReportListItem = z.infer<typeof ReportListItemSchema>;

// GET /reports/{result_id} 응답 (다시 보기)
export const ReportEnvelopeSchema = z.object({
  result_id: z.string(),
  created_at: z.string(),
  region: RegionSchema,
  image_available: z.boolean(),
  // 백엔드 `StoredCheck.product_name`. 여기 안 적어두면 zod가 조용히 버린다
  // (2026-08-24). 실제로 버려져서 개선 모드가 상품명 없이 생성했고, 백엔드가
  // 상품 종류를 못 알아내(`infer_product_type` -> None) 이미지 힌트가 전부
  // 중립 폴백("잎, 물방울, 천, 돌 표면")으로 떨어졌다. 그래서 어떤 제품이든
  // 나뭇잎·대리석 사진만 나왔다.
  product_name: z.string().nullable().optional(),
  input_snapshot: DomesticInputSnapshotSchema.nullable().optional(),
  report: z.union([CheckReportSchema, USPreflightReportSchema, USExportReadinessReportSchema, ExportReadinessReportSchema]),
});
export type ReportEnvelope = z.infer<typeof ReportEnvelopeSchema>;
