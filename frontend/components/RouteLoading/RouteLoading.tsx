/**
 * RouteLoading: 라우트 전환 중 본문 영역에 뜨는 공용 로딩 (터미널 톤).
 * 각 라우트의 loading.tsx가 이 컴포넌트를 재노출한다. 셸(상단바·사이드바)은 layout이라 유지된다.
 * 라우트 전환 외에, 페이지 안에서 짧게 뭔가를 불러오는 동안(예: 콘텐츠 생성 화면이
 * 원본 리포트를 먼저 읽어오는 동안)에도 같은 톤으로 쓸 수 있게 message를 받는다
 * (팀장 지시로 로딩 UI 통일, 2026-08-23).
 */
export function RouteLoading({ message = "불러오는 중" }: { message?: string }) {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[320px] font-mono text-[12.5px] text-[var(--ink-3)]">
      <span>[ {message} ]</span>
      <span
        className="inline-block w-[0.6em] h-[1em] ml-[6px] bg-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]"
        aria-hidden="true"
      />
    </div>
  );
}

export default RouteLoading;
