export default async function ReportPage({ params }: PageProps<"/report/[id]">) {
  const { id } = await params;
  return (
    <p className="mono" style={{ padding: "24px" }}>
      리포트 {id} — barum-report.html 목업 나오면 채움
    </p>
  );
}
