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
import { Dropzone } from "@/components/Dropzone";
import { useTier, useImproveQuota } from "@/lib/tier";
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
    imagesUploaded: ["상세페이지 상단 배너", "제품 텍스처 컷", "임상 결과 그래프"],
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
    imagesUploaded: ["상세페이지 상단 컷", "전성분 표기 컷"],
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

  const { tier } = useTier();
  const { remaining, consume, resetWithAd } = useImproveQuota();

  const [report, setReport] = useState<CheckReport | null>(null);
  const [loading, setLoading] = useState(!!id);
  // 클릭 후 /generate 응답을 기다리는 동안. 초기 리포트 로딩(loading)과 분리한다 -
  // 하나로 묶으면 "리포트 불러오는 중"이라는 문구가 생성 대기에도 그대로 뜬다
  // (팀장 지시로 로딩 UI 분리, 2026-08-23).
  const [generating, setGenerating] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
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
  // 상품 스펙표(제형·용량) 입력. 둘 다 비워두면 백엔드가 표 모듈 자체를 안
  // 만든다(ensure_product_spec_module) - 표 카드가 화면에서 사라지는 버그의
  // 원인 중 하나였다(입력할 UI가 없어서 정상 입력 경로를 아무도 테스트한 적이
  // 없었다, 2026-08-23).
  const [createFormulationType, setCreateFormulationType] = useState("");
  const [createVolume, setCreateVolume] = useState("");
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
  const addProductPhotos = (files: FileList | File[] | null) => {
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

  // 미리보기·내보내기에 쓰는 제품명.
  const displayProductName = createProductName || (report ? "제품" : "선크림");

  // 내보내기 파일명. 예전엔 "detail_draft.html"·"${mockKey}_detail_draft.png"로
  // 상품명과 무관하게 고정이었다(파일 여러 개 받으면 다 같은 이름이라 구분이 안 됨,
  // 2026-08-24 팀장 지적). 상품명을 파일명에 쓰되 경로 구분자·따옴표 등은 지운다.
  const exportFileBase =
    displayProductName.trim().replace(/[\\/:*?"<>|]+/g, "").replace(/\s+/g, "_").slice(0, 60) || "detail";

  // 수용된 지적 목록 추출
  const acceptedIndices = acceptedParam
    ? acceptedParam.split(",").map(Number)
    : report
      ? report.findings.map((f, idx) => (f.flag === "위반" ? idx : -1)).filter((idx) => idx !== -1)
      : [1, 2]; // 기본 mockup에서는 위반 2건 수용

  // findingIdx를 들고 있어야 report.replacements와 finding_index로 짝지을 수 있다
  // (PR #265 - 판정할 때 배치로 만들어진 진짜 대체표현. 데모용 하드코딩 목록으로
  // 대신하던 걸 실제 값으로 바꾼다, 2026-08-23 팀장 실측 버그).
  const acceptedFindings: Array<{
    span: string;
    violation_type: string;
    findingIdx: number;
    mockReplacement?: string;
  }> = report
    ? report.findings
        .map((f, idx) => ({ span: f.span, violation_type: f.violation_type, findingIdx: idx }))
        .filter((f) => acceptedIndices.includes(f.findingIdx))
    : [
        {
          span: "손상된 피부를 재생",
          violation_type: "1호_의약품오인",
          findingIdx: -1,
          mockReplacement: "피부 장벽을 보호하고 건강하게 가꿈",
        },
        {
          span: "시중 제품 대비 3배 빠른 흡수",
          violation_type: "5호_거짓과장기만",
          findingIdx: -1,
          mockReplacement: "산뜻하고 빠르게 흡수",
        },
      ];

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

  // 순서를 뒤집는다(팀장 지시, 2026-08-23): 예전엔 "생성 전 확인" 모달을
  // 하드코딩된 문구로 채워서 무엇을 지울지 정해지지도 않은 시점에 "지웠다"고
  // 확언하고 있었다. 이제 생성 API를 먼저 부르고, 응답의 pii_removed·
  // risk_confirmations로 모달을 채운 뒤 사용자가 확인해야 결과를 확정
  // 표시한다("생성 전"이 아니라 "결과 확정 전" 확인).
  const handleGenerate = async () => {
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
          formulation_type: createFormulationType.trim() || undefined,
          volume: createVolume.trim() || undefined,
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

        // 위반 span(지적된 문구 자체)을 전성분인 척 보내고 있었다. 백엔드
        // 성분대조 로직이 이걸 실제 전성분으로 읽고 "고시원료가 전성분에
        // 없다"는 지어낸 근거로 위반을 판정하는 사고로 이어짐(베베 확인,
        // 2026-08-23). 실제 전성분 입력값이 없으면 그냥 안 보낸다 - 백엔드는
        // None이면 "전성분 미입력, 확인 못 함"으로 정직하게 검토필요를 낸다.
        //
        // approved_replacements: 리포트에서 수용한 대체표현을 그대로 실어
        // 보낸다. 안 보내면 백엔드가 판정을 처음부터 다시 돌리고(비용 2배)
        // 검출된 모든 위반을 치환해서, 사용자가 고른 항목이 무시되고 생성마다
        // 결과가 실행편차로 흔들린다(2026-08-23 베베 감사로 발견). mock
        // 리포트(report===null)는 승인할 실제 리포트가 없어 그대로 둔다.
        const approvedReplacements = report
          ? report.replacements
              .filter((r) => r.finding_index !== null && r.finding_index !== undefined && acceptedIndices.includes(r.finding_index))
              .map((r) => ({
                original: r.original,
                replaced: r.replaced,
                finding_index: r.finding_index,
                violation_type: r.violation_type,
                note: r.note,
              }))
          : undefined;

        res = await generateContent({
          mode: "improve",
          content: rawContent,
          result_id: id || undefined,
          product_name: createProductName || undefined,
          certifications: [],
          approved_replacements: approvedReplacements,
        });
      }
      if (mode === "improve" && tier === "Free") consume();
      setGenResult(res);
      setConfirmedRisks({});
      setIsModalOpen(true);
    } catch (err) {
      console.error(err);
      showError("콘텐츠 생성 오류", "콘텐츠 생성 중 오류가 발생했습니다: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setGenerating(false);
    }
  };

  // 모달에서 확인 항목을 다 체크한 뒤에만 결과를 확정 표시한다.
  const allRisksConfirmed = !genResult || genResult.risk_confirmations.every((rc) => confirmedRisks[rc.id]);

  const handleConfirmResult = () => {
    setIsModalOpen(false);
    setIsGenerated(true);
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

  // 원본 그대로 data URI로 굽던 걸 canvas로 리사이즈·재인코딩한다. 상세페이지
  // 카드는 max-width:520px(.detailpage)인데 원본 생성 이미지는 1264x848·
  // 450~590KB짜리라 카드 5~6장이면 내보낸 HTML이 2.7MB까지 불었다(팀장 지적,
  // 2026-08-24 실측 3,239,743바이트). 레티나 감안 폭 1040px+JPEG q0.82로
  // 실측 확인: 573KB→52KB(11배 감소), 원본과 나란히 놓고 봐도(전체·확대 크롭
  // 둘 다) 눈에 띄는 화질 저하 없음. 알파 채널 있는 이미지만 WebP(JPEG는 알파를
  // 못 담는다) - 실제 생성 이미지는 전부 불투명 사진이라 대부분 JPEG로 간다.
  const hasAlphaChannel = (ctx: CanvasRenderingContext2D, w: number, h: number): boolean => {
    const { data } = ctx.getImageData(0, 0, w, h);
    // 전체 픽셀을 다 보면 큰 이미지에서 느려서 37픽셀 간격으로 샘플링한다(소수 스텝이라
    // 격자 패턴과 안 겹친다). 실측 대상이 전부 사진이라 이 정도 샘플로 충분하다.
    for (let i = 3; i < data.length; i += 4 * 37) {
      if (data[i] < 255) return true;
    }
    return false;
  };

  const compressImage = (blob: Blob, maxWidth = 1040, quality = 0.82): Promise<string> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const objectUrl = URL.createObjectURL(blob);
      img.onload = () => {
        URL.revokeObjectURL(objectUrl);
        const scale = Math.min(1, maxWidth / img.naturalWidth);
        const w = Math.round(img.naturalWidth * scale);
        const h = Math.round(img.naturalHeight * scale);
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("2d context 생성 실패"));
          return;
        }
        ctx.drawImage(img, 0, 0, w, h);
        const mime = hasAlphaChannel(ctx, w, h) ? "image/webp" : "image/jpeg";
        resolve(canvas.toDataURL(mime, quality));
      };
      img.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        reject(new Error("이미지 디코드 실패"));
      };
      img.src = objectUrl;
    });
  };

  // HTML 내보내기 (Blob)
  // 이미지를 data URI로 바꿔 내보낸 HTML이 네트워크 없이도 혼자 열리게 한다 (타임아웃 3초 시 원본 URL로 안전 폴백).
  const toDataUri = async (url: string): Promise<string | null> => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(resolveImageUrl(url), { signal: controller.signal });
      clearTimeout(timeoutId);
      if (!res.ok) return resolveImageUrl(url);
      const blob = await res.blob();
      try {
        return await compressImage(blob);
      } catch {
        // 리사이즈 실패(디코드 안 되는 포맷 등)해도 "네트워크 없이 혼자 열리는" 보장은
        // 지킨다 - 용량 절감만 포기하고 원본 그대로 data URI로 굽는다.
        return await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result as string);
          reader.onerror = () => resolve(resolveImageUrl(url));
          reader.readAsDataURL(blob);
        });
      }
    } catch {
      return resolveImageUrl(url);
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

      // 인정문구(source="approved_claim")는 법정 고정 문구라 우리가 늘리거나
      // 꾸미면 안 된다 - 짧게 끝나는 게 정상이다. 근데 짧은 한 줄만 있으면
      // "본문 없는 깨진 카드"처럼 보인다(베베 발견, 2026-08-23). 어느 모듈에
      // 붙을지 고정돼 있지 않아(_link_risky_module_sections가 계획 순서대로
      // 아무 위험 모듈에나 꽂는다, 베베 확인) layoutType 분기와 무관하게
      // source로만 판단하고 모든 분기에 태그를 넣는다.
      const isApprovedClaim = s.source === "approved_claim";
      const claimTag = isApprovedClaim ? `<span class="dp-claim-tag">인정문구</span>` : "";
      const claimTagOnLight = isApprovedClaim ? `<span class="dp-claim-tag-onlight">인정문구</span>` : "";

      if ((idx === 0 || layoutType === "hero_fullbleed") && dataUri) {
        const { headline, subcopy } = splitHeadline(s.text);
        return `${swapComment}
    <div class="dp-hero" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')">
      <div class="dp-hero-card"><span>${escapeHtml(productName)}</span>${claimTag}<p>${escapeHtml(headline)}${subcopy ? ` ${escapeHtml(subcopy)}` : ""}</p></div>
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
      <div class="dp-split-copy">${claimTagOnLight}<p class="dp-headline">${escapeHtml(headline)}</p>${subcopy ? `<p class="dp-subcopy">${escapeHtml(subcopy)}</p>` : ""}</div>
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
      <div class="dp-split-copy">${claimTagOnLight}<p class="dp-step-text">${escapeHtml(s.text)}</p></div>
    </div>`;
      }

      if (layoutType === "section_statement") {
        const { headline, subcopy } = splitHeadline(s.text);
        const tone = statementAltIndex % 2 === 0 ? "" : " dp-statement-sub";
        statementAltIndex++;
        return `<div class="dp-statement${tone}${finePrint}">${claimTagOnLight}<p class="dp-headline">${escapeHtml(headline)}</p>${subcopy ? `<p class="dp-subcopy">${escapeHtml(subcopy)}</p>` : ""}</div>`;
      }

      if (layoutType === "mood_macro" && dataUri) {
        // 텍스처/원료 클로즈업 무드컷. 텍스트는 짧은 캡션 하나만(또는 생략).
        const { headline } = splitHeadline(s.text);
        return `${swapComment}
    <div class="dp-mood" data-swap="${escapeAttr(s.kind)}" style="background-image:url('${dataUri}')"></div>
    ${aiImageCaption}
    ${headline ? `${claimTagOnLight}<p class="dp-caption">${escapeHtml(headline)}</p>` : ""}`;
      }

      if (layoutType === "banner_strip") {
        return `<div class="dp-banner">${claimTagOnLight}<p>${escapeHtml(s.text)}</p></div>`;
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
    <div class="dp-block${finePrint}">${claimTagOnLight}<p>${escapeHtml(s.text)}</p></div>`;
      }
      return `<div class="dp-block${finePrint}">${claimTagOnLight}<p>${escapeHtml(s.text)}</p></div>`;
    }).join("\n    ");

    // 카드형 산출물 렌더링(useCards는 위에서 이미 계산). 백엔드가 sections·
    // module_images·layout_plan을 module_kind로 이미 짝지어 카드로 낸다 - 프론트는
    // 더 이상 매칭하지 않는다.
    let cardsHtml = "";
    if (useCards) {
      const cardBlocks = await Promise.all(
        [...result.cards].sort((a, b) => a.order - b.order).map(async (card) => {
          const dataUri = card.image_url
            ? await resolveOrInline(card.image_url)
            : null;
          const isAiGenerated = card.image_status === "generated";
          const imageCaption = isAiGenerated && dataUri ? aiImageCaption : "";
          const finePrintCard = isFinePrintKind(card.module_kind) ? " dp-fine" : "";
          const swapComment = `<!-- 이미지 교체: 아래 background-image url(...)을 판매자 본인 제품 사진으로 바꾸세요. data-swap="${escapeAttr(card.module_kind)}" -->`;
          // 실증자료 필요 고지. 있으면 카드 유형과 무관하게 항상 같이 낸다(빠뜨리면
          // 사용자가 위반에서 벗어난 줄 안다, 2026-08-20 팀장 지시와 같은 이유).
          const noteHtml = card.note ? `<div class="dp-block dp-fine"><p>${escapeHtml(card.note)}</p></div>` : "";
          // 인정문구(text_source="approved_claim")는 법정 고정 문구라 짧게
          // 끝나는 게 정상이다 - "본문 없는 깨진 카드"처럼 안 보이게 작은 태그로
          // 의도된 짧음임을 드러낸다(베베 발견, 2026-08-23). 어느 모듈에 붙을지
          // 고정돼 있지 않다 - _link_risky_module_sections가 계획 순서대로
          // 아무 위험 모듈에나 꽂아서 매 생성마다 카드 kind가 달라질 수 있다
          // (베베 확인). 그래서 layout_type 분기와 무관하게 text_source로만
          // 판단하고, 모든 분기에 태그를 넣는다. 히어로(사진 위, 밝은 글자)와
          // 나머지(밝은 배경, 어두운 글자)는 대비가 반대라 톤을 분리한다.
          const isApprovedClaim = card.text_source === "approved_claim";
          const claimTag = isApprovedClaim ? `<span class="dp-claim-tag">인정문구</span>` : "";
          const claimTagOnLight = isApprovedClaim ? `<span class="dp-claim-tag-onlight">인정문구</span>` : "";

          // 표 카드(상품 스펙표): headline·body가 비어 있고 table_rows만 있다
          // (PR #314, 베베). 문장 카드와 같은 틀로 그리면 빈 카드처럼 보이니
          // 먼저 걸러서 실제 <table>로 그린다. 옛 sections 경로의 dp-table
          // 스타일을 그대로 재사용(레이아웃 새로 안 만듦).
          if (card.layout_type === "table_info" && card.table_rows && card.table_rows.length > 0) {
            const rowsHtml = card.table_rows
              .map((r) => `<tr><td>${escapeHtml(r.label)}</td><td>${escapeHtml(r.value)}</td></tr>`)
              .join("");
            return `<div class="dp-table-wrap"><table class="dp-table">${rowsHtml}</table></div>
    ${noteHtml}`;
          }

          // 실증자료 수치강조 카드: layout_type이 아니라 card.clinical_stat 유무로
          // 분기한다(베베 계약, 2026-08-24) - 계획기가 clinical_bar_compare를
          // 고르든 다른 유형을 고르든 백엔드가 줄 수 있는 건 claim/value 단일
          // 수치뿐이라 layout_type별로 갈라봐야 그릴 게 같다. value는 자유표기라
          // ("87%"도 "4주 후 2.1배"도 온다) 퍼센트로 가정해 막대 길이 등을
          // 계산하지 않고 원문 그대로 큰 글자로 낸다(비교 대상 없는 단일 수치라
          // dataviz 스킬 기준으로 "히어로 figure" - 팔레트 검증 대상 아님).
          if (card.clinical_stat) {
            const stat = card.clinical_stat;
            const footParts = [stat.period, stat.institution, stat.note].filter((v): v is string => !!v);
            const footHtml = footParts.length > 0
              ? `<p class="dp-stat-foot">${footParts.map(escapeHtml).join(" · ")}</p>`
              : "";
            return `<div class="dp-stat">${claimTagOnLight}<p class="dp-stat-label">${escapeHtml(stat.claim)}</p><p class="dp-stat-value">${escapeHtml(stat.value)}</p>${footHtml}</div>
    ${noteHtml}`;
          }

          // card.body(본문)가 8개 템플릿 어디에서도 렌더되지 않고 있었다 -
          // headline만 <p>로 넣고 body는 그냥 버려졌다(팀장이 직접 코드로 확인,
          // 2026-08-23). 백엔드는 헤드라인·본문을 둘 다 정상 생성하는데 화면엔
          // 본문이 아예 안 나가 상세페이지가 헤드라인만 나열된 것처럼 부실해
          // 보였다. 옛 sections 경로가 쓰던 .dp-subcopy를 그대로 재사용한다.
          const bodyHtml = card.body ? `<p class="dp-subcopy">${escapeHtml(card.body)}</p>` : "";

          if (dataUri) {
            return `${swapComment}
    <div class="dp-card" data-swap="${escapeAttr(card.module_kind)}">
      <div class="dp-card-media-wrap">
        <img src="${dataUri}" alt="${escapeAttr(card.headline || '상세 이미지')}" class="dp-card-img" />
        ${imageCaption}
      </div>
      <div class="dp-card-body">
        ${claimTagOnLight}
        ${card.headline ? `<p class="dp-headline">${escapeHtml(card.headline)}</p>` : ""}
        ${bodyHtml}
      </div>
    </div>
    ${noteHtml}`;
          }

          return `<div class="dp-card-text${finePrintCard}">
      <div class="dp-card-body">
        ${claimTagOnLight}
        ${card.headline ? `<p class="dp-headline">${escapeHtml(card.headline)}</p>` : ""}
        ${bodyHtml}
      </div>
    </div>
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
    .dp-card { margin-bottom: 0; background: var(--dp-surface); border-bottom: 1px solid var(--dp-line); }
    .dp-card:last-child { border-bottom: none; }
    .dp-card-media-wrap { position: relative; width: 100%; background: var(--dp-surface-sub); }
    .dp-card-img { width: 100%; height: auto; display: block; object-fit: contain; }
    .dp-ai-caption { margin: 6px 16px 8px; font-size: 10px; font-weight: 500; letter-spacing: .2px; color: var(--dp-ink-3); text-align: right; }
    .dp-card-body { padding: 22px 24px 26px; text-align: center; }
    .dp-headline { margin: 0 0 8px; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 18px; font-weight: 700; letter-spacing: -0.3px; line-height: 1.45; color: var(--dp-ink); }
    .dp-subcopy { margin: 0; font-family: "Pretendard Variable", Pretendard, sans-serif; font-size: 13.5px; font-weight: 400; line-height: 1.75; color: var(--dp-ink-2); word-break: keep-all; }
    .dp-card-text { padding: 28px 24px; text-align: center; border-bottom: 1px solid var(--dp-line); background: var(--dp-surface); }
    .dp-card-text.dp-fine { background: var(--dp-surface-sub); padding: 18px 24px; }
    .dp-card-text:last-child { border-bottom: none; }
    .dp-claim-tag-onlight { display: inline-block; font-family: "Pretendard Variable", Pretendard, sans-serif; font-size: 10px; font-weight: 600; letter-spacing: 0.3px; color: var(--dp-ink-3); background: var(--dp-surface-sub); border: 1px solid var(--dp-line); border-radius: 3px; padding: 2px 7px; margin: 0 0 8px; }
    .dp-ai-notice { padding: 12px 24px; font-size: 11px; color: var(--dp-ink-3); background: var(--dp-surface-sub); line-height: 1.6; }
    .dp-block { padding: 34px 24px; }
    .dp-block p { margin: 0; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 16px; font-weight: 500; line-height: 1.8; color: var(--dp-ink-2); letter-spacing: -0.1px; }
    .dp-block.dp-fine { padding: 20px 24px; background: var(--dp-surface-sub); }
    .dp-block.dp-fine p { font-family: "Pretendard Variable", Pretendard, sans-serif; font-size: 11.5px; font-weight: 400; line-height: 1.7; color: var(--dp-ink-3); }
    .dp-step-text { margin: 0; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 14.5px; font-weight: 500; line-height: 1.8; color: var(--dp-ink-2); white-space: pre-line; }
    .dp-table-wrap { padding: 20px 24px; }
    .dp-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
    .dp-table tr { border-bottom: 1px solid var(--dp-line); }
    .dp-table tr:last-child { border-bottom: none; }
    .dp-table td { padding: 10px 4px; }
    .dp-table td:first-child { color: var(--dp-ink-3); width: 30%; }
    .dp-table td:last-child { color: var(--dp-ink-2); font-weight: 600; }
    .dp-stat { padding: 32px 24px; background: var(--dp-surface); text-align: center; border-bottom: 1px solid var(--dp-line); }
    .dp-stat-label { margin: 0 0 10px; font-family: "Pretendard Variable", Pretendard, sans-serif; font-size: 13px; font-weight: 600; color: var(--dp-ink-3); }
    .dp-stat-value { margin: 0; font-family: "SUIT Variable", "SUIT", "Pretendard Variable", sans-serif; font-size: 40px; font-weight: 700; color: var(--dp-accent); letter-spacing: -0.5px; line-height: 1.2; }
    .dp-stat-foot { margin: 10px 0 0; font-family: "Pretendard Variable", Pretendard, sans-serif; font-size: 11px; color: var(--dp-ink-3); }
    .dp-close { padding: 20px 24px; border-top: 1px solid var(--dp-line); font-size: 11px; color: var(--dp-ink-3); line-height: 1.65; background: var(--dp-surface-sub); }
  </style>`;

    const detailPageHtml = `<div class="detailpage">
    ${useCards ? cardsHtml : `${sectionsHtml}\n${imagesHtml}`}
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
    a.download = `${exportFileBase}_draft.html`;
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
      a.download = `${exportFileBase}_draft.png`;
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

      pdf.save(`${exportFileBase}_draft.pdf`);
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
            <span className="text-[var(--ink-3)] font-mono text-[10.5px]">* 필수 표시 외 항목은 없으면 해당 모듈이 제외됩니다</span>
          </div>

          <div className="grid grid-cols-2 gap-4 max-[900px]:grid-cols-1">
            {/* 좌측 열: 기본 제품 정보 & 비주얼 */}
            <div className="flex flex-col gap-3.5">
              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
                <label className="block font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_8px] tracking-[0.3px]">
                  제품명 <span className="text-[var(--crit)]">*</span>
                </label>
                <input
                  type="text"
                  value={createProductName}
                  onChange={(e) => setCreateProductName(e.target.value)}
                  placeholder="예: 글로우 세럼"
                  className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[13px] p-[8px_10px] outline-none focus:border-[var(--brand)]"
                />
              </div>

              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">
                  제품 사진 (AI 합성 시 참고 이미지로 사용)
                </p>
                <Dropzone
                  accept="image/png,image/jpeg,image/webp"
                  supportedExtensions="PNG · JPG · WEBP"
                  title="제품 사진 던져넣기"
                  subtitle="drop or click · 여러 장 가능"
                  compact
                  onFilesSelected={addProductPhotos}
                />
                {createProductPhotos.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2.5">
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
                          className="absolute top-0.5 right-0.5 w-4 h-4 flex items-center justify-center bg-black/60 text-white cursor-pointer hover:bg-black/80"
                        >
                          <Trash size={10} weight="bold" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">제형·용량 (상품 스펙표 모듈용)</p>
                <div className="grid grid-cols-2 gap-2 max-[600px]:grid-cols-1">
                  <input
                    type="text"
                    value={createFormulationType}
                    onChange={(e) => setCreateFormulationType(e.target.value)}
                    placeholder="제형 (예: 크림, 액상)"
                    className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                  />
                  <input
                    type="text"
                    value={createVolume}
                    onChange={(e) => setCreateVolume(e.target.value)}
                    placeholder="용량 (예: 50ml)"
                    className="w-full border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                  />
                </div>
                <p className="m-[8px_0_0] text-[11px] text-[var(--ink-3)]">둘 다 비워두면 상품 스펙표 모듈 자체를 안 만들어요.</p>
              </div>

              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">색상톤·분위기 (이미지·문구 생성에 반영)</p>
                <div className="grid grid-cols-2 gap-2 max-[600px]:grid-cols-1">
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
            </div>

            {/* 우측 열: 법적 근거 & 증빙 자료 */}
            <div className="flex flex-col gap-3.5">
              <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">전성분 + 함량 (인정문구 함량기준 대조용)</p>
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
                        className="w-[110px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12.5px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
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
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">보유 인증서 (인정문구 매칭용)</p>
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
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">실증자료 (임상 수치 모듈에만 필요. barum은 진위를 검증하지 않습니다)</p>
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
                          placeholder="시험기관명"
                          className="flex-1 border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                        />
                        <input
                          type="text"
                          value={row.period || ""}
                          onChange={(e) => updateClinicalEvidence(row.id, "period", e.target.value)}
                          placeholder="시험기간 (예: 4주)"
                          className="w-[130px] border border-[var(--line-2)] bg-[var(--surface-sub)] text-[var(--ink)] text-[12px] p-[6px_9px] outline-none focus:border-[var(--brand)]"
                        />
                      </div>
                      <input
                        type="text"
                        value={row.note || ""}
                        onChange={(e) => updateClinicalEvidence(row.id, "note", e.target.value)}
                        placeholder="피험자 수·조건 등 부연"
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
                <p className="font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_10px] tracking-[0.3px]">설문조사 결과 (향·발림성·재구매의향 등 비효능 항목만. 실증자료 아님)</p>
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
            </div>
          </div>

          {/* 하단 전폭: 추가정보 및 이미지 생성 설정 */}
          <div className="flex flex-col gap-3.5 mt-3.5">
            <div className="border border-[var(--line-2)] bg-[var(--surface)] p-[15px_16px]">
              <label className="block font-mono text-[10.5px] text-[var(--ink-3)] m-[0_0_8px] tracking-[0.3px]">추가정보</label>
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
              <ul className="list-none m-0 p-0 flex flex-col gap-2">
                {acceptedFindings.map((f, i) => {
                  const rep = report?.replacements.find((r) => r.finding_index === f.findingIdx);
                  const replacedText = rep?.replaced || f.mockReplacement;
                  const isReplaced = !!replacedText;

                  return (
                    <li key={i} className="text-[12.5px] text-[var(--ink-2)] flex items-start gap-2">
                      {isReplaced ? (
                        <svg className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[var(--brand-ink)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                          <path d="M4 12l5 5L20 6" />
                        </svg>
                      ) : (
                        <span className="shrink-0 mt-0.5 text-[var(--ink-3)] font-mono text-[11px]">[-]</span>
                      )}
                      <span>
                        {isReplaced ? (
                          <>
                            <span className="text-[var(--ink-3)] line-through decoration-[var(--ink-3)]">{f.span}</span>
                            <span className="text-[var(--ink-3)] mx-1">→</span>
                            <span className="font-semibold text-[var(--ink)]">{replacedText}</span>
                          </>
                        ) : (
                          <>
                            <span className="text-[var(--ink-2)]">{f.span}</span>
                            <span className="text-[var(--ink-3)] text-[11.5px] ml-1.5">(자동 수정 불가 · 원문 유지)</span>
                          </>
                        )}
                        {rep?.note && (
                          <span className="block text-[11px] text-[var(--ink-3)] mt-0.5">ⓘ {rep.note}</span>
                        )}
                      </span>
                    </li>
                  );
                })}
                {acceptedFindings.length === 0 && (
                  <li style={{ color: "var(--ink-3)" }}>수용 처리된 수정 권고안이 없습니다.</li>
                )}
              </ul>
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
                ? "입력한 제품 정보로 상세페이지 초안 1안을 만듭니다. 생성 후 확인이 필요한 항목이 있으면 결과를 보여드리기 전에 먼저 보여드려요."
                : "입력 요약을 반영해 상세페이지 초안 1안을 만듭니다. 생성 후 확인이 필요한 항목이 있으면 결과를 보여드리기 전에 먼저 보여드려요."}
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
              onClick={handleGenerate}
            >
              생성하기 <span className="font-mono">→</span>
            </button>
          </div>
        )}

        {/* 생성 결과 (게이트 통과 후 표시) */}
        {isGenerated && genResult && (
          <div id="resultWrap">
            {/* recheck.safe(=n_findings===0)는 위반·검토필요를 안 갈랐다. 검토필요는
                실증자료를 요구하는 정상 동작이지 실패가 아닌데, safe 기준으로 배지를
                그리면 "위반 0건, 검토필요만 있음"도 "재검증 실패"로 떴다(팀장 실측,
                2026-08-23). 위반 유무만으로 통과/실패를 가르고, 검토필요는 경고색
                없이 별도 정보로 안내한다. 구조적 불가/재판정 3분류는 백엔드
                dropped 노출이 아직 없어 보류(베베 후속 PR 예정) - 이번엔 위반
                유무 기준까지만. */}
            <div className="mb-3.5">
              {(() => {
                const hasViolation = genResult.recheck.n_violation > 0;
                return (
                  <div
                    className={`inline-flex items-center gap-1.75 font-mono text-[11.5px] p-[5px_10px] border ${
                      hasViolation
                        ? "border-[var(--crit-bd)] bg-[var(--crit-bg)] text-[var(--crit)]"
                        : "border-[var(--line-2)] bg-[var(--surface)] text-[var(--ink-2)]"
                    }`}
                    id="recheckBadge"
                  >
                    {/* "재검증 실패"라고 쓰지 않는다(팀장 지시, 2026-08-24). 생성이
                        실패한 게 아니라 자동으로 고칠 수 없는 표현이 남은 것이고,
                        "실패"는 산출물 전체가 못 쓰는 것처럼 읽힌다. 무엇을 해야
                        하는지(수정 필요)를 건수와 함께 사실대로 적는다. 색은
                        그대로 crit을 쓴다 - 남은 위반은 실제로 지금 급한 항목이라
                        DESIGN.md "빨강만 경보" 기준에 맞는다. */}
                    {hasViolation ? (
                      <>
                        <X size={14} weight="bold" className="text-[var(--crit)] mr-1" />
                        수정 필요 · 위반 {genResult.recheck.n_violation}건
                      </>
                    ) : (
                      <>
                        <Check size={14} weight="bold" className="text-[var(--brand-ink)] mr-1" />
                        재검증 통과
                      </>
                    )}
                  </div>
                );
              })()}
              {genResult.recheck.n_needs_review > 0 && (
                <p className="m-0 mt-1.5 text-[11px] text-[var(--ink-3)]">
                  검토필요 {genResult.recheck.n_needs_review}건 - 실증자료 확인이 필요한 표현입니다(위반 아님).
                </p>
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
                <span className="text-[var(--ink-2)]">{exportFileBase}_draft.html</span>
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
                        {/* 문장 하나에 지적이 여러 건이면 사유가 \n으로 이어붙어 온다
                            (PR #324, 베베) - pre-line 없으면 한 줄로 붙어 보인다. */}
                        <p className="m-[2px_0_0] text-[11.5px] text-[var(--ink-3)] whitespace-pre-line">{rc.reason}</p>
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

      {/* 결과 확정 전 확인 모달 (터미널 다이얼로그). 예전엔 "생성 전 확인"
          이름으로 생성 API 호출 전에 하드코딩된 문구를 보여줬다 - 뭘 지울지
          정해지지도 않은 시점에 "지웠다"고 확언하는 구조였다(팀장 실측,
          2026-08-23). 이제 생성이 끝난 뒤 실제 pii_removed·risk_confirmations로
          채우고, 사용자가 확인해야 결과 화면을 연다. */}
      <Modal
        isOpen={isModalOpen}
        title="생성 결과 확인"
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
                !allRisksConfirmed
                  ? "bg-[var(--surface-sub)] text-[var(--ink-3)] border-[var(--line-2)] cursor-not-allowed"
                  : "bg-[var(--brand)] text-[var(--on-brand)] border-[var(--brand)] cursor-pointer hover:bg-[var(--brand-deep)]"
              }`}
              id="cmConfirm"
              disabled={!allRisksConfirmed}
              onClick={handleConfirmResult}
            >
              확인하고 결과 보기
            </button>
          </>
        }
      >
        <p className="mt-5 mb-3 text-[14.5px] text-[var(--ink)] font-mono font-bold tracking-[0.2px] first:mt-1">
          [ 제거된 개인정보 · {genResult?.pii_removed.length ?? 0}건 ]
        </p>
        {genResult && genResult.pii_removed.length > 0 ? (
          <ul className="list-none m-0 mb-4 p-0 flex flex-col gap-2">
            {genResult.pii_removed.map((item, i) => (
              <li key={i} className="flex items-center gap-2 p-1.5 px-2.5 text-[13.5px] text-[var(--ink-2)]">
                <span className="font-mono text-[12px] font-bold text-[var(--ink-3)] shrink-0 mt-0.5 leading-none">[system]</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 mb-4 px-2.5 text-[13px] text-[var(--ink-3)]">제거된 개인정보가 없습니다.</p>
        )}
        <div className="h-0 border-t border-dashed border-[var(--line-2)] my-4" />
        <p className="mt-5 mb-3 text-[14.5px] text-[var(--ink)] font-mono font-bold tracking-[0.2px] first:mt-1">
          [ 확인 필요 · {genResult?.risk_confirmations.length ?? 0}건 ]
        </p>
        {genResult && genResult.risk_confirmations.length > 0 ? (
          <ul className="list-none m-0 mb-1.5 p-0 flex flex-col gap-2">
            {genResult.risk_confirmations.map((rc) => (
              <li
                key={rc.id}
                className="flex items-center justify-between gap-4 p-3 px-2.5 border-b border-dashed border-[var(--line)] cursor-pointer transition-colors duration-[120ms] hover:bg-[var(--nav-hover)] last:border-b-0"
                onClick={() => setConfirmedRisks((prev) => ({ ...prev, [rc.id]: !prev[rc.id] }))}
              >
                <div className="flex items-center gap-2 grow">
                  <span className="font-mono text-[12px] font-bold text-[var(--crit)] shrink-0 mt-0.5 leading-none">[warn]</span>
                  <span className="text-[13.5px] text-[var(--ink-2)] font-sans leading-[1.55]">
                    <span className="font-bold">{rc.text}</span>
                    {/* 문장 하나에 지적이 여러 건이면 사유가 \n으로 이어붙어 온다
                        (PR #324, 베베) - pre-line 없으면 한 줄로 붙어 보인다. */}
                    <span className="block text-[11.5px] text-[var(--ink-3)] mt-0.5 whitespace-pre-line">{rc.reason}</span>
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={!!confirmedRisks[rc.id]}
                  onChange={(e) => setConfirmedRisks((prev) => ({ ...prev, [rc.id]: e.target.checked }))}
                  onClick={(e) => e.stopPropagation()}
                  className="appearance-none -webkit-appearance-none w-4 h-4 border border-[var(--line-2)] bg-[var(--surface-sub)] inline-flex items-center justify-center cursor-pointer outline-none shrink-0 relative transition-all duration-[120ms] m-0 checked:border-[var(--brand-ink)] checked:bg-[var(--nav-active-bg)] checked:after:content-['✓'] checked:after:font-mono checked:after:text-[11px] checked:after:font-bold checked:after:text-[var(--brand-ink)] checked:after:absolute checked:after:top-1/2 checked:after:left-1/2 checked:after:-translate-x-1/2 checked:after:-translate-y-1/2 checked:after:leading-none hover:border-[var(--brand-ink)]"
                  tabIndex={-1}
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 mb-1.5 px-2.5 text-[13px] text-[var(--ink-3)]">확인이 필요한 항목이 없습니다.</p>
        )}
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
