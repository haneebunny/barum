"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { PageContent } from "@/components/PageContent/PageContent";
import { Modal } from "@/components/Modal/Modal";
import { HistoryRow, HistoryRowList } from "@/components/HistoryRow/HistoryRow";
import { recentHistory, rowProps, type HistoryStatus } from "@/lib/mockHistory";
import { setDraft } from "@/lib/draftHandoff";

type EntryTab = "KR" | "EX";

const CONTINUE_ITEMS = recentHistory(3);

function continueHref(result_id: string, status: HistoryStatus) {
  return status === "draft" ? `/inspect?id=${result_id}` : `/report/${result_id}`;
}

export default function HomePage() {
  const router = useRouter();
  const [selectedRegion, setSelectedRegion] = useState("미국 FDA·FTC");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<EntryTab>("KR");
  const [adText, setAdText] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const triggerRef = useRef<HTMLSpanElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    if (activeTab === "EX" && selectedRegion === "미국 FDA·FTC") {
      return "/inspect?region=us";
    }
    return "/inspect";
  };

  const submitText = (text: string) => {
    if (!text.trim()) return;
    setDraft({ ad_text: text });
    router.push(getInspectUrl());
  };

  const submitFiles = (files: File[]) => {
    if (files.length === 0) return;
    setDraft({ files });
    router.push(getInspectUrl());
  };

  const handlePromptKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitText(adText);
    }
  };

  const handlePromptPaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const text = e.clipboardData.getData("text");
    if (text.trim()) submitText(text);
  };

  const handleDropzoneDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDropzoneDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDropzoneDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    submitFiles(Array.from(e.dataTransfer.files));
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    submitFiles(Array.from(e.target.files ?? []));
  };

  const handleSkipStart = () => {
    router.push(getInspectUrl());
  };

  return (
    <>
      <PageContent>
      {/* 랜딩에서 설득이 끝난 사람의 작업 화면: 마케팅 카피 없이 얇은 한 줄만 */}
      <div className="pt-[26px] pb-[4px] flex flex-col sm:flex-row sm:items-baseline gap-[6px] sm:gap-[10px]">
        <h1 className="m-0 text-[var(--ink)] text-[22px] font-extrabold tracking-[-0.3px] whitespace-nowrap flex items-center gap-2">
          <span className="text-[var(--brand-ink)] font-mono">›</span>
          무엇을 검사할까요?
          <span className="inline-block w-[0.14em] h-[1em] bg-[var(--brand-ink)] align-[-2px] animate-[blink_1.1s_steps(1)_infinite]" aria-hidden="true"></span>
        </h1>
        <span className="font-mono text-[13px] text-[var(--ink-3)]">이미지 · 문구 · 제품정보 중 있는 것만 넣으면 됩니다</span>
      </div>

      <div className="pt-[18px] pb-[4px]">
        <div className="border border-[var(--line-2)] bg-[var(--surface)]">
          {/* 탭 바: KR/EX 기준 전환 */}
          <div className="flex items-center border-b border-[var(--line)] bg-[var(--surface-sub)] overflow-x-auto">
            <button
              type="button"
              onClick={() => setActiveTab("KR")}
              className={`flex items-center gap-2 shrink-0 p-[9px_14px] border-r border-[var(--line)] font-mono text-[11.5px] tracking-[0.3px] transition-colors duration-150 cursor-pointer ${
                activeTab === "KR" ? "bg-[var(--surface)] text-[var(--ink)]" : "bg-transparent text-[var(--ink-3)] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
              }`}
            >
              <span className="bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold p-[1px_6px]">KR</span>
              국내 · 화장품법
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("EX")}
              className={`flex items-center gap-2 shrink-0 p-[9px_14px] border-r border-[var(--line)] font-mono text-[11.5px] tracking-[0.3px] transition-colors duration-150 cursor-pointer ${
                activeTab === "EX" ? "bg-[var(--surface)] text-[var(--ink)]" : "bg-transparent text-[var(--ink-3)] hover:text-[var(--ink)] hover:bg-[var(--nav-hover)]"
              }`}
            >
              <span className="bg-[var(--brand-deep)] text-[var(--on-brand)] font-bold p-[1px_6px]">EX</span>
              해외 수출 ·{" "}
              <span
                role="button"
                tabIndex={0}
                ref={triggerRef}
                onClick={e => {
                  e.stopPropagation();
                  setActiveTab("EX");
                  openModal(e);
                }}
                onKeyDown={handleSelKeyDown}
                aria-haspopup="dialog"
                aria-expanded={isModalOpen}
                className="underline decoration-dashed underline-offset-2 hover:text-[var(--ink)]"
              >
                {selectedRegion} ▾
              </span>
            </button>
            <span className="ml-auto pr-3 font-mono text-[10.5px] text-[var(--ink-3)] hidden sm:inline whitespace-nowrap">
              $ bareum check --{activeTab.toLowerCase()}
            </span>
          </div>

          {/* 문구 프롬프트 + 파일 드롭존 */}
          <div className="p-[16px_18px]">
            <div className="flex items-start gap-2">
              <span className="text-[var(--brand-ink)] font-mono text-[13.5px] leading-[1.6] mt-[1px]">›</span>
              <textarea
                value={adText}
                onChange={e => setAdText(e.target.value)}
                onPaste={handlePromptPaste}
                onKeyDown={handlePromptKeyDown}
                placeholder="검사할 문구를 붙여넣으세요"
                rows={1}
                className="flex-1 resize-none border-0 bg-transparent outline-none font-mono text-[13.5px] text-[var(--ink)] placeholder:text-[var(--ink-3)] leading-[1.6]"
              />
            </div>

            <div
              className={`mt-3 border border-dashed p-[18px_16px] text-center cursor-pointer transition-all duration-150 ${
                isDragging ? "border-[var(--brand)] bg-[var(--surface)]" : "border-[var(--line-2)] bg-[var(--surface-sub)]"
              }`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={handleDropzoneDragOver}
              onDragLeave={handleDropzoneDragLeave}
              onDrop={handleDropzoneDrop}
              role="button"
              tabIndex={0}
              aria-label="이미지·파일 첨부"
              onKeyDown={e => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
            >
              <div className="text-[var(--brand-ink)] mb-2 flex justify-center">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
                  <path d="M12 19V5M12 5l-5 5M12 5l5 5" />
                </svg>
              </div>
              <p className="m-0 text-[13.5px] text-[var(--ink-2)]">
                이미지·파일은 여기로 끌어다 놓거나{" "}
                <span className="text-[var(--brand-ink)] font-semibold underline underline-offset-2">파일 선택</span>
              </p>
              <p className="mt-1 mb-0 font-mono text-[10.5px] text-[var(--ink-3)]">PNG · JPG · PDF · 여러 장 가능</p>
              <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileInputChange} />
            </div>
          </div>

          {/* 하단 안내 */}
          <div className="flex items-center justify-between gap-3 p-[9px_18px] border-t border-dashed border-[var(--line-2)] flex-wrap">
            <span className="font-mono text-[10.5px] text-[var(--ink-3)]">
              붙여넣거나 끌어다 놓는 순간 검사 준비로 넘어가요 · 기준은 나중에 탭으로 바꿔 다시 검사할 수 있어요
            </span>
            <button
              type="button"
              onClick={handleSkipStart}
              className="shrink-0 font-mono text-[11px] font-bold text-[var(--brand-ink)] bg-transparent border-0 cursor-pointer hover:underline"
            >
              자료 없이 시작 →
            </button>
          </div>
        </div>
      </div>

      <div className="pt-[22px] pb-[8px]">
        <div className="flex items-center gap-[11px] m-[0_0_13px]">
          <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">
            <svg className="w-3.25 h-3.25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="square">
              <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
              <path d="M3 3v5h5" />
            </svg>
          </span>
          <h2 className="m-0 text-[15px] font-bold text-[var(--ink)] tracking-[-0.2px]">이어서 하기</h2>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
          <span className="text-[var(--ink-3)] font-mono text-[12px]">최근 프로젝트 3</span>
        </div>

        <HistoryRowList>
          {CONTINUE_ITEMS.map(item => {
            return (
              <HistoryRow
                key={item.result_id}
                href={continueHref(item.result_id, item.status)}
                {...rowProps(item)}
              />
            );
          })}
        </HistoryRowList>
      </div>
      </PageContent>

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
