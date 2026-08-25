"use client";

// 랜딩 → /home 진입 시 "콘솔이 켜진다" 연출.
// 터미널 다이얼로그 규격(DESIGN.md §5: 모노, 브래킷 타이틀, radius 0, 백드롭 rgba(7,11,8,.5))을 따른다.
// 라우트 청크 로딩 시간을 겸해서 가려주는 역할도 한다.
// prefers-reduced-motion이면 연출 없이 기본 내비게이션 그대로 둔다.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const BOOT_LINES = [
  "› 바름 콘솔 연결",
  "› 검사 기준 불러오는 중 · 화장품법 제13조 / 별표5",
  "[ok] 세션 준비 완료",
];

const LINE_INTERVAL_MS = 230;
const NAVIGATE_AFTER_MS = 900;

export function useConsoleEntry() {
  const router = useRouter();
  const [booting, setBooting] = useState(false);

  useEffect(() => {
    router.prefetch("/home");
  }, [router]);

  useEffect(() => {
    if (!booting) return;
    const t = setTimeout(() => router.push("/home"), NAVIGATE_AFTER_MS);
    return () => clearTimeout(t);
  }, [booting, router]);

  // Link의 onClick에 그대로 물린다. 감소 모드면 preventDefault 하지 않아 기본 내비게이션.
  const enterConsole = (e: React.MouseEvent) => {
    // 콘솔에 들어가 본 사람 = 재방문자. 랜딩 CTA가 이 값을 보고 "내 콘솔로"로 바뀐다.
    try {
      localStorage.setItem("barum-entered", "1");
    } catch {
      // 저장 실패해도 진입 자체엔 지장 없음
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    e.preventDefault();
    setBooting(true);
  };

  return { booting, enterConsole };
}

export function BootOverlay({ show }: { show: boolean }) {
  if (!show) return null;
  return <VisibleBootOverlay />;
}

function VisibleBootOverlay() {
  const [lineCount, setLineCount] = useState(1);

  useEffect(() => {
    const t = setInterval(
      () => setLineCount(prev => Math.min(prev + 1, BOOT_LINES.length)),
      LINE_INTERVAL_MS
    );
    return () => clearInterval(t);
  }, []);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      style={{ background: "rgba(7,11,8,.5)" }}
      role="status"
      aria-live="polite"
      aria-label="콘솔로 이동 중"
    >
      <div className="w-[400px] max-w-[calc(100vw-40px)] bg-[var(--surface)] border border-[var(--line-2)] shadow-[0_14px_44px_rgba(7,11,8,0.28)] font-mono p-[18px_20px] animate-[modalin_0.16s_ease]">
        <div className="text-[var(--ink)] text-[13px] font-bold mb-[10px]">[ 콘솔 시작 ]</div>
        <div className="flex flex-col gap-[5px] text-[12px] leading-[1.5]">
          {BOOT_LINES.slice(0, lineCount).map(line => (
            <div
              key={line}
              className={line.startsWith("[ok]") ? "text-[var(--brand-ink)] font-bold" : "text-[var(--ink-2)]"}
            >
              {line}
            </div>
          ))}
        </div>
        <span className="inline-block w-[0.6em] h-[1em] mt-[6px] bg-[var(--brand-ink)] animate-[blink_1.1s_steps(1)_infinite]" aria-hidden="true" />
      </div>
    </div>
  );
}
