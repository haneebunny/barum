/**
 * PageFooter: 모든 페이지 하단에 공통으로 노출되는 화장품법 규제 고지 컴포넌트.
 * compliance 텍스트를 단일 소스로 관리한다.
 */
export function PageFooter() {
  return (
    <div className="mt-[22px] p-[10px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] text-[11px] text-[var(--ink-3)] leading-[1.65]">
      바름은 사전 스크리너이며 최종 법적 판단이 아닙니다. &apos;통과&apos;가 100% 안전을 보장하지
      않으며, 최종 게시 판단과 책임은 사업자에게 있습니다.{" "}
      <b className="text-[var(--brand-ink)] font-semibold">적용 기준: 화장품법 · 고시 2025-79호 · 미국 FDA/FTC</b>
    </div>
  );
}
