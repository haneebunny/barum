"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { Warning, MagnifyingGlass, Check, X, CaretDown, CircleNotch, Lock } from "@phosphor-icons/react";
import type { ReportEnvelope, Finding, Replacement } from "@/lib/api/schema";
import { getReport, getRemediation, getReportImageUrl } from "@/lib/api/client";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { useError } from "@/lib/error/ErrorContext";
import { TabSwitch, TabOption } from "@/components/TabSwitch/TabSwitch";

const FIXTURE_OPTIONS: TabOption<"unjudged" | "text" | "image">[] = [
  { value: "image", label: "이미지 예시" },
  { value: "text", label: "텍스트 예시" },
  { value: "unjudged", label: "미판정 포함" },
];

const TIER_OPTIONS: TabOption<"FREE" | "BASIC" | "PRO">[] = [
  { value: "FREE", label: "Free" },
  { value: "BASIC", label: "Basic" },
  { value: "PRO", label: "Pro" },
];

const TYPE_LABEL = {
  "1호_의약품오인": "1호 · 의약품 오인",
  "2호_기능성오인": "2호 · 기능성 오인",
  "5호_거짓과장기만": "5호 · 거짓·과장·기만",
};

// 근거 등급(evidence_grade) → 점 채움 개수·라벨. 색이 아니라 채움 개수(형태)로만
// 구분한다 - 등급이 낮다고 "안전"으로 읽히면 안 된다(팀장 승인, 2026-08-23).
// 표시 라벨은 디디 확정 전 잠정본(2026-08-23) - 바뀌어도 이 테이블만 고치면 된다.
// 라벨은 "신뢰도 상/중/하"로 표시하지만 wire 값(rule_confirmed 등)은 그대로다 -
// 이 테이블만 바뀌면 된다(디디 확정, 2026-08-23).
const EVIDENCE_GRADE_DOTS: Record<string, { dots: number; label: string }> = {
  rule_confirmed: { dots: 3, label: "신뢰도 상" },
  citation_verified: { dots: 2, label: "신뢰도 중" },
  unverified: { dots: 1, label: "신뢰도 하" },
};

function EvidenceGradeBadge({ grade }: { grade: string | null | undefined }) {
  const entry = grade ? EVIDENCE_GRADE_DOTS[grade] : undefined;
  if (!entry) return null;
  return (
    <span className="inline-flex items-center gap-1 shrink-0 text-[10.5px] text-[var(--ink-3)] font-medium leading-none">
      {/* 점은 장식(●●●가 "확정된 위반"처럼 심각도로 오독될 수 있어 라벨 텍스트를
          항상 같이 보여준다 - 디디 최종안, 2026-08-23) */}
      <span className="font-mono tracking-[1px]" aria-hidden="true">
        {"●".repeat(entry.dots)}
        {"○".repeat(3 - entry.dots)}
      </span>
      {entry.label}
    </span>
  );
}

interface FindingCardProps {
  finding: Finding; // 그룹 대표(첫 항목). span+violation_type이 같으면 근거·설명도 같다(결정론적 규칙 매칭)
  index: number; // 대표 idx
  // 이 카드가 묶고 있는 모든 occurrence의 원본 idx(원문 하이라이트와 짝짓는 키).
  // 길이 1이면 그룹핑 안 된 단독 지적.
  positionIdxs: number[];
  orderIndex: number;
  num: number;
  act: "accept" | "exclude" | null;
  // 그룹 전체에 한 번에 적용된다(팀장 판단: 컴플라이언스 도구에서 부분 수용은 이상하다).
  onAction: (idxs: number[], orderIndex: number, act: "accept" | "exclude") => void;
  isHovered: boolean;
  onHover: (hover: boolean) => void;
  open: boolean;
  onToggle: () => void;
  onScrollToPosition: (idx: number) => void;
  tier: "FREE" | "BASIC" | "PRO";
  remediationCount: number;
  onFetchRemediation: () => void;
  // 판정할 때 배치로 만들어져 리포트에 실려온 대체표현(PR #265). 있으면 그대로 쓰고
  // 새로 호출하지 않는다. hasReportReplacements가 false일 때만(옛 리포트·생성 실패)
  // /remediate 실시간 조회로 폴백한다.
  replacement: Replacement | undefined;
  hasReportReplacements: boolean;
}

function getRemediationText(violationType: string, suggestionsNode: React.ReactNode) {
  if (violationType === "1호_의약품오인") {
    return (
      <>
        의학적 효능 표현 대신 {suggestionsNode} 과 같은 화장품 범주 보습 및 케어 표현으로 다듬어 보세요.
      </>
    );
  }
  if (violationType === "2호_기능성오인") {
    return (
      <>
        기능성 오인 표현 대신 {suggestionsNode} 과 같은 안전하고 허용된 기능성 표현으로 다듬어 보세요.
      </>
    );
  }
  return (
    <>
      위반 우려가 있는 표현 대신 {suggestionsNode} 과 같은 권장 표현으로 다듬어 보세요.
    </>
  );
}

function FindingCard({
  finding,
  index,
  positionIdxs,
  orderIndex,
  num,
  act,
  onAction,
  isHovered,
  onHover,
  open,
  onToggle,
  onScrollToPosition,
  tier,
  remediationCount,
  onFetchRemediation,
  replacement,
  hasReportReplacements,
}: FindingCardProps) {
  const { showError } = useError();
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [hasFetched, setHasFetched] = useState(false);
  const [showSuggestionsArea, setShowSuggestionsArea] = useState(false);

  useEffect(() => {
    setSuggestions([]);
    setLoading(false);
    setHasFetched(false);

    if (tier === "FREE") {
      setShowSuggestionsArea(false);
      return;
    }

    if (hasReportReplacements) {
      // 판정할 때 배치로 이미 만들어져 리포트에 실려왔다(PR #265). 호출 0회.
      // replacement가 없으면 이 finding엔 제안할 수 없었다는 뜻(제안 불가 시
      // 제안하지 않는다, 2026-08-20 팀장 지시) - 재조회 대상이 아니다.
      setShowSuggestionsArea(true);
      setSuggestions(replacement ? [replacement.replaced] : []);
      setHasFetched(true);
      onFetchRemediation();
      return;
    }

    // 폴백: 이 필드가 생기기 전에 저장된 옛 리포트이거나 생성 자체가 실패한 경우만
    // 기존처럼 /remediate를 실시간으로 부른다.
    setShowSuggestionsArea(true);
    setLoading(true);
    getRemediation({
      sentence: finding.sentence,
      violation_type: finding.violation_type,
      span: finding.span,
    })
      .then((res) => {
        setSuggestions(res.suggestions);
        setHasFetched(true);
        setLoading(false);
        onFetchRemediation();
      })
      .catch((err) => {
        console.error("Failed to fetch remediation suggestion", err);
        showError("대체 제안 오류", "대체 표현 제안을 불러오지 못했습니다: " + (err instanceof Error ? err.message : String(err)));
        setLoading(false);
      });
  }, [finding, tier, hasReportReplacements, replacement]);

  const handleFetchSuggestions = () => {
    setLoading(true);
    getRemediation({
      sentence: finding.sentence,
      violation_type: finding.violation_type,
      span: finding.span,
    })
      .then((res) => {
        setSuggestions(res.suggestions);
        setHasFetched(true);
        setLoading(false);
        onFetchRemediation();
      })
      .catch((err) => {
        console.error("Failed to fetch remediation suggestion", err);
        showError("대체 제안 오류", "대체 표현 제안을 불러오지 못했습니다: " + (err instanceof Error ? err.message : String(err)));
        setLoading(false);
      });
  };

  const handleShowAndFetchSuggestions = () => {
    setShowSuggestionsArea(true);
    if (hasReportReplacements) {
      setSuggestions(replacement ? [replacement.replaced] : []);
      setHasFetched(true);
      onFetchRemediation();
      return;
    }
    handleFetchSuggestions();
  };

  const cls = finding.flag === "위반" ? "violation" : "review";
  const isExcluded = act === "exclude";

  // 호버 translate 제거 및 피그마 디자인 규격 적용 (rounded, overflow, flex-col)
  const cardCls = `border border-[var(--line-2)] bg-[var(--surface)] transition-all duration-[120ms] rounded-[4px] overflow-hidden flex flex-col ${cls === "violation" ? "border-l-[3px] border-l-[var(--crit)]" : "border-l-[3px] border-l-[var(--ink-3)]"
    } ${isExcluded ? "opacity-50" : ""}`;

  // 밑줄 스타일(테두리·배경 박스 아님) - 목업 원안 복원(design/mockups/barum-report.html
  // .fcard.violation/.review .fsent .fspan, 팀장 지시로 언젠가 테두리+배경 칩으로
  // 바뀌어 있었다). 박스 개수를 줄이려는 목적도 있다(디디 확정, 2026-08-23).
  const spanStyle = `font-bold border-b-2 ${cls === "violation" ? "text-[var(--crit)] border-b-[var(--crit)]" : "text-[var(--ink)] border-b-[var(--ink-3)]"
    }`;

  const handleHeaderClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button")) {
      return;
    }
    onToggle();
  };

  return (
    <div
      className={cardCls}
      data-i={index}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      {/* 토글 고정 헤더 (상시 노출) */}
      <div
        className="cursor-pointer border-b border-[var(--line)] bg-[var(--surface-sub)] p-[8px_12px_8px]"
        onClick={handleHeaderClick}
      >
        <div className="flex gap-2.5">
          {/* 컨텍스트 콘텐츠 영역 (1행: 문구와 액션 / 2행: 유형 정보) */}
          <div className="flex-1 min-w-0">
            {/* 1행: [번호+flag] pill + 표현(밑줄) + 수용/제외 버튼(유료 한정) 또는
                유료 안내 + chevron. pill과 표현은 간격 없이 붙여서 시각적으로
                하나처럼 읽히게 한다(디디 확정, 2026-08-23) - 실제 테두리 박스는
                pill 하나뿐이라(표현은 밑줄만) #295가 고친 "짧은 제목도 억지로
                늘어나는" 문제가 재현되지 않는다.
                버튼 묶음은 shrink-0으로 항상 제 폭을 지키고(#292), 표현 span은
                min-w-0만 줘서 평소엔 내용 크기대로, 공간이 부족할 때만 줄어들며
                줄바꿈된다(flex-1은 안 씀, #295). */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 min-w-0">
                {/* [번호 flag] pill. 채움 아니고 테두리만(§F, 일괄/개별 상태색 원칙) */}
                <span className={`shrink-0 inline-flex items-center gap-1 px-1.5 h-[22px] font-mono text-[11px] font-bold border rounded-sm ${cls === "violation" ? "text-[var(--crit)] border-[var(--crit)]" : "text-[var(--ink-3)] border-[var(--ink-3)]"
                  }`}>
                  {num} {cls === "violation" ? "위반" : "검토필요"}
                </span>
                <span className={`${spanStyle} min-w-0 ${isExcluded ? "line-through opacity-50" : ""}`}>
                  {finding.span}
                  {positionIdxs.length > 1 && (
                    <span className="ml-1 font-mono font-normal text-[10.5px] opacity-75">({positionIdxs.length}곳)</span>
                  )}
                </span>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {tier === "FREE" ? (
                  // 박스 줄이기(디디 확정, 2026-08-23) - 테두리 빼고 텍스트+자물쇠만
                  <span className="inline-flex items-center gap-1 text-[10.5px] font-bold text-[var(--ink-3)] whitespace-nowrap">
                    <Lock size={11} weight="bold" />
                    유료 요금제 전용
                  </span>
                ) : (
                  <>
                    <button
                      // 수용=채움, 제외=윤곽선으로 위계를 준다(새 심각도 색 없이, 팀장 지시).
                      // 라이트는 --brand 배경이 대비 미달(3.39:1)이라 --brand-deep(9.36:1) 사용,
                      // 다크는 --brand 그대로 통과(6.48:1) - 디디 검증 완료(DESIGN.md §4.1, PR #268)
                      className={`font-sans text-[11.5px] p-[4px_9px] border rounded-sm cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shrink-0 transition-all duration-[120ms] ${act === "accept"
                        ? "font-bold text-[var(--on-brand)] border-[var(--brand-deep)] bg-[var(--brand-deep)] dark:border-[var(--brand)] dark:bg-[var(--brand)]"
                        : "font-semibold text-[var(--ink-3)] border-[var(--line-2)] bg-transparent hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                        }`}
                      onClick={() => onAction(positionIdxs, orderIndex, "accept")}
                    >
                      <Check size={11} weight="bold" />
                      수용
                    </button>
                    <button
                      className={`font-sans text-[11.5px] p-[4px_9px] border rounded-sm cursor-pointer inline-flex items-center gap-1 whitespace-nowrap shrink-0 transition-all duration-[120ms] ${act === "exclude"
                        ? "font-bold text-[var(--ink)] border-[var(--ink-3)] bg-[var(--surface-sub)]"
                        : "font-semibold text-[var(--ink-3)] border-[var(--line-2)] bg-transparent hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                        }`}
                      onClick={() => onAction(positionIdxs, orderIndex, "exclude")}
                    >
                      <X size={11} weight="bold" />
                      제외
                    </button>
                  </>
                )}
                {/* 토글 chevron */}
                <span
                  className={`text-[var(--ink-3)] inline-flex items-center transition-transform duration-[200ms] ${open ? "rotate-180" : ""
                    }`}
                >
                  <CaretDown size={14} weight="bold" />
                </span>
              </div>
            </div>

            {/* 2행: 위반/검토필요 유형 + 근거 등급(점 채움). 근거 등급은 flag(위반/검토필요)와
                다른 축이라 ftype 바로 옆에 붙인다(디디 안, 2026-08-23) - "검토필요 +
                규칙문서 확정"처럼 flag는 낮아도 등급은 최고인 조합이 나올 수 있는데,
                이 배치는 그걸 모순으로 안 보이게 한다(규칙문서에 실려 있다는 사실 자체는
                확실하고, 다만 실증자료 유무로 위반/검토필요가 갈릴 뿐이라는 뜻). */}
            <div className="flex items-center gap-2 mt-1.5">
              <span className="text-[11.5px] text-[var(--ink-3)] font-medium leading-none">
                {cls === "violation" ? "위반 유형" : "검토 필요 유형"} {TYPE_LABEL[finding.violation_type as keyof typeof TYPE_LABEL] || finding.violation_type}
              </span>
              <EvidenceGradeBadge grade={finding.evidence_grade} />
            </div>
          </div>
        </div>
      </div>

      {/* 아코디언 바디 wrapper */}
      <div className={`accordion-wrapper ${open ? "open" : ""}`}>
        <div className="accordion-content">
          {/* 라이트는 --surface(흰색)가 더 밝지만, 다크는 순서가 반대다
              (canvas < surface < surface-sub) - 다크에서 --surface-sub를 써야
              "펼치면 더 밝게 튀어 보이는" 의도가 다크에서도 유지된다(디디 실측치,
              PM 8대 루루 지시 2026-08-22). */}
          <div className="p-[13px_14px_14px] border-t border-[var(--line)] bg-[var(--surface)] dark:bg-[var(--surface-sub)] flex flex-col gap-3.5">

            {/* 그룹으로 묶인 카드일 때만: 발견 위치별로 원문 하이라이트로 바로 이동 */}
            {positionIdxs.length > 1 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11.5px] text-[var(--ink-3)] font-semibold">발견 위치</span>
                {positionIdxs.map((pidx, i) => (
                  <button
                    key={pidx}
                    type="button"
                    onClick={() => onScrollToPosition(pidx)}
                    className="font-mono text-[11px] px-1.5 py-0.5 border border-[var(--line-2)] rounded-sm bg-[var(--surface-sub)] text-[var(--ink-2)] hover:bg-[var(--nav-hover)] hover:border-[var(--ink-3)] cursor-pointer"
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            )}

            {/* Pro 기능: 대체 표현 제안 보기 버튼을 수용 / 제외 아래(바디 최상단)로 배치 */}
            {(tier !== "FREE" || num === 1) ? (
              !showSuggestionsArea && (
                <div className="flex justify-end">
                  <button
                    onClick={handleShowAndFetchSuggestions}
                    className="font-sans text-[12px] font-bold p-[6px_14px] border border-[var(--brand)] bg-[var(--brand)] text-[var(--on-brand)] hover:bg-[var(--brand-deep)] cursor-pointer inline-flex items-center gap-1.5 transition-all duration-[120ms] rounded-sm shadow-sm"
                  >
                    대체 표현 제안 보기 {tier === "FREE" ? "(체험 1회)" : ""}
                  </button>
                </div>
              )
            ) : (
              // 유료 페이월: 안내문 여러 줄을 겹쳐 쌓는 대신, 실제 제안 영역을 블러
              // 처리해 "가려진 콘텐츠가 있다"는 걸 한 번에 보여준다(PM 지시 2026-08-22).
              <div className="relative border border-dashed border-[var(--line-2)] bg-[var(--surface)] p-[12px_14px] rounded-sm overflow-hidden">
                <div
                  className="text-[14px] text-[var(--ink-2)] leading-1.6 blur-[4px] select-none"
                  aria-hidden="true"
                >
                  {getRemediationText(
                    finding.violation_type,
                    <span className="font-bold text-[var(--on-brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] px-1.5 py-0.5 rounded-[3px] mx-1">
                      안전한 대체 표현
                    </span>
                  )}
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="flex items-center gap-1.5 bg-[var(--surface)] border border-[var(--line-2)] rounded-full px-3 py-1 shadow-sm">
                    <Lock size={12} weight="bold" className="text-[var(--ink-3)]" />
                    <span className="text-[11.5px] font-bold text-[var(--ink-3)]">유료 요금제 전용</span>
                  </div>
                </div>
              </div>
            )}

            {/* 순서: [근거] 설명을 조문보다 먼저 - "어디가 왜 위반인지"를 먼저 보여주고
                법령 원문은 뒤로 미룬다(디디 확정, 2026-08-23). */}
            <p className="text-[13px] text-[var(--ink-2)] leading-1.6 m-0 font-sans">
              {/* 규칙 경로·VLM 경로 모두 표시 형식을 통일한다(백엔드가 explanation을
                  LLM 문장으로 바꿔도 화면은 그대로 받아 쓴다, PM 지시 2026-08-22) */}
              <span className="font-bold text-[var(--ink)]">[근거]</span> {finding.explanation}
            </p>

            {/* 조문 원문 인용. 사방 테두리 박스 대신 왼쪽 세로선만(박스 줄이기,
                디디 확정, 2026-08-23) - <blockquote> 태그 자체가 인용 느낌을
                주므로 배경·전체 테두리 없이도 구분된다. */}
            {(finding.legal_basis || finding.legal_basis_text) && (
              <blockquote className="m-0 border-l-2 border-[var(--line-2)] pl-3">
                {tier === "FREE" && num > 1 ? (
                  <span className="text-[12.5px] text-[var(--ink-3)] font-semibold block py-1">🔒 유료 요금제 전용 (Basic 이상 공개)</span>
                ) : (
                  <>
                    {finding.legal_basis && (
                      <div className="font-mono text-[11.5px] text-[var(--brand-ink)] font-semibold mb-1">
                        {finding.legal_basis}
                      </div>
                    )}
                    {finding.legal_basis_text && (
                      <div className="text-[12.5px] text-[var(--ink-2)] leading-[1.7] break-keep">
                        {finding.legal_basis_text}
                      </div>
                    )}
                  </>
                )}
              </blockquote>
            )}

            {/* 대체 표현 제안 영역: 초록색 버튼 클릭 시 나타나며 로딩 진행 (유료 및 FREE 1번째 카드 한정) */}
            {(tier !== "FREE" || num === 1) && showSuggestionsArea && (
              <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface)] p-[12px_14px] rounded-sm transition-all duration-300">
                <div className="flex items-center gap-1.75 mb-2">
                  <b className="text-[12px] text-[var(--ink-2)] font-bold">대체 표현 제안</b>
                  {tier === "FREE" && (
                    <span className="font-mono text-[10px] text-[var(--ink-3)] border border-[var(--line-2)] p-[1px_6px] ml-2">
                      FREE 요금제 체험 (1/1)
                    </span>
                  )}
                </div>
                <div className="text-[14px] text-[var(--ink-2)] leading-1.6">
                  {loading ? (
                    <div className="flex items-center gap-2 text-[var(--ink-3)] font-mono text-[12.5px]">
                      <CircleNotch size={14} className="animate-spin text-[var(--brand-ink)]" />
                      대체 표현 제안을 불러오는 중...
                    </div>
                  ) : hasFetched ? (
                    suggestions.length > 0 ? (
                      <>
                        {/* 옅은 연두(--nav-active-bg)+그린 텍스트(--brand-ink) 조합이 가독성
                            지적을 받아, 수용 버튼과 같은 채움 조합(--brand-deep/--brand +
                            --on-brand, 디디 검증 9.36:1 라이트/6.48:1 다크)으로 교체했다. */}
                        {getRemediationText(
                          finding.violation_type,
                          <span className="font-bold text-[var(--on-brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] px-1.5 py-0.5 rounded-[3px] mx-1">
                            {suggestions.join(", ")}
                          </span>
                        )}
                        {replacement?.note && (
                          <div className="mt-2 text-[12px] text-[var(--ink-3)] border-t border-dashed border-[var(--line-2)] pt-2">
                            ⓘ {replacement.note}
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="text-[var(--ink-3)]">대체 표현 없음</span>
                    )
                  ) : null}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}

import type { CheckReport } from "@/lib/api/schema";

interface ReportClientProps {
  envelope: Omit<ReportEnvelope, "report"> & { report: CheckReport };
}

function escapeHtml(s: string) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] || c));
}

function markSentence(
  sentence: string,
  hlItems: Array<{ span: string; cls: string; badge: number; idx: number }>,
  actions: Record<number, "accept" | "exclude" | "hold" | null>
) {
  let out = escapeHtml(sentence);
  const items = [...hlItems].sort((a, b) => b.span.length - a.span.length);
  items.forEach((it) => {
    const needle = escapeHtml(it.span);
    if (out.indexOf(needle) === -1) return;
    const isExcluded = actions[it.idx] === "exclude";
    const isViolation = it.cls === "violation";

    let spanCls = "relative px-1 rounded-sm cursor-default border inline ";
    if (isExcluded) {
      spanCls += "opacity-50 line-through ";
    }
    if (isViolation) {
      spanCls += "border-[var(--crit)] bg-[var(--crit-bg)] font-semibold";
    } else {
      spanCls += "border-[var(--line-2)] bg-[var(--surface-sub)]";
    }

    out = out.replace(
      needle,
      `<span class="${spanCls}"><span class="absolute top-[-9px] left-[-2px] font-mono text-[9.5px] font-bold color-inherit">${it.badge}</span>${needle}</span>`
    );
  });
  return out;
}

export function ReportClient({ envelope }: ReportClientProps) {
  const { showError } = useError();
  const [activeEnvelope, setActiveEnvelope] = useState<Omit<ReportEnvelope, "report"> & { report: CheckReport }>(envelope);
  const [activeFixture, setActiveFixture] = useState<"image" | "text" | "unjudged">(() => {
    if (envelope.result_id === "demo-text-id" || envelope.result_id === "text" || envelope.result_id === "demo-id-2") return "text";
    if (envelope.result_id === "demo-unjudged-id" || envelope.result_id === "unjudged" || envelope.result_id === "a3Fk9mdemo") return "unjudged";
    return "image";
  });
  const [loading, setLoading] = useState(false);
  const [actions, setActions] = useState<Record<number, "accept" | "exclude" | null>>({});
  // "모두 수용" 실행취소용 스냅샷. 개별 조작이나 리포트 전환이 끼어들면 되돌릴
  // 대상이 불분명해지므로 null로 비운다(팀장 지시 - 17건 일괄 변경은 실수하면
  // 아파서 되돌리기가 있어야 한다, 2026-08-23).
  const [bulkUndoSnapshot, setBulkUndoSnapshot] = useState<Record<number, "accept" | "exclude" | null> | null>(null);
  const [imageErrors, setImageErrors] = useState<Record<string, boolean>>({});
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [tier, setTier] = useState<"FREE" | "BASIC" | "PRO">("FREE");
  const [remediationCount, setRemediationCount] = useState<number>(0);
  const [openOrderIndex, setOpenOrderIndex] = useState<number | null>(0);
  const [flagFilter, setFlagFilter] = useState<"위반" | "검토필요" | null>(null);

  const d = activeEnvelope.report;

  // 판정 로직 중복 제거(화면 워크어라운드, 근본 원인은 발표 후 과제 - PM 8대
  // 루루 지시 2026-08-22). 같은 문장이 규칙 경로(span=문구 일부)와 VLM 경로
  // (span=문장 전체)에서 둘 다 finding으로 나오면 sentence+violation_type이
  // 같은 두 finding이 생긴다. 이건 1번의 span 그룹핑(§ 아래)으로는 안 걸린다
  // (span 값 자체가 다르다) - 별도 단계로 먼저 걸러야 한다. 규칙 경로 쪽 span이
  // 더 좁고 구체적이라 사용자에게 더 유용하므로 그쪽을 남긴다(span이 sentence
  // 전체와 다르면 규칙 경로로 본다). 이 중복은 같은 지적을 두 번 센 것이므로
  // (1번과 달리) 상단 요약 건수에서도 함께 뺀다.
  const sentenceDedupBestIdx = new Map<string, number>();
  d.findings.forEach((f, i) => {
    const key = `${f.sentence}\0${f.violation_type}`;
    const currentIdx = sentenceDedupBestIdx.get(key);
    if (currentIdx === undefined) {
      sentenceDedupBestIdx.set(key, i);
      return;
    }
    const current = d.findings[currentIdx];
    const currentIsWholeSentence = current.span === current.sentence;
    const candidateIsWholeSentence = f.span === f.sentence;
    if (currentIsWholeSentence && !candidateIsWholeSentence) {
      sentenceDedupBestIdx.set(key, i); // 후보가 규칙 경로(좁은 span)로 보임 - 교체
    }
  });
  const visibleFindingIdx = new Set(sentenceDedupBestIdx.values());

  const findByOrder = d.findings
    .map((f, i) => ({ f, idx: i, num: 0 }))
    .filter((o) => visibleFindingIdx.has(o.idx))
    .sort((a, b) => a.f.location.order - b.f.location.order);

  // finding_index로 지적 카드와 짝짓는다(PR #265). original은 경로마다(조건표=단어,
  // LLM=문장) 값이 달라 키가 못 된다. 아래 그룹 키가 이 값을 써야 해서 그룹핑보다
  // 앞으로 옮겼다(PR #269 이후 버그 수정, 상세는 바로 아래 그룹핑 주석).
  const hasReportReplacements = d.replacements.length > 0;
  const replacementByFindingIndex = new Map<number, (typeof d.replacements)[number]>();
  d.replacements.forEach((r) => {
    if (typeof r.finding_index === "number") {
      replacementByFindingIndex.set(r.finding_index, r);
    }
  });

  // 지적 카드 그룹핑(팀장 확정 A안): span+violation_type이 같으면 카드 하나로
  // 묶는다. **대체표현 유무도 키에 포함한다** - PR #269로 근거 문구가 고정
  // 템플릿이 아니라 LLM이 문장마다 생성하는 값이 되면서 "같은 span+유형이면
  // 설명도 항상 같다"는 가정이 깨졌다. 특히 상품명에서 잡힌 occurrence는 "고유
  // 명사라 대체 제안을 안 한다"는 설명인데, 대표(첫 항목)가 하필 이 경우면 본문
  // occurrence까지 대체표현이 통째로 안 보이게 된다(실사례: "재생" 4곳 중 상품명
  // 1곳이 대표가 돼 나머지 3곳 대체표현이 묻힘). 대체표현 유무로 한 번 더 가르면
  // 상품명 occurrence와 본문 occurrence가 서로 다른 카드로 갈려 각자 맞는 설명을
  // 보여준다("대체표현 있는 쪽을 대표로" 하는 안은 기각 - 그러면 상품명 카드가
  // 자기한테 안 맞는 본문용 설명 밑에 깔린다). 원문 하이라이트(원본 idx 기준)는
  // 그대로 두고, 카드 번호만 그룹 단위로 매긴다 - 아래서 findByOrder의 num을 그룹
  // 번호로 되쓰면 원문 하이라이트 배지도 자동으로 같은 그룹은 같은 번호를 쓰게 된다.
  const groupItemsByKey = new Map<string, number[]>();
  findByOrder.forEach((o) => {
    const key = `${o.f.span}\0${o.f.violation_type}\0${replacementByFindingIndex.has(o.idx)}`;
    if (!groupItemsByKey.has(key)) groupItemsByKey.set(key, []);
    groupItemsByKey.get(key)!.push(o.idx);
  });
  const findGroups = Array.from(groupItemsByKey.values()).map((positionIdxs, i) => ({
    key: String(i),
    positionIdxs,
    repIdx: positionIdxs[0],
    representative: d.findings[positionIdxs[0]],
    num: i + 1,
  }));
  const groupNumByIdx = new Map<number, number>();
  findGroups.forEach((g) => {
    g.positionIdxs.forEach((idx) => groupNumByIdx.set(idx, g.num));
  });
  findByOrder.forEach((item) => {
    item.num = groupNumByIdx.get(item.idx) ?? 0;
  });

  // 카드 패널은 그룹 단위로 그린다. 상단 요약(위반/검토필요 건수)은 그룹핑과
  // 무관하게 원본 finding 개수 그대로 쓴다(표시만 묶고 실제 발견 건수를 줄여
  // 보이면 안 된다, 팀장 지시) - nViol/nReview는 아래에서 d.findings 기준으로 계산.
  const visibleFindGroups = flagFilter
    ? findGroups.filter((g) => g.representative.flag === flagFilter)
    : findGroups;

  useEffect(() => {
    setRemediationCount(0);
    setOpenOrderIndex(0);
    setFlagFilter(null);
    setBulkUndoSnapshot(null);
  }, [activeEnvelope]);

  // 필터가 걸려 있으면 "보이는 것만"이 대상이다(팀장 판단 필요 지점 - 안 보이는
  // 것까지 바뀌면 화면과 실제 상태가 어긋나 더 놀랍다). 이미 제외(exclude)한
  // 항목은 명시적 결정이라 존중해서 안 건드리고, 이미 수용한 항목은 대상에서
  // 빼서 버튼의 "N건" 표시가 "실제로 바뀔 건수"를 그대로 보여주게 한다.
  const acceptAllTargets = visibleFindGroups
    .flatMap((g) => g.positionIdxs)
    .filter((idx) => actions[idx] !== "exclude" && actions[idx] !== "accept");

  const handleAcceptAllVisible = () => {
    if (acceptAllTargets.length === 0) return;
    setBulkUndoSnapshot({ ...actions });
    setActions((prev) => {
      const next = { ...prev };
      acceptAllTargets.forEach((idx) => {
        next[idx] = "accept";
      });
      return next;
    });
  };

  const handleUndoBulkAccept = () => {
    if (!bulkUndoSnapshot) return;
    setActions(bulkUndoSnapshot);
    setBulkUndoSnapshot(null);
  };

  const scrollToBox = (idx: number, isUj = false) => {
    const id = isUj ? `highlight-box-uj-${idx}` : `highlight-box-${idx}`;
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  };

  // 그룹 전체에 한 번에 적용된다(팀장 판단: 컴플라이언스 도구에서 부분 수용은
  // 이상하다). idxs[0]을 대표값으로 토글 여부를 판단한다 - 그룹은 항상 이
  // 함수를 통해서만 값이 바뀌므로 idxs 전체가 항상 같은 값을 유지한다.
  const handleAction = (idxs: number[], orderIndex: number, act: "accept" | "exclude") => {
    setBulkUndoSnapshot(null); // 개별 조작이 끼면 일괄 되돌리기 대상이 불분명해진다
    setActions((prev) => {
      const next = { ...prev };
      if (next[idxs[0]] === act) {
        idxs.forEach((idx) => {
          next[idx] = null;
        });
      } else {
        idxs.forEach((idx) => {
          next[idx] = act;
        });

        const nextOrderIndex = orderIndex + 1;
        if (nextOrderIndex < findGroups.length) {
          setOpenOrderIndex(nextOrderIndex);
          const nextGroup = findGroups[nextOrderIndex];
          setTimeout(() => {
            scrollToBox(nextGroup.repIdx, false);
          }, 220);
        }
      }
      return next;
    });
  };

  const handleFixtureChange = async (key: "image" | "text" | "unjudged") => {
    setLoading(true);
    try {
      const data = await getReport(key);
      setActiveEnvelope(data as any);
      setActiveFixture(key);
      setActions({});
      setBulkUndoSnapshot(null);
    } catch (err) {
      console.error(err);
      showError("리포트 조회 오류", "리포트를 불러오지 못했습니다: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  let nViol = 0;
  let nReview = 0;

  d.findings.forEach((f, i) => {
    if (!visibleFindingIdx.has(i)) return; // sentence 중복 제거된 finding은 건수에서도 뺀다
    if (actions[i] === "exclude") return;
    if (f.flag === "위반") {
      nViol++;
    } else {
      nReview++;
    }
  });

  const isImageMode = findByOrder.some((o) => o.f.location.tile) || d.unjudged.some((u) => u.location.tile);

  const ujByOrder = [...d.unjudged].sort((a, b) => a.location.order - b.location.order);

  const hasInteracted = Object.keys(actions).length > 0;
  const acceptedIndices = hasInteracted
    ? Object.entries(actions)
      .filter(([_, act]) => act === "accept")
      .map(([i]) => i)
      .join(",")
    : d.findings
      .map((f, i) => (visibleFindingIdx.has(i) && f.flag === "위반" ? i : -1))
      .filter((idx) => idx !== -1)
      .join(",");

  return (
    <>
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface)] font-mono text-[11.5px] text-[var(--ink-3)] flex-wrap">
        <div className="ml-auto flex items-center gap-4 max-[900px]:ml-0 max-[900px]:w-full flex-wrap">
          <TabSwitch
            label="목업 전용 · 실제 화면엔 없음:"
            options={FIXTURE_OPTIONS}
            value={activeFixture}
            onChange={handleFixtureChange}
            disabled={loading}
          />
          <TabSwitch
            label="티어 미리보기"
            options={TIER_OPTIONS}
            value={tier}
            onChange={setTier}
          />
        </div>
      </div>

      {/* 요약 상단바 */}
      <div className="p-[18px_20px] border-b border-[var(--line)]">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <button
            type="button"
            aria-pressed={flagFilter === "위반"}
            onClick={() => setFlagFilter((prev) => (prev === "위반" ? null : "위반"))}
            // 선택 시 채움으로 바꾼다(디디 확정, 2026-08-23) - 전엔 outline 링 하나만
            // 더해서 nViol>0일 때 이미 색이 있는 칩과 선택 상태가 거의 구별 안 됐다.
            // 다크모드 --crit(#ff5252)는 밝은 색이라 밝은 글자(--on-brand)를 얹으면
            // 대비가 2.86:1로 기준 미달 - 어두운 --canvas(#101612)를 얹어야
            // 5.74:1로 통과한다(직접 계산, 기존 토큰만 재사용·새 색 없음).
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[14px] font-bold border rounded-[3px] cursor-pointer transition-all duration-[120ms] ${flagFilter === "위반"
              ? "border-[var(--crit)] bg-[var(--crit)] text-[var(--on-brand)] dark:text-[var(--canvas)]"
              : nViol > 0
                ? "border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)]"
                : "border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)]"
              }`}
          >
            <Warning size={14} weight="bold" />
            위반 <span className="font-mono">{nViol}</span> 건
          </button>
          <button
            type="button"
            aria-pressed={flagFilter === "검토필요"}
            onClick={() => setFlagFilter((prev) => (prev === "검토필요" ? null : "검토필요"))}
            // 검토필요 칩도 위반과 같은 방식 - 다크모드 --ink-3(#8aa294)도 밝은
            // 색이라 --canvas를 얹어야 6.70:1로 통과한다(직접 계산).
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[14px] font-bold border rounded-[3px] cursor-pointer transition-all duration-[120ms] ${flagFilter === "검토필요"
              ? "border-[var(--ink-3)] bg-[var(--ink-3)] text-[var(--on-brand)] dark:text-[var(--canvas)]"
              : "border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)]"
              }`}
          >
            <MagnifyingGlass size={14} weight="bold" />
            검토필요 <span className="font-mono">{nReview}</span> 건
          </button>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[14px] font-bold border border-dashed rounded-[3px] border-[var(--line-2)] text-[var(--ink-3)] bg-transparent">
            미판정 <span className="font-mono">{d.unjudged.length}</span> 건
          </span>
          {flagFilter && (
            <button
              type="button"
              onClick={() => setFlagFilter(null)}
              className="inline-flex items-center gap-1 px-2 py-1 text-[12px] font-mono text-[var(--ink-3)] border border-dashed border-[var(--line-2)] rounded-[3px] cursor-pointer hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
            >
              <X size={11} weight="bold" /> 전체 보기
            </button>
          )}
        </div>
        {d.summary.n_ocr_failed_tiles > 0 && (
          // 위반 신호가 아니라 "우리가 못 읽었다"는 안내라 경보색을 쓰지 않는다
          // (§F, PM 8대 루루 지시 2026-08-22). 글자로만 알린다.
          <p className="m-0 mt-2.5 text-[12px] text-[var(--ink-3)]">
            이미지 일부를 못 읽었습니다. 다시 시도해 주세요.
          </p>
        )}
      </div>

      {/* 2단 리포트 그리드 (뼈대 유지) */}
      <div className="grid grid-cols-[0.86fr_1.14fr] max-[900px]:grid-cols-1">
        <div className="p-[18px_20px_22px] border-r border-[var(--line)] max-[900px]:border-r-0 max-[900px]:border-b max-[900px]:border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11.5px] p-[2px_7px] inline-flex items-center">01</span>
            <h2 className="m-0 text-[14px] font-bold text-[var(--ink)] tracking-[-0.2px]">검증 카드</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
            <span className="text-[var(--ink-3)] font-mono text-[11px]">
              {flagFilter && <span className="font-mono">{visibleFindGroups.length}/</span>}
              <span className="font-mono">{findGroups.length}</span>건
            </span>
          </div>
          {/* 모두 수용: 개별 수용 버튼(채움, --brand-deep/--brand)보다 시각적으로
              약하게 - 일괄 동작이 기본값처럼 보이면 안 된다(팀장 지시,
              2026-08-23). 채움 없이 테두리+텍스트만 쓴다. 이미 "제외"한 항목은
              명시적 결정이라 안 건드리고, 필터가 걸려 있으면 보이는 것만 대상이다
              (버튼 문구가 그 범위를 드러낸다). 되돌리기는 확인 모달 대신 클릭
              직후 나타나는 링크로 처리한다(17건 일괄 변경이라 사고 방지 필요하지만
              모달 확인 단계를 넣기엔 개별 수용/제외에 이미 있는 토글식 취소
              관례와 결이 다르다고 판단). */}
          {/* FREE 티어는 카드에 수용/제외 버튼 자체가 없다("유료 요금제 전용"만
              보임) - 일괄 버튼만 따로 있으면 앞뒤가 안 맞는다. */}
          {tier !== "FREE" && (
            <div className="flex items-center gap-2.5 mb-2.5">
              <button
                type="button"
                onClick={handleAcceptAllVisible}
                disabled={acceptAllTargets.length === 0}
                className="font-mono text-[11px] font-semibold text-[var(--ink-3)] border border-[var(--line-2)] rounded-sm px-2 py-1 cursor-pointer inline-flex items-center gap-1 hover:text-[var(--ink)] hover:border-[var(--ink-3)] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:text-[var(--ink-3)] disabled:hover:border-[var(--line-2)]"
              >
                <Check size={11} weight="bold" />
                {flagFilter ? `보이는 ${acceptAllTargets.length}건 모두 수용` : `모두 수용 (${acceptAllTargets.length}건)`}
              </button>
              {bulkUndoSnapshot && (
                <button
                  type="button"
                  onClick={handleUndoBulkAccept}
                  className="font-mono text-[11px] text-[var(--ink-3)] underline cursor-pointer hover:text-[var(--ink)]"
                >
                  되돌리기
                </button>
              )}
            </div>
          )}
          {/* 신뢰도 범례. 상/중/하로 가면서 "하 = 안전"으로 오독될 위험이 커져서,
              뒷문장(낮아도 실제 위반일 수 있다)이 유일한 방어다 - 절대 빼지 않는다
              (디디 확정, 2026-08-23). */}
          <p className="m-0 mb-2.5 text-[11px] text-[var(--ink-3)]">
            신뢰도 상·중·하는 AI가 이 판정에 얼마나 확신하는지를 나타내며, 위반·검토필요(심각도)와는 다른 축입니다. 신뢰도 하는 지적이 틀렸거나 무시해도 된다는 뜻이 아닙니다. 실제 위반이어도 AI가 낮은 확신으로 판단할 수 있습니다.
          </p>
          <div className="flex flex-col gap-3">
            {findGroups.map((g, orderIndex) => {
              if (flagFilter && g.representative.flag !== flagFilter) return null;
              return (
                <FindingCard
                  key={g.key}
                  finding={g.representative}
                  index={g.repIdx}
                  positionIdxs={g.positionIdxs}
                  orderIndex={orderIndex}
                  num={g.num}
                  act={actions[g.repIdx] || null}
                  onAction={handleAction}
                  isHovered={g.positionIdxs.includes(hoveredIndex ?? -1)}
                  onHover={(h) => setHoveredIndex(h ? g.repIdx : null)}
                  open={openOrderIndex === orderIndex}
                  onToggle={() => {
                    setOpenOrderIndex(openOrderIndex === orderIndex ? null : orderIndex);
                  }}
                  onScrollToPosition={(idx) => scrollToBox(idx, false)}
                  tier={tier}
                  remediationCount={remediationCount}
                  onFetchRemediation={() => setRemediationCount((prev) => prev + 1)}
                  replacement={replacementByFindingIndex.get(g.repIdx)}
                  hasReportReplacements={hasReportReplacements}
                />
              );
            })}
            {flagFilter && visibleFindGroups.length === 0 && (
              <div className="flex flex-col items-center gap-2 border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[24px_16px] text-center">
                <p className="m-0 text-[13px] text-[var(--ink-3)]">
                  {flagFilter} 항목이 없습니다.
                </p>
                <button
                  type="button"
                  onClick={() => setFlagFilter(null)}
                  className="text-[12px] font-mono text-[var(--brand-ink)] border-b border-[var(--brand-ink)] cursor-pointer bg-transparent"
                >
                  전체 보기
                </button>
              </div>
            )}
          </div>
          {d.unjudged.length > 0 && (
            <div className="mt-4 pt-3.5 border-t border-dashed border-[var(--line-2)]">
              <div className="flex items-center gap-[11px] m-[0_0_13px]">
                <span className="text-[var(--ink-3)] bg-[var(--surface-sub)] border border-[var(--line-2)] font-mono font-bold text-[11.5px] p-[2px_7px] inline-flex items-center">?</span>
                <h2 className="m-0 text-[14px] font-bold text-[var(--ink)] tracking-[-0.2px]">재검사 필요</h2>
                <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
                <span className="text-[var(--ink-3)] font-mono text-[11px]">판정 실패 · 미판정</span>
              </div>
              <div className="flex flex-col gap-1.5">
                {ujByOrder.map((u, i) => (
                  <div
                    className="flex items-start gap-2.25 border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[8px_10px] cursor-pointer hover:bg-[var(--surface)] transition-all duration-[120ms]"
                    onClick={() => scrollToBox(i, true)}
                    key={i}
                  >
                    <span className="shrink-0 w-[18px] h-[18px] inline-flex items-center justify-center font-mono text-[10.5px] font-bold text-[var(--ink-3)] border border-dashed border-[var(--ink-3)] rounded-full">{String.fromCharCode(65 + i)}</span>
                    <span className="flex-1 text-[13px] text-[var(--ink-2)]">{u.sentence}</span>
                    <span className="shrink-0 font-mono text-[10.5px] text-[var(--ink-3)]">
                      {u.location.tile ? u.location.tile : `문구 #${u.location.order}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="p-[18px_20px_22px]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11.5px] p-[2px_7px] inline-flex items-center">02</span>
            <h2 className="m-0 text-[14px] font-bold text-[var(--ink)] tracking-[-0.2px]">원문 하이라이트</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
            <span className="text-[var(--ink-3)] font-mono text-[11px]">
              {isImageMode ? "이미지 모드 · 타일 오버레이" : "텍스트 모드 · 스팬 밑줄"}
            </span>
          </div>
          <div id="origPanel">
            {loading ? (
              <p className="text-[var(--ink-3)] p-3">
                로딩 중...
              </p>
            ) : isImageMode ? (
              (() => {
                const byTile: Record<
                  string,
                  Array<
                    | { type: "find"; num: number; idx: number; item: typeof d.findings[number] }
                    | { type: "uj"; letter: string; item: typeof d.unjudged[number] }
                  >
                > = {};

                findByOrder.forEach((o) => {
                  const t = o.f.location.tile;
                  if (t) {
                    if (!byTile[t]) byTile[t] = [];
                    byTile[t].push({ type: "find", num: o.num, idx: o.idx, item: o.f });
                  }
                });

                ujByOrder.forEach((u, i) => {
                  const t = u.location.tile;
                  if (t) {
                    if (!byTile[t]) byTile[t] = [];
                    byTile[t].push({ type: "uj", letter: String.fromCharCode(65 + i), item: u });
                  }
                });

                const tiles = Object.keys(byTile).sort();

                const sampleLoc = findByOrder[0]?.f.location || ujByOrder[0]?.location;
                const srcW = sampleLoc?.source_w;
                const srcH = sampleLoc?.source_h;

                const hasCoords =
                  typeof srcW === "number" &&
                  typeof srcH === "number" &&
                  srcW > 0 &&
                  srcH > 0;

                const isMockId =
                  activeEnvelope.result_id === "demo-image-id" ||
                  activeEnvelope.result_id === "image" ||
                  activeEnvelope.result_id === "demo-id-1" ||
                  activeEnvelope.result_id === "demo-id-3" ||
                  activeEnvelope.result_id === "demo-id-5";

                const showRealImage = hasCoords && !isMockId && !imageErrors.global;
                const imageUrl = getReportImageUrl(activeEnvelope.result_id);

                if (showRealImage) {
                  return (
                    <div className="border border-[var(--line-2)] p-3 bg-[var(--surface-sub)] flex flex-col gap-2">
                      <div className="font-mono text-[11px] text-[var(--ink-3)] mb-1">
                        원본 광고 검증 이미지 ({srcW}x{srcH} px)
                      </div>
                      <div
                        className="relative w-full"
                        style={{
                          aspectRatio: `${srcW} / ${srcH}`,
                          overflow: "hidden",
                          backgroundColor: "var(--surface)",
                        }}
                      >
                        <img
                          src={imageUrl}
                          alt="원본 광고"
                          onError={() => {
                            setImageErrors((prev) => ({ ...prev, global: true }));
                          }}
                          style={{
                            width: "100%",
                            height: "100%",
                            display: "block",
                          }}
                        />

                        {/* 실제 좌표 기반 하이라이트 박스 오버레이 */}
                        <div className="absolute inset-0 z-10 pointer-events-none">
                          {(() => {
                            // 같은 위치(문장 order 또는 y_start)를 공유하는 항목들의 서브 인덱스 계산 (배지 겹침 방지)
                            const locCounts: Record<string, number> = {};
                            const itemSubIndices: Record<number, number> = {};

                            findByOrder.forEach((o) => {
                              const key = `${o.f.location.tile}_${o.f.location.order}_${o.f.location.y_start}_${o.f.location.x_start ?? 0}`;
                              itemSubIndices[o.idx] = locCounts[key] || 0;
                              locCounts[key] = (locCounts[key] || 0) + 1;
                            });

                            return findByOrder.map((o) => {
                              const loc = o.f.location;
                              if (typeof loc.y_start !== "number" || typeof loc.y_end !== "number") return null;
                              const isExcluded = actions[o.idx] === "exclude";
                              if (isExcluded) return null;

                              const hasX = typeof loc.x_start === "number" && typeof loc.x_end === "number" && loc.x_end > loc.x_start;

                              // 시각적 여백(패딩): 좌우 6px, 상하 4px 확장
                              const padXPct = hasX ? (10 / srcW) * 100 : 0;
                              const padYPct = (10 / srcH) * 100;

                              const rawTopPct = (loc.y_start / srcH) * 100;
                              const rawHeightPct = ((loc.y_end - loc.y_start) / srcH) * 100;
                              const rawLeftPct = hasX ? (loc.x_start! / srcW) * 100 : 0;
                              const rawWidthPct = hasX ? ((loc.x_end! - loc.x_start!) / srcW) * 100 : 100;

                              const leftPct = Math.max(0, rawLeftPct - padXPct);
                              const widthPct = hasX ? Math.min(100 - leftPct, rawWidthPct + padXPct * 2) : 100;
                              const topPct = Math.max(0, rawTopPct - padYPct);
                              const heightPct = Math.min(100 - topPct, rawHeightPct + padYPct * 2);

                              const isViolation = o.f.flag === "위반";
                              const isHovered = hoveredIndex === o.idx;
                              const badgeOffset = (itemSubIndices[o.idx] || 0) * 22; // 4, 5번 등 같은 문장 항목 나란히 배치

                              return (
                                <div
                                  id={`highlight-box-${o.idx}`}
                                  key={`find-${o.idx}`}
                                  style={{
                                    position: "absolute",
                                    left: `${leftPct}%`,
                                    width: `${widthPct}%`,
                                    top: `${topPct}%`,
                                    height: `${heightPct}%`,
                                    border: isViolation
                                      ? `2px solid ${isHovered ? "var(--crit)" : "rgba(239, 68, 68, 0.85)"}`
                                      : `2px dashed ${isHovered ? "var(--ink)" : "rgba(100, 116, 139, 0.6)"}`,
                                    backgroundColor: isViolation
                                      ? (isHovered ? "rgba(239, 68, 68, 0.18)" : "rgba(239, 68, 68, 0.08)")
                                      : (isHovered ? "rgba(100, 116, 139, 0.15)" : "rgba(100, 116, 139, 0.04)"),
                                    borderRadius: "4px",
                                    pointerEvents: "auto",
                                    cursor: "pointer",
                                    transition: "all 0.15s ease-in-out",
                                    boxShadow: isHovered ? "0 0 0 2px rgba(239, 68, 68, 0.3)" : "none",
                                  }}
                                  onMouseEnter={() => setHoveredIndex(o.idx)}
                                  onMouseLeave={() => setHoveredIndex(null)}
                                >
                                  <span
                                    style={{
                                      position: "absolute",
                                      left: `${-8 + badgeOffset}px`,
                                      top: "-10px",
                                      width: "19px",
                                      height: "19px",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      fontFamily: "monospace",
                                      fontSize: "10.5px",
                                      fontWeight: "bold",
                                      borderRadius: "50%",
                                      border: `1.5px solid ${isViolation ? "var(--crit)" : "var(--ink-3)"}`,
                                      color: isViolation ? "var(--crit)" : "var(--ink-3)",
                                      backgroundColor: "var(--surface)",
                                      boxShadow: "0 1px 3px rgba(0,0,0,0.18)",
                                      zIndex: 10 + (itemSubIndices[o.idx] || 0),
                                    }}
                                  >
                                    {o.num}
                                  </span>
                                </div>
                              );
                            });
                          })()}

                          {ujByOrder.map((u, i) => {
                            const loc = u.location;
                            if (typeof loc.y_start !== "number" || typeof loc.y_end !== "number") return null;

                            const topPct = (loc.y_start / srcH) * 100;
                            const heightPct = ((loc.y_end - loc.y_start) / srcH) * 100;
                            const hasX = typeof loc.x_start === "number" && typeof loc.x_end === "number" && loc.x_end > loc.x_start;
                            const leftPct = hasX ? (loc.x_start! / srcW) * 100 : 0;
                            const widthPct = hasX ? ((loc.x_end! - loc.x_start!) / srcW) * 100 : 100;
                            const letter = String.fromCharCode(65 + i);

                            return (
                              <div
                                id={`highlight-box-uj-${i}`}
                                key={`uj-${i}`}
                                style={{
                                  position: "absolute",
                                  left: `${leftPct}%`,
                                  width: `${widthPct}%`,
                                  top: `${topPct}%`,
                                  height: `${heightPct}%`,
                                  border: "2px dashed rgba(100, 116, 139, 0.4)",
                                  backgroundColor: "rgba(100, 116, 139, 0.04)",
                                  borderRadius: "3px",
                                }}
                              >
                                <span
                                  style={{
                                    position: "absolute",
                                    right: "-8px",
                                    top: "-8px",
                                    width: "18px",
                                    height: "18px",
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontFamily: "monospace",
                                    fontSize: "10px",
                                    fontWeight: "bold",
                                    borderRadius: "50%",
                                    border: "1px dashed var(--ink-3)",
                                    color: "var(--ink-3)",
                                    backgroundColor: "var(--surface)",
                                    boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
                                    zIndex: 2,
                                  }}
                                >
                                  {letter}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                }

                return (
                  <>
                    {tiles.map((t) => {
                      const rows = byTile[t].sort(
                        (a, b) => a.item.location.order - b.item.location.order
                      );
                      return (
                        <div className="border border-[var(--line-2)] mb-3.5 last:mb-0" key={t}>
                          <div className="font-mono text-[11px] text-[var(--ink-3)] p-[6px_10px] border-b border-[var(--line)] bg-[var(--surface-sub)]">{t}</div>
                          <div className="relative aspect-[4/5] bg-[repeating-linear-gradient(135deg,var(--surface-sub)_0_10px,var(--surface)_10px_20px)] p-2.5 flex flex-col gap-2">
                            {rows.map((r, ri) => {
                              if (r.type === "find") {
                                const isExcluded = actions[r.idx] === "exclude";
                                const cls = r.item.flag === "위반" ? "violation" : "review";
                                const isRowHovered = hoveredIndex === r.idx;
                                return (
                                  <div
                                    className={`relative flex items-center gap-2 p-[7px_9px] text-[12.5px] border transition-all duration-[120ms] ${isExcluded
                                      ? "opacity-50 border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]"
                                      : cls === "violation"
                                        ? `border-[var(--crit-bd)] ${isRowHovered ? "bg-[rgba(239,68,68,0.18)] border-[var(--crit)] scale-[1.01]" : "bg-[var(--crit-bg)]"} text-[var(--crit)]`
                                        : `border-[var(--line-2)] ${isRowHovered ? "bg-[var(--surface-sub)] border-[var(--ink-2)] scale-[1.01]" : "bg-[var(--surface)]"} text-[var(--ink-2)] border-solid`
                                      }`}
                                    onMouseEnter={() => setHoveredIndex(r.idx)}
                                    onMouseLeave={() => setHoveredIndex(null)}
                                    key={ri}
                                  >
                                    <span className={`shrink-0 w-[19px] h-[19px] inline-flex items-center justify-center font-mono text-[11px] font-bold rounded-full border-[1.5px] border-current ${isExcluded
                                      ? "text-[var(--ink-3)] border-[var(--ink-3)]"
                                      : cls === "violation"
                                        ? "text-[var(--crit)] border-[var(--crit)]"
                                        : "text-[var(--ink-3)] border-[var(--ink-3)]"
                                      }`}>{r.num}</span>
                                    <span className={`flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap ${cls === "violation" && !isExcluded ? "text-[var(--crit)]" : ""
                                      }`}>{r.item.span}</span>
                                  </div>
                                );
                              } else {
                                return (
                                  <div className="relative flex items-center gap-2 p-[7px_9px] text-[12.5px] border border-dashed border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]" key={ri}>
                                    <span className="shrink-0 w-[19px] h-[19px] inline-flex items-center justify-center font-mono text-[11px] font-bold rounded-full border border-dashed border-[var(--ink-3)] text-[var(--ink-3)]">{r.letter}</span>
                                    <span className="flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{r.item.sentence}</span>
                                  </div>
                                );
                              }
                            })}
                          </div>
                        </div>
                      );
                    })}
                    <p className="text-[var(--ink-3)] text-[10.5px] mt-2">
                      실제 좌표(bbox)는 없어 타일 내 순서대로만 배치(문서 참조)
                    </p>
                  </>
                );
              })()
            ) : (
              (() => {
                const seenFindings: Record<string, Array<{ span: string; cls: string; badge: number; idx: number }>> = {};
                const sentenceOrders: Record<string, number> = {};

                findByOrder.forEach((o) => {
                  const sentence = o.f.sentence;
                  if (!seenFindings[sentence]) {
                    seenFindings[sentence] = [];
                    sentenceOrders[sentence] = o.f.location.order;
                  }
                  seenFindings[sentence].push({
                    span: o.f.span,
                    cls: o.f.flag === "위반" ? "violation" : "review",
                    badge: o.num,
                    idx: o.idx,
                  });
                });

                const unjudgedSentences: Array<{ sentence: string; letter: string; order: number }> = [];
                ujByOrder.forEach((u, i) => {
                  unjudgedSentences.push({
                    sentence: u.sentence,
                    letter: String.fromCharCode(65 + i),
                    order: u.location.order,
                  });
                });

                interface TextSentenceNode {
                  type: "find" | "uj";
                  sentence: string;
                  order: number;
                  hlItems?: Array<{ span: string; cls: string; badge: number; idx: number }>;
                  letter?: string;
                }

                const allSentences: TextSentenceNode[] = [];

                Object.keys(seenFindings).forEach((s) => {
                  allSentences.push({
                    type: "find",
                    sentence: s,
                    order: sentenceOrders[s],
                    hlItems: seenFindings[s],
                  });
                });

                unjudgedSentences.forEach((u) => {
                  allSentences.push({
                    type: "uj",
                    sentence: u.sentence,
                    order: u.order,
                    letter: u.letter,
                  });
                });

                allSentences.sort((a, b) => a.order - b.order);

                const htmlContent = allSentences
                  .map((node) => {
                    if (node.type === "find" && node.hlItems) {
                      return markSentence(node.sentence, node.hlItems, actions);
                    } else if (node.type === "uj" && node.letter) {
                      return `<span class="relative px-[1px] cursor-default border-b-2 border-dashed border-[var(--ink-3)]"><span class="absolute top-[-9px] left-[-2px] font-mono text-[9.5px] font-bold color-inherit">${node.letter}</span>${escapeHtml(
                        node.sentence
                      )}</span>`;
                    }
                    return "";
                  })
                  .join(" ");

                return (
                  <div
                    className="border border-[var(--line-2)] bg-[var(--surface-sub)] p-[16px_15px] text-[15px] text-[var(--ink)] leading-[2]"
                    dangerouslySetInnerHTML={{ __html: htmlContent }}
                  />
                );
              })()
            )}
          </div>
        </div>
      </div>

      {/* 하단 브릿지 */}
      <div className="p-[18px_20px] border-t border-[var(--line)] flex items-center justify-between gap-3.5 flex-wrap">
        <p className="m-0 text-[12.5px] text-[var(--ink-3)] max-w-[56ch]">지적된 표현을 검토했다면, 위험을 낮춘 수정 권고안을 반영해 상세페이지 초안을 만들 수 있어요.</p>
        {tier === "PRO" ? (
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              href={`/content?id=${activeEnvelope.result_id}&accepted=${acceptedIndices}`}
              onClick={(e) => {
                if (!hasInteracted) {
                  const proceed = window.confirm(
                    "수정 권고안에 대해 '수용' 또는 '제외'를 선택하지 않으셨습니다. 모든 위반 우려 표현을 수용한 상태로 상세페이지 초안을 생성하시겠습니까?\n\n'취소'를 누르시면 리포트에서 직접 선택하실 수 있습니다."
                  );
                  if (!proceed) {
                    e.preventDefault();
                  }
                }
              }}
              className="font-sans text-[14px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] no-underline"
            >
              이 수정안대로 상세페이지 만들기 <span className="font-mono">→</span>
            </Link>
            <Link
              href="/content?mode=create"
              className="font-sans text-[14px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] no-underline"
            >
              처음부터 새로 만들기 <span className="font-mono">→</span>
            </Link>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 max-[600px]:flex-col max-[600px]:items-end">
            <span className="text-[11.5px] text-[var(--crit)] font-semibold">🔒 상세페이지 제작은 Pro 요금제 전용 기능입니다.</span>
            <button
              disabled
              className="font-sans text-[13px] font-bold p-[10px_14px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-3)] cursor-not-allowed inline-flex items-center justify-center gap-1.5 rounded-sm"
            >
              상세페이지 만들기 잠김 🔒
            </button>
          </div>
        )}
      </div>

      <PageFooter basis={envelope.report.basis ?? null} snapshot />
    </>
  );
}
