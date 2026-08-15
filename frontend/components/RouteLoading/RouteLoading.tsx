/**
 * RouteLoading: 라우트 전환 중 본문 영역에 뜨는 공용 로딩 (터미널 톤).
 * 각 라우트의 loading.tsx가 이 컴포넌트를 재노출한다. 셸(상단바·사이드바)은 layout이라 유지된다.
 */
export function RouteLoading() {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[320px] font-mono text-[12.5px] text-[var(--ink-3)]">
      <span>[ 불러오는 중 ]</span>
      <span
        className="inline-block w-[0.6em] h-[1em] ml-[6px] bg-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]"
        aria-hidden="true"
      />
    </div>
  );
}

export default RouteLoading;
