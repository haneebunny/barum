"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Location } from "@/lib/api/schema";

const ZOOM_LEVELS = [100, 160, 220] as const;

/** 하이라이트 대상이 갖춰야 할 최소 계약. 국내 Finding(flag: 위반/검토필요)과
 * 미국 USPreflightFinding(flag 없음, category만 있음)이 둘 다 구조적으로 만족한다
 * (둘 다 이 필드들을 갖고 있어 타입 변환 없이 그대로 넘길 수 있다). flag가 있으면
 * 그걸로 심각도 색을 정하고(국내 기존 동작 그대로), 없으면 isCrit으로 정한다
 * (미국 - 호출부에서 category==="미국_미승인_성분"일 때만 true로 채워 넘긴다).
 */
interface HighlightSource {
  location: Location;
  span: string;
  sentence: string;
  flag?: "위반" | "검토필요";
  isCrit?: boolean;
}

interface UnjudgedLike {
  sentence: string;
  location: Location;
}

function isCritOf(item: HighlightSource): boolean {
  return item.flag ? item.flag === "위반" : !!item.isCrit;
}

interface FindByOrderItem {
  f: HighlightSource;
  idx: number;
  num: number;
}

interface ReportImageViewerProps {
  findByOrder: FindByOrderItem[];
  /** 미판정 개념이 없는 도메인(미국 등)은 생략하면 빈 배열로 취급한다. */
  ujByOrder?: UnjudgedLike[];
  /** null이면 실제 이미지를 아예 시도 안 한다(목업 result_id 등 - 백엔드에 이미지가 없음, 버그 아님). */
  imageUrl: string | null;
  imageErrorGlobal: boolean;
  onImageError: () => void;
  /** accept/exclude 개념이 없는 도메인은 생략하면 빈 객체로 취급한다(전부 표시). */
  actions?: Record<number, "accept" | "exclude" | null>;
  hoveredIndex: number | null;
  onHoverChange: (idx: number | null) => void;
}

/** 원문 하이라이트 패널 본문 (실제 이미지 + 좌표 오버레이, 줌/미니맵) */
export function ReportImageViewer({
  findByOrder,
  ujByOrder = [],
  imageUrl,
  imageErrorGlobal,
  onImageError,
  actions = {},
  hoveredIndex,
  onHoverChange,
}: ReportImageViewerProps) {
  const sampleLoc = findByOrder[0]?.f.location || ujByOrder[0]?.location;
  const srcW = sampleLoc?.source_w;
  const srcH = sampleLoc?.source_h;
  const hasCoords = typeof srcW === "number" && typeof srcH === "number" && srcW > 0 && srcH > 0;
  const showRealImage = hasCoords && !!imageUrl && !imageErrorGlobal;

  if (!showRealImage || !imageUrl) {
    return (
      <div className="p-8 text-center text-[var(--ink-3)] text-[12.5px] border border-[var(--line-2)] bg-[var(--surface-sub)] font-mono">
        원본 이미지를 불러올 수 없습니다.
      </div>
    );
  }

  return (
    <ZoomableImage
      srcW={srcW!}
      srcH={srcH!}
      imageUrl={imageUrl}
      onImageError={onImageError}
      findByOrder={findByOrder}
      ujByOrder={ujByOrder}
      actions={actions}
      hoveredIndex={hoveredIndex}
      onHoverChange={onHoverChange}
    />
  );
}

interface ZoomableImageProps {
  srcW: number;
  srcH: number;
  imageUrl: string;
  onImageError: () => void;
  findByOrder: FindByOrderItem[];
  ujByOrder: UnjudgedLike[];
  actions: Record<number, "accept" | "exclude" | null>;
  hoveredIndex: number | null;
  onHoverChange: (idx: number | null) => void;
}

const MINIMAP_W = 40;

function ZoomableImage({
  srcW,
  srcH,
  imageUrl,
  onImageError,
  findByOrder,
  ujByOrder,
  actions,
  hoveredIndex,
  onHoverChange,
}: ZoomableImageProps) {
  const [zoomIndex, setZoomIndex] = useState(0);
  const [scroll, setScroll] = useState({ top: 0, left: 0 });
  const [dims, setDims] = useState({ viewerW: 0, viewerH: 0, contentW: 0, contentH: 0 });
  const viewerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const pendingCenterFrac = useRef<{ x: number; y: number } | null>(null);

  const zoomPct = ZOOM_LEVELS[zoomIndex];

  const recomputeDims = () => {
    const viewer = viewerRef.current;
    const content = contentRef.current;
    if (!viewer || !content) return;
    setDims({
      viewerW: viewer.clientWidth,
      viewerH: viewer.clientHeight,
      contentW: content.offsetWidth,
      contentH: content.offsetHeight,
    });
  };

  useLayoutEffect(() => {
    const viewer = viewerRef.current;
    const content = contentRef.current;
    if (!viewer || !content) return;

    const frac = pendingCenterFrac.current;
    if (frac) {
      viewer.scrollLeft = Math.max(0, frac.x * content.offsetWidth - viewer.clientWidth / 2);
      viewer.scrollTop = Math.max(0, frac.y * content.offsetHeight - viewer.clientHeight / 2);
      pendingCenterFrac.current = null;
    }
    recomputeDims();
  }, [zoomIndex]);

  useEffect(() => {
    recomputeDims();
  }, []);

  // Z 단축키: 클릭 줌과 같은 동작(다음 배율로 순환), 클릭 지점 대신 현재 뷰포트
  // 중앙을 기준으로 재중앙. 입력 필드에 타이핑 중이면 안 먹게 막는다(팀장 지시,
  // 2026-08-23 - "Z 누르면 확대되는 단축키").
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "z") return;
      const active = document.activeElement;
      const tag = active?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || (active as HTMLElement)?.isContentEditable) return;

      const viewer = viewerRef.current;
      const content = contentRef.current;
      if (!viewer || !content) return;
      const centerX = viewer.scrollLeft + viewer.clientWidth / 2;
      const centerY = viewer.scrollTop + viewer.clientHeight / 2;
      pendingCenterFrac.current = {
        x: centerX / content.offsetWidth,
        y: centerY / content.offsetHeight,
      };
      setZoomIndex((prev) => (prev + 1) % ZOOM_LEVELS.length);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const handleContentClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const content = contentRef.current;
    if (!content) return;
    const rect = content.getBoundingClientRect();
    pendingCenterFrac.current = {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
    setZoomIndex((prev) => (prev + 1) % ZOOM_LEVELS.length);
  };

  const handleScroll = () => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    setScroll({ top: viewer.scrollTop, left: viewer.scrollLeft });
  };

  const minimapH = MINIMAP_W * (srcH / srcW);
  const rectStyle = dims.contentW > 0 && dims.contentH > 0
    ? {
      top: `${(scroll.top / dims.contentH) * minimapH}px`,
      left: `${(scroll.left / dims.contentW) * MINIMAP_W}px`,
      height: `${Math.min(minimapH, (dims.viewerH / dims.contentH) * minimapH)}px`,
      width: `${Math.min(MINIMAP_W, (dims.viewerW / dims.contentW) * MINIMAP_W)}px`,
    }
    : null;

  return (
    <div className="h-full border border-[var(--line-2)] p-3 bg-[var(--surface-sub)] flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-[var(--ink-3)]">
          원본 광고 검증 이미지 ({srcW}x{srcH} px) · {zoomPct}%
        </span>
        <button
          type="button"
          onClick={() => {
            // ref로 직접 스크롤을 0으로 만든다. zoomIndex가 이미 0이면(예: 100%인
            // 채로 아래로 스크롤만 내려간 상태) setZoomIndex(0)는 값이 안 바뀌어서
            // 리렌더도, 그 리렌더에 의존하는 이펙트도 안 돈다 - 스크롤 리셋을 이펙트에
            // 맡기면 이 케이스에서 조용히 안 먹는다(실측으로 확인, 2026-08-23).
            pendingCenterFrac.current = null;
            setZoomIndex(0);
            if (viewerRef.current) {
              viewerRef.current.scrollTop = 0;
              viewerRef.current.scrollLeft = 0;
            }
          }}
          className="font-mono text-[10.5px] px-2 py-1 border border-[var(--line-2)] rounded-sm bg-transparent text-[var(--ink-2)] hover:bg-[var(--nav-hover)] hover:border-[var(--ink-3)] cursor-pointer"
        >
          맞춤
        </button>
      </div>

      <div
        ref={viewerRef}
        onScroll={handleScroll}
        className="relative w-full h-[78vh] min-h-[580px] max-h-[920px] overflow-auto"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <div
          ref={contentRef}
          onClick={handleContentClick}
          className="relative"
          style={{ width: `${zoomPct}%`, aspectRatio: `${srcW} / ${srcH}`, cursor: "zoom-in" }}
        >
          <img
            src={imageUrl}
            alt="원본 광고"
            onError={onImageError}
            draggable={false}
            style={{ width: "100%", height: "100%", display: "block", pointerEvents: "none" }}
          />

          <div className="absolute inset-0 z-10 pointer-events-none">
            {(() => {
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
                if (actions[o.idx] === "exclude") return null;

                const hasX = typeof loc.x_start === "number" && typeof loc.x_end === "number" && loc.x_end > loc.x_start;
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
                const isViolation = isCritOf(o.f);
                const isHovered = hoveredIndex === o.idx;
                const badgeOffset = (itemSubIndices[o.idx] || 0) * 22;

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
                    onMouseEnter={() => onHoverChange(o.idx)}
                    onMouseLeave={() => onHoverChange(null)}
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

        {/* 미니맵: 뷰어 우측 하단 고정(뷰어 기준, 페이지 기준 아님 - 세로로 아주 긴
            이미지라 페이지 스크롤과 뷰어 내부 스크롤이 다르다). 같은 이미지를 작게
            띄우고 현재 보이는 영역만 사각형으로 표시(팀장 지시, 2026-08-23). */}
        <div
          className="sticky float-right bottom-2 mr-2 border border-[var(--line-2)] bg-[var(--surface-sub)] shadow-[0_1px_4px_rgba(0,0,0,0.25)]"
          style={{ width: MINIMAP_W, height: minimapH, pointerEvents: "none" }}
        >
          <img
            src={imageUrl}
            alt=""
            style={{ width: "100%", height: "100%", display: "block", opacity: 0.9 }}
          />
          {rectStyle && (
            <div
              className="absolute border-2 border-[var(--brand)]"
              style={{ ...rectStyle, backgroundColor: "rgba(255,255,255,0.12)" }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
