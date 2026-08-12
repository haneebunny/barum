import type { Region, CheckReport, ReportEnvelope } from "./schema";

// POST /check 함수 시그니처만. 실제 fetch 구현은 홈·검사 페이지 착수 턴에서 채움.
export interface CheckAdInput {
  region: Region;
  adText?: string;
  image?: File;
  ingredients?: string;
}

export async function checkAd(input: CheckAdInput): Promise<CheckReport> {
  throw new Error(`checkAd not implemented (region=${input.region})`);
}

export async function getReport(resultId: string): Promise<ReportEnvelope> {
  throw new Error(`getReport not implemented (resultId=${resultId})`);
}

export function getReportImageUrl(resultId: string): string {
  throw new Error(`getReportImageUrl not implemented (resultId=${resultId})`);
}

export async function health(): Promise<{ status: string }> {
  throw new Error("health not implemented");
}
