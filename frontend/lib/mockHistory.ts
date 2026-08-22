/**
 * 검사 이력 데모(mock) 단일 소스.
 * history/mypage/home 세 화면이 같은 result_id를 각자 따로 하드코딩하면서 내용이 어긋났던 문제(2026-08-22) 이후
 * 여기 하나로 모은다. API가 생기면 이 파일을 GET /reports 응답으로 교체한다.
 */

import type { Region } from "@/lib/api/schema";
import type { HistoryRowIconStatus } from "@/components/HistoryRow/HistoryRow";

export type HistoryStatus = "review" | "done" | "draft";

export interface MockHistoryItem {
  result_id: string;
  created_at: string;
  region: Region;
  product_name: string;
  n_violation: number;
  n_needs_review: number;
  status: HistoryStatus;
  score: number | null;
}

export const REGION_LABEL: Record<Region, string> = { KR: "국내", US: "해외 · 미국" };

// DESIGN.md §1: 빨강 = 위반·검토 필요. 나머지 상태(작성중·완료)는 회색.
export const STATUS_META: Record<HistoryStatus, { label: string; crit: boolean }> = {
  review: { label: "검토 필요", crit: true },
  done: { label: "검사 완료", crit: false },
  draft: { label: "작성중", crit: false },
};

export function daysAgo(created_at: string): number {
  const diff = Date.now() - new Date(created_at).getTime();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

export function dateLabel(created_at: string): string {
  const d = daysAgo(created_at);
  if (d === 0) return "오늘";
  if (d === 1) return "어제";
  if (d < 7) return `${d}일 전`;
  if (d < 14) return "1주 전";
  if (d < 21) return "2주 전";
  return new Date(created_at).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

function isoDate(daysBack: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysBack);
  return d.toISOString();
}

export const MOCK_HISTORY: MockHistoryItem[] = [
  { result_id: "demo-id-1", created_at: isoDate(0), region: "US", product_name: "글로우 세럼 상세페이지", n_violation: 1, n_needs_review: 1, status: "review", score: 62 },
  { result_id: "demo-id-2", created_at: isoDate(2), region: "KR", product_name: "수분 크림 리뉴얼 상세페이지", n_violation: 0, n_needs_review: 0, status: "done", score: 98 },
  { result_id: "demo-id-3", created_at: isoDate(1), region: "US", product_name: "선크림 SPF50 신제품", n_violation: 0, n_needs_review: 0, status: "draft", score: null },
  { result_id: "demo-id-4", created_at: isoDate(4), region: "KR", product_name: "탄력 앰플 SNS 광고 문구", n_violation: 2, n_needs_review: 1, status: "review", score: 41 },
  { result_id: "demo-id-5", created_at: isoDate(6), region: "KR", product_name: "클렌징 폼 상세페이지 v2", n_violation: 0, n_needs_review: 0, status: "done", score: 95 },
  { result_id: "demo-id-6", created_at: isoDate(10), region: "KR", product_name: "미백 크림 패키지 문구", n_violation: 1, n_needs_review: 0, status: "review", score: 70 },
  { result_id: "demo-id-7", created_at: isoDate(14), region: "KR", product_name: "진정 토너 상세페이지", n_violation: 0, n_needs_review: 0, status: "done", score: 100 },
  { result_id: "demo-id-8", created_at: isoDate(18), region: "US", product_name: "아이크림 리뉴얼 초안", n_violation: 0, n_needs_review: 0, status: "done", score: 88 },
];

/** 최근 N건 미리보기용 정렬(최신순). history 전체 목록은 원래 순서를 그대로 쓴다. */
export function recentHistory(count: number): MockHistoryItem[] {
  return [...MOCK_HISTORY].sort((a, b) => daysAgo(a.created_at) - daysAgo(b.created_at)).slice(0, count);
}

/**
 * MockHistoryItem 하나를 <HistoryRow>에 그대로 뿌릴 수 있는 props로 바꾼다.
 * history/mypage/home 셋 다 이 함수 하나로 행을 만든다. 화면마다 따로 파생하면서 벌어졌던
 * 표시 차이(2026-08-22, mypage만 위반 건수가 안 보이던 문제)를 근본적으로 막는다.
 * 화면별로 다른 건 "몇 건을 보여줄지"와 href/잠금 여부뿐, 행 하나의 모양은 항상 동일하다.
 */
export function rowProps(item: MockHistoryItem) {
  const meta = STATUS_META[item.status];
  return {
    product_name: item.product_name,
    region_label: REGION_LABEL[item.region],
    status_icon: item.status as HistoryRowIconStatus,
    status_label: meta.label,
    status_crit: meta.crit,
    count_label: item.status === "draft" ? "검사 전" : `위반 ${item.n_violation} · 검토 ${item.n_needs_review}`,
    count_crit: item.n_violation > 0,
    score_label: item.score === null ? undefined : `점수 ${item.score}점`,
    date_label: dateLabel(item.created_at),
  };
}
