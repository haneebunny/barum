"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { Warning, ShieldWarning, Question, ArrowsClockwise, CaretDown, Check } from "@phosphor-icons/react";
import type { USPreflightReport, USPreflightFinding, USPreflightCategory } from "@/lib/api/schema";
import { USPreflightReportSchema } from "@/lib/api/schema";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { getReport, getReportImageUrl } from "@/lib/api/client";
import { ReportImageViewer } from "@/components/ReportImageViewer/ReportImageViewer";
import { TicketCheckoutModal } from "@/components/TicketCheckout/TicketCheckoutModal";
import { useReportAccess, useTickets } from "@/lib/tickets";

const CATEGORY_META: Record<
  USPreflightCategory,
  { label: string; icon: typeof ShieldWarning; isCrit: boolean }
> = {
  "OTC의약품_분류전환": {
    label: "OTC 의약품 분류 전환",
    icon: ArrowsClockwise,
    isCrit: false,
  },
  "미국_미승인_성분": {
    label: "미국 FDA 미승인 성분",
    icon: ShieldWarning,
    isCrit: true,
  },
  "성분정보_확인불가": {
    label: "성분 정보 확인 불가",
    icon: Question,
    isCrit: false,
  },
};

function escapeHtml(s: string) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] || c));
}

// 국내 ReportClient의 markSentence와 같은 방식(span을 원문 문장 안에서 찾아 감싼다).
// 텍스트 입력(이미지 없음)일 때만 쓰인다 - 이미지가 있으면 ReportImageViewer가 대신한다.
function markFindingSpan(finding: USPreflightFinding, num: number) {
  const meta = CATEGORY_META[finding.category];
  const out = escapeHtml(finding.sentence);
  const needle = escapeHtml(finding.span);
  if (out.indexOf(needle) === -1) return out;
  const spanCls = meta.isCrit
    ? "relative px-1 rounded-sm cursor-default border inline border-[var(--crit)] bg-[var(--crit-bg)] font-semibold"
    : "relative px-1 rounded-sm cursor-default border inline border-[var(--line-2)] bg-[var(--surface-sub)]";
  return out.replace(
    needle,
    `<span class="${spanCls}"><span class="absolute top-[-9px] left-[-2px] font-mono text-[9.5px] font-bold color-inherit">${num}</span>${needle}</span>`
  );
}

interface FindingCardProps {
  finding: USPreflightFinding;
  idx: number;
  num: number;
  open: boolean;
  onToggle: () => void;
  onHover: (hover: boolean) => void;
}

// 카드 뼈대·타이포는 국내 리포트와 통일한다(왼쪽 심각도선·pill 번호·아코디언).
// 수용/제외·대체표현·신뢰도 배지·조문 인용은 넣지 않는다 - 미국 프리플라이트
// 데이터(USPreflightFinding)엔 그 근거가 되는 필드 자체가 없다(위반유형·flag·
// evidence_grade·legal_basis 없음, span/sentence/category/explanation/location뿐).
// 없는 데이터를 있는 척 보여주면 오히려 사용자를 오도한다(2026-08-24, 인터뷰로 확정).
function FindingCard({ finding, idx, num, open, onToggle, onHover }: FindingCardProps) {
  const meta = CATEGORY_META[finding.category];
  const accentColor = meta.isCrit ? "var(--crit)" : "var(--ink-3)";
  const Icon = meta.icon;

  return (
    <div
      className="pl-4 pb-4 border-l-[3px] bg-[var(--surface)] dark:bg-transparent"
      style={{ borderLeftColor: accentColor }}
      data-i={idx}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      <div className="cursor-pointer" onClick={onToggle}>
        <div className="flex items-center gap-2.25 flex-wrap pt-3.5">
          <span className="font-mono text-[12px] font-bold text-[var(--ink-3)]">[{num}]</span>
          <Icon size={14} weight="bold" style={{ color: accentColor }} className="shrink-0" />
          <span className="font-extrabold text-[13px] tracking-[0.2px]" style={{ color: accentColor }}>
            {meta.label}
          </span>
          <span
            className={`ml-auto text-[var(--ink-3)] inline-flex items-center transition-transform duration-[200ms] ${open ? "rotate-180" : ""}`}
          >
            <CaretDown size={14} weight="bold" />
          </span>
        </div>

        <div className="mt-2.25">
          <span
            className="font-bold text-[15px] text-[var(--ink)] pb-[3px] border-b-2 inline min-w-0"
            style={{ borderBottomColor: accentColor }}
          >
            &ldquo;{finding.span}&rdquo;
          </span>
        </div>
      </div>

      <div className={`accordion-wrapper ${open ? "open" : ""}`}>
        <div className="accordion-content">
          <div className="pt-3.5 flex flex-col gap-3">
            {finding.sentence && finding.sentence !== finding.span && (
              <p className="text-[12.5px] text-[var(--ink-3)] leading-[1.6] m-0 max-w-[62ch]">
                원문: {finding.sentence}
              </p>
            )}
            <p className="text-[13.5px] text-[var(--ink-2)] leading-[1.7] m-0 font-sans max-w-[62ch]">
              <span className="font-bold text-[var(--ink)]">[근거]</span> {finding.explanation}
            </p>
          </div>
        </div>
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
  const [openIdx, setOpenIdx] = useState<number | null>(0);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [imageErrorGlobal, setImageErrorGlobal] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<USPreflightCategory | null>(null);

  // 해외 프리플라이트는 무료 체험이 없다. 이용권을 쓰기 전엔 요약 건수조차 안 보여준다.
  const { isUnlocked, unlock } = useReportAccess(resultId);
  const { has, consume } = useTickets();
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(`us-preflight-${resultId}`);
      if (raw) {
        const parsed = USPreflightReportSchema.safeParse(JSON.parse(raw));
        if (parsed.success) {
          window.setTimeout(() => setReport(parsed.data), 0);
          return;
        }
        console.warn("임시 저장된 미국 프리플라이트 결과 형식이 올바르지 않아 서버에서 다시 조회합니다.");
        window.sessionStorage.removeItem(`us-preflight-${resultId}`);
      }
    } catch (cacheError) {
      console.warn("임시 저장된 미국 프리플라이트 결과를 읽지 못해 서버에서 다시 조회합니다.", cacheError);
    }

    if (resultId.startsWith("us-local-")) {
      window.setTimeout(
        () => setError("임시 저장된 미국 프리플라이트 결과를 찾을 수 없습니다. 해외 검사를 다시 실행해 주세요."),
        0,
      );
      return;
    }

    getReport(resultId)
      .then((envelope) => {
        if (envelope.region === "US") {
          const parsed = USPreflightReportSchema.safeParse(envelope.report);
          if (parsed.success) {
            setReport(parsed.data);
          } else {
            setError("이 결과는 미국 프리플라이트 형식이 아닙니다. 해외 검사를 다시 실행해 주세요.");
          }
        } else {
          setError("해당 미국 리포트 데이터를 찾을 수 없습니다.");
        }
      })
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

  // 이용권을 쓰기 전엔 리포트 본문을 통째로 막는다(국내와 달리 무료 요약이 없다).
  if (!isUnlocked) {
    const openWithTicket = () => {
      if (!consume("overseas")) {
        setCheckoutOpen(true);
        return;
      }
      unlock("overseas");
    };
    return (
      <>
        <div className="p-[18px_20px] border-b border-[var(--line)] flex items-center gap-4 flex-wrap">
          <h1 className="text-[15px] font-bold text-[var(--ink)] m-0">미국 수출 프리플라이트</h1>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
          <span className="font-mono text-[11.5px] text-[var(--ink-3)]">검사 완료 · 열람 전</span>
        </div>

        <div className="p-[28px_20px]">
          <div className="max-w-[620px] mx-auto border border-[var(--line-2)] bg-[var(--surface-sub)] p-[22px_24px]">
            <p className="m-0 mb-2.5 font-mono text-[11px] font-bold text-[var(--ink-3)] tracking-[0.3px]">[ 이용권 필요 ]</p>
            <h2 className="m-0 mb-2.5 text-[17px] font-extrabold text-[var(--ink)] tracking-[-0.3px] break-keep">
              검사가 끝났습니다. 이용권으로 리포트를 여세요.
            </h2>
            <p className="m-0 mb-4 text-[13px] text-[var(--ink-2)] leading-[1.75] break-keep">
              해외 프리플라이트는 무료 체험이 없습니다. 이용권 1장으로 성분 OTC 분류 판정, 미국 미승인 성분,
              라벨링 이슈와 수정 권고안 전체를 볼 수 있고, 한 번 연 리포트는 기간 제한 없이 남습니다.
            </p>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={openWithTicket}
                className="font-sans text-[13px] font-bold p-[11px_16px] border border-[var(--brand-deep)] dark:border-[var(--brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] text-[var(--on-brand)] cursor-pointer hover:opacity-90 inline-flex items-center justify-center gap-1.5"
              >
                {has("overseas") ? "보유 이용권으로 열기" : "이용권 구매하고 열기"} <span className="font-mono">→</span>
              </button>
              <Link
                href="/inspect?region=US"
                className="font-sans text-[13px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] inline-flex items-center gap-1.5 no-underline"
              >
                <span className="font-mono">←</span> 다시 검사
              </Link>
            </div>
          </div>
        </div>

        <PageFooter />

        <TicketCheckoutModal
          isOpen={checkoutOpen}
          onClose={() => setCheckoutOpen(false)}
          kinds={["overseas"]}
          defaultKind="overseas"
          reason="이 미국 프리플라이트 리포트 전체를 엽니다. 현재 선크림 단일 품목 베타 범위입니다."
          onPurchased={() => {
            if (consume("overseas")) unlock("overseas");
          }}
        />
      </>
    );
  }

  const { findings, summary, disclaimer } = report;

  const findByOrder = findings
    .map((f, idx) => ({ f, idx, num: 0 }))
    .sort((a, b) => a.f.location.order - b.f.location.order)
    .map((o, i) => ({ ...o, num: i + 1 }));

  // 국내 ReportImageViewer가 요구하는 형태로 isCrit만 얹어 그대로 넘긴다
  // (컴포넌트는 flag가 없으면 isCrit을 본다 - 미국·국내 공용화, 2026-08-24).
  const highlightItems = findByOrder.map((o) => ({
    f: { ...o.f, isCrit: CATEGORY_META[o.f.category].isCrit },
    idx: o.idx,
    num: o.num,
  }));

  const visibleFindByOrder = categoryFilter
    ? findByOrder.filter((o) => o.f.category === categoryFilter)
    : findByOrder;

  const imageFinding = findByOrder.find(({ f }) => {
    const location = f.location;
    return Boolean(location.tile)
      && typeof location.y_start === "number"
      && typeof location.y_end === "number"
      && location.y_end > location.y_start
      && typeof location.source_w === "number"
      && location.source_w > 0
      && typeof location.source_h === "number"
      && location.source_h > 0;
  });
  const isImageMode = Boolean(imageFinding);
  const sampleLoc = imageFinding?.f.location;
  const srcW = sampleLoc?.source_w;
  const srcH = sampleLoc?.source_h;
  const hasCoords = typeof srcW === "number" && typeof srcH === "number" && srcW > 0 && srcH > 0;
  const canShowRealImage = hasCoords && !imageErrorGlobal;

  return (
    <>
      {/* 요약 + 필터 바 (국내 리포트 상단바와 같은 뼈대) */}
      <div className="p-[18px_20px] border-b border-[var(--line)]">
        <div className="flex items-center gap-4 flex-wrap mb-3">
          <h1 className="text-[15px] font-bold text-[var(--ink)] m-0">미국 수출 프리플라이트</h1>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
          <div className="flex items-center gap-4 font-mono text-[12px]">
            <span className="text-[var(--ink-3)]">
              검사 문장 <span className="text-[var(--ink-2)] font-bold">{summary.n_sentences}</span>
            </span>
            <span className="text-[var(--ink-3)]">
              지적{" "}
              <span className={`font-bold ${summary.n_findings > 0 ? "text-[var(--crit)]" : "text-[var(--ink-2)]"}`}>
                {summary.n_findings}
              </span>
            </span>
          </div>
        </div>

        {summary.n_findings > 0 && (
          <div className="flex flex-wrap items-center gap-4">
            {(Object.keys(CATEGORY_META) as USPreflightCategory[]).map((cat) => {
              const count = findings.filter((f) => f.category === cat).length;
              if (count === 0) return null;
              const meta = CATEGORY_META[cat];
              const Icon = meta.icon;
              const isActive = categoryFilter === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => setCategoryFilter((prev) => (prev === cat ? null : cat))}
                  className={`inline-flex items-center gap-1.5 px-2 py-1 text-[13px] font-bold border-b-2 cursor-pointer transition-all duration-[120ms] ${
                    isActive
                      ? meta.isCrit
                        ? "border-[var(--crit)] bg-[var(--crit)] text-[var(--on-brand)] dark:text-[var(--canvas)]"
                        : "border-[var(--ink-3)] bg-[var(--ink-3)] text-[var(--on-brand)] dark:text-[var(--canvas)]"
                      : meta.isCrit
                        ? "border-[var(--crit)] bg-transparent text-[var(--crit)] hover:bg-[var(--crit-bg)]"
                        : "border-[var(--ink-3)] bg-transparent text-[var(--ink-2)] hover:bg-[var(--surface-sub)]"
                  }`}
                >
                  {isActive ? <Check size={13} weight="bold" /> : <Icon size={13} weight="bold" />}
                  {meta.label} <span className="font-mono">{count}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {findings.length === 0 ? (
        <div className="text-center p-[40px_20px]">
          <p className="text-[var(--ink-2)] text-[14px] font-semibold mb-1">지적 사항 없음</p>
          <p className="text-[var(--ink-3)] text-[12.5px]">
            입력된 자료에서 미국 자외선차단 규제 관련 이슈가 발견되지 않았습니다.
          </p>
        </div>
      ) : (
        /* 2단 리포트 그리드 (국내와 동일한 뼈대) */
        <div className="grid grid-cols-[0.86fr_1.14fr] max-[900px]:grid-cols-1">
          <div className="p-[18px_20px_22px] border-r border-[var(--line)] max-[900px]:border-r-0 max-[900px]:border-b max-[900px]:border-[var(--line)]">
            <div className="flex items-center gap-[11px] m-[0_0_13px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11.5px] p-[2px_7px] inline-flex items-center">01</span>
              <h2 className="m-0 text-[14px] font-bold text-[var(--ink)] tracking-[-0.2px]">검증 카드</h2>
              <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
              <span className="text-[var(--ink-3)] font-mono text-[11px]">
                {categoryFilter && <span className="font-mono">{visibleFindByOrder.length}/</span>}
                <span className="font-mono">{findByOrder.length}</span>건
              </span>
            </div>
            <div className="flex flex-col gap-3 [&>*+*]:border-t [&>*+*]:border-[var(--line)]">
              {visibleFindByOrder.map((o) => (
                <FindingCard
                  key={o.idx}
                  finding={o.f}
                  idx={o.idx}
                  num={o.num}
                  open={openIdx === o.idx}
                  onToggle={() => setOpenIdx(openIdx === o.idx ? null : o.idx)}
                  onHover={(h) => setHoveredIndex(h ? o.idx : null)}
                />
              ))}
              {categoryFilter && visibleFindByOrder.length === 0 && (
                <div className="flex flex-col items-center gap-2 border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[24px_16px] text-center">
                  <p className="m-0 text-[13px] text-[var(--ink-3)]">해당 유형이 없습니다.</p>
                  <button
                    type="button"
                    onClick={() => setCategoryFilter(null)}
                    className="text-[12px] font-mono text-[var(--brand-ink)] border-b border-[var(--brand-ink)] cursor-pointer bg-transparent"
                  >
                    전체 보기
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="p-[18px_20px_22px]">
            <div className="flex items-center gap-[11px] m-[0_0_13px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11.5px] p-[2px_7px] inline-flex items-center">02</span>
              <h2 className="m-0 text-[14px] font-bold text-[var(--ink)] tracking-[-0.2px]">원문 하이라이트</h2>
              <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
              {isImageMode ? (
                <span className="text-[var(--ink-3)] font-mono text-[11px]">원본 이미지</span>
              ) : (
                <span className="text-[var(--ink-3)] font-mono text-[11px]">텍스트 모드 · 스팬 밑줄</span>
              )}
            </div>
            <div id="origPanel">
              {isImageMode ? (
                <ReportImageViewer
                  findByOrder={highlightItems}
                  imageUrl={canShowRealImage ? getReportImageUrl(resultId) : null}
                  imageErrorGlobal={imageErrorGlobal}
                  onImageError={() => setImageErrorGlobal(true)}
                  hoveredIndex={hoveredIndex}
                  onHoverChange={setHoveredIndex}
                />
              ) : (
                <div
                  className="border border-[var(--line-2)] bg-[var(--surface-sub)] p-[16px_15px] text-[15px] text-[var(--ink)] leading-[2]"
                  dangerouslySetInnerHTML={{
                    __html: findByOrder.map((o) => markFindingSpan(o.f, o.num)).join(" "),
                  }}
                />
              )}
            </div>
          </div>
        </div>
      )}

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
