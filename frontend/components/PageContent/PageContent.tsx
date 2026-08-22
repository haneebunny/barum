"use client";

import type { ReactNode } from "react";

/**
 * 페이지 본문 좌우 여백을 한 곳에서 관리한다.
 * 상단에 풀블리드 스트립(브레드크럼 바 등)이 없는 페이지에서, <PageFooter> 앞까지 본문 섹션들을 감싼다.
 * 각 섹션은 여기서 상하 여백만 정하고 좌우는 이 컴포넌트에 맡긴다.
 */
export function PageContent({ children }: { children: ReactNode }) {
  return <div className="px-9">{children}</div>;
}
