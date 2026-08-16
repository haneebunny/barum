"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { Warning, MagnifyingGlass, Check, X, Clock } from "@phosphor-icons/react";
import type { ReportEnvelope, Finding } from "@/lib/api/schema";
import { getReport, getRemediation, getReportImageUrl } from "@/lib/api/client";
import { PageFooter } from "@/components/PageFooter/PageFooter";

const TYPE_LABEL = {
  "1호_의약품오인": "1호 · 의약품 오인",
  "2호_기능성오인": "2호 · 기능성 오인",
  "5호_거짓과장기만": "5호 · 거짓·과장·기만",
};

interface FindingCardProps {
  finding: Finding;
  index: number;
  num: number;
  act: "accept" | "exclude" | "hold" | null;
  onAction: (idx: number, act: "accept" | "exclude" | "hold") => void;
  isHovered: boolean;
  onHover: (hover: boolean) => void;
  onCardClick?: (idx: number) => void;
}

function FindingCard({ finding, index, num, act, onAction, isHovered, onHover, onCardClick }: FindingCardProps) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getRemediation({
      sentence: finding.sentence,
      violation_type: finding.violation_type,
      span: finding.span,
    })
      .then((res) => {
        if (active) {
          setSuggestions(res.suggestions);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to fetch remediation suggestion", err);
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [finding]);

  const cls = finding.flag === "위반" ? "violation" : "review";
  const isExcluded = act === "exclude";
  const isHold = act === "hold";

  const cardCls = `border border-[var(--line-2)] bg-[var(--surface)] transition-all duration-[120ms] ${
    cls === "violation" ? "border-l-[3px] border-l-[var(--crit)]" : "border-l-[3px] border-l-[var(--ink-3)]"
  } ${isExcluded ? "opacity-50" : ""} ${isHold ? "relative" : ""} ${
    isHovered ? "translate-x-0.5 border-[var(--ink-2)] bg-[var(--surface-sub)]" : ""
  }`;

  const spanStyle = cls === "violation" ? "font-bold text-[var(--crit)] border-b-2 border-[var(--crit)]" : "font-bold text-[var(--ink)] border-b-2 border-[var(--ink-3)]";

  const handleCardClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button")) {
      return;
    }
    onCardClick?.(index);
  };

  return (
    <div
      className={cardCls}
      data-i={index}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onClick={handleCardClick}
      style={{ cursor: "pointer" }}
    >
      {isHold && <span className="absolute top-[9px] right-[12px] font-mono text-[10px] text-[var(--ink-3)]">보류 중</span>}
      <div className="flex items-center gap-2.25 p-[9px_12px] border-b border-[var(--line)] bg-[var(--surface-sub)]">
        <span className={`shrink-0 w-5 h-5 inline-flex items-center justify-center font-mono text-[11px] font-bold rounded-full border-[1.5px] border-current ${
          cls === "violation" ? "text-[var(--crit)] border-[var(--crit)]" : "text-[var(--ink-3)] border-[var(--ink-3)]"
        }`}>{num}</span>
        <span className="font-mono text-[11px] text-[var(--ink-2)] font-semibold">
          {TYPE_LABEL[finding.violation_type as keyof typeof TYPE_LABEL] || finding.violation_type}
        </span>
        <span className={`ml-auto inline-flex items-center gap-1.25 text-[11.5px] font-bold ${
          cls === "violation" ? "text-[var(--crit)]" : "text-[var(--ink-3)]"
        }`}>
          {cls === "violation" ? (
            <Warning size={14} weight="bold" />
          ) : (
            <MagnifyingGlass size={14} weight="bold" />
          )}
          {finding.flag}
        </span>
      </div>
      <div className="p-[13px_14px_14px]">
        <p
          className={`m-0 mb-2 text-[14px] text-[var(--ink)] leading-[1.65] ${isExcluded ? "line-through decoration-[var(--ink-3)]" : ""}`}
          dangerouslySetInnerHTML={{
            __html: escapeHtml(finding.sentence).replace(
              escapeHtml(finding.span),
              `<span class="${spanStyle}">${escapeHtml(finding.span)}</span>`
            ),
          }}
        />
        <p className="font-mono text-[11px] text-[var(--brand-ink)] m-[0_0_8px]">{finding.legal_basis}</p>
        <p className="text-[12.5px] text-[var(--ink-3)] leading-1.6 m-[0_0_12px]">{finding.explanation}</p>
        <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[10px_11px] m-[0_0_12px]">
          <div className="flex items-center gap-1.75 mb-1.5">
            <b className="text-[11.5px] text-[var(--ink-2)] font-bold">대체 표현 제안</b>
            <span className="font-mono text-[9.5px] text-[var(--ink-3)] border border-[var(--line-2)] p-[1px_6px]">권고안 · 확정 아님</span>
          </div>
          <div className="text-[13px] text-[var(--ink-2)] leading-1.6">
            {loading ? (
              <span className="text-[var(--ink-3)]">로딩 중...</span>
            ) : suggestions.length > 0 ? (
              suggestions.join(", ")
            ) : (
              <span className="text-[var(--ink-3)]">대체 표현 없음</span>
            )}
          </div>
        </div>
        <div className="flex gap-1.5">
          <button
            className={`font-sans text-[11.5px] p-[6px_11px] border cursor-pointer inline-flex items-center gap-1.25 transition-all duration-[120ms] ${
              act === "accept"
                ? "font-bold text-[var(--ink)] border-[var(--ink-2)] bg-[var(--nav-active-bg)]"
                : "font-semibold text-[var(--ink-3)] border-[var(--line-2)] bg-transparent hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
            }`}
            onClick={() => onAction(index, "accept")}
          >
            <Check size={13} weight="bold" />
            수용
          </button>
          <button
            className={`font-sans text-[11.5px] p-[6px_11px] border cursor-pointer inline-flex items-center gap-1.25 transition-all duration-[120ms] ${
              act === "exclude"
                ? "font-bold text-[var(--ink)] border-[var(--ink-3)] bg-[var(--surface-sub)]"
                : "font-semibold text-[var(--ink-3)] border-[var(--line-2)] bg-transparent hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
            }`}
            onClick={() => onAction(index, "exclude")}
          >
            <X size={13} weight="bold" />
            제외
          </button>
          <button
            className={`font-sans text-[11.5px] p-[6px_11px] border cursor-pointer inline-flex items-center gap-1.25 transition-all duration-[120ms] ${
              act === "hold"
                ? "font-bold text-[var(--ink)] border-[var(--ink-3)] bg-[var(--surface-sub)]"
                : "font-semibold text-[var(--ink-3)] border-[var(--line-2)] bg-transparent hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
            }`}
            onClick={() => onAction(index, "hold")}
          >
            <Clock size={13} weight="bold" />
            보류
          </button>
        </div>
      </div>
    </div>
  );
}

interface ReportClientProps {
  envelope: ReportEnvelope;
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
    
    let spanCls = "relative px-[1px] cursor-default ";
    if (isExcluded) {
      spanCls += "opacity-50 line-through ";
    }
    if (isViolation) {
      spanCls += "border-b-2 border-[var(--crit)] text-[var(--crit)] font-semibold";
    } else {
      spanCls += "border-b-2 border-[var(--ink-3)]";
    }
    
    out = out.replace(
      needle,
      `<span class="${spanCls}"><span class="absolute top-[-9px] left-[-2px] font-mono text-[9px] font-bold color-inherit">${it.badge}</span>${needle}</span>`
    );
  });
  return out;
}

export function ReportClient({ envelope }: ReportClientProps) {
  const [activeEnvelope, setActiveEnvelope] = useState<ReportEnvelope>(envelope);
  const [activeFixture, setActiveFixture] = useState<"image" | "text" | "unjudged" | string>(() => {
    if (envelope.result_id === "demo-text-id" || envelope.result_id === "text" || envelope.result_id === "demo-id-2") return "text";
    if (envelope.result_id === "demo-unjudged-id" || envelope.result_id === "unjudged" || envelope.result_id === "a3Fk9mdemo") return "unjudged";
    return "image";
  });
  const [loading, setLoading] = useState(false);
  const [actions, setActions] = useState<Record<number, "accept" | "exclude" | "hold" | null>>({});
  const [imageErrors, setImageErrors] = useState<Record<string, boolean>>({});
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

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

  const handleAction = (idx: number, act: "accept" | "exclude" | "hold") => {
    setActions((prev) => {
      const next = { ...prev };
      if (next[idx] === act) {
        next[idx] = null;
      } else {
        next[idx] = act;
      }
      return next;
    });
  };

  const handleFixtureChange = async (key: "image" | "text" | "unjudged") => {
    setLoading(true);
    try {
      const data = await getReport(key);
      setActiveEnvelope(data);
      setActiveFixture(key);
      setActions({});
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const d = activeEnvelope.report;

  let nViol = 0;
  let nReview = 0;

  d.findings.forEach((f, i) => {
    if (actions[i] === "exclude") return;
    if (f.flag === "위반") {
      nViol++;
    } else {
      nReview++;
    }
  });

  const typeCounts: Record<string, number> = {};
  d.findings.forEach((f, i) => {
    if (actions[i] === "exclude") return;
    typeCounts[f.violation_type] = (typeCounts[f.violation_type] || 0) + 1;
  });

  const isImageMode = d.findings.some((f) => f.location.tile) || d.unjudged.some((u) => u.location.tile);

  const findByOrder = d.findings
    .map((f, i) => ({ f, idx: i, num: 0 }))
    .sort((a, b) => a.f.location.order - b.f.location.order);
  findByOrder.forEach((item, index) => {
    item.num = index + 1;
  });

  const ujByOrder = [...d.unjudged].sort((a, b) => a.location.order - b.location.order);

  const hasInteracted = Object.keys(actions).length > 0;
  const acceptedIndices = hasInteracted
    ? Object.entries(actions)
        .filter(([_, act]) => act === "accept")
        .map(([i]) => i)
        .join(",")
    : d.findings
        .map((f, i) => (f.flag === "위반" ? i : -1))
        .filter((idx) => idx !== -1)
        .join(",");

  return (
    <>
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
        <span className="text-[var(--ink-2)]">
          <Link href="/" className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]">
            홈
          </Link>{" "}
          <span className="text-[var(--ink-3)]">›</span>{" "}
          {activeEnvelope.region === "US" ? (
            <>
              해외 수출 검증 <span className="text-[var(--ink-3)]">›</span> 미국{" "}
            </>
          ) : (
            <>국내 광고 검증</>
          )}
          <span className="text-[var(--ink-3)]">›</span> 리포트
        </span>
        <div className="ml-auto flex items-center gap-1.75 max-[900px]:ml-0 max-[900px]:w-full">
          <span className="text-[var(--ink-3)] text-[10px]">목업 전용 · 실제 화면엔 없음:</span>
          <div className="flex border border-[var(--line-2)]" id="fixtureSwitch" role="group" aria-label="fixture 전환">
            <button
              onClick={() => handleFixtureChange("image")}
              className={`font-mono text-[10.5px] p-[4px_9px] border-0 border-r border-[var(--line-2)] bg-transparent cursor-pointer transition-all duration-[120ms] last:border-r-0 ${
                activeFixture === "image" ? "bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold" : "text-[var(--ink-3)] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
              }`}
              disabled={loading}
            >
              이미지 예시
            </button>
            <button
              onClick={() => handleFixtureChange("text")}
              className={`font-mono text-[10.5px] p-[4px_9px] border-0 border-r border-[var(--line-2)] bg-transparent cursor-pointer transition-all duration-[120ms] last:border-r-0 ${
                activeFixture === "text" ? "bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold" : "text-[var(--ink-3)] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
              }`}
              disabled={loading}
            >
              텍스트 예시
            </button>
            <button
              onClick={() => handleFixtureChange("unjudged")}
              className={`font-mono text-[10.5px] p-[4px_9px] border-0 border-r border-[var(--line-2)] bg-transparent cursor-pointer transition-all duration-[120ms] last:border-r-0 ${
                activeFixture === "unjudged" ? "bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold" : "text-[var(--ink-3)] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
              }`}
              disabled={loading}
            >
              미판정 포함
            </button>
          </div>
        </div>
      </div>

      {/* 요약 상단바 */}
      <div className="p-[18px_20px] border-b border-[var(--line)]">
        <p className="m-[0_0_12px] text-[16px] font-bold text-[var(--ink)] tracking-[-0.2px]">
          <span className="text-[var(--crit)]">위반 <span className="font-mono">{nViol}</span>건</span>
          <span className="text-[var(--ink-3)] font-normal mx-0.75">·</span>
          검토필요 <span className="font-mono">{nReview}</span>건
          <span className="text-[var(--ink-3)] font-normal mx-0.75">·</span>
          미판정 <span className="font-mono">{d.unjudged.length}</span>건
        </p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(typeCounts).map(([type, count]) => {
            if (count === 0) return null;
            const label = TYPE_LABEL[type as keyof typeof TYPE_LABEL] || type;
            return (
              <span key={type} className="font-mono text-[11px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)] p-[3px_9px] inline-flex items-center gap-1.5">
                {label} <span className="text-[var(--ink-3)] font-mono">{count}</span>
              </span>
            );
          })}
          {Object.keys(typeCounts).length === 0 && (
            <span className="font-mono text-[11px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-3)] p-[3px_9px] inline-flex items-center gap-1.5">제외 처리 후 남은 지적 없음</span>
          )}
        </div>
      </div>

      {/* 2단 리포트 그리드 (뼈대 유지) */}
      <div className="grid grid-cols-[0.86fr_1.14fr] max-[900px]:grid-cols-1">
        <div className="p-[18px_20px_22px] border-r border-[var(--line)] max-[900px]:border-r-0 max-[900px]:border-b max-[900px]:border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
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
                              {findByOrder.map((o) => {
                                const loc = o.f.location;
                                if (typeof loc.y_start !== "number" || typeof loc.y_end !== "number") return null;
                                const isExcluded = actions[o.idx] === "exclude";
                                if (isExcluded) return null;

                                const topPct = (loc.y_start / srcH) * 100;
                                const heightPct = ((loc.y_end - loc.y_start) / srcH) * 100;
                                const isViolation = o.f.flag === "위반";
                                const isHovered = hoveredIndex === o.idx;

                                return (
                                  <div
                                    id={`highlight-box-${o.idx}`}
                                    key={`find-${o.idx}`}
                                    style={{
                                  position: "absolute",
                                  left: 0,
                                  right: 0,
                                  top: `${topPct}%`,
                                  height: `${heightPct}%`,
                                  border: isViolation
                                    ? `2px solid ${isHovered ? "var(--crit)" : "rgba(239, 68, 68, 0.4)"}`
                                    : `2px dashed ${isHovered ? "var(--ink)" : "rgba(100, 116, 139, 0.3)"}`,
                                  backgroundColor: isViolation
                                    ? (isHovered ? "rgba(239, 68, 68, 0.12)" : "rgba(239, 68, 68, 0.04)")
                                    : (isHovered ? "rgba(100, 116, 139, 0.12)" : "rgba(100, 116, 139, 0.02)"),
                                  pointerEvents: "auto",
                                  cursor: "pointer",
                                  transition: "all 0.15s ease-in-out",
                                }}
                                onMouseEnter={() => setHoveredIndex(o.idx)}
                                onMouseLeave={() => setHoveredIndex(null)}
                              >
                                <span
                                  style={{
                                    position: "absolute",
                                    left: "6px",
                                    top: "6px",
                                    width: "19px",
                                    height: "19px",
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontFamily: "monospace",
                                    fontSize: "10px",
                                    fontWeight: "bold",
                                    borderRadius: "50%",
                                    border: `1.5px solid ${isViolation ? "var(--crit)" : "var(--ink-3)"}`,
                                    color: isViolation ? "var(--crit)" : "var(--ink-3)",
                                    backgroundColor: "var(--surface)",
                                    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                                  }}
                                >
                                  {o.num}
                                </span>
                              </div>
                            );
                          })}

                              {ujByOrder.map((u, i) => {
                                const loc = u.location;
                                if (typeof loc.y_start !== "number" || typeof loc.y_end !== "number") return null;

                                const topPct = (loc.y_start / srcH) * 100;
                                const heightPct = ((loc.y_end - loc.y_start) / srcH) * 100;
                                const letter = String.fromCharCode(65 + i);

                                return (
                                  <div
                                    id={`highlight-box-uj-${i}`}
                                    key={`uj-${i}`}
                                    style={{
                                  position: "absolute",
                                  left: 0,
                                  right: 0,
                                  top: `${topPct}%`,
                                  height: `${heightPct}%`,
                                  border: "2px dashed rgba(100, 116, 139, 0.2)",
                                  backgroundColor: "rgba(100, 116, 139, 0.01)",
                                }}
                              >
                                <span
                                  style={{
                                    position: "absolute",
                                    right: "6px",
                                    top: "6px",
                                    width: "19px",
                                    height: "19px",
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
                                    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
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
                                    className={`relative flex items-center gap-2 p-[7px_9px] text-[12px] border transition-all duration-[120ms] ${
                                      isExcluded
                                        ? "opacity-50 border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]"
                                        : cls === "violation"
                                          ? `border-[var(--crit-bd)] ${isRowHovered ? "bg-[rgba(239,68,68,0.18)] border-[var(--crit)] scale-[1.01]" : "bg-[var(--crit-bg)]"} text-[var(--crit)]`
                                          : `border-[var(--line-2)] ${isRowHovered ? "bg-[var(--surface-sub)] border-[var(--ink-2)] scale-[1.01]" : "bg-[var(--surface)]"} text-[var(--ink-2)] border-solid`
                                    }`}
                                    onMouseEnter={() => setHoveredIndex(r.idx)}
                                    onMouseLeave={() => setHoveredIndex(null)}
                                    key={ri}
                                  >
                                    <span className={`shrink-0 w-[19px] h-[19px] inline-flex items-center justify-center font-mono text-[10.5px] font-bold rounded-full border-[1.5px] border-current ${
                                      isExcluded
                                        ? "text-[var(--ink-3)] border-[var(--ink-3)]"
                                        : cls === "violation"
                                          ? "text-[var(--crit)] border-[var(--crit)]"
                                          : "text-[var(--ink-3)] border-[var(--ink-3)]"
                                    }`}>{r.num}</span>
                                    <span className={`flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap ${
                                      cls === "violation" && !isExcluded ? "text-[var(--crit)]" : ""
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
        <div className="p-[18px_20px_22px]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">지적 카드</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]" />
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]"><span className="font-mono">{d.findings.length}</span>건</span>
          </div>
          <div className="flex flex-col gap-3">
            {findByOrder.map((o) => (
              <FindingCard
                key={o.idx}
                finding={o.f}
                index={o.idx}
                num={o.num}
                act={actions[o.idx] || null}
                onAction={handleAction}
                isHovered={hoveredIndex === o.idx}
                onHover={(h) => setHoveredIndex(h ? o.idx : null)}
                onCardClick={(idx) => scrollToBox(idx, false)}
              />
            ))}
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
      </div>

      {/* 하단 브릿지 */}
      <div className="p-[18px_20px] border-t border-[var(--line)] flex items-center justify-between gap-3.5 flex-wrap">
        <p className="m-0 text-[12px] text-[var(--ink-3)] max-w-[56ch]">지적된 표현을 검토했다면, 위험을 낮춘 수정 권고안을 반영해 상세페이지 초안을 만들 수 있어요.</p>
        <Link
          href={`/content?id=${activeEnvelope.result_id}&accepted=${acceptedIndices}`}
          className="font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-white border-[var(--brand)] dark:text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-ink)] dark:hover:bg-[#63e89f] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] no-underline"
        >
          이 수정안대로 상세페이지 만들기 <span className="font-mono">→</span>
        </Link>
      </div>

      <PageFooter basis={envelope.report.basis ?? null} snapshot />
    </>
  );
}
