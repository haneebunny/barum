import { z } from "zod";
import { RegulatoryBasisSchema } from "./schema";
import type {
  Region,
  CheckReport,
  ReportEnvelope,
  RegulatoryBasis,
  RemediationRequest,
  RemediationResponse,
  GenerateRequest,
  GenerateResponse,
} from "./schema";

export interface CheckAdInput {
  region: Region;
  adText?: string;
  image?: File;
  ingredients?: string;
  productName?: string;
}

function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
  if (input.productName) {
    formData.append("product_name", input.productName);
  }

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API check failed: ${response.status} - ${errText}`);
  }

  return response.json();
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
        flag: "검토필요",
        explanation: "미백은 기능성 심사·고시원료 확인이 필요한 표현이다. 심사 근거 없이 주장하면 기능성 오인. (전성분 미입력, 성분 정합 확인 못 함)",
        location: {
          tile: "detail_000_t00.png",
          order: 0,
          y_start: 0,
          y_end: 1480,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      {
        span: "아토피 피부염을 완화하고 손상된 피부를 재생",
        sentence: "아토피 피부염을 완화하고 손상된 피부를 재생합니다.",
        violation_type: "1호_의약품오인",
        legal_basis: "화장품법 제13조 제1항 제1호 (의약품 오인)",
        flag: "위반",
        explanation: "질병(아토피)의 완화·재생은 의약품으로 오인될 수 있는 의학적 효능 표현이다.",
        location: {
          tile: "detail_000_t01.png",
          order: 2,
          y_start: 1400,
          y_end: 2900,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
      {
        span: "시중 제품 대비 3배 빠른 흡수",
        sentence: "시중 제품 대비 3배 빠른 흡수를 자랑합니다.",
        violation_type: "5호_거짓과장기만",
        legal_basis: "화장품법 제13조 제1항 제5호 (거짓·과장·기만, 개정법 기준)",
        flag: "위반",
        explanation: "객관적 근거 없는 비교 수치(3배)는 거짓·과장 광고에 해당할 소지가 있다.",
        location: {
          tile: "detail_000_t01.png",
          order: 3,
          y_start: 1400,
          y_end: 2900,
          source_h: 9000,
          source_w: 1000,
        } as any,
      },
    ],
    unjudged: [],
    summary: {
      region: "KR",
      n_sentences: 5,
      n_findings: 3,
      n_violation: 2,
      n_needs_review: 1,
      n_unjudged: 0,
      counts_by_type: {
        "2호_기능성오인": 1,
        "1호_의약품오인": 1,
        "5호_거짓과장기만": 1,
        "합법": 0,
        "대상외": 0,
      },
    },
    result_id: "demo-image-id",
  },
  text: {
    findings: [
      {
        span: "주름을 개선하는",
        sentence: "매일 발라 주름을 개선하는 안티에이징 크림.",
        violation_type: "2호_기능성오인",
        legal_basis: "화장품법 제13조 제1항 제2호 (기능성 오인)",
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
      counts_by_type: {
        "2호_기능성오인": 1,
        "1호_의약품오인": 1,
        "합법": 0,
        "5호_거짓과장기만": 0,
        "대상외": 0,
      },
    },
    result_id: "demo-text-id",
  },
  unjudged: {
    findings: [
      {
        span: "파워 수분 공급",
        sentence: "콜라겐 함유로 파워 수분 공급.",
        violation_type: "5호_거짓과장기만",
        legal_basis: "화장품법 제13조 제1항 제5호 (거짓·과장·기만, 개정법 기준)",
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
      counts_by_type: {
        "5호_거짓과장기만": 1,
        "합법": 0,
        "1호_의약품오인": 0,
        "2호_기능성오인": 0,
        "대상외": 0,
      },
    },
    result_id: "demo-unjudged-id",
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

  return response.json();
}

export function getReportImageUrl(resultId: string): string {
  return `${getApiUrl()}/reports/${resultId}/image`;
}

// 지금 시점 적용 기준 (푸터 등 검사 이력 없는 화면용). 리포트 화면은 report.basis(검사 시점 스냅샷)를 쓴다
export async function getReferenceBasis(): Promise<Record<string, RegulatoryBasis>> {
  const url = `${getApiUrl()}/reference/basis`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Reference basis fetch failed: ${response.status}`);
  }
  const data = await response.json();
  return z.record(z.string(), RegulatoryBasisSchema).parse(data);
}

export async function health(): Promise<{ status: string }> {
  const url = `${getApiUrl()}/health`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
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

  return response.json();
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

  return response.json();
}
