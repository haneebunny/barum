"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { PageFooter } from "@/components/PageFooter/PageFooter";


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

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      closeModal();
    }
  };

  useEffect(() => {
    if (!isModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isModalOpen]);

  useEffect(() => {
    if (isModalOpen) {
      closeBtnRef.current?.focus();
    } else {
      triggerRef.current?.focus();
    }
  }, [isModalOpen]);

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
      {/* 알림 바: 대기 건수 0이면 자동 숨김(상시 빨강 아님). data-count로 제어 */}
      {needCount > 0 && (
        <div className="needbar" id="needbar" data-count={needCount}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
            <path d="M12 3 2 20h20L12 3z" />
            <path d="M12 10v4M12 17v.5" />
          </svg>
          <span>
            <b>확인 안 한 항목 {needCount}건.</b> 게시 전 검토해 주세요.
          </span>
          <span
            className="go"
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
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
        </div>
      )}

      <div className="hero">
        <div className="eyebrow">
          <span className="dotpulse"></span>바름 · 셀프서비스 규제 검증
        </div>
        <h1>
          게시하기 전에, 규제부터 확인하세요
          <span className="cursor" aria-hidden="true"></span>
        </h1>
        <p>
          상세페이지와 광고 문구를 검사해 위반 위험을 조항, 근거와 함께 보여드려요. 원하면 위험을 낮춘 수정 권고안까지
          만들어드립니다.
        </p>
      </div>

      <div className="doorwrap">
        <div className="doors">
          <div
            className="door"
            role="button"
            tabIndex={0}
            onClick={handleDomesticClick}
            onKeyDown={handleDomesticKeyDown}
            aria-label="국내 광고 검증 시작"
          >
            <div className="dtop">
              <span className="dno">KR</span>
              <span>국내 · 화장품법 기준</span>
            </div>
            <div className="dbody">
              <div className="glyph">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                  <circle cx={11} cy={11} r={7} />
                  <path d="M16 16l5 5" />
                </svg>
              </div>
              <h3>
                국내 광고를
                <br />
                검증할래요
              </h3>
              <p>상세페이지, 광고 문구, 제품 정보를 넣으면 화장품법 기준으로 위반 위험을 조항, 근거와 함께 찾아드려요.</p>
              <div className="inp">
                <span className="ic">이미지</span>
                <span className="ic">문구</span>
                <span className="ic">제품정보</span>
              </div>
              <div className="cta">
                <span>국내 검증 시작</span>
                <span className="mono">→</span>
              </div>
            </div>
          </div>

          <div
            className="door"
            role="button"
            tabIndex={0}
            onClick={handleOverseasClick}
            onKeyDown={handleOverseasKeyDown}
            aria-label="해외 수출용 광고 검증 시작"
          >
            <div className="dtop">
              <span className="dno">EX</span>
              <span>해외 · 수출 대상국 기준</span>
            </div>
            <div className="dbody">
              <div className="glyph">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                  <circle cx={12} cy={12} r={9} />
                  <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
                </svg>
              </div>
              <h3>
                해외 수출용으로
                <br />
                검증할래요
              </h3>
              <p>같은 자료에 대상국만 고르면 미국 수출 기준으로 먼저 검증해드려요. 다른 국가는 순차 지원 예정입니다.</p>
              <div className="region">
                대상국{" "}
                <span
                  className="sel"
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
              <div className="inp">
                <span className="ic">이미지</span>
                <span className="ic">문구</span>
                <span className="ic">제품정보</span>
              </div>
              <div className="cta">
                <span>해외 검증 시작</span>
                <span className="mono">→</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="recent">
        <div className="seclabel">
          <span className="n">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="square">
              <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
              <path d="M3 3v5h5" />
            </svg>
          </span>
          <h2>이어서 하기</h2>
          <span className="rule"></span>
          <span className="hint">최근 프로젝트 3</span>
        </div>

        <Link href="/report/demo-id-1" className="rrow">
          <span className="rname">글로우 세럼 · 미국 상세페이지</span>
          <span className="rtag">해외 · 미국</span>
          <span className="rstat need">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
              <path d="M12 3 2 20h20L12 3z" />
              <path d="M12 10v4M12 17v.5" />
            </svg>
            검토 필요
          </span>
          <span className="raction">리포트 다시 보기</span>
          <span className="rupd">방금</span>
        </Link>

        <Link href="/report/demo-id-2" className="rrow">
          <span className="rname">수분 크림 리뉴얼 상세페이지</span>
          <span className="rtag">국내</span>
          <span className="rstat done">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="square">
              <path d="M4 12l5 5L20 6" />
            </svg>
            검사 완료
          </span>
          <span className="raction">리포트 다시 보기</span>
          <span className="rupd">2일 전</span>
        </Link>

        <Link href="/inspect?id=demo-id-3" className="rrow">
          <span className="rname">선크림 SPF50 신제품</span>
          <span className="rtag">해외 · 미국·EU</span>
          <span className="rstat">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="square">
              <path d="M12 20h9" />
              <path d="M14 4l6 6L8 22H2v-6L14 4z" />
            </svg>
            작성중
          </span>
          <span className="raction">이어서 작성</span>
          <span className="rupd">어제</span>
        </Link>
      </div>

      <PageFooter />

      {/* 대상국 선택 모달 (터미널 다이얼로그, 전부 모노) - React State 바인딩 */}
      {isModalOpen && (
        <div className="modal-backdrop" id="regionModal" onClick={handleBackdropClick}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="rmTitle">
            <div className="modal-head">
              <span id="rmTitle">[ 대상국 선택 ]</span>
              <button
                className="modal-x"
                id="rmClose"
                aria-label="닫기"
                ref={closeBtnRef}
                onClick={closeModal}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <button
                className={`opt ${selectedRegion === "미국 FDA·FTC" ? "on" : ""}`}
                data-v="미국 FDA·FTC"
                onClick={() => selectRegion("미국 FDA·FTC")}
              >
                <span className="rc">›</span> 미국 <span className="rd">FDA · FTC</span>
              </button>
              <button className="opt" disabled title="준비 중">
                <span className="rc">›</span> 유럽연합 <span className="rd">준비 중</span>
              </button>
              <button className="opt" disabled title="준비 중">
                <span className="rc">›</span> 일본 <span className="rd">준비 중</span>
              </button>
              <button className="opt" disabled title="준비 중">
                <span className="rc">›</span> 중국 <span className="rd">준비 중</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
