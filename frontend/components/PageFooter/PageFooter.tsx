"use client";

/**
 * PageFooter: 모든 페이지 하단에 공통으로 노출되는 화장품법 규제 고지 컴포넌트.
 *
 * 적용 기준 표기는 하드코딩하지 않고 citation_registry 단일 소스에서 읽는다.
 * (2026-08-15, 식품 도메인 고시번호 "2025-79호"가 화장품 근거로 잘못 표기됐던 사고 이후 규칙)
 * - 일반 화면: GET /reference/basis 실시간 값
 * - 리포트 화면: 검사 시점 스냅샷(report.basis)을 basis prop으로 주입 (snapshot 모드)
 * - API 실패·미기동 시: 검증된 정적 문구로 폴백 (페이지는 항상 뜬다)
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { getReferenceBasis } from "@/lib/api/client";
import type { BasisCitation, RegulatoryBasis } from "@/lib/api/schema";

// 폴백은 citation_registry와 대조된 값만 쓴다 (kr_law_art13 · kr_rule_appendix5 · US)
const FALLBACK_BASIS_LINE = "화장품법 제13조 · 시행규칙 별표5 · 미국 FDA/FTC";

// 푸터엔 긴 정식 명칭 대신 괄호·대괄호 앞부분만 짧게 쓴다
function shortName(citation: BasisCitation): string {
  return citation.law_name.split(" (")[0].split(" [")[0];
}

function formatBasisLine(basisList: RegulatoryBasis[]): string {
  const names = basisList.flatMap((basis) => basis.citations.map(shortName));
  return names.length > 0 ? names.join(" · ") : FALLBACK_BASIS_LINE;
}

interface PageFooterProps {
  /** 검사 시점 기준 스냅샷 (리포트 화면 전용). 주면 실시간 조회를 하지 않는다 */
  basis?: RegulatoryBasis | null;
  /** true면 스냅샷 모드: basis가 없어도(구버전 리포트) 실시간 값으로 대체하지 않는다 */
  snapshot?: boolean;
}

export function PageFooter({ basis, snapshot = false }: PageFooterProps) {
  const [liveLine, setLiveLine] = useState<string | null>(null);

  useEffect(() => {
    if (snapshot || basis) return;
    let alive = true;
    getReferenceBasis()
      .then((res) => {
        if (alive) setLiveLine(formatBasisLine(Object.values(res)));
      })
      .catch(() => {
        // 백엔드 미기동 등: 폴백 문구 유지
      });
    return () => {
      alive = false;
    };
  }, [snapshot, basis]);

  const line = basis ? formatBasisLine([basis]) : liveLine ?? FALLBACK_BASIS_LINE;
  const label = snapshot ? "적용 기준(검사 시점)" : "적용 기준";

  return (
    // mt-auto: 본문이 짧아도 푸터가 셸 박스 바닥에 붙어 하단 흰 공백이 생기지 않게
    <div className="mt-auto p-[10px_20px] border-t border-[var(--line)] bg-[var(--surface-sub)] text-[11px] text-[var(--ink-3)] leading-[1.65]">
      바름은 사전 스크리너이며 최종 법적 판단이 아닙니다. &apos;통과&apos;가 100% 안전을 보장하지
      않으며, 최종 게시 판단과 책임은 사업자에게 있습니다.{" "}
      <b className="text-[var(--brand-ink)] font-semibold">
        {label}: {line}
      </b>
      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-[var(--ink-3)]">
        <span>&copy; 2026 바름</span>
        <span aria-hidden="true">·</span>
        <Link href="/" className="text-[var(--ink-3)] hover:text-[var(--ink)] underline underline-offset-2">
          회사 소개
        </Link>
        <span aria-hidden="true">·</span>
        <Link href="/privacy" className="text-[var(--ink-3)] hover:text-[var(--ink)] underline underline-offset-2">
          개인정보 처리방침
        </Link>
        <span aria-hidden="true">·</span>
        <Link href="/policy/ai" className="text-[var(--ink-3)] hover:text-[var(--ink)] underline underline-offset-2">
          AI 이용 안내
        </Link>
      </div>
    </div>
  );
}
