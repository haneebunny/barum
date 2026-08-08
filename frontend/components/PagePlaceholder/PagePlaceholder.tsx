import type { ReactNode } from "react";

/**
 * 화면 스텁 자리표시. 이번 컷은 골격만 세우므로 실제 콘텐츠 없이
 * 화면 제목·용도만 렌더한다. 후속 컷에서 각 page가 실내용으로 대체된다.
 */
export function PagePlaceholder({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <section>
      <header className="flex items-baseline gap-3.5">
        <h1 className="m-0 text-[22px] font-extrabold tracking-tight text-ink">
          {title}
        </h1>
        {subtitle && <p className="m-0 text-[12.5px] text-ink-3">{subtitle}</p>}
      </header>

      <div className="mt-4 rounded-card border border-line bg-surface p-5 shadow-card">
        <p className="m-0 text-[13px] text-ink-2">
          이 화면은 골격만 준비돼 있습니다. 실제 목록·판단·조치 콘텐츠는 후속
          컷에서 구현됩니다.
        </p>
        {children}
      </div>
    </section>
  );
}
