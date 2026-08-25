"use client";

import { useState, useEffect, useRef, ChangeEvent, KeyboardEvent, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { checkAd, checkUSPreflight, getReport, getReports, uploadIngredients } from "@/lib/api/client";
import type { CheckReport, DomesticInputSnapshot, ReportEnvelope, ReportListItem, USPreflightReport } from "@/lib/api/schema";
import { UploadSimple, Check, X, CircleNotch, Warning, Minus } from "@phosphor-icons/react";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { Modal } from "@/components/Modal/Modal";
import { RouteLoading } from "@/components/RouteLoading/RouteLoading";
import { useError } from "@/lib/error/ErrorContext";
import { takeDraft } from "@/lib/draftHandoff";

function getAnalysisStats(report: CheckReport | USPreflightReport) {
  return {
    issueCount: report.findings.length,
    imageFindings: report.findings[0] && "location" in report.findings[0] ? report.findings.filter((finding) => finding.location?.tile).length : 0,
  };
}

const CATEGORY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "skincare", label: "기초 화장품" }, { value: "sun_care", label: "선케어·자외선 차단" },
  { value: "cleansing", label: "클렌징" }, { value: "makeup", label: "메이크업" }, { value: "mask_pack", label: "마스크팩" },
  { value: "haircare", label: "헤어케어" }, { value: "bodycare", label: "바디케어" }, { value: "fragrance", label: "향수·향 제품" }, { value: "other", label: "기타" },
];

function formatReportDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" });
}

function getSnapshot(envelope: ReportEnvelope | null): DomesticInputSnapshot | null {
  return envelope?.input_snapshot ?? null;
}

function categoryLabel(value: string | null | undefined): string {
  return CATEGORY_OPTIONS.find((option) => option.value === value)?.label || value || "분류 미입력";
}
import { TicketCheckoutModal } from "@/components/TicketCheckout/TicketCheckoutModal";
import { useDailyChecks, useTickets } from "@/lib/tickets";

interface FileItem {
  id: string;
  name: string;
  ext: string;
  file?: File;
  ingredientParseStatus?: "uploading" | "done" | "error";
  ingredientRows?: Array<{ name: string; amount: string }>;
  ingredientWarnings?: string[];
  ingredientError?: string;
}

const INGREDIENT_FILE_EXTENSIONS = new Set([".xlsx", ".csv", ".txt"]);
const AD_IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".webp"]);
const AD_IMAGE_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function getFileParts(file: File): Pick<FileItem, "name" | "ext"> {
  const lastDot = file.name.lastIndexOf(".");
  return {
    name: lastDot === -1 ? file.name : file.name.substring(0, lastDot),
    ext: lastDot === -1 ? "" : file.name.substring(lastDot),
  };
}

function isSupportedAdImage(file: File): boolean {
  const { ext } = getFileParts(file);
  return AD_IMAGE_EXTENSIONS.has(ext.toLowerCase())
    && (!file.type || AD_IMAGE_MIME_TYPES.has(file.type.toLowerCase()));
}

function createLocalReportId(region: "US" | "KR"): string {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${region.toLowerCase()}-local-${suffix}`;
}

function cacheUSPreflight(resultId: string, report: USPreflightReport): void {
  try {
    window.sessionStorage.setItem(`us-preflight-${resultId}`, JSON.stringify(report));
  } catch (error) {
    console.warn("미국 프리플라이트 결과를 임시 저장하지 못했습니다.", error);
  }
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
  const [adFiles, setAdFiles] = useState<FileItem[]>([]);
  const [adFileError, setAdFileError] = useState<string | null>(null);
  const [pFiles, setPFiles] = useState<FileItem[]>([]);
  const [ingredientFileError, setIngredientFileError] = useState<string | null>(null);
  const [productName, setProductName] = useState(isSunscreenDraft ? "미국 수출 선스크린 데모" : "");
  const [domesticReports, setDomesticReports] = useState<ReportListItem[]>([]);
  const [domesticReportsLoading, setDomesticReportsLoading] = useState(false);
  const [domesticReportsAvailable, setDomesticReportsAvailable] = useState(true);
  const [selectedDomesticReportId, setSelectedDomesticReportId] = useState<string | null>(null);
  const [selectedDomesticReport, setSelectedDomesticReport] = useState<ReportEnvelope | null>(null);
  const [selectedDomesticReportLoading, setSelectedDomesticReportLoading] = useState(false);
  const [selectedDomesticReportError, setSelectedDomesticReportError] = useState<string | null>(null);
  const [inspectStatus, setInspectStatus] = useState<"running" | "done" | null>(null);
  const selectedSnapshot = getSnapshot(selectedDomesticReport);
  const hasImportedSource = Boolean(selectedDomesticReportId && selectedSnapshot);
  const importedClaims = selectedSnapshot
    ? [selectedSnapshot.ad_text_raw, ...selectedSnapshot.ocr_sentences.map((sentence) => sentence.text)]
      .filter((value): value is string => Boolean(value?.trim()))
      .join("\n")
    : "";
  const directRasterImage = adFiles.find((item) => item.file && isSupportedAdImage(item.file))?.file;
  const hasAnalysisSource = hasImportedSource
    ? importedClaims.trim().length > 0
    : adText.trim().length > 0 || Boolean(directRasterImage);
  const status = inspectStatus || (hasAnalysisSource ? "ready" : "idle");
  const importedInputsDisabled = status === "running" || hasImportedSource;

  useEffect(() => {
    if (regionParam !== "US") return;
    let active = true;
    const frame = window.requestAnimationFrame(() => {
      setDomesticReportsLoading(true);
      setDomesticReportsAvailable(true);
      getReports("KR")
        .then((reports) => {
          if (active) {
            setDomesticReports(reports);
            setDomesticReportsAvailable(true);
          }
        })
        .catch((error) => {
          console.warn("국내 검사 결과 재사용 기능을 사용할 수 없어 직접 입력으로 전환합니다.", error);
          if (active) setDomesticReportsAvailable(false);
        })
        .finally(() => {
          if (active) setDomesticReportsLoading(false);
        });
    });
    return () => {
      active = false;
      window.cancelAnimationFrame(frame);
    };
  }, [regionParam]);

  const [isDragging, setIsDragging] = useState(false);
  const [isDraggingP, setIsDraggingP] = useState(false);
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);

  // 실행 게이팅. 국내는 하루 3회까지 무료고, 소진 후에도 이용권이 있으면 돌릴 수 있다.
  // 해외 프리플라이트는 무료 체험이 없어서 처음부터 이용권을 요구한다.
  // 이용권 차감 자체는 리포트를 열 때 일어난다(무료 요약을 나중에 업그레이드하는 흐름 때문).
  const daily = useDailyChecks();
  const { has } = useTickets();
  const [isBlockedOpen, setIsBlockedOpen] = useState(false);
  const isUS = regionParam === "US";
  const hasPaidTicket = isUS ? has("overseas") : has("domestic") || has("combo");
  const canRunCheck = isUS ? hasPaidTicket : daily.canRunFreeCheck || hasPaidTicket;

  // 홈 화면에서 붙여넣거나 끌어다 놓은 초안을 그대로 이어받는다 (1단계 입력 UI 자체는 그대로).
  useEffect(() => {
    const draft = takeDraft();
    if (!draft) return;
    const frame = window.requestAnimationFrame(() => {
      if (draft.ad_text) setAdText(draft.ad_text);
      if (draft.files?.length) {
        const image = draft.files.find(isSupportedAdImage);
        if (image) {
          setAdFiles([{ id: `ad-file-draft-${Date.now()}`, ...getFileParts(image), file: image }]);
        }
        const rejected = draft.files.filter((file) => !isSupportedAdImage(file));
        if (rejected.length > 0 || draft.files.length > 1) {
          setAdFileError(image
            ? "광고 이미지는 JPG, PNG, WEBP 중 1개만 사용할 수 있습니다. 지원되는 첫 이미지만 가져왔습니다."
            : "초안의 첨부 파일은 지원하지 않습니다. JPG, PNG, WEBP 이미지 중 1개를 다시 첨부해 주세요.");
        }
      }
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
      newItems.push({
        id: `${isProductInfo ? "p" : "ad"}-file-${Date.now()}-${i}-${Math.random()}`,
        ...getFileParts(file),
        file,
        ingredientParseStatus: isProductInfo ? "uploading" : undefined,
      });
    }
    if (isProductInfo) {
      const supportedItems = newItems.filter((item) => INGREDIENT_FILE_EXTENSIONS.has(item.ext.toLowerCase()));
      const rejectedItems = newItems.filter((item) => !INGREDIENT_FILE_EXTENSIONS.has(item.ext.toLowerCase()));
      setIngredientFileError(
        rejectedItems.length > 0
          ? `지원하지 않는 파일은 제외했습니다: ${rejectedItems.map((item) => `${item.name}${item.ext}`).join(", ")}. xlsx, csv, txt만 첨부할 수 있습니다.`
          : null,
      );
      if (supportedItems.length === 0) return;

      setPFiles((prev) => [...prev, ...supportedItems]);
      supportedItems.forEach((item) => {
        if (!item.file) return;
        void uploadIngredients(item.file)
          .then((response) => {
            setPFiles((current) => current.map((fileItem) => fileItem.id === item.id
              ? {
                  ...fileItem,
                  ingredientParseStatus: "done",
                  ingredientRows: response.rows,
                  ingredientWarnings: response.warnings,
                  ingredientError: undefined,
                }
              : fileItem));
          })
          .catch((error) => {
            setPFiles((current) => current.map((fileItem) => fileItem.id === item.id
              ? {
                  ...fileItem,
                  ingredientParseStatus: "error",
                  ingredientRows: [],
                  ingredientWarnings: [],
                  ingredientError: error instanceof Error ? error.message : "파일을 해석하지 못했습니다.",
                }
              : fileItem));
          });
      });
    } else {
      const supportedItems = newItems.filter((item) => item.file && isSupportedAdImage(item.file));
      const rejectedItems = newItems.filter((item) => !item.file || !isSupportedAdImage(item.file));
      if (supportedItems.length === 0) {
        setAdFileError("지원하지 않는 파일입니다. 광고 이미지는 JPG, PNG, WEBP 중 1개만 첨부해 주세요.");
        return;
      }
      setAdFiles([supportedItems[0]]);
      setAdFileError(
        rejectedItems.length > 0 || files.length > 1
          ? "광고 이미지는 JPG, PNG, WEBP 중 1개만 사용할 수 있습니다. 지원되는 첫 이미지만 첨부했습니다."
          : null,
      );
    }
  };

  const handleFileAdd = (e: ChangeEvent<HTMLInputElement>, isProductInfo: boolean) => {
    addFilesToList(e.target.files, isProductInfo);
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (status === "running" || hasImportedSource) return;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (status === "running" || hasImportedSource) return;
    addFilesToList(e.dataTransfer.files, false);
  };

  // 제품 정보(pFiles) 쪽은 광고 이미지 쪽과 별도 드롭 영역이라 상태·핸들러를 따로 둔다
  // (팀장이 겪은 버그: 광고 이미지 쪽만 드롭이 되고 제품 정보 쪽엔 애초에 핸들러가
  // 없었다, 2026-08-23).
  const handleDragOverP = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (status === "running" || hasImportedSource) return;
    setIsDraggingP(true);
  };

  const handleDragLeaveP = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingP(false);
  };

  const handleDropP = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingP(false);
    if (status === "running" || hasImportedSource) return;
    addFilesToList(e.dataTransfer.files, true);
  };

  const removeAdFile = (id: string) => {
    setAdFiles((prev) => prev.filter((f) => f.id !== id));
    setAdFileError(null);
  };

  const removePFile = (id: string) => {
    setPFiles((prev) => prev.filter((f) => f.id !== id));
    setIngredientFileError(null);
  };

  const handleReset = () => {
    setAdText("");
    setIngText("");
    setAdFiles([]);
    setAdFileError(null);
    setPFiles([]);
    setIngredientFileError(null);
    setProductName("");
    setSelectedDomesticReportId(null);
    setSelectedDomesticReport(null);
    setSelectedDomesticReportError(null);
    setSelectedDomesticReportLoading(false);
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

  const handleDomesticReportSelect = async (report: ReportListItem) => {
    if (status === "running") return;
    setSelectedDomesticReportId(report.result_id);
    setSelectedDomesticReport(null);
    setSelectedDomesticReportError(null);
    setResultId(null);
    setInspectStatus(null);
    if (!report.snapshot_available) return;

    setSelectedDomesticReportLoading(true);
    try {
      const envelope = await getReport(report.result_id);
      if (!envelope.input_snapshot) {
        throw new Error("이 과거 리포트에는 미국 수출에 재사용할 원본 입력이 저장되어 있지 않습니다.");
      }
      setSelectedDomesticReport(envelope);
    } catch (error) {
      setSelectedDomesticReportError(error instanceof Error ? error.message : "국내 검사 원본을 불러오지 못했습니다.");
    } finally {
      setSelectedDomesticReportLoading(false);
    }
  };

  const clearDomesticReport = () => {
    if (status === "running") return;
    setSelectedDomesticReportId(null);
    setSelectedDomesticReport(null);
    setSelectedDomesticReportError(null);
    setSelectedDomesticReportLoading(false);
    setInspectStatus(null);
    setResultId(null);
  };


  const handleRun = async () => {
    if (status === "running" || !hasAnalysisSource) return;

    const uploadingIngredientFiles = pFiles.filter((file) => file.ingredientParseStatus === "uploading");
    if (uploadingIngredientFiles.length > 0) {
      showError("전성분 파일 분석 중", "전성분 파일 해석이 끝난 뒤 다시 실행해 주세요.");
      return;
    }
    const failedIngredientFiles = pFiles.filter((file) => file.ingredientParseStatus === "error");
    if (failedIngredientFiles.length > 0) {
      showError(
        "전성분 파일 확인 필요",
        `해석하지 못한 파일이 있습니다: ${failedIngredientFiles.map((file) => `${file.name}${file.ext}`).join(", ")}. 파일을 삭제하거나 다시 첨부해 주세요.`,
      );
      return;
    }

    if (isUS && selectedDomesticReportId && !selectedSnapshot) {
      showError("원본 자료 확인 필요", "선택한 국내 리포트에는 재사용할 원본 입력이 없습니다. 직접 입력으로 전환하거나 snapshot이 저장된 리포트를 선택해 주세요.");
      return;
    }

    if (!canRunCheck) {
      setIsBlockedOpen(true);
      return;
    }
    // 무료분으로 돌린 경우에만 카운트한다. 이용권 보유자의 실행까지 세면 한도 표시가 넘친다.
    if (!isUS && daily.canRunFreeCheck) daily.record();

    setInspectStatus("running");
    setResultId(null);
    setIsLogModalOpen(true);

    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // API 호출용 파라미터 조립
    const actualImage = directRasterImage;
    const parsedIngredients = pFiles
      .flatMap((file) => file.ingredientRows || [])
      // /check 계열의 ingredients는 성분명 목록 계약이다. 함량은 FileItem에
      // 보존해 화면에만 표시하고 ingredient_amounts 계약이 연결되기 전에는 섞지 않는다.
      .map((row) => row.name)
      .filter(Boolean)
      .join(", ");
    // 직접 붙여넣은 값과 파일 파싱값을 모두 보존한다. 파일명은 성분으로 보내지 않는다.
    const ingredients = [ingText.trim(), parsedIngredients].filter(Boolean).join(", ");
    // 미국은 이전 프리플라이트 API를 사용해 기존 결과 화면과 같은 형식으로 표시한다.
    const isDirectImageAnalysis = !hasImportedSource && Boolean(actualImage?.type.startsWith("image/"));
    const importedOcrSentenceCount = selectedSnapshot?.ocr_sentences.length || 0;
    const imageStepLabel = hasImportedSource
      ? "저장 OCR 문장 재사용"
      : isDirectImageAnalysis
        ? "이미지 OCR 분석"
        : "이미지 자료 확인";
    const imageStepResult = (imageFindings: number): Pick<TaskStep, "status" | "valueText"> => {
      if (hasImportedSource) {
        return {
          status: "done",
          valueText: importedOcrSentenceCount > 0 ? `${importedOcrSentenceCount}문장 재사용` : "저장 문장 없음",
        };
      }
      if (!isDirectImageAnalysis) return { status: "done", valueText: "대상 없음" };
      return {
        status: imageFindings > 0 ? "warn" : "done",
        valueText: imageFindings > 0 ? `${imageFindings}건 감지` : "이상 없음",
      };
    };

    // 1단계: API 호출 시작 (US면 이전 프리플라이트 엔드포인트)
    const importedIngredients = selectedSnapshot?.normalized_ingredients.length
      ? selectedSnapshot.normalized_ingredients.join(", ")
      : selectedSnapshot?.ingredients_input_kind === "TEXT" ? selectedSnapshot.ingredients_raw || undefined : undefined;
    const apiPromise = regionParam === "US"
      ? checkUSPreflight({
          adText: hasImportedSource ? importedClaims || undefined : adText || undefined,
          image: hasImportedSource ? undefined : actualImage,
          ingredients: hasImportedSource ? importedIngredients : ingredients || undefined,
          productName: hasImportedSource ? selectedSnapshot?.product_name || undefined : productName || undefined,
        })
      : checkAd({
          region: regionParam,
          adText: adText || undefined,
          image: actualImage,
          ingredients: ingredients || undefined,
          // 국내 화면에는 아직 제품명/분류 입력 UI가 없으므로 빈 값을 명시해
          // 저장 snapshot의 계약을 유지한다. 이후 입력 UI가 생기면 이 값만 연결한다.
          productName: null,
          domesticCategory: null,
          domesticSubcategory: null,
        });

    const isImage = isDirectImageAnalysis;

    if (reduceMotion) {
      try {
        const report = await apiPromise;
        const rid = report.result_id ?? createLocalReportId(regionParam);
        setResultId(rid);
        if (regionParam === "US") {
          cacheUSPreflight(rid, report as USPreflightReport);
        }

        const { issueCount, imageFindings } = getAnalysisStats(report);

        setSteps([
          { id: 1, label: "자료 확인", status: "done", valueText: isImage ? `이미지 ${adFiles.length}개` : "광고 문구" },
          { id: 2, label: "광고 문구 분석", status: "done", valueText: "완료" },
          { id: 3, label: "규제 기준 대조", status: issueCount > 0 ? "warn" : "done", valueText: issueCount > 0 ? `${issueCount}건 확인 필요` : "이상 없음" },
          { id: 4, label: imageStepLabel, ...imageStepResult(imageFindings) },
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
        { id: 4, label: imageStepLabel, status: "idle" },
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
      const rid = report.result_id ?? createLocalReportId(regionParam);
      setResultId(rid);
      if (regionParam === "US") {
        cacheUSPreflight(rid, report as USPreflightReport);
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
        if (s.id === 4) return { ...s, ...imageStepResult(imageFindings) };
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
                disabled={importedInputsDisabled}
              />
            </div>
            <div className="flex items-center gap-2.5 text-[var(--ink-3)] font-mono text-[10.5px] m-[13px_0_11px] before:content-[''] before:flex-1 before:border-t before:border-[var(--line)] after:content-[''] after:flex-1 after:border-t after:border-[var(--line)]">
              <span>또는 이미지 첨부</span>
            </div>
            <div
              className={`border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] text-center p-[15px_16px] transition-all duration-[120ms] ${
                importedInputsDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              }`}
              onClick={importedInputsDisabled ? undefined : triggerAdFileSelect}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              style={{
                borderColor: isDragging ? "var(--brand)" : undefined,
                borderStyle: isDragging ? "solid" : undefined,
                backgroundColor: isDragging ? "var(--surface)" : undefined,
              }}
              tabIndex={importedInputsDisabled ? -1 : 0}
              role="button"
              aria-label="광고 이미지 첨부 영역"
              onKeyDown={(e) => {
                if (importedInputsDisabled) return;
                handleKeyDown(e, triggerAdFileSelect);
              }}
            >
              <div className="text-[var(--brand-ink)] mb-2.25 flex justify-center">
                <UploadSimple size={24} weight="regular" />
              </div>
              <h3 className="m-[0_0_8px] text-[var(--ink)] text-[14px] font-bold">상세페이지 · 광고 이미지 던져넣기</h3>
              <span className="inline-block font-mono text-[11.5px] text-[var(--brand-ink)] bg-[var(--surface)] border border-[var(--line)] p-[7px_11px]">
                drop or click · jpg png webp <span className="text-[var(--brand)] animate-[blink_1.1s_steps(1)_infinite]">▊</span>
              </span>
            </div>
            <input
              type="file"
              ref={adFileInputRef}
              style={{ display: "none" }}
              accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
              onChange={(e) => handleFileAdd(e, false)}
            />
            {adFileError && (
              <p className="mt-2 mb-0 border border-[var(--crit-bd)] bg-[var(--crit-bg)] p-2 text-[11px] leading-[1.5] text-[var(--crit)]">
                {adFileError}
              </p>
            )}
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
                      if (importedInputsDisabled) return;
                      removeAdFile(file.id);
                    }}
                    tabIndex={importedInputsDisabled ? -1 : 0}
                    role="button"
                    aria-label={`${file.name}${file.ext} 파일 삭제`}
                    onKeyDown={(e) => {
                      if (importedInputsDisabled) return;
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
                  importedInputsDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
                }`}
                onClick={importedInputsDisabled ? undefined : triggerAdFileSelect}
                // 드래그오버 시각 효과는 위 큰 드롭존에만 준다 - 여기까지 같이 반응하면
                // 두 영역이 동시에 반짝여 헷갈린다(팀장 지시, 2026-08-23). 드롭 자체는
                // 계속 받는다(핸들러는 유지).
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                tabIndex={importedInputsDisabled ? -1 : 0}
                role="button"
                aria-label="광고 이미지 파일 추가"
                onKeyDown={(e) => {
                  if (importedInputsDisabled) return;
                  handleKeyDown(e, triggerAdFileSelect);
                }}
              >
                {adFiles.length > 0 ? "+ 이미지 바꾸기" : "+ 이미지 추가"}
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
            {regionParam === "US" && domesticReportsAvailable && (
              <div className="mb-4 border border-[var(--brand)] bg-[var(--surface-sub)] p-[13px_14px]">
                <div className="flex items-start justify-between gap-3 mb-2.5">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-[10.5px] text-[var(--on-brand)] bg-[var(--brand-deep)] px-1.5 py-0.5">SOURCE</span>
                      <span className="text-[12px] font-semibold text-[var(--ink)]">국내 검사 결과 불러오기</span>
                    </div>
                    <p className="m-0 text-[11px] leading-[1.5] text-[var(--ink-3)]">이미 국내 검사를 완료했다면 원본 입력을 다시 올리지 않고 미국 수출 분석으로 이어갈 수 있습니다.</p>
                  </div>
                  {selectedDomesticReportId && (
                    <button type="button" className="shrink-0 text-[11px] text-[var(--ink-2)] underline" onClick={clearDomesticReport} disabled={status === "running"}>
                      직접 입력으로 돌아가기
                    </button>
                  )}
                </div>

                {domesticReportsLoading && <p className="m-0 text-[11.5px] text-[var(--ink-3)]">국내 검사 결과를 불러오는 중입니다...</p>}
                {!domesticReportsLoading && domesticReports.length === 0 && (
                  <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface)] p-2.5 text-[11.5px] leading-[1.5] text-[var(--ink-3)]">
                    불러올 국내 검사 결과가 없습니다. 국내 검사 후 저장된 결과가 여기에 표시됩니다. 지금은 아래에서 직접 입력할 수 있습니다.
                  </div>
                )}

                {!domesticReportsLoading && domesticReports.length > 0 && (
                  <div className="flex flex-col gap-1.5 max-h-[180px] overflow-y-auto">
                    {domesticReports.map((report) => {
                      const selected = selectedDomesticReportId === report.result_id;
                      return (
                        <button
                          type="button"
                          key={report.result_id}
                          onClick={() => void handleDomesticReportSelect(report)}
                          disabled={status === "running"}
                          className={`text-left border p-2.5 transition-colors ${selected ? "border-[var(--brand)] bg-[var(--surface)]" : "border-[var(--line)] bg-[var(--surface)] hover:border-[var(--brand)]"}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-[12px] font-semibold text-[var(--ink)]">{report.product_name || "제품명 미입력"}</span>
                            <span className={`shrink-0 font-mono text-[10px] ${report.snapshot_available ? "text-[var(--brand-ink)]" : "text-[var(--ink-3)]"}`}>
                              {report.snapshot_available ? "원본 있음" : "과거 결과"}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center justify-between gap-2 text-[10.5px] text-[var(--ink-3)]">
                            <span>{formatReportDate(report.created_at)}</span>
                            <span>{report.input_materials.length ? report.input_materials.join(" · ") : "자료 상태 확인 필요"}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                {selectedDomesticReportLoading && <p className="mt-2.5 mb-0 text-[11.5px] text-[var(--ink-3)]">선택한 국내 원본을 확인하는 중입니다...</p>}
                {selectedDomesticReportError && (
                  <div className="mt-2.5 border border-[var(--crit)] bg-[var(--surface)] p-2.5 text-[11.5px] leading-[1.5] text-[var(--crit)]">
                    {selectedDomesticReportError}<br />이 항목은 직접 입력 방식으로 진행할 수 있습니다.
                  </div>
                )}
                {selectedDomesticReportId && !selectedDomesticReportLoading && !selectedDomesticReportError && !selectedSnapshot && (
                  <div className="mt-2.5 border border-[var(--line-2)] bg-[var(--surface)] p-2.5 text-[11.5px] leading-[1.5] text-[var(--ink-3)]">
                    이 과거 리포트에는 국내 검사 당시의 원본 입력이 저장되어 있지 않습니다. 결과만 다시 볼 수 있고 미국 분석으로 자동 재사용할 수는 없습니다.
                  </div>
                )}
                {selectedSnapshot && (
                  <div className="mt-2.5 border border-[var(--line)] bg-[var(--surface)] p-2.5">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[11.5px] font-semibold text-[var(--ink)]">이번 미국 분석에 사용할 국내 원본</span>
                      <span className="font-mono text-[10px] text-[var(--brand-ink)]">{selectedSnapshot.extraction.ocr_status === "COMPLETE" ? "OCR 완료" : `OCR ${selectedSnapshot.extraction.ocr_status}`}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-2 max-[650px]:grid-cols-1 text-[11px]">
                      <div><span className="text-[var(--ink-3)]">제품명</span><p className="m-0 mt-0.5 text-[var(--ink)]">{selectedSnapshot.product_name || "미입력"}</p></div>
                      <div><span className="text-[var(--ink-3)]">국내 분류</span><p className="m-0 mt-0.5 text-[var(--ink)]">{categoryLabel(selectedSnapshot.domestic_category)}{selectedSnapshot.domestic_subcategory ? ` · ${selectedSnapshot.domestic_subcategory}` : ""}</p></div>
                      <div className="min-w-0"><span className="text-[var(--ink-3)]">광고 문구 / OCR</span><p className="m-0 mt-0.5 truncate text-[var(--ink)]">{selectedSnapshot.ad_text_raw || selectedSnapshot.ocr_sentences[0]?.text || "없음"}</p></div>
                      <div className="min-w-0"><span className="text-[var(--ink-3)]">성분</span><p className="m-0 mt-0.5 truncate text-[var(--ink)]">{selectedSnapshot.normalized_ingredients.length ? `${selectedSnapshot.normalized_ingredients.length}개 확인됨` : selectedSnapshot.ingredients_input_kind === "FILENAME_ONLY" ? "파일명만 저장됨" : "없음"}</p></div>
                    </div>
                    <div className="mt-2 border-t border-dashed border-[var(--line-2)] pt-2 text-[10.5px] text-[var(--ink-3)]">
                      자료: {selectedSnapshot.assets.length ? selectedSnapshot.assets.map((asset) => asset.original_filename || asset.role).join(" · ") : "원본 파일 없음"}
                      {selectedSnapshot.warnings.length > 0 && <span className="text-[var(--crit)]"> · 확인 필요: {selectedSnapshot.warnings.join(" · ")}</span>}
                    </div>
                    <p className={`mt-2 mb-0 text-[10.5px] leading-[1.55] ${importedClaims ? "text-[var(--ink-3)]" : "text-[var(--crit)]"}`}>
                      {importedClaims
                        ? "국내 검사 당시 광고 원문과 저장된 OCR 문장을 사용합니다. 원본 이미지는 다시 분석하지 않습니다."
                        : "재사용할 광고 문구나 OCR 문장이 없어 이 결과로는 미국 검사를 실행할 수 없습니다."}
                    </p>
                  </div>
                )}
              </div>
            )}
            {regionParam === "US" && !hasImportedSource && (
              <label className="mb-4 block text-[11.5px] text-[var(--ink-2)]">
                제품명 <span className="text-[var(--ink-3)]">· 선택</span>
                <input
                  className="mt-1 w-full border border-[var(--line-2)] bg-[var(--surface-sub)] p-[8px_9px] text-[12.5px] text-[var(--ink)] outline-none focus:border-[var(--brand)]"
                  value={productName}
                  onChange={(event) => setProductName(event.target.value)}
                  disabled={status === "running"}
                  placeholder="미국 수출 제품명"
                />
              </label>
            )}
            <div>
              <span className="block text-[12px] text-[var(--ink-2)] font-semibold mb-1.5">전성분 붙여넣기 (함량 % 선택 기재)</span>
              <textarea
                id="ingtext"
                className="w-full min-h-[92px] vertical border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] font-sans text-[13.5px] leading-1.6 p-[11px_12px] outline-none block placeholder:text-[var(--ink-3)] focus:border-[var(--brand)]"
                placeholder="예) 정제수, 나이아신아마이드 5%, 글리세린, 판테놀..."
                value={ingText}
                onChange={handleIngTextChange}
                disabled={importedInputsDisabled}
              />
            </div>
            <div className="flex items-center gap-2.5 text-[var(--ink-3)] font-mono text-[10.5px] m-[13px_0_11px] before:content-[''] before:flex-1 before:border-t before:border-[var(--line)] after:content-[''] after:flex-1 after:border-t after:border-[var(--line)]">
              <span>또는 파일 첨부</span>
            </div>
            <div
              className={`border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] text-center p-[15px_16px] transition-all duration-[120ms] ${
                importedInputsDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              }`}
              onClick={importedInputsDisabled ? undefined : triggerPFileSelect}
              onDragOver={handleDragOverP}
              onDragLeave={handleDragLeaveP}
              onDrop={handleDropP}
              style={{
                borderColor: isDraggingP ? "var(--brand)" : undefined,
                borderStyle: isDraggingP ? "solid" : undefined,
                backgroundColor: isDraggingP ? "var(--surface)" : undefined,
              }}
              tabIndex={importedInputsDisabled ? -1 : 0}
              role="button"
              aria-label="제품 정보/참고자료 첨부 영역"
              onKeyDown={(e) => {
                if (importedInputsDisabled) return;
                handleKeyDown(e, triggerPFileSelect);
              }}
            >
              <div className="text-[var(--brand-ink)] mb-2.25 flex justify-center">
                <UploadSimple size={24} weight="regular" />
              </div>
              <h3 className="m-[0_0_8px] text-[var(--ink)] text-[14px] font-bold">전성분표 파일 던져넣기</h3>
              <span className="inline-block font-mono text-[11.5px] text-[var(--brand-ink)] bg-[var(--surface)] border border-[var(--line)] p-[7px_11px]">
                drop or click · xlsx csv txt
              </span>
            </div>
            <input
              type="file"
              ref={pFileInputRef}
              style={{ display: "none" }}
              multiple
              accept=".xlsx,.csv,.txt"
              onChange={(e) => handleFileAdd(e, true)}
            />
            <p className="mt-2 mb-0 text-[10.5px] leading-[1.5] text-[var(--ink-3)]">
              파일 내용은 업로드 즉시 해석됩니다. 붙여넣은 전성분이 있으면 파일에서 읽은 성분을 뒤에 합쳐 검사합니다. PDF는 지원하지 않습니다.
            </p>
            {ingredientFileError && (
              <p className="mt-2 mb-0 border border-[var(--crit-bd)] bg-[var(--crit-bg)] p-2 text-[11px] leading-[1.5] text-[var(--crit)]">
                {ingredientFileError}
              </p>
            )}
            <div className="mt-3 flex flex-col gap-[5px]" id="pfiles">
              {pFiles.map((file) => (
                <div className="bg-[var(--surface-sub)] border border-[var(--line)] p-[8px_10px] font-mono text-[11.5px]" key={file.id}>
                  <div className="flex items-center gap-2.5">
                    {file.ingredientParseStatus === "uploading" ? (
                      <CircleNotch size={14} weight="bold" className="text-[var(--brand-ink)] animate-spin" />
                    ) : file.ingredientParseStatus === "error" ? (
                      <Warning size={14} weight="bold" className="text-[var(--crit)]" />
                    ) : (
                      <Check size={14} weight="bold" className="text-[var(--brand-ink)]" />
                    )}
                    <span className="text-[var(--ink)] flex-1">
                      {file.name}<span className="text-[var(--ink-3)]">{file.ext}</span>
                    </span>
                    <span className={`text-[10.5px] ${file.ingredientParseStatus === "error" ? "text-[var(--crit)]" : "text-[var(--brand-ink)]"}`}>
                      {file.ingredientParseStatus === "uploading"
                        ? "해석 중"
                        : file.ingredientParseStatus === "error"
                          ? "해석 실패"
                          : `${file.ingredientRows?.length || 0}개 성분`}
                    </span>
                    <button
                      type="button"
                      className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--crit)] disabled:cursor-not-allowed"
                      onClick={() => removePFile(file.id)}
                      disabled={importedInputsDisabled}
                      aria-label={`${file.name}${file.ext} 파일 삭제`}
                    >
                      <X size={14} weight="bold" />
                    </button>
                  </div>
                  {file.ingredientError && (
                    <p className="mt-1.5 mb-0 text-[10.5px] leading-[1.5] text-[var(--crit)]">{file.ingredientError}</p>
                  )}
                  {file.ingredientWarnings && file.ingredientWarnings.length > 0 && (
                    <ul className="mt-1.5 mb-0 pl-4 text-[10.5px] leading-[1.5] text-[var(--ink-3)]">
                      {file.ingredientWarnings.map((warning, index) => <li key={`${file.id}-warning-${index}`}>{warning}</li>)}
                    </ul>
                  )}
                  {file.ingredientParseStatus === "done" && file.ingredientRows && file.ingredientRows.length > 0 && (
                    <p className="mt-1.5 mb-0 truncate text-[10.5px] leading-[1.5] text-[var(--ink-3)]" title={file.ingredientRows.map((row) => row.amount ? `${row.name} (${row.amount})` : row.name).join(", ")}>
                      미리보기: {file.ingredientRows.slice(0, 3).map((row) => row.amount ? `${row.name} (${row.amount})` : row.name).join(", ")}
                      {file.ingredientRows.length > 3 ? ` 외 ${file.ingredientRows.length - 3}개` : ""}
                    </p>
                  )}
                </div>
              ))}
              <div
                className={`flex items-center gap-2.5 border border-line p-[8px_10px] font-mono text-[11.5px] border-dashed justify-center text-[var(--ink-3)] transition-colors duration-[120ms] ${
                  importedInputsDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
                }`}
                onClick={importedInputsDisabled ? undefined : triggerPFileSelect}
                // 드래그오버 시각 효과는 위 큰 드롭존에만 준다(팀장 지시, 2026-08-23 -
                // 왼쪽과 같은 이유). 드롭 자체는 계속 받는다.
                onDragOver={handleDragOverP}
                onDragLeave={handleDragLeaveP}
                onDrop={handleDropP}
                tabIndex={importedInputsDisabled ? -1 : 0}
                role="button"
                aria-label="제품 정보 파일 추가"
                onKeyDown={(e) => {
                  if (importedInputsDisabled) return;
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

          {/* 남은 무료 실행 안내. 상태 표시라 색은 쓰지 않는다 */}
          <span className="self-center font-mono text-[11.5px] text-[var(--ink-3)] tabular-nums break-keep">
            {isUS ? (
              hasPaidTicket
                ? "해외 프리플라이트 이용권 보유"
                : "해외 프리플라이트는 이용권이 필요합니다"
            ) : daily.canRunFreeCheck ? (
              `오늘 무료 검사 ${daily.remaining}/${daily.limit}회 남음`
            ) : hasPaidTicket ? (
              "오늘 무료 검사 소진 · 이용권으로 실행"
            ) : (
              "오늘 무료 검사를 모두 사용했습니다"
            )}
          </span>
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

      {/* 실행이 막혔을 때 띄우는 구매 유도. 결제 후 영수증을 닫으면 실행 버튼이 풀린다. */}
      <TicketCheckoutModal
        isOpen={isBlockedOpen}
        onClose={() => setIsBlockedOpen(false)}
        kinds={isUS ? ["overseas"] : ["domestic", "combo"]}
        defaultKind={isUS ? "overseas" : "domestic"}
        reason={
          isUS
            ? "해외 프리플라이트는 무료 체험이 없습니다. 이용권을 구매하면 검사를 실행할 수 있어요."
            : `국내 검사는 하루 ${daily.limit}회까지 무료입니다. 오늘 무료 검사를 모두 사용해서 더 돌리려면 이용권이 필요해요.`
        }
      />

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
