"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getReport, generateContent } from "@/lib/api/client";
import type { CheckReport, GenerateResponse, Section } from "@/lib/api/schema";
import { Check, X, CaretDown, FileCode, FileImage, FilePdf } from "@phosphor-icons/react";
import { PageFooter } from "@/components/PageFooter/PageFooter";
import { Modal } from "@/components/Modal/Modal";

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

const SRC_LABEL = {
  remediation: "조건표 치환",
  llm: "LLM 생성",
  template: "표준 문구"
};

function getRemediationProposal(violationType: string, span: string): string {
  if (span.includes("아토피 피부염")) return "순화된 보습 표현으로 대체";
  if (span.includes("3배 빠른 흡수")) return "근거 없는 비교 수치 제거";
  if (span.includes("멜라닌")) return "생성 억제 대신 기능성 화장품 표현 활용";
  if (span.includes("주름을 개선")) return "주름 개선 기능성 심사 필 문구 사용";
  if (span.includes("염증을 가라앉히고")) return "의학적 판단 여지 제거 및 보습 완화";
  if (span.includes("파워 수분 공급")) return "자극적인 수식어 배제";
  return "순화된 표현 권고";
}

function ContentGeneratorContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const id = searchParams.get("id") || "";
  const acceptedParam = searchParams.get("accepted") || "";

  const [report, setReport] = useState<CheckReport | null>(null);
  const [loading, setLoading] = useState(!!id);
  const [isGenerated, setIsGenerated] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [checks, setChecks] = useState({ ck1: false, ck2: false });
  const [copied, setCopied] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [exportingType, setExportingType] = useState<"html" | "png" | "pdf" | null>(null);
  const [genResult, setGenResult] = useState<GenerateResponse | null>(null);
  const [confirmedRisks, setConfirmedRisks] = useState<Record<string, boolean>>({});

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
        setReport(envelope.report);
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
    setLoading(true);
    try {
      let rawContent = "";
      if (report) {
        rawContent = buildOriginalContent(report);
      } else {
        rawContent = "자외선 차단 100%! 피부 재생 및 기미·주근깨 완벽 치료하는 선크림 SPF50";
      }

      const ingredients = report
        ? Array.from(new Set(report.findings.map(f => f.span))).join(", ")
        : undefined;

      const res = await generateContent({
        mode: "improve",
        content: rawContent,
        result_id: id || undefined,
        product_name: report ? (mockKey === "image" ? "글로우 세럼" : "수분 크림") : "선크림",
        ingredients: ingredients || undefined,
        certifications: [],
      });
      setGenResult(res);
      setIsGenerated(true);
    } catch (err) {
      console.error(err);
      alert("콘텐츠 생성 중 오류가 발생했습니다: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
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
  const exportHtml = () => {
    if (!genResult) return;
    const productName = report ? (mockKey === "image" ? "글로우 세럼" : "수분 크림") : "제품";
    
    const sectionsHtml = genResult.sections.map((s) => {
      return `<div class="dp-block"><b>${s.kind} (${SRC_LABEL[s.source as keyof typeof SRC_LABEL] || s.source})</b><p>${s.text}</p></div>`;
    }).join("");

    const imagesHtml = genResult.image_plan.placed.map((img) => {
      return `<div class="dp-img"><span>${img.image_url}</span></div>`;
    }).join("");

    const htmlContent = `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>${productName} 상세페이지 초안</title>
  <style>
    body { font-family: sans-serif; padding: 40px; background: #E7ECEB; color: #14231B; display: flex; justify-content: center; }
    .detailpage { width: 100%; max-width: 520px; background: #fff; border: 1px solid #CDD6D3; }
    .dp-hero { aspect-ratio: 4/3; background: repeating-linear-gradient(135deg, #F0F3F2 0 10px, #FFFFFF 10px 20px); display: flex; align-items: flex-end; padding: 16px; }
    .dp-hero span { font-size: 19px; font-weight: 800; background: #fff; padding: 6px 10px; border: 1px solid #CDD6D3; }
    .dp-block { padding: 16px 18px; border-top: 1px solid #DDE4E2; }
    .dp-block b { font-size: 11.5px; color: #14231B; display: block; margin-bottom: 7px; }
    .dp-block p { margin: 0; font-size: 13.5px; line-height: 1.75; color: #33413A; }
    .dp-img { aspect-ratio: 16/10; background: repeating-linear-gradient(135deg, #F0F3F2 0 10px, #FFFFFF 10px 20px); border-top: 1px solid #DDE4E2; display: flex; align-items: center; justify-content: center; color: #5C6B62; font-size: 10px; font-family: monospace; }
    .dp-close { padding: 14px 18px; border-top: 1px dashed #CDD6D3; font-size: 11px; color: #5C6B62; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="detailpage">
    <div class="dp-hero"><span>${productName}</span></div>
    ${sectionsHtml}
    ${imagesHtml}
    <div class="dp-close">${genResult.disclaimer}</div>
  </div>
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
      exportHtml();
    } else if (type === "png") {
      await exportPng();
    } else if (type === "pdf") {
      await exportPdf();
    }
    setExportingType(null);
  };

  if (loading) {
    return <div className="devnote" style={{ padding: "40px 20px" }}>리포트를 불러오는 중입니다…</div>;
  }

  return (
    <>
      <div className="metastrip">
        <span className="crumb">
          <Link href="/" className="home">
            홈
          </Link>{" "}
          <span className="sep">›</span>{" "}
          <span
            onClick={() => router.push(id ? `/report/${id}` : "/")}
            style={{ cursor: "pointer" }}
            className="home"
          >
            리포트
          </span>{" "}
          <span className="sep">›</span> 콘텐츠 생성
        </span>
        <span className="devnote">
          {id ? `리포트 연동: ${id}` : "더미 데이터 모드"} · 백엔드 FR-11/13 완료
        </span>
      </div>

      {/* 입력 요약 */}
      <div className="sec">
        <div className="seclabel">
          <span className="n">01</span>
          <h2>입력 요약</h2>
          <span className="rule"></span>
          <span className="hint">리포트에서 수용 처리된 항목</span>
        </div>
        <div className="srcgrid">
          <div className="srccard">
            <p className="sctitle">수용된 수정 권고안 · {acceptedFindings.length}건</p>
            <ul className="srclist">
              {acceptedFindings.map((f, i) => (
                <li key={i}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                    <path d="M4 12l5 5L20 6" />
                  </svg>
                  <span>
                    <span className="strike">{f.span}</span>
                    <span className="arrow">→</span>
                    {getRemediationProposal(f.violation_type || "", f.span || "")}
                  </span>
                </li>
              ))}
              {acceptedFindings.length === 0 && (
                <li style={{ color: "var(--ink-3)" }}>수용 처리된 수정 권고안이 없습니다.</li>
              )}
            </ul>
          </div>
          <div className="srccard">
            <p className="sctitle">재사용한 업로드 이미지 · {uploadedImages.length}장</p>
            <div className="imgchips">
              {uploadedImages.map((img, i) => (
                <span key={i} className="imgchip">
                  {img}
                </span>
              ))}
              {uploadedImages.length === 0 && (
                <span className="devnote" style={{ color: "var(--ink-3)" }}>
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

      {/* 생성 결과 */}
      <div className="sec" style={{ borderBottom: 0 }}>
        <div className="seclabel">
          <span className="n">02</span>
          <h2>생성된 상세페이지 초안</h2>
          <span className="rule"></span>
          <span className="hint" id="secHint">
            {isGenerated ? "원샷 생성 · 편집 불가 · 재검증 통과" : "원샷 생성 · 편집 불가"}
          </span>
        </div>

        {/* 생성 전 게이트 */}
        {!isGenerated && (
          <div className="gate" id="gateCard">
            <p>입력 요약을 반영해 상세페이지 초안 1안을 만듭니다. 생성 전 확인이 필요한 항목이 있어요.</p>
            <button className="btn primary" id="startGen" ref={startGenRef} onClick={() => setIsModalOpen(true)}>
              확인 후 생성하기 <span className="mono">→</span>
            </button>
          </div>
        )}

        {/* 생성 결과 (게이트 통과 후 표시) */}
        {isGenerated && genResult && (
          <div id="resultWrap">
            <div className={`recheck${!genResult.recheck.safe ? " warn" : ""}`} id="recheckBadge" style={{
              backgroundColor: genResult.recheck.safe ? undefined : "var(--crit-bg)",
              borderColor: genResult.recheck.safe ? undefined : "var(--crit)",
              color: genResult.recheck.safe ? undefined : "var(--crit)"
            }}>
              {genResult.recheck.safe ? (
                <>
                  <Check size={14} weight="bold" style={{ color: "var(--brand-ink)", marginRight: "4px" }} />
                  재검증 통과 · 위반 0건 · 검토필요 0건
                </>
              ) : (
                <>
                  <X size={14} weight="bold" style={{ color: "var(--crit)", marginRight: "4px" }} />
                  재검증 실패 · 위반 {genResult.recheck.n_violation}건 · 검토필요 {genResult.recheck.n_needs_review}건
                </>
              )}
            </div>
            <div className="genframe">
              <div className="genhead">
                <span className="dot"></span>
                <span className="fname">detail_draft.html</span>
              </div>
              <div className="genbody">
                <div className="detailpage" id="detailPage">
                  <div className="dp-hero">
                    <span className="dp-htxt">{report ? (mockKey === "image" ? "글로우 세럼" : "수분 크림") : "선크림"}</span>
                  </div>
                  <div id="secList">
                    {genResult.sections.map((s, idx) => (
                      <div className="dp-block" key={idx}>
                        <div className="dp-kind">
                          <b>{s.kind}</b>
                          <span className="dp-src">{SRC_LABEL[s.source as keyof typeof SRC_LABEL] || s.source}</span>
                        </div>
                        <p>{s.text}</p>
                      </div>
                    ))}
                    {genResult.image_plan.placed.map((img, idx) => (
                      <div className="dp-block img" key={`img-${idx}`}>
                        <div className="dp-img">
                          <span className="dp-imglabel">{img.image_url}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="dp-close" id="dpDisclaimer">
                    {genResult.disclaimer}
                  </div>
                </div>
              </div>
            </div>
            {genResult.risk_confirmations.length > 0 && (
              <div className="srccard" style={{ margin: "14px 0", width: "100%", border: "1px solid var(--crit)" }}>
                <p className="sctitle" style={{ color: "var(--crit)", fontWeight: "bold" }}>⚠️ 자동 수정 불가 잔존 위험 · {genResult.risk_confirmations.length}건 (확인 필요)</p>
                <ul className="srclist" style={{ padding: "8px 12px" }}>
                  {genResult.risk_confirmations.map((rc) => (
                    <li key={rc.id} style={{ display: "flex", gap: "8px", alignItems: "flex-start", marginBottom: "8px" }}>
                      <input
                        type="checkbox"
                        id={rc.id}
                        checked={!!confirmedRisks[rc.id]}
                        onChange={(e) => setConfirmedRisks(prev => ({ ...prev, [rc.id]: e.target.checked }))}
                        style={{ marginTop: "3px" }}
                      />
                      <label htmlFor={rc.id} style={{ cursor: "pointer" }}>
                        <span style={{ fontWeight: "bold", fontSize: "13px" }}>{rc.text}</span>
                        <p style={{ margin: "2px 0 0", fontSize: "11.5px", color: "var(--ink-3)" }}>{rc.reason}</p>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="genactions">
              <p>
                생성된 문구는 리포트에서 수용한 권고안을 조건표 안에서 재배열한 것으로, 원문에 없던 효능을 새로 만들지
                않았습니다.
                {genResult.risk_confirmations.length > 0 && " (잔존 위험 항목 확인 후 사용을 권장합니다.)"}
              </p>
              <div className="btnrow">
                <button className={`btn ghost ${copied ? "copied" : ""}`} id="copyBtn" onClick={handleCopy}>
                  {copied ? "복사됨" : "텍스트 복사"}
                </button>
                <div className={`expdd ${dropdownOpen ? "open" : ""}`} id="expDd">
                  <button
                    className="btn primary"
                    id="expTrigger"
                    ref={dropdownTriggerRef}
                    aria-haspopup="true"
                    aria-expanded={dropdownOpen}
                    onClick={toggleDropdown}
                    disabled={exportingType !== null}
                  >
                    {exportingType ? "내보내는 중…" : "내보내기"}{" "}
                    <CaretDown className="chev" size={13} weight="bold" />
                  </button>
                  {dropdownOpen && (
                    <div className="ddmenu" id="expMenu">
                      <button id="expHtml" onClick={() => handleExport("html")} disabled={exportingType !== null}>
                        <FileCode size={14} weight="regular" />
                        HTML로 내보내기
                      </button>
                      <button id="expPng" onClick={() => handleExport("png")} disabled={exportingType !== null}>
                        <FileImage size={14} weight="regular" />
                        PNG로 내보내기
                      </button>
                      <button id="expPdf" onClick={() => handleExport("pdf")} disabled={exportingType !== null}>
                        <FilePdf size={14} weight="regular" />
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
            <button className="btn ghost" id="cmCancel" onClick={() => setIsModalOpen(false)}>
              취소
            </button>
            <button
              className="btn primary"
              id="cmConfirm"
              disabled={!checks.ck1 || !checks.ck2}
              onClick={handleConfirm}
            >
              확인하고 생성
            </button>
          </>
        }
      >
        <p className="modal-sub">[ 제거된 개인정보 · 2건 ]</p>
        <ul className="piilist">
          <li>
            <span className="cli-tag system">[system]</span>
            <span>이미지 배경 속 매장 명판 텍스트를 자동으로 지웠어요.</span>
          </li>
          <li>
            <span className="cli-tag system">[system]</span>
            <span>고객 후기 캡처에 있던 개인 아이디를 자동으로 지웠어요.</span>
          </li>
        </ul>
        <div className="modal-divider" />
        <p className="modal-sub">[ 생성 전 확인 필요 · 2건 ]</p>
        <ul className="checklist" id="checkList">
          <li
            className="checkrow"
            onClick={() => setChecks((prev) => ({ ...prev, ck1: !prev.ck1 }))}
          >
            <div className="checkrow-content">
              <span className="cli-tag warn">[warn]</span>
              <span>효능 표현이 조건표 허용 범위 안에서만 순화되었는지 확인했어요.</span>
            </div>
            <span className={`cli-checkbox ${checks.ck1 ? "checked" : ""}`}>
              ✓
            </span>
          </li>
          <li
            className="checkrow"
            onClick={() => setChecks((prev) => ({ ...prev, ck2: !prev.ck2 }))}
          >
            <div className="checkrow-content">
              <span className="cli-tag warn">[warn]</span>
              <span>생성된 문구에 원문에 없던 새로운 효능 주장이 없는지 확인했어요.</span>
            </div>
            <span className={`cli-checkbox ${checks.ck2 ? "checked" : ""}`}>
              ✓
            </span>
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
    <Suspense fallback={<div className="devnote" style={{ padding: "20px" }}>로딩 중…</div>}>
      <ContentPageWrapper />
    </Suspense>
  );
}
