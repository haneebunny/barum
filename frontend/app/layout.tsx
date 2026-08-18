import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell/AppShell";

export const metadata: Metadata = {
  title: "바름 | 화장품 광고 심의 사전검수 서비스",
  description: "이커머스 브랜드 및 셀러를 위한 화장품법 위반 위험 사전검수 콘솔. AI와 RAG 엔진을 기반으로 광고 문구와 상세페이지의 위반 소지를 실시간 분석하고 안전한 대체 표현 권고안을 제안합니다.",
  keywords: ["바름", "barum", "화장품 광고 심의", "화장품법 위반", "광고 검수", "광고 컴플라이언스", "식약처 가이드라인", "사전검수 콘솔", "화장품 셀러"],
  openGraph: {
    title: "바름 | 화장품 광고 심의 사전검수 서비스",
    description: "이커머스 브랜드를 위한 화장품법 위반 위험 사전검수 및 대체 문구 제안 솔루션",
    type: "website",
    locale: "ko_KR",
  },
};

const THEME_INIT_SCRIPT =
  "(function(){try{var s=localStorage.getItem('barum-theme');document.documentElement.setAttribute('data-theme', s||'light');var n=localStorage.getItem('barum-nav');document.documentElement.setAttribute('data-nav', n==='0'?'collapsed':'open');}catch(e){document.documentElement.setAttribute('data-theme','light');document.documentElement.setAttribute('data-nav','open');}})();";

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
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap"
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
