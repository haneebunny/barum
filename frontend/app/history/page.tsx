"use client";

import Link from "next/link";
import { useState } from "react";
import { Trash } from "@phosphor-icons/react";
import { FilterDropdown } from "@/components/Dropdown/FilterDropdown";
import { HistoryRow, HistoryRowList, HistoryRowLocked } from "@/components/HistoryRow/HistoryRow";
import { Modal } from "@/components/Modal/Modal";
import { PageContent } from "@/components/PageContent/PageContent";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { PageHeader } from "@/components/PageHeader/PageHeader";
import type { ReportListItem } from "@/lib/api/schema";
import {
  DEMO_PRODUCT_NAME,
  DEMO_RESULT_ID,
  DEMO_US_SUNSCREEN_PRODUCT_NAME,
  DEMO_US_SUNSCREEN_RESULT_ID,
} from "@/lib/demo/demo";
import { daysAgo, dateLabel, historyHref, historyRowProps, REGION_LABEL } from "@/lib/reportHistory";
import { FREE_SUMMARY_RETENTION_DAYS, freeSummaryDaysLeft, isFreeSummaryExpired, useAllReportAccess } from "@/lib/tickets";
import { useReportHistory } from "@/lib/useReportHistory";

function LockIcon() {
  return (
    <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
      <rect x={5} y={11} width={14} height={9} />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

function DeleteButton({ productName, onClick }: { productName: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 border-0 bg-transparent p-[7px_5px] font-mono text-[11px] text-[var(--ink-3)] cursor-pointer hover:text-[var(--crit)]"
      aria-label={`${productName} 검사 이력 삭제`}
    >
      <Trash size={14} weight="regular" />
      삭제
    </button>
  );
}

const REGION_OPTIONS = [
  { key: "전체", label: "전체" },
  { key: "국내", label: "국내" },
  { key: "해외", label: "해외" },
] as const;

const STATUS_FILTERS = [
  { key: "all", label: "전체" },
  { key: "review", label: "검토 필요" },
  { key: "done", label: "검사 완료" },
] as const;

const PERIOD_FILTERS = [
  { key: 9999, label: "전체 기간" },
  { key: 7, label: "최근 7일" },
  { key: 30, label: "최근 30일" },
] as const;

export default function HistoryPage() {
  const reportAccess = useAllReportAccess();
  const { rows: allRows, loading, error, remove } = useReportHistory(100);
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<(typeof REGION_OPTIONS)[number]["key"]>("전체");
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]["key"]>("all");
  const [period, setPeriod] = useState<number>(9999);
  const [deleteTarget, setDeleteTarget] = useState<ReportListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const rows = allRows.filter((row) => {
    const productName = row.product_name?.trim() || "이름 없는 검사";
    if (query && !productName.includes(query.trim())) return false;
    if (region !== "전체" && !REGION_LABEL[row.region].startsWith(region)) return false;
    if (status !== "all" && row.status !== status) return false;
    if (daysAgo(row.created_at) > period) return false;
    return true;
  });

  const isLockedRow = (row: ReportListItem) =>
    isFreeSummaryExpired(row.created_at, reportAccess[row.result_id]);

  const deleteAction = (row: ReportListItem) => (
    <DeleteButton
      productName={row.product_name?.trim() || "이름 없는 검사"}
      onClick={() => {
        setDeleteError(null);
        setDeleteTarget(row);
      }}
    />
  );

  const confirmDelete = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await remove(deleteTarget.result_id);
      setDeleteTarget(null);
    } catch (requestError) {
      console.error(requestError);
      setDeleteError("검사 이력을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <PageContent>
        <PageHeader title="검사 이력" subtitle={`이 기기에 저장된 검사 ${allRows.length}건`} />

        <section className="pt-[28px]" aria-labelledby="sample-report-heading">
          <div className="mb-[11px] flex items-end gap-3 flex-wrap">
            <div>
              <p className="m-0 mb-1 font-mono text-[10.5px] font-bold text-[var(--brand-ink)] tracking-[0.4px]">
                [ SAMPLE REPORTS ]
              </p>
              <h2 id="sample-report-heading" className="m-0 text-[15px] font-bold text-[var(--ink)]">
                완성된 샘플 리포트
              </h2>
            </div>
            <p className="m-0 pb-[1px] text-[11.5px] text-[var(--ink-3)]">
              실제 검사 결과 형식을 이용권 없이 확인할 수 있습니다.
            </p>
          </div>
          <HistoryRowList>
            <HistoryRow
              href={`/report/${DEMO_RESULT_ID}`}
              product_name={DEMO_PRODUCT_NAME}
              region_label="국내"
              status_icon="review"
              status_label="검토 필요"
              status_crit
              count_label="위반 12 · 검토 7"
              count_crit
              date_label="샘플"
            />
            <HistoryRow
              href={`/report/us/${DEMO_US_SUNSCREEN_RESULT_ID}`}
              product_name={DEMO_US_SUNSCREEN_PRODUCT_NAME}
              region_label="해외 · 미국"
              status_icon="review"
              status_label="검토 필요"
              status_crit
              count_label="확인 필요 2건"
              count_crit
              date_label="샘플"
            />
          </HistoryRowList>
        </section>

        <div className="pt-[34px] pb-[10px] flex items-end gap-3 flex-wrap">
          <div>
            <p className="m-0 mb-1 font-mono text-[10.5px] font-bold text-[var(--ink-3)] tracking-[0.4px]">
              [ MY HISTORY ]
            </p>
            <h2 className="m-0 text-[15px] font-bold text-[var(--ink)]">이 기기의 검사 이력</h2>
          </div>
        </div>

        <div className="pb-[16px] flex items-center gap-[18px] flex-wrap">
          <div className="flex items-center gap-2 border border-[var(--line-2)] bg-[var(--surface)] p-[6px_10px] min-w-[220px]">
            <svg className="w-3.5 h-3.5 shrink-0 text-[var(--ink-3)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
              <circle cx={11} cy={11} r={7} />
              <path d="M16 16l5 5" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="제품명 검색"
              className="border-0 bg-transparent outline-none font-mono text-[12px] text-[var(--ink)] placeholder:text-[var(--ink-3)] w-full"
              aria-label="제품명 검색"
            />
          </div>
          <FilterDropdown label="국가" options={REGION_OPTIONS} selectedValue={region} onSelect={setRegion} />
          <FilterDropdown label="상태" options={STATUS_FILTERS} selectedValue={status} onSelect={setStatus} />
          <FilterDropdown label="기간" options={PERIOD_FILTERS} selectedValue={period} onSelect={setPeriod} />
        </div>

        <div>
          {loading && (
            <div className="border border-dashed border-[var(--line-2)] p-[36px_20px] text-center font-mono text-[12px] text-[var(--ink-3)]">
              [ 이 기기의 검사 이력을 불러오는 중 ]
            </div>
          )}
          {!loading && error && (
            <div className="border border-[var(--crit-bd)] bg-[var(--crit-bg)] p-[20px] text-center font-mono text-[12px] text-[var(--crit)]">
              [ {error} ]
            </div>
          )}
          {!loading && !error && rows.length === 0 && (
            <div className="border border-dashed border-[var(--line-2)] p-[36px_20px] text-center font-mono text-[12px] text-[var(--ink-3)]">
              [ 조건에 맞는 이 기기의 검사 이력이 없습니다 ]
            </div>
          )}
          {!loading && !error && rows.length > 0 && (
            <HistoryRowList>
              {rows.map((row) => {
                const props = historyRowProps(row);
                if (isLockedRow(row)) {
                  return (
                    <HistoryRowLocked
                      key={row.result_id}
                      product_name={props.product_name}
                      region_label={REGION_LABEL[row.region]}
                      status_label={props.status_label}
                      date_label={dateLabel(row.created_at)}
                      action={deleteAction(row)}
                      lock_message={
                        <>
                          <LockIcon />
                          무료 요약은 {FREE_SUMMARY_RETENTION_DAYS}일간만 보관됩니다. 이용권으로 열어둔 리포트는 기간 제한 없이 남아요.
                          <Link href="/#pricing" className="ml-1 font-mono text-[11px] font-bold text-[var(--brand-ink)] border-b border-[var(--brand-ink)] no-underline cursor-pointer">
                            이용권 보기
                          </Link>
                        </>
                      }
                    />
                  );
                }
                const daysLeft = reportAccess[row.result_id]?.unlockedWith
                  ? null
                  : freeSummaryDaysLeft(row.created_at);
                return (
                  <HistoryRow
                    key={row.result_id}
                    href={historyHref(row)}
                    {...props}
                    action={deleteAction(row)}
                    date_label={daysLeft !== null && daysLeft <= 3 ? `${props.date_label} · 만료 D-${daysLeft}` : props.date_label}
                  />
                );
              })}
            </HistoryRowList>
          )}
        </div>

        <div className="pt-[8px] pb-[18px] font-mono text-[10.5px] text-[var(--ink-3)]">
          이 브라우저에서 실행한 검사만 표시 · 사이트 데이터를 지우거나 다른 기기를 사용하면 이력을 불러올 수 없음
        </div>
      </PageContent>

      <PageFooter />

      <Modal
        isOpen={deleteTarget !== null}
        title="검사 이력 삭제"
        onClose={() => {
          if (!deleting) setDeleteTarget(null);
        }}
        footer={
          <div className="flex gap-2">
            <button
              type="button"
              className="border border-[var(--line-2)] bg-transparent px-3 py-2 font-sans text-[12px] font-semibold text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)]"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              취소
            </button>
            <button
              type="button"
              className="border border-[var(--crit)] bg-[var(--crit)] px-3 py-2 font-sans text-[12px] font-bold text-[var(--surface)] cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => void confirmDelete()}
              disabled={deleting}
            >
              {deleting ? "삭제 중" : "삭제"}
            </button>
          </div>
        }
      >
        <p className="m-0 font-sans text-[13px] leading-[1.7] text-[var(--ink-2)]">
          {deleteTarget?.product_name?.trim() || "이름 없는 검사"}의 결과와 첨부한 증거 이미지를 삭제합니다. 삭제한 이력은 복구할 수 없습니다.
        </p>
        {deleteError && (
          <p className="mt-3 mb-0 border border-[var(--crit-bd)] bg-[var(--crit-bg)] p-2 font-sans text-[12px] text-[var(--crit)]">
            {deleteError}
          </p>
        )}
      </Modal>
    </>
  );
}
