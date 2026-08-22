"use client";

import Link from "next/link";
import type { ReactNode } from "react";

export type HistoryRowIconStatus = "review" | "done" | "draft";

export function HistoryStatusIcon({ status }: { status: HistoryRowIconStatus }) {
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

/** 검사 이력 리스트 컨테이너. 좌우 테두리 없이 위아래 선으로만 묶고, 행 사이는 hairline으로 구분한다. */
export function HistoryRowList({ children }: { children: ReactNode }) {
  return <div className="border-y border-[var(--line-2)] divide-y divide-[var(--line)]">{children}</div>;
}

/** 행 2단 중 아랫단(기계 계층 메타). 항목 사이는 가운뎃점으로 잇는다. */
function MetaLine({ items }: { items: ReactNode[] }) {
  const shown = items.filter(Boolean);
  return (
    <div className="mt-[7px] flex items-center gap-[7px] font-mono text-[11px] text-[var(--ink-3)] [font-variant-numeric:tabular-nums] min-w-0">
      {shown.map((item, i) => (
        <span key={i} className="flex items-center gap-[7px] whitespace-nowrap">
          {i > 0 && <span className="text-[var(--line-2)]">·</span>}
          {item}
        </span>
      ))}
    </div>
  );
}

/** 터미널 다이얼로그 타이틀([ ... ]) 규칙을 상태 표시에도 적용. 박스 테두리 없는 순수 텍스트 브래킷. */
function StatusChip({
  status_icon,
  status_label,
  status_crit,
}: {
  status_icon: HistoryRowIconStatus;
  status_label: string;
  status_crit: boolean;
}) {
  return (
    <span
      className={`shrink-0 inline-flex items-center gap-[5px] font-mono text-[11px] whitespace-nowrap ${
        status_crit ? "text-[var(--crit)]" : "text-[var(--ink-2)]"
      }`}
    >
      <HistoryStatusIcon status={status_icon} />[ {status_label} ]
    </span>
  );
}

interface HistoryRowProps {
  href: string;
  product_name: string;
  region_label?: string;
  status_icon: HistoryRowIconStatus;
  status_label: string;
  status_crit: boolean;
  /** 위반·검토 건수 등 요약. 없으면 메타 줄에서 생략된다. */
  count_label?: string;
  count_crit?: boolean;
  score_label?: string;
  date_label: string;
}

/**
 * 검사 이력 한 행. HistoryRowList 안에서만 쓴다.
 * 2단 구조로 위계를 만든다. 윗단은 사람이 읽는 제품명·상태, 아랫단은 기계 계층 메타.
 * 날짜만 우측에 홀로 두어 메타와 섞이지 않게 한다.
 */
export function HistoryRow({
  href,
  product_name,
  region_label,
  status_icon,
  status_label,
  status_crit,
  count_label,
  count_crit,
  score_label,
  date_label,
}: HistoryRowProps) {
  const has_meta_line = count_label !== undefined || score_label !== undefined;
  return (
    <Link
      href={href}
      className="group flex flex-col gap-1.5 sm:grid sm:grid-cols-[1fr_auto] sm:items-center sm:gap-5 p-[12px_10px] cursor-pointer no-underline transition-colors duration-150 hover:bg-[var(--nav-active-bg)]"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-[var(--ink)] font-semibold text-[14.5px] tracking-[-0.2px] truncate min-w-0">{product_name}</span>
          {/* 메타가 지역뿐이거나 아예 없으면 둘째 줄을 만들지 않고 여기 붙인다 */}
          {!has_meta_line && region_label && <span className="shrink-0 font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">{region_label}</span>}
        </div>
        {has_meta_line && (
          <MetaLine
            items={[
              region_label,
              count_label && <span className={count_crit ? "text-[var(--crit)] font-bold" : undefined}>{count_label}</span>,
              score_label,
            ]}
          />
        )}
      </div>
      <div className="flex items-center gap-3.5 shrink-0">
        <StatusChip status_icon={status_icon} status_label={status_label} status_crit={status_crit} />
        <span className="text-[var(--ink-3)] opacity-[0.92] font-mono text-[11px] whitespace-nowrap text-right [font-variant-numeric:tabular-nums]">{date_label}</span>
        <svg
          className="w-3.5 h-3.5 shrink-0 text-[var(--ink-3)] opacity-0 transition-opacity duration-150 group-hover:opacity-100"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="square"
          aria-hidden="true"
        >
          <path d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </Link>
  );
}

interface HistoryRowLockedProps {
  product_name: string;
  region_label: string;
  status_label: string;
  date_label: string;
  lock_message: ReactNode;
}

/** 잠긴(블러 처리된) 검사 이력 행. 클릭 불가, HistoryRowList 안에서만 쓴다. */
export function HistoryRowLocked({ product_name, region_label, status_label, date_label, lock_message }: HistoryRowLockedProps) {
  return (
    <div className="relative">
      <div className="flex flex-col gap-1.5 sm:grid sm:grid-cols-[1fr_auto] sm:items-center sm:gap-5 p-[12px_10px] blur-[3px] select-none" aria-hidden="true">
        <div className="min-w-0">
          <span className="text-[var(--ink)] font-semibold text-[14.5px] truncate min-w-0 block">{product_name}</span>
          <MetaLine items={[region_label, "위반 -- · 검토 --", "점수 --"]} />
        </div>
        <div className="flex items-center gap-3.5 shrink-0">
          <span className="font-mono text-[11px] text-[var(--ink-2)] whitespace-nowrap">[ {status_label} ]</span>
          <span className="text-[var(--ink-3)] opacity-[0.92] font-mono text-[11px] whitespace-nowrap">{date_label}</span>
        </div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center gap-2 text-[var(--ink-2)] text-[12px] font-semibold px-6 text-center">
        {lock_message}
      </div>
    </div>
  );
}
