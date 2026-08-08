import type { Metadata } from "next";
import "./globals.css";
import { ThemeScript } from "./theme-script";
import { AppShell } from "@/components/AppShell/AppShell";

export const metadata: Metadata = {
  title: "VeriCops",
  description: "식약처 사이버조사팀 허위·과대광고 사후 모니터링 콘솔",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  // suppressHydrationWarning: ThemeScript가 하이드레이션 전에 data-theme를 바꾸므로
  // 서버 마크업과 클라이언트 초기값이 다를 수 있다. html 한 곳만 억제한다.
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link
          rel="preconnect"
          href="https://cdn.jsdelivr.net"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css"
        />
        <ThemeScript />
      </head>
      <body className="min-h-screen">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
