"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { Warning, MagnifyingGlass, Check, X, CaretDown, CircleNotch, Lock } from "@phosphor-icons/react";
import type { ReportEnvelope, Finding, Replacement } from "@/lib/api/schema";
import { getRemediation, getReportImageUrl } from "@/lib/api/client";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { useError } from "@/lib/error/ErrorContext";
import { ReportImageViewer } from "@/components/ReportImageViewer/ReportImageViewer";
import { Modal } from "@/components/Modal/Modal";
import { useTier, type Tier } from "@/lib/tier";



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
  tier: Tier;
  // 판정할 때 배치로 만들어져 리포트에 실려온 대체표현(PR #265). 있으면 그대로 쓰고
  // 새로 호출하지 않는다. hasReportReplacements가 false일 때만(옛 리포트·생성 실패)
  // /remediate 실시간 조회로 폴백한다.
  replacement: Replacement | undefined;
  hasReportReplacements: boolean;
  onOpenPricingModal: () => void;
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

// 잠긴 대체표현 자물쇠 클릭 시 뜨는 요금제 안내. 결제 연동 없이 티어
// 비교+업그레이드 CTA만 있는 가벼운 모달(시연용, 팀장 지시 2026-08-23).
// 실제 결제 대신 이 화면의 티어 미리보기 스위치를 바로 바꿔 데모 흐름을
// 끊지 않는다.
function PricingModal({
  isOpen,
  onClose,
  onSelectTier,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSelectTier: (tier: "Basic" | "Pro") => void;
}) {
  return (
    <Modal isOpen={isOpen} title="요금제 업그레이드" onClose={onClose} size="sm">
      <div className="flex flex-col gap-3">
        <p className="m-0 text-[12.5px] text-[var(--ink-3)] leading-[1.6]">
          FREE는 지적 3건까지만 근거·조문·대체표현을 볼 수 있어요. 업그레이드하면 전체 지적을 제한 없이 확인할 수 있습니다.
        </p>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => onSelectTier("Basic")}
            className="flex items-center justify-between gap-2 p-[10px_14px] border border-[var(--line-2)] rounded-sm cursor-pointer hover:border-[var(--brand)] transition-colors duration-[120ms] text-left"
          >
            <span>
              <span className="block font-bold text-[13px] text-[var(--ink)]">Basic</span>
              <span className="block text-[11.5px] text-[var(--ink-3)]">전체 지적 근거·조문·대체표현 무제한</span>
            </span>
            <span className="font-mono text-[11px] font-bold text-[var(--brand-ink)] whitespace-nowrap">선택 →</span>
          </button>
          <button
            type="button"
            onClick={() => onSelectTier("Pro")}
            className="flex items-center justify-between gap-2 p-[10px_14px] border border-[var(--line-2)] rounded-sm cursor-pointer hover:border-[var(--brand)] transition-colors duration-[120ms] text-left"
          >
            <span>
              <span className="block font-bold text-[13px] text-[var(--ink)]">Pro</span>
              <span className="block text-[11.5px] text-[var(--ink-3)]">Basic 전체 + 콘텐츠 생성·이력 대시보드</span>
            </span>
            <span className="font-mono text-[11px] font-bold text-[var(--brand-ink)] whitespace-nowrap">선택 →</span>
          </button>
        </div>
        <p className="m-0 text-[10.5px] text-[var(--ink-3)]">결제 연동 전 데모입니다 - 선택하면 이 화면의 티어 미리보기가 바뀝니다.</p>
      </div>
    </Modal>
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
  replacement,
  hasReportReplacements,
  onOpenPricingModal,
}: FindingCardProps) {
  const { showError } = useError();
  // 옛 리포트(hasReportReplacements=false)만 쓰는 폴백. 배치 데이터가 있으면
  // (표준 경로) replacement prop을 렌더 시점에 그대로 읽으면 되고 fetch가
  // 필요 없다 - 버튼 클릭으로 트리거하던 걸 없앴다(팀장 지시, 2026-08-23:
  // "버튼 눌렀는데 결과가 없음이면 그 버튼 자체가 낚시"). null=아직 안 불러옴.
  const [legacySuggestions, setLegacySuggestions] = useState<string[] | null>(null);
  const [legacyLoading, setLegacyLoading] = useState(false);

  useEffect(() => {
    if (hasReportReplacements) return;
    setLegacyLoading(true);
    setLegacySuggestions(null);
    getRemediation({
      sentence: finding.sentence,
      violation_type: finding.violation_type,
      span: finding.span,
    })
      .then((res) => {
        setLegacySuggestions(res.suggestions);
        setLegacyLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch remediation suggestion", err);
        showError("대체 제안 오류", "대체 표현 제안을 불러오지 못했습니다: " + (err instanceof Error ? err.message : String(err)));
        setLegacyLoading(false);
      });
  }, [finding, hasReportReplacements]);

  const cls = finding.flag === "위반" ? "violation" : "review";
  const isExcluded = act === "exclude";
  const isAccepted = act === "accept";
  const accentColor = cls === "violation" ? "var(--crit)" : "var(--ink-3)";
  // FREE 티어도 첫 3건은 근거·조문·대체표현 전부 잠금 없이(팀장 지시,
  // 2026-08-23) - num===1 한정 "체험 1회" 클릭 방식은 폐기.
  const isUnlocked = tier !== "Free" || num <= 3;

  const handleHeaderClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button")) {
      return;
    }
    onToggle();
  };

  // 대체 표현 3상태: 1) 표현 있음 2) 없음(구조적 제안 불가, 지어내지 않는다)
  // 3) 로딩 중(폴백 경로만 해당) - undefined면 아직 판단 불가(로딩).
  const replacementSuggestions: string[] | null | undefined = hasReportReplacements
    ? (replacement ? [replacement.replaced] : null)
    : legacyLoading
      ? undefined
      : (legacySuggestions && legacySuggestions.length > 0 ? legacySuggestions : null);

  return (
    <div
      // 규칙선 스타일(디디 카드 재설계 확정, design/mockups/card-terminal-redesign.html,
      // 2026-08-23) - 카드마다 테두리+배경 박스를 두르던 걸 왼쪽 심각도선 하나로
      // 대체한다. 항목 사이 구분선은 부모 목록 컨테이너의 [&>*+*]:border-t가 담당
      // (첫 카드는 위 구분선이 없어야 해서 :first-child 대신 인접 형제 선택자를 씀).
      // 카드 배경은 라이트만 흰색(--surface) - 디디 다크모드 작업은 여기서 멈췄고
      // 색 판단 남은 게 없는 단순 지시라 다크는 손 안 댐(PM 8대 루루 지시,
      // 2026-08-23, globals.css 37~55행 다크 값 그대로 유지).
      className={`pl-4 pb-4 border-l-[3px] bg-[var(--surface)] dark:bg-transparent ${isExcluded ? "opacity-50" : ""}`}
      style={{ borderLeftColor: accentColor }}
      data-i={index}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      {/* 토글 헤더 (상시 노출): 번호·flag·유형·신뢰도 한 줄 + 표현·수용/제외 한 줄.
          번호는 pill 밖 - pill 안엔 flag 텍스트만(팀장 지시, 2026-08-23). */}
      <div className="cursor-pointer" onClick={handleHeaderClick}>
        <div className="flex items-center gap-2.25 flex-wrap pt-3.5">
          <span className="font-mono text-[12px] font-bold text-[var(--ink-3)]">[{num}]</span>
          <span className="font-extrabold text-[13px] tracking-[0.2px]" style={{ color: accentColor }}>
            {cls === "violation" ? "위반" : "검토필요"}
          </span>
          {/* "위반 유형"/"검토 필요 유형" 접두어 제거 - 바로 앞 flag 텍스트와
              중복이었다(팀장 지시, 2026-08-23). */}
          <span className="text-[11.5px] text-[var(--ink-3)]">
            유형 {TYPE_LABEL[finding.violation_type as keyof typeof TYPE_LABEL] || finding.violation_type}
          </span>
          <EvidenceGradeBadge grade={finding.evidence_grade} />
          <span
            className={`ml-auto text-[var(--ink-3)] inline-flex items-center transition-transform duration-[200ms] ${open ? "rotate-180" : ""}`}
          >
            <CaretDown size={14} weight="bold" />
          </span>
        </div>

        {/* 표현(밑줄 인용) + 수용/제외. 잠긴 카드는 이 자리에 "유료 요금제 전용"을
            반복하지 않는다 - 접힌 헤더에서 아예 뺐다(팀장 지시, 카드당 문구는
            본문 안 한 곳으로 통일). 표현이 길어지면 줄어들며 줄바꿈되고 버튼
            묶음은 shrink-0으로 항상 제 폭을 지킨다(#292·#295 교훈 유지). */}
        <div className="flex items-center justify-between gap-3 mt-2.25">
          <span
            className={`font-bold text-[15px] text-[var(--ink)] pb-[3px] border-b-2 min-w-0 ${isExcluded ? "line-through opacity-50" : ""}`}
            style={{ borderBottomColor: accentColor }}
          >
            &ldquo;{finding.span}&rdquo;
            {positionIdxs.length > 1 && (
              <span className="ml-1 font-mono font-normal text-[10.5px] opacity-75">({positionIdxs.length}곳)</span>
            )}
          </span>

          {isUnlocked && (
            <div className="flex items-center gap-3 shrink-0 font-mono text-[11.5px]">
              {/* 수용 = 유일한 상태변경 주액션이라 항상 채움(CTA와 같은 급) -
                  §4.1 검증 조합 재사용(라이트 --brand-deep 9.36:1 / 다크 --brand
                  6.48:1). 이미 수용된 상태는 텍스트로 알린다(색만으로 상태를
                  구분하지 않는다, §F). */}
              <button
                className="font-bold whitespace-nowrap shrink-0 px-2.5 py-1 rounded-sm cursor-pointer text-[var(--on-brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] hover:opacity-90 transition-opacity duration-[120ms]"
                onClick={() => onAction(positionIdxs, orderIndex, "accept")}
              >
                {isAccepted ? "✓ 수용됨" : "[ 수용 ]"}
              </button>
              {/* 제외 = 보조 액션, 채움 없이 텍스트만. 선택 상태는 밑줄로 구분 */}
              <button
                className={`font-semibold whitespace-nowrap shrink-0 cursor-pointer text-[var(--ink-3)] hover:text-[var(--ink)] ${isExcluded ? "underline" : ""}`}
                onClick={() => onAction(positionIdxs, orderIndex, "exclude")}
              >
                {isExcluded ? "제외됨" : "제외"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 아코디언 바디 wrapper */}
      <div className={`accordion-wrapper ${open ? "open" : ""}`}>
        <div className="accordion-content">
          <div className="pt-3.5 flex flex-col gap-3.5">

            {/* 그룹으로 묶인 카드일 때만: 발견 위치별로 원문 하이라이트로 바로 이동 */}
            {positionIdxs.length > 1 && (
              <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                <span className="text-[var(--ink-3)] font-semibold">발견 위치</span>
                {positionIdxs.map((pidx, i) => (
                  <button
                    key={pidx}
                    type="button"
                    onClick={() => onScrollToPosition(pidx)}
                    className="px-1.5 py-0.5 border border-[var(--line-2)] rounded-sm text-[var(--ink-2)] hover:bg-[var(--nav-hover)] hover:border-[var(--ink-3)] cursor-pointer"
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            )}

            {/* 순서: [근거] → 조문 → 대체표현 - "왜 위반인지 먼저, 대응은 마지막"
                (팀장 지시, 2026-08-23). 대체표현을 맨 위에 두면 근거를 보기도
                전에 해결책부터 보여주는 셈이라 뒤로 옮겼다. */}
            <p className="text-[13.5px] text-[var(--ink-2)] leading-[1.7] m-0 font-sans max-w-[62ch]">
              {/* 규칙 경로·VLM 경로 모두 표시 형식을 통일한다(백엔드가 explanation을
                  LLM 문장으로 바꿔도 화면은 그대로 받아 쓴다, PM 지시 2026-08-22) */}
              <span className="font-bold text-[var(--ink)]">[근거]</span> {finding.explanation}
            </p>

            {/* 조문 원문 인용. 잠긴 카드는 자물쇠 아이콘만(문구 반복 제거 -
                카드당 "유료 요금제 전용"은 대체표현 자리 한 곳에만, 팀장 지시). */}
            {(finding.legal_basis || finding.legal_basis_text) && (
              <blockquote className="m-0 border-l border-[var(--line-2)] pl-3 max-w-[62ch]">
                {!isUnlocked ? (
                  <span className="inline-flex items-center py-1 text-[var(--ink-3)]">
                    <Lock size={13} weight="bold" />
                  </span>
                ) : (
                  <>
                    {finding.legal_basis && (
                      <div className="font-mono text-[11px] text-[var(--ink-3)] mb-1">
                        {finding.legal_basis}
                      </div>
                    )}
                    {finding.legal_basis_text && (
                      <div className="text-[12.5px] text-[var(--ink-3)] leading-[1.7] break-keep">
                        {finding.legal_basis_text}
                      </div>
                    )}
                  </>
                )}
              </blockquote>
            )}

            {/* 대체 표현: 버튼·클릭·fetch 흐름 없이 항상 렌더, 3상태로 분기
                (팀장 지시, 2026-08-23). CTA 버튼을 없앤다 - "버튼 눌렀는데
                결과가 없음이면 낚시"라는 지적을 그대로 반영. */}
            {!isUnlocked ? (
              // 상태 3: 잠금 - 블러+자물쇠, 클릭하면 요금제 모달. 카드당 유일한
              // "유료 요금제 전용" 문구가 여기 있다.
              <button
                type="button"
                onClick={onOpenPricingModal}
                className="relative max-w-[62ch] text-left cursor-pointer"
              >
                <div
                  className="text-[13.5px] text-[var(--ink-2)] leading-[1.7] blur-[3.5px] select-none"
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
                  <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-bold text-[var(--ink-3)] bg-[var(--canvas)] border border-[var(--line-2)] px-2.5 py-1 rounded-sm">
                    <Lock size={12} weight="bold" />
                    유료 요금제 전용
                  </span>
                </div>
              </button>
            ) : replacementSuggestions === undefined ? (
              // 상태: 로딩(옛 리포트 폴백 경로만)
              <div className="flex items-center gap-2 text-[var(--ink-3)] font-mono text-[12.5px] max-w-[62ch]">
                <CircleNotch size={14} className="animate-spin text-[var(--brand-ink)]" />
                대체 표현 제안을 불러오는 중...
              </div>
            ) : replacementSuggestions === null ? (
              // 상태 2: 제안 불가 - 지어내지 않고 정직하게 알린다(구조적으로
              // 자동 수정이 안 되는 문구, 예: 제품명·유통채널).
              <p className="text-[13.5px] text-[var(--ink-3)] leading-[1.7] m-0 max-w-[62ch]">
                자동 수정하지 못했습니다.
              </p>
            ) : (
              // 상태 1: 대체표현 있음 - 바로 표시
              <div className="text-[13.5px] text-[var(--ink-2)] leading-[1.7] max-w-[62ch]">
                {getRemediationText(
                  finding.violation_type,
                  <span className="font-bold text-[var(--on-brand)] bg-[var(--brand-deep)] dark:bg-[var(--brand)] px-1.5 py-0.5 rounded-[3px] mx-1">
                    {replacementSuggestions.join(", ")}
                  </span>
                )}
                {replacement?.note && (
                  <div className="mt-2 text-[12px] text-[var(--ink-3)] border-t border-dashed border-[var(--line-2)] pt-2">
                    ⓘ {replacement.note}
                  </div>
                )}
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
  const router = useRouter();
  const [activeEnvelope] = useState<Omit<ReportEnvelope, "report"> & { report: CheckReport }>(envelope);
  const [actions, setActions] = useState<Record<number, "accept" | "exclude" | null>>({});
  // "모두 수용" 실행취소용 스냅샷. 개별 조작이나 리포트 전환이 끼어들면 되돌릴
  // 대상이 불분명해지므로 null로 비운다(팀장 지시 - 17건 일괄 변경은 실수하면
  // 아파서 되돌리기가 있어야 한다, 2026-08-23).
  const [bulkUndoSnapshot, setBulkUndoSnapshot] = useState<Record<number, "accept" | "exclude" | null> | null>(null);
  const [imageErrors, setImageErrors] = useState<Record<string, boolean>>({});
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { tier, setTier } = useTier();
  // 대체표현 열람 "체험 1회" 클릭 카운트는 폐기(FREE도 첫 3건은 전부 잠금
  // 없이 보이는 구조로 바뀌어 더 이상 필요 없다, 2026-08-23).
  const [pricingModalOpen, setPricingModalOpen] = useState(false);
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [openOrderIndex, setOpenOrderIndex] = useState<number | null>(0);
  const [flagFilter, setFlagFilter] = useState<"위반" | "검토필요" | null>(null);

  const d = activeEnvelope.report;

  // 판정 로직 중복 제거(화면 워크어라운드, 근본 원인은 발표 후 과제 - PM 8대
  // 루루 지시 2026-08-22). 같은 문장이 규칙 경로와 VLM 경로에서 둘 다 finding으로
  // 나오면 sentence+violation_type이 같은 finding들이 생긴다. 이건 1번의 span
  // 그룹핑(§ 아래)으로는 안 걸린다(span 값 자체가 다르다) - 별도 단계로 먼저 걸러야
  // 한다.
  //
  // **2026-08-23 f.source 기준으로 재작성.** 원래는 "span이 문장 전체면 VLM"이라는
  // 휴리스틱으로 그룹당 대표 1개만 남겼는데, #296(문장당 규칙 지적 전건 매칭) 이후
  // 전제가 깨졌다 - 한 문장에서 같은 유형의 규칙 지적이 여러 개 나올 수 있게 됐는데
  // (예: '세포재생'·'진피층' 둘 다 1호), 대표 1개만 남기는 로직이 나머지를 화면과
  // 상단 요약 건수에서 지워버렸다(베베 감사로 발견). f.source("rule"|"vlm", 스키마에
  // 이미 있음)로 판단하면 정확하다:
  //   - 규칙 경로가 하나라도 있으면 전부 남긴다(문장당 여러 건 가능) + VLM은 버린다
  //     (규칙 경로가 더 구체적이라는 원래 의도는 유지)
  //   - VLM만 있으면 기존처럼 대표 1개만(VLM 중복은 같은 문구를 다시 잡은 것에
  //     가깝다)
  //   - source가 없는 예전 리포트는 안전하게 예전 span 휴리스틱으로 폴백
  const dedupGroups = new Map<string, number[]>();
  d.findings.forEach((f, i) => {
    const key = `${f.sentence}\0${f.violation_type}`;
    if (!dedupGroups.has(key)) dedupGroups.set(key, []);
    dedupGroups.get(key)!.push(i);
  });
  const visibleFindingIdx = new Set<number>();
  dedupGroups.forEach((idxs) => {
    const ruleIdxs = idxs.filter((i) => d.findings[i].source === "rule");
    const vlmIdxs = idxs.filter((i) => d.findings[i].source === "vlm");
    const unknownIdxs = idxs.filter((i) => d.findings[i].source !== "rule" && d.findings[i].source !== "vlm");

    if (ruleIdxs.length > 0) {
      ruleIdxs.forEach((i) => visibleFindingIdx.add(i));
    } else if (vlmIdxs.length > 0) {
      visibleFindingIdx.add(vlmIdxs[0]);
    }

    if (ruleIdxs.length === 0 && vlmIdxs.length === 0 && unknownIdxs.length > 0) {
      // source 없는 예전 리포트 폴백: 예전 span 휴리스틱(좁은 span=규칙 경로로 추정)
      let bestIdx = unknownIdxs[0];
      for (const i of unknownIdxs.slice(1)) {
        const current = d.findings[bestIdx];
        const candidate = d.findings[i];
        const currentIsWholeSentence = current.span === current.sentence;
        const candidateIsWholeSentence = candidate.span === candidate.sentence;
        if (currentIsWholeSentence && !candidateIsWholeSentence) {
          bestIdx = i;
        }
      }
      visibleFindingIdx.add(bestIdx);
    } else if (unknownIdxs.length > 0) {
      // rule/vlm이 이미 있는 그룹에 source 없는 것도 섞여 있으면(드묾) 안전하게 다 남긴다.
      unknownIdxs.forEach((i) => visibleFindingIdx.add(i));
    }
  });

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

  // "원본 보기" 토글·이미지 URL 결정에 둘 다 필요해서 헤더보다 앞서 계산해둔다.
  // 목업 result_id는 백엔드에 실제 이미지가 없어 원본 보기 자체를 못 띄운다(버그 아님,
  // PM 8대 루루 확인, 2026-08-23).
  const sampleLoc = findByOrder[0]?.f.location || ujByOrder[0]?.location;
  const srcW = sampleLoc?.source_w;
  const srcH = sampleLoc?.source_h;
  const hasCoords = typeof srcW === "number" && typeof srcH === "number" && srcW > 0 && srcH > 0;
  const isMockId =
    activeEnvelope.result_id === "demo-image-id" ||
    activeEnvelope.result_id === "image" ||
    activeEnvelope.result_id === "demo-id-1" ||
    activeEnvelope.result_id === "demo-id-3" ||
    activeEnvelope.result_id === "demo-id-5";
  const canShowRealImage = hasCoords && !isMockId && !imageErrors.global;

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
      <div className="grid grid-cols-[0.86fr_1.14fr] max-[900px]:grid-cols-1 items-start">
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
          {tier !== "Free" && (
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
          {/* 카드 사이 구분은 위 규칙선 하나로(디디 카드 재설계, 2026-08-23) -
              [&>*+*] 조합자로 첫 카드만 위 선이 없게 한다(:first-child 대신 -
              필터로 앞 카드들이 숨겨질 수 있어 "실제 렌더된 첫 카드"가 항상
              DOM상 첫 자식은 아니지만, 형제 결합자는 "바로 앞 형제가 있는
              요소"만 잡으므로 숨은 형제와 무관하게 정확히 동작한다). */}
          <div className="flex flex-col gap-3 [&>*+*]:border-t [&>*+*]:border-[var(--line)]">
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
                  replacement={replacementByFindingIndex.get(g.repIdx)}
                  hasReportReplacements={hasReportReplacements}
                  onOpenPricingModal={() => setPricingModalOpen(true)}
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
        <div className="p-[18px_20px_22px] flex flex-col min-h-0">
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
          <div id="origPanel" className="flex-1 flex flex-col min-h-0 sticky top-[20px]">
            {isImageMode ? (
              <ReportImageViewer
                findByOrder={findByOrder}
                ujByOrder={ujByOrder}
                imageUrl={canShowRealImage ? getReportImageUrl(activeEnvelope.result_id) : null}
                imageErrorGlobal={!!imageErrors.global}
                onImageError={() => setImageErrors((prev) => ({ ...prev, global: true }))}
                actions={actions}
                hoveredIndex={hoveredIndex}
                onHoverChange={setHoveredIndex}
              />
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
        {tier === "Pro" ? (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => {
                if (!hasInteracted) {
                  setConfirmModalOpen(true);
                } else {
                  router.push(`/content?id=${activeEnvelope.result_id}&accepted=${acceptedIndices}`);
                }
              }}
              className="font-sans text-[14px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms]"
            >
              이 수정안대로 상세페이지 만들기 <span className="font-mono">→</span>
            </button>
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

      <PricingModal
        isOpen={pricingModalOpen}
        onClose={() => setPricingModalOpen(false)}
        onSelectTier={(t) => {
          setTier(t);
          setPricingModalOpen(false);
        }}
      />

      <Modal
        isOpen={confirmModalOpen}
        title="상세페이지 생성 안내"
        onClose={() => setConfirmModalOpen(false)}
        size="md"
        footer={
          <div className="flex justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => setConfirmModalOpen(false)}
              className="font-sans text-[13px] font-semibold px-3.5 py-2 border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] cursor-pointer transition-all duration-[120ms]"
            >
              직접 선택
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirmModalOpen(false);
                router.push(`/content?id=${activeEnvelope.result_id}&accepted=${acceptedIndices}`);
              }}
              className="font-sans text-[13px] font-bold px-4 py-2 border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] hover:bg-[var(--brand-deep)] cursor-pointer transition-all duration-[120ms]"
            >
              일괄 수용하고 생성 →
            </button>
          </div>
        }
      >
        <div className="flex flex-col gap-3 py-1 text-[13px] text-[var(--ink-2)] leading-[1.6]">
          <div className="p-3.5 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)]">
            <p className="m-0 font-bold text-[13.5px] leading-snug">
              수정 권고안에 대해 '수용' 또는 '제외'를 선택하지 않으셨습니다.
            </p>
            <p className="m-[6px_0_0] text-[12.5px] text-[var(--ink-3)]">
              모든 위반 우려 표현을 수용한 상태로 상세페이지 초안을 생성하시겠습니까?
            </p>
          </div>
          <p className="m-0 text-[12px] text-[var(--ink-3)]">
            '직접 선택'을 누르시면 리포트 화면에서 각 수정 권고안을 개별 검토하실 수 있습니다.
          </p>
        </div>
      </Modal>
    </>
  );
}
