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

  // 텍스트 글자색은 유지하고 테두리와 배경으로만 하이라이트
  const spanStyle = `font-semibold text-[var(--ink)] border px-1.5 py-0.5 rounded-sm inline-block ${cls === "violation" ? "border-[var(--crit)] bg-[var(--crit-bg)]" : "border-[var(--line-2)] bg-[var(--surface-sub)]"
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
          {/* 사각형 번호 배지 */}
          <span className={`shrink-0 w-[22px] h-[22px] inline-flex items-center justify-center font-mono text-[11px] font-bold border rounded-none bg-[var(--surface)] ${cls === "violation" ? "text-[var(--crit)] border-[var(--crit)]" : "text-[var(--ink-3)] border-[var(--line-2)]"
            }`}>{num}</span>

          {/* 컨텍스트 콘텐츠 영역 (1행: 문구와 액션 / 2행: 유형 정보) */}
          <div className="flex-1 min-w-0">
            {/* 1행: 문구 + 수용/제외 버튼(유료 한정) 또는 유료 안내 + chevron */}
            <div className="flex items-center justify-between gap-2">
              <span className={`${spanStyle} ${isExcluded ? "line-through opacity-50" : ""}`}>
                {finding.span}
                {positionIdxs.length > 1 && (
                  <span className="ml-1 font-mono font-normal text-[10px] opacity-75">({positionIdxs.length}곳)</span>
                )}
              </span>

              <div className="flex items-center gap-1.5 ml-auto">
                {tier === "FREE" ? (
                  <span className="text-[10px] font-bold text-[var(--ink-3)] bg-[var(--line)] px-2 py-0.5 rounded-sm border border-[var(--line-2)]">
                    유료 요금제 전용
                  </span>
                ) : (
                  <>
                    <button
                      // 수용=채움, 제외=윤곽선으로 위계를 준다(새 심각도 색 없이, 팀장 지시).
                      // 라이트는 --brand 배경이 대비 미달(3.39:1)이라 --brand-deep(9.36:1) 사용,
                      // 다크는 --brand 그대로 통과(6.48:1) - 디디 검증 완료(DESIGN.md §4.1, PR #268)
                      className={`font-sans text-[11px] p-[4px_9px] border rounded-sm cursor-pointer inline-flex items-center gap-1 transition-all duration-[120ms] ${act === "accept"
                        ? "font-bold text-[var(--on-brand)] border-[var(--brand-deep)] bg-[var(--brand-deep)] dark:border-[var(--brand)] dark:bg-[var(--brand)]"
                        : "font-semibold text-[var(--ink-3)] border-[var(--line-2)] bg-transparent hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                        }`}
                      onClick={() => onAction(positionIdxs, orderIndex, "accept")}
                    >
                      <Check size={11} weight="bold" />
                      수용
                    </button>
                    <button
                      className={`font-sans text-[11px] p-[4px_9px] border rounded-sm cursor-pointer inline-flex items-center gap-1 transition-all duration-[120ms] ${act === "exclude"
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

            {/* 2행: 위반/검토필요 유형. flag가 검토필요인데 "위반"이라고 적으면 확정 위반과 헷갈린다 */}
            <div className="text-[11px] text-[var(--ink-3)] mt-1.5 font-medium leading-none">
              {cls === "violation" ? "위반 유형" : "검토 필요 유형"} {TYPE_LABEL[finding.violation_type as keyof typeof TYPE_LABEL] || finding.violation_type}
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
                <span className="text-[11px] text-[var(--ink-3)] font-semibold">발견 위치</span>
                {positionIdxs.map((pidx, i) => (
                  <button
                    key={pidx}
                    type="button"
                    onClick={() => onScrollToPosition(pidx)}
                    className="font-mono text-[10.5px] px-1.5 py-0.5 border border-[var(--line-2)] rounded-sm bg-[var(--surface-sub)] text-[var(--ink-2)] hover:bg-[var(--nav-hover)] hover:border-[var(--ink-3)] cursor-pointer"
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
                    className="font-sans text-[11.5px] font-bold p-[6px_14px] border border-[var(--brand)] bg-[var(--brand)] text-[var(--on-brand)] hover:bg-[var(--brand-deep)] cursor-pointer inline-flex items-center gap-1.5 transition-all duration-[120ms] rounded-sm shadow-sm"
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
                  className="text-[13px] text-[var(--ink-2)] leading-1.6 blur-[4px] select-none"
                  aria-hidden="true"
                >
                  {getRemediationText(
                    finding.violation_type,
                    <span className="font-bold text-[var(--brand-ink)] bg-[var(--nav-active-bg)] px-1.5 py-0.5 rounded-[3px] mx-1">
                      안전한 대체 표현
                    </span>
                  )}
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="flex items-center gap-1.5 bg-[var(--surface)] border border-[var(--line-2)] rounded-full px-3 py-1 shadow-sm">
                    <Lock size={12} weight="bold" className="text-[var(--ink-3)]" />
                    <span className="text-[11px] font-bold text-[var(--ink-3)]">유료 요금제 전용</span>
                  </div>
                </div>
              </div>
            )}

            {/* 조문 원문 인용 (화장품법 조항 및 조문 원문을 흰색 상자 안에 표기) */}
            {(finding.legal_basis || finding.legal_basis_text) && (
              <blockquote className="m-0 border border-[var(--line-2)] bg-[var(--surface)] p-[8px_12px] rounded-sm">
                {tier === "FREE" && num > 1 ? (
                  <span className="text-[12px] text-[var(--ink-3)] font-semibold block py-1">🔒 유료 요금제 전용 (Basic 이상 공개)</span>
                ) : (
                  <>
                    {finding.legal_basis && (
                      <div className="font-mono text-[11px] text-[var(--brand-ink)] font-semibold mb-1">
                        {finding.legal_basis}
                      </div>
                    )}
                    {finding.legal_basis_text && (
                      <div className="text-[12px] text-[var(--ink-2)] leading-[1.7] break-keep">
                        {finding.legal_basis_text}
                      </div>
                    )}
                  </>
                )}
              </blockquote>
            )}

            <p className="text-[12.5px] text-[var(--ink-2)] leading-1.6 m-0 font-sans">
              {/* 규칙 경로·VLM 경로 모두 표시 형식을 통일한다(백엔드가 explanation을
                  LLM 문장으로 바꿔도 화면은 그대로 받아 쓴다, PM 지시 2026-08-22) */}
              <span className="font-bold text-[var(--ink)]">[근거]</span> {finding.explanation}
            </p>

            {/* 대체 표현 제안 영역: 초록색 버튼 클릭 시 나타나며 로딩 진행 (유료 및 FREE 1번째 카드 한정) */}
            {(tier !== "FREE" || num === 1) && showSuggestionsArea && (
              <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface)] p-[12px_14px] rounded-sm transition-all duration-300">
                <div className="flex items-center gap-1.75 mb-2">
                  <b className="text-[11.5px] text-[var(--ink-2)] font-bold">대체 표현 제안</b>
                  {tier === "FREE" && (
                    <span className="font-mono text-[9.5px] text-[var(--ink-3)] border border-[var(--line-2)] p-[1px_6px] ml-2">
                      FREE 요금제 체험 (1/1)
                    </span>
                  )}
                </div>
                <div className="text-[13px] text-[var(--ink-2)] leading-1.6">
                  {loading ? (
                    <div className="flex items-center gap-2 text-[var(--ink-3)] font-mono text-[12px]">
                      <CircleNotch size={14} className="animate-spin text-[var(--brand-ink)]" />
                      대체 표현 제안을 불러오는 중...
                    </div>
                  ) : hasFetched ? (
                    suggestions.length > 0 ? (
                      <>
                        {getRemediationText(
                          finding.violation_type,
                          <span className="font-bold text-[var(--brand-ink)] bg-[var(--nav-active-bg)] px-1.5 py-0.5 rounded-[3px] mx-1">
                            {suggestions.join(", ")}
                          </span>
                        )}
                        {replacement?.note && (
                          <div className="mt-2 text-[11.5px] text-[var(--ink-3)] border-t border-dashed border-[var(--line-2)] pt-2">
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
      `<span class="${spanCls}"><span class="absolute top-[-9px] left-[-2px] font-mono text-[9px] font-bold color-inherit">${it.badge}</span>${needle}</span>`
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
    const key = `${f.sentence} ${f.violation_type}`;
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

  // 지적 카드 그룹핑(팀장 확정 A안): span+violation_type이 완전히 같으면 카드
  // 하나로 묶는다. 같은 span+유형은 규칙 매칭이라 결정론적이라 근거 문구
  // (finding.explanation)가 항상 같다 - 그룹 대표(첫 항목)만 보여줘도 근거가 갈리지
  // 않는다. 원문 하이라이트(원본 idx 기준)는 그대로 두고, 카드 번호만 그룹 단위로
  // 매긴다 - 아래서 findByOrder의 num을 그룹 번호로 되쓰면 원문 하이라이트 배지도
  // 자동으로 같은 그룹은 같은 번호를 쓰게 된다.
  const groupItemsByKey = new Map<string, number[]>();
  findByOrder.forEach((o) => {
    const key = `${o.f.span} ${o.f.violation_type}`;
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

  // finding_index로 지적 카드와 짝짓는다(PR #265). original은 경로마다(조건표=단어,
  // LLM=문장) 값이 달라 키가 못 된다.
  const hasReportReplacements = d.replacements.length > 0;
  const replacementByFindingIndex = new Map<number, (typeof d.replacements)[number]>();
  d.replacements.forEach((r) => {
    if (typeof r.finding_index === "number") {
      replacementByFindingIndex.set(r.finding_index, r);
    }
  });

  useEffect(() => {
    setRemediationCount(0);
    setOpenOrderIndex(0);
    setFlagFilter(null);
  }, [activeEnvelope]);

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
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
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
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[13px] font-bold border rounded-[3px] cursor-pointer transition-all duration-[120ms] ${nViol > 0
              ? "border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)]"
              : "border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)]"
              } ${flagFilter === "위반" ? "outline outline-2 outline-offset-1 outline-[var(--ink)]" : ""}`}
          >
            <Warning size={14} weight="bold" />
            위반 <span className="font-mono">{nViol}</span> 건
          </button>
          <button
            type="button"
            aria-pressed={flagFilter === "검토필요"}
            onClick={() => setFlagFilter((prev) => (prev === "검토필요" ? null : "검토필요"))}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[13px] font-bold border rounded-[3px] cursor-pointer transition-all duration-[120ms] border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)] ${flagFilter === "검토필요" ? "outline outline-2 outline-offset-1 outline-[var(--ink)]" : ""
              }`}
          >
            <MagnifyingGlass size={14} weight="bold" />
            검토필요 <span className="font-mono">{nReview}</span> 건
          </button>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[13px] font-bold border border-dashed rounded-[3px] border-[var(--line-2)] text-[var(--ink-3)] bg-transparent">
            미판정 <span className="font-mono">{d.unjudged.length}</span> 건
          </span>
          {flagFilter && (
            <button
              type="button"
              onClick={() => setFlagFilter(null)}
              className="inline-flex items-center gap-1 px-2 py-1 text-[11.5px] font-mono text-[var(--ink-3)] border border-dashed border-[var(--line-2)] rounded-[3px] cursor-pointer hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
            >
              <X size={11} weight="bold" /> 전체 보기
            </button>
          )}
        </div>
        {d.summary.n_ocr_failed_tiles > 0 && (
          // 위반 신호가 아니라 "우리가 못 읽었다"는 안내라 경보색을 쓰지 않는다
          // (§F, PM 8대 루루 지시 2026-08-22). 글자로만 알린다.
          <p className="m-0 mt-2.5 text-[11.5px] text-[var(--ink-3)]">
            이미지 일부를 못 읽었습니다. 다시 시도해 주세요.
          </p>
        )}
      </div>

      {/* 2단 리포트 그리드 (뼈대 유지) */}
      <div className="grid grid-cols-[0.86fr_1.14fr] max-[900px]:grid-cols-1">
        <div className="p-[18px_20px_22px] border-r border-[var(--line)] max-[900px]:border-r-0 max-[900px]:border-b max-[900px]:border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">검증 카드</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">
              {flagFilter && <span className="font-mono">{visibleFindGroups.length}/</span>}
              <span className="font-mono">{findGroups.length}</span>건
            </span>
          </div>
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
                    const nextOpen = openOrderIndex === orderIndex ? null : orderIndex;
                    setOpenOrderIndex(nextOpen);
                    if (nextOpen !== null) {
                      scrollToBox(g.repIdx, false);
                    }
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
                <p className="m-0 text-[12.5px] text-[var(--ink-3)]">
                  {flagFilter} 항목이 없습니다.
                </p>
                <button
                  type="button"
                  onClick={() => setFlagFilter(null)}
                  className="text-[11.5px] font-mono text-[var(--brand-ink)] border-b border-[var(--brand-ink)] cursor-pointer bg-transparent"
                >
                  전체 보기
                </button>
              </div>
            )}
          </div>
          {d.unjudged.length > 0 && (
            <div className="mt-4 pt-3.5 border-t border-dashed border-[var(--line-2)]">
              <div className="flex items-center gap-[11px] m-[0_0_13px]">
                <span className="text-[var(--ink-3)] bg-[var(--surface-sub)] border border-[var(--line-2)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">?</span>
                <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">재검사 필요</h2>
                <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
                <span className="text-[var(--ink-3)] font-mono text-[10.5px]">판정 실패 · 미판정</span>
              </div>
              <div className="flex flex-col gap-1.5">
                {ujByOrder.map((u, i) => (
                  <div
                    className="flex items-start gap-2.25 border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[8px_10px] cursor-pointer hover:bg-[var(--surface)] transition-all duration-[120ms]"
                    onClick={() => scrollToBox(i, true)}
                    key={i}
                  >
                    <span className="shrink-0 w-[18px] h-[18px] inline-flex items-center justify-center font-mono text-[10px] font-bold text-[var(--ink-3)] border border-dashed border-[var(--ink-3)] rounded-full">{String.fromCharCode(65 + i)}</span>
                    <span className="flex-1 text-[12.5px] text-[var(--ink-2)]">{u.sentence}</span>
                    <span className="shrink-0 font-mono text-[10px] text-[var(--ink-3)]">
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
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">원문 하이라이트</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">
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
                      <div className="font-mono text-[10.5px] text-[var(--ink-3)] mb-1">
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
                          <div className="font-mono text-[10.5px] text-[var(--ink-3)] p-[6px_10px] border-b border-[var(--line)] bg-[var(--surface-sub)]">{t}</div>
                          <div className="relative aspect-[4/5] bg-[repeating-linear-gradient(135deg,var(--surface-sub)_0_10px,var(--surface)_10px_20px)] p-2.5 flex flex-col gap-2">
                            {rows.map((r, ri) => {
                              if (r.type === "find") {
                                const isExcluded = actions[r.idx] === "exclude";
                                const cls = r.item.flag === "위반" ? "violation" : "review";
                                const isRowHovered = hoveredIndex === r.idx;
                                return (
                                  <div
                                    className={`relative flex items-center gap-2 p-[7px_9px] text-[12px] border transition-all duration-[120ms] ${isExcluded
                                      ? "opacity-50 border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]"
                                      : cls === "violation"
                                        ? `border-[var(--crit-bd)] ${isRowHovered ? "bg-[rgba(239,68,68,0.18)] border-[var(--crit)] scale-[1.01]" : "bg-[var(--crit-bg)]"} text-[var(--crit)]`
                                        : `border-[var(--line-2)] ${isRowHovered ? "bg-[var(--surface-sub)] border-[var(--ink-2)] scale-[1.01]" : "bg-[var(--surface)]"} text-[var(--ink-2)] border-solid`
                                      }`}
                                    onMouseEnter={() => setHoveredIndex(r.idx)}
                                    onMouseLeave={() => setHoveredIndex(null)}
                                    key={ri}
                                  >
                                    <span className={`shrink-0 w-[19px] h-[19px] inline-flex items-center justify-center font-mono text-[10.5px] font-bold rounded-full border-[1.5px] border-current ${isExcluded
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
                                  <div className="relative flex items-center gap-2 p-[7px_9px] text-[12px] border border-dashed border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]" key={ri}>
                                    <span className="shrink-0 w-[19px] h-[19px] inline-flex items-center justify-center font-mono text-[10.5px] font-bold rounded-full border border-dashed border-[var(--ink-3)] text-[var(--ink-3)]">{r.letter}</span>
                                    <span className="flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{r.item.sentence}</span>
                                  </div>
                                );
                              }
                            })}
                          </div>
                        </div>
                      );
                    })}
                    <p className="text-[var(--ink-3)] text-[10px] mt-2">
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
                      return `<span class="relative px-[1px] cursor-default border-b-2 border-dashed border-[var(--ink-3)]"><span class="absolute top-[-9px] left-[-2px] font-mono text-[9px] font-bold color-inherit">${node.letter}</span>${escapeHtml(
                        node.sentence
                      )}</span>`;
                    }
                    return "";
                  })
                  .join(" ");

                return (
                  <div
                    className="border border-[var(--line-2)] bg-[var(--surface-sub)] p-[16px_15px] text-[14px] text-[var(--ink)] leading-[2]"
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
        <p className="m-0 text-[12px] text-[var(--ink-3)] max-w-[56ch]">지적된 표현을 검토했다면, 위험을 낮춘 수정 권고안을 반영해 상세페이지 초안을 만들 수 있어요.</p>
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
              className="font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] no-underline"
            >
              이 수정안대로 상세페이지 만들기 <span className="font-mono">→</span>
            </Link>
            <Link
              href="/content?mode=create"
              className="font-sans text-[13px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] no-underline"
            >
              처음부터 새로 만들기 <span className="font-mono">→</span>
            </Link>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 max-[600px]:flex-col max-[600px]:items-end">
            <span className="text-[11px] text-[var(--crit)] font-semibold">🔒 상세페이지 제작은 Pro 요금제 전용 기능입니다.</span>
            <button
              disabled
              className="font-sans text-[12.5px] font-bold p-[10px_14px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-3)] cursor-not-allowed inline-flex items-center justify-center gap-1.5 rounded-sm"
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
