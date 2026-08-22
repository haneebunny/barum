"use client";

import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}

/**
 * 페이지 최상단 타이틀 행. 상단 여백·폰트 크기·간격을 여기 하나로 고정한다.
 * history/mypage가 각자 pt-44px/26px, 22px/20px로 따로 정의하면서 서로 어긋났던 문제(2026-08-22) 이후.
 */
export function PageHeader({ title, subtitle, right }: PageHeaderProps) {
  return (
    <div className="pt-[36px]">
      <div className="flex items-center gap-3.5 flex-wrap">
        <h1 className="m-0 text-[var(--ink)] text-[21px] font-extrabold tracking-[-0.4px] whitespace-nowrap">{title}</h1>
        {subtitle && <span className="font-mono text-[11px] text-[var(--ink-3)]">{subtitle}</span>}
        {right && <span className="ml-auto">{right}</span>}
      </div>
    </div>
  );
}
