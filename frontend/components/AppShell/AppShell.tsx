"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { Dropdown } from "@/components/Dropdown/Dropdown";
import { TierProvider } from "@/lib/tier";

const navListeners = new Set<() => void>();

function subscribeNav(onStoreChange: () => void) {
  navListeners.add(onStoreChange);
  return () => navListeners.delete(onStoreChange);
}

function getNavSnapshot(): boolean {
  try {
    return localStorage.getItem("barum-nav") === "0";
  } catch {
    return false;
  }
}

function getNavServerSnapshot(): boolean {
  return false;
}

function toggleNav(current: boolean) {
  const next = !current;
  try {
    localStorage.setItem("barum-nav", next ? "0" : "1");
  } catch {
    // 저장 실패해도 이번 화면에서는 그대로 토글
  }
  // pre-paint CSS(globals.css의 html[data-nav="collapsed"] 규칙)와 상태를 맞춘다
  document.documentElement.setAttribute("data-nav", next ? "collapsed" : "open");
  navListeners.forEach((notify) => notify());
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const collapsed = useSyncExternalStore(subscribeNav, getNavSnapshot, getNavServerSnapshot);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const isLandingPage = pathname === "/";

  const handleLogout = () => {
    setIsProfileOpen(false);
    if (window.confirm("로그아웃 하시겠습니까?")) {
      alert("로그아웃 되었습니다.");
      router.push("/");
    }
  };

  return (
    <TierProvider>
      <div className={`w-full transition-all duration-200 ${isLandingPage ? "max-w-none" : "flex flex-col max-w-[1480px] bg-[var(--surface)] border border-[var(--line-2)] shadow-[0_1px_3px_rgba(20,35,27,0.05),0_10px_34px_rgba(20,35,27,0.045)]"}`}>
        {!isLandingPage && (
          <div className="flex items-center gap-3 p-[11px_15px] border-b border-[var(--line-2)] bg-[var(--surface-sub)]">
            <Link href="/home" className="flex items-center gap-3 no-underline cursor-pointer">
              <svg className="w-8 h-8 shrink-0 block" viewBox="0 0 170 170" fill="none" role="img" aria-label="바름">
                <circle cx="101.542" cy="97.5538" r="42.3692" fill="#95DDB7" />
                <circle cx="67.8038" cy="72.4461" r="42.3692" fill="#00813E" fillOpacity="0.5" />
              </svg>
              <span className="text-[var(--ink)] inline-flex items-center" aria-label="바름">
                <svg
                  className="h-5 w-auto block"
                  viewBox="2.6 -86.2 176.8 98.2"
                  role="img"
                  aria-label="바름"
                >
                  <path
                    fill="currentColor"
                    stroke="currentColor"
                    strokeWidth={3.5}
                    strokeLinejoin="round"
                    paintOrder="stroke"
                    d="M77.10 1.20Q77.10 2.50 77.95 3.30Q78.80 4.10 81.40 5L81.40 5L72.10 9.80Q71.70 10 71.30 10L71.30 10Q70.80 10 70.40 9.50L70.40 9.50Q69.80 8.60 69.45 7.45Q69.10 6.30 69.10 4.30L69.10 4.30L69.10-76.30Q69.10-77.60 68.25-78.40Q67.40-79.20 64.80-80.10L64.80-80.10L74.10-84Q74.50-84.20 74.90-84.20L74.90-84.20Q77.10-84.20 77.10-78.20L77.10-78.20L77.10-40.50L91.50-40.50L89.90-35L77.10-35L77.10 1.20ZM8.40-65.30Q8.40-66.80 7.60-67.65Q6.80-68.50 4.60-69.50L4.60-69.50L13.40-73Q14.80-73.60 15.60-72.15Q16.40-70.70 16.40-67.50L16.40-67.50L16.40-48.40L43.40-48.40L43.40-67.70Q43.40-69.20 42.60-70.05Q41.80-70.90 39.60-71.90L39.60-71.90L48.10-75.40Q49.50-76 50.30-74.55Q51.10-73.10 51.10-69.90L51.10-69.90L51.10-15.70Q54.40-16 57.60-16.30L57.60-16.30L55.70-9.90L29.60-9.90Q22.70-9.90 17-8.80Q11.30-7.70 7.40-5.70L7.40-5.70Q7.80-7.50 8.10-10.35Q8.40-13.20 8.40-15.90L8.40-15.90L8.40-65.30ZM16.40-12.70Q19.20-14.30 22.40-15Q25.60-15.70 30.60-15.70L30.60-15.70L43.40-15.70L43.40-42.80L16.40-42.80L16.40-12.70ZM105.60-75L107.60-80.30L166.40-80.30Q165.50-76.30 165.50-73.50L165.50-73.50L165.50-60.20L115.20-60.20L115.20-49.10Q117.70-49.80 120.95-50.05Q124.20-50.30 129.40-50.30L129.40-50.30L167.80-50.30L166.20-45.20L128.50-45.20Q120.90-45.20 116.25-44.75Q111.60-44.30 106.60-43.20L106.60-43.20Q107.20-46.40 107.20-51L107.20-51L107.20-58.80Q107.20-62.20 105.60-65.20L105.60-65.20L157.50-65.20L157.50-75L105.60-75ZM114.60 3.30Q119.60 2.70 128.80 2.70L128.80 2.70L157.80 2.70L157.80-14L114.60-14L114.60 3.30ZM101.90-29.20Q98.70-29.20 97.25-29.85Q95.80-30.50 95.80-31.50L95.80-31.50Q95.80-32 96.10-32.30L96.10-32.30L100.50-37.80Q101.50-36 102.55-35.40Q103.60-34.80 105.20-34.80L105.20-34.80L177.40-34.80L175.80-29.20L101.90-29.20ZM105.40-19L166.70-19Q165.80-16 165.80-12.20L165.80-12.20L165.80 2.60Q168.40 2.40 170.20 2L170.20 2L168.30 8L127.80 8Q114.20 8 105.50 9.90L105.50 9.90Q106 8.60 106.30 6.35Q106.60 4.10 106.60 2L106.60 2L106.60-11Q106.60-15.90 105.40-19L105.40-19Z"
                  />
                </svg>
              </span>
            </Link>
            <div className="ml-auto flex items-center gap-2.5 relative">
              <ThemeToggle />
              <button
                type="button"
                className="flex items-center gap-2 bg-transparent border-0 cursor-pointer p-1 text-[var(--ink-3)] hover:text-[var(--ink)] focus:outline-none"
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                aria-haspopup="true"
                aria-expanded={isProfileOpen}
                aria-label="사용자 프로필 메뉴"
              >
                <span className="text-[12px]">
                  브랜드 <b className="text-[var(--ink-2)] font-semibold">yourberry</b>
                </span>
                <span className="w-6 h-6 border border-[var(--line-2)] text-[var(--brand-ink)] inline-flex items-center justify-center font-mono text-[11px] font-bold">YB</span>
              </button>

              <Dropdown isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} className="w-36 right-0">
                <Link
                  href="/mypage"
                  className="p-[10px_14px] hover:bg-[var(--nav-hover)] text-[var(--ink-2)] hover:text-[var(--ink)] no-underline text-left"
                  onClick={() => setIsProfileOpen(false)}
                >
                  마이페이지
                </Link>
                <button
                  type="button"
                  className="p-[10px_14px] hover:bg-[var(--nav-hover)] text-[var(--crit)] border-0 bg-transparent text-left cursor-pointer font-mono font-medium"
                  onClick={handleLogout}
                >
                  로그아웃
                </button>
              </Dropdown>
            </div>
          </div>
        )}

        <div className={isLandingPage ? "w-full" : `app-side-grid grid flex-1 max-[900px]:flex max-[900px]:flex-col transition-[grid-template-columns] duration-[220ms] ease-in-out ${collapsed ? "grid-cols-[56px_minmax(0,1fr)]" : "grid-cols-[216px_minmax(0,1fr)]"}`}>
          {!isLandingPage && (
            <aside className="bg-[var(--surface-sub)] border-r border-[var(--line-2)] overflow-hidden max-[900px]:fixed max-[900px]:bottom-0 max-[900px]:left-0 max-[900px]:right-0 max-[900px]:z-40 max-[900px]:w-full max-[900px]:h-auto max-[900px]:border-r-0 max-[900px]:border-t max-[900px]:border-[var(--line-2)]">
              <div className={`w-full h-full flex flex-col gap-2 max-[900px]:flex-row max-[900px]:p-[8px_12px] max-[900px]:justify-around max-[900px]:items-center ${collapsed ? "p-[13px_8px] items-center" : "p-[13px_11px]"}`}>
                {/* 접힌 상태: 펼침 토글을 레일 최상단에 아이콘 단독으로 */}
                {collapsed && (
                  <button
                    type="button"
                    className="inline-flex items-center justify-center w-10 p-[10px_0] border-0 bg-transparent text-[var(--ink-3)] cursor-pointer transition-all duration-[120ms] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)] max-[900px]:hidden"
                    onClick={() => toggleNav(collapsed)}
                    aria-label="사이드바 펼치기"
                    aria-expanded={false}
                    title="사이드바 펼치기"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </button>
                )}
                <nav className={`flex flex-col gap-[2px] mt-[2px] max-[900px]:flex-row max-[900px]:mt-0 max-[900px]:w-full max-[900px]:justify-around ${collapsed ? "items-center" : ""}`}>
                  {/* 홈 행: 펼친 상태에선 오른쪽에 접기 토글을 나란히 (클릭 영역은 분리) */}
                  <div className={collapsed ? "contents" : "flex items-center max-[900px]:contents"}>
                    <Link href="/home" className={`flex items-center text-[13px] no-underline transition-all duration-[120ms] ${collapsed ? "w-10 p-[10px_0] justify-center gap-0" : "flex-1 gap-[11px] p-[9px_11px]"
                      } max-[900px]:flex-col max-[900px]:items-center max-[900px]:flex-1 max-[900px]:justify-center max-[900px]:p-2 max-[900px]:gap-1 ${pathname === "/home"
                        ? "bg-[var(--nav-active-bg)] text-[var(--ink)] font-bold"
                        : "text-[var(--ink-2)] cursor-pointer hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                      }`} title="홈">
                      <svg className="w-[17px] h-[17px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                        <path d="M4 11 12 4l8 7" />
                        <path d="M6 10v9h12v-9" />
                      </svg>
                      <span className={`app-side-expanded-only whitespace-nowrap ${collapsed ? "hidden" : ""} max-[900px]:!inline max-[900px]:text-[10px]`}>홈</span>
                    </Link>
                    {!collapsed && (
                      <button
                        type="button"
                        className="app-side-expanded-only inline-flex items-center justify-center shrink-0 ml-[2px] p-[8px_6px] border-0 bg-transparent text-[var(--ink-3)] cursor-pointer transition-all duration-[120ms] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)] max-[900px]:hidden"
                        onClick={() => toggleNav(collapsed)}
                        aria-label="사이드바 접기"
                        aria-expanded={true}
                        title="사이드바 접기"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
                          <path d="M15 6l-6 6 6 6" />
                        </svg>
                      </button>
                    )}
                  </div>
                  <Link href="/history" className={`flex items-center text-[13px] no-underline transition-all duration-[120ms] ${collapsed ? "w-10 p-[10px_0] justify-center gap-0" : "gap-[11px] p-[9px_11px]"
                    } max-[900px]:flex-col max-[900px]:items-center max-[900px]:flex-1 max-[900px]:justify-center max-[900px]:p-2 max-[900px]:gap-1 ${pathname === "/history"
                      ? "bg-[var(--nav-active-bg)] text-[var(--ink)] font-bold"
                      : "text-[var(--ink-2)] cursor-pointer hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                    }`} title="검사 이력">
                    <svg className="w-[17px] h-[17px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                      <path d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                    <span className={`app-side-expanded-only whitespace-nowrap ${collapsed ? "hidden" : ""} max-[900px]:!inline max-[900px]:text-[10px]`}>검사 이력</span>
                  </Link>
                  <Link href="/mypage" className={`flex items-center text-[13px] no-underline transition-all duration-[120ms] ${collapsed ? "w-10 p-[10px_0] justify-center gap-0" : "gap-[11px] p-[9px_11px]"
                    } max-[900px]:flex-col max-[900px]:items-center max-[900px]:flex-1 max-[900px]:justify-center max-[900px]:p-2 max-[900px]:gap-1 ${pathname === "/mypage"
                      ? "bg-[var(--nav-active-bg)] text-[var(--ink)] font-bold"
                      : "text-[var(--ink-2)] cursor-pointer hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                    }`} title="마이페이지">
                    <svg className="w-[17px] h-[17px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                      <circle cx="12" cy="8" r="3.5" />
                      <path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6" />
                    </svg>
                    <span className={`app-side-expanded-only whitespace-nowrap ${collapsed ? "hidden" : ""} max-[900px]:!inline max-[900px]:text-[10px]`}>마이페이지</span>
                  </Link>
                </nav>
              </div>
            </aside>
          )}

          <main className={`min-w-0 flex flex-col ${isLandingPage ? "" : "max-[900px]:pb-[70px]"}`}>{children}</main>
        </div>
      </div>
    </TierProvider>
  );
}
