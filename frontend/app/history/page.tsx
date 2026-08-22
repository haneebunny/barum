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
import { PageContent } from "@/components/PageContent/PageContent";
import { HistoryRow, HistoryRowList, HistoryRowLocked } from "@/components/HistoryRow/HistoryRow";
import { PageHeader } from "@/components/PageHeader/PageHeader";
import { TabSwitch } from "@/components/TabSwitch/TabSwitch";
import { useTier, type Tier } from "@/lib/tier";
import { MOCK_HISTORY, REGION_LABEL, STATUS_META, daysAgo, dateLabel, rowProps, type MockHistoryItem } from "@/lib/mockHistory";
import { FilterDropdown } from "@/components/Dropdown/FilterDropdown";

const MOCK_STATS = [
  { value: "24", unit: "건", label: "이번 달 검사", sub: "지난달 대비 +6건" },
  { value: "9", unit: "건", label: "위반 검출", sub: "검토필요 별도 4건", crit: true },
  { value: "78", unit: "%", label: "권고안 적용률", sub: "적용 후 평균 96점" },
];

function LockIcon() {
  return (
    <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
      <rect x={5} y={11} width={14} height={9} />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

const TIER_OPTIONS: { value: Tier; label: string }[] = [
  { value: "Free", label: "Free" },
  { value: "Basic", label: "Basic" },
  { value: "Pro", label: "Pro" },
];

const REGION_OPTIONS = [
  { key: "전체", label: "전체" },
  { key: "국내", label: "국내" },
  { key: "해외", label: "해외" },
] as const;

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
  const [region, setRegion] = useState<(typeof REGION_OPTIONS)[number]["key"]>("전체");
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

  const isLockedRow = (row: MockHistoryItem) => tier === "Free" && daysAgo(row.created_at) > 7;

  const rowHref = (row: MockHistoryItem) =>
    row.status === "draft" ? `/inspect?id=${row.result_id}` : `/report/${row.result_id}`;

  return (
    <>
      <PageContent>
      <PageHeader
        title="검사 이력"
        subtitle={`총 ${MOCK_HISTORY.length}건 · 최근 30일`}
        right={<TabSwitch label="티어 미리보기" options={TIER_OPTIONS} value={tier} onChange={setTier} />}
      />

      {/* Pro 현황 스트립 */}
      <div className="pt-[28px]">
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
      <div className="pt-[28px] pb-[16px] flex items-center gap-[18px] flex-wrap">
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
        <FilterDropdown
          label="국가"
          options={REGION_OPTIONS}
          selectedValue={region}
          onSelect={setRegion}
        />
        <FilterDropdown
          label="상태"
          options={STATUS_FILTERS}
          selectedValue={status}
          onSelect={setStatus}
        />
        <FilterDropdown
          label="기간"
          options={PERIOD_FILTERS}
          selectedValue={period}
          onSelect={setPeriod}
        />
      </div>

      {/* 이력 목록 */}
      <div>
        {rows.length === 0 && (
          <div className="border border-dashed border-[var(--line-2)] p-[36px_20px] text-center font-mono text-[12px] text-[var(--ink-3)]">
            [ 조건에 맞는 이력이 없습니다 ]
          </div>
        )}
        {rows.length > 0 && (
          <HistoryRowList>
            {rows.map(row => {
              if (isLockedRow(row)) {
                return (
                  <HistoryRowLocked
                    key={row.result_id}
                    product_name={row.product_name}
                    region_label={REGION_LABEL[row.region]}
                    status_label={STATUS_META[row.status].label}
                    date_label={dateLabel(row.created_at)}
                    lock_message={
                      <>
                        <LockIcon />
                        7일 이전 이력은 Basic부터 무제한 보관됩니다
                        <Link href="/#pricing" className="ml-1 font-mono text-[11px] font-bold text-[var(--brand-ink)] border-b border-[var(--brand-ink)] no-underline cursor-pointer">
                          요금제 보기
                        </Link>
                      </>
                    }
                  />
                );
              }
              return <HistoryRow key={row.result_id} href={rowHref(row)} {...rowProps(row)} />;
            })}
          </HistoryRowList>
        )}
      </div>

      {/* 하단 안내 */}
      <div className="pt-[4px] pb-[18px] font-mono text-[10.5px] text-[var(--ink-3)]">
        {tier === "Free" ? "Free는 최근 7일 이력만 보관됩니다" : "이력 무제한 보관 중"} · 행을 누르면 리포트로 이동
      </div>
      </PageContent>

      <PageFooter />
    </>
  );
}
