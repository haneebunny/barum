import type { ReactNode } from "react";
import { TopBar } from "@/components/TopBar/TopBar";

/**
 * 앱 셸: 고정 상단바 + 가운데 정렬 콘텐츠 영역.
 * shell 폭·패딩은 목업 .shell(max-width:1560px; padding:0 24px)과 동일.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-[1560px] px-6 py-6">{children}</main>
    </div>
  );
}
