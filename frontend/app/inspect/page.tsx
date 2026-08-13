"use client";

import { useState, useRef, useEffect, ChangeEvent, KeyboardEvent, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { checkAd } from "@/lib/api/client";
import { UploadSimple, Check, X } from "@phosphor-icons/react";
import { PageFooter } from "@/components/PageFooter/PageFooter";

interface FileItem {
  id: string;
  name: string;
  ext: string;
  file?: File;
}

function InspectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const regionParam = searchParams.get("region")?.toUpperCase() === "US" ? "US" : "KR";
  const idParam = searchParams.get("id") || "";

  const isSunscreenDraft = idParam === "demo-id-3";

  const [adText, setAdText] = useState(
    isSunscreenDraft
      ? "자외선 차단 100%! 피부 재생 및 기미·주근깨 완벽 치료하는 선크림 SPF50"
      : ""
  );
  const [ingText, setIngText] = useState(
    isSunscreenDraft
      ? "정제수, 티타늄디옥사이드, 아연옥사이드, 부틸렌글라이콜, 글리세린"
      : ""
  );
  const [adFiles, setAdFiles] = useState<FileItem[]>(
    isSunscreenDraft
      ? [{ id: "ad-file-draft", name: "선크림_기획안", ext: ".pdf" }]
      : [
          { id: "ad-file-1", name: "신제품_광고안", ext: ".jpg" },
          { id: "ad-file-2", name: "상세페이지_v2", ext: ".pdf" },
        ]
  );
  const [pFiles, setPFiles] = useState<FileItem[]>(
    isSunscreenDraft
      ? []
      : [{ id: "p-file-1", name: "성분표_전성분", ext: ".xlsx" }]
  );

  const [inspectStatus, setInspectStatus] = useState<"running" | "done" | null>(null);
  const status = inspectStatus || (adText.trim().length > 0 || adFiles.length > 0 ? "ready" : "idle");

  const [isDragging, setIsDragging] = useState(false);

  const [logs, setLogs] = useState<Array<{ ts: string; msg: React.ReactNode }>>([
    {
      ts: "--:--:--",
      msg: <span className="dim">검사 실행을 누르면 분석이 시작됩니다.</span>,
    },
  ]);
  const [resultId, setResultId] = useState<string | null>(null);
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs]);

  const adFileInputRef = useRef<HTMLInputElement>(null);
  const pFileInputRef = useRef<HTMLInputElement>(null);

  const handleAdTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setAdText(e.target.value);
  };

  const handleIngTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setIngText(e.target.value);
  };

  const addFilesToList = (files: FileList | null, isProductInfo: boolean) => {
    if (!files) return;
    const newItems: FileItem[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const lastDot = file.name.lastIndexOf(".");
      let name = file.name;
      let ext = "";
      if (lastDot !== -1) {
        name = file.name.substring(0, lastDot);
        ext = file.name.substring(lastDot);
      }
      newItems.push({
        id: `${isProductInfo ? "p" : "ad"}-file-${Date.now()}-${i}-${Math.random()}`,
        name,
        ext,
        file,
      });
    }
    if (isProductInfo) {
      setPFiles((prev) => [...prev, ...newItems]);
    } else {
      setAdFiles((prev) => [...prev, ...newItems]);
    }
  };

  const handleFileAdd = (e: ChangeEvent<HTMLInputElement>, isProductInfo: boolean) => {
    addFilesToList(e.target.files, isProductInfo);
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (status === "running") return;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (status === "running") return;
    addFilesToList(e.dataTransfer.files, false);
  };

  const removeAdFile = (id: string) => {
    setAdFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const removePFile = (id: string) => {
    setPFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleReset = () => {
    setAdText("");
    setIngText("");
    setAdFiles([]);
    setPFiles([]);
    setInspectStatus(null);
    setResultId(null);
    setLogs([
      {
        ts: "--:--:--",
        msg: <span className="dim">검사 실행을 누르면 분석이 시작됩니다.</span>,
      },
    ]);
  };

  const getTimestamp = () => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  };



  const handleRun = async () => {
    if (status === "running" || (!adText.trim() && adFiles.length === 0)) return;

    setInspectStatus("running");
    setResultId(null);

    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // API 호출용 파라미터 조립
    const actualImage = adFiles.find((f) => f.file)?.file;
    const ingredients = ingText || pFiles.map((f) => `${f.name}${f.ext}`).join(", ");

    // 1단계: API 호출 시작
    const apiPromise = checkAd({
      region: regionParam,
      adText: adText || undefined,
      image: actualImage,
      ingredients: ingredients || undefined,
    });

    const isImage = adFiles.length > 0;
    const isIngredient = ingText.trim().length > 0 || pFiles.length > 0;

    // 로그 목록 템플릿 빌드용 헬퍼
    const getLog1Msg = () => (
      <span>
        <span className="k">[확인]</span> 자료 확인 중{" "}
        <span className="dim">
          · {isImage ? `이미지 ${adFiles.length}개` : "광고 문구"}
          {isIngredient ? " + 제품 정보" : ""}
        </span>
      </span>
    );
    const getLog2Msg = () => (
      <span>
        <span className="k">[분석]</span> 광고 문구 분석 <span className="bar">██████████</span> <span className="ok">완료</span>
      </span>
    );
    const getLog3Msg = (findingsCount?: number) => (
      <span>
        <span className="k">[대조]</span> 규제 기준 대조 중…{" "}
        {findingsCount !== undefined ? (
          <>
            <span className="risk">{findingsCount}건 감지</span>
            {isIngredient ? <span className="dim"> · 고시원료 매칭 포함</span> : ""}
          </>
        ) : (
          <span className="dim">분석 대기...</span>
        )}
      </span>
    );
    const getLog4Msg = () => (
      <span>
        <span className="k">[근거]</span> 위반 근거 연결 <span className="bar">██████████</span> <span className="ok">완료</span>
      </span>
    );
    const getLog5Msg = (count: number, fileName: string) => (
      <span>
        <span className="k">[근거]</span> 이미지 내 위험 표현 <span className="risk">{count}건</span>{" "}
        <span className="dim">→ {fileName}</span>
      </span>
    );
    const getLog6Msg = () => (
      <span>
        <span className="k">[준비]</span> <span className="ok">수정 권고안 준비 완료</span> <span className="dim">→ 우측 하단 「리포트 보기」</span>
      </span>
    );

    if (reduceMotion) {
      // 모션 감축이 켜진 경우 지연 없이 API 응답을 대기한 뒤 한 번에 출력
      try {
        const report = await apiPromise;
        setResultId(report.result_id);

        const currentLogs: Array<{ ts: string; msg: React.ReactNode }> = [];

        // 1번 로그
        currentLogs.push({ ts: getTimestamp(), msg: getLog1Msg() });
        // 2번 로그
        currentLogs.push({ ts: getTimestamp(), msg: getLog2Msg() });
        // 3번 로그 (API 결과 바인딩)
        currentLogs.push({ ts: getTimestamp(), msg: getLog3Msg(report.findings.length) });
        // 4번 로그
        currentLogs.push({ ts: getTimestamp(), msg: getLog4Msg() });

        // 5번 로그 (이미지가 있고 이미지 위반 건수가 있는 경우)
        const imageFindings = report.findings.filter((f) => f.location?.tile);
        if (isImage && imageFindings.length > 0) {
          const firstImageFinding = imageFindings[0];
          const fileName = firstImageFinding.location?.tile || "상세페이지";
          currentLogs.push({
            ts: getTimestamp(),
            msg: getLog5Msg(imageFindings.length, fileName),
          });
        }

        // 6번 로그
        currentLogs.push({ ts: getTimestamp(), msg: getLog6Msg() });

        setLogs(currentLogs);
        setInspectStatus("done");
      } catch (err) {
        console.error(err);
        setLogs([
          {
            ts: getTimestamp(),
            msg: <span className="risk">[에러] 검사 도중 예외가 발생했습니다. 다시 시도해 주세요.</span>,
          },
        ]);
        setInspectStatus(null);
      }
      return;
    }

    // 모션 감축이 꺼진 경우: 애니메이션 & API 대기 동기화
    setLogs([]); // 기존 로그 비우기

    const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    try {
      // 1번 로그 추가 (즉시)
      setLogs([{ ts: getTimestamp(), msg: getLog1Msg() }]);
      await delay(430);

      // 2번 로그 추가
      setLogs((prev) => [...prev, { ts: getTimestamp(), msg: getLog2Msg() }]);
      await delay(430);

      // 3번 로그 대기 상태로 추가
      setLogs((prev) => [...prev, { ts: getTimestamp(), msg: getLog3Msg() }]);

      // API 완료 대기
      const report = await apiPromise;
      setResultId(report.result_id);

      // API 완료 후 3번 로그 갱신 (결과 바인딩)
      setLogs((prev) => {
        const nextLogs = [...prev];
        nextLogs[2] = { ts: nextLogs[2].ts, msg: getLog3Msg(report.findings.length) };
        return nextLogs;
      });
      await delay(430);

      // 4번 로그 추가
      setLogs((prev) => [...prev, { ts: getTimestamp(), msg: getLog4Msg() }]);
      await delay(430);

      // 5번 로그 추가 (이미지가 있고 이미지 위반 건수가 있는 경우)
      const imageFindings = report.findings.filter((f) => f.location?.tile);
      if (isImage && imageFindings.length > 0) {
        const firstImageFinding = imageFindings[0];
        const fileName = firstImageFinding.location?.tile || "상세페이지";
        const msgNode = getLog5Msg(imageFindings.length, fileName);
        if (msgNode) {
          setLogs((prev) => [...prev, { ts: getTimestamp(), msg: msgNode }]);
          await delay(430);
        }
      }

      // 6번 로그 추가
      setLogs((prev) => [...prev, { ts: getTimestamp(), msg: getLog6Msg() }]);
      setInspectStatus("done");
    } catch (err) {
      console.error(err);
      setLogs((prev) => [
        ...prev,
        {
          ts: getTimestamp(),
          msg: <span className="risk">[에러] 검사 도중 예외가 발생했습니다. 다시 시도해 주세요.</span>,
        },
      ]);
      setInspectStatus(null);
    }
  };

  const triggerAdFileSelect = () => {
    adFileInputRef.current?.click();
  };

  const triggerPFileSelect = () => {
    pFileInputRef.current?.click();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>, action: () => void) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      action();
    }
  };

  return (
    <>
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
        <span className="text-[var(--ink-2)]">
          <Link href="/" className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]">
            홈
          </Link>{" "}
          <span className="text-[var(--ink-3)]">›</span>{" "}
          {regionParam === "US" ? (
            <>
              해외 수출 검증 <span className="text-[var(--ink-3)]">›</span> 미국
            </>
          ) : (
            <>국내 광고 검증</>
          )}
        </span>
        <span className="ml-auto text-[var(--brand-ink)] inline-flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-[var(--brand)]"></span>
          <span id="mstatTxt">
            {status === "idle" && "입력 대기"}
            {status === "ready" && "입력 완료"}
            {status === "running" && "분석 중"}
            {status === "done" && "분석 완료"}
          </span>
        </span>
      </div>

      <div className="grid grid-cols-[1.02fr_0.98fr] max-[900px]:grid-cols-1">
        {/* 좌: 자료 투입 */}
        <div className="p-[18px_20px_22px] border-r border-[var(--line)] max-[900px]:border-r-0 max-[900px]:border-b max-[900px]:border-[var(--line)]">
          <div className="mb-5 last:mb-0">
            <div className="flex items-center gap-[11px] m-[0_0_13px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
              <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">검사 대상 · 광고 자료</h2>
              <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
              <span className="text-[var(--ink-3)] font-mono text-[10.5px]">문구 또는 이미지 · 최소 하나</span>
            </div>
            <div>
              <span className="block text-[12px] text-[var(--ink-2)] font-semibold mb-1.5">검사할 광고 문구 붙여넣기</span>
              <textarea
                id="adtext"
                className="w-full min-h-[92px] vertical border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] font-sans text-[13.5px] leading-1.6 p-[11px_12px] outline-none block placeholder:text-[var(--ink-3)] focus:border-[var(--brand)]"
                placeholder="예) 단 4주 만에 여드름 완치! 미국 피부과가 인정한 미백 세럼. 부작용 전혀 없는 100% 순수 성분."
                value={adText}
                onChange={handleAdTextChange}
                disabled={status === "running"}
              />
            </div>
            <div className="flex items-center gap-2.5 text-[var(--ink-3)] font-mono text-[10.5px] m-[13px_0_11px] before:content-[''] before:flex-1 before:border-t before:border-[var(--line)] after:content-[''] after:flex-1 after:border-t after:border-[var(--line)]">
              <span>또는 이미지 첨부</span>
            </div>
            <div
              className={`border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] text-center p-[15px_16px] transition-all duration-[120ms] ${
                status === "running" ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              }`}
              onClick={status === "running" ? undefined : triggerAdFileSelect}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              style={{
                borderColor: isDragging ? "var(--brand)" : undefined,
                borderStyle: isDragging ? "solid" : undefined,
                backgroundColor: isDragging ? "var(--surface)" : undefined,
              }}
              tabIndex={status === "running" ? -1 : 0}
              role="button"
              aria-label="광고 이미지/파일 첨부 영역"
              onKeyDown={(e) => {
                if (status === "running") return;
                handleKeyDown(e, triggerAdFileSelect);
              }}
            >
              <div className="text-[var(--brand-ink)] mb-2.25">
                <UploadSimple size={24} weight="regular" />
              </div>
              <h3 className="m-[0_0_8px] text-[var(--ink)] text-[14px] font-bold">상세페이지 · 광고 이미지 던져넣기</h3>
              <span className="inline-block font-mono text-[11.5px] text-[var(--brand-ink)] bg-[var(--surface)] border border-[var(--line)] p-[7px_11px]">
                drop or click · jpg png pdf xlsx <span className="text-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]">▊</span>
              </span>
            </div>
            <input
              type="file"
              ref={adFileInputRef}
              style={{ display: "none" }}
              multiple
              onChange={(e) => handleFileAdd(e, false)}
            />
            <div className="mt-3 flex flex-col gap-[5px]" id="files">
              {adFiles.map((file) => (
                <div className="flex items-center gap-2.5 bg-[var(--surface-sub)] border border-[var(--line)] p-[8px_10px] font-mono text-[11.5px]" key={file.id}>
                  <Check size={14} weight="bold" className="text-[var(--brand-ink)] font-bold" />
                  <span className="text-[var(--ink)] flex-1">
                    {file.name}
                    <span className="text-[var(--ink-3)]">{file.ext}</span>
                  </span>
                  <span className="text-[var(--brand-ink)] text-[10.5px]">첨부됨</span>
                  <span
                    className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--crit)]"
                    onClick={() => {
                      if (status === "running") return;
                      removeAdFile(file.id);
                    }}
                    tabIndex={status === "running" ? -1 : 0}
                    role="button"
                    aria-label={`${file.name}${file.ext} 파일 삭제`}
                    onKeyDown={(e) => {
                      if (status === "running") return;
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        removeAdFile(file.id);
                      }
                    }}
                  >
                    <X size={14} weight="bold" />
                  </span>
                </div>
              ))}
              <div
                className={`flex items-center gap-2.5 border border-line p-[8px_10px] font-mono text-[11.5px] border-dashed justify-center text-[var(--ink-3)] transition-colors duration-[120ms] ${
                  status === "running" ? "cursor-not-allowed opacity-60" : "cursor-pointer bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
                }`}
                onClick={status === "running" ? undefined : triggerAdFileSelect}
                tabIndex={status === "running" ? -1 : 0}
                role="button"
                aria-label="광고 이미지 파일 추가"
                onKeyDown={(e) => {
                  if (status === "running") return;
                  handleKeyDown(e, triggerAdFileSelect);
                }}
              >
                + 파일 더 추가
              </div>
            </div>
          </div>

          <div className="mb-5 last:mb-0">
            <div className="flex items-center gap-[11px] m-[0_0_13px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
              <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">제품 정보 · 참고자료</h2>
              <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
              <span className="text-[var(--ink-3)] font-mono text-[10.5px]">전성분 · 선택</span>
            </div>
            <div>
              <span className="block text-[12px] text-[var(--ink-2)] font-semibold mb-1.5">전성분 붙여넣기 (함량 % 선택 기재)</span>
              <textarea
                id="ingtext"
                className="w-full min-h-[92px] vertical border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] font-sans text-[13.5px] leading-1.6 p-[11px_12px] outline-none block placeholder:text-[var(--ink-3)] focus:border-[var(--brand)]"
                placeholder="예) 정제수, 나이아신아마이드 5%, 글리세린, 판테놀..."
                value={ingText}
                onChange={handleIngTextChange}
                disabled={status === "running"}
              />
            </div>
            <div className="flex items-center gap-2.5 text-[var(--ink-3)] font-mono text-[10.5px] m-[13px_0_11px] before:content-[''] before:flex-1 before:border-t before:border-[var(--line)] after:content-[''] after:flex-1 after:border-t after:border-[var(--line)]">
              <span>또는 파일 첨부</span>
            </div>
            <input
              type="file"
              ref={pFileInputRef}
              style={{ display: "none" }}
              multiple
              onChange={(e) => handleFileAdd(e, true)}
            />
            <div className="mt-3 flex flex-col gap-[5px]" id="pfiles">
              {pFiles.map((file) => (
                <div className="flex items-center gap-2.5 bg-[var(--surface-sub)] border border-[var(--line)] p-[8px_10px] font-mono text-[11.5px]" key={file.id}>
                  <Check size={14} weight="bold" className="text-[var(--brand-ink)] font-bold" />
                  <span className="text-[var(--ink)] flex-1">
                    {file.name}
                    <span className="text-[var(--ink-3)]">{file.ext}</span>
                  </span>
                  <span className="text-[var(--brand-ink)] text-[10.5px]">첨부됨</span>
                  <span
                    className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--crit)]"
                    onClick={() => {
                      if (status === "running") return;
                      removePFile(file.id);
                    }}
                    tabIndex={status === "running" ? -1 : 0}
                    role="button"
                    aria-label={`${file.name}${file.ext} 파일 삭제`}
                    onKeyDown={(e) => {
                      if (status === "running") return;
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        removePFile(file.id);
                      }
                    }}
                  >
                    <X size={14} weight="bold" />
                  </span>
                </div>
              ))}
              <div
                className={`flex items-center gap-2.5 border border-line p-[8px_10px] font-mono text-[11.5px] border-dashed justify-center text-[var(--ink-3)] transition-colors duration-[120ms] ${
                  status === "running" ? "cursor-not-allowed opacity-60" : "cursor-pointer bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
                }`}
                onClick={status === "running" ? undefined : triggerPFileSelect}
                tabIndex={status === "running" ? -1 : 0}
                role="button"
                aria-label="제품 정보 파일 추가"
                onKeyDown={(e) => {
                  if (status === "running") return;
                  handleKeyDown(e, triggerPFileSelect);
                }}
              >
                + 파일 더 추가
              </div>
            </div>
          </div>

          <div className="mb-5 last:mb-0">
            <div className="flex gap-2.5 mt-0.5">
              <button
                className={`font-sans text-[13px] font-bold p-[11px_16px] border inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] ${
                  status === "running" || status === "idle"
                    ? "bg-[var(--surface-sub)] text-[var(--ink-3)] border-[var(--line-2)] cursor-not-allowed"
                    : "bg-[var(--brand)] text-white border-[var(--brand)] dark:text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-ink)] dark:hover:bg-[#63e89f]"
                }`}
                id="runBtn"
                disabled={status === "running" || status === "idle"}
                onClick={handleRun}
              >
                검사 실행 <span className="font-mono">→</span>
              </button>
              <button
                className={`font-sans text-[13px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] ${
                  status === "running" ? "text-[var(--ink-3)] cursor-not-allowed" : "text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)]"
                }`}
                disabled={status === "running"}
                onClick={handleReset}
              >
                초기화
              </button>
            </div>
          </div>
        </div>

        {/* 우: 실시간 검토 로그 */}
        <div className="p-[18px_20px_22px]">
          <div className="block" style={{ marginBottom: "14px" }}>
            <div className="flex items-center gap-[11px] m-[0_0_13px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">03</span>
              <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">분석 로그</h2>
              <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
              <span className="text-[var(--ink-3)] font-mono text-[10.5px]">실시간</span>
            </div>
            <div className="bg-[var(--surface-sub)] border border-[var(--line-2)] p-[13px_14px] min-h-[250px] font-mono text-[12px] overflow-y-auto" id="log" ref={consoleRef}>
              {logs.map((log, index) => (
                <div key={index} className="flex gap-2.5 p-[2.5px_0] opacity-0 translate-y-[3px] animate-[rise_0.3s_forwards]">
                  <span className="text-[var(--ink-3)] shrink-0 pt-0.25">{log.ts}</span>
                  <span className="break-all">{log.msg}</span>
                </div>
              ))}
            </div>
          </div>
          <button
            className={`font-sans text-[13px] font-bold p-[11px_16px] border w-full inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] ${
              status !== "done"
                ? "bg-[var(--surface-sub)] text-[var(--ink-3)] border-[var(--line-2)] cursor-not-allowed"
                : "bg-[var(--brand)] text-white border-[var(--brand)] dark:text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-ink)] dark:hover:bg-[#63e89f]"
            }`}
            id="toReport"
            disabled={status !== "done"}
            onClick={() => {
              if (status === "done" && resultId) {
                router.push(`/report/${resultId}`);
              }
            }}
          >
            리포트 보기 <span className="font-mono">→</span>
          </button>
        </div>
      </div>

      <PageFooter />
    </>
  );
}

function InspectPageWrapper() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  const region = searchParams.get("region") || "";
  return <InspectContent key={`${id}-${region}`} />;
}

export default function InspectPage() {
  return (
    <Suspense fallback={<div className="devnote" style={{ padding: "20px" }}>로딩 중...</div>}>
      <InspectPageWrapper />
    </Suspense>
  );
}
