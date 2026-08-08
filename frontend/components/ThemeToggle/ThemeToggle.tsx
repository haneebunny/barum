"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "@phosphor-icons/react";

type Theme = "light" | "dark";

/**
 * 다크/라이트 토글. 클릭 시 <html data-theme> 전환 + localStorage 저장.
 *
 * 테마의 진실 소스는 React state가 아니라 <html data-theme> 속성이다(FOUC 스크립트가
 * 하이드레이션 전에 이미 확정한다). 그래서 useSyncExternalStore로 그 속성을 '구독'해
 * 읽는다. 이러면 effect 안 setState 없이도 아이콘이 맞고, SSR 불일치도 없다.
 */

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}

function getSnapshot(): Theme {
  return document.documentElement.getAttribute("data-theme") === "dark"
    ? "dark"
    : "light";
}

// 서버·초기 하이드레이션에서는 값을 모른다(null → 자리만 잡고 아이콘은 마운트 후).
function getServerSnapshot(): Theme | null {
  return null;
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      // localStorage 차단 환경(사생활 모드 등)은 세션 한정 토글로 감수한다.
    }
  }

  const isDark = theme === "dark";
  const label = isDark ? "라이트 모드로 전환" : "다크 모드로 전환";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="grid h-9 w-9 place-items-center rounded-app text-ink-2 hover:bg-surface-sub hover:text-ink"
    >
      {/* theme 미확정(null) 동안은 아이콘 없이 자리만 잡아 레이아웃 이동을 막는다 */}
      {theme === null ? null : isDark ? (
        <Sun size={18} weight="regular" />
      ) : (
        <Moon size={18} weight="regular" />
      )}
    </button>
  );
}
