"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal/Modal";
import {
  DEMO_CHECKOUT_NOTE,
  TICKET_PRODUCTS,
  TICKET_VALIDITY_NOTE,
  formatDate,
  formatPrice,
  getProduct,
  useTickets,
  type TicketKind,
} from "@/lib/tickets";

interface TicketCheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** 고를 수 있는 이용권 종류. 1개만 주면 종류 선택 단계를 건너뛴다. */
  kinds?: TicketKind[];
  /** 처음 선택돼 있을 종류 */
  defaultKind?: TicketKind;
  /** 왜 이 모달이 떴는지 한 줄. 리포트 언락 유도 등 맥락 표시용. */
  reason?: string;
  /** 결제 완료 후. 리포트 언락처럼 구매 직후 이어서 할 일이 있으면 여기서 받는다. */
  onPurchased?: (kind: TicketKind, size: number) => void;
}

/**
 * 이용권 결제 모달(데모).
 * 종류·수량 선택 → 금액·유효기간 확인 → 결제하기 → 완료 화면 → 잔액 반영.
 * 실제 PG 연동은 범위 밖이라 결제 단계는 짧은 대기 후 성공으로 끝난다.
 */
export function TicketCheckoutModal(props: TicketCheckoutModalProps) {
  // 닫혀 있으면 아예 마운트하지 않는다. 이러면 다시 열 때 선택·완료 상태가
  // 저절로 초기화돼서 리셋용 useEffect가 필요 없다.
  if (!props.isOpen) return null;
  return <TicketCheckoutDialog {...props} />;
}

function TicketCheckoutDialog({
  onClose,
  kinds,
  defaultKind,
  reason,
  onPurchased,
}: TicketCheckoutModalProps) {
  const { purchase } = useTickets();
  const offered = TICKET_PRODUCTS.filter((p) => !kinds || kinds.includes(p.kind));
  const initialKind = defaultKind ?? offered[0]?.kind ?? "domestic";

  const [kind, setKind] = useState<TicketKind>(initialKind);
  const [size, setSize] = useState<number>(1);
  const [phase, setPhase] = useState<"select" | "paying" | "done">("select");
  const [receipt, setReceipt] = useState<{ price: number; expiresAt: string } | null>(null);

  const product = getProduct(kind);
  const pack = product.packs.find((p) => p.size === size) ?? product.packs[0];

  const handlePay = () => {
    setPhase("paying");
    // 실제 PG 왕복 대신 짧은 대기. 결제 흐름의 체감을 남기기 위한 데모 지연이다.
    window.setTimeout(() => {
      const lot = purchase(kind, pack.size);
      setReceipt({ price: lot.price, expiresAt: lot.expiresAt });
      setPhase("done");
      onPurchased?.(kind, pack.size);
    }, 600);
  };

  const btnBase =
    "font-sans text-[13px] p-[11px_16px] border inline-flex items-center justify-center gap-1.5 transition-all duration-[120ms]";
  const btnGhost = `${btnBase} font-semibold border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)]`;
  // DESIGN §4.1: 텍스트 얹는 소형 채움 버튼은 라이트에서 --brand가 AA 미달이라 --brand-deep을 쓴다.
  const btnFill = `${btnBase} font-bold border-[var(--brand-deep)] dark:border-[var(--brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] text-[var(--on-brand)] cursor-pointer hover:opacity-90`;
  const btnDisabled = `${btnBase} font-bold bg-[var(--surface-sub)] text-[var(--ink-3)] border-[var(--line-2)] cursor-not-allowed`;

  return (
    <Modal
      isOpen
      title={phase === "done" ? "결제 완료" : "이용권 구매"}
      size="md"
      onClose={onClose}
      footer={
        phase === "done" ? (
          <button type="button" className={btnFill} onClick={onClose}>
            확인
          </button>
        ) : (
          <>
            <button type="button" className={btnGhost} onClick={onClose} disabled={phase === "paying"}>
              취소
            </button>
            <button
              type="button"
              className={phase === "paying" ? btnDisabled : btnFill}
              disabled={phase === "paying"}
              onClick={handlePay}
            >
              {phase === "paying" ? "결제 처리 중..." : `${formatPrice(pack.price)} 결제하기`}
            </button>
          </>
        )
      }
    >
      {phase === "done" && receipt ? (
        <div className="font-sans">
          <p className="m-0 mb-2 font-mono text-[13px] font-bold text-[var(--brand-ink)]">
            [ok] 결제가 완료되었습니다
          </p>
          <p className="m-0 mb-4 text-[13.5px] text-[var(--ink-2)] leading-[1.7] break-keep">
            {product.name} {pack.size}건을 {formatPrice(receipt.price)}에 구매했습니다. 잔액에 바로
            반영되었습니다.
          </p>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t border-dashed border-[var(--line-2)] pt-3">
            <dt className="text-[12.5px] text-[var(--ink-3)]">추가된 수량</dt>
            <dd className="m-0 font-mono text-[12.5px] tabular-nums text-[var(--ink)]">
              {pack.size}건
            </dd>
            <dt className="text-[12.5px] text-[var(--ink-3)]">사용 기한</dt>
            <dd className="m-0 font-mono text-[12.5px] tabular-nums text-[var(--ink)]">
              {formatDate(receipt.expiresAt)}까지
            </dd>
          </dl>
          <p className="mt-4 mb-0 font-mono text-[11.5px] text-[var(--ink-3)]">{DEMO_CHECKOUT_NOTE}</p>
        </div>
      ) : (
        <div className="font-sans">
          {reason && (
            <p className="m-0 mb-4 p-[10px_12px] bg-[var(--surface-sub)] border border-[var(--line)] text-[13px] text-[var(--ink-2)] leading-[1.65] break-keep">
              {reason}
            </p>
          )}

          {offered.length > 1 && (
            <>
              <p className="m-0 mb-2 font-mono text-[12px] font-bold text-[var(--ink)] tracking-[0.2px]">
                [ 이용권 종류 ]
              </p>
              <div className="flex flex-col gap-1.5 mb-5">
                {offered.map((p) => {
                  const selected = p.kind === kind;
                  return (
                    <button
                      key={p.kind}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => {
                        setKind(p.kind);
                        setSize(1);
                      }}
                      className={`text-left p-[10px_12px] border cursor-pointer transition-all duration-[120ms] ${
                        selected
                          ? "border-[var(--brand-deep)] dark:border-[var(--brand-ink)] bg-[var(--nav-active-bg)]"
                          : "border-[var(--line-2)] bg-transparent hover:bg-[var(--nav-hover)]"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className="font-mono text-[11px] text-[var(--ink-3)]">
                          {selected ? "[x]" : "[ ]"}
                        </span>
                        <span className="text-[13.5px] font-bold text-[var(--ink)]">{p.name}</span>
                      </span>
                      <span className="block mt-1 pl-[26px] text-[12.5px] text-[var(--ink-3)] leading-[1.6] break-keep">
                        {p.desc}
                      </span>
                    </button>
                  );
                })}
              </div>
            </>
          )}

          <p className="m-0 mb-2 font-mono text-[12px] font-bold text-[var(--ink)] tracking-[0.2px]">
            [ 수량 ]
          </p>
          {product.packs.length === 1 ? (
            <p className="m-0 mb-5 text-[13px] text-[var(--ink-3)] leading-[1.65] break-keep">
              {product.name}은 1건 단위로만 판매합니다.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5 mb-5">
              {product.packs.map((p) => {
                const selected = p.size === pack.size;
                // 1건 단가 대비 할인율. 묶음의 이득을 숫자로 보여준다.
                const unit = product.packs[0].price;
                const discount = Math.round((1 - p.price / (unit * p.size)) * 100);
                return (
                  <button
                    key={p.size}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setSize(p.size)}
                    className={`flex-1 min-w-[110px] p-[10px_12px] border cursor-pointer text-left transition-all duration-[120ms] ${
                      selected
                        ? "border-[var(--brand-deep)] dark:border-[var(--brand-ink)] bg-[var(--nav-active-bg)]"
                        : "border-[var(--line-2)] bg-transparent hover:bg-[var(--nav-hover)]"
                    }`}
                  >
                    <span className="block text-[13px] font-bold text-[var(--ink)]">{p.size}건</span>
                    <span className="block mt-0.5 font-mono text-[12.5px] tabular-nums text-[var(--ink-2)]">
                      {formatPrice(p.price)}
                    </span>
                    {discount > 0 && (
                      <span className="block mt-0.5 font-mono text-[11px] tabular-nums text-[var(--ink-3)]">
                        1건씩 {p.size}장보다 {discount}% 저렴
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t border-dashed border-[var(--line-2)] pt-3">
            <dt className="text-[12.5px] text-[var(--ink-3)]">상품</dt>
            <dd className="m-0 text-[12.5px] text-[var(--ink)]">
              {product.name} {pack.size}건
            </dd>
            <dt className="text-[12.5px] text-[var(--ink-3)]">결제 금액</dt>
            <dd className="m-0 font-mono text-[13px] font-bold tabular-nums text-[var(--ink)]">
              {formatPrice(pack.price)}
            </dd>
          </dl>

          <p className="mt-3 mb-0 text-[12px] text-[var(--ink-3)] leading-[1.7] break-keep">
            {TICKET_VALIDITY_NOTE}
          </p>
          <p className="mt-2 mb-0 font-mono text-[11.5px] text-[var(--ink-3)]">{DEMO_CHECKOUT_NOTE}</p>
        </div>
      )}
    </Modal>
  );
}
