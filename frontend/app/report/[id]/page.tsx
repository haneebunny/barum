import { getReport } from "@/lib/api/client";
import { CheckReportSchema, type ReportEnvelope } from "@/lib/api/schema";
import { ReportClient } from "./ReportClient";

export default async function ReportPage({ params }: PageProps<"/report/[id]">) {
  const { id } = await params;
  let envelope: ReportEnvelope;
  try {
    envelope = await getReport(id);
  } catch (error) {
    return (
      <div className="mono" style={{ padding: "24px", color: "var(--crit)" }}>
        <h1>리포트를 불러오는 중 오류가 발생했습니다.</h1>
        <p>요청 ID: {id}</p>
        <p>에러: {error instanceof Error ? error.message : String(error)}</p>
      </div>
    );
  }

  const parsedReport = CheckReportSchema.safeParse(envelope.report);
  if (envelope.region !== "KR" || !parsedReport.success) {
    return (
      <div className="mono" style={{ padding: "24px", color: "var(--crit)" }}>
        <h1>국내 검사 리포트 형식이 아닙니다.</h1>
        <p>요청 ID: {id}</p>
      </div>
    );
  }

  return <ReportClient envelope={{ ...envelope, report: parsedReport.data }} />;
}
