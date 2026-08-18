"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { Warning, ShieldWarning, Question, ArrowsClockwise } from "@phosphor-icons/react";
import type { USPreflightReport, USPreflightFinding, USPreflightCategory } from "@/lib/api/schema";
import { PageFooter } from "@/components/PageFooter/PageFooter";

const CATEGORY_META: Record<
  USPreflightCategory,
  { label: string; desc: string; isCrit: boolean }
> = {
  "OTC의약품_분류전환": {
    label: "OTC 의약품 분류 전환",
    desc: "미국에서는 화장품이 아닌 OTC 의약품으로 규제됩니다",
    isCrit: false,
  },
  "미국_미승인_성분": {
    label: "미국 FDA 미승인 성분",
    desc: "미국 FDA 승인 목록에 없는 자외선차단 성분입니다",
    isCrit: true,
  },
  "성분정보_확인불가": {
    label: "성분 정보 확인 불가",
    desc: "전성분 정보가 없어 성분 적합성을 확인할 수 없습니다",
    isCrit: false,
  },
};

function CategoryIcon({ category }: { category: USPreflightCategory }) {
  if (category === "미국_미승인_성분") {
    return <ShieldWarning size={16} weight="bold" className="text-[var(--crit)] shrink-0" />;
  }
  if (category === "OTC의약품_분류전환") {
    return <ArrowsClockwise size={16} weight="bold" className="text-[var(--ink-2)] shrink-0" />;
  }
  return <Question size={16} weight="bold" className="text-[var(--ink-3)] shrink-0" />;
}

function FindingCard({ finding, index }: { finding: USPreflightFinding; index: number }) {
  const meta = CATEGORY_META[finding.category];

  return (
    <div
      className={`border p-[16px_18px] ${
        meta.isCrit
          ? "border-[var(--crit-bd)] bg-[var(--crit-bg)]"
          : "border-[var(--line-2)] bg-[var(--surface)]"
      }`}
    >
      <div className="flex items-start gap-3 mb-3">
        <span className="font-mono text-[11px] font-bold text-[var(--on-brand)] bg-[var(--brand-deep)] p-[2px_6px] shrink-0 leading-[1.4]">
          {String(index + 1).padStart(2, "0")}
        </span>
        <CategoryIcon category={finding.category} />
        <div className="flex-1 min-w-0">
          <span
            className={`text-[12px] font-bold font-mono ${
              meta.isCrit ? "text-[var(--crit)]" : "text-[var(--ink-2)]"
            }`}
          >
            {meta.label}
          </span>
        </div>
      </div>

      <div className="ml-[52px]">
        <div className="mb-2">
          <span
            className={`inline font-semibold text-[13.5px] ${
              meta.isCrit
                ? "text-[var(--crit)] underline decoration-[var(--crit)] underline-offset-2"
                : "text-[var(--ink)] underline decoration-[var(--ink-3)] underline-offset-2"
            }`}
          >
            {finding.span}
          </span>
        </div>

        {finding.sentence !== finding.span && (
          <p className="text-[12.5px] text-[var(--ink-3)] mb-2 leading-[1.6]">
            원문: {finding.sentence}
          </p>
        )}

        <p className="text-[13px] text-[var(--ink-2)] leading-[1.65]">{finding.explanation}</p>
      </div>
    </div>
  );
}

interface USReportClientProps {
  resultId: string;
}

export function USReportClient({ resultId }: USReportClientProps) {
  const [report, setReport] = useState<USPreflightReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem(`us-preflight-${resultId}`);
    if (!raw) {
      setError("리포트 데이터를 찾을 수 없습니다. 검사 화면에서 다시 시도해 주세요.");
      return;
    }
    try {
      setReport(JSON.parse(raw));
    } catch {
      setError("리포트 데이터를 파싱할 수 없습니다.");
    }
  }, [resultId]);

  if (error) {
    return (
      <>
        <div className="p-[24px] text-center">
          <Warning size={32} className="text-[var(--crit)] mx-auto mb-3" />
          <p className="text-[var(--ink)] text-[14px] font-semibold mb-2">{error}</p>
          <Link
            href="/inspect?region=US"
            className="text-[var(--brand-ink)] text-[13px] underline"
          >
            해외 수출 검증으로 돌아가기
          </Link>
        </div>
        <PageFooter />
      </>
    );
  }

  if (!report) {
    return (
      <div className="p-[24px] text-[var(--ink-3)] text-[13px]">로딩 중...</div>
    );
  }

  const { findings, summary, disclaimer } = report;
  const critCount = findings.filter((f) => f.category === "미국_미승인_성분").length;
  const otcCount = findings.filter((f) => f.category === "OTC의약품_분류전환").length;
  const missingCount = findings.filter((f) => f.category === "성분정보_확인불가").length;

  return (
    <>
      {/* 브레드크럼 */}
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
        <span className="text-[var(--ink-2)]">
          <Link href="/" className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]">
            홈
          </Link>{" "}
          <span className="text-[var(--ink-3)]">›</span> 해외 수출 검증{" "}
          <span className="text-[var(--ink-3)]">›</span> 미국{" "}
          <span className="text-[var(--ink-3)]">›</span> 리포트
        </span>
      </div>

      {/* 요약 바 */}
      <div className="p-[16px_20px] border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="flex items-center gap-4 flex-wrap">
          <h1 className="text-[15px] font-bold text-[var(--ink)] m-0">
            미국 수출 프리플라이트
          </h1>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />

          <div className="flex items-center gap-4 font-mono text-[12px]">
            <span className="text-[var(--ink-3)]">
              검사 문장 <span className="text-[var(--ink-2)] font-bold">{summary.n_sentences}</span>
            </span>
            <span className="text-[var(--ink-3)]">
              지적{" "}
              <span
                className={`font-bold ${
                  summary.n_findings > 0 ? "text-[var(--crit)]" : "text-[var(--ink-2)]"
                }`}
              >
                {summary.n_findings}
              </span>
            </span>
          </div>
        </div>

        {/* 카테고리별 건수 태그 */}
        {summary.n_findings > 0 && (
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            {critCount > 0 && (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] p-[3px_8px] border border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)]">
                <ShieldWarning size={12} weight="bold" />
                미승인 성분 {critCount}
              </span>
            )}
            {otcCount > 0 && (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] p-[3px_8px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)]">
                <ArrowsClockwise size={12} weight="bold" />
                분류 전환 {otcCount}
              </span>
            )}
            {missingCount > 0 && (
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] p-[3px_8px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-3)]">
                <Question size={12} weight="bold" />
                확인 불가 {missingCount}
              </span>
            )}
          </div>
        )}
      </div>

      {/* 지적 카드 목록 */}
      <div className="p-[18px_20px_24px]">
        {findings.length === 0 ? (
          <div className="text-center p-[40px_20px]">
            <p className="text-[var(--ink-2)] text-[14px] font-semibold mb-1">
              지적 사항 없음
            </p>
            <p className="text-[var(--ink-3)] text-[12.5px]">
              입력된 자료에서 미국 자외선차단 규제 관련 이슈가 발견되지 않았습니다.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {findings.map((finding, idx) => (
              <FindingCard key={idx} finding={finding} index={idx} />
            ))}
          </div>
        )}
      </div>

      {/* 하단 액션 */}
      <div className="p-[14px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] flex items-center justify-between flex-wrap gap-3">
        <Link
          href="/inspect?region=US"
          className="font-sans text-[13px] font-semibold p-[9px_14px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] transition-colors inline-flex items-center gap-1.5 no-underline"
        >
          <span className="font-mono">←</span> 다시 검사
        </Link>
      </div>

      {/* disclaimer 푸터 */}
      <div className="p-[10px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] text-[11px] text-[var(--ink-3)] leading-[1.65]">
        {disclaimer}
      </div>

      <PageFooter />
    </>
  );
}
