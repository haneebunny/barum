"use client";

import { useEffect, useState } from "react";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { PageContent } from "@/components/PageContent/PageContent";
import { PageHeader } from "@/components/PageHeader/PageHeader";
import { HistoryRow, HistoryRowList } from "@/components/HistoryRow/HistoryRow";
import { TicketCheckoutModal } from "@/components/TicketCheckout/TicketCheckoutModal";
import { historyHref, historyRowProps } from "@/lib/reportHistory";
import { useReportHistory } from "@/lib/useReportHistory";
import type { ExportProfile } from "@/lib/api/schema";
import { DEFAULT_EXPORT_PROFILE, readExportProfile, writeExportProfile } from "@/lib/exportProfile";
import {
  EXPIRY_WARNING_DAYS,
  BETA_PRODUCTS,
  MAIN_PRODUCTS,
  TICKET_VALIDITY_NOTE,
  daysUntil,
  formatDate,
  formatPrice,
  getProduct,
  isExpired,
  useDailyChecks,
  useTickets,
  type TicketKind,
  type TicketLot,
} from "@/lib/tickets";

/** 구매 lot 하나의 상태 라벨. 색이 아니라 글자로 구분한다(F 규칙: 비긴급 상태에 색 금지). */
function lotStatus(lot: TicketLot): string {
  if (lot.remaining === 0) return "모두 사용함";
  if (isExpired(lot)) return "기간 만료";
  const left = daysUntil(lot.expiresAt);
  if (left <= EXPIRY_WARNING_DAYS) return `${lot.remaining}건 남음 · 만료 ${left}일 전`;
  return `${lot.remaining}건 남음`;
}
export default function MyPage() {
  // 구매 자체는 결제 모달이 처리한다. 여기선 잔액과 이력만 읽는다.
  const { lots, balance, expiringSoon } = useTickets();
  const daily = useDailyChecks();
  const { rows: recentHistory, loading: historyLoading, error: historyError } = useReportHistory(5);
  const [checkoutKind, setCheckoutKind] = useState<TicketKind | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);

  const openCheckout = (kind?: TicketKind) => {
    setCheckoutKind(kind ?? null);
    setIsCheckoutOpen(true);
  };

  /** 그 종류에서 잔량이 남은 것 중 가장 먼저 만료되는 날짜. 보유가 없으면 null. */
  const soonestExpiry = (kind: TicketKind): string | null => {
    const lot = lots
      .filter((l) => l.kind === kind && l.remaining > 0 && !isExpired(l))
      .sort((a, b) => new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime())[0];
    return lot ? `${formatDate(lot.expiresAt)}까지` : null;
  };

  // 최근 구매가 위로
  const purchaseHistory = [...lots].sort(
    (a, b) => new Date(b.purchasedAt).getTime() - new Date(a.purchasedAt).getTime(),
  );


  const [exportProfile, setExportProfile] = useState<ExportProfile>(DEFAULT_EXPORT_PROFILE);
  const [profileSaved, setProfileSaved] = useState(false);
  const profileFields: Array<[keyof ExportProfile, string]> = [
    ["legal_manufacturer", "법인명"],
    ["manufacturer_name", "제조사명"],
    ["manufacturing_site", "제조 시설명"],
    ["manufacturing_site_address", "제조 시설 주소"],
    ["us_agent_name", "U.S. Agent 이름"],
    ["us_agent_contact", "U.S. Agent 연락처"],
    ["importer_name", "미국 수입자"],
    ["importer_contact", "수입자 연락처"],
  ];

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setExportProfile(readExportProfile()));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const updateProfile = <K extends keyof ExportProfile>(key: K, value: ExportProfile[K]) => {
    setExportProfile((previous) => ({ ...previous, [key]: value }));
    setProfileSaved(false);
  };

  const textValue = (key: keyof ExportProfile) => String(exportProfile[key] ?? "");

  return (
    <>
      <PageContent>
        <PageHeader title="마이페이지" />

        {/* 보유 이용권 */}
        <div className="py-[18px] border-b border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">보유 이용권</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">yourberry 계정</span>
          </div>

          <div className="grid grid-cols-3 gap-3.5 max-[900px]:grid-cols-1">
            {MAIN_PRODUCTS.map((product) => (
              <div key={product.kind} className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px] flex flex-col">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">{product.name}</p>
                <div className="flex items-baseline gap-1.5 mb-1.5">
                  <span className="text-[26px] font-extrabold text-[var(--ink)] tracking-[-0.4px] tabular-nums">{balance(product.kind)}</span>
                  <span className="font-mono text-[12.5px] text-[var(--ink-2)]">건 남음</span>
                </div>
                <p className="m-0 mb-3 text-[12px] text-[var(--ink-3)] leading-[1.6] break-keep">{product.desc}</p>
                <div className="mt-auto flex items-center justify-between gap-2 pt-2.5 border-t border-dashed border-[var(--line-2)]">
                  <span className="font-mono text-[10.5px] text-[var(--ink-3)] tabular-nums">
                    {soonestExpiry(product.kind) ?? "보유 없음"}
                  </span>
                  <button
                    type="button"
                    onClick={() => openCheckout(product.kind)}
                    className="font-sans text-[12px] font-semibold p-[6px_11px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] transition-all duration-[120ms]"
                  >
                    충전
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* 베타 상품은 위 3종과 위계를 나눠 한 줄로 아래에 붙인다 */}
          {BETA_PRODUCTS.map((product) => (
            <div
              key={product.kind}
              className="mt-3.5 border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[13px_16px] flex items-center gap-3 flex-wrap"
            >
              <span className="border border-[var(--line-2)] text-[var(--ink-3)] font-mono text-[10.5px] font-bold px-[6px] py-[2px]">BETA</span>
              <span className="text-[13px] font-bold text-[var(--ink)]">{product.name}</span>
              <span className="font-mono text-[12.5px] tabular-nums text-[var(--ink-2)]">
                <b className="text-[15px] font-bold">{balance(product.kind)}</b>건 남음
              </span>
              <span className="text-[12px] text-[var(--ink-3)] break-keep">{product.desc} · 선크림 단일 품목</span>
              <span className="ml-auto flex items-center gap-2.5">
                <span className="font-mono text-[10.5px] text-[var(--ink-3)] tabular-nums">
                  {soonestExpiry(product.kind) ?? "보유 없음"}
                </span>
                <button
                  type="button"
                  onClick={() => openCheckout(product.kind)}
                  className="font-sans text-[12px] font-semibold p-[6px_11px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] transition-all duration-[120ms]"
                >
                  충전
                </button>
              </span>
            </div>
          ))}

          {expiringSoon.length > 0 && (
            <p className="m-[14px_0_0] p-[11px_13px] border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] text-[12.5px] text-[var(--ink-2)] leading-[1.7] break-keep">
              <b className="text-[var(--ink)] font-bold">만료 임박</b>{" "}
              {expiringSoon
                .map((l) => `${getProduct(l.kind).name} ${l.remaining}건 (${daysUntil(l.expiresAt)}일 남음)`)
                .join(" · ")}
              . 기한이 지나면 사용할 수 없습니다.
            </p>
          )}

          {/* 오늘의 무료 검사. 국내 검사에만 적용된다 */}
          <div className="mt-3.5 border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
            <div className="flex items-baseline justify-between mb-2.25">
              <span className="text-[12.5px] text-[var(--ink-2)]">오늘의 무료 국내 검사</span>
              <span className="font-mono tabular-nums text-[13px] text-[var(--ink)]">
                <b className="text-[16px] font-bold">{daily.used}</b> / {daily.limit}회
              </span>
            </div>
            <div
              className="h-2 bg-[var(--line-2)] border border-[var(--line-2)] overflow-hidden"
              aria-label={`오늘 무료 검사 ${daily.used}회 사용, ${daily.remaining}회 남음`}
            >
              <div
                className="h-full bg-[var(--ink-3)]"
                style={{ width: `${Math.round((daily.used / daily.limit) * 100)}%` }}
              ></div>
            </div>
            <div className="font-mono text-[10.5px] text-[var(--ink-3)] mt-2">
              {daily.remaining}회 남음 · 매일 자정 초기화 · 해외 프리플라이트는 무료 검사가 없습니다
            </div>
          </div>

          <div className="flex items-center gap-3.5 mt-3.5 p-[13px_15px] border border-[var(--line-2)] bg-[var(--surface-sub)]">
            <div className="flex-1 min-w-0">
              <b className="text-[var(--ink)] font-bold">필요한 만큼만 이용권으로 결제하세요.</b>
              <p className="m-[2px_0_0] text-[12px] text-[var(--ink-3)] leading-[1.7] break-keep">{TICKET_VALIDITY_NOTE}</p>
            </div>
            <button
              type="button"
              onClick={() => openCheckout()}
              className="shrink-0 font-sans text-[13px] font-bold p-[11px_16px] border border-[var(--brand-deep)] dark:border-[var(--brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] text-[var(--on-brand)] cursor-pointer hover:opacity-90 inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms]"
            >
              이용권 구매 <span className="font-mono">→</span>
            </button>
          </div>
        </div>


        {/* 미국 수출 프로필: 여러 제품에서 재사용 */}
        <div className="py-[18px] border-b border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">미국 수출 프로필</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">다음 검사에 재사용</span>
          </div>
          <p className="m-[0_0_12px] text-[12px] text-[var(--ink-3)] leading-[1.6]">
            제조 시설과 미국 유통 파트너 정보를 한 번 저장하면 다른 제품의 수출 준비에서도 다시 사용할 수 있습니다.
          </p>
          <div className="grid grid-cols-2 gap-2.5 max-[900px]:grid-cols-1">
            {profileFields.map(([key, label]) => (
              <label key={key} className="text-[11.5px] text-[var(--ink-2)]">
                {label}
                <input
                  className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface-sub)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                  value={textValue(key)}
                  onChange={(event) => updateProfile(key, event.target.value)}
                />
              </label>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              className="font-sans text-[12.5px] font-bold p-[9px_14px] border border-[var(--brand)] bg-[var(--brand)] text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-deep)]"
              onClick={() => {
                writeExportProfile(exportProfile);
                setProfileSaved(true);
              }}
            >
              프로필 저장
            </button>
            <span className="font-mono text-[10.5px] text-[var(--brand-ink)]" aria-live="polite">
              {profileSaved ? "저장됨 · 다음 미국 검사에 재사용됩니다." : "변경사항이 있습니다."}
            </span>
          </div>
        </div>

        {/* 구매 이력 */}
        <div className="py-[18px] border-b border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">구매 이력</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">{purchaseHistory.length}건</span>
          </div>
          {purchaseHistory.length === 0 ? (
            <p className="m-0 p-[18px_16px] border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] text-[12.5px] text-[var(--ink-3)] text-center">
              아직 구매한 이용권이 없습니다.
            </p>
          ) : (
            <ul className="list-none m-0 p-0 border border-[var(--line-2)] bg-[var(--surface)]">
              {purchaseHistory.map((lot) => (
                <li
                  key={lot.id}
                  className="grid grid-cols-[100px_1fr_auto_auto] gap-3 items-baseline p-[11px_14px] border-b border-[var(--line)] last:border-b-0 max-[900px]:grid-cols-2"
                >
                  <span className="font-mono text-[11.5px] text-[var(--ink-3)] tabular-nums">{formatDate(lot.purchasedAt)}</span>
                  <span className="text-[12.5px] text-[var(--ink)]">
                    {getProduct(lot.kind).name} {lot.size}건
                  </span>
                  <span className="font-mono text-[11.5px] text-[var(--ink-3)] tabular-nums whitespace-nowrap">{lotStatus(lot)}</span>
                  <span className="font-mono text-[12.5px] text-[var(--ink-2)] tabular-nums text-right whitespace-nowrap">{formatPrice(lot.price)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 검사 이력 */}
        <div className="py-[18px] border-b-0">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">03</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">검사 이력</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">최근 5건</span>
          </div>
          {recentHistory.length > 0 ? (
            <HistoryRowList>
              {recentHistory.map((row) => (
                <HistoryRow key={row.result_id} href={historyHref(row)} {...historyRowProps(row)} />
              ))}
            </HistoryRowList>
          ) : (
            <div className="border-y border-dashed border-[var(--line-2)] p-[18px_10px] font-mono text-[11px] text-[var(--ink-3)]">
              [ {historyLoading ? "이 기기의 검사 이력을 불러오는 중" : historyError || "이 기기에 저장된 검사 이력이 없습니다"} ]
            </div>
          )}
        </div>
      </PageContent>

      <PageFooter />

      <TicketCheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        defaultKind={checkoutKind ?? undefined}
      />
    </>
  );
}
