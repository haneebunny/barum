import type {
  Region,
  CheckReport,
  ReportEnvelope,
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

export async function getReport(resultId: string): Promise<ReportEnvelope> {
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
