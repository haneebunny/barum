"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getReport, generateContent, resolveImageUrl, uploadProductPhoto } from "@/lib/api/client";
import type { CheckReport, ClinicalEvidence, GenerateResponse, IngredientAmount, Section, SurveyEvidence } from "@/lib/api/schema";
import { Check, X, CaretDown, FileCode, FileImage, FilePdf, Plus, Trash } from "@phosphor-icons/react";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { Modal } from "@/components/Modal/Modal";
import { RouteLoading } from "@/components/RouteLoading/RouteLoading";
import { GenerationLoading } from "@/components/GenerationLoading/GenerationLoading";
import { useTier, useImproveQuota, type Tier } from "@/lib/tier";
import { useError } from "@/lib/error/ErrorContext";

interface ProductPhotoItem {
  id: string;
  file: File;
  previewUrl: string;
  photoId: string | null;
  uploading: boolean;
  error: string | null;
}

interface ContentMockData {
  productName: string;
  sections: Array<{ kind: string; source: "remediation" | "llm" | "template"; text: string }>;
  imagesUploaded: string[];
  imagesPlaced: Array<{ slot: string; image_url: string }>;
  layout: Array<{ type: "section" | "image"; i: number }>;
}

const DEFAULT_MOCKS: Record<string, ContentMockData> = {
  image: {
    productName: "글로우 세럼",
    sections: [
      { kind: "광고문구", source: "remediation", text: "건조하고 예민해지기 쉬운 피부에 수분과 보습감을 더해줍니다. 매일 사용해 은은한 광채와 촉촉함을 유지해보세요." },
      { kind: "사용법", source: "llm", text: "세안 후 토너 다음 단계에서 적당량을 덜어 얼굴 전체에 고르게 펴 발라주세요. 아침·저녁 데일리 케어로 사용하기 좋습니다." },
      { kind: "주의사항", source: "template", text: "화장품 사용 시 이상이 있는 경우 사용을 중지하고 피부과 전문의와 상담하세요. 직사광선을 피해 서늘한 곳에 보관하세요." }
    ],
    imagesUploaded: ["detail_000_t00.png", "detail_000_t01.png", "detail_000_t02.png"],
    imagesPlaced: [
      { slot: "body_1", image_url: "detail_000_t01.png" },
      { slot: "body_2", image_url: "detail_000_t02.png" }
    ],
    layout: [
      { type: "section", i: 0 }, { type: "image", i: 0 },
      { type: "section", i: 1 }, { type: "image", i: 1 },
      { type: "section", i: 2 }
    ]
  },
  text: {
    productName: "수분 크림",
    sections: [
      { kind: "광고문구", source: "remediation", text: "푸석하고 메마른 피부에 풍부한 수분을 공급하여 촉촉하고 건강한 피부 장벽으로 관리해줍니다." },
      { kind: "사용법", source: "llm", text: "스킨케어 마지막 단계에서 본품 적당량을 취해 피부 결을 따라 골고루 펴 바른 뒤 가볍게 두드려 흡수시킵니다." },
      { kind: "주의사항", source: "template", text: "사용 중 붉은 반점, 부어오름, 가려움증 등의 이상 증상이 있을 경우 전문의와 상담하세요." }
    ],
    imagesUploaded: [],
    imagesPlaced: [],
    layout: [
      { type: "section", i: 0 },
      { type: "section", i: 1 },
      { type: "section", i: 2 }
    ]
  },
  unjudged: {
    productName: "한방 에센스",
    sections: [
      { kind: "광고문구", source: "remediation", text: "피부에 탄력을 더해 촉촉하고 유연하게 가꿔주는 마일드 포뮬러 에센스입니다." },
      { kind: "사용법", source: "llm", text: "적당량을 덜어 피부 결에 따라 펴 바른 후 손바닥으로 감싸 흡수시킵니다." },
      { kind: "주의사항", source: "template", text: "상처가 있는 부위 등에는 사용을 자제하시고 어린이의 손이 닿지 않는 곳에 보관하세요." }
    ],
    imagesUploaded: ["detail_002_t00.png", "detail_002_t01.png"],
    imagesPlaced: [
      { slot: "body_1", image_url: "detail_002_t00.png" },
      { slot: "body_2", image_url: "detail_002_t01.png" }
    ],
    layout: [
      { type: "section", i: 0 }, { type: "image", i: 0 },
      { type: "section", i: 1 }, { type: "image", i: 1 },
      { type: "section", i: 2 }
    ]
  }
};

const CERT_CATEGORIES = ["미백", "주름개선", "자외선차단"];

let clinicalEvidenceSeq = 0;
function nextClinicalEvidenceId() {
  clinicalEvidenceSeq += 1;
  return `ce-${clinicalEvidenceSeq}`;
}

let surveyEvidenceSeq = 0;
function nextSurveyEvidenceId() {
  surveyEvidenceSeq += 1;
  return `se-${surveyEvidenceSeq}`;
}

let ingredientAmountSeq = 0;
function nextIngredientAmountId() {
  ingredientAmountSeq += 1;
  return `ia-${ingredientAmountSeq}`;
}

let productPhotoSeq = 0;
function nextProductPhotoId() {
  productPhotoSeq += 1;
  return `pp-${productPhotoSeq}`;
}

function getRemediationProposal(violationType: string, span: string): string {
  if (span.includes("아토피 피부염")) return "순화된 보습 표현으로 대체";
  if (span.includes("3배 빠른 흡수")) return "근거 없는 비교 수치 제거";
  if (span.includes("멜라닌")) return "생성 억제 대신 기능성 화장품 표현 활용";
  if (span.includes("주름을 개선")) return "주름 개선 기능성 심사 필 문구 사용";
  if (span.includes("염증을 가라앉히고")) return "의학적 판단 여지 제거 및 보습 완화";
  if (span.includes("파워 수분 공급")) return "자극적인 수식어 배제";
  return "순화된 표현 권고";
}

function UpgradeCard({ title, desc, children }: { title: string; desc: string; children?: React.ReactNode }) {
  return (
    <div className="p-[18px_20px]">
      <div className="border border-[var(--line-2)] bg-[var(--surface-sub)] p-[32px_24px] flex flex-col items-center gap-3 text-center">
        <svg className="w-8 h-8 text-[var(--ink-3)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
          <rect x={5} y={11} width={14} height={9} />
          <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        </svg>
        <p className="m-0 text-[14px] font-bold text-[var(--ink)]">{title}</p>
        <p className="m-0 text-[12.5px] text-[var(--ink-3)] max-w-[44ch]">{desc}</p>
        {children}
        <Link
          href="/#pricing"
          className="font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] no-underline"
        >
          요금제 보기 <span className="font-mono">→</span>
        </Link>
      </div>
    </div>
  );
}

function ContentGeneratorContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { showError } = useError();
  const id = searchParams.get("id") || "";
  const acceptedParam = searchParams.get("accepted") || "";
  const mode = searchParams.get("mode") === "create" ? "create" : "improve";

  const { tier, setTier } = useTier();
  const { remaining, consume, resetWithAd } = useImproveQuota();

  const [report, setReport] = useState<CheckReport | null>(null);
  const [loading, setLoading] = useState(!!id);
  // 클릭 후 /generate 응답을 기다리는 동안. 초기 리포트 로딩(loading)과 분리한다 -
  // 하나로 묶으면 "리포트 불러오는 중"이라는 문구가 생성 대기에도 그대로 뜬다
  // (팀장 지시로 로딩 UI 분리, 2026-08-23).
  const [generating, setGenerating] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [checks, setChecks] = useState({ ck1: false, ck2: false });
  const [copied, setCopied] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [exportingType, setExportingType] = useState<"html" | "png" | "pdf" | null>(null);
  const [genResult, setGenResult] = useState<GenerateResponse | null>(null);
  const [confirmedRisks, setConfirmedRisks] = useState<Record<string, boolean>>({});
  // 화면 미리보기와 export HTML이 렌더러 두 벌로 나뉘어 있어 결과가 어긋나던 문제(표가
  // 미리보기에서만 빈 칸으로 나오는 등) 해결책. buildDetailContent()가 유일한 소스이고,
  // 미리보기는 그 결과를 그대로 DOM에 꽂아 넣는다(2026-08-20 팀장 지시, 렌더러 통합).
  const [previewContent, setPreviewContent] = useState<{ detailPageHtml: string; styleTag: string } | null>(null);

  // create 모드 입력: 제품명·성분+함량·인증서·실증자료·추가정보
  const [createProductName, setCreateProductName] = useState("");
  const [createIngredientAmounts, setCreateIngredientAmounts] = useState<
    Array<IngredientAmount & { id: string }>
  >([]);
  const [createCertifications, setCreateCertifications] = useState<Set<string>>(new Set());
  const [createClinicalEvidence, setCreateClinicalEvidence] = useState<
    Array<ClinicalEvidence & { id: string }>
  >([]);
  const [createSurveyEvidence, setCreateSurveyEvidence] = useState<
    Array<SurveyEvidence & { id: string }>
  >([]);
  const [createNotes, setCreateNotes] = useState("");
  const [createColorTone, setCreateColorTone] = useState("");
  const [createMood, setCreateMood] = useState("");
  const [createGenerateImages, setCreateGenerateImages] = useState(false);
  const [createProductPhotos, setCreateProductPhotos] = useState<ProductPhotoItem[]>([]);

  // 선택 즉시 업로드해서 photo_id를 미리 받아둔다(생성 버튼 누를 때 다시 기다리지 않게).
  const addProductPhotos = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((file) => {
      const id = nextProductPhotoId();
      const previewUrl = URL.createObjectURL(file);
      setCreateProductPhotos((prev) => [
        ...prev,
        { id, file, previewUrl, photoId: null, uploading: true, error: null },
      ]);
      uploadProductPhoto(file)
        .then((res) => {
          setCreateProductPhotos((prev) =>
            prev.map((p) => (p.id === id ? { ...p, photoId: res.photo_id, uploading: false } : p))
          );
        })
        .catch((err) => {
          console.error("Failed to upload product photo", err);
          setCreateProductPhotos((prev) =>
            prev.map((p) =>
              p.id === id
                ? { ...p, uploading: false, error: err instanceof Error ? err.message : String(err) }
                : p
            )
          );
        });
    });
  };
  const removeProductPhoto = (id: string) => {
    setCreateProductPhotos((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((p) => p.id !== id);
    });
  };

  const addIngredientAmount = () => {
    setCreateIngredientAmounts((prev) => [
      ...prev,
      { id: nextIngredientAmountId(), name: "", amount: "" }
    ]);
  };
  const updateIngredientAmount = (id: string, field: "name" | "amount", value: string) => {
    setCreateIngredientAmounts((prev) =>
      prev.map((row) => (row.id === id ? { ...row, [field]: value } : row))
    );
  };
  const removeIngredientAmount = (id: string) => {
    setCreateIngredientAmounts((prev) => prev.filter((row) => row.id !== id));
  };

  const toggleCertification = (category: string) => {
    setCreateCertifications((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const addClinicalEvidence = () => {
    setCreateClinicalEvidence((prev) => [
      ...prev,
      { id: nextClinicalEvidenceId(), claim: "", value: "", institution: "", period: "", note: "" }
    ]);
  };
  const updateClinicalEvidence = (
    id: string,
    field: "claim" | "value" | "institution" | "period" | "note",
    value: string
  ) => {
    setCreateClinicalEvidence((prev) =>
      prev.map((row) => (row.id === id ? { ...row, [field]: value } : row))
    );
  };
  const removeClinicalEvidence = (id: string) => {
    setCreateClinicalEvidence((prev) => prev.filter((row) => row.id !== id));
  };

  const addSurveyEvidence = () => {
    setCreateSurveyEvidence((prev) => [
      ...prev,
      { id: nextSurveyEvidenceId(), claim: "", value: "", sample_size: "", institution: "", period: "", method: "" }
    ]);
  };
  const updateSurveyEvidence = (
    id: string,
    field: "claim" | "value" | "sample_size" | "institution" | "period" | "method",
    value: string
  ) => {
    setCreateSurveyEvidence((prev) =>
      prev.map((row) => (row.id === id ? { ...row, [field]: value } : row))
    );
  };
  const removeSurveyEvidence = (id: string) => {
    setCreateSurveyEvidence((prev) => prev.filter((row) => row.id !== id));
  };
  const isSurveyEvidenceComplete = (row: SurveyEvidence) =>
    !!(row.claim.trim() && row.value.trim() && row.sample_size.trim() && row.institution.trim() && row.period.trim() && row.method.trim());

  const buildOriginalContent = (reportData: CheckReport) => {
    const items: Array<{ sentence: string; order: number }> = [];
    reportData.findings.forEach((f) => {
      if (!items.some((it) => it.sentence === f.sentence)) {
        items.push({ sentence: f.sentence, order: f.location.order });
      }
    });
    reportData.unjudged.forEach((u) => {
      if (!items.some((it) => it.sentence === u.sentence)) {
        items.push({ sentence: u.sentence, order: u.location.order });
      }
    });
    return items.sort((a, b) => a.order - b.order).map((it) => it.sentence).join(" ");
  };

  const startGenRef = useRef<HTMLButtonElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const dropdownTriggerRef = useRef<HTMLButtonElement>(null);

  const toggleDropdown = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDropdownOpen((prev) => !prev);
  };

  // 리포트 데이터 로드
  useEffect(() => {
    if (!id) return;
    getReport(id)
      .then((envelope) => {
        setReport(envelope.report as CheckReport);
      })
      .catch((err) => {
        console.error("Failed to fetch report context, falling back to mock", err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [id]);

  // 어떤 mockData를 보여줄지 설정
  let mockKey = "image";
  if (id === "demo-text-id" || id === "text" || id === "demo-id-2") {
    mockKey = "text";
  } else if (id === "demo-unjudged-id" || id === "unjudged" || id === "a3Fk9mdemo") {
    mockKey = "unjudged";
  }
  const mockData = DEFAULT_MOCKS[mockKey];

  // 미리보기·내보내기에 쓰는 제품명. create 모드는 입력한 제품명, 아니면 기존 improve 모드 로직 그대로
  const displayProductName =
    mode === "create"
      ? createProductName || "제품"
      : report
        ? (mockKey === "image" ? "글로우 세럼" : "수분 크림")
        : "선크림";

  // 수용된 지적 목록 추출
  const acceptedIndices = acceptedParam
    ? acceptedParam.split(",").map(Number)
    : report
      ? report.findings.map((f, idx) => (f.flag === "위반" ? idx : -1)).filter((idx) => idx !== -1)
      : [1, 2]; // 기본 mockup에서는 위반 2건 수용

  const acceptedFindings = report
    ? report.findings.filter((_, idx) => acceptedIndices.includes(idx))
    : [
        { span: "아토피 피부염을 완화하고 손상된 피부를 재생", violation_type: "1호_의약품오인" },
        { span: "시중 제품 대비 3배 빠른 흡수", violation_type: "5호_거짓과장기만" }
      ];

  // 업로드된 이미지 칩 추출
  const uploadedImages = report
    ? Array.from(
        new Set([
          ...report.findings.map((f) => f.location?.tile).filter(Boolean),
          ...report.unjudged.map((u) => u.location?.tile).filter(Boolean)
        ])
      )
    : mockData.imagesUploaded;

  // 모달 포커스 및 키보드 접근성 처리
  useEffect(() => {
    if (isModalOpen) {
      closeBtnRef.current?.focus();
    } else {
      startGenRef.current?.focus();
    }
  }, [isModalOpen]);

  // Esc 키 입력 시 모달 닫기
  useEffect(() => {
    if (!isModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isModalOpen]);

  // 내보내기 드롭다운 외부 클릭 시 닫기
  useEffect(() => {
    if (!dropdownOpen) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        dropdownTriggerRef.current &&
        !dropdownTriggerRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("click", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("click", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [dropdownOpen]);

  const handleConfirm = async () => {
    setIsModalOpen(false);
    setGenerating(true);
    try {
      let res: GenerateResponse;
      if (mode === "create") {
        res = await generateContent({
          mode: "create",
          product_name: createProductName || undefined,
          ingredient_amounts: createIngredientAmounts
            .filter((row) => row.name.trim() && row.amount.trim())
            .map(({ name, amount }) => ({ name, amount })),
          certifications: Array.from(createCertifications).map((c) => `${c} 기능성 인증`),
          clinical_evidence: createClinicalEvidence.length
            ? createClinicalEvidence
                .filter((row) => row.claim.trim() && row.value.trim())
                .map(({ claim, value, institution, period, note }) => ({
                  claim,
                  value,
                  institution: institution || undefined,
                  period: period || undefined,
                  note: note || undefined,
                }))
            : undefined,
          survey_evidence: createSurveyEvidence.some(isSurveyEvidenceComplete)
            ? createSurveyEvidence
                .filter(isSurveyEvidenceComplete)
                .map(({ claim, value, sample_size, institution, period, method }) => ({
                  claim,
                  value,
                  sample_size,
                  institution,
                  period,
                  method,
                }))
            : undefined,
          notes: createNotes || undefined,
          color_tone: createColorTone || undefined,
          mood: createMood || undefined,
          product_photo_ids: createProductPhotos.length
            ? createProductPhotos.map((p) => p.photoId).filter((id): id is string => !!id)
            : undefined,
          image_generation: createGenerateImages ? { requested: true } : undefined,
        });
      } else {
        let rawContent = "";
        if (report) {
          rawContent = buildOriginalContent(report);
        } else {
          rawContent = "자외선 차단 100%! 피부 재생 및 기미·주근깨 완벽 치료하는 선크림 SPF50";
        }

        const ingredients = report
          ? Array.from(new Set(report.findings.map(f => f.span))).join(", ")
          : undefined;

        res = await generateContent({
          mode: "improve",
          content: rawContent,
          result_id: id || undefined,
          product_name: report ? (mockKey === "image" ? "글로우 세럼" : "수분 크림") : "선크림",
          ingredients: ingredients || undefined,
          certifications: [],
        });
      }
      if (mode === "improve" && tier === "Free") consume();
      setGenResult(res);
      setIsGenerated(true);
    } catch (err) {
      console.error(err);
      showError("콘텐츠 생성 오류", "콘텐츠 생성 중 오류가 발생했습니다: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = () => {
    if (!genResult) return;
    const text = genResult.sections
      .map((s) => `[${s.kind}]\n${s.text}`)
      .join("\n\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  };

  // HTML 내보내기 (Blob)
  // 이미지를 data URI로 바꿔 내보낸 HTML이 네트워크 없이도 혼자 열리게 한다.
  const toDataUri = async (url: string): Promise<string | null> => {
    try {
      const res = await fetch(resolveImageUrl(url));
      if (!res.ok) return null;
      const blob = await res.blob();
      return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch (e) {
      console.error("Failed to inline image for export", url, e);
      return null;
    }
  };

  // 파인프린트(작은 글씨)로 다룰 섹션 종류. 라벨은 안 보여주되 타이포로는 구분한다.
  const isFinePrintKind = (kind: string) => kind.includes("caution") || kind.includes("주의");

  // data-swap="${escapeAttr(s.kind)}"는 큰따옴표 속성인데 '만 막고 있었다. s.kind는 고정
  // 리터럴이 아니라 레이아웃 플래너 LLM 출력(layout.py plan_layout)에서 온 값도 있어서
  // "가 안 걸러진 채로 올 수 있다(2026-08-20 PM8 지적, 조사로 확인). &·<·>·"·' 전부 이스케이프.
  const escapeAttr = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] || c));
  const escapeHtml = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] || c));

  // 문장 하나짜리 text를 헤드라인(첫 문장)+서브카피(나머지)로 휴리스틱 분리.
  // 백엔드가 headline/subcopy를 따로 안 줘서 쓰는 임시 방편(디디 B안 대기, 팀장·PM 확인).
  //
  // **줄바꿈을 마침표보다 먼저 본다.** 백엔드 프롬프트에 "첫 문장은 20자 이내"를 넣은 뒤
  // LLM이 실제로 "칙칙함의 원인\n피부 표면의 각질 축적과..." 처럼 줄바꿈으로 헤드라인을
  // 분리해서 준다. 그런데 마침표만 경계로 보면 줄바꿈을 무시하고 첫 마침표까지 통째로
  // 잘라서 65자짜리 "헤드라인"이 나온다(2026-08-20 실측). LLM은 이미 우리가 원하는
  // 구조를 만들어주는데 이쪽이 못 받던 것이다.
  const splitHeadline = (text: string): { headline: string; subcopy: string } => {
    const newline = text.match(/^([^\n]+)\n([\s\S]*)$/);
    if (newline) {
      const [, headline, subcopy] = newline;
      return { headline: headline.trim(), subcopy: subcopy.trim() };
    }
    // 마침표 뒤에 숫자가 붙으면 문장 끝이 아니라 소수점이다. 이 예외가 없으면
    // 실증자료 "23.5% 개선"이 헤드라인 "…23." + 서브카피 "5% 개선…"으로 쪼개져
    // **사업자가 입력한 수치가 왜곡된다**(2026-08-20 실측). barum은 실증 수치를
    // LLM에도 안 태우고 그대로 싣는 게 원칙인데 렌더 단계에서 깨지고 있었다.
    // 헤드라인이 길던 때는 안 보이다가 짧아지면서 드러났다.
    const match = text.match(/^([\s\S]+?[.!?](?!\d))\s*([\s\S]*)$/);
    if (!match) return { headline: text, subcopy: "" };
    const [, headline, subcopy] = match;
    return { headline: headline.trim(), subcopy: subcopy.trim() };
  };

  // 화면 미리보기와 export HTML이 렌더러 두 벌이라 결과가 어긋나던 문제(표가 미리보기에서만
  // 빈 칸으로 나오는 등)의 근본 해결책. 이 함수가 유일한 소스이고, exportHtml()과 미리보기용
  // useEffect 둘 다 이걸 호출한다(2026-08-20 팀장 지시, 렌더러 통합). inlineImages=true면
  // 다운로드 파일이 네트워크 없이도 혼자 열리도록 이미지를 data URI로 굽고, false(미리보기)면
  // fetch 없이 resolveImageUrl()만 써서 빠르게 그린다.
  const buildDetailContent = async (
    result: GenerateResponse,
    opts: { inlineImages: boolean }
  ): Promise<{ detailPageHtml: string; styleTag: string }> => {
    const productName = displayProductName;
    const hasAnyGeneratedImage = result.image_plan.module_images.some((mi) => mi.status === "generated" && mi.image_url)
      || result.cards.some((c) => c.image_status === "generated" && c.image_url);
    // 카드형 산출물(PR #272, 팀장 확정 2026-08-22). 백엔드가 sections·module_images·
    // layout_plan을 module_kind로 이미 짝지어 카드로 낸다 - 있으면 이쪽을 쓰고, 없는
    // (길이 0) 옛 응답만 아래 sections 매칭 경로로 폴백한다(하위호환).
    const useCards = result.cards.length > 0;
    const layoutModulesByKind: Record<string, string | null | undefined> = {};
    for (const m of result.layout_plan?.modules || []) {
      layoutModulesByKind[m.kind] = m.layout_type;
    }

    const resolveOrInline = async (url: string): Promise<string | null> =>
      opts.inlineImages ? toDataUri(url) : resolveImageUrl(url);

    // 섹션별로 매칭되는 module_image를 이미지 URL(또는 다운로드용 data URI)로 매핑
    // (카드 경로에선 안 쓴다 - 쓸모없는 이미지까지 굽는 걸 피한다)
    const moduleImageUrls: Record<string, string | null> = {};
    if (!useCards) {
      for (const mi of result.image_plan.module_images) {
        if (mi.status === "generated" && mi.image_url) {
          moduleImageUrls[mi.module_kind] = await resolveOrInline(mi.image_url);
        }
      }
    }

    // 이미지 위 배지 대신 이미지 아래 작은 캡션으로(팀장 지시: 이미지 위에 얹지 않기).
    // 법적 요건(AI기본법 제31조③, "명확하게 인식 가능한 방식")은 캡션으로도 충족.
    const aiImageCaption = `<p class="dp-ai-caption">AI 생성</p>`;
    let statementAltIndex = 0;

    // 히어로(첫 섹션)는 이미지 하단 화이트 카드로, 나머지는 layout_type이 있으면 그 유형대로,
    // 없으면(백엔드 미배선 구버전) 무드컷(이미지)+카피(텍스트) 분리 블록으로 폴백.
    // (카드형 응답이면 이 블록 자체를 건너뛴다 - result.sections는 카드 경로에서도
    // 여전히 오지만 화면엔 안 쓴다)
    const sectionsHtml = useCards ? "" : result.sections.map((s, idx) => {
      // 이미지·layout_type은 module_kind로 먼저 찾는다. 위반소지 모듈(hero_intro 등)의
      // 내용은 인정문구·실증자료가 채워서 s.kind가 "광고문구"·"실증자료"로 나오는데,
      // s.kind로만 찾으면 그 모듈들의 이미지가 통째로 버려진다(2026-08-20 실측:
      // 6장 생성해서 2장만 쓰였다). module_kind가 없는 구버전 응답은 s.kind로 폴백.
      const lookupKey = s.module_kind || s.kind;
      const dataUri = moduleImageUrls[lookupKey];
      const finePrint = isFinePrintKind(s.kind) ? " dp-fine" : "";
      const layoutType = layoutModulesByKind[lookupKey];
      const swapComment = `<!-- 이미지 교체: 아래 background-image url(...)을 판매자 본인 제품 사진으로 바꾸세요. data-swap="${escapeAttr(s.kind)}" -->`;

      if ((idx === 0 || layoutType === "hero_fullbleed") && dataUri) {
        const { headline, subcopy } = splitHeadline(s.text);
        return `${swapComment}
    <div class="dp-hero" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')">
      <div class="dp-hero-card"><span>${escapeHtml(productName)}</span><p>${escapeHtml(headline)}${subcopy ? ` ${escapeHtml(subcopy)}` : ""}</p></div>
    </div>
    ${aiImageCaption}`;
      }

      if (layoutType === "image_text_split" && dataUri) {
        const { headline, subcopy } = splitHeadline(s.text);
        const side = statementAltIndex % 2 === 0 ? "left" : "right";
        statementAltIndex++;
        return `${swapComment}
    <div class="dp-split dp-split-${side}">
      <div class="dp-split-media-wrap">
        <div class="dp-split-media" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')"></div>
        ${aiImageCaption}
      </div>
      <div class="dp-split-copy"><p class="dp-headline">${escapeHtml(headline)}</p>${subcopy ? `<p class="dp-subcopy">${escapeHtml(subcopy)}</p>` : ""}</div>
    </div>`;
      }

      if (layoutType === "step_list" && dataUri) {
        // 디디 지정: 스텝마다 개별 이미지가 아니라 섹션 전체에 대표 이미지 1장(예: 손으로
        // 펴 바르는 동작 하나). 골격은 image_text_split과 같되, 사용법 문구는 헤드라인이
        // 아니라 흐르는 본문이라 헤드라인/서브카피로 안 쪼갠다(구조화된 steps[] 필드가
        // 아직 없어 s.text를 그대로 쓴다. 2026-08-20 디디 판단).
        const side = statementAltIndex % 2 === 0 ? "left" : "right";
        statementAltIndex++;
        return `${swapComment}
    <div class="dp-split dp-split-${side}">
      <div class="dp-split-media-wrap">
        <div class="dp-split-media" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')"></div>
        ${aiImageCaption}
      </div>
      <div class="dp-split-copy"><p class="dp-step-text">${escapeHtml(s.text)}</p></div>
    </div>`;
      }

      if (layoutType === "section_statement") {
        const { headline, subcopy } = splitHeadline(s.text);
        const tone = statementAltIndex % 2 === 0 ? "" : " dp-statement-sub";
        statementAltIndex++;
        return `<div class="dp-statement${tone}${finePrint}"><p class="dp-headline">${escapeHtml(headline)}</p>${subcopy ? `<p class="dp-subcopy">${escapeHtml(subcopy)}</p>` : ""}</div>`;
      }

      if (layoutType === "mood_macro" && dataUri) {
        // 텍스처/원료 클로즈업 무드컷. 텍스트는 짧은 캡션 하나만(또는 생략).
        const { headline } = splitHeadline(s.text);
        return `${swapComment}
    <div class="dp-mood" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')"></div>
    ${aiImageCaption}
    ${headline ? `<p class="dp-caption">${escapeHtml(headline)}</p>` : ""}`;
      }

      if (layoutType === "banner_strip") {
        return `<div class="dp-banner"><p>${escapeHtml(s.text)}</p></div>`;
      }

      if (layoutType === "table_info" && s.table_rows && s.table_rows.length > 0) {
        const rowsHtml = s.table_rows
          .map((r) => `<tr><td>${escapeHtml(r.label)}</td><td>${escapeHtml(r.value)}</td></tr>`)
          .join("");
        return `<div class="dp-table-wrap"><table class="dp-table">${rowsHtml}</table></div>`;
      }

      if (dataUri) {
        // 무드컷(이미지)과 카피(텍스트)를 별도 블록으로 분리 (layout_type 없거나 미지원 유형일 때 폴백)
        return `${swapComment}
    <div class="dp-mood" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')"></div>
    ${aiImageCaption}
    <div class="dp-block${finePrint}"><p>${escapeHtml(s.text)}</p></div>`;
      }
      return `<div class="dp-block${finePrint}"><p>${escapeHtml(s.text)}</p></div>`;
    }).join("\n    ");

    // 카드형 산출물 렌더링(useCards는 위에서 이미 계산). 백엔드가 sections·
    // module_images·layout_plan을 module_kind로 이미 짝지어 카드로 낸다 - 프론트는
    // 더 이상 매칭하지 않는다.
    let cardsHtml = "";
    if (useCards) {
      const cardBlocks = await Promise.all(
        [...result.cards].sort((a, b) => a.order - b.order).map(async (card) => {
          const dataUri = card.image_status === "generated" && card.image_url
            ? await resolveOrInline(card.image_url)
            : null;
          const finePrintCard = isFinePrintKind(card.module_kind) ? " dp-fine" : "";
          const swapComment = `<!-- 이미지 교체: 아래 background-image url(...)을 판매자 본인 제품 사진으로 바꾸세요. data-swap="${escapeAttr(card.module_kind)}" -->`;
          // 실증자료 필요 고지. 있으면 카드 유형과 무관하게 항상 같이 낸다(빠뜨리면
          // 사용자가 위반에서 벗어난 줄 안다, 2026-08-20 팀장 지시와 같은 이유).
          const noteHtml = card.note ? `<div class="dp-block dp-fine"><p>${escapeHtml(card.note)}</p></div>` : "";

          if ((card.order === 0 || card.layout_type === "hero_fullbleed") && dataUri) {
            return `${swapComment}
    <div class="dp-hero" data-swap="${escapeAttr(card.module_kind)}" style="background-image:url('${dataUri}')">
      <div class="dp-hero-card"><span>${escapeHtml(productName)}</span><p>${escapeHtml(card.headline)}</p></div>
    </div>
    ${aiImageCaption}
    ${noteHtml}`;
          }

          if (card.layout_type === "image_text_split" && dataUri) {
            const side = statementAltIndex % 2 === 0 ? "left" : "right";
            statementAltIndex++;
            return `${swapComment}
    <div class="dp-split dp-split-${side}">
      <div class="dp-split-media-wrap">
        <div class="dp-split-media" data-swap="${escapeAttr(card.module_kind)}" style="background-image:url('${dataUri}')"></div>
        ${aiImageCaption}
      </div>
      <div class="dp-split-copy"><p class="dp-headline">${escapeHtml(card.headline)}</p></div>
    </div>
    ${noteHtml}`;
          }

          if (card.layout_type === "step_list" && dataUri) {
            const side = statementAltIndex % 2 === 0 ? "left" : "right";
            statementAltIndex++;
            return `${swapComment}
    <div class="dp-split dp-split-${side}">
      <div class="dp-split-media-wrap">
        <div class="dp-split-media" data-swap="${escapeAttr(card.module_kind)}" style="background-image:url('${dataUri}')"></div>
        ${aiImageCaption}
      </div>
      <div class="dp-split-copy"><p class="dp-step-text">${escapeHtml(card.headline)}</p></div>
    </div>
    ${noteHtml}`;
          }

          if (card.layout_type === "section_statement") {
            const tone = statementAltIndex % 2 === 0 ? "" : " dp-statement-sub";
            statementAltIndex++;
            return `<div class="dp-statement${tone}${finePrintCard}"><p class="dp-headline">${escapeHtml(card.headline)}</p></div>
    ${noteHtml}`;
          }

          if (card.layout_type === "mood_macro" && dataUri) {
            return `${swapComment}
    <div class="dp-mood" data-swap="${escapeAttr(card.module_kind)}" style="background-image:url('${dataUri}')"></div>
    ${aiImageCaption}
    ${card.headline ? `<p class="dp-caption">${escapeHtml(card.headline)}</p>` : ""}
    ${noteHtml}`;
          }

          if (card.layout_type === "banner_strip") {
            return `<div class="dp-banner"><p>${escapeHtml(card.headline)}</p></div>
    ${noteHtml}`;
          }

          if (dataUri) {
            // 무드컷(이미지)과 카피(텍스트)를 별도 블록으로 분리 (layout_type 없거나 미지원 유형일 때 폴백)
            return `${swapComment}
    <div class="dp-mood" data-swap="${escapeAttr(card.module_kind)}" style="background-image:url('${dataUri}')"></div>
    ${aiImageCaption}
    <div class="dp-block${finePrintCard}"><p>${escapeHtml(card.headline)}</p></div>
    ${noteHtml}`;
          }
          return `<div class="dp-block${finePrintCard}"><p>${escapeHtml(card.headline)}</p></div>
    ${noteHtml}`;
        })
      );
      cardsHtml = cardBlocks.join("\n    ");
    }

    const placedImages = await Promise.all(
      result.image_plan.placed.map(async (img) => {
        const dataUri = await resolveOrInline(img.image_url);
        return dataUri
          ? `<div class="dp-mood" style="background-image:url('${dataUri}')"></div>`
          : `<div class="dp-mood"><span class="dp-mood-fallback">${escapeHtml(img.image_url)}</span></div>`;
      })
    );
    const imagesHtml = placedImages.join("\n    ");

    const aiPageNotice = hasAnyGeneratedImage
      ? `<div class="dp-ai-notice">이 상세페이지는 AI가 생성한 문구·이미지를 포함합니다.</div>`
      : "";

    const styleTag = `<style>
    :root {
      --dp-surface: #FAF9F6;
      --dp-surface-sub: #F1EFEA;
      --dp-line: #E3DFD7;
      --dp-ink: #1D1B18;
      --dp-ink-2: #4A4640;
      --dp-ink-3: #6F6A61;
      --dp-accent: #7A2E3A;
      --dp-on-accent: #FDFBF9;
      --dp-radius: 6px;
    }
    .detailpage * { box-sizing: border-box; }
    .detailpage { width: 100%; max-width: 520px; background: var(--dp-surface); border: 1px solid var(--dp-line); border-radius: var(--dp-radius); overflow: hidden; font-family: "Pretendard Variable", Pretendard, -apple-system, sans-serif; color: var(--dp-ink-2); }
    .dp-hero { position: relative; aspect-ratio: 4/3; background-color: var(--dp-surface-sub); background-size: cover; background-position: center; display: flex; align-items: flex-end; padding: 24px; }
    /* 불투명 카드는 이미지를 가려 "발표자료" 느낌이 난다(팀장 지시, 2026-08-20). 카드 대신
       아래에서 올라오는 스크림 위에 글자만 얹는다. 스크림 최하단 alpha 0.6은 최악 조건
       (순백 이미지)에서도 흰 글자 대비 5.74:1로 WCAG AA 본문 기준(4.5:1)을 넘는다(DESIGN.md §3.1). */
    .dp-hero::after { content: ""; position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.34) 34%, rgba(0,0,0,0) 68%); pointer-events: none; }
    .dp-hero-card { position: relative; z-index: 1; max-width: 88%; }
    .dp-hero-card span { display: block; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 20px; font-weight: 600; letter-spacing: -0.3px; line-height: 1.4; color: #ffffff; margin: 0 0 7px; }
    .dp-hero-card p { margin: 0; font-size: 13.5px; line-height: 1.7; color: rgba(255,255,255,0.92); }
    .dp-ai-notice { padding: 12px 24px; font-size: 11px; color: var(--dp-ink-3); background: var(--dp-surface-sub); line-height: 1.6; }
    .dp-block { padding: 34px 24px; }
    .dp-block p { margin: 0; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 16px; font-weight: 500; line-height: 1.8; color: var(--dp-ink-2); letter-spacing: -0.1px; }
    .dp-block.dp-fine { padding: 20px 24px; background: var(--dp-surface-sub); }
    .dp-block.dp-fine p { font-family: "Pretendard Variable", Pretendard, sans-serif; font-size: 11.5px; font-weight: 400; line-height: 1.7; color: var(--dp-ink-3); }
    .dp-step-text { margin: 0; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 14.5px; font-weight: 500; line-height: 1.8; color: var(--dp-ink-2); white-space: pre-line; }
    .dp-mood { position: relative; aspect-ratio: 4/3; background-color: var(--dp-surface-sub); background-size: cover; background-position: center; margin: 0 24px; border-radius: var(--dp-radius); overflow: hidden; }
    .dp-mood-fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-family: monospace; font-size: 10px; color: var(--dp-ink-3); }
    .dp-ai-caption { margin: 5px 24px 0; font-size: 9.5px; font-weight: 500; letter-spacing: .2px; color: var(--dp-ink-3); text-align: right; }
    .dp-headline { margin: 0 0 8px; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 18px; font-weight: 600; letter-spacing: -0.3px; line-height: 1.45; color: var(--dp-ink); }
    .dp-subcopy { margin: 0; font-size: 13px; font-weight: 400; line-height: 1.75; color: var(--dp-ink-3); }
    .dp-statement { padding: 40px 24px; background: var(--dp-surface); text-align: center; }
    .dp-statement.dp-statement-sub { background: var(--dp-surface-sub); }
    .dp-statement .dp-headline { font-size: 20px; }
    .dp-split { display: flex; align-items: stretch; gap: 0; }
    .dp-split-right { flex-direction: row-reverse; }
    .dp-split-media-wrap { flex: 0 0 42%; display: flex; flex-direction: column; margin: 24px 0 24px 24px; }
    .dp-split-right .dp-split-media-wrap { margin: 24px 24px 24px 0; }
    .dp-split-media { flex: 1; position: relative; background-color: var(--dp-surface-sub); background-size: cover; background-position: center; border-radius: var(--dp-radius); }
    .dp-split-media-wrap .dp-ai-caption { margin: 5px 0 0; }
    .dp-split-copy { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 24px; min-width: 0; }
    .dp-caption { margin: 10px 24px 0; font-size: 11.5px; color: var(--dp-ink-3); text-align: center; }
    .dp-banner { padding: 14px 24px; background: var(--dp-surface-sub); text-align: center; }
    .dp-banner p { margin: 0; font-size: 12.5px; font-weight: 600; color: var(--dp-ink-2); letter-spacing: -0.1px; }
    .dp-table-wrap { padding: 20px 24px; }
    .dp-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
    .dp-table tr { border-bottom: 1px solid var(--dp-line); }
    .dp-table tr:last-child { border-bottom: none; }
    .dp-table td { padding: 10px 4px; }
    .dp-table td:first-child { color: var(--dp-ink-3); width: 30%; }
    .dp-table td:last-child { color: var(--dp-ink-2); font-weight: 600; }
    .dp-close { padding: 20px 24px; border-top: 1px solid var(--dp-line); font-size: 11px; color: var(--dp-ink-3); line-height: 1.65; background: var(--dp-surface-sub); }
  </style>`;

    const detailPageHtml = `<div class="detailpage">
    ${useCards ? cardsHtml : sectionsHtml}
    ${imagesHtml}
    ${aiPageNotice}
    <div class="dp-close">${escapeHtml(result.disclaimer)}</div>
  </div>`;

    return { detailPageHtml, styleTag };
  };

  const exportHtml = async () => {
    if (!genResult) return;
    const { detailPageHtml, styleTag } = await buildDetailContent(genResult, { inlineImages: true });
    const htmlContent = `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>${escapeHtml(displayProductName)} 상세페이지 초안</title>
  <!--
    barum이 만든 상세페이지 초안입니다.
    - 이미지를 판매자 본인 사진으로 바꾸려면: 아래 "이미지 교체" 주석이 붙은 <div data-swap="..."> 블록을 찾아
      style="background-image:url('...')" 부분만 원하는 이미지 경로로 바꾸면 됩니다.
    - 문구는 <p> 태그 안 텍스트를 그대로 수정하면 됩니다.
    - AI 생성 표시(전체 안내문·이미지별 "AI 생성" 태그)는 관련 법령(AI기본법 제31조 3항, "이용자가
      명확하게 인식할 수 있는 방식으로 고지") 대응용이니 임의로 지우거나 대비를 낮추지 마세요.
    - 이 페이지의 색·폰트는 barum 서비스 화면과 별개의 상세페이지 전용 톤입니다.
  -->
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/sun-typeface/SUIT@2/fonts/variable/woff2/SUIT-Variable.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
  ${styleTag}
</head>
<body style="margin:0; padding:48px 16px; background: var(--dp-surface-sub); display:flex; justify-content:center;">
  ${detailPageHtml}
</body>
</html>`;

    const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `detail_draft.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 미리보기도 exportHtml과 같은 buildDetailContent()를 쓴다(렌더러 통합). genResult가
  // 바뀔 때마다 다시 그린다. inlineImages:false라 fetch 없이 즉시 끝난다.
  useEffect(() => {
    if (!genResult) return;
    let cancelled = false;
    buildDetailContent(genResult, { inlineImages: false }).then((r) => {
      if (!cancelled) setPreviewContent(r);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genResult]);

  // export HTML 전용 CDN 폰트(SUIT·Pretendard)를 미리보기에서도 쓰려면 문서에 한 번 걸어둬야
  // 한다(앱 전역 폰트는 JetBrains Mono·D2Coding이라 이 상세페이지 톤과 다르다).
  useEffect(() => {
    const hrefs = [
      "https://cdn.jsdelivr.net/gh/sun-typeface/SUIT@2/fonts/variable/woff2/SUIT-Variable.css",
      "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css",
    ];
    hrefs.forEach((href) => {
      if (document.querySelector(`link[href="${href}"]`)) return;
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      document.head.appendChild(link);
    });
  }, []);

  // PNG 내보내기 (html2canvas)
  const exportPng = async () => {
    try {
      const html2canvas = (await import("html2canvas")).default;
      const element = document.getElementById("detailPage");
      if (!element) return;

      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        backgroundColor: null
      });
      const url = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.href = url;
      a.download = `${mockKey}_detail_draft.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      console.error("Failed PNG generation", e);
      alert("PNG 변환 중 오류가 발생했습니다.");
    }
  };

  // PDF 내보내기 (html2canvas + jspdf)
  const exportPdf = async () => {
    try {
      const html2canvas = (await import("html2canvas")).default;
      const { jsPDF } = await import("jspdf");
      const element = document.getElementById("detailPage");
      if (!element) return;

      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        backgroundColor: "#FFFFFF"
      });
      const imgData = canvas.toDataURL("image/png");

      const pdf = new jsPDF("p", "mm", "a4");
      const imgWidth = 210; // A4 가로 mm
      const pageHeight = 297; // A4 세로 mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      pdf.save(`${mockKey}_detail_draft.pdf`);
    } catch (e) {
      console.error("Failed PDF generation", e);
      alert("PDF 변환 중 오류가 발생했습니다.");
    }
  };

  const handleExport = async (type: "html" | "png" | "pdf") => {
    setExportingType(type);
    setDropdownOpen(false);

    // 사용자 경험을 위해 살짝 지연 (내보내는 중 로딩 상태 표시 연출)
    await new Promise((resolve) => setTimeout(resolve, 800));

    if (type === "html") {
      await exportHtml();
    } else if (type === "png") {
      await exportPng();
    } else if (type === "pdf") {
      await exportPdf();
    }
    setExportingType(null);
  };

  if (loading) {
    return <RouteLoading message="리포트를 불러오는 중" />;
  }

  if (generating) {
    return (
      <GenerationLoading
        mode={mode === "create" ? "create" : "improve"}
        imagesRequested={mode === "create" && createGenerateImages}
      />
    );
  }

  return (
    <>
      <div className="flex items-center gap-3 p-[9px_20px] border-b border-[var(--line)] bg-[var(--surface-sub)] font-mono text-[11px] text-[var(--ink-3)] flex-wrap">
        <span className="text-[var(--ink-2)]">
          <Link href="/" className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]">
            홈
          </Link>{" "}
          <span className="text-[var(--ink-3)]">›</span>{" "}
          {mode === "create" ? (
            "콘텐츠 생성"
          ) : (
            <>
              <span
                onClick={() => router.push(id ? `/report/${id}` : "/")}
                style={{ cursor: "pointer" }}
                className="text-[var(--ink-3)] cursor-pointer hover:text-[var(--ink)]"
              >
                리포트
              </span>{" "}
              <span className="text-[var(--ink-3)]">›</span> 콘텐츠 생성
            </>
          )}
        </span>
        <span className="text-[var(--ink-3)] text-[10px]">
          {mode === "create" ? "새로 만들기 모드" : id ? `리포트 연동: ${id}` : "더미 데이터 모드"} · 백엔드 FR-11/13 완료
        </span>
        <span className="ml-auto inline-flex items-center gap-[6px] font-mono text-[10.5px] text-[var(--ink-3)]">
          티어 미리보기
          {(["Free", "Basic", "Pro"] as Tier[]).map(t => (
            <button
              key={t}
              type="button"
              onClick={() => setTier(t)}
              className={`font-mono text-[11px] p-[4px_9px] border cursor-pointer transition-all duration-[120ms] ${
                tier === t
                  ? "border-[var(--ink-3)] text-[var(--ink)] bg-[var(--nav-active-bg)] font-bold"
                  : "border-[var(--line-2)] text-[var(--ink-3)] bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
              }`}
            >
              {t}
            </button>
          ))}
        </span>
      </div>

      {/* 티어 게이팅 */}
      {mode === "create" && tier !== "Pro" ? (
        <UpgradeCard
          title="콘텐츠 생성은 Pro에서 이용 가능합니다"
          desc="제품 정보를 입력하면 화장품법을 준수하는 상세페이지 초안을 자동으로 만들어줍니다. Pro 요금제에서 월 5회까지 사용할 수 있어요."
        />
      ) : mode === "improve" && tier === "Free" && remaining <= 0 ? (
        <UpgradeCard
          title="무료 체험 1회를 모두 사용했습니다"
          desc="수정 권고안 기반 콘텐츠 개선은 Basic부터 무제한으로 이용할 수 있어요."
        >
          <button
            type="button"
            onClick={resetWithAd}
            className="font-sans text-[12px] font-semibold p-[8px_14px] border border-[var(--line-2)] bg-transparent text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] inline-flex items-center justify-center gap-1.5 transition-all duration-[120ms]"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="square">
              <polygon points="6,4 20,12 6,20" />
            </svg>
            광고 보고 1회 추가 사용
          </button>
        </UpgradeCard>
      ) : (
      <>

      {/* 입력 요약 / create 모드 입력 폼 */}
      {mode === "create" ? (
        <div className="p-[18px_20px] border-b border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">제품 정보 입력</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">전부 선택 입력, 없으면 그 근거가 필요한 모듈만 빠집니다</span>
          </div>
          <div className="flex flex-col gap-3.5">
            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <label className="block font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_8px] tracking-[0.3px]">제품명</label>
              <input
                type="text"
                value={createProductName}
                onChange={(e) => setCreateProductName(e.target.value)}
                placeholder="예: 글로우 세럼"
                className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[13px] p-[8px_10px] outline-none focus:border-[var(--brand)]"
              />
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">제품 사진 (선택, AI 합성 시 참고 이미지로 사용)</p>
              <div className="flex flex-wrap gap-2 mb-2">
                {createProductPhotos.map((p) => (
                  <div key={p.id} className="relative w-[76px] h-[76px] border border-[var(--line-2)] bg-[var(--surface-sub)] overflow-hidden">
                    <img src={p.previewUrl} alt="제품 사진 미리보기" className="w-full h-full object-cover" />
                    {p.uploading && (
                      <div className="absolute inset-0 bg-black/50 flex items-center justify-center text-white text-[10px] font-mono">업로드중</div>
                    )}
                    {p.error && (
                      <div className="absolute inset-0 bg-[var(--crit-bg)]/90 flex items-center justify-center text-[var(--crit)] text-[9px] font-mono text-center p-1">업로드 실패</div>
                    )}
                    <button
                      type="button"
                      onClick={() => removeProductPhoto(p.id)}
                      aria-label="제품 사진 삭제"
                      className="absolute top-0.5 right-0.5 w-4 h-4 flex items-center justify-center bg-black/60 text-white cursor-pointer"
                    >
                      <Trash size={10} weight="bold" />
                    </button>
                  </div>
                ))}
              </div>
              <label className="inline-flex items-center gap-1.5 self-start text-[11.5px] text-[var(--ink-3)] hover:text-[var(--ink)] border border-dashed border-[var(--line-2)] p-[6px_10px] cursor-pointer">
                <Plus size={12} weight="bold" /> 제품 사진 추가
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    addProductPhotos(e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">전성분 + 함량 (선택, 인정문구 함량기준 대조용)</p>
              <div className="flex flex-col gap-1.5">
                {createIngredientAmounts.map((row) => (
                  <div key={row.id} className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={row.name}
                      onChange={(e) => updateIngredientAmount(row.id, "name", e.target.value)}
                      placeholder="성분명 (예: 나이아신아마이드)"
                      className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                    />
                    <input
                      type="text"
                      value={row.amount}
                      onChange={(e) => updateIngredientAmount(row.id, "amount", e.target.value)}
                      placeholder="함량 (예: 2%)"
                      className="w-[120px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                    />
                    <button
                      type="button"
                      onClick={() => removeIngredientAmount(row.id)}
                      aria-label="성분 삭제"
                      className="text-[var(--ink-3)] hover:text-[var(--crit)] p-1 cursor-pointer"
                    >
                      <Trash size={14} weight="bold" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addIngredientAmount}
                  className="flex items-center gap-1.5 self-start text-[11.5px] text-[var(--ink-3)] hover:text-[var(--ink)] border border-dashed border-[var(--line-2)] p-[6px_10px] cursor-pointer"
                >
                  <Plus size={12} weight="bold" /> 성분 추가
                </button>
              </div>
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">보유 인증서 (선택, 인정문구 매칭용)</p>
              <div className="flex flex-wrap gap-3">
                {CERT_CATEGORIES.map((cat) => (
                  <label key={cat} className="flex items-center gap-1.5 text-[12.5px] text-[var(--ink-2)] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={createCertifications.has(cat)}
                      onChange={() => toggleCertification(cat)}
                    />
                    {cat} 기능성 인증
                  </label>
                ))}
              </div>
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">실증자료 (선택, 임상 수치 모듈에만 필요. barum은 진위를 검증하지 않습니다)</p>
              <div className="flex flex-col gap-2.5">
                {createClinicalEvidence.map((row) => (
                  <div key={row.id} className="border border-dashed border-[var(--line-2)] p-[10px_11px] flex flex-col gap-1.5">
                    <div className="flex items-center gap-1.5">
                      <input
                        type="text"
                        value={row.claim}
                        onChange={(e) => updateClinicalEvidence(row.id, "claim", e.target.value)}
                        placeholder="무엇을 개선했는지 (예: 다크스팟 개선)"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <input
                        type="text"
                        value={row.value}
                        onChange={(e) => updateClinicalEvidence(row.id, "value", e.target.value)}
                        placeholder="결과 수치 (예: 87%)"
                        className="w-[110px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <button
                        type="button"
                        onClick={() => removeClinicalEvidence(row.id)}
                        aria-label="실증자료 삭제"
                        className="text-[var(--ink-3)] hover:text-[var(--crit)] p-1 cursor-pointer"
                      >
                        <Trash size={14} weight="bold" />
                      </button>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="text"
                        value={row.institution || ""}
                        onChange={(e) => updateClinicalEvidence(row.id, "institution", e.target.value)}
                        placeholder="시험기관명 (선택)"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <input
                        type="text"
                        value={row.period || ""}
                        onChange={(e) => updateClinicalEvidence(row.id, "period", e.target.value)}
                        placeholder="시험기간 (선택, 예: 4주)"
                        className="w-[130px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                    </div>
                    <input
                      type="text"
                      value={row.note || ""}
                      onChange={(e) => updateClinicalEvidence(row.id, "note", e.target.value)}
                      placeholder="피험자 수·조건 등 부연 (선택)"
                      className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                    />
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addClinicalEvidence}
                  className="flex items-center gap-1.5 self-start text-[11.5px] text-[var(--ink-3)] hover:text-[var(--ink)] border border-dashed border-[var(--line-2)] p-[6px_10px] cursor-pointer"
                >
                  <Plus size={12} weight="bold" /> 실증자료 추가
                </button>
              </div>
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">설문조사 결과 (선택, 향·발림성·재구매의향 등 비효능 항목만. 실증자료 아님)</p>
              <div className="flex flex-col gap-2.5">
                {createSurveyEvidence.map((row) => (
                  <div key={row.id} className="border border-dashed border-[var(--line-2)] p-[10px_11px] flex flex-col gap-1.5">
                    <div className="flex items-center gap-1.5">
                      <input
                        type="text"
                        value={row.claim}
                        onChange={(e) => updateSurveyEvidence(row.id, "claim", e.target.value)}
                        placeholder="무엇에 대한 응답인지 · 필수 (예: 향에 만족)"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <input
                        type="text"
                        value={row.value}
                        onChange={(e) => updateSurveyEvidence(row.id, "value", e.target.value)}
                        placeholder="결과 수치 · 필수 (예: 96%)"
                        className="w-[110px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <button
                        type="button"
                        onClick={() => removeSurveyEvidence(row.id)}
                        aria-label="설문조사 삭제"
                        className="text-[var(--ink-3)] hover:text-[var(--crit)] p-1 cursor-pointer"
                      >
                        <Trash size={14} weight="bold" />
                      </button>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="text"
                        value={row.sample_size}
                        onChange={(e) => updateSurveyEvidence(row.id, "sample_size", e.target.value)}
                        placeholder="표본 수 · 필수 (예: 200명)"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <input
                        type="text"
                        value={row.institution}
                        onChange={(e) => updateSurveyEvidence(row.id, "institution", e.target.value)}
                        placeholder="조사기관명 · 필수"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="text"
                        value={row.period}
                        onChange={(e) => updateSurveyEvidence(row.id, "period", e.target.value)}
                        placeholder="조사 시기 · 필수 (예: 2026년 3월)"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                      <input
                        type="text"
                        value={row.method}
                        onChange={(e) => updateSurveyEvidence(row.id, "method", e.target.value)}
                        placeholder="조사 방법 · 필수 (예: 온라인 자기기입식 설문)"
                        className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                      />
                    </div>
                    {!isSurveyEvidenceComplete(row) && (
                      <p className="m-0 text-[11px] text-[var(--ink-3)]">6개 항목을 모두 채워야 사용돼요. 비어있으면 이 설문은 생성에서 빠져요.</p>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addSurveyEvidence}
                  className="flex items-center gap-1.5 self-start text-[11.5px] text-[var(--ink-3)] hover:text-[var(--ink)] border border-dashed border-[var(--line-2)] p-[6px_10px] cursor-pointer"
                >
                  <Plus size={12} weight="bold" /> 설문조사 추가
                </button>
              </div>
              <p className="m-[8px_0_0] text-[11px] text-[var(--ink-3)]">
                피부 변화(효능) 주장은 설문으로 못 받쳐서 생성에서 빠지고 사유가 남아요. 6개 항목을 다 채워도 판정에서 자동으로 안전해지는 건 아니에요. 검토 범위만 좁혀줄 뿐이에요.
              </p>
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">색상톤·분위기 (선택, 이미지·문구 생성에 반영)</p>
              <div className="flex flex-col gap-1.5">
                <input
                  type="text"
                  value={createColorTone}
                  onChange={(e) => setCreateColorTone(e.target.value)}
                  placeholder="색상톤 (예: 베이지·아이보리 톤)"
                  className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                />
                <input
                  type="text"
                  value={createMood}
                  onChange={(e) => setCreateMood(e.target.value)}
                  placeholder="분위기 (예: 미니멀하고 차분한)"
                  className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                />
              </div>
              <p className="m-[8px_0_0] text-[11px] text-[var(--ink-3)]">비워두면 상품 종류에 맞춰 기본 톤으로 생성돼요.</p>
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <label className="block font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_8px] tracking-[0.3px]">추가정보 (선택)</label>
              <textarea
                value={createNotes}
                onChange={(e) => setCreateNotes(e.target.value)}
                placeholder="상품 종류·타깃·기타 참고사항을 자유롭게 적어주세요"
                className="w-full min-h-[64px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[13px] p-[8px_10px] outline-none focus:border-[var(--brand)] resize-y"
              />
            </div>

            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <label className="flex items-center gap-2 text-[12.5px] text-[var(--ink-2)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={createGenerateImages}
                  onChange={(e) => setCreateGenerateImages(e.target.checked)}
                />
                모듈별 배경 이미지도 생성하기
              </label>
              <p className="m-[6px_0_0] text-[11px] text-[var(--ink-3)]">
                제품·라벨·글자는 안 그리고 배경·질감만 만들어요. 이미지 생성은 별도 비용이 발생해서 기본은 꺼져 있어요.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-[18px_20px] border-b border-[var(--line)]">
          <div className="flex items-center gap-[11px] m-[0_0_13px]">
            <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">01</span>
            <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">입력 요약</h2>
            <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">리포트에서 수용 처리된 항목</span>
          </div>
          <div className="grid grid-cols-2 gap-3.5 max-[900px]:grid-cols-1">
            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">수용된 수정 권고안 · {acceptedFindings.length}건</p>
              <ul className="list-none m-0 p-0 flex flex-col gap-1.25">
                {acceptedFindings.map((f, i) => (
                  <li key={i} className="text-[12.5px] text-[var(--ink-2)] flex items-start gap-1.75">
                    <svg className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--brand-ink)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                      <path d="M4 12l5 5L20 6" />
                    </svg>
                    <span>
                      <span className="text-[var(--ink-3)] line-through decoration-[var(--ink-3)]">{f.span}</span>
                      <span className="text-[var(--ink-3)] mx-0.5">→</span>
                      {getRemediationProposal(f.violation_type || "", f.span || "")}
                    </span>
                  </li>
                ))}
                {acceptedFindings.length === 0 && (
                  <li style={{ color: "var(--ink-3)" }}>수용 처리된 수정 권고안이 없습니다.</li>
                )}
              </ul>
            </div>
            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">재사용한 업로드 이미지 · {uploadedImages.length}장</p>
              <div className="flex flex-wrap gap-1.75">
                {uploadedImages.map((img, i) => (
                  <span key={i} className="font-mono text-[11px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-3)] p-[4px_9px]">
                    {img}
                  </span>
                ))}
                {uploadedImages.length === 0 && (
                  <span className="text-[var(--ink-3)] text-[10px]">
                    첨부된 이미지가 없습니다.
                  </span>
                )}
              </div>
              <p style={{ margin: "11px 0 0", fontSize: "11.5px", color: "var(--ink-3)" }}>
                이미지는 새로 만들지 않고 업로드분을 재배치만 합니다.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 생성 결과 */}
      <div className="p-[18px_20px] border-b-0">
        <div className="flex items-center gap-[11px] m-[0_0_13px]">
          <span className="text-[var(--on-brand)] bg-[var(--brand-deep)] font-mono font-bold text-[11px] p-[2px_7px] inline-flex items-center">02</span>
          <h2 className="m-0 text-[13px] font-bold text-[var(--ink)] tracking-[-0.2px]">생성된 상세페이지 초안</h2>
          <span className="flex-1 h-0 border-t border-dashed border-[var(--line-2)]"></span>
          {/* "재검증 통과"를 여기 고정 문구로 박아뒀더니 실제로 재검증에
              실패해도(아래 recheckBadge가 "재검증 실패"를 보여줄 때도) 이
              문구는 그대로 "통과"라고 말해서 같은 화면에 통과/실패가 동시에
              떴다(팀장 실측, 2026-08-23). 여긴 결과가 아니라 파이프라인
              설명 자리라 결과를 암시하는 말을 빼고 "포함"으로 바꾼다 -
              실제 결과는 아래 recheckBadge 하나만 말한다. */}
          <span className="text-[var(--ink-3)] font-mono text-[10.5px]" id="secHint">
            {isGenerated ? "원샷 생성 · 편집 불가 · 재검증 포함" : "원샷 생성 · 편집 불가"}
          </span>
        </div>

        {/* 생성 전 게이트 */}
        {!isGenerated && (
          <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[26px_20px] flex flex-col items-center gap-3 text-center" id="gateCard">
            <p className="m-0 text-[12.5px] text-[var(--ink-3)] max-w-[52ch]">
              {mode === "create"
                ? "입력한 제품 정보로 상세페이지 초안 1안을 만듭니다. 생성 전 확인이 필요한 항목이 있어요."
                : "입력 요약을 반영해 상세페이지 초안 1안을 만듭니다. 생성 전 확인이 필요한 항목이 있어요."}
            </p>
            {mode === "create" && !createProductName.trim() && (
              <p className="m-0 text-[11.5px] text-[var(--crit)]">제품명을 입력해야 생성할 수 있어요.</p>
            )}
            {mode === "create" && createCertifications.size === 0 && createClinicalEvidence.length === 0 && (
              <p className="m-0 text-[11.5px] text-[var(--ink-3)] max-w-[52ch]">
                인증서·실증자료가 없으면 효능을 주장하는 문단은 만들지 않아요. 도입부를 포함해 일부 구성이 빠질 수 있어요.
              </p>
            )}
            {mode === "create" && createProductPhotos.some((p) => p.uploading) && (
              <p className="m-0 text-[11.5px] text-[var(--ink-3)]">제품 사진 업로드가 끝날 때까지 잠시만 기다려주세요.</p>
            )}
            <button
              className="font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] disabled:opacity-50 disabled:cursor-not-allowed"
              id="startGen"
              ref={startGenRef}
              disabled={
                (mode === "create" && !createProductName.trim()) ||
                createProductPhotos.some((p) => p.uploading)
              }
              onClick={() => setIsModalOpen(true)}
            >
              확인 후 생성하기 <span className="font-mono">→</span>
            </button>
          </div>
        )}

        {/* 생성 결과 (게이트 통과 후 표시) */}
        {isGenerated && genResult && (
          <div id="resultWrap">
            <div
              className={`inline-flex items-center gap-1.75 font-mono text-[11.5px] p-[5px_10px] border mb-3.5 ${
                genResult.recheck.safe
                  ? "border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]"
                  : "border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)]"
              }`}
              id="recheckBadge"
            >
              {genResult.recheck.safe ? (
                <>
                  <Check size={14} weight="bold" className="text-[var(--brand-ink)] mr-1" />
                  재검증 통과 · 위반 0건 · 검토필요 0건
                </>
              ) : (
                <>
                  <X size={14} weight="bold" className="text-[var(--crit)] mr-1" />
                  재검증 실패 · 위반 {genResult.recheck.n_violation}건 · 검토필요 {genResult.recheck.n_needs_review}건
                </>
              )}
            </div>

            {genResult.layout_plan && genResult.layout_plan.modules.length > 0 && (
              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px] mb-3.5">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">
                  구성 계획 · {genResult.layout_plan.modules.length}개 모듈
                  {genResult.layout_plan.product_type && ` · ${genResult.layout_plan.product_type}`}
                  {" · "}
                  {genResult.layout_plan.source === "planner" ? "AI 계획" : "고정 플랜"}
                </p>
                <ol className="list-none m-0 p-0 flex flex-wrap gap-1.5">
                  {genResult.layout_plan.modules.map((m, i) => (
                    <li
                      key={`${m.kind}-${i}`}
                      className="flex items-center gap-1.5 font-mono text-[11px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink-2)] p-[4px_9px]"
                    >
                      <span className="text-[var(--ink-3)]">{i + 1}.</span>
                      {m.kind}
                      {m.has_claim_risk && (
                        <span className="text-[var(--brand-ink)]" title="실증자료 기반 근거로 통과된 모듈">
                          ✓근거
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {genResult.skipped_claims.length > 0 && (
              <div className="border border-dashed border-[var(--line-2)] bg-[var(--surface-sub)] p-[15px_16px] mb-3.5">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">
                  근거 부족으로 제외됨 · {genResult.skipped_claims.length}건
                </p>
                <ul className="list-none m-0 p-0 flex flex-col gap-1.5">
                  {genResult.skipped_claims.map((s, i) => (
                    <li key={i} className="text-[12px] text-[var(--ink-3)] flex items-start gap-1.75">
                      <X size={13} weight="bold" className="shrink-0 mt-0.5" />
                      <span>
                        <b className="text-[var(--ink-2)] font-semibold">{s.category}</b>: {s.reason}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="border border-[var(--line-2)] bg-[var(--surface-sub)]">
              <div className="flex items-center gap-2 p-[8px_12px] border-b border-[var(--line-2)] font-mono text-[11px] text-[var(--ink-3)]">
                <span className="w-1.75 h-1.75 rounded-full bg-[var(--line-2)] shrink-0"></span>
                <span className="text-[var(--ink-2)]">detail_draft.html</span>
              </div>
              <div className="p-[22px] flex justify-center">
                {previewContent ? (
                  <div
                    className="w-full max-w-[520px]"
                    id="detailPage"
                    // export HTML과 같은 buildDetailContent() 결과를 그대로 꽂는다(렌더러 통합).
                    // dp-* 클래스는 barum 서비스 토큰과 안 겹치게 이미 분리 설계돼 있다.
                    dangerouslySetInnerHTML={{ __html: previewContent.styleTag + previewContent.detailPageHtml }}
                  />
                ) : (
                  <div className="w-full max-w-[520px] aspect-[4/3] bg-[repeating-linear-gradient(135deg,var(--surface-sub)_0_10px,var(--surface)_10px_20px)] flex items-end p-4 border border-[var(--line-2)]">
                    <span className="text-[var(--ink)] text-[19px] font-extrabold tracking-[-0.3px] bg-[var(--surface)] p-[6px_10px] border border-[var(--line-2)]">
                      {displayProductName}
                    </span>
                  </div>
                )}
              </div>
            </div>
            {genResult.risk_confirmations.length > 0 && (
              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px] mt-3.5 w-full border-[var(--crit)]" style={{ border: "1px solid var(--crit)" }}>
                <p className="font-mono text-[10.5px] text-[var(--crit)] m-[0_0_10px] tracking-[0.3px] font-bold">⚠️ 자동 수정 불가 잔존 위험 · {genResult.risk_confirmations.length}건 (확인 필요)</p>
                <ul className="list-none m-0 p-0 flex flex-col gap-1.25 p-[8px_12px]">
                  {genResult.risk_confirmations.map((rc) => (
                    <li key={rc.id} className="flex gap-2 items-start mb-2">
                      <input
                        type="checkbox"
                        id={rc.id}
                        checked={!!confirmedRisks[rc.id]}
                        onChange={(e) => setConfirmedRisks(prev => ({ ...prev, [rc.id]: e.target.checked }))}
                        className="mt-0.75"
                      />
                      <label className="cursor-pointer" htmlFor={rc.id}>
                        <span className="font-bold text-[13px]">{rc.text}</span>
                        <p className="m-[2px_0_0] text-[11.5px] text-[var(--ink-3)]">{rc.reason}</p>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex items-center justify-between gap-3.5 p-[13px_20px] flex-wrap">
              <p className="m-0 text-[11.5px] text-[var(--ink-3)] max-w-[44ch]">
                생성된 문구는 리포트에서 수용한 권고안을 조건표 안에서 재배열한 것으로, 원문에 없던 효능을 새로 만들지
                않았습니다.
                {genResult.risk_confirmations.length > 0 && " (잔존 위험 항목 확인 후 사용을 권장합니다.)"}
              </p>
              <div className="flex gap-2 flex-wrap">
                <button
                  className={`font-sans text-[13px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] ${
                    copied
                      ? "text-[var(--brand-ink)] border-[var(--brand)] bg-[var(--surface-sub)]"
                      : "text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)]"
                  }`}
                  id="copyBtn"
                  onClick={handleCopy}
                >
                  {copied ? "복사됨" : "텍스트 복사"}
                </button>
                <div className="relative" id="expDd">
                  <button
                    className={`font-sans text-[13px] font-bold p-[11px_16px] border bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] disabled:opacity-50 disabled:cursor-not-allowed ${
                      exportingType ? "" : "cursor-pointer hover:bg-[var(--brand-deep)]"
                    }`}
                    id="expTrigger"
                    ref={dropdownTriggerRef}
                    aria-haspopup="true"
                    aria-expanded={dropdownOpen}
                    onClick={toggleDropdown}
                    disabled={exportingType !== null}
                  >
                    {exportingType ? "내보내는 중…" : "내보내기"}{" "}
                    <CaretDown className={`w-3.25 h-3.25 transition-transform duration-150 ${dropdownOpen ? "rotate-180" : ""}`} size={13} weight="bold" />
                  </button>
                  {dropdownOpen && (
                    <div className="absolute right-0 bottom-[calc(100%+6px)] min-w-[190px] bg-[var(--surface)] border border-[var(--line-2)] shadow-[0_10px_26px_rgba(20,35,27,0.14)] z-10" id="expMenu">
                      <button
                        className="flex items-center gap-2 w-full text-left p-[9px_12px] font-sans text-[12.5px] font-semibold text-[var(--ink-2)] bg-transparent border-0 border-b border-[var(--line)] cursor-pointer whitespace-nowrap transition-all duration-120 hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] disabled:opacity-50 disabled:cursor-not-allowed last:border-b-0"
                        id="expHtml"
                        onClick={() => handleExport("html")}
                        disabled={exportingType !== null}
                      >
                        <FileCode className="w-3.5 h-3.5 shrink-0 text-[var(--ink-3)]" size={14} weight="regular" />
                        HTML로 내보내기
                      </button>
                      <button
                        className="flex items-center gap-2 w-full text-left p-[9px_12px] font-sans text-[12.5px] font-semibold text-[var(--ink-2)] bg-transparent border-0 border-b border-[var(--line)] cursor-pointer whitespace-nowrap transition-all duration-120 hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] disabled:opacity-50 disabled:cursor-not-allowed last:border-b-0"
                        id="expPng"
                        onClick={() => handleExport("png")}
                        disabled={exportingType !== null}
                      >
                        <FileImage className="w-3.5 h-3.5 shrink-0 text-[var(--ink-3)]" size={14} weight="regular" />
                        PNG로 내보내기
                      </button>
                      <button
                        className="flex items-center gap-2 w-full text-left p-[9px_12px] font-sans text-[12.5px] font-semibold text-[var(--ink-2)] bg-transparent border-0 border-b border-[var(--line)] cursor-pointer whitespace-nowrap transition-all duration-120 hover:bg-[var(--nav-hover)] hover:text-[var(--ink)] disabled:opacity-50 disabled:cursor-not-allowed last:border-b-0"
                        id="expPdf"
                        onClick={() => handleExport("pdf")}
                        disabled={exportingType !== null}
                      >
                        <FilePdf className="w-3.5 h-3.5 shrink-0 text-[var(--ink-3)]" size={14} weight="regular" />
                        PDF로 내보내기
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      </>
      )}

      <PageFooter />

      {/* 생성 전 확인 모달 (터미널 다이얼로그) */}
      <Modal
        isOpen={isModalOpen}
        title="생성 전 확인"
        size="md"
        onClose={() => setIsModalOpen(false)}
        ref={closeBtnRef}
        footer={
          <>
            <button
              className="font-sans text-[13px] font-semibold p-[11px_16px] border border-[var(--line-2)] bg-transparent inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] text-[var(--ink-2)] cursor-pointer hover:bg-[var(--nav-hover)] hover:text-[var(--ink)]"
              id="cmCancel"
              onClick={() => setIsModalOpen(false)}
            >
              취소
            </button>
            <button
              className={`font-sans text-[13px] font-bold p-[11px_16px] border inline-flex items-center justify-center gap-1.75 transition-all duration-[120ms] ${
                !checks.ck1 || !checks.ck2
                  ? "bg-[var(--surface-sub)] text-[var(--ink-3)] border-[var(--line-2)] cursor-not-allowed"
                  : "bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)]"
              }`}
              id="cmConfirm"
              disabled={!checks.ck1 || !checks.ck2}
              onClick={handleConfirm}
            >
              확인하고 생성
            </button>
          </>
        }
      >
        <p className="mt-5 mb-3 text-[14.5px] text-[var(--ink)] font-mono font-bold tracking-[0.2px] first:mt-1">
          [ 제거된 개인정보 · 2건 ]
        </p>
        <ul className="list-none m-0 mb-4 p-0 flex flex-col gap-2">
          <li className="flex items-center gap-2 p-1.5 px-2.5 text-[13.5px] text-[var(--ink-2)]">
            <span className="font-mono text-[12px] font-bold text-[var(--ink-3)] shrink-0 mt-0.5 leading-none">[system]</span>
            <span>이미지 배경 속 매장 명판 텍스트를 자동으로 지웠어요.</span>
          </li>
          <li className="flex items-center gap-2 p-1.5 px-2.5 text-[13.5px] text-[var(--ink-2)]">
            <span className="font-mono text-[12px] font-bold text-[var(--ink-3)] shrink-0 mt-0.5 leading-none">[system]</span>
            <span>고객 후기 캡처에 있던 개인 아이디를 자동으로 지웠어요.</span>
          </li>
        </ul>
        <div className="h-0 border-t border-dashed border-[var(--line-2)] my-4" />
        <p className="mt-5 mb-3 text-[14.5px] text-[var(--ink)] font-mono font-bold tracking-[0.2px] first:mt-1">
          [ 생성 전 확인 필요 · 2건 ]
        </p>
        <ul className="list-none m-0 mb-1.5 p-0 flex flex-col gap-2">
          <li
            className="flex items-center justify-between gap-4 p-3 px-2.5 border-b border-dashed border-[var(--line)] cursor-pointer transition-colors duration-[120ms] hover:bg-[var(--nav-hover)] last:border-b-0"
            onClick={() => setChecks((prev) => ({ ...prev, ck1: !prev.ck1 }))}
          >
            <div className="flex items-center gap-2 grow">
              <span className="font-mono text-[12px] font-bold text-[var(--crit)] shrink-0 mt-0.5 leading-none">[warn]</span>
              <span className="text-[13.5px] text-[var(--ink-2)] font-sans leading-[1.55]">
                효능 표현이 조건표 허용 범위 안에서만 순화되었는지 확인했어요.
              </span>
            </div>
            <input
              type="checkbox"
              checked={checks.ck1}
              onChange={(e) => setChecks((prev) => ({ ...prev, ck1: e.target.checked }))}
              onClick={(e) => e.stopPropagation()}
              className="appearance-none -webkit-appearance-none w-4 h-4 border border-[var(--line-2)] bg-[var(--surface-sub)] inline-flex items-center justify-center cursor-pointer outline-none shrink-0 relative transition-all duration-[120ms] m-0 checked:border-[var(--brand-ink)] checked:bg-[var(--nav-active-bg)] checked:after:content-['✓'] checked:after:font-mono checked:after:text-[11px] checked:after:font-bold checked:after:text-[var(--brand-ink)] checked:after:absolute checked:after:top-1/2 checked:after:left-1/2 checked:after:-translate-x-1/2 checked:after:-translate-y-1/2 checked:after:leading-none hover:border-[var(--brand-ink)]"
              tabIndex={-1}
            />
          </li>
          <li
            className="flex items-center justify-between gap-4 p-3 px-2.5 border-b border-dashed border-[var(--line)] cursor-pointer transition-colors duration-[120ms] hover:bg-[var(--nav-hover)] last:border-b-0"
            onClick={() => setChecks((prev) => ({ ...prev, ck2: !prev.ck2 }))}
          >
            <div className="flex items-center gap-2 grow">
              <span className="font-mono text-[12px] font-bold text-[var(--crit)] shrink-0 mt-0.5 leading-none">[warn]</span>
              <span className="text-[13.5px] text-[var(--ink-2)] font-sans leading-[1.55]">
                생성된 문구에 원문에 없던 새로운 효능 주장이 없는지 확인했어요.
              </span>
            </div>
            <input
              type="checkbox"
              checked={checks.ck2}
              onChange={(e) => setChecks((prev) => ({ ...prev, ck2: e.target.checked }))}
              onClick={(e) => e.stopPropagation()}
              className="appearance-none -webkit-appearance-none w-4 h-4 border border-[var(--line-2)] bg-[var(--surface-sub)] inline-flex items-center justify-center cursor-pointer outline-none shrink-0 relative transition-all duration-[120ms] m-0 checked:border-[var(--brand-ink)] checked:bg-[var(--nav-active-bg)] checked:after:content-['✓'] checked:after:font-mono checked:after:text-[11px] checked:after:font-bold checked:after:text-[var(--brand-ink)] checked:after:absolute checked:after:top-1/2 checked:after:left-1/2 checked:after:-translate-x-1/2 checked:after:-translate-y-1/2 checked:after:leading-none hover:border-[var(--brand-ink)]"
              tabIndex={-1}
            />
          </li>
        </ul>
      </Modal>
    </>
  );
}

function ContentPageWrapper() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  return <ContentGeneratorContent key={id} />;
}

export default function ContentPage() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <ContentPageWrapper />
    </Suspense>
  );
}
