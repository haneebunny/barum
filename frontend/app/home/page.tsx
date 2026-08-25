"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { PageContent } from "@/components/PageContent/PageContent";
import { HistoryRow, HistoryRowList } from "@/components/HistoryRow/HistoryRow";
import { recentHistory, rowProps, type HistoryStatus } from "@/lib/mockHistory";
import { DEMO_RESULT_ID } from "@/lib/demo/demo";
import { grantDemoAccess } from "@/lib/tickets";

type RegionChoice = "kr" | "ex" | null;

const CONTINUE_ITEMS = recentHistory(3);

function continueHref(result_id: string, status: HistoryStatus) {
  return status === "draft" ? `/inspect?id=${result_id}` : `/report/${result_id}`;
}

const WORKFLOW_STEPS = [
  { icon: "map-pin", label: "판매 지역 선택" },
  { icon: "photo", label: "광고 입력" },
  { icon: "list-details", label: "제품 정보", optional: true },
  { icon: "search", label: "검사 실행" },
  { icon: "report", label: "결과 확인" },
];

function WorkflowIcon({ name }: { name: string }) {
  switch (name) {
    case "map-pin":
      return (
        <svg className="w-[15px] h-[15px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
          <path d="M12 21c-4-4-8-7.5-8-12a8 8 0 1 1 16 0c0 4.5-4 8-8 12z" />
          <circle cx="12" cy="9" r="2.5" />
        </svg>
      );
    case "photo":
      return (
        <svg className="w-[15px] h-[15px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
          <rect x="3" y="3" width="18" height="18" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="M21 15l-5-5L5 21" />
        </svg>
      );
    case "list-details":
      return (
        <svg className="w-[15px] h-[15px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
          <path d="M13 5h8M13 9h5M13 15h8M13 19h5M3 5l3 0M3 9l3 0M3 15l3 0M3 19l3 0" />
        </svg>
      );
    case "search":
      return (
        <svg className="w-[15px] h-[15px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
          <circle cx="11" cy="11" r="7" />
          <path d="M16 16l5 5" />
        </svg>
      );
    case "report":
      return (
        <svg className="w-[15px] h-[15px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
          <rect x="3" y="3" width="18" height="18" />
          <path d="M8 16V12M12 16V8M16 16v-2" />
        </svg>
      );
    default:
      return null;
  }
}

export default function HomePage() {
  const router = useRouter();
  const [region, setRegion] = useState<RegionChoice>(null);
  const [selectedCountry, setSelectedCountry] = useState("미국 FDA·FTC");

  useEffect(() => {
    try {
      localStorage.setItem("barum-entered", "1");
    } catch {
      /* noop */
    }
  }, []);

  const handleStart = () => {
    if (!region) return;
    if (region === "ex" && selectedCountry === "미국 FDA·FTC") {
      router.push("/inspect?region=us");
    } else {
      router.push("/inspect");
    }
  };

  // 심사위원 데모: 유어베리 세럼으로 프리필된 검사 화면으로. 이용권을 미리 채워 페이월을 우회한다.
  const handleDemo = () => {
    grantDemoAccess();
    router.push(`/inspect?id=${DEMO_RESULT_ID}`);
  };

  return (
    <>
      <PageContent>
        {/* 헤더 */}
        <div className="pt-[48px] pb-[6px]">
          <h1 className="m-0 text-[var(--ink)] text-[26px] font-extrabold tracking-[-0.3px] whitespace-nowrap flex items-center gap-2">
            <span className="text-[var(--brand-ink)] font-mono">›</span>
            무엇을 검사할까요?
            <span className="inline-block w-[0.14em] h-[1em] bg-[var(--brand-ink)] align-[-2px] animate-[blink_1.1s_steps(1)_infinite]" aria-hidden="true" />
          </h1>
        </div>

        {/* 지역 선택 카드 */}
        <div className="pt-[24px] pb-[4px]">
          <div className="flex gap-0">
            <button
              type="button"
              onClick={() => setRegion("kr")}
              className={`flex-1 text-left border border-[var(--line-2)] bg-[var(--surface)] cursor-pointer transition-[border-color] duration-150 hover:border-[var(--brand-ink)] ${
                region === "kr" ? "border-[var(--brand-deep)] border-2" : ""
              }`}
              style={{ borderRight: region === "kr" ? undefined : "none" }}
            >
              <div className={`h-[3px] transition-colors duration-150 ${region === "kr" ? "bg-[var(--brand-deep)]" : "bg-[var(--line-2)]"}`} />
              <div className="p-[20px_18px]">
                <div className="flex items-center gap-[10px] mb-[8px]">
                  <span className={`w-[32px] h-[32px] flex items-center justify-center border text-[15px] transition-colors duration-150 ${
                    region === "kr"
                      ? "bg-[var(--brand-deep)] text-[var(--on-brand)] border-[var(--brand-deep)]"
                      : "border-[var(--line-2)] text-[var(--ink-3)]"
                  }`}>
                    <svg className="w-[16px] h-[16px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
                      <path d="M3 21h18M5 21V7l8-4 8 4v14" />
                      <path d="M9 9h1M14 9h1M9 13h1M14 13h1M9 17h1M14 17h1" />
                    </svg>
                  </span>
                  <span className="text-[16px] font-bold text-[var(--ink)]">국내</span>
                </div>
                <span className="font-mono text-[10.5px] text-[var(--ink-3)]">화장품법 제13조 기준</span>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setRegion("ex")}
              className={`flex-1 text-left border border-[var(--line-2)] bg-[var(--surface)] cursor-pointer transition-[border-color] duration-150 hover:border-[var(--brand-ink)] ${
                region === "ex" ? "border-[var(--brand-deep)] border-2" : ""
              }`}
            >
              <div className={`h-[3px] transition-colors duration-150 ${region === "ex" ? "bg-[var(--brand-deep)]" : "bg-[var(--line-2)]"}`} />
              <div className="p-[20px_18px]">
                <div className="flex items-center gap-[10px] mb-[8px]">
                  <span className={`w-[32px] h-[32px] flex items-center justify-center border text-[15px] transition-colors duration-150 ${
                    region === "ex"
                      ? "bg-[var(--brand-deep)] text-[var(--on-brand)] border-[var(--brand-deep)]"
                      : "border-[var(--line-2)] text-[var(--ink-3)]"
                  }`}>
                    <svg className="w-[16px] h-[16px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
                      <path d="M2 12h5l2.5-8 5 16 2.5-8H22" />
                    </svg>
                  </span>
                  <span className="text-[16px] font-bold text-[var(--ink)]">해외</span>
                </div>
                <span className="font-mono text-[10.5px] text-[var(--ink-3)]">수출 대상국 규정 기준</span>
              </div>
            </button>
          </div>

          {/* 해외 선택 시 나라 선택 패널 */}
          {region === "ex" && (
            <div className="border border-t-0 border-[var(--line-2)] bg-[var(--surface-sub)] p-[10px_14px]">
              <span className="font-mono text-[10.5px] text-[var(--ink-3)]">› 대상국 선택</span>
              <div className="flex gap-[6px] mt-[8px] flex-wrap">
                <button
                  type="button"
                  onClick={() => setSelectedCountry("미국 FDA·FTC")}
                  className={`font-mono text-[11px] p-[5px_12px] border cursor-pointer transition-all duration-100 ${
                    selectedCountry === "미국 FDA·FTC"
                      ? "bg-[var(--brand-deep)] text-[var(--on-brand)] border-[var(--brand-deep)]"
                      : "bg-transparent text-[var(--ink-3)] border-[var(--line-2)] hover:border-[var(--brand-ink)] hover:text-[var(--ink)]"
                  }`}
                >
                  미국 FDA·FTC
                </button>
                <button type="button" disabled className="font-mono text-[11px] p-[5px_12px] border border-[var(--line-2)] bg-transparent text-[var(--ink-3)] opacity-40 cursor-not-allowed">
                  EU 준비 중
                </button>
                <button type="button" disabled className="font-mono text-[11px] p-[5px_12px] border border-[var(--line-2)] bg-transparent text-[var(--ink-3)] opacity-40 cursor-not-allowed">
                  일본 준비 중
                </button>
                <button type="button" disabled className="font-mono text-[11px] p-[5px_12px] border border-[var(--line-2)] bg-transparent text-[var(--ink-3)] opacity-40 cursor-not-allowed">
                  중국 준비 중
                </button>
              </div>
            </div>
          )}

          {/* 검사 시작 버튼 */}
          {region && (
            <button
              type="button"
              onClick={handleStart}
              className="mt-[14px] w-full p-[11px] border-0 bg-[var(--brand-deep)] text-[var(--on-brand)] font-mono text-[12px] font-bold cursor-pointer transition-colors duration-100 hover:bg-[var(--brand)] tracking-[0.3px]"
            >
              검사 시작 →
            </button>
          )}

          {/* 심사위원 데모 체험 (유어베리 세럼, 프리필 + 픽스처) */}
          <button
            type="button"
            onClick={handleDemo}
            className="mt-[10px] w-full p-[10px] border border-[var(--brand-deep)] bg-transparent text-[var(--brand-deep)] font-mono text-[12px] font-bold cursor-pointer transition-colors duration-100 hover:bg-[var(--brand-deep)] hover:text-[var(--on-brand)] tracking-[0.3px]"
          >
            데모로 체험하기 (유어베리 세럼) →
          </button>
        </div>

        {/* 구분선 */}
        <div className="border-t border-dashed border-[var(--line)] my-[28px]" />

        {/* 이어서 하기 */}
        <div className="pb-[8px]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">
              <svg className="w-3.25 h-3.25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="square">
                <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
                <path d="M3 3v5h5" />
              </svg>
            </span>
            <h2 className="m-0 text-[15px] font-bold text-[var(--ink)] tracking-[-0.2px]">이어서 하기</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
            <span className="text-[var(--ink-3)] font-mono text-[12px]">최근 3</span>
          </div>

          <HistoryRowList>
            {CONTINUE_ITEMS.map(item => (
              <HistoryRow
                key={item.result_id}
                href={continueHref(item.result_id, item.status)}
                {...rowProps(item)}
              />
            ))}
          </HistoryRowList>
        </div>

        {/* 구분선 */}
        <div className="border-t border-dashed border-[var(--line)] my-[28px]" />

        {/* 검사 워크플로우 */}
        <div className="pb-[4px]">
          <div className="flex items-center gap-[8px] mb-[14px]">
            <span className="font-mono text-[10.5px] text-[var(--ink-3)] tracking-[0.5px]">검사 워크플로우</span>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line)]" />
          </div>

          <div className="flex items-start">
            {WORKFLOW_STEPS.map((step, i) => (
              <div key={step.icon} className="contents">
                {i > 0 && (
                  <span className="font-mono text-[11px] text-[var(--line-2)] pt-[8px] shrink-0 select-none">→</span>
                )}
                <div className="flex-1 flex flex-col items-center gap-[6px]">
                  <span
                    className={`w-[30px] h-[30px] flex items-center justify-center border-[1.5px] ${
                      i === 0
                        ? "bg-[var(--brand-deep)] text-[var(--on-brand)] border-[var(--brand-deep)]"
                        : step.optional
                          ? "bg-[var(--surface)] text-[var(--ink-3)] border-dashed border-[var(--line-2)]"
                          : "bg-[var(--surface)] text-[var(--ink-3)] border-[var(--line-2)]"
                    }`}
                  >
                    <WorkflowIcon name={step.icon} />
                  </span>
                  <span className={`text-[11px] text-center leading-[1.35] max-w-[72px] ${
                    step.optional ? "text-[var(--ink-3)]" : "text-[var(--ink-2)]"
                  }`}>
                    {step.label}
                    {step.optional && <><br /><span className="font-mono text-[9.5px]">(선택)</span></>}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </PageContent>

      <PageFooter />
    </>
  );
}
