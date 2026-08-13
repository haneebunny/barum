"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { Modal } from "@/components/Modal/Modal";

interface FeatItem {
  text: string;
  is_active: boolean;
}

interface TierInfo {
  name: "Free" | "Basic" | "Pro";
  price: string;
  used: number;
  limit: number | null;
  feats: FeatItem[];
  up: {
    title: string;
    desc: string;
  };
}

const TIERS: Record<"Free" | "Basic" | "Pro", TierInfo> = {
  Free: {
    name: "Free",
    price: "0원",
    used: 2,
    limit: 3,
    feats: [
      { text: "월 3건 검사", is_active: true },
      { text: "위반 탐지 · 근거 조항", is_active: true },
      { text: "수정 권고안", is_active: false },
      { text: "검사 이력 무제한", is_active: false },
    ],
    up: {
      title: "Basic으로 올리면 수정 권고안까지 볼 수 있어요.",
      desc: "위반을 낮춘 대체 표현 제안과 무제한 검사 이력이 열립니다.",
    },
  },
  Basic: {
    name: "Basic",
    price: "4.9만원",
    used: 12,
    limit: 20,
    feats: [
      { text: "월 20건 검사", is_active: true },
      { text: "위반 탐지 · 근거 조항", is_active: true },
      { text: "수정 권고안 제공", is_active: true },
      { text: "검사 이력 무제한", is_active: true },
    ],
    up: {
      title: "Pro로 올리면 검사가 무제한이 됩니다.",
      desc: "콘텐츠 생성 월 5회와 이력 통합 대시보드가 함께 열립니다.",
    },
  },
  Pro: {
    name: "Pro",
    price: "14.9만원",
    used: 47,
    limit: null,
    feats: [
      { text: "검사 무제한", is_active: true },
      { text: "수정 권고안 제공", is_active: true },
      { text: "콘텐츠 생성 월 5회", is_active: true },
      { text: "이력 통합 대시보드", is_active: true },
    ],
    up: {
      title: "현재 최상위 요금제(Pro)를 이용 중입니다.",
      desc: "리포트를 PDF로 내보내려면 Export 애드온을 추가할 수 있어요.",
    },
  },
};

export default function MyPage() {
  const [tier, set_tier] = useState<"Free" | "Basic" | "Pro">("Basic");
  const [is_compare_modal_open, set_is_compare_modal_open] = useState(false);

  const compare_btn_ref = useRef<HTMLButtonElement>(null);
  const modal_close_btn_ref = useRef<HTMLButtonElement>(null);

  const active_tier = TIERS[tier];

  return (
    <>
      {/* 메타스트립: 브레드크럼 + 목업 전용 등급 스위처 */}
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
        <span className="text-[var(--ink-2)]">
          <Link href="/" className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]">
            홈
          </Link>{" "}
          <span className="text-[var(--ink-3)]">›</span> 마이페이지
        </span>
        <div className="ml-auto flex items-center gap-1.75">
          <span className="text-[var(--ink-3)] text-[10px]">목업 전용 · 실제 화면엔 없음:</span>
          <div className="flex border border-[var(--line-2)]" id="tierSwitch" role="group" aria-label="요금제 전환">
            {(["Free", "Basic", "Pro"] as const).map((t) => (
              <button
                key={t}
                className={`font-mono text-[10.5px] p-[4px_10px] border-0 border-r border-[var(--line-2)] bg-transparent cursor-pointer transition-all duration-[120ms] last:border-r-0 ${
                  tier === t
                    ? "bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold"
                    : "text-[var(--ink-3)] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
                }`}
                onClick={() => set_tier(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 요금제 + 사용량 */}
      <div className="p-[18px_20px] border-b border-[var(--line)]">
        <div className="flex items-center gap-[11px] m-[0_0_13px]">
          <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
          <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">요금제 · 사용량</h2>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
          <span className="text-[var(--ink-3)] font-mono text-[10.5px]">glowskin 계정</span>
        </div>
        <div className="grid grid-cols-2 gap-3.5 max-[900px]:grid-cols-1">
          <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
            <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">현재 요금제</p>
            <div className="flex items-baseline gap-2.25 mb-1.5">
              <span className="text-[22px] font-extrabold text-[var(--ink)] tracking-[-0.4px]">{active_tier.name}</span>
              <span className="font-mono text-[12.5px] text-[var(--ink-2)]">
                {active_tier.price} <span className="text-[var(--ink-3)]">/ 월</span>
              </span>
            </div>
            <ul className="list-none m-[8px_0_0] p-0 flex flex-col gap-1.25">
              {active_tier.feats.map((feat, index) => (
                <li key={index} className={`text-[12.5px] flex items-start gap-1.75 ${feat.is_active ? "text-[var(--ink-2)]" : "text-[var(--ink-3)]"}`}>
                  {feat.is_active ? (
                    <svg
                      className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--brand-ink)]"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M4 12l5 5L20 6" />
                    </svg>
                  ) : (
                    <svg
                      className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--ink-3)]"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M5 12h14" />
                    </svg>
                  )}
                  <span>{feat.text}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
            <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">이번 달 사용량</p>
            {active_tier.limit === null ? (
              <div>
                <div className="flex items-baseline justify-between mb-2.25">
                  <span className="text-[12.5px] text-[var(--ink-2)]">이번 달 검사</span>
                  <span className="font-mono tabular-nums text-[13px] text-[var(--ink)]">
                    <b className="text-[16px] font-bold">{active_tier.used}</b>건
                  </span>
                </div>
                <span className="inline-flex items-center gap-1.5 font-mono text-[12px] text-[var(--brand-ink)] border border-[var(--line-2)] bg-[var(--surface-sub)] p-[4px_9px]">
                  <svg
                    viewBox="0 0 24 24"
                    width="14"
                    height="14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    aria-hidden="true"
                  >
                    <path d="M7 12c0-2 1.5-3.5 3.5-3.5S14 12 14 12s1.5 3.5 3.5 3.5S21 14 21 12s-1.5-3.5-3.5-3.5S14 12 14 12s-1.5 3.5-3.5 3.5S3 14 3 12s1.5-3.5 4-3.5" />
                  </svg>
                  무제한 검사
                </span>
                <div className="font-mono text-[10.5px] text-[var(--ink-3)] mt-2">한도 없음 · 이번 달 {active_tier.used}건 사용</div>
              </div>
            ) : (
              <div>
                <div className="flex items-baseline justify-between mb-2.25">
                  <span className="text-[12.5px] text-[var(--ink-2)]">검사 사용량</span>
                  <span className="font-mono tabular-nums text-[13px] text-[var(--ink)]">
                    <b className="text-[16px] font-bold">{active_tier.used}</b> / {active_tier.limit}건
                  </span>
                </div>
                <div 
                  className="h-2 bg-[var(--line-2)] border border-[var(--line-2)] overflow-hidden" 
                  aria-label={`검사 사용량 ${Math.round((active_tier.used / active_tier.limit) * 100)}% 사용함`}
                >
                  <div 
                    className="h-full bg-[var(--ink-3)]" 
                    style={{ width: `${Math.round((active_tier.used / active_tier.limit) * 100)}%` }}
                  ></div>
                </div>
                <div className="font-mono text-[10.5px] text-[var(--ink-3)] mt-2">{active_tier.limit - active_tier.used}건 남음 · 매월 1일 초기화</div>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3.5 mt-3.5 p-[13px_15px] border border-[var(--line-2)] bg-[var(--surface-sub)]" id="upBanner">
          <div className="flex-1 min-w-0">
            <b className="text-[var(--ink)] font-bold">{active_tier.up.title}</b>
            <p className="m-[2px_0_0] text-[12px] text-[var(--ink-3)]">{active_tier.up.desc}</p>
          </div>
          <button 
            id="openCompare"
            ref={compare_btn_ref}
            className="font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-white border-[var(--brand)] dark:text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-ink)] dark:hover:bg-[#63e89f] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms]" 
            onClick={() => set_is_compare_modal_open(true)}
          >
            요금제 비교 <span className="font-mono">→</span>
          </button>
        </div>
      </div>

      {/* Pro 전용: 이력 통합 대시보드 */}
      {tier === "Pro" && (
        <div className="p-[18px_20px] border-b border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">이력 통합 대시보드</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">Pro · 이번 분기</span>
          </div>
          <div className="grid grid-cols-2 gap-3.5 mb-3.5 max-[900px]:grid-cols-1">
            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[14px_15px]">
              <p className="text-[12px] text-[var(--ink-3)] mb-1.5">이번 분기 위반</p>
              <div className="text-[30px] font-extrabold leading-none tracking-[-0.5px] text-[var(--crit)]">42</div>
              <div className="font-mono text-[11px] text-[var(--ink-3)] mt-1.25">지난 분기 대비 8건 감소</div>
              <svg className="mt-2.75 block w-full h-[34px]" viewBox="0 0 240 34" preserveAspectRatio="none" aria-hidden="true">
                {[5, 7, 4, 6, 8, 5, 3, 4].map((val, i) => {
                  const max_val = 8;
                  const height_factor = 24 / max_val;
                  const h = val * height_factor;
                  const y = 34 - h;
                  const x = 1 + i * 30;
                  const fill = i === 7 ? "var(--crit)" : "var(--ink-3)";
                  return (
                    <rect
                      key={i}
                      x={x}
                      y={y}
                      width={28}
                      height={h + 4}
                      rx={4}
                      fill={fill}
                    >
                      <title>{8 - i}주 전 기준 {val}건</title>
                    </rect>
                  );
                })}
              </svg>
            </div>
            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[14px_15px]">
              <p className="text-[12px] text-[var(--ink-3)] mb-1.5">이번 분기 검토필요</p>
              <div className="text-[30px] font-extrabold leading-none tracking-[-0.5px] text-[var(--ink)]">21</div>
              <div className="font-mono text-[11px] text-[var(--ink-3)] mt-1.25">지난 분기 대비 3건 증가</div>
              <svg className="mt-2.75 block w-full h-[34px]" viewBox="0 0 240 34" preserveAspectRatio="none" aria-hidden="true">
                {[2, 3, 2, 4, 3, 2, 3, 2].map((val, i) => {
                  const max_val = 4;
                  const height_factor = 24 / max_val;
                  const h = val * height_factor;
                  const y = 34 - h;
                  const x = 1 + i * 30;
                  const fill = i === 7 ? "var(--ink-2)" : "var(--ink-3)";
                  return (
                    <rect
                      key={i}
                      x={x}
                      y={y}
                      width={28}
                      height={h + 4}
                      rx={4}
                      fill={fill}
                    >
                      <title>{8 - i}주 전 기준 {val}건</title>
                    </rect>
                  );
                })}
              </svg>
            </div>
          </div>
          <p className="font-mono text-[10.5px] text-[var(--ink-3)] mt-0.5">최근 8주 주별 추이 · 막대에 올리면 값 표시 · 검사 128건 기준</p>
        </div>
      )}

      {/* 검사 이력 */}
      <div className="p-[18px_20px] border-b-0">
        <div className="flex items-center gap-[11px] m-[0_0_13px]">
          <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center" id="histNo">{tier === "Pro" ? "03" : "02"}</span>
          <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">검사 이력</h2>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
          <span className="text-[var(--ink-3)] font-mono text-[10.5px]" id="histHint">최근 5건</span>
        </div>
        <div className="flex flex-col gap-1.75">
          <Link href="/report/demo-id-1" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3.25 border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
            <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">글로우 세럼 · 미국 상세페이지</span>
            <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">해외 · 미국</span>
            <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--crit)] border-[var(--crit-bd)] bg-[var(--crit-bg)] font-semibold">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
                className="w-[13px] h-[13px]"
              >
                <path d="M12 3 2 20h20L12 3z" />
                <path d="M12 10v4M12 17v.5" />
              </svg>
              검토 필요
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">방금</span>
          </Link>

          <Link href="/report/demo-id-2" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3.25 border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
            <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">수분 크림 리뉴얼 상세페이지</span>
            <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">국내</span>
            <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--ink-2)] border-[var(--line-2)]">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
                className="w-[13px] h-[13px]"
              >
                <path d="M4 12l5 5L20 6" />
              </svg>
              검사 완료
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">2일 전</span>
          </Link>

          <Link href="/report/demo-id-3" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3.25 border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
            <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">선크림 SPF50 신제품</span>
            <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">국내</span>
            <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--crit)] border-[var(--crit-bd)] bg-[var(--crit-bg)] font-semibold">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
                className="w-[13px] h-[13px]"
              >
                <path d="M12 3 2 20h20L12 3z" />
                <path d="M12 10v4M12 17v.5" />
              </svg>
              위반 3건
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">3일 전</span>
          </Link>

          <Link href="/report/demo-id-4" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3.25 border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
            <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">아이크림 재론칭 상세페이지</span>
            <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">국내</span>
            <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--ink-2)] border-[var(--line-2)]">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
                className="w-[13px] h-[13px]"
              >
                <path d="M4 12l5 5L20 6" />
              </svg>
              검사 완료
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">1주 전</span>
          </Link>

          <Link href="/report/demo-id-5" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3.25 border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
            <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">클렌징폼 성분 개편</span>
            <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">해외 · 미국</span>
            <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--crit)] border-[var(--crit-bd)] bg-[var(--crit-bg)] font-semibold">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
                className="w-[13px] h-[13px]"
              >
                <path d="M12 3 2 20h20L12 3z" />
                <path d="M12 10v4M12 17v.5" />
              </svg>
              검토 필요
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">2주 전</span>
          </Link>
        </div>
      </div>

      <PageFooter />

      <Modal
        isOpen={is_compare_modal_open}
        title="요금제 비교"
        onClose={() => set_is_compare_modal_open(false)}
        ref={modal_close_btn_ref}
      >
        <div className="flex flex-col gap-0.5">
          <div className={`grid grid-cols-[auto_auto_1fr] gap-[10px] items-baseline p-2.5 border-b border-[var(--line)] last:border-b-0 ${tier === "Free" ? "bg-[var(--nav-active-bg)]" : ""}`}>
            <span className="text-[var(--brand-ink)]">›</span>
            <span className="text-[var(--ink)] font-bold text-[13px] min-w-[56px]">
              Free
              {tier === "Free" && <span className="text-[var(--ink-3)] text-[10.5px] ml-1.5"> (현재 이용 중)</span>}
            </span>
            <span className="text-[var(--ink-2)] text-[12px] whitespace-nowrap text-right ml-auto">0원 / 월</span>
            <span className="text-[var(--ink-3)] text-[11.5px] col-span-full mt-0.5 ml-[22px]">월 3건 검사 · 위반 탐지와 근거까지 체험</span>
          </div>
          <div className={`grid grid-cols-[auto_auto_1fr] gap-[10px] items-baseline p-2.5 border-b border-[var(--line)] last:border-b-0 ${tier === "Basic" ? "bg-[var(--nav-active-bg)]" : ""}`}>
            <span className="text-[var(--brand-ink)]">›</span>
            <span className="text-[var(--ink)] font-bold text-[13px] min-w-[56px]">
              Basic
              {tier === "Basic" && <span className="text-[var(--ink-3)] text-[10.5px] ml-1.5"> (현재 이용 중)</span>}
            </span>
            <span className="text-[var(--ink-2)] text-[12px] whitespace-nowrap text-right ml-auto">4.9만원 / 월</span>
            <span className="text-[var(--ink-3)] text-[11.5px] col-span-full mt-0.5 ml-[22px]">월 20건 · 수정 권고안 제공 · 검사 이력 무제한</span>
          </div>
          <div className={`grid grid-cols-[auto_auto_1fr] gap-[10px] items-baseline p-2.5 border-b border-[var(--line)] last:border-b-0 ${tier === "Pro" ? "bg-[var(--nav-active-bg)]" : ""}`}>
            <span className="text-[var(--brand-ink)]">›</span>
            <span className="text-[var(--ink)] font-bold text-[13px] min-w-[56px]">
              Pro
              {tier === "Pro" && <span className="text-[var(--ink-3)] text-[10.5px] ml-1.5"> (현재 이용 중)</span>}
            </span>
            <span className="text-[var(--ink-2)] text-[12px] whitespace-nowrap text-right ml-auto">14.9만원 / 월</span>
            <span className="text-[var(--ink-3)] text-[11.5px] col-span-full mt-0.5 ml-[22px]">검사 무제한 · 콘텐츠 생성 월 5회 · 이력 통합 대시보드</span>
          </div>
          <div className="p-2.5 border-t border-dashed border-[var(--line-2)] text-[var(--ink-2)] text-[12px]">
            <b className="text-[var(--ink)] font-bold">Export 애드온</b> <span className="text-[var(--brand-ink)]">건당 4.9만원</span> · 리포트를 PDF로 내보내기 (모든 요금제에 추가 가능)
          </div>
        </div>
      </Modal>
    </>
  );
}
