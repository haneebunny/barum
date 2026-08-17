"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { Modal } from "@/components/Modal/Modal";

export default function HomePage() {
  const router = useRouter();
  const [selectedRegion, setSelectedRegion] = useState("미국 FDA·FTC");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [needCount, setNeedCount] = useState(2);

  const triggerRef = useRef<HTMLSpanElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const openModal = (e?: React.MouseEvent | React.KeyboardEvent) => {
    e?.stopPropagation();
    e?.preventDefault();
    setIsModalOpen(true);
  };
  const closeModal = () => setIsModalOpen(false);

  const selectRegion = (region: string) => {
    setSelectedRegion(region);
    closeModal();
  };

  const handleSelKeyDown = (e: React.KeyboardEvent<HTMLSpanElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openModal(e);
    }
  };

  useEffect(() => {
    if (isModalOpen) {
      closeBtnRef.current?.focus();
    } else {
      triggerRef.current?.focus();
    }
  }, [isModalOpen]);

  // 재방문 기록: 랜딩이 이 값을 보고 CTA를 "내 콘솔로"로 바꾼다
  useEffect(() => {
    try {
      localStorage.setItem("barum-entered", "1");
    } catch {
      // 저장 실패해도 기능엔 지장 없음
    }
  }, []);

  const getInspectUrl = () => {
    if (selectedRegion === "미국 FDA·FTC") {
      return "/inspect?region=us";
    }
    return "/inspect";
  };

  const handleDomesticClick = () => {
    router.push("/inspect");
  };

  const handleDomesticKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      router.push("/inspect");
    }
  };

  const handleOverseasClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest(".sel")) {
      return;
    }
    router.push(getInspectUrl());
  };

  const handleOverseasKeyDown = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest(".sel")) {
      return;
    }
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      router.push(getInspectUrl());
    }
  };

  return (
    <>
      {/* 알림 바: 대기 건수 0이면 자동 숨김. data-count로 제어 */}
      {needCount > 0 && (
        <div className="flex items-center gap-2.5 p-[10px_20px] border-b border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)] text-[13px]" id="needbar" data-count={needCount}>
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
            <path d="M12 3 2 20h20L12 3z" />
            <path d="M12 10v4M12 17v.5" />
          </svg>
          <span>
            <b className="font-bold">확인 안 한 항목 {needCount}건.</b> 게시 전 검토해 주세요.
          </span>
          <span
            className="ml-auto text-[var(--crit)] font-bold cursor-pointer inline-flex items-center gap-1 text-[12.5px]"
            role="button"
            tabIndex={0}
            onClick={() => router.push("/report/demo-id-1")}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                router.push("/report/demo-id-1");
              }
            }}
          >
            보기
            <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
        </div>
      )}

      {/* 랜딩에서 설득이 끝난 사람의 작업 화면: 마케팅 카피 없이 얇은 한 줄만 */}
      <div className="p-[26px_22px_4px] flex items-baseline gap-[10px]">
        <h1 className="m-0 text-[var(--ink)] text-[17px] font-extrabold tracking-[-0.3px]">
          무엇을 검사할까요?
          <span className="inline-block w-[0.14em] h-[1em] bg-[var(--brand-ink)] ml-1.5 align-[-2px] animate-[blink_1.1s_steps(1)_infinite]" aria-hidden="true"></span>
        </h1>
        <span className="font-mono text-[10.5px] text-[var(--ink-3)]">이미지 · 문구 · 제품정보 중 있는 것만 넣으면 됩니다</span>
      </div>

      <div className="p-[18px_22px_4px]">
        <div className="grid grid-cols-2 gap-[13px]">
          <div
            className="border border-[var(--line-2)] bg-[var(--surface)] flex flex-col cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)] hover:shadow-[inset_0_0_0_1px_var(--brand)]"
            role="button"
            tabIndex={0}
            onClick={handleDomesticClick}
            onKeyDown={handleDomesticKeyDown}
            aria-label="국내 광고 검증 시작"
          >
            <div className="flex items-center gap-2 p-[8px_13px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[10.5px] text-[var(--ink-3)] tracking-[0.3px]">
              <span className="bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold p-[1px_6px]">KR</span>
              <span>국내 · 화장품법 기준</span>
            </div>
            <div className="p-[16px_15px_14px] flex-1 flex flex-col">
              <div className="text-[var(--brand-ink)] mb-[11px]">
                <svg className="w-[26px] h-[26px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                  <circle cx={11} cy={11} r={7} />
                  <path d="M16 16l5 5" />
                </svg>
              </div>
              <h3 className="m-[0_0_6px] text-[17px] text-[var(--ink)] font-bold leading-[1.35] tracking-[-0.3px]">국내 광고 검증</h3>
              <p className="m-[0_0_14px] text-[12.5px] text-[var(--ink-3)] leading-1.6 flex-1">화장품법 기준으로 위반 위험과 조항 근거를 찾아드려요.</p>
              <div className="border-t border-dashed border-[var(--line-2)] pt-3 text-[var(--brand-ink)] font-bold text-[13px] flex items-center justify-between">
                <span>국내 검증 시작</span>
                <span className="font-mono">→</span>
              </div>
            </div>
          </div>

          <div
            className="border border-[var(--line-2)] bg-[var(--surface)] flex flex-col cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)] hover:shadow-[inset_0_0_0_1px_var(--brand)]"
            role="button"
            tabIndex={0}
            onClick={handleOverseasClick}
            onKeyDown={handleOverseasKeyDown}
            aria-label="해외 수출용 광고 검증 시작"
          >
            <div className="flex items-center gap-2 p-[8px_13px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[10.5px] text-[var(--ink-3)] tracking-[0.3px]">
              <span className="bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold p-[1px_6px]">EX</span>
              <span>해외 · 수출 대상국 기준</span>
            </div>
            <div className="p-[16px_15px_14px] flex-1 flex flex-col">
              <div className="text-[var(--brand-ink)] mb-[11px]">
                <svg className="w-[26px] h-[26px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                  <circle cx={12} cy={12} r={9} />
                  <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
                </svg>
              </div>
              <h3 className="m-[0_0_6px] text-[17px] text-[var(--ink)] font-bold leading-[1.35] tracking-[-0.3px]">해외 수출용 검증</h3>
              <p className="m-[0_0_14px] text-[12.5px] text-[var(--ink-3)] leading-1.6 flex-1">같은 자료를 대상국 기준으로 다시 검사해요.</p>
              <div className="flex items-center gap-2 mb-3 text-[12px] text-[var(--ink-3)]">
                대상국{" "}
                <span
                  className="border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] p-[3px_9px] font-mono text-[11px] cursor-pointer transition-all duration-120 hover:border-[var(--ink-3)]"
                  role="button"
                  tabIndex={0}
                  ref={triggerRef}
                  onClick={openModal}
                  onKeyDown={handleSelKeyDown}
                  aria-haspopup="dialog"
                  aria-expanded={isModalOpen}
                >
                  {selectedRegion} ▾
                </span>
              </div>
              <div className="border-t border-dashed border-[var(--line-2)] pt-3 text-[var(--brand-ink)] font-bold text-[13px] flex items-center justify-between">
                <span>해외 검증 시작</span>
                <span className="font-mono">→</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="p-[22px_22px_8px]">
        <div className="flex items-center gap-[11px] m-[0_0_13px]">
          <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">
            <svg className="w-3.25 h-3.25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="square">
              <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
              <path d="M3 3v5h5" />
            </svg>
          </span>
          <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">이어서 하기</h2>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
          <span className="text-[var(--ink-3)] font-mono text-[10.5px]">최근 프로젝트 3</span>
        </div>

        <Link href="/report/demo-id-1" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-[13px] border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] mb-[7px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
          <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">글로우 세럼 · 미국 상세페이지</span>
          <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">해외 · 미국</span>
          <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--crit)] border-[var(--crit-bd)] bg-[var(--crit-bg)] font-semibold">
            <svg className="w-3.25 h-3.25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
              <path d="M12 3 2 20h20L12 3z" />
              <path d="M12 10v4M12 17v.5" />
            </svg>
            검토 필요
          </span>
          <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
          <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">방금</span>
        </Link>

        <Link href="/report/demo-id-2" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-[13px] border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] mb-[7px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
          <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">수분 크림 리뉴얼 상세페이지</span>
          <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">국내</span>
          <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--ink-2)] border-[var(--line-2)]">
            <svg className="w-3.25 h-3.25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
              <path d="M4 12l5 5L20 6" />
            </svg>
            검사 완료
          </span>
          <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">리포트 다시 보기</span>
          <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">2일 전</span>
        </Link>

        <Link href="/inspect?id=demo-id-3" className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-[13px] border border-[var(--line)] bg-[var(--surface)] p-[11px_14px] mb-[7px] cursor-pointer no-underline transition-all duration-150 hover:border-[var(--brand)]">
          <span className="text-[var(--ink)] font-semibold text-[13.5px] truncate min-w-0">선크림 SPF50 신제품</span>
          <span className="font-mono text-[10.5px] border border-[var(--line-2)] p-[2px_7px] text-[var(--ink-3)] whitespace-nowrap">해외 · 미국·EU</span>
          <span className="inline-flex items-center gap-[5px] text-[11.5px] p-[2px_9px] border border-[var(--line-2)] whitespace-nowrap text-[var(--ink-3)]">
            <svg className="w-3.25 h-3.25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="square">
              <path d="M12 20h9" />
              <path d="M14 4l6 6L8 22H2v-6L14 4z" />
            </svg>
            작성중
          </span>
          <span className="font-mono text-[11px] text-[var(--ink-3)] whitespace-nowrap">이어서 작성</span>
          <span className="text-[var(--ink-3)] font-mono text-[10.5px] whitespace-nowrap">어제</span>
        </Link>
      </div>

      <PageFooter />

      <Modal
        isOpen={isModalOpen}
        title="대상국 선택"
        onClose={closeModal}
        ref={closeBtnRef}
      >
        <button
          className={`flex items-center gap-[9px] w-full text-left border-0 bg-transparent text-[var(--ink-2)] font-mono text-[12.5px] p-[9px_10px] cursor-pointer transition-all duration-[120ms] hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] ${
            selectedRegion === "미국 FDA·FTC" ? "bg-[var(--nav-active-bg)] text-[var(--ink)] font-bold" : ""
          }`}
          onClick={() => selectRegion("미국 FDA·FTC")}
        >
          <span className="text-[var(--brand-ink)]">›</span> 미국 <span className="ml-auto text-[var(--ink-3)] text-[11px]">FDA · FTC</span>
        </button>
        <button
          className="flex items-center gap-[9px] w-full text-left border-0 bg-transparent text-[var(--ink-3)] font-mono text-[12.5px] p-[9px_10px] cursor-not-allowed"
          disabled
          title="준비 중"
        >
          <span className="text-[var(--ink-3)]">›</span> 유럽연합 <span className="ml-auto text-[var(--ink-3)] text-[11px]">준비 중</span>
        </button>
        <button
          className="flex items-center gap-[9px] w-full text-left border-0 bg-transparent text-[var(--ink-3)] font-mono text-[12.5px] p-[9px_10px] cursor-not-allowed"
          disabled
          title="준비 중"
        >
          <span className="text-[var(--ink-3)]">›</span> 일본 <span className="ml-auto text-[var(--ink-3)] text-[11px]">준비 중</span>
        </button>
        <button
          className="flex items-center gap-[9px] w-full text-left border-0 bg-transparent text-[var(--ink-3)] font-mono text-[12.5px] p-[9px_10px] cursor-not-allowed"
          disabled
          title="준비 중"
        >
          <span className="text-[var(--ink-3)]">›</span> 중국 <span className="ml-auto text-[var(--ink-3)] text-[11px]">준비 중</span>
        </button>
      </Modal>
    </>
  );
}
