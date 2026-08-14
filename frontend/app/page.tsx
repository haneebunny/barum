"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";

// ── Intersection Observer를 통한 reveal 훅 ──────────────────────────
function useReveal(threshold = 0.15) {
  const [revealed, setRevealed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !ref.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setRevealed(true);
          observer.unobserve(entry.target);
        }
      },
      {
        rootMargin: `0px 0px -${threshold * 100}% 0px`,
        threshold: 0,
      }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, revealed] as const;
}

// ── 데이터 (목업 DC script 원본 그대로, em-dash 제거) ──────────────────────────
const rounds = [
  { tag: "Q1", label: "기미 크림 상세페이지", text: '"붙이기만 하면 기미가 사라져요"', ok: false, verdict: "위반 · 의약품 오인", law: "화장품법 제13조 ①1호", why: "'사라진다'는 치료 효능을 말하는 표현이에요. 화장품 광고에서 가장 많이 적발되는 유형입니다.", fixLabel: "권고안", fix: '"멜라닌 생성 억제로 미백에 도움" (미백 기능성 원료 함유 시)' },
  { tag: "Q2", label: "주름 크림 광고 문구", text: '"주름개선 기능성화장품 · 아데노신 0.04% 함유"', ok: true, verdict: "통과 · 표방 가능", law: "기능성 심사 범위", why: "심사받은 기능성 원료를 기준 함량으로 표기했어요 - 이런 문구는 써도 됩니다.", fixLabel: "참고", fix: "'통과'도 100% 안전 보장은 아니에요. 최종 판단은 사람이 해요." },
  { tag: "Q3", label: "진정 앰플 SNS 광고", text: '"민감 피부에도 자극 전혀 없는 순한 포뮬러"', ok: false, verdict: "검토필요 · 입증 자료 필요", law: "표시광고 실증제", why: "'전혀 없는'처럼 단정하는 표현은 요구가 오면 15일 안에 입증 자료를 내야 해요. 자료가 없다면 위험합니다.", fixLabel: "권고안", fix: '"피부 자극 테스트 완료" (시험기관 · 조건 명시)' },
];

export default function LandingPage() {
  // ── prefers-reduced-motion 체크 ──
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);
    const listener = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener("change", listener);
    return () => mediaQuery.removeEventListener("change", listener);
  }, []);

  // ── 헤더 compact 상태 (80px 초과 시 compact, 60px 미만 시 해제) ──
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const sy = window.scrollY;
          setCompact(prev => {
            if (sy > 80) return true;
            if (sy < 60) return false;
            return prev;
          });
          ticking = false;
        });
        ticking = true;
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // ── 스크롤 진행률 (0 ~ 1) ──
  const [scrollProgress, setScrollProgress] = useState(0);
  useEffect(() => {
    if (typeof window === "undefined") return;
    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const scrollHeight = document.documentElement.scrollHeight;
          const innerHeight = window.innerHeight;
          const total = scrollHeight - innerHeight;
          const p = total > 0 ? Math.max(0, Math.min(1, window.scrollY / total)) : 0;
          setScrollProgress(p);
          ticking = false;
        });
        ticking = true;
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // ── 섹션 등장 reveal 훅들 ──
  const [featuresRef, featuresRevealedRaw] = useReveal(0.15);
  const [reportRef, reportRevealedRaw] = useReveal(0.15);
  const [exportSectionRef, exportSectionRevealedRaw] = useReveal(0.15);
  const [exportObserverRef, exportActiveRaw] = useReveal(0.40);
  const [pricingRef, pricingRevealedRaw] = useReveal(0.15);
  const [faqRef, faqRevealedRaw] = useReveal(0.15);
  const [ctaRef, ctaRevealedRaw] = useReveal(0.15);

  const featuresRevealed = prefersReducedMotion ? true : featuresRevealedRaw;
  const reportRevealed = prefersReducedMotion ? true : reportRevealedRaw;
  const exportSectionRevealed = prefersReducedMotion ? true : exportSectionRevealedRaw;
  const exportActive = prefersReducedMotion ? true : exportActiveRaw;
  const pricingRevealed = prefersReducedMotion ? true : pricingRevealedRaw;
  const faqRevealed = prefersReducedMotion ? true : faqRevealedRaw;
  const ctaRevealed = prefersReducedMotion ? true : ctaRevealedRaw;

  // ── 통계 카운트업 상태 및 로직 ──
  const statsRef = useRef<HTMLDivElement>(null);
  const [statsTriggered, setStatsTriggered] = useState(false);
  const [stat1, setStat1] = useState(0);
  const [stat3, setStat3] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined" || !statsRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setStatsTriggered(true);
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -30% 0px", threshold: 0 }
    );
    observer.observe(statsRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!statsTriggered) return;
    if (prefersReducedMotion) {
      setStat1(2680);
      setStat3(15);
      return;
    }
    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

    let start1: number | null = null;
    const duration1 = 900;
    let frameId1: number;
    const animate1 = (timestamp: number) => {
      if (!start1) start1 = timestamp;
      const progress = Math.min((timestamp - start1) / duration1, 1);
      const eased = easeOutCubic(progress);
      setStat1(Math.floor(eased * 2680));
      if (progress < 1) {
        frameId1 = requestAnimationFrame(animate1);
      }
    };
    frameId1 = requestAnimationFrame(animate1);

    let start3: number | null = null;
    const duration3 = 600;
    let frameId3: number;
    const animate3 = (timestamp: number) => {
      if (!start3) start3 = timestamp;
      const progress = Math.min((timestamp - start3) / duration3, 1);
      const eased = easeOutCubic(progress);
      setStat3(Math.floor(eased * 15));
      if (progress < 1) {
        frameId3 = requestAnimationFrame(animate3);
      }
    };
    frameId3 = requestAnimationFrame(animate3);

    return () => {
      cancelAnimationFrame(frameId1);
      cancelAnimationFrame(frameId3);
    };
  }, [statsTriggered, prefersReducedMotion]);

  const displayStat1 = prefersReducedMotion ? "2,680" : (statsTriggered ? stat1.toLocaleString() : "0");
  const displayStat3 = prefersReducedMotion ? "15" : (statsTriggered ? stat3.toString() : "0");

  // ── 퀴즈 상태 ──
  const [qi, setQi] = useState(0);
  const [hqCi, setHqCi] = useState(0);
  const [picked, setPicked] = useState<"o" | "x" | null>(null);
  const [score, setScore] = useState(0);
  const [fin, setFin] = useState(false);
  // ── EXPORT 애드온 토글 상태 ──
  const [exportOpen, setExportOpen] = useState(false);

  const rd = rounds[qi];
  const correct = picked !== null && ((picked === "o") === rd.ok);
  const qNum = (fin ? 3 : qi + 1) + " / 3";
  const nextLabel = qi < 2 ? "다음 문구 →" : "내 점수 보기 →";
  const scoreMsg = score === 3 ? "완벽해요. 그래도 상세페이지 문구 수십 개를 매번 눈으로 볼 순 없죠." : score >= 2 ? "좋은 감이에요. 하지만 실제 상세페이지엔 문구가 수십 개입니다." : "괜찮아요 - 그래서 바름이 있어요. 감 대신 조항으로 확인하세요.";

  // 퀴즈 문구 타이핑 (목업 tick() 로직)
  useEffect(() => {
    if (fin || picked !== null || hqCi >= rd.text.length) return;
    const t = setInterval(() => setHqCi(p => p + 1), 46);
    return () => clearInterval(t);
  }, [fin, picked, hqCi, rd]);

  const pick = (v: "o" | "x") => {
    if (picked !== null || fin) return;
    setPicked(v);
    if ((v === "o") === rd.ok) setScore(p => p + 1);
    setHqCi(rd.text.length);
  };
  const nextRound = () => {
    if (qi < 2) { setQi(p => p + 1); setPicked(null); setHqCi(0); }
    else setFin(true);
  };
  const retry = () => { setQi(0); setPicked(null); setScore(0); setFin(false); setHqCi(0); };

  return (
    <div className="flex flex-col bg-[var(--surface)] text-[var(--ink)]">

      {/* ── 랜딩 전용 네비 (목업 헤더 우측 nav 파트 + 테마 토글 탑재) ── */}
      <div 
        className="flex items-center gap-6 px-4 border-b bg-[var(--surface-sub)] text-[13.5px] font-semibold sticky top-0 z-50 transition-all relative"
        style={{
          paddingTop: compact ? "8px" : "12px",
          paddingBottom: compact ? "8px" : "12px",
          borderBottomColor: compact ? "var(--ink-3)" : "var(--line-2)",
          transition: prefersReducedMotion ? "none" : "padding 180ms ease-in-out, border-color 180ms ease-in-out"
        }}
      >
        {/* Logo Mark & Wordmark */}
        <div className="flex items-center gap-3">
          <svg className="w-[30px] h-[30px] shrink-0 block" viewBox="0 0 170 170" fill="none" role="img" aria-label="바름">
            <circle cx="101.542" cy="97.5538" r="42.3692" fill="#95DDB7" />
            <circle cx="67.8038" cy="72.4461" r="42.3692" fill="#00813E" fillOpacity="0.5" />
          </svg>
          <span className="text-[var(--ink)] inline-flex items-center" aria-label="바름">
            <svg
              className="h-[19px] w-auto block"
              viewBox="2.6 -86.2 176.8 98.2"
              role="img"
              aria-label="바름"
            >
              <path
                fill="currentColor"
                stroke="currentColor"
                strokeWidth={3.5}
                strokeLinejoin="round"
                paintOrder="stroke"
                d="M77.10 1.20Q77.10 2.50 77.95 3.30Q78.80 4.10 81.40 5L81.40 5L72.10 9.80Q71.70 10 71.30 10L71.30 10Q70.80 10 70.40 9.50L70.40 9.50Q69.80 8.60 69.45 7.45Q69.10 6.30 69.10 4.30L69.10 4.30L69.10-76.30Q69.10-77.60 68.25-78.40Q67.40-79.20 64.80-80.10L64.80-80.10L74.10-84Q74.50-84.20 74.90-84.20L74.90-84.20Q77.10-84.20 77.10-78.20L77.10-78.20L77.10-40.50L91.50-40.50L89.90-35L77.10-35L77.10 1.20ZM8.40-65.30Q8.40-66.80 7.60-67.65Q6.80-68.50 4.60-69.50L4.60-69.50L13.40-73Q14.80-73.60 15.60-72.15Q16.40-70.70 16.40-67.50L16.40-67.50L16.40-48.40L43.40-48.40L43.40-67.70Q43.40-69.20 42.60-70.05Q41.80-70.90 39.60-71.90L39.60-71.90L48.10-75.40Q49.50-76 50.30-74.55Q51.10-73.10 51.10-69.90L51.10-69.90L51.10-15.70Q54.40-16 57.60-16.30L57.60-16.30L55.70-9.90L29.60-9.90Q22.70-9.90 17-8.80Q11.30-7.70 7.40-5.70L7.40-5.70Q7.80-7.50 8.10-10.35Q8.40-13.20 8.40-15.90L8.40-15.90L8.40-65.30ZM16.40-12.70Q19.20-14.30 22.40-15Q25.60-15.70 30.60-15.70L30.60-15.70L43.40-15.70L43.40-42.80L16.40-42.80L16.40-12.70ZM105.60-75L107.60-80.30L166.40-80.30Q165.50-76.30 165.50-73.50L165.50-73.50L165.50-60.20L115.20-60.20L115.20-49.10Q117.70-49.80 120.95-50.05Q124.20-50.30 129.40-50.30L129.40-50.30L167.80-50.30L166.20-45.20L128.50-45.20Q120.90-45.20 116.25-44.75Q111.60-44.30 106.60-43.20L106.60-43.20Q107.20-46.40 107.20-51L107.20-51L107.20-58.80Q107.20-62.20 105.60-65.20L105.60-65.20L157.50-65.20L157.50-75L105.60-75ZM114.60 3.30Q119.60 2.70 128.80 2.70L128.80 2.70L157.80 2.70L157.80-14L114.60-14L114.60 3.30ZM101.90-29.20Q98.70-29.20 97.25-29.85Q95.80-30.50 95.80-31.50L95.80-31.50Q95.80-32 96.10-32.30L96.10-32.30L100.50-37.80Q101.50-36 102.55-35.40Q103.60-34.80 105.20-34.80L105.20-34.80L177.40-34.80L175.80-29.20L101.90-29.20ZM105.40-19L166.70-19Q165.80-16 165.80-12.20L165.80-12.20L165.80 2.60Q168.40 2.40 170.20 2L170.20 2L168.30 8L127.80 8Q114.20 8 105.50 9.90L105.50 9.90Q106 8.60 106.30 6.35Q106.60 4.10 106.60 2L106.60 2L106.60-11Q106.60-15.90 105.40-19L105.40-19Z"
              />
            </svg>
          </span>
          <span 
            className="font-mono text-[11px] text-[var(--ink-3)] border border-[var(--line-2)] px-[7px] py-[2px] whitespace-nowrap"
            style={{
              opacity: compact ? 0 : 1,
              transform: compact ? "scale(0.9)" : "scale(1)",
              transformOrigin: "left center",
              transition: prefersReducedMotion ? "none" : "opacity 180ms ease-in-out, transform 180ms ease-in-out"
            }}
          >
            올리기 전 광고 검사
          </span>
        </div>

        {/* Right Nav menu */}
        <div className="ml-auto flex items-center gap-6">
          <a href="#features" className="text-[var(--ink-2)] no-underline hover:text-[var(--ink)]">기능</a>
          <a href="#export" className="text-[var(--ink-2)] no-underline hover:text-[var(--ink)]">수출 검사</a>
          <a href="#pricing" className="text-[var(--ink-2)] no-underline hover:text-[var(--ink)]">요금제</a>
          <a href="#faq" className="text-[var(--ink-2)] no-underline hover:text-[var(--ink)]">FAQ</a>
          
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <Link
              href="/home"
              className="inline-flex items-center gap-2 no-underline text-[var(--on-brand)] bg-[var(--brand)] hover:bg-[var(--brand-ink)] cursor-pointer p-[10px_18px] text-[13px] font-bold"
            >
              무료 검사 시작 <span className="font-mono">→</span>
            </Link>
          </div>
        </div>

        {/* ── 스크롤 진행률 라인 (헤더 내부 하단 절대 배치) ── */}
        <div 
          style={{
            position: "absolute",
            bottom: "-1px",
            left: 0,
            width: "100%",
            height: "2px",
            backgroundColor: "var(--brand)",
            transform: `scaleX(${scrollProgress})`,
            transformOrigin: "left",
            transition: prefersReducedMotion ? "none" : "transform 60ms linear",
            pointerEvents: "none"
          }}
        />

        {/* ── 스크롤 진행률 라벨 (헤더 내부 하단 우측 배치) ── */}
        <div 
          style={{
            position: "absolute",
            right: "16px",
            top: "100%",
            marginTop: "6px",
            fontFamily: "var(--mono)",
            fontSize: "11px",
            color: scrollProgress >= 1 ? "var(--brand-ink)" : "var(--ink-3)",
            fontWeight: 600,
            backgroundColor: "var(--surface)",
            padding: "2px 6px",
            border: `1px solid ${scrollProgress >= 1 ? "var(--brand-ink)" : "var(--line-2)"}`,
            lineHeight: "1",
            opacity: scrollProgress > 0 ? 1 : 0,
            transition: prefersReducedMotion ? "none" : "opacity 200ms ease-out",
            pointerEvents: "auto"
          }}
        >
          {scrollProgress >= 1 ? "검사 완료" : `검사 ${Math.round(scrollProgress * 100)}%`}
        </div>
      </div>

      {/* ── 히어로 ── */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_560px] border-b border-[var(--line)] items-stretch">

        {/* 좌 */}
        <div className="border-r border-[var(--line)] p-[62px_44px_56px]">
          <div className="flex items-center gap-2 mb-[18px] text-[11.5px] font-mono tracking-[0.4px] text-[var(--brand-ink)]">
            <span className="inline-block w-[7px] h-[7px] bg-[var(--brand)]" />
            바름 · 올리기 전에 검사하는 광고 컴플라이언스
          </div>
          <h1 className="m-0 mb-[18px] text-[var(--ink)] text-[52px] font-extrabold leading-[1.22] tracking-[-1.4px] break-keep">
            걸리고 나서 알면,<br />이미 늦었으니까
            <span className="inline-block w-[0.14em] h-[0.95em] ml-2 align-[-4px] bg-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]" />
          </h1>
          <p className="m-0 mb-[30px] text-[var(--ink-3)] text-[16px] leading-[1.7] max-w-[44ch] break-keep">
            광고를 올리기 전 3분. 위반 위험이 있는 문구를 찾아 어떤 조항에 걸리는지 보여드리고, 안전하게 고친 문구까지 제안해 드려요.
          </p>
          <div className="flex gap-[10px] items-center mb-[24px]">
            <Link
              href="/home"
              className="inline-flex items-center gap-2 no-underline text-[var(--on-brand)] bg-[var(--brand)] hover:bg-[var(--brand-ink)] cursor-pointer p-[13px_22px] text-[14.5px] font-bold"
            >
              무료로 검사 시작 <span className="font-mono">→</span>
            </Link>
            <span
              className="inline-flex border border-[var(--line-2)] text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-active-bg)] hover:text-[var(--ink)] p-[13px_20px] text-[14px] font-semibold"
            >
              리포트 예시 보기
            </span>
          </div>
          <div className="text-[var(--ink-3)] font-mono text-[11px] leading-[1.8]">
            가입 없이 월 3건 무료 · 신용카드 불필요<br />결과는 참고 정보이며 법적 자문이 아닙니다
          </div>
        </div>

        {/* 우: 퀴즈 패널 */}
        <div className="bg-[var(--surface-sub)] flex flex-col">
          {/* 상단 바 */}
          <div className="flex items-center gap-3 border-b border-[var(--line)] text-[var(--ink-3)] px-4 py-[9px] font-mono text-[11px]">
            <span>이 문구, 올려도 될까요?</span>
            <span className="ml-auto text-[var(--brand-ink)]">감으로 맞혀보세요 · {qNum}</span>
          </div>

          {/* 본문 */}
          <div className="flex-1 flex flex-col p-[20px_20px_16px]">
            {/* 태그 */}
            <div className="flex items-center gap-2 mb-[8px] text-[var(--ink-3)] font-mono text-[10.5px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-bold px-[6px] py-[1px]">{rd.tag}</span>
              {rd.label}
            </div>
            {/* 문구 박스 */}
            <div className="text-[var(--ink)] bg-[var(--surface)] border border-[var(--line-2)] min-h-[76px] p-[13px_14px] text-[18px] font-semibold leading-[1.55] break-keep">
              {rd.text.slice(0, hqCi)}
              <span className="inline-block w-[0.14em] h-[1em] ml-[2px] align-[-2px] bg-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]" />
            </div>

            {/* O/X 버튼 */}
            {!fin && picked === null && (
              <>
                <div className="flex gap-[9px] mt-[12px]">
                  <span
                    onClick={() => pick("o")}
                    className="flex-1 flex items-center justify-center gap-[9px] border border-[var(--line-2)] bg-[var(--surface)] cursor-pointer text-[var(--ink-2)] hover:border-[var(--brand)] hover:text-[var(--brand-ink)] py-3.5 text-[14px] font-bold"
                  >
                    <span className="text-[var(--brand-ink)] text-[17px] font-bold font-mono">O</span>
                    올려도 된다
                  </span>
                  <span
                    onClick={() => pick("x")}
                    className="flex-1 flex items-center justify-center gap-[9px] border border-[var(--line-2)] bg-[var(--surface)] cursor-pointer text-[var(--ink-2)] hover:border-[var(--crit)] hover:text-[var(--crit)] py-3.5 text-[14px] font-bold"
                  >
                    <span className="text-[var(--crit)] text-[17px] font-bold font-mono">X</span>
                    위험하다
                  </span>
                </div>
                <div className="mt-[12px] text-[var(--ink-3)] font-mono text-[11px]">▸ 실제 적발 사례에서 가져온 유형입니다</div>
              </>
            )}

            {/* 결과 */}
            {!fin && picked !== null && (
              <div className="mt-[12px] animate-[popIn_0.25s_both]">
                <div className="mb-[9px] text-[var(--ink)] text-[15px] font-extrabold">
                  {correct ? "정확해요 - 사람 눈으로도 잡았네요." : "함정이었어요. 실무에선 이렇게 놓칩니다."}
                </div>
                <div className="mb-[9px]">
                  {!rd.ok ? (
                    <span className="inline-flex items-center gap-[6px] text-[var(--crit)] border border-[var(--crit-bd)] bg-[var(--crit-bg)] mr-[7px] text-[11.5px] font-semibold px-[9px] py-[3px]">
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square"><path d="M12 3 2 20h20L12 3z" /><path d="M12 10v4M12 17v.5" /></svg>
                      {rd.verdict}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-[6px] text-[var(--ink-2)] border border-[var(--line-2)] mr-[7px] text-[11.5px] font-semibold px-[9px] py-[3px]">
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square"><path d="M4 12l5 5L20 6" /></svg>
                      {rd.verdict}
                    </span>
                  )}
                  <span className="inline-flex text-[var(--ink-3)] border border-[var(--line-2)] font-mono text-[10.5px] font-semibold px-2 py-[3px]">{rd.law}</span>
                </div>
                <div className="text-[var(--ink-2)] text-[13px] leading-[1.65] break-keep">{rd.why}</div>
                <div className="flex gap-[8px] items-start mt-[10px] bg-[var(--surface)] border border-[var(--line-2)] p-[9px_11px] text-[12.5px] leading-[1.6] text-[var(--ink)] break-keep">
                  <span className="whitespace-nowrap text-[var(--brand-ink)] font-mono text-[10px] font-bold pt-[3px]">{rd.fixLabel}</span>
                  <span>{rd.fix}</span>
                </div>
                <span
                  onClick={nextRound}
                  className="flex items-center justify-center gap-[7px] mt-[12px] bg-[var(--brand)] text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-ink)] py-3 text-[13.5px] font-bold"
                >
                  {nextLabel}
                </span>
              </div>
            )}

            {/* 완료 화면 */}
            {fin && (
              <div className="mt-[12px] text-center p-[10px_6px_2px] animate-[popIn_0.25s_both]">
                <div className="text-[var(--ink-3)] mb-[8px] font-mono text-[11px] font-bold">당신의 감</div>
                <div className="text-[var(--ink)] mb-[8px] font-mono text-[44px] font-extrabold">{score} / 3</div>
                <div className="text-[var(--ink-2)] mb-[16px] text-[13.5px] leading-[1.65] break-keep">{scoreMsg}</div>
                <Link
                  href="/home"
                  className="flex items-center justify-center gap-[7px] bg-[var(--brand)] text-[var(--on-brand)] no-underline hover:bg-[var(--brand-ink)] py-3.5 text-[14px] font-bold"
                >
                  내 광고 문구 검사하기 - 무료 <span className="font-mono">→</span>
                </Link>
                <span
                  onClick={retry}
                  className="inline-block mt-[10px] text-[var(--ink-3)] cursor-pointer border-b border-[var(--line-2)] hover:text-[var(--ink)] text-[12px] font-semibold"
                >
                  다시 풀기
                </span>
              </div>
            )}
          </div>

          {/* 하단 상태바 */}
          <div className="flex border-t border-[var(--line-2)] font-mono text-[11px]">
            <span className="bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold p-[7px_13px]">바름</span>
            <span className="border-r border-[var(--line)] text-[var(--ink-3)] p-[7px_13px]">퀴즈 {qNum}</span>
            <span className="text-[var(--ink-3)] p-[7px_13px]">맞힌 수 {score}개</span>
            <span className="ml-auto text-[var(--ink-3)] p-[7px_13px]">^N 새 검사</span>
          </div>
        </div>
      </div>

      {/* ── 경고 배너 ── */}
      <div className="flex items-center gap-[10px] border-b border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)] p-[10px_20px] text-[13px]">
        <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square"><path d="M12 3 2 20h20L12 3z" /><path d="M12 10v4M12 17v.5" /></svg>
        <span><b className="font-bold">작년 한 해 화장품 부당광고 적발 2,680건.</b> 게시 전에 걸러주는 장치는 없습니다. 확인 책임은 브랜드에게 있습니다.</span>
      </div>

      {/* ── 통계 그리드 ── */}
      <div ref={statsRef} className="grid grid-cols-4 border-b border-[var(--line)] bg-[var(--surface-sub)]">
        {[
          { val: displayStat1, unit: "건", sub: "2024년 적발 · 3년 새 +40%", red: false },
          { val: "2~6", unit: "개월", sub: "위반 시 광고업무정지", red: true },
          { val: displayStat3, unit: "일", sub: "입증 자료 제출 기한", red: false },
          { val: "0", unit: "개", sub: "게시 전 의무 심의 절차", red: false },
        ].map((s, i) => (
          <div key={i} className={`p-[20px_24px] ${i < 3 ? "border-r border-[var(--line)]" : ""}`}>
            <div className={`text-[27px] font-mono font-bold [font-variant-numeric:tabular-nums] ${s.red ? "text-[var(--crit)]" : "text-[var(--ink)]"}`}>
              {s.val}<span className="text-[12px] font-semibold text-[var(--ink-3)]"> {s.unit}</span>
            </div>
            <div className="mt-[3px] text-[11.5px] leading-[1.5] text-[var(--ink-3)]">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* ── 기능 섹션 ── */}
      <div 
        id="features" 
        ref={featuresRef} 
        className="border-b border-[var(--line)] p-[58px_44px_54px]"
        style={{
          opacity: featuresRevealed ? 1 : 0,
          transform: featuresRevealed ? "none" : "translateY(12px)",
          transition: prefersReducedMotion ? "none" : "opacity 320ms cubic-bezier(.2,.7,.2,1), transform 320ms cubic-bezier(.2,.7,.2,1)"
        }}
      >
        <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11.5px] font-bold tracking-[0.4px]">기능</div>
        <h2 className="m-0 mb-[10px] text-[var(--ink)] text-[34px] font-extrabold leading-[1.3] tracking-[-1px] break-keep">
          찾아내는 데서 끝내지 않아요.<br />고치고, 새로 만드는 것까지.
        </h2>
        <p className="m-0 mb-[30px] text-[var(--ink-3)] text-[15px] leading-[1.7] max-w-[60ch] break-keep">
          규제가 뭔지 알려주는 서비스는 많아요. 바름은 &lsquo;내 광고가 걸리는가&rsquo;에 답합니다.
        </p>
        <div className="grid grid-cols-4 gap-3">
          {/* 01 찾고 */}
          <div 
            className="bg-[var(--surface)] border border-[var(--line-2)] p-[20px_18px]"
            style={{
              clipPath: featuresRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 0ms"
            }}
          >
            <div
              style={{
                opacity: featuresRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 220ms"
              }}
            >
              <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11px] font-bold">01 찾고</div>
              <div className="text-[var(--brand-ink)] mb-[11px]"><svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square"><circle cx={11} cy={11} r={7} /><path d="M16 16l5 5" /></svg></div>
              <div className="text-[var(--ink)] mb-[7px] text-[15.5px] font-bold break-keep">이미지 속 문구까지 읽어요</div>
              <p className="m-0 text-[var(--ink-3)] text-[12.5px] leading-[1.65] break-keep">상세페이지 이미지를 올리면 그 안의 문구까지 자동으로 읽어 위반 위험을 찾아요.</p>
            </div>
          </div>
          {/* 02 근거 대고 */}
          <div 
            className="bg-[var(--surface)] border border-[var(--line-2)] p-[20px_18px]"
            style={{
              clipPath: featuresRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 50ms"
            }}
          >
            <div
              style={{
                opacity: featuresRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 270ms"
              }}
            >
              <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11px] font-bold">02 근거 대고</div>
              <div className="text-[var(--brand-ink)] mb-[11px]"><svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square"><path d="M5 3h11l3 3v15H5z" /><path d="M9 8h6M9 12h6M9 16h4" /></svg></div>
              <div className="text-[var(--ink)] mb-[7px] text-[15.5px] font-bold break-keep">점수가 아니라 조항으로</div>
              <p className="m-0 text-[var(--ink-3)] text-[12.5px] leading-[1.65] break-keep">문구마다 어떤 법 조항에 걸리는지 원문과 함께 보여드려요. 애매하면 &lsquo;검토필요&rsquo;로 정직하게.</p>
            </div>
          </div>
          {/* 03 고치고 */}
          <div 
            className="bg-[var(--surface)] border border-[var(--line-2)] p-[20px_18px]"
            style={{
              clipPath: featuresRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 100ms"
            }}
          >
            <div
              style={{
                opacity: featuresRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 320ms"
              }}
            >
              <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11px] font-bold">03 고치고</div>
              <div className="text-[var(--brand-ink)] mb-[11px]"><svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square"><path d="M12 20h9" /><path d="M14 4l6 6L8 22H2v-6L14 4z" /></svg></div>
              <div className="text-[var(--ink)] mb-[7px] text-[15.5px] font-bold break-keep">안전한 문구로 바꿔드려요</div>
              <p className="m-0 text-[var(--ink-3)] text-[12.5px] leading-[1.65] break-keep">위반 문구마다 위험을 낮춘 수정안을 제안해요. 없는 효능을 지어내지 않아요.</p>
            </div>
          </div>
          {/* 04 만들고 PRO */}
          <div 
            className="bg-[var(--surface)] border border-[var(--brand-deep)] shadow-[inset_0_0_0_1px_var(--brand-deep)] p-[20px_18px]"
            style={{
              clipPath: featuresRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 150ms"
            }}
          >
            <div
              style={{
                opacity: featuresRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 370ms"
              }}
            >
              <div className="flex items-center gap-[6px] text-[var(--brand-ink)] mb-[12px] font-mono text-[11px] font-bold">
                04 만들고 <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] px-[6px] py-[1px] text-[10px]">PRO</span>
              </div>
              <div className="text-[var(--brand-ink)] mb-[11px]"><svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square"><path d="M12 3v18M3 12h18" /></svg></div>
              <div className="text-[var(--ink)] mb-[7px] text-[15.5px] font-bold break-keep">안전한 초안을 새로</div>
              <p className="m-0 text-[var(--ink-3)] text-[12.5px] leading-[1.65] break-keep">제품 자료만 주시면 상세페이지 · 광고 문구 초안을 만들어 드려요. 위험한 이미지 요청은 거절해요.</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── 리포트 섹션 ── */}
      <div 
        id="report" 
        ref={reportRef} 
        className="border-b border-[var(--line)] bg-[var(--surface-sub)] p-[58px_44px_54px]"
        style={{
          opacity: reportRevealed ? 1 : 0,
          transform: reportRevealed ? "none" : "translateY(12px)",
          transition: prefersReducedMotion ? "none" : "opacity 320ms cubic-bezier(.2,.7,.2,1), transform 320ms cubic-bezier(.2,.7,.2,1)"
        }}
      >
        <div className="grid grid-cols-[400px_1fr] gap-[26px] items-start">
          <div>
            <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11.5px] font-bold tracking-[0.4px]">리포트</div>
            <h2 className="m-0 mb-[14px] text-[var(--ink)] text-[34px] font-extrabold leading-[1.3] tracking-[-1px] break-keep">
              어디가, 왜,<br />어떻게 고쳐야 하는지
            </h2>
            <p className="m-0 mb-[22px] text-[var(--ink-3)] text-[15px] leading-[1.7] break-keep">
              원본 위에 위험 문구를 표시하고, 근거 조항과 고친 문구를 나란히 보여드려요. 게시 판단에 필요한 것만 한 화면에.
            </p>
            {/* 범례 */}
            <div className="flex flex-col gap-[8px] text-[var(--ink-2)] text-[13px] font-medium">
              <div className="flex gap-[8px] items-center">
                <span className="inline-block w-[10px] h-[10px] bg-[var(--crit-bg)] border border-[var(--crit)]" />
                위반 · 조항 근거가 분명한 것
              </div>
              <div className="flex gap-[8px] items-center">
                <span className="inline-block w-[10px] h-[10px] bg-[var(--surface)] border border-dashed border-[var(--crit)]" />
                검토필요 · 입증 자료가 필요한 것
              </div>
              <div className="flex gap-[8px] items-center">
                <span className="inline-block w-[10px] h-[10px] bg-[var(--surface)] border border-[var(--line-2)]" />
                통과 · 이번 기준에서 미검출
              </div>
            </div>
          </div>

          {/* 리포트 UI 데모 */}
          <div className="bg-[var(--surface)] border border-[var(--line-2)] shadow-[0_10px_34px_rgba(20,35,27,0.07)]">
            {/* 상단 바 */}
            <div className="flex items-center gap-3 border-b border-[var(--line)] bg-[var(--surface-sub)] p-[9px_14px] font-mono text-[11px] text-[var(--ink-3)]">
              <span>리포트 &gt; 글로우세럼_상세페이지</span>
              <span className="ml-auto font-semibold text-[var(--crit)]">위반 1 · 검토필요 1</span>
              <span className="text-[var(--ink-3)]">이미지 4 / 12</span>
            </div>
            {/* 파일 태그들 */}
            <div className="flex flex-wrap gap-2 border-b border-[var(--line)] p-[8px_14px]">
              {["텍스트 붙여넣기", "상세페이지 이미지 12", "제품 상세 · 성분표", "인증 · 시험 자료 PDF 2"].map(t => (
                <span key={t} className="inline-flex items-center gap-1 bg-[var(--brand-deep)] text-[var(--on-brand)] font-mono text-[10.5px] font-bold px-[7px] py-[2px]">■ {t}</span>
              ))}
              <span className="ml-auto text-[var(--ink-3)] font-mono text-[11px]">한 번에 함께 분석</span>
            </div>
            <div className="grid grid-cols-2">
              {/* 좌: 이미지 영역 */}
              <div className="border-r border-[var(--line)] p-[12px_14px]">
                <div className="text-[var(--ink-3)] mb-[8px] font-mono text-[11px]">업로드한 상세페이지</div>
                <div className="flex items-center justify-center text-[var(--ink-3)] bg-[var(--surface-sub)] border border-dashed border-[var(--line-2)] h-[120px] text-[11px] text-center leading-[1.7]">
                  [ 상세페이지 이미지 ]<br />원본 그대로 보관
                </div>
                <div className="mt-[8px] text-[var(--crit)] text-[10.5px]">▸ 이미지 속 문구 2건 검출</div>
              </div>
              {/* 우: 판정 */}
              <div className="p-[12px_14px]">
                <div className="text-[var(--ink-3)] mb-[8px] font-mono text-[11px]">문구별 판정</div>
                {/* 위반 카드 */}
                <div className="mb-[8px] border border-[var(--crit-bd)] bg-[var(--crit-bg)] p-[10px_12px]">
                  <div className="flex items-center justify-between mb-[6px]">
                    <span className="font-semibold text-[var(--crit)] text-[11px]">위반 · 기능성 범위 이탈</span>
                    <span className="text-[var(--on-brand)] bg-[var(--crit)] font-mono text-[9px] font-bold px-[6px] py-[2px]">화장품법 제13조 ①2호</span>
                  </div>
                  <div className="font-semibold text-[var(--ink)] mb-[6px] text-[11.5px]">&quot;7일 만에 미백 완성&quot; - 심사받은 범위를 벗어난 기간 · 완성 단정 표현</div>
                  <div className="text-[var(--ink-3)] text-[11px] leading-[1.6] border-t border-[var(--crit-bd)] pt-1.5 mt-1">
                    권고안 &quot;나이아신아마이드 함유, 멜라닌 생성 억제로 미백에 도움&quot; <span className="text-[var(--brand-ink)]">적용 →</span>
                  </div>
                </div>
                {/* 검토필요 카드 */}
                <div className="border border-dashed border-[var(--crit-bd)] p-[10px_12px]">
                  <div className="flex items-center justify-between mb-[6px]">
                    <span className="text-[var(--ink-3)] text-[11px] font-semibold">검토필요 · 입증 자료 필요</span>
                    <span className="text-[var(--crit)] border border-[var(--crit-bd)] font-mono text-[9px] font-bold px-[6px] py-[2px]">표시광고 실증제</span>
                  </div>
                  <div className="text-[var(--ink)] text-[11.5px]">&quot;순식간에 스며드는&quot; - 체감 표현, 인체적용시험 자료 권장</div>
                </div>
                {/* 버튼 */}
                <div className="flex gap-[8px] mt-[10px]">
                  <span className="flex-1 flex items-center justify-center text-[var(--on-brand)] bg-[var(--brand)] cursor-pointer hover:bg-[var(--brand-ink)] py-2.5 text-[13px] font-bold">권고안 전체 적용</span>
                  <span className="flex-1 flex items-center justify-center text-[var(--ink-2)] border border-[var(--line-2)] cursor-pointer hover:bg-[var(--nav-active-bg)] py-2.5 text-[13px] font-bold">수정 후 재검사</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 수출 검사 섹션 ── */}
      <div 
        id="export" 
        ref={exportSectionRef} 
        className="border-b border-[var(--line)] p-[58px_44px_54px]"
        style={{
          opacity: exportSectionRevealed ? 1 : 0,
          transform: exportSectionRevealed ? "none" : "translateY(12px)",
          transition: prefersReducedMotion ? "none" : "opacity 320ms cubic-bezier(.2,.7,.2,1), transform 320ms cubic-bezier(.2,.7,.2,1)"
        }}
      >
        <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11.5px] font-bold tracking-[0.4px]">수출 검사</div>
        <h2 className="m-0 mb-[28px] text-[var(--ink)] text-[34px] font-extrabold leading-[1.3] tracking-[-1px] break-keep">
          한국에선 화장품,<br />미국에선 의약품입니다.
        </h2>
        <p className="m-0 mb-[28px] text-[var(--ink-3)] text-[15px] leading-[1.7] max-w-[58ch] break-keep">
          대상 국가만 미국으로 바꾸면 같은 문구 · 성분을 미국 기준으로 다시 검사해요. 1차 지원국은 미국, 다른 국가는 순차 지원 예정.
        </p>
        <div ref={exportObserverRef} className="grid grid-cols-[1fr_44px_1fr] items-stretch overflow-hidden">
          {/* KR */}
          <div 
            className="bg-[var(--surface)] border border-[var(--line-2)]"
            style={{
              transform: exportActive ? "none" : "translateX(-16px)",
              opacity: exportActive ? 1 : 0,
              transition: prefersReducedMotion ? "none" : "transform 300ms ease-out, opacity 300ms ease-out"
            }}
          >
            <div className="flex items-center gap-[8px] border-b border-[var(--line)] text-[var(--ink-3)] px-[13px] py-2 font-mono text-[10.5px]">
              <span className="font-bold text-[var(--on-brand)] bg-[var(--brand-deep)] px-[6px] py-[1px]">KR</span>
              국내 · 화장품법 기준
            </div>
            <div className="p-[18px_17px]">
              <p className="m-0 mb-[12px] text-[var(--ink)] text-[15px] font-semibold leading-[1.6]">&quot;SPF50+ 자외선 차단, 톤업 선크림&quot;</p>
              <span className="inline-flex items-center gap-[5px] text-[var(--ink-2)] border border-[var(--line-2)] mb-[10px] text-[11.5px] font-semibold px-2 py-[2px]">
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square"><path d="M4 12l5 5L20 6" /></svg>
                기능성화장품 - 표방 가능
              </span>
              <p className="m-0 text-[var(--ink-3)] text-[12.5px] leading-[1.65] break-keep">자외선차단은 식약처 심사 대상. 심사 범위 안 표현으로 확인.</p>
            </div>
          </div>
          {/* 가운데 ⇄ */}
          <div 
            className="flex items-center justify-center text-[var(--brand-ink)] font-mono text-[16px] font-bold"
            style={{
              transform: exportActive ? "rotate(180deg)" : "rotate(0)",
              transition: prefersReducedMotion ? "none" : "transform 360ms ease-out 300ms"
            }}
          >
            ⇄
          </div>
          {/* US */}
          <div 
            className="bg-[var(--surface)] border"
            style={{
              transform: exportActive ? "none" : "translateX(16px)",
              opacity: exportActive ? 1 : 0,
              borderColor: exportActive ? "var(--crit-bd)" : "var(--line-2)",
              transition: prefersReducedMotion ? "none" : "transform 300ms ease-out, opacity 300ms ease-out, border-color 300ms ease-out 200ms"
            }}
          >
            <div 
              className="flex items-center gap-[8px] border-b px-[13px] py-2 font-mono text-[10.5px]"
              style={{
                borderColor: exportActive ? "var(--crit-bd)" : "var(--line-2)",
                backgroundColor: exportActive ? "var(--crit-bg)" : "var(--surface-sub)",
                color: exportActive ? "var(--crit)" : "var(--ink-3)",
                transition: prefersReducedMotion ? "none" : "border-color 300ms ease-out 200ms, background-color 300ms ease-out 200ms, color 300ms ease-out 200ms"
              }}
            >
              <span 
                className="font-bold text-white px-[6px] py-[1px]"
                style={{
                  backgroundColor: exportActive ? "var(--crit)" : "var(--ink-3)",
                  transition: prefersReducedMotion ? "none" : "background-color 300ms ease-out 200ms"
                }}
              >
                US
              </span>
              미국 · FDA 기준
            </div>
            <div className="p-[18px_17px]">
              <p className="m-0 mb-[12px] text-[var(--ink)] text-[15px] font-semibold leading-[1.6]">&quot;SPF50+ 자외선 차단, 톤업 선크림&quot;</p>
              <span 
                className="inline-flex items-center gap-[5px] text-[var(--crit)] border border-[var(--crit-bd)] bg-[var(--crit-bg)] mb-[10px] text-[11.5px] font-semibold px-2 py-[2px]"
                style={{
                  opacity: exportActive ? 1 : 0,
                  transform: exportActive ? "scale(1)" : "scale(0.94)",
                  transformOrigin: "left center",
                  transition: prefersReducedMotion ? "none" : "opacity 300ms ease-out 200ms, transform 300ms ease-out 200ms"
                }}
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square"><path d="M12 3 2 20h20L12 3z" /><path d="M12 10v4M12 17v.5" /></svg>
                의약품으로 분류 - 경고
              </span>
              <p className="m-0 text-[var(--ink-3)] text-[12.5px] leading-[1.65] break-keep">선크림은 미국에서 의약품이에요. 승인 목록에 없는 차단 성분 1건도 함께 짚어드려요.</p>
            </div>
          </div>
        </div>
        <div className="mt-[14px] text-[var(--ink-3)] font-mono text-[11px]">
          수출 전 1차 점검용이에요 · EU · 일본 · 중국 순차 지원 예정
        </div>
      </div>

      {/* ── 요금제 섹션 ── */}
      <div 
        id="pricing" 
        ref={pricingRef} 
        className="border-b border-[var(--line)] p-[58px_44px_54px]"
        style={{
          opacity: pricingRevealed ? 1 : 0,
          transform: pricingRevealed ? "none" : "translateY(12px)",
          transition: prefersReducedMotion ? "none" : "opacity 320ms cubic-bezier(.2,.7,.2,1), transform 320ms cubic-bezier(.2,.7,.2,1)"
        }}
      >
        <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11.5px] font-bold tracking-[0.4px]">요금제</div>
        <h2 className="m-0 mb-[28px] text-[var(--ink)] text-[34px] font-extrabold leading-[1.3] tracking-[-1px] break-keep">
          진단은 무료로 시작,<br />더 필요할 때만 유료로.
        </h2>
        <div className="grid grid-cols-3 gap-3 mb-[12px]">
          {/* FREE */}
          <div 
            className="flex flex-col bg-[var(--surface)] border border-[var(--line-2)]"
            style={{
              clipPath: pricingRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 0ms"
            }}
          >
            <div
              style={{
                opacity: pricingRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 220ms"
              }}
              className="flex-1 flex flex-col"
            >
              <div className="p-[20px_20px_0]">
                <div className="text-[var(--ink-3)] mb-[10px] font-mono text-[12px] font-bold">FREE</div>
                <div className="text-[var(--ink)] mb-[2px] text-[34px] font-extrabold tracking-[-1px]">0원</div>
                <div className="text-[var(--ink-3)] mb-[16px] text-[12px]">일단 검사부터 해보세요</div>
              </div>
              <div className="flex-1 border-t border-dashed border-[var(--line-2)] text-[var(--ink-2)] p-[14px_20px] text-[13px] font-medium leading-[2]">
                국내 검사 월 3건<br />위험 문구 표시 + <b className="text-[var(--ink)]">조항 근거 1건 공개</b><br />이력 7일 보관
              </div>
              <div className="p-[0_20px_20px]">
                <Link href="/home" className="flex items-center justify-center no-underline border border-[var(--line-2)] text-[var(--ink-2)] hover:bg-[var(--nav-active-bg)] cursor-pointer py-[11px] text-[13.5px] font-bold">무료로 시작</Link>
              </div>
            </div>
          </div>
          {/* BASIC */}
          <div 
            className="flex flex-col bg-[var(--surface)] border border-[var(--line-2)]"
            style={{
              clipPath: pricingRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 50ms"
            }}
          >
            <div
              style={{
                opacity: pricingRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 270ms"
              }}
              className="flex-1 flex flex-col"
            >
              <div className="p-[20px_20px_0]">
                <div className="text-[var(--ink-3)] mb-[10px] font-mono text-[12px] font-bold">BASIC</div>
                <div className="text-[var(--ink)] mb-[2px] text-[34px] font-extrabold tracking-[-1px]">월 4.9만원</div>
                <div className="text-[var(--ink-3)] mb-[16px] text-[12px]">인플루언서 · 1인 브랜드</div>
              </div>
              <div className="flex-1 border-t border-dashed border-[var(--line-2)] text-[var(--ink-2)] p-[14px_20px] text-[13px] font-medium leading-[2]">
                국내 검사 월 20건<br /><b className="text-[var(--brand-ink)]">전체 조항 근거 + 문구별 수정안</b><br />이력 무제한 · 재검사 무제한
              </div>
              <div className="p-[0_20px_20px]">
                <Link href="/home" className="flex items-center justify-center no-underline border border-[var(--brand)] text-[var(--brand-ink)] hover:bg-[var(--nav-active-bg)] cursor-pointer py-[11px] text-[13.5px] font-bold">Basic 시작</Link>
              </div>
            </div>
          </div>
          {/* PRO */}
          <div 
            className="flex flex-col bg-[var(--surface)] relative border border-[var(--brand-deep)] shadow-[inset_0_0_0_1px_var(--brand-deep)]"
            style={{
              clipPath: pricingRevealed ? "inset(0)" : "inset(0 100% 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 220ms ease-out 100ms"
            }}
          >
            <span className="absolute top-[-1px] right-[-1px] text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono text-[10px] font-bold px-2 py-[3px]">추천 · 상시 운영 브랜드</span>
            <div
              style={{
                opacity: pricingRevealed ? 1 : 0,
                transition: prefersReducedMotion ? "none" : "opacity 320ms ease-out 320ms"
              }}
              className="flex-1 flex flex-col"
            >
              <div className="p-[20px_20px_0]">
                <div className="text-[var(--brand-ink)] mb-[10px] font-mono text-[12px] font-bold">PRO</div>
                <div className="text-[var(--ink)] mb-[2px] text-[34px] font-extrabold tracking-[-1px]">월 14.9만원</div>
                <div className="text-[var(--ink-3)] mb-[16px] text-[12px]">검사를 넘어 제작까지</div>
              </div>
              <div className="flex-1 border-t border-dashed border-[var(--line-2)] text-[var(--ink-2)] p-[14px_20px] text-[13px] font-medium leading-[2]">
                국내 검사 무제한<br />Basic 전체 포함<br /><b className="text-[var(--brand-ink)]">상세페이지 초안 제작 월 5회</b><br />전체 검사 현황 대시보드<br />수출 검사 애드온 구매 가능
              </div>
              <div className="p-[0_20px_20px]">
                <Link href="/home" className="flex items-center justify-center gap-[7px] no-underline bg-[var(--brand)] text-[var(--on-brand)] hover:bg-[var(--brand-ink)] cursor-pointer py-[11px] text-[13.5px] font-bold">Pro 시작 <span className="font-mono">→</span></Link>
              </div>
            </div>
          </div>
        </div>

        {/* EXPORT 애드온 (토글 기능 포함) */}
        <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)]">
          <div
            onClick={() => setExportOpen(v => !v)}
            className="flex items-center gap-[14px] cursor-pointer hover:bg-[var(--nav-active-bg)] p-[14px_20px]"
          >
            <span className="text-[var(--surface)] bg-[var(--ink)] font-mono text-[11px] font-bold px-[7px] py-[2px]">EXPORT</span>
            <span className="text-[var(--ink)] text-[14px] font-semibold">미국 수출 검사 애드온</span>
            <span className="text-[var(--ink-3)] text-[13px] break-keep">건당 4.9만원 · Pro 전용</span>
            <span className="ml-auto inline-flex items-center gap-[5px] text-[var(--brand-ink)] whitespace-nowrap text-[13px] font-bold">
              {exportOpen ? "접기" : "자세히"}
              <span className="inline-flex transition-transform duration-200" style={{ transform: exportOpen ? "rotate(180deg)" : "rotate(0)" }}>
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square"><path d="M6 9l6 6 6-6" /></svg>
              </span>
            </span>
          </div>
          {exportOpen && (
            <div className="p-[0_20px_16px] animate-[popIn_0.2s_both]">
              <div className="grid grid-cols-3 gap-3 pt-1">
                {[
                  { label: "대상", text: "미국 FDA/FTC 기준 1차 스크리닝 (EU · 일본 · 중국 순차 지원 예정)" },
                  { label: "포함 항목", text: "성분 OTC 분류 판정 · 라벨링 필수 항목 · 금지 클레임 탐지 · 수정 권고안" },
                  { label: "비용 비교", text: "RA 컨설팅 건당 200만~670만원 대비 약 1/40 (올리기 전 1차 점검용)" },
                ].map(c => (
                  <div key={c.label} className="bg-[var(--surface)] border border-[var(--line)] p-[12px_14px]">
                    <div className="text-[var(--brand-ink)] mb-[6px] font-mono text-[11px] font-bold">{c.label}</div>
                    <div className="text-[var(--ink-2)] text-[13px] leading-[1.6]">{c.text}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── FAQ 섹션 ── */}
      <div 
        id="faq" 
        ref={faqRef} 
        className="p-[58px_44px_46px]"
        style={{
          opacity: faqRevealed ? 1 : 0,
          transform: faqRevealed ? "none" : "translateY(12px)",
          transition: prefersReducedMotion ? "none" : "opacity 320ms cubic-bezier(.2,.7,.2,1), transform 320ms cubic-bezier(.2,.7,.2,1)"
        }}
      >
        <div className="text-[var(--brand-ink)] mb-[12px] font-mono text-[11.5px] font-bold tracking-[0.4px]">FAQ</div>
        <h2 className="m-0 mb-[24px] text-[var(--ink)] text-[28px] font-extrabold leading-[1.3] tracking-[-0.8px]">자주 묻는 질문</h2>
        <div className="grid grid-cols-2 gap-3 mb-[34px]">
          {[
            { q: "법률 자문을 대체하나요?", a: "아니요. 바름은 게시 전에 위험을 미리 점검하는 도구예요. 위험 문구와 조항 근거를 보여드리지만, 최종 게시 판단과 책임은 사업자에게 있어요." },
            { q: "이미지 안의 문구도 검사되나요?", a: "네. 상세페이지 이미지를 올리면 그 안의 문구까지 자동으로 읽어서 판정해요. 위반 표현의 상당수가 이미지 안에 있거든요." },
            { q: "'통과'면 100% 안전한가요?", a: "아니요. 위험해 보이는 건 놓치지 않게 넓게 잡지만, 통과가 합법 보증은 아니에요. 화면과 약관에도 이 점을 계속 알려드려요." },
            { q: "올린 자료는 어떻게 처리되나요?", a: "검사와 초안 제작에만 쓰고, 개인정보는 자동으로 걸러내요. 올리신 자료를 AI 학습에 쓰지 않아요." },
          ].map((f, i) => (
            <div 
              key={f.q} 
              className="border border-[var(--line)] p-[16px_18px] bg-[var(--surface)]"
              style={{
                clipPath: faqRevealed ? "inset(0)" : "inset(0 100% 0 0)",
                transition: prefersReducedMotion ? "none" : `clip-path 220ms ease-out ${50 * i}ms`
              }}
            >
              <div 
                style={{
                  opacity: faqRevealed ? 1 : 0,
                  transition: prefersReducedMotion ? "none" : `opacity 320ms ease-out ${50 * i + 220}ms`
                }}
              >
                <div className="text-[var(--ink)] mb-[7px] text-[14px] font-bold break-keep">
                  <span className="text-[var(--brand-ink)] mr-[7px] font-mono text-[11px] font-bold">Q</span>
                  {f.q}
                </div>
                <p className="m-0 text-[var(--ink-3)] text-[13px] leading-[1.7] break-keep">{f.a}</p>
              </div>
            </div>
          ))}
        </div>
 
        {/* CTA 배너 */}
        <div 
          ref={ctaRef}
          className="relative overflow-hidden flex items-center gap-[30px] p-[44px_40px]"
        >
          {/* Animated Background Wipe Layer */}
          <div 
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "var(--brand-deep)",
              zIndex: 0,
              clipPath: ctaRevealed ? "inset(0)" : "inset(100% 0 0 0)",
              transition: prefersReducedMotion ? "none" : "clip-path 420ms cubic-bezier(.2,.7,.2,1)"
            }}
          />
          
          <div className="relative z-10 flex-1">
            <div className="text-[var(--on-brand)] mb-[8px] text-[30px] font-extrabold leading-[1.3] tracking-[-0.8px] break-keep">
              지금 광고 문구를 붙여넣으세요.<br />3분 뒤 조항까지 나옵니다.
            </div>
            <div className="font-mono text-[12px] text-[var(--brand)]">
              가입 없이 월 3건 무료 · 신용카드 불필요 ▊
            </div>
          </div>
          <Link
            href="/home"
            className="relative z-10 inline-flex items-center gap-[8px] no-underline bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--nav-active-bg)] cursor-pointer whitespace-nowrap p-[15px_28px] text-[15px] font-bold"
          >
            무료 검사 시작 <span className="font-mono">→</span>
          </Link>
        </div>
      </div>

      {/* ── 면책 + 푸터 ── */}
      <div className="border-t border-[var(--line)] bg-[var(--surface-sub)] text-[var(--ink-3)] p-[10px_20px] text-[11px] leading-[1.65]">
        바름은 게시 전 사전 점검 도구이며 최종 법적 판단이 아닙니다. 위험 후보를 넓게 잡기 때문에 &lsquo;통과&rsquo;가 100% 안전을 보장하진 않습니다. 최종 게시 판단과 책임은 사업자에게 있습니다.{" "}
        <b className="text-[var(--brand-ink)] font-semibold">적용 기준: 화장품법 · 고시 2025-79호 · 미국 FDA/FTC</b>
      </div>
      <div className="flex border-t border-[var(--line-2)] bg-[var(--surface-sub)] font-mono text-[11px]">
        <span className="font-bold bg-[var(--brand-deep)] text-[var(--on-brand)] p-[7px_13px]">바름</span>
        <span className="border-r border-[var(--line)] text-[var(--ink-3)] p-[7px_13px]">팀 유어베리 YourVeri</span>
        <span className="border-r border-[var(--line)] text-[var(--ink-3)] p-[7px_13px]">© 2026</span>
        <span className="flex-1 text-[var(--ink-3)] p-[7px_13px]">올리기 전에, 바르게.</span>
        <span className="text-[var(--ink-3)] p-[7px_13px]">^N 새 검사</span>
      </div>
    </div>
  );
}
