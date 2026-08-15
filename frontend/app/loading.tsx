// 루트 폴백 로딩. 자체 loading.tsx가 없는 모든 라우트(랜딩 포함)에 적용된다.
// 터미널 톤은 home/loading.tsx와 동일하게 유지.
export default function RootLoading() {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[60vh] font-mono text-[12.5px] text-[var(--ink-3)]">
      <span>[ 불러오는 중 ]</span>
      <span
        className="inline-block w-[0.6em] h-[1em] ml-[6px] bg-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]"
        aria-hidden="true"
      />
    </div>
  );
}
