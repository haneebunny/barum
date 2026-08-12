"use client";

import { useSyncExternalStore } from "react";

type Mode = "light" | "dark";

const listeners = new Set<() => void>();

function subscribe(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  return () => listeners.delete(onStoreChange);
}

function getSnapshot(): Mode {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function getServerSnapshot(): Mode {
  return "light";
}

function setTheme(next: Mode) {
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem("barum-theme", next);
  } catch {
    // 저장 실패해도 화면 전환 자체는 그대로 둔다 (프라이빗 모드 등)
  }
  listeners.forEach((notify) => notify());
}

export function ThemeToggle() {
  const mode = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  return (
    <div className="themetog" role="group" aria-label="테마 전환">
      <button
        type="button"
        className={mode === "light" ? "on" : undefined}
        aria-label="라이트 모드"
        title="라이트"
        onClick={() => setTheme("light")}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
        </svg>
      </button>
      <button
        type="button"
        className={mode === "dark" ? "on" : undefined}
        aria-label="다크 모드"
        title="다크"
        onClick={() => setTheme("dark")}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
          <path d="M20 14.5A8 8 0 0 1 9.5 4 7 7 0 1 0 20 14.5z" />
        </svg>
      </button>
    </div>
  );
}
