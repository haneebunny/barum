import { USPreflightReportSchema } from "@/lib/api/schema";
import {
  DEMO_US_SUNSCREEN_DETAIL_IMAGE,
  isDemoUSReportId,
} from "@/lib/demo/demo";
import demoUSSunscreenReport from "@/lib/demo/fixtures/us-sunscreen-report.json";
import { USReportClient } from "./USReportClient";

export default async function USReportPage({ params }: PageProps<"/report/us/[id]">) {
  const { id } = await params;

  if (isDemoUSReportId(id)) {
    const report = USPreflightReportSchema.parse(demoUSSunscreenReport);
    return (
      <USReportClient
        resultId={id}
        initialReport={report}
        demoImageUrl={DEMO_US_SUNSCREEN_DETAIL_IMAGE}
        demoUnlocked
      />
    );
  }

  return <USReportClient resultId={id} />;
}
