"use client";

/**
 * 검사 이력 페이지.
 *
 * - Pro 현황 스트립: stat 타일 3개. non-Pro는 잠금 티저(블러+자물쇠, 완전 숨김 아님)
 * - Free 티어: 7일 이전 행 잠금 티저 (Basic부터 무제한 보관)
 * - 티어 스위처는 목업 전용(데모 장치)
 * - 데이터: mock을 StoredCheck 구조에 맞춤. API가 생기면 MOCK_HISTORY를
 *   GET /reports 목록 응답으로 교체하고 필터를 쿼리 파라미터로 옮긴다.
 */

import Link from "next/link";
import { useState } from "react";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { useTier, type Tier } from "@/lib/tier";
import type { Region } from "@/lib/api/schema";

type RowStatus = "review" | "done" | "draft";

interface HistoryItem {
  result_id: string;
  created_at: string;
  region: Region;
  image_available: boolean;
  product_name: string;
  report: {
    summary: {
      n_violation: number;
      n_needs_review: number;
    };
  };
  status: RowStatus;
  score: number | null;
}

const REGION_LABEL: Record<Region, string> = { KR: "국내", US: "해외 · 미국" };

function daysAgo(created_at: string): number {
  const diff = Date.now() - new Date(created_at).getTime();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

function dateLabel(created_at: string): string {
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

const MOCK_HISTORY: HistoryItem[] = [
  { result_id: "demo-id-1", created_at: isoDate(0), region: "US", image_available: true, product_name: "글로우 세럼 · 미국 상세페이지", report: { summary: { n_violation: 1, n_needs_review: 1 } }, status: "review", score: 62 },
  { result_id: "demo-id-2", created_at: isoDate(2), region: "KR", image_available: true, product_name: "수분 크림 리뉴얼 상세페이지", report: { summary: { n_violation: 0, n_needs_review: 0 } }, status: "done", score: 98 },
  { result_id: "demo-id-3", created_at: isoDate(1), region: "US", image_available: false, product_name: "선크림 SPF50 신제품", report: { summary: { n_violation: 0, n_needs_review: 0 } }, status: "draft", score: null },
  { result_id: "demo-id-4", created_at: isoDate(4), region: "KR", image_available: true, product_name: "탄력 앰플 SNS 광고 문구", report: { summary: { n_violation: 2, n_needs_review: 1 } }, status: "review", score: 41 },
  { result_id: "demo-id-5", created_at: isoDate(6), region: "KR", image_available: true, product_name: "클렌징 폼 상세페이지 v2", report: { summary: { n_violation: 0, n_needs_review: 0 } }, status: "done", score: 95 },
  { result_id: "demo-id-6", created_at: isoDate(10), region: "KR", image_available: true, product_name: "미백 크림 패키지 문구", report: { summary: { n_violation: 1, n_needs_review: 0 } }, status: "review", score: 70 },
  { result_id: "demo-id-7", created_at: isoDate(14), region: "KR", image_available: true, product_name: "진정 토너 상세페이지", report: { summary: { n_violation: 0, n_needs_review: 0 } }, status: "done", score: 100 },
  { result_id: "demo-id-8", created_at: isoDate(18), region: "US", image_available: true, product_name: "아이크림 리뉴얼 초안", report: { summary: { n_violation: 0, n_needs_review: 0 } }, status: "done", score: 88 },
];

const MOCK_STATS = [
  { value: "24", unit: "건", label: "이번 달 검사", sub: "지난달 대비 +6건" },
  { value: "9", unit: "건", label: "위반 검출", sub: "검토필요 별도 4건", crit: true },
  { value: "78", unit: "%", label: "권고안 적용률", sub: "적용 후 평균 96점" },
];

const STATUS_META: Record<RowStatus, { label: string; crit: boolean }> = {
  review: { label: "검토 필요", crit: false },
  done: { label: "검사 완료", crit: false },
  draft: { label: "작성중", crit: false },
};

function StatusIcon({ status }: { status: RowStatus }) {
  if (status === "review") {
    return (
      <svg className="w-3.25 h-3.25 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
        <path d="M12 3 2 20h20L12 3z" />
        <path d="M12 10v4M12 17v.5" />
      </svg>
    );
  }
  if (status === "done") {
    return (
      <svg className="w-3.25 h-3.25 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
        <path d="M4 12l5 5L20 6" />
      </svg>
    );
  }
  return (
    <svg className="w-3.25 h-3.25 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="square">
      <path d="M12 20h9" />
      <path d="M14 4l6 6L8 22H2v-6L14 4z" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
      <rect x={5} y={11} width={14} height={9} />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

const REGION_FILTERS = ["전체", "국내", "해외"] as const;
const STATUS_FILTERS = [
  { key: "all", label: "전체" },
  { key: "review", label: "검토 필요" },
  { key: "done", label: "검사 완료" },
  { key: "draft", label: "작성중" },
] as const;
const PERIOD_FILTERS = [
  { key: 9999, label: "전체 기간" },
  { key: 7, label: "최근 7일" },
  { key: 30, label: "최근 30일" },
] as const;

export default function HistoryPage() {
  const { tier, setTier } = useTier();
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<(typeof REGION_FILTERS)[number]>("전체");
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]["key"]>("all");
  const [period, setPeriod] = useState<number>(9999);

  const rows = MOCK_HISTORY.filter(row => {
    if (query && !row.product_name.includes(query.trim())) return false;
    const rl = REGION_LABEL[row.region];
    if (region !== "전체" && !rl.startsWith(region)) return false;
    if (status !== "all" && row.status !== status) return false;
    if (daysAgo(row.created_at) > period) return false;
    return true;
  });

  const isLockedRow = (row: HistoryItem) => tier === "Free" && daysAgo(row.created_at) > 7;
  const filterPill = (active: boolean) =>
    `font-mono text-[11px] p-[4px_9px] border cursor-pointer transition-all duration-[120ms] ${
      active
        ? "border-[var(--ink-3)] text-[var(--ink)] bg-[var(--nav-active-bg)] font-bold"
        : "border-[var(--line-2)] text-[var(--ink-3)] bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
    }`;

  const rowHref = (row: HistoryItem) =>
    row.status === "draft" ? `/inspect?id=${row.result_id}` : `/report/${row.result_id}`;

  return (
    <>
      {/* 페이지 헤더 */}
      <div className="p-[30px_22px_8px]">
        <div className="flex items-center gap-3">
          <h1 className="m-0 text-[var(--ink)] text-[22px] font-extrabold tracking-[-0.5px]">검사 이력</h1>
          <span className="font-mono text-[11px] text-[var(--ink-3)]">총 {MOCK_HISTORY.length}건 · 최근 30일</span>
          <span className="ml-auto inline-flex items-center gap-[6px] font-mono text-[10.5px] text-[var(--ink-3)]">
            티어 미리보기
            {(["Free", "Basic", "Pro"] as Tier[]).map(t => (
              <button key={t} type="button" onClick={() => setTier(t)} className={filterPill(tier === t)}>
                {t}
              </button>
            ))}
          </span>
        </div>
      </div>

      {/* Pro 현황 스트립 */}
      <div className="p-[14px_22px_4px]">
        <div className="relative">
          <div className={`grid grid-cols-3 border border-[var(--line-2)] bg-[var(--surface)] ${tier === "Pro" ? "" : "blur-[3px] select-none pointer-events-none"}`} aria-hidden={tier !== "Pro"}>
            {MOCK_STATS.map((s, i) => (
              <div key={s.label} className={`p-[16px_20px] ${i < 2 ? "border-r border-[var(--line)]" : ""}`}>
                <div className={`text-[24px] font-mono font-bold [font-variant-numeric:tabular-nums] ${s.crit ? "text-[var(--crit)]" : "text-[var(--ink)]"}`}>
                  {s.value}
                  <span className="text-[12px] font-semibold text-[var(--ink-3)]"> {s.unit}</span>
                </div>
                <div className="mt-[2px] text-[12px] font-semibold text-[var(--ink-2)]">{s.label}</div>
                <div className="text-[11px] text-[var(--ink-3)]">{s.sub}</div>
              </div>
            ))}
          </div>
          {tier !== "Pro" && (
            <div className="absolute inset-0 flex items-center justify-center gap-2 text-[var(--ink-2)] text-[12.5px] font-semibold">
              <LockIcon />
              전체 검사 현황 대시보드는 Pro에서 제공됩니다
              <Link href="/#pricing" className="ml-1 font-mono text-[11px] font-bold text-[var(--brand-ink)] border-b border-[var(--brand-ink)] no-underline cursor-pointer">
                요금제 보기
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* 필터 바 */}
      <div className="p-[14px_22px_10px] flex items-center gap-[14px] flex-wrap">
        <div className="flex items-center gap-2 border border-[var(--line-2)] bg-[var(--surface)] p-[6px_10px] min-w-[220px]">
          <svg className="w-3.5 h-3.5 shrink-0 text-[var(--ink-3)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
            <circle cx={11} cy={11} r={7} />
            <path d="M16 16l5 5" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="제품명 검색"
            className="border-0 bg-transparent outline-none font-mono text-[12px] text-[var(--ink)] placeholder:text-[var(--ink-3)] w-full"
            aria-label="제품명 검색"
          />
        </div>
        <span className="inline-flex gap-[5px]">
          {REGION_FILTERS.map(r => (
            <button key={r} type="button" onClick={() => setRegion(r)} className={filterPill(region === r)}>{r}</button>
          ))}
        </span>
        <span className="inline-flex gap-[5px]">
          {STATUS_FILTERS.map(s => (
            <button key={s.key} type="button" onClick={() => setStatus(s.key)} className={filterPill(status === s.key)}>{s.label}</button>
          ))}
        </span>
        <span className="inline-flex gap-[5px]">
          {PERIOD_FILTERS.map(p => (
            <button key={p.key} type="button" onClick={() => setPeriod(p.key)} className={filterPill(period === p.key)}>{p.label}</button>
          ))}
        </span>
      </div>

      {/* 이력 목록 */}
      <div className="p-[0_22px_8px]">
        {rows.length === 0 && (
          <div className="border border-dashed border-[var(--line-2)] p-[36px_20px] text-center font-mono text-[12px] text-[var(--ink-3)]">
            [ 조건에 맞는 이력이 없습니다 ]
          </div>
        )}
        {rows.map(row => {
          const meta = STATUS_META[row.status];
          const locked = isLockedRow(row);
          const rl = REGION_LABEL[row.region];
          const nV = row.report.summary.n_violation;
          const nR = row.report.summary.n_needs_review;
          const dl = dateLabel(row.created_at);

          if (locked) {
            return (
              <div key={row.result_id} className="relative border border-[var(--line)] bg-[var(--surface)] mb-[7px]">
                <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] items-center gap-[13px] p-[11px_14px] blur-[3px] select-none" aria-hidden="true">
                  <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">{row.product_name}</span>
                  <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">{rl}</span>
                  <span className="text-[11.5px] p-[2px_9px] border border-[var(--line-2)] text-[var(--ink-2)]">{meta.label}</span>
                  <span className="font-mono text-[11px] text-[var(--ink-3)]">점수 --</span>
                  <span className="font-mono text-[11px] text-[var(--ink-3)]">리포트</span>
                  <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">{dl}</span>
                </div>
                <div className="absolute inset-0 flex items-center justify-center gap-2 text-[var(--ink-2)] text-[12px] font-semibold">
                  <LockIcon />
                  7일 이전 이력은 Basic부터 무제한 보관됩니다
                  <Link href="/#pricing" className="ml-1 font-mono text-[11px] font-bold text-[var(--brand-ink)] border-b border-[var(--brand-ink)] no-underline cursor-pointer">
                    요금제 보기
                  </Link>
                </div>
              </div>
            );
          }
          return (
            <Link
              key={row.result_id}
              href={rowHref(row)}
              className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] items-center gap-[13px] border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] mb-[7px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]"
            >
              <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">{row.product_name}</span>
              <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">{rl}</span>
              <span
                className={`inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border whitespace-nowrap ${
                  meta.crit
                    ? "text-[var(--crit)] border-[var(--crit-bd)] bg-[var(--crit-bg)] font-semibold"
                    : "text-[var(--ink-2)] border-[var(--line-2)]"
                }`}
              >
                <StatusIcon status={row.status} />
                {meta.label}
              </span>
              <span className={`font-mono text-[11px] whitespace-nowrap [font-variant-numeric:tabular-nums] ${nV > 0 ? "text-[var(--crit)] font-bold" : "text-[var(--ink-3)]"}`}>
                {row.status === "draft" ? "검사 전" : `위반 ${nV} · 검토 ${nR}`}
              </span>
              <span className="font-mono text-[11px] text-[var(--ink-2)] whitespace-nowrap [font-variant-numeric:tabular-nums]">
                {row.score === null ? "점수 --" : `점수 ${row.score}점`}
              </span>
              <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap text-right min-w-[52px]">{dl}</span>
            </Link>
          );
        })}
      </div>

      {/* 하단 안내 */}
      <div className="p-[4px_22px_18px] font-mono text-[10.5px] text-[var(--ink-3)]">
        {tier === "Free" ? "Free는 최근 7일 이력만 보관됩니다" : "이력 무제한 보관 중"} · 행을 누르면 리포트로 이동
      </div>

      <PageFooter />
    </>
  );
}
