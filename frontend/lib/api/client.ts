import { z } from "zod";
import {
  RegulatoryBasisSchema,
  CheckReportSchema,
  ReportEnvelopeSchema,
  RemediationResponseSchema,
  USPreflightReportSchema,
  USExportReadinessReportSchema,
  ExportReadinessReportSchema,
  GenerateResponseSchema,
  IngredientUploadResponseSchema,
  ReportListItemSchema,
} from "./schema";
import type {
  Region,
  CheckReport,
  ReportEnvelope,
  RegulatoryBasis,
  RemediationRequest,
  RemediationResponse,
  GenerateRequest,
  GenerateResponse,
  USPreflightReport,
  ExportProfile,
  ExportProduct,
  USExportReadinessReport,
  ExportReadinessReport,
  DomesticProductCategory,
  GenericLabelEvidence,
  GenericProductEvidence,
  ReadinessInputState,
  IngredientUploadResponse,
  ReportListItem,
} from "./schema";

export interface CheckAdInput {
  region: Region;
  adText?: string;
  image?: File;
  ingredients?: string | null;
  productName?: string | null;
  domesticCategory?: DomesticProductCategory | null;
  domesticSubcategory?: string | null;
}

function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

// 응답을 스키마로 검증한다. 실패해도 화면은 안 죽인다 - 스키마와 실제 응답이
// 맞는지 지금까지 한 번도 확인된 적이 없어서(zod가 그동안 아예 안 돌고 있었다,
// 2026-08-23 콘텐츠 생성 크래시 조사), 갑자기 엄격하게 켜면 어긋난 자리마다
// 화면이 통째로 죽는다. 대신 raw 데이터를 그대로 반환하고 콘솔에 어느
// 엔드포인트·어느 필드(zod path)가 어긋났는지 구체적으로 남긴다 - 그게 이
// 검증 작업의 실제 목적이다(어긋난 자리를 처음으로 보이게 하는 것).
function validateResponse<T>(schema: z.ZodType<T>, data: unknown, endpoint: string): T {
  const result = schema.safeParse(data);
  if (result.success) return result.data;
  const issues = result.error.issues
    .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
    .join(" / ");
  console.warn(`[schema mismatch] ${endpoint} 응답이 schema.ts와 어긋남 - ${issues}`);
  return data as T;
}

export async function checkAd(input: CheckAdInput): Promise<CheckReport> {
  const url = `${getApiUrl()}/check`;
  const formData = new FormData();
  formData.append("region", input.region);
  
  if (input.adText) {
    formData.append("ad_text", input.adText);
  }
  if (input.image) {
    formData.append("image", input.image);
  }
  if (input.ingredients) {
    formData.append("ingredients", input.ingredients);
  }
  if (input.productName !== null && input.productName !== undefined) {
    formData.append("product_name", input.productName);
  }
  if (input.domesticCategory !== null && input.domesticCategory !== undefined) {
    formData.append("domestic_category", input.domesticCategory);
  }
  if (input.domesticSubcategory !== null && input.domesticSubcategory !== undefined) {
    formData.append("domestic_subcategory", input.domesticSubcategory);
  }

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API check failed: ${response.status} - ${errText}`);
  }

  return validateResponse(CheckReportSchema, await response.json(), "POST /check");
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const MOCK_REPORTS: Record<string, CheckReport> = {
  image: {
    findings: [
      {
        span: "멜라닌 생성을 억제해 미백에 도움",
        sentence: "멜라닌 생성을 억제해 미백에 도움을 줍니다.",
        violation_type: "2호_기능성오인",
        legal_basis: "화장품법 제13조 제1항 제2호 (기능성 오인)",
        legal_basis_text: "기능성화장품이 아닌 화장품을 기능성화장품으로 잘못 인식할 우려가 있거나 기능성화장품의 안전성ㆍ유효성에 관한 심사결과와 다른 내용의 표시 또는 광고",
        flag: "검토필요",
        explanation: "미백은 기능성 심사·고시원료 확인이 필요한 표현이다. 심사 근거 없이 주장하면 기능성 오인. (전성분 미입력, 성분 정합 확인 못 함)",
        confidence: null,
        source: "rule",
        // 근거 등급 배지 데모: "검토필요 + 규칙문서 확정" 조합(범례가 필요한 이유가 된 사례)
        evidence_grade: "rule_confirmed",
        location: {
          tile: "detail_000_t00.png",
          order: 0,
          x_start: 120,
          x_end: 780,
          y_start: 450,
          y_end: 580,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      {
        span: "아토피 피부염을 완화하고 손상된 피부를 재생",
        sentence: "아토피 피부염을 완화하고 손상된 피부를 재생합니다.",
        violation_type: "1호_의약품오인",
        legal_basis: "화장품법 제13조 제1항 제1호 (의약품 오인)",
        legal_basis_text: "의약품으로 잘못 인식할 우려가 있는 표시 또는 광고",
        flag: "위반",
        explanation: "질병(아토피)의 완화·재생은 의약품으로 오인될 수 있는 의학적 효능 표현이다.",
        confidence: 87,
        source: "vlm",
        // 근거 등급 배지 데모: VLM 경로 + 인용검증 통과
        evidence_grade: "citation_verified",
        location: {
          tile: "detail_000_t01.png",
          order: 2,
          x_start: 80,
          x_end: 920,
          y_start: 1850,
          y_end: 2020,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      {
        span: "시중 제품 대비 3배 빠른 흡수",
        sentence: "시중 제품 대비 3배 빠른 흡수를 자랑합니다.",
        violation_type: "5호_거짓과장기만",
        legal_basis: "화장품법 제13조 제1항 제5호 (거짓·과장·기만, 개정법 기준)",
        legal_basis_text: "그 밖에 사실과 다르게 소비자를 속이거나 소비자가 잘못 인식하도록 할 우려가 있는 표시 또는 광고",
        flag: "위반",
        explanation: "객관적 근거 없는 비교 수치(3배)는 거짓·과장 광고에 해당할 소지가 있다.",
        // 근거 등급 배지 데모: 인용검증 실패("낮은 등급=안전 아님" 확인용, 위반 flag와 짝)
        evidence_grade: "unverified",
        location: {
          tile: "detail_000_t01.png",
          order: 3,
          x_start: 220,
          x_end: 780,
          y_start: 2450,
          y_end: 2600,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      {
        span: "아토피 피부염을 완화하고 손상된 피부를 재생",
        sentence: "매일 사용으로 아토피 피부염을 완화하고 손상된 피부를 재생해보세요.",
        violation_type: "1호_의약품오인",
        legal_basis: "화장품법 제13조 제1항 제1호 (의약품 오인)",
        legal_basis_text: "의약품으로 잘못 인식할 우려가 있는 표시 또는 광고",
        flag: "위반",
        explanation: "질병(아토피)의 완화·재생은 의약품으로 오인될 수 있는 의학적 효능 표현이다.",
        location: {
          tile: "detail_000_t02.png",
          order: 4,
          x_start: 80,
          x_end: 920,
          y_start: 500,
          y_end: 650,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      // 8번 데모: 규칙 경로(좁은 span)와 VLM 경로(span=문장 전체)가 같은 문장을
      // 둘 다 finding으로 잡은 경우. sentence+violation_type 중복 제거로 규칙
      // 경로(이 항목)만 남고 바로 아래 VLM 중복은 화면에서 빠져야 한다.
      {
        span: "진정",
        sentence: "민감 피부 진정 피부과 테스트 완료로 안심하고 사용하세요.",
        violation_type: "2호_기능성오인",
        legal_basis: "화장품법 제13조 제1항 제2호 (기능성 오인)",
        legal_basis_text: "기능성화장품이 아닌 화장품을 기능성화장품으로 잘못 인식할 우려가 있거나 기능성화장품의 안전성ㆍ유효성에 관한 심사결과와 다른 내용의 표시 또는 광고",
        flag: "검토필요",
        explanation: "진정 효과는 기능성 심사 확인이 필요한 표현이다.",
        location: {
          tile: "detail_000_t02.png",
          order: 5,
          x_start: 80,
          x_end: 300,
          y_start: 1200,
          y_end: 1350,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      {
        span: "민감 피부 진정 피부과 테스트 완료로 안심하고 사용하세요.",
        sentence: "민감 피부 진정 피부과 테스트 완료로 안심하고 사용하세요.",
        violation_type: "2호_기능성오인",
        legal_basis: "화장품법 제13조 제1항 제2호 (기능성 오인)",
        legal_basis_text: "기능성화장품이 아닌 화장품을 기능성화장품으로 잘못 인식할 우려가 있거나 기능성화장품의 안전성ㆍ유효성에 관한 심사결과와 다른 내용의 표시 또는 광고",
        flag: "검토필요",
        explanation: "VLM 경로 중복 - 화면에서 가려져야 한다(사용자에겐 노출되면 안 됨).",
        location: {
          tile: "detail_000_t02.png",
          order: 5,
          x_start: 80,
          x_end: 300,
          y_start: 1200,
          y_end: 1350,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
    ],
    unjudged: [],
    summary: {
      region: "KR",
      n_sentences: 6,
      n_findings: 6,
      n_violation: 3,
      n_needs_review: 2,
      n_unjudged: 0,
      // 9번 데모: 이미지 예시는 OCR 실패 타일 1개가 있었던 것으로 표시(문구 확인용)
      n_ocr_failed_tiles: 1,
      counts_by_type: {
        "2호_기능성오인": 2,
        "1호_의약품오인": 2,
        "5호_거짓과장기만": 1,
        "합법": 0,
        "대상외": 0,
      },
    },
    result_id: "demo-image-id",
    // 지적 카드 그룹핑(팀장 확정 A안) 데모: 마지막 finding은 위 아토피 finding과
    // span+violation_type이 같다. 왼쪽 카드는 하나로 묶이고("2곳") 상단 요약(위반
    // 건수)은 원본 finding 개수(4개) 그대로 나와야 한다.
    // PR #265 데모: 판정할 때 배치로 만들어진 대체표현. finding_index=2(거짓·과장)는
    // 일부러 안 넣어 "제안할 수 없으면 제안하지 않는다" 케이스를 같이 보여준다.
    replacements: [
      {
        original: "멜라닌 생성을 억제해 미백에 도움",
        replaced: "피부 톤 정돈에 도움",
        violation_type: "2호_기능성오인",
        basis: "합법 표기 틀(조건표) 기반 대체 표현",
        finding_index: 0,
        note: null,
      },
      {
        original: "아토피 피부염을 완화하고 손상된 피부를 재생합니다.",
        replaced: "건조하고 예민한 피부에 진정 케어를 더합니다.",
        violation_type: "1호_의약품오인",
        basis: "합법 표기 틀(조건표) + 문장 다듬기",
        finding_index: 1,
        note: null,
      },
      {
        // finding_index=1과 같은 span+유형(그룹핑 데모, 위 주석). 그룹 키에
        // "대체표현 유무"가 들어가면서(2026-08-23, 상품명 그룹핑 버그 수정) 그룹
        // 대표가 아닌 쪽도 실제로 대체표현을 갖고 있어야 같은 그룹으로 묶인다 -
        // 실제 배치 생성(build_replacements)도 finding별로 도니 항상 이렇다.
        original: "매일 사용으로 아토피 피부염을 완화하고 손상된 피부를 재생해보세요.",
        replaced: "매일 사용으로 건조하고 예민한 피부에 진정 케어를 더해보세요.",
        violation_type: "1호_의약품오인",
        basis: "합법 표기 틀(조건표) + 문장 다듬기",
        finding_index: 3,
        note: null,
      },
    ] as any,
  },
  text: {
    findings: [
      {
        span: "주름을 개선하는",
        sentence: "매일 발라 주름을 개선하는 안티에이징 크림.",
        violation_type: "2호_기능성오인",
        legal_basis: "화장품법 제13조 제1항 제2호 (기능성 오인)",
        legal_basis_text: "기능성화장품이 아닌 화장품을 기능성화장품으로 잘못 인식할 우려가 있거나 기능성화장품의 안전성ㆍ유효성에 관한 심사결과와 다른 내용의 표시 또는 광고",
        flag: "검토필요",
        explanation: "주름개선은 기능성 화장품 심사가 필요한 표현이다. (전성분 미입력, 성분 정합 확인 못 함)",
        location: {
          tile: null,
          order: 0,
          y_start: null,
          y_end: null,
          source_h: null,
          source_w: null,
        } as any,
      },
      {
        span: "염증을 가라앉히고 상처를 치료",
        sentence: "트러블로 인한 염증을 가라앉히고 상처를 치료합니다.",
        violation_type: "1호_의약품오인",
        legal_basis: "화장품법 제13조 제1항 제1호 (의약품 오인)",
        legal_basis_text: "의약품으로 잘못 인식할 우려가 있는 표시 또는 광고",
        flag: "위반",
        explanation: "염증 완화·상처 치료는 의약품으로 오인될 수 있는 의학적 효능 표현이다.",
        location: {
          tile: null,
          order: 1,
          y_start: null,
          y_end: null,
          source_h: null,
          source_w: null,
        } as any,
      },
    ],
    unjudged: [],
    summary: {
      region: "KR",
      n_sentences: 3,
      n_findings: 2,
      n_violation: 1,
      n_needs_review: 1,
      n_unjudged: 0,
      n_ocr_failed_tiles: 0,
      counts_by_type: {
        "2호_기능성오인": 1,
        "1호_의약품오인": 1,
        "합법": 0,
        "5호_거짓과장기만": 0,
        "대상외": 0,
      },
    },
    result_id: "demo-text-id",
    // 이 필드 이전에 저장된 옛 리포트/생성 실패 케이스 데모: 비워두면 /remediate
    // 실시간 조회로 폴백한다.
    replacements: [],
  },
  unjudged: {
    findings: [
      {
        span: "파워 수분 공급",
        sentence: "콜라겐 함유로 파워 수분 공급.",
        violation_type: "5호_거짓과장기만",
        legal_basis: "화장품법 제13조 제1항 제5호 (거짓·과장·기만, 개정법 기준)",
        legal_basis_text: "그 밖에 사실과 다르게 소비자를 속이거나 소비자가 잘못 인식하도록 할 우려가 있는 표시 또는 광고",
        flag: "위반",
        explanation: "'파워'는 근거 없는 과장 수식으로 볼 소지가 있다.",
        location: {
          tile: "detail_002_t00.png",
          order: 0,
          y_start: 0,
          y_end: 1520,
          source_h: 8000,
          source_w: 1000,
        } as any,
      },
    ],
    unjudged: [
      {
        sentence: "7가지 한방 추출물로 피부 진정에 탁월",
        location: {
          tile: "detail_002_t00.png",
          order: 1,
          y_start: 0,
          y_end: 1520,
          source_h: 8000,
          source_w: 1000,
        } as any,
      },
      {
        sentence: "탄력 있는 피부로 가꿔주는 펩타이드 앰플",
        location: {
          tile: "detail_002_t01.png",
          order: 2,
          y_start: 1440,
          y_end: 2960,
          source_h: 8000,
          source_w: 1000,
        } as any,
      },
    ],
    summary: {
      region: "KR",
      n_sentences: 3,
      n_findings: 1,
      n_violation: 1,
      n_needs_review: 0,
      n_unjudged: 2,
      n_ocr_failed_tiles: 0,
      counts_by_type: {
        "5호_거짓과장기만": 1,
        "합법": 0,
        "1호_의약품오인": 0,
        "2호_기능성오인": 0,
        "대상외": 0,
      },
    },
    result_id: "demo-unjudged-id",
    replacements: [],
  },
};

export async function getReport(resultId: string): Promise<ReportEnvelope> {
  const isMock =
    resultId === "demo-image-id" ||
    resultId === "image" ||
    resultId === "demo-id-1" ||
    resultId === "demo-id-3" ||
    resultId === "demo-text-id" ||
    resultId === "text" ||
    resultId === "demo-id-2" ||
    resultId === "demo-id-4" ||
    resultId === "demo-unjudged-id" ||
    resultId === "unjudged" ||
    resultId === "a3Fk9mdemo" ||
    resultId === "demo-id-5";

  if (isMock) {
    let report: CheckReport;
    if (resultId.includes("text") || resultId === "text" || resultId === "demo-id-2" || resultId === "demo-id-4") {
      report = MOCK_REPORTS.text;
    } else if (resultId.includes("unjudged") || resultId === "unjudged" || resultId === "a3Fk9mdemo" || resultId === "demo-id-5") {
      report = MOCK_REPORTS.unjudged;
    } else {
      report = MOCK_REPORTS.image;
    }
    return {
      result_id: resultId,
      created_at: new Date().toISOString(),
      region: resultId === "demo-id-1" ? "US" : report.summary.region,
      image_available:
        resultId.includes("image") ||
        resultId.includes("unjudged") ||
        resultId === "a3Fk9mdemo" ||
        resultId === "image" ||
        resultId === "demo-id-1" ||
        resultId === "demo-id-3" ||
        resultId === "demo-id-5",
      report,
    };
  }

  const url = `${getApiUrl()}/reports/${resultId}`;
  const response = await fetch(url);

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Failed to fetch report (id=${resultId}): ${response.status} - ${errText}`);
  }

  return validateResponse(ReportEnvelopeSchema, await response.json(), `GET /reports/${resultId}`);
}

export async function getReports(region: Region = "KR", limit = 50): Promise<ReportListItem[]> {
  const params = new URLSearchParams({ region, limit: String(limit) });
  const response = await fetch(`${getApiUrl()}/reports?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch reports (${region}): ${response.status} - ${await response.text()}`);
  }
  return validateResponse(z.array(ReportListItemSchema), await response.json(), `GET /reports?region=${region}`);
}

export interface ExportReadinessFromReportInput {
  domestic_category?: DomesticProductCategory | null;
  domestic_subcategory?: string | null;
  profile_state?: ReadinessInputState;
  profile?: ExportProfile;
}

export async function createExportReadinessFromReport(
  resultId: string,
  input: ExportReadinessFromReportInput,
): Promise<ExportReadinessReport> {
  const response = await fetch(`${getApiUrl()}/reports/${resultId}/export-readiness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const body = await response.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: { code?: string; message?: string } | string };
      if (typeof parsed.detail === "object" && parsed.detail !== null) {
        detail = `${parsed.detail.code ? `${parsed.detail.code}: ` : ""}${parsed.detail.message || body}`;
      } else if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      }
    } catch {
      // 서버가 JSON이 아닌 오류 본문을 반환해도 원문을 안내한다.
    }
    throw new Error(`Saved domestic report reuse failed: ${response.status} - ${detail}`);
  }
  return validateResponse(ExportReadinessReportSchema, await response.json(), `POST /reports/${resultId}/export-readiness`);
}

export function getReportImageUrl(resultId: string): string {
  return `${getApiUrl()}/reports/${resultId}/image`;
}

// 백엔드가 절대 URL(외부 스토리지)이나 백엔드 상대 경로("/..." 프록시 라우트) 중
// 어느 쪽으로 image_url을 줘도 그대로 쓸 수 있게 정규화한다.
export function resolveImageUrl(url: string): string {
  if (/^https?:\/\//.test(url)) {
    return url;
  }
  return `${getApiUrl()}${url.startsWith("/") ? "" : "/"}${url}`;
}

// 지금 시점 적용 기준 (푸터 등 검사 이력 없는 화면용). 리포트 화면은 report.basis(검사 시점 스냅샷)를 쓴다
export async function getReferenceBasis(): Promise<Record<string, RegulatoryBasis>> {
  const url = `${getApiUrl()}/reference/basis`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Reference basis fetch failed: ${response.status}`);
  }
  const data = await response.json();
  return validateResponse(z.record(z.string(), RegulatoryBasisSchema), data, "GET /reference/basis");
}

const HealthResponseSchema = z.object({ status: z.string() });

export async function health(): Promise<{ status: string }> {
  const url = `${getApiUrl()}/health`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return validateResponse(HealthResponseSchema, await response.json(), "GET /health");
}

export async function getRemediation(req: RemediationRequest): Promise<RemediationResponse> {
  const url = `${getApiUrl()}/remediate`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Failed to remediate: ${response.status} - ${errText}`);
  }

  return validateResponse(RemediationResponseSchema, await response.json(), "POST /remediate");
}

export interface CheckUSPreflightInput {
  adText?: string;
  image?: File;
  ingredients?: string;
  productName?: string;
}

export async function checkUSPreflight(input: CheckUSPreflightInput): Promise<USPreflightReport> {
  const url = `${getApiUrl()}/check/us-sunscreen`;
  const formData = new FormData();
  formData.append("country", "US");

  if (input.adText) {
    formData.append("ad_text", input.adText);
  }
  if (input.image) {
    formData.append("image", input.image);
  }
  if (input.ingredients) {
    formData.append("ingredients", input.ingredients);
  }
  if (input.productName) {
    formData.append("product_name", input.productName);
  }

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`US preflight check failed: ${response.status} - ${errText}`);
  }

  return validateResponse(USPreflightReportSchema, await response.json(), "POST /check/us-sunscreen");
}

export interface USExportReadinessInput {
  adText?: string;
  image?: File;
  ingredients?: string;
  productName?: string;
  product: ExportProduct;
  profile: ExportProfile;
}

export async function createUSExportReadiness(
  input: USExportReadinessInput,
): Promise<USExportReadinessReport> {
  const url = `${getApiUrl()}/export-readiness/us-sunscreen`;
  const formData = new FormData();
  formData.append("country", "US");

  if (input.adText) formData.append("ad_text", input.adText);
  if (input.image) formData.append("image", input.image);
  if (input.ingredients) formData.append("ingredients", input.ingredients);
  if (input.productName) formData.append("product_name", input.productName);
  formData.append("product", JSON.stringify(input.product));
  formData.append("profile", JSON.stringify(input.profile));

  const response = await fetch(url, { method: "POST", body: formData });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`US export readiness check failed: ${response.status} - ${errText}`);
  }

  return validateResponse(
    USExportReadinessReportSchema,
    await response.json(),
    "POST /export-readiness/us-sunscreen",
  );
}

export interface ExportReadinessInput {
  destination_country: "US";
  domestic_category: DomesticProductCategory;
  domestic_subcategory?: string | null;
  product_name?: string | null;
  intended_use?: string | null;
  claims: string[];
  ingredients: string[];
  label_evidence: GenericLabelEvidence;
  product_evidence: GenericProductEvidence;
  profile_state: ReadinessInputState;
  profile: ExportProfile;
}

export async function createExportReadiness(input: ExportReadinessInput): Promise<ExportReadinessReport> {
  const response = await fetch(`${getApiUrl()}/export-readiness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`Export readiness check failed: ${response.status} - ${await response.text()}`);
  }
  return validateResponse(ExportReadinessReportSchema, await response.json(), "POST /export-readiness");
}

export async function getUSExportReadiness(resultId: string): Promise<USExportReadinessReport | ExportReadinessReport> {
  const url = `${getApiUrl()}/reports/${resultId}/readiness`;
  const response = await fetch(url);
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Failed to fetch US export readiness (id=${resultId}): ${response.status} - ${errText}`);
  }

  return validateResponse(
    z.union([USExportReadinessReportSchema, ExportReadinessReportSchema]),
    await response.json(),
    `GET /reports/${resultId}/readiness`,
  );
}

const UploadProductPhotoResponseSchema = z.object({ photo_id: z.string() });

export async function uploadProductPhoto(file: File): Promise<{ photo_id: string }> {
  const url = `${getApiUrl()}/uploads/product-photo`;
  const formData = new FormData();
  formData.append("photo", file);

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Failed to upload product photo: ${response.status} - ${errText}`);
  }

  return validateResponse(
    UploadProductPhotoResponseSchema,
    await response.json(),
    "POST /uploads/product-photo"
  );
}

// 전성분+함량 손입력이 20~30개면 지옥이라, 엑셀·CSV·txt로 한 번에 올리면
// 백엔드(openpyxl)가 파싱해서 rows로 돌려준다(팀장 지시, 2026-08-24).
export async function uploadIngredients(file: File): Promise<IngredientUploadResponse> {
  const url = `${getApiUrl()}/uploads/ingredients`;
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    // 415(형식 불량)·422(빈 파일·파싱 불가)·413(5MB 초과) 전부 detail에 사람이
    // 읽을 이유를 담아 보낸다(백엔드 계약, 2026-08-24) - 그대로 화면에 쓴다.
    // JSON이 아니거나 detail이 없는 응답(프록시 에러 등)만 일반 문구로 폴백.
    let detail = `업로드에 실패했습니다 (${response.status}).`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // JSON 파싱 실패 시 기본 문구 그대로
    }
    throw new Error(detail);
  }

  return validateResponse(
    IngredientUploadResponseSchema,
    await response.json(),
    "POST /uploads/ingredients"
  );
}

export async function generateContent(req: GenerateRequest): Promise<GenerateResponse> {
  const url = `${getApiUrl()}/generate`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Failed to generate content: ${response.status} - ${errText}`);
  }

  return validateResponse(GenerateResponseSchema, await response.json(), "POST /generate");
}
