import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell/AppShell";

export const metadata: Metadata = {
  title: "바름",
  description: "셀러용 광고 규제 사전검수 콘솔",
};

const THEME_INIT_SCRIPT =
  "(function(){try{var s=localStorage.getItem('barum-theme');document.documentElement.setAttribute('data-theme', s||'light');}catch(e){document.documentElement.setAttribute('data-theme','light');}})();";

export default function RootLayout({ children }: LayoutProps<"/">) {
  // suppressHydrationWarning: 위 스크립트가 하이드레이션 전에 data-theme를 바꿔서
  // 서버 마크업과 클라이언트 초기값이 다를 수 있다. html 한 곳만 억제한다.
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- app router라 _document 없음, 목업과 동일한 CDN 폰트 */}
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css"
        />
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
