"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";

/** 평면 네비게이션. "공이 누구 손에" 흐름 순서(큐 → 상세 → 대시보드 → 조치 → 점검). */
const NAV = [
  { href: "/", label: "검토 큐" },
  { href: "/detail", label: "검토 상세" },
  { href: "/dashboard", label: "대시보드" },
  { href: "/action", label: "조치·이관" },
  { href: "/inspection", label: "점검 관리" },
] as const;

export function TopBar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 flex h-[58px] items-center gap-7 border-b border-line bg-surface px-6">
      {/* 브랜드 */}
      <Link href="/" className="flex items-center gap-[11px] pr-2 no-underline">
        <span className="grid h-[30px] w-[30px] place-items-center rounded-[5px] bg-navy text-[15px] font-extrabold tracking-tight text-white">
          V
        </span>
        <span className="flex flex-col leading-[1.15]">
          <span className="text-[16px] font-extrabold tracking-tight text-ink">
            VeriCops
          </span>
          <span className="mt-px text-[11px] text-ink-3">사후 모니터링 콘솔</span>
        </span>
      </Link>

      {/* 네비 */}
      <nav className="flex h-full gap-0.5">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`relative flex items-center px-[13px] text-[13.5px] no-underline transition-colors hover:text-accent ${
                active ? "font-bold text-accent" : "font-medium text-ink-2"
              }`}
            >
              {item.label}
              {active && (
                <span className="absolute inset-x-[13px] bottom-[-1px] h-0.5 bg-accent" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* 우측: 스타일가이드(개발용) + 테마 토글 */}
      <div className="ml-auto flex items-center gap-3.5">
        <Link
          href="/styleguide"
          aria-current={pathname === "/styleguide" ? "page" : undefined}
          className={`text-[12.5px] no-underline transition-colors hover:text-accent ${
            pathname === "/styleguide"
              ? "font-semibold text-accent"
              : "text-ink-3"
          }`}
        >
          스타일가이드
        </Link>
        <span className="h-6 w-px bg-line-2" />
        <ThemeToggle />
      </div>
    </header>
  );
}
