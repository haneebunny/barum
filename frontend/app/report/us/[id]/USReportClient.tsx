"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { Check, Minus, Warning, ShieldWarning, Question, ArrowsClockwise } from "@phosphor-icons/react";
import type {
  ExportReadinessCategory,
  ExportReadinessStatus,
  ReadinessItem,
  USExportReadinessReport,
  ExportReadinessReport,
  GenericReadinessItem,
  USPreflightReport,
  USPreflightFinding,
  USPreflightCategory,
} from "@/lib/api/schema";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { getReport, getUSExportReadiness } from "@/lib/api/client";

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

const READINESS_STATUS_META: Record<
  ExportReadinessStatus,
  { label: string; className: string }
> = {
  COMPLIANT: { label: "준비됨", className: "text-[var(--brand-ink)]" },
  REQUIRED_CHANGE: { label: "준비 필요", className: "text-[var(--crit)]" },
  VERIFICATION_REQUIRED: { label: "확인 필요", className: "text-[var(--ink-2)]" },
  NOT_ASSESSED: { label: "미입력", className: "text-[var(--ink-3)]" },
  BLOCKER: { label: "별도 경로 검토 필요", className: "text-[var(--crit)]" },
};

const READINESS_CATEGORY_META: Record<ExportReadinessCategory, string> = {
  CLASSIFICATION: "미국 규제 분류",
  FORMULA: "성분·처방",
  TESTING: "시험자료",
  LABELING: "라벨·Drug Facts",
  CLAIMS: "광고 claim",
  ESTABLISHMENT: "제조시설·U.S. Agent",
  LISTING_IMPORT: "Drug Listing·수입",
};

const READINESS_CATEGORIES: ExportReadinessCategory[] = [
  "CLASSIFICATION",
  "FORMULA",
  "TESTING",
  "LABELING",
  "CLAIMS",
  "ESTABLISHMENT",
  "LISTING_IMPORT",
];

function ReadinessStatusIcon({ status }: { status: ExportReadinessStatus }) {
  if (status === "COMPLIANT") return <Check size={17} weight="bold" className="text-[var(--brand-ink)] shrink-0" />;
  if (status === "REQUIRED_CHANGE" || status === "BLOCKER") return <Warning size={17} weight="bold" className="text-[var(--crit)] shrink-0" />;
  if (status === "VERIFICATION_REQUIRED") return <Question size={17} weight="bold" className="text-[var(--ink-2)] shrink-0" />;
  return <Minus size={17} weight="bold" className="text-[var(--ink-3)] shrink-0" />;
}

function ReadinessItemCard({ item }: { item: ReadinessItem }) {
  const meta = READINESS_STATUS_META[item.status];
  return (
    <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[13px_14px]">
      <div className="flex items-start gap-2.5">
        <ReadinessStatusIcon status={item.status} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2 flex-wrap">
            <h3 className="m-0 text-[13px] font-bold text-[var(--ink)]">{item.title}</h3>
            <span className={`font-mono text-[10.5px] font-bold ${meta.className}`}>{meta.label}</span>
          </div>
          <p className="m-[6px_0_0] text-[12.5px] text-[var(--ink-2)] leading-[1.6]">{item.summary}</p>
          <p className="m-[7px_0_0] text-[12px] text-[var(--ink-3)] leading-[1.55]">
            다음 행동: <span className="text-[var(--ink-2)]">{item.next_action}</span>
          </p>
          {item.evidence.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {item.evidence.map((evidence) => (
                <span key={evidence} className="font-mono text-[10px] text-[var(--ink-3)] border border-[var(--line)] bg-[var(--surface-sub)] px-1.5 py-0.5">
                  {evidence}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileSnapshot({ report }: { report: USExportReadinessReport }) {
  const profile = report.profile_snapshot;
  const rows = [
    ["법인·제조사", profile.manufacturer_name || profile.legal_manufacturer],
    ["제조시설", profile.manufacturing_site],
    ["U.S. Agent", profile.us_agent_name],
    ["수입자", profile.importer_name],
    ["FDA registration", profile.fda_establishment_registration || profile.registration_status],
    ["CGMP", profile.cgmp_ready === true ? "준비됨" : profile.cgmp_ready === false ? "아니오" : "미입력"],
    ["Drug Listing", profile.drug_listing_status || profile.ndc_or_listing_number],
  ];
  return (
    <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[14px_15px]">
      <div className="flex items-center gap-2 mb-3">
        <span className="font-mono text-[10.5px] text-[var(--brand-ink)]">PROFILE SNAPSHOT</span>
        <span className="text-[11px] text-[var(--ink-3)]">이 리포트 생성 당시의 프로필</span>
      </div>
      <div className="grid grid-cols-2 gap-x-5 gap-y-2 max-[650px]:grid-cols-1">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-3 border-b border-dashed border-[var(--line)] pb-1.5 text-[11.5px]">
            <span className="text-[var(--ink-3)]">{label}</span>
            <span className="text-right text-[var(--ink-2)]">{String(value || "미입력")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReadinessReportView({ report }: { report: USExportReadinessReport }) {
  const { summary } = report;
  const statusOrder: ExportReadinessStatus[] = [
    "COMPLIANT",
    "REQUIRED_CHANGE",
    "VERIFICATION_REQUIRED",
    "NOT_ASSESSED",
    "BLOCKER",
  ];
  return (
    <>
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
        <span className="text-[var(--ink-2)]">
          <Link href="/" className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]">홈</Link>{" "}
          <span>›</span> 해외 수출 검증 <span>›</span> 미국 <span>›</span> 리포트
        </span>
      </div>

      <div className="p-[16px_20px] border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="flex items-start gap-4 flex-wrap">
          <div>
            <p className="m-0 font-mono text-[10.5px] text-[var(--brand-ink)]">US EXPORT READINESS</p>
            <h1 className="mt-1 text-[17px] font-bold text-[var(--ink)]">{report.product_name || "미국 수출 준비도"}</h1>
            <p className="m-[5px_0_0] text-[12px] text-[var(--ink-3)]">미국 수출 준비를 위해 필요한 자료와 조치를 정리한 안내입니다.</p>
          </div>
          <div className="ml-auto flex items-center gap-2 border border-[var(--line-2)] bg-[var(--surface-sub)] p-[8px_10px]">
            <ReadinessStatusIcon status={summary.overall_status} />
            <span className={`text-[13px] font-bold ${READINESS_STATUS_META[summary.overall_status].className}`}>
              전체 {READINESS_STATUS_META[summary.overall_status].label}
            </span>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {statusOrder.map((status) => (
            <span key={status} className={`inline-flex items-center gap-1.5 border border-[var(--line-2)] bg-[var(--surface-sub)] px-2 py-1 font-mono text-[10.5px] ${READINESS_STATUS_META[status].className}`}>
              <ReadinessStatusIcon status={status} />
              {READINESS_STATUS_META[status].label} {summary.counts_by_status[status] || 0}
            </span>
          ))}
          <span className="ml-auto self-center font-mono text-[11px] text-[var(--ink-3)]">총 {summary.total}개 항목</span>
        </div>
      </div>

      <div className="p-[18px_20px_24px] flex flex-col gap-3">
        <div className="flex items-center gap-[11px]">
          <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px]">01</span>
          <h2 className="m-0 text-[13px] font-bold text-[var(--ink)]">미국 수출 준비 체크리스트</h2>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
        </div>
        {READINESS_CATEGORIES.map((category) => {
          const items = report.items.filter((item) => item.category === category);
          return (
            <section key={category} className="border border-[var(--line-2)] bg-[var(--surface-sub)] p-[12px]">
              <div className="flex items-center gap-2 mb-2.5">
                <span className="font-mono text-[10px] text-[var(--ink-3)]">{category}</span>
                <h3 className="m-0 text-[13px] font-bold text-[var(--ink)]">{READINESS_CATEGORY_META[category]}</h3>
                <span className="ml-auto font-mono text-[10.5px] text-[var(--ink-3)]">{items.length}개</span>
              </div>
              {items.length > 0 ? (
                <div className="flex flex-col gap-2">{items.map((item) => <ReadinessItemCard key={item.id} item={item} />)}</div>
              ) : (
                <p className="m-0 text-[12px] text-[var(--ink-3)]">이 카테고리의 판정 항목이 없습니다.</p>
              )}
            </section>
          );
        })}
        <ProfileSnapshot report={report} />
      </div>

      <div className="p-[10px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] text-[11px] text-[var(--ink-3)] leading-[1.65]">{report.disclaimer}</div>
      <div className="p-[14px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] flex items-center justify-between flex-wrap gap-3">
        <Link href="/inspect?region=US" className="font-sans text-[13px] font-semibold p-[9px_14px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] transition-colors inline-flex items-center gap-1.5 no-underline">
          <span className="font-mono">←</span> 다시 검사
        </Link>
        <Link href="/mypage" className="font-sans text-[13px] font-semibold p-[9px_14px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] transition-colors no-underline">
          수출 프로필 관리
        </Link>
      </div>
      <PageFooter />
    </>
  );
}

const INPUT_STATE_LABELS: Record<string, string> = { PROVIDED: "자료 있음", NOT_AVAILABLE: "자료 없음", UNKNOWN: "있는지 모름", NOT_ENTERED: "나중에 입력" };

function GenericItemCard({ item }: { item: GenericReadinessItem }) {
  return <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[13px_14px]">
    <div className="flex items-start gap-2.5"><ReadinessStatusIcon status={item.status} /><div className="min-w-0 flex-1"><div className="flex flex-wrap gap-2 items-center"><h3 className="m-0 text-[13px] font-bold text-[var(--ink)]">{item.title}</h3><span className="font-mono text-[10.5px] text-[var(--ink-3)]">{INPUT_STATE_LABELS[item.user_state]}</span></div><p className="m-[6px_0_0] text-[12.5px] text-[var(--ink-2)] leading-[1.6]">{item.summary}</p><p className="m-[7px_0_0] text-[12px] text-[var(--ink-3)]">다음 행동: <span className="text-[var(--ink-2)]">{item.next_action}</span></p><details className="mt-2 text-[11px] text-[var(--ink-3)]"><summary className="cursor-pointer">왜 필요한가 / 어떤 자료인가 / 모르면 어디에 확인하나</summary><p className="m-[5px_0_0] leading-[1.55]">{item.why_it_matters}</p><p className="m-[3px_0_0] leading-[1.55]">자료: {item.what_document}</p><p className="m-[3px_0_0] leading-[1.55]">확인: {item.how_to_find}</p></details></div></div>
  </div>;
}

function GenericReadinessReportView({ report }: { report: ExportReadinessReport }) {
  const priorityIds = new Set(report.priority_actions.map((action) => action.item_id));
  const priorityItems = report.items.filter((item) => priorityIds.has(item.id)).slice(0, 3);
  const laterItems = report.items.filter((item) => !priorityIds.has(item.id) && item.status !== "COMPLIANT");
  const completeItems = report.items.filter((item) => item.status === "COMPLIANT");
  return <><div className="p-[16px_20px] border-b border-[var(--line)] bg-[var(--surface)]"><p className="m-0 font-mono text-[10.5px] text-[var(--brand-ink)]">EXPORT READINESS</p><h1 className="m-[4px_0_0] text-[17px] font-bold text-[var(--ink)]">{report.product_name || "미국 수출 준비도"}</h1><p className="m-[5px_0_0] text-[12px] text-[var(--ink-3)]">수출국: 미국 · 국내 제품 분류: {CATEGORY_OPTIONS_FOR_REPORT[report.domestic_category] || report.domestic_category}</p><p className="m-[5px_0_0] text-[12px] text-[var(--ink-2)]">{report.regulatory_route.label}</p></div><div className="p-[18px_20px_24px] flex flex-col gap-4"><section><h2 className="m-[0_0_10px] text-[14px] font-bold text-[var(--ink)]">지금 할 일</h2>{priorityItems.length ? <div className="flex flex-col gap-2">{priorityItems.map((item) => <GenericItemCard key={item.id} item={item} />)}</div> : <p className="m-0 text-[12px] text-[var(--ink-3)]">입력한 자료를 기준으로 우선 처리할 항목이 없습니다.</p>}</section><section><h2 className="m-[0_0_10px] text-[14px] font-bold text-[var(--ink)]">이후 준비할 일</h2><div className="flex flex-col gap-2">{laterItems.map((item) => <GenericItemCard key={item.id} item={item} />)}</div></section><section><h2 className="m-[0_0_10px] text-[14px] font-bold text-[var(--ink)]">확인 완료</h2>{completeItems.length ? <div className="flex flex-col gap-2">{completeItems.map((item) => <GenericItemCard key={item.id} item={item} />)}</div> : <p className="m-0 text-[12px] text-[var(--ink-3)]">이번 입력에서 확인 완료로 분류된 항목이 없습니다.</p>}</section><details className="border border-[var(--line-2)] bg-[var(--surface-sub)] p-[12px]"><summary className="cursor-pointer text-[12.5px] font-semibold text-[var(--ink)]">전체 체크리스트 보기 ({report.items.length}개)</summary><div className="mt-3 flex flex-col gap-2">{report.items.filter((item) => !priorityIds.has(item.id)).map((item) => <GenericItemCard key={item.id} item={item} />)}</div></details></div><div className="p-[10px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] text-[11px] text-[var(--ink-3)] leading-[1.65]">{report.disclaimer}</div><div className="p-[14px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)]"><Link href="/inspect?region=US" className="text-[13px] font-semibold text-[var(--brand-ink)] underline">다시 준비도 확인하기</Link></div><PageFooter /></>;
}

const CATEGORY_OPTIONS_FOR_REPORT: Record<string, string> = { skincare: "기초 화장품", sun_care: "선케어·자외선 차단", cleansing: "클렌징", makeup: "메이크업", mask_pack: "마스크팩", haircare: "헤어케어", bodycare: "바디케어", fragrance: "향수·향 제품", other: "기타" };

interface USReportClientProps {
  resultId: string;
}

export function USReportClient({ resultId }: USReportClientProps) {
  const [report, setReport] = useState<USPreflightReport | USExportReadinessReport | ExportReadinessReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const readinessRaw = sessionStorage.getItem(`us-readiness-${resultId}`);
    if (readinessRaw) {
      try {
        const storedReport = JSON.parse(readinessRaw) as USExportReadinessReport | ExportReadinessReport;
        window.setTimeout(() => setReport(storedReport), 0);
        return;
      } catch {
        // 파싱 에러 시 서버 조회로 폴백
      }
    }

    const legacyRaw = sessionStorage.getItem(`us-preflight-${resultId}`);
    if (legacyRaw) {
      try {
        const storedReport = JSON.parse(legacyRaw) as USPreflightReport;
        window.setTimeout(() => setReport(storedReport), 0);
        return;
      } catch {
        // 파싱 에러 시 서버 조회로 폴백
      }
    }

    getUSExportReadiness(resultId)
      .then((readiness) => setReport(readiness))
      .catch(() => getReport(resultId).then((envelope) => {
        if (envelope.region !== "US") {
          setError("해당 미국 리포트 데이터를 찾을 수 없습니다.");
          return;
        }
        if ("report_type" in envelope.report) {
          setReport(envelope.report);
        } else if ("findings" in envelope.report && "summary" in envelope.report && "n_findings" in envelope.report.summary) {
          setReport(envelope.report as USPreflightReport);
        } else {
          setError("해당 미국 리포트 데이터를 찾을 수 없습니다.");
        }
      }))
      .catch((err) => {
        console.error(err);
        setError("리포트 데이터를 찾을 수 없습니다. 검사 화면에서 다시 시도해 주세요.");
      });
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

  if ("report_type" in report && report.report_type === "export_readiness") {
    return <GenericReadinessReportView report={report} />;
  }
  if ("report_type" in report) {
    return <ReadinessReportView report={report} />;
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
