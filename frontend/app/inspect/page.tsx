"use client";

import { useState, useEffect, useRef, ChangeEvent, KeyboardEvent, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { checkAd, createExportReadiness } from "@/lib/api/client";
import type { CheckReport, DomesticProductCategory, ExportProfile, ExportReadinessReport, GenericLabelEvidence, GenericProductEvidence, ReadinessInputState } from "@/lib/api/schema";
import { UploadSimple, Check, X, CircleNotch, Warning, Minus } from "@phosphor-icons/react";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { Modal } from "@/components/Modal/Modal";
import { RouteLoading } from "@/components/RouteLoading/RouteLoading";
import { useError } from "@/lib/error/ErrorContext";
import { takeDraft } from "@/lib/draftHandoff";
import { DEFAULT_EXPORT_PROFILE, readExportProfile } from "@/lib/exportProfile";

type NullableBoolean = boolean | null;

function parseNullableBoolean(value: string): NullableBoolean {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

function nullableBooleanValue(value: NullableBoolean): string {
  return value === null ? "" : value ? "true" : "false";
}

function getAnalysisStats(report: CheckReport | ExportReadinessReport) {
  if ("items" in report) {
    return {
      issueCount: report.items.filter((item) => item.status !== "COMPLIANT").length,
      imageFindings: 0,
    };
  }
  return {
    issueCount: report.findings.length,
    imageFindings: report.findings.filter((finding) => finding.location?.tile).length,
  };
}

const CATEGORY_OPTIONS: Array<{ value: DomesticProductCategory; label: string }> = [
  { value: "skincare", label: "기초 화장품" }, { value: "sun_care", label: "선케어·자외선 차단" },
  { value: "cleansing", label: "클렌징" }, { value: "makeup", label: "메이크업" }, { value: "mask_pack", label: "마스크팩" },
  { value: "haircare", label: "헤어케어" }, { value: "bodycare", label: "바디케어" }, { value: "fragrance", label: "향수·향 제품" }, { value: "other", label: "기타" },
];

const EVIDENCE_STATE_OPTIONS: Array<{ value: ReadinessInputState; label: string }> = [
  { value: "PROVIDED", label: "자료 있음" }, { value: "NOT_AVAILABLE", label: "자료 없음" },
  { value: "UNKNOWN", label: "있는지 모름" }, { value: "NOT_ENTERED", label: "나중에 입력" },
];

function evidence(input_state: ReadinessInputState) { return { input_state, evidence: [] }; }

interface FileItem {
  id: string;
  name: string;
  ext: string;
  file?: File;
}

function InspectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { showError } = useError();
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
      : []
  );
  const [pFiles, setPFiles] = useState<FileItem[]>([]);
  const [productName, setProductName] = useState(isSunscreenDraft ? "미국 수출 선스크린 데모" : "");
  const [domesticCategory, setDomesticCategory] = useState<DomesticProductCategory>(isSunscreenDraft ? "sun_care" : "skincare");
  const [domesticSubcategory, setDomesticSubcategory] = useState("");
  const [labelEvidenceState, setLabelEvidenceState] = useState<ReadinessInputState>("NOT_ENTERED");
  const [sunLabelState, setSunLabelState] = useState<ReadinessInputState>("NOT_ENTERED");
  const [sunTestState, setSunTestState] = useState<ReadinessInputState>("NOT_ENTERED");
  const [intendedUse, setIntendedUse] = useState(isSunscreenDraft ? "sunscreen" : "");
  const [spfValue, setSpfValue] = useState("");
  const [spfDisplayed, setSpfDisplayed] = useState<NullableBoolean>(null);
  const [broadSpectrum, setBroadSpectrum] = useState<NullableBoolean>(null);
  const [waterResistant, setWaterResistant] = useState<NullableBoolean>(null);
  const [waterResistanceMinutes, setWaterResistanceMinutes] = useState("");
  const [spfTestReport, setSpfTestReport] = useState<NullableBoolean>(null);
  const [broadSpectrumTestReport, setBroadSpectrumTestReport] = useState<NullableBoolean>(null);
  const [waterResistanceTestReport, setWaterResistanceTestReport] = useState<NullableBoolean>(null);
  const [drugFactsReady, setDrugFactsReady] = useState<NullableBoolean>(null);
  const [claimsReviewed, setClaimsReviewed] = useState<NullableBoolean>(null);
  const [drugListingReady, setDrugListingReady] = useState<NullableBoolean>(null);
  const [exportProfile, setExportProfile] = useState<ExportProfile>(DEFAULT_EXPORT_PROFILE);

  const [inspectStatus, setInspectStatus] = useState<"running" | "done" | null>(null);
  const status = inspectStatus || (adText.trim().length > 0 || adFiles.length > 0 || ingText.trim().length > 0 || productName.trim().length > 0 ? "ready" : "idle");

  useEffect(() => {
    if (regionParam !== "US") return;
    const frame = window.requestAnimationFrame(() => setExportProfile(readExportProfile()));
    return () => window.cancelAnimationFrame(frame);
  }, [regionParam]);

  const [isDragging, setIsDragging] = useState(false);
  const [isDraggingP, setIsDraggingP] = useState(false);
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);

  // 홈 화면에서 붙여넣거나 끌어다 놓은 초안을 그대로 이어받는다 (1단계 입력 UI 자체는 그대로).
  useEffect(() => {
    const draft = takeDraft();
    if (!draft) return;
    const frame = window.requestAnimationFrame(() => {
      if (draft.ad_text) setAdText(draft.ad_text);
      if (draft.files?.length) setAdFiles(draft.files.map((file, i) => {
        const lastDot = file.name.lastIndexOf(".");
        return {
          id: `ad-file-draft-${Date.now()}-${i}`,
          name: lastDot === -1 ? file.name : file.name.substring(0, lastDot),
          ext: lastDot === -1 ? "" : file.name.substring(lastDot),
          file,
        };
      }));
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  interface TaskStep {
    id: number;
    label: string;
    status: "idle" | "running" | "done" | "warn";
    valueText?: string;
  }

  const [steps, setSteps] = useState<TaskStep[]>([
    { id: 1, label: "자료 확인", status: "idle" },
    { id: 2, label: "광고 문구 분석", status: "idle" },
    { id: 3, label: "규제 기준 대조", status: "idle" },
    { id: 4, label: regionParam === "US" ? "이미지 참고자료" : "이미지 내 위험 표현 검사", status: "idle" },
    { id: 5, label: "수정 권고안 준비", status: "idle" },
  ]);
  const [resultId, setResultId] = useState<string | null>(null);
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [steps, isLogModalOpen]);

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

  // 제품 정보(pFiles) 쪽은 광고 이미지 쪽과 별도 드롭 영역이라 상태·핸들러를 따로 둔다
  // (팀장이 겪은 버그: 광고 이미지 쪽만 드롭이 되고 제품 정보 쪽엔 애초에 핸들러가
  // 없었다, 2026-08-23).
  const handleDragOverP = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (status === "running") return;
    setIsDraggingP(true);
  };

  const handleDragLeaveP = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingP(false);
  };

  const handleDropP = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingP(false);
    if (status === "running") return;
    addFilesToList(e.dataTransfer.files, true);
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
    setProductName("");
    setDomesticCategory("skincare");
    setDomesticSubcategory("");
    setLabelEvidenceState("NOT_ENTERED");
    setSunLabelState("NOT_ENTERED");
    setSunTestState("NOT_ENTERED");
    setIntendedUse("");
    setSpfValue("");
    setSpfDisplayed(null);
    setBroadSpectrum(null);
    setWaterResistant(null);
    setWaterResistanceMinutes("");
    setSpfTestReport(null);
    setBroadSpectrumTestReport(null);
    setWaterResistanceTestReport(null);
    setDrugFactsReady(null);
    setClaimsReviewed(null);
    setDrugListingReady(null);
    setInspectStatus(null);
    setResultId(null);
    setIsLogModalOpen(false);
    setSteps([
      { id: 1, label: "자료 확인", status: "idle" },
      { id: 2, label: "광고 문구 분석", status: "idle" },
      { id: 3, label: "규제 기준 대조", status: "idle" },
      { id: 4, label: regionParam === "US" ? "이미지 참고자료" : "이미지 내 위험 표현 검사", status: "idle" },
      { id: 5, label: "수정 권고안 준비", status: "idle" },
    ]);
  };


  const handleRun = async () => {
    const hasInput = adText.trim() || adFiles.length > 0 || ingText.trim() || productName.trim();
    if (status === "running" || !hasInput) return;

    setInspectStatus("running");
    setResultId(null);
    setIsLogModalOpen(true);

    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // API 호출용 파라미터 조립
    const actualImage = adFiles.find((f) => f.file)?.file;
    const ingredients = ingText || pFiles.map((f) => `${f.name}${f.ext}`).join(", ");
    // generic US readiness는 현재 JSON 계약이라 광고 이미지를 전송하지 않는다.
    // 사용자가 이미지가 분석됐다고 오해하지 않도록 해당 진행 단계의 문구를 분리한다.
    const imageAnalysisSupported = regionParam !== "US";

    // 1단계: API 호출 시작 (US면 전용 엔드포인트)
    const apiPromise = regionParam === "US"
      ? createExportReadiness({
          destination_country: "US",
          domestic_category: domesticCategory,
          domestic_subcategory: domesticSubcategory || null,
          product_name: productName || null,
          intended_use: intendedUse || null,
          claims: adText ? [adText] : [],
          ingredients: ingredients ? ingredients.split(",").map((item) => item.trim()).filter(Boolean) : [],
          label_evidence: {
            statement_of_identity: evidence(labelEvidenceState), net_quantity: evidence(labelEvidenceState),
            business_name_address: evidence(labelEvidenceState), ingredient_declaration: evidence(labelEvidenceState),
            english_required_information: evidence(labelEvidenceState), adverse_event_contact: evidence(labelEvidenceState),
          } satisfies GenericLabelEvidence,
          product_evidence: {
            facility_registration: evidence("NOT_ENTERED"), product_listing: evidence("NOT_ENTERED"), safety_substantiation: evidence("NOT_ENTERED"), color_additives: evidence("NOT_ENTERED"),
            spf_test: evidence(sunTestState), broad_spectrum_test: evidence(sunTestState), water_resistance_test: evidence(sunTestState), drug_facts_label: evidence(sunLabelState),
          } satisfies GenericProductEvidence,
          profile_state: Object.values(exportProfile).some((value) => value !== null && value !== "" && value !== undefined) ? "PROVIDED" : "NOT_ENTERED",
          profile: exportProfile,
        })
      : checkAd({
          region: regionParam,
          adText: adText || undefined,
          image: actualImage,
          ingredients: ingredients || undefined,
        });

    const isImage = adFiles.length > 0;

    if (reduceMotion) {
      try {
        const report = await apiPromise;
        const rid = report.result_id ?? `us-${Date.now()}`;
        setResultId(rid);
        if (regionParam === "US") {
          sessionStorage.setItem(`us-readiness-${rid}`, JSON.stringify(report));
        }

        const { issueCount, imageFindings } = getAnalysisStats(report);

        setSteps([
          { id: 1, label: "자료 확인", status: "done", valueText: isImage ? `이미지 ${adFiles.length}개` : "광고 문구" },
          { id: 2, label: "광고 문구 분석", status: "done", valueText: "완료" },
          { id: 3, label: "규제 기준 대조", status: issueCount > 0 ? "warn" : "done", valueText: issueCount > 0 ? `${issueCount}건 확인 필요` : "이상 없음" },
          { id: 4, label: imageAnalysisSupported ? "이미지 내 위험 표현 검사" : "이미지 참고자료", status: imageAnalysisSupported && isImage ? (imageFindings > 0 ? "warn" : "done") : "done", valueText: !imageAnalysisSupported ? (isImage ? "별도 분석 안 함" : "대상 없음") : (isImage ? (imageFindings > 0 ? `${imageFindings}건 감지` : "이상 없음") : "대상 없음") },
          { id: 5, label: "수정 권고안 준비", status: "done", valueText: "준비 완료" },
        ]);
        setInspectStatus("done");
      } catch (err) {
        console.error(err);
        showError("검사 오류", err instanceof Error ? err.message : String(err));
        setSteps(prev => prev.map(s => ({ ...s, status: "warn", valueText: "에러 발생" })));
        setInspectStatus(null);
      }
      return;
    }

    const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    try {
      // 0단계 초기화
      setSteps([
        { id: 1, label: "자료 확인", status: "running" },
        { id: 2, label: "광고 문구 분석", status: "idle" },
        { id: 3, label: "규제 기준 대조", status: "idle" },
        { id: 4, label: imageAnalysisSupported ? "이미지 내 위험 표현 검사" : "이미지 참고자료", status: "idle" },
        { id: 5, label: "수정 권고안 준비", status: "idle" },
      ]);

      // 1단계 애니메이션 진행 후 2단계 시작
      await delay(430);
      setSteps(prev => prev.map(s => {
        if (s.id === 1) return { ...s, status: "done", valueText: isImage ? `이미지 ${adFiles.length}개` : "광고 문구" };
        if (s.id === 2) return { ...s, status: "running" };
        return s;
      }));

      // 2단계 애니메이션 진행 후 3단계 시작
      await delay(430);
      setSteps(prev => prev.map(s => {
        if (s.id === 2) return { ...s, status: "done", valueText: "완료" };
        if (s.id === 3) return { ...s, status: "running" };
        return s;
      }));

      // 3단계: 실제 API 응답 대기
      const report = await apiPromise;
      const rid = report.result_id ?? `us-${Date.now()}`;
      setResultId(rid);
      if (regionParam === "US") {
        sessionStorage.setItem(`us-readiness-${rid}`, JSON.stringify(report));
      }

      const { issueCount, imageFindings } = getAnalysisStats(report);

      // 3단계 완료 처리 후 4단계 시작
      setSteps(prev => prev.map(s => {
        if (s.id === 3) return { ...s, status: issueCount > 0 ? "warn" : "done", valueText: issueCount > 0 ? `${issueCount}건 확인 필요` : "이상 없음" };
        if (s.id === 4) return { ...s, status: "running" };
        return s;
      }));
      await delay(430);

      // 4단계 완료 처리 후 5단계 시작
      setSteps(prev => prev.map(s => {
        if (s.id === 4) return { ...s, status: imageAnalysisSupported && isImage ? (imageFindings > 0 ? "warn" : "done") : "done", valueText: !imageAnalysisSupported ? (isImage ? "별도 분석 안 함" : "대상 없음") : (isImage ? (imageFindings > 0 ? `${imageFindings}건 감지` : "이상 없음") : "대상 없음") };
        if (s.id === 5) return { ...s, status: "running" };
        return s;
      }));
      await delay(430);

      // 5단계 완료 처리
      setSteps(prev => prev.map(s => {
        if (s.id === 5) return { ...s, status: "done", valueText: "준비 완료" };
        return s;
      }));
      setInspectStatus("done");
    } catch (err) {
      console.error(err);
      showError("검사 오류", err instanceof Error ? err.message : String(err));
      setSteps(prev => prev.map(s => {
        if (s.status === "running" || s.status === "idle") {
          return { ...s, status: "warn", valueText: "실패" };
        }
        return s;
      }));
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
          {status === "running" ? (
            <CircleNotch size={12} className="animate-spin text-[var(--brand)]" />
          ) : (
            <span className="w-1.5 h-1.5 bg-[var(--brand)]"></span>
          )}
          <span id="mstatTxt">
            {status === "idle" && "입력 대기"}
            {status === "ready" && "입력 완료"}
            {status === "running" && "분석 중"}
            {status === "done" && "분석 완료"}
          </span>
        </span>
      </div>

      <div className="grid grid-cols-2 max-[900px]:grid-cols-1 border-b border-[var(--line)]">
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
              <div className="text-[var(--brand-ink)] mb-2.25 flex justify-center">
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
                // 드래그오버 시각 효과는 위 큰 드롭존에만 준다 - 여기까지 같이 반응하면
                // 두 영역이 동시에 반짝여 헷갈린다(팀장 지시, 2026-08-23). 드롭 자체는
                // 계속 받는다(핸들러는 유지).
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
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
        </div>

        {/* 우: 제품 정보 · 참고자료 */}
        <div className="p-[18px_20px_22px]">
          <div className="mb-5 last:mb-0">
            <div className="flex items-center gap-[11px] m-[0_0_13px]">
              <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
              <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">제품 정보 · 참고자료</h2>
              <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
              <span className="text-[var(--ink-3)] font-mono text-[10.5px]">전성분 · 선택</span>
            </div>
            {regionParam === "US" && (
              <div className="mb-4 border border-[var(--line-2)] bg-[var(--surface-sub)] p-[13px_14px]">
                <div className="flex items-center gap-2 mb-2.5"><span className="font-mono text-[10.5px] text-[var(--brand-ink)] border border-[var(--line-2)] bg-[var(--surface)] p-[3px_7px]">01–04</span><span className="text-[12px] font-semibold text-[var(--ink)]">선택한 제품에 맞는 준비 항목을 정리하고 있습니다</span></div>
                <div className="grid grid-cols-2 gap-2.5 max-[650px]:grid-cols-1">
                  <label className="text-[11.5px] text-[var(--ink-2)]">국내 판매 카테고리
                    <select className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]" value={domesticCategory} onChange={(event) => setDomesticCategory(event.target.value as DomesticProductCategory)} disabled={status === "running"}>{CATEGORY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
                  </label>
                  <label className="text-[11.5px] text-[var(--ink-2)]">세부 제품 유형 <input className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]" value={domesticSubcategory} onChange={(event) => setDomesticSubcategory(event.target.value)} disabled={status === "running"} placeholder="예: 에센스, 크림, 로션" /></label>
                  <label className="text-[11.5px] text-[var(--ink-2)]">제품명 <input className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]" value={productName} onChange={(event) => setProductName(event.target.value)} disabled={status === "running"} placeholder="제품명" /></label>
                  <label className="text-[11.5px] text-[var(--ink-2)]">미국 판매 목적 <input className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]" value={intendedUse} onChange={(event) => setIntendedUse(event.target.value)} disabled={status === "running"} placeholder="예: 보습, 세정, 자외선 차단" /></label>
                </div>
                <label className="block mt-2.5 text-[11.5px] text-[var(--ink-2)]">미국 판매용 라벨 초안·필수 표기 자료 <select className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]" value={labelEvidenceState} onChange={(event) => setLabelEvidenceState(event.target.value as ReadinessInputState)} disabled={status === "running"}>{EVIDENCE_STATE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                <details className="mt-2 text-[11px] text-[var(--ink-3)]"><summary className="cursor-pointer">왜 필요한가 / 어떤 자료인가 / 모르면 어디에 확인하나</summary><p className="m-[6px_0_0] leading-[1.55]">미국 판매용 라벨의 기본 표기와 연락처를 확인하기 위한 자료입니다. 포장 시안 또는 라벨 PDF를 준비하고, 없으면 디자인·품질 담당자에게 확인하세요.</p></details>
                {domesticCategory === "sun_care" && <div className="mt-3 border-t border-dashed border-[var(--line-2)] pt-3"><p className="m-[0_0_2px] text-[12px] font-semibold text-[var(--ink)]">자외선 차단 제품 추가 확인</p><p className="m-[0_0_2px] text-[11px] text-[var(--ink-3)]">표기와 시험·라벨 자료의 준비 상태만 확인합니다.</p><div className="grid grid-cols-2 gap-2.5 mt-2 max-[650px]:grid-cols-1"><label className="text-[11.5px] text-[var(--ink-2)]">자외선 차단 관련 시험자료 <select className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)]" value={sunTestState} onChange={(event) => setSunTestState(event.target.value as ReadinessInputState)}>{EVIDENCE_STATE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><label className="text-[11.5px] text-[var(--ink-2)]">미국 판매용 라벨 자료 <select className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)]" value={sunLabelState} onChange={(event) => setSunLabelState(event.target.value as ReadinessInputState)}>{EVIDENCE_STATE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label></div></div>}
                <div className="mt-3 border-t border-dashed border-[var(--line-2)] pt-2.5 text-[11px] text-[var(--ink-3)]">{Object.values(exportProfile).some((value) => value !== null && value !== "") ? <>저장된 수출 프로필을 이번 분석에 사용합니다. <Link href="/mypage" className="text-[var(--brand-ink)] underline">수정하기</Link></> : <>저장된 프로필이 없습니다. 프로필 없이 계속할 수 있으며, 제조시설·수입자 관련 준비 항목은 결과에서 안내합니다. <Link href="/mypage" className="text-[var(--brand-ink)] underline">지금 저장하기</Link></>}</div>
              </div>
            )}
            {false && regionParam === "US" && (
              <div className="mb-4 border border-[var(--line-2)] bg-[var(--surface-sub)] p-[13px_14px]">
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="font-mono text-[10.5px] text-[var(--brand-ink)] border border-[var(--line-2)] bg-[var(--surface)] p-[3px_7px]">US READINESS</span>
                  <span className="text-[12px] font-semibold text-[var(--ink)]">제품별 수출 준비 정보</span>
                </div>
                <div className="grid grid-cols-2 gap-2.5 max-[650px]:grid-cols-1">
                  <label className="text-[11.5px] text-[var(--ink-2)]">
                    제품명
                    <input
                      className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                      value={productName}
                      onChange={(e) => setProductName(e.target.value)}
                      disabled={status === "running"}
                      placeholder="미국 수출 제품명"
                    />
                  </label>
                  <label className="text-[11.5px] text-[var(--ink-2)]">
                    의도 용도
                    <select
                      className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                      value={intendedUse}
                      onChange={(e) => setIntendedUse(e.target.value)}
                      disabled={status === "running"}
                    >
                      <option value="">선택하지 않음</option>
                      <option value="sunscreen">자외선차단 제품</option>
                      <option value="other">기타 제품</option>
                    </select>
                  </label>
                  <label className="text-[11.5px] text-[var(--ink-2)]">
                    표시 SPF
                    <input
                      type="number"
                      min="0"
                      className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                      value={spfValue}
                      onChange={(e) => setSpfValue(e.target.value)}
                      disabled={status === "running"}
                      placeholder="예: 50"
                    />
                  </label>
                  <label className="text-[11.5px] text-[var(--ink-2)]">
                    SPF 표시 여부
                    <select
                      className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                      value={nullableBooleanValue(spfDisplayed)}
                      onChange={(e) => setSpfDisplayed(parseNullableBoolean(e.target.value))}
                      disabled={status === "running"}
                    >
                      <option value="">미입력</option><option value="true">예</option><option value="false">아니오</option>
                    </select>
                  </label>
                </div>
                <div className="grid grid-cols-2 gap-2.5 mt-2.5 max-[650px]:grid-cols-1">
                  {[
                    ["Broad Spectrum 표시", broadSpectrum, setBroadSpectrum],
                    ["Water Resistant 표시", waterResistant, setWaterResistant],
                    ["SPF 시험자료", spfTestReport, setSpfTestReport],
                    ["Broad Spectrum 시험자료", broadSpectrumTestReport, setBroadSpectrumTestReport],
                    ["Water Resistance 시험자료", waterResistanceTestReport, setWaterResistanceTestReport],
                    ["Drug Facts / 미국 라벨", drugFactsReady, setDrugFactsReady],
                    ["미국용 claim 검토", claimsReviewed, setClaimsReviewed],
                    ["Drug Listing 준비", drugListingReady, setDrugListingReady],
                  ].map(([label, value, setter]) => (
                    <label key={label as string} className="text-[11.5px] text-[var(--ink-2)]">
                      {label as string}
                      <select
                        className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                        value={nullableBooleanValue(value as NullableBoolean)}
                        onChange={(e) => (setter as React.Dispatch<React.SetStateAction<NullableBoolean>>)(parseNullableBoolean(e.target.value))}
                        disabled={status === "running"}
                      >
                        <option value="">미입력</option><option value="true">예</option><option value="false">아니오</option>
                      </select>
                    </label>
                  ))}
                  <label className="text-[11.5px] text-[var(--ink-2)]">
                    Water Resistant 지속 시간
                    <select
                      className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                      value={waterResistanceMinutes}
                      onChange={(e) => setWaterResistanceMinutes(e.target.value)}
                      disabled={status === "running"}
                    >
                      <option value="">미입력</option><option value="40">40분</option><option value="80">80분</option>
                    </select>
                  </label>
                </div>
                <div className="mt-2.5 border-t border-dashed border-[var(--line-2)] pt-2.5 text-[11px] text-[var(--ink-3)]">
                  저장된 미국 수출 프로필: <span className="text-[var(--ink-2)]">{String(exportProfile.manufacturer_name || exportProfile.legal_manufacturer || "미입력")}</span>{" "}
                  <Link href="/mypage" className="ml-1 text-[var(--brand-ink)] underline">프로필 편집</Link>
                </div>
              </div>
            )}
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
            <div
              className={`border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] text-center p-[15px_16px] transition-all duration-[120ms] ${
                status === "running" ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              }`}
              onClick={status === "running" ? undefined : triggerPFileSelect}
              onDragOver={handleDragOverP}
              onDragLeave={handleDragLeaveP}
              onDrop={handleDropP}
              style={{
                borderColor: isDraggingP ? "var(--brand)" : undefined,
                borderStyle: isDraggingP ? "solid" : undefined,
                backgroundColor: isDraggingP ? "var(--surface)" : undefined,
              }}
              tabIndex={status === "running" ? -1 : 0}
              role="button"
              aria-label="제품 정보/참고자료 첨부 영역"
              onKeyDown={(e) => {
                if (status === "running") return;
                handleKeyDown(e, triggerPFileSelect);
              }}
            >
              <div className="text-[var(--brand-ink)] mb-2.25 flex justify-center">
                <UploadSimple size={24} weight="regular" />
              </div>
              <h3 className="m-[0_0_8px] text-[var(--ink)] text-[14px] font-bold">전성분표 · 참고자료 던져넣기</h3>
              <span className="inline-block font-mono text-[11.5px] text-[var(--brand-ink)] bg-[var(--surface)] border border-[var(--line)] p-[7px_11px]">
                drop or click · xlsx txt pdf
              </span>
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
                // 드래그오버 시각 효과는 위 큰 드롭존에만 준다(팀장 지시, 2026-08-23 -
                // 왼쪽과 같은 이유). 드롭 자체는 계속 받는다.
                onDragOver={handleDragOverP}
                onDragLeave={handleDragLeaveP}
                onDrop={handleDropP}
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
        </div>
      </div>

      {/* 하단 컨트롤 영역 */}
      <div className="p-[16px_20px] bg-[var(--surface-sub)] flex items-center justify-between border-b border-[var(--line)] flex-wrap gap-3">
        <div className="flex gap-2.5">
          <button
            className={`font-sans text-[13px] font-bold p-[11px_16px] border inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] ${
              status === "running" || status === "idle"
                ? "bg-[var(--surface-sub)] text-[var(--ink-3)] border-[var(--line-2)] cursor-not-allowed"
                : "bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)]"
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

        <div className="flex gap-2.5 items-center">
          {(status === "running" || status === "done") && (
            <button
              onClick={() => setIsLogModalOpen(true)}
              className="font-sans text-[13px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)]"
            >
              분석 로그{" "}
              {status === "running" ? (
                <CircleNotch size={14} className="animate-spin text-[var(--brand)]" />
              ) : (
                <span className="w-1.5 h-1.5 bg-[var(--brand)] rounded-full"></span>
              )}
            </button>
          )}

          {status === "done" && (
            <button
              className="font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms]"
              id="toReport"
              onClick={() => {
                if (resultId) {
                  const reportPath = regionParam === "US" ? `/report/us/${resultId}` : `/report/${resultId}`;
                  router.push(reportPath);
                }
              }}
            >
              리포트 보기 <span className="font-mono">→</span>
            </button>
          )}
        </div>
      </div>

      {/* 분석 로그 모달 */}
      <Modal
        isOpen={isLogModalOpen}
        title="분석 로그"
        onClose={() => setIsLogModalOpen(false)}
        size="md"
        footer={
          <div className="flex justify-between items-center w-full font-mono text-[12px]">
            <span className="text-[var(--ink-3)]">
              {status === "running" ? "분석이 진행 중입니다…" : "분석이 완료되었습니다."}
            </span>
            <div className="flex gap-2">
              {status === "done" && (
                <button
                  className="font-sans text-[12px] font-bold p-[7px_14px] bg-[var(--brand)] text-[var(--on-brand)] border border-[var(--brand)] dark:text-[var(--on-brand)] cursor-pointer hover:bg-[var(--brand-deep)] transition-colors"
                  onClick={() => {
                    if (resultId) {
                      const reportPath = regionParam === "US" ? `/report/us/${resultId}` : `/report/${resultId}`;
                      router.push(reportPath);
                    }
                  }}
                >
                  리포트 보기
                </button>
              )}
              <button
                className="font-sans text-[12px] font-semibold p-[7px_14px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] transition-colors"
                onClick={() => setIsLogModalOpen(false)}
              >
                닫기
              </button>
            </div>
          </div>
        }
      >
        <div
          className="bg-[var(--surface-sub)] border border-[var(--line-2)] min-h-[250px] font-sans text-[13px] overflow-y-auto flex flex-col justify-center py-2 w-full"
          id="log"
          ref={consoleRef}
        >
          {steps.map((step) => {
            const isIdle = step.status === "idle";
            const isRunning = step.status === "running";
            const isDone = step.status === "done";
            const isWarn = step.status === "warn";

            return (
              <div
                key={step.id}
                className={`flex items-center justify-between p-[12px_16px] border-b border-[var(--line)] last:border-b-0 transition-opacity duration-300 ${
                  isIdle ? "opacity-50" : "opacity-100"
                }`}
              >
                <div className="flex items-center gap-3">
                  {isIdle && <Minus className="text-[var(--ink-3)]" size={16} />}
                  {isRunning && <CircleNotch className="text-[var(--brand)] animate-spin" size={16} />}
                  {isDone && <Check className="text-[var(--brand-ink)] font-bold" size={16} />}
                  {isWarn && <Warning className="text-[var(--crit)]" size={16} />}
                  
                  <span className={`font-semibold ${isRunning ? "text-[var(--brand-ink)]" : "text-[var(--ink)]"}`}>
                    {step.label}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {isRunning && <span className="text-[var(--brand-ink)] font-mono text-[11px] uppercase tracking-wider">분석 중</span>}
                  {isIdle && <span className="text-[var(--ink-3)] text-[11px]">대기 중</span>}
                  {isDone && (
                    <span className="text-[var(--ink-3)] text-[12px] font-sans">
                      {step.valueText || "완료"}
                    </span>
                  )}
                  {isWarn && (
                    <span className="text-[var(--crit)] font-semibold text-[12px]">
                      {step.valueText || "검토 필요"}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Modal>

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
    <Suspense fallback={<RouteLoading />}>
      <InspectPageWrapper />
    </Suspense>
  );
}
