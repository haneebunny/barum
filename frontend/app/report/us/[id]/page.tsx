import { USReportClient } from "./USReportClient";

export default async function USReportPage({ params }: PageProps<"/report/us/[id]">) {
  const { id } = await params;
  return <USReportClient resultId={id} />;
}
