// /home 라우트 로딩 중 표시 (터미널 톤, 사이드바·상단바는 layout이라 그대로 유지됨)
export default function HomeLoading() {
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
