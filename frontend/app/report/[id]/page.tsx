import { getReport } from "@/lib/api/client";
import { ReportClient } from "./ReportClient";

export default async function ReportPage({ params }: PageProps<"/report/[id]">) {
  const { id } = await params;
  try {
    const envelope = await getReport(id);
    return <ReportClient envelope={envelope} />;
  } catch (error) {
    return (
      <div className="mono" style={{ padding: "24px", color: "var(--crit)" }}>
        <h1>리포트를 불러오는 중 오류가 발생했습니다.</h1>
        <p>요청 ID: {id}</p>
        <p>에러: {error instanceof Error ? error.message : String(error)}</p>
      </div>
    );
  }
}
