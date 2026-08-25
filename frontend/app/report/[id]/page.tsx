import { getReport } from "@/lib/api/client";
import { CheckReportSchema, type ReportEnvelope } from "@/lib/api/schema";
import { ReportClient } from "./ReportClient";
import { DEMO_RESULT_ID } from "@/lib/demo/demo";
import demoReport from "@/lib/demo/fixtures/report.json";

export default async function ReportPage({ params }: PageProps<"/report/[id]">) {
  const { id } = await params;

  // 데모(유어베리): 백엔드 대신 커밋된 픽스처를 그대로 렌더한다(백엔드/Supabase 의존 0).
  if (id === DEMO_RESULT_ID) {
    const demoEnv = demoReport as unknown as ReportEnvelope & { demo_corrections?: unknown };
    const parsed = CheckReportSchema.safeParse(demoEnv.report);
    if (parsed.success) {
      return <ReportClient envelope={{ ...demoEnv, report: parsed.data }} />;
    }
  }

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
