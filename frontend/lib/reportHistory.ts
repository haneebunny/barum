import type { HistoryRowIconStatus } from "@/components/HistoryRow/HistoryRow";
import type { ReportListItem, Region } from "@/lib/api/schema";

export const REGION_LABEL: Record<Region, string> = { KR: "국내", US: "해외 · 미국" };

export function daysAgo(createdAt: string): number {
  const diff = Date.now() - new Date(createdAt).getTime();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

export function dateLabel(createdAt: string): string {
  const days = daysAgo(createdAt);
  if (days === 0) return "오늘";
  if (days === 1) return "어제";
  if (days < 7) return `${days}일 전`;
  if (days < 14) return "1주 전";
  if (days < 21) return "2주 전";
  return new Date(createdAt).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

export function historyHref(item: ReportListItem): string {
  return item.report_kind === "us_preflight"
    ? `/report/us/${item.result_id}`
    : `/report/${item.result_id}`;
}

export function historyRowProps(item: ReportListItem) {
  const needsReview = item.status === "review";
  const countLabel = item.report_kind === "us_preflight"
    ? `확인 필요 ${item.n_findings}건`
    : `위반 ${item.n_violation} · 검토 ${item.n_needs_review}${item.n_unjudged ? ` · 미판정 ${item.n_unjudged}` : ""}`;
  return {
    product_name: item.product_name?.trim() || "이름 없는 검사",
    region_label: REGION_LABEL[item.region],
    status_icon: item.status as HistoryRowIconStatus,
    status_label: needsReview ? "검토 필요" : "검사 완료",
    status_crit: needsReview,
    count_label: countLabel,
    count_crit: needsReview,
    score_label: undefined,
    date_label: dateLabel(item.created_at),
  };
}
