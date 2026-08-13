"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { PageFooter } from "@/components/PageFooter/PageFooter";

interface FeatItem {
  text: string;
  is_active: boolean;
}

interface TierInfo {
  name: "Free" | "Basic" | "Pro";
  price: string;
  used: number;
  limit: number | null;
  feats: FeatItem[];
  up: {
    title: string;
    desc: string;
  };
}

const TIERS: Record<"Free" | "Basic" | "Pro", TierInfo> = {
  Free: {
    name: "Free",
    price: "0원",
    used: 2,
    limit: 3,
    feats: [
      { text: "월 3건 검사", is_active: true },
      { text: "위반 탐지 · 근거 조항", is_active: true },
      { text: "수정 권고안", is_active: false },
      { text: "검사 이력 무제한", is_active: false },
    ],
    up: {
      title: "Basic으로 올리면 수정 권고안까지 볼 수 있어요.",
      desc: "위반을 낮춘 대체 표현 제안과 무제한 검사 이력이 열립니다.",
    },
  },
  Basic: {
    name: "Basic",
    price: "4.9만원",
    used: 12,
    limit: 20,
    feats: [
      { text: "월 20건 검사", is_active: true },
      { text: "위반 탐지 · 근거 조항", is_active: true },
      { text: "수정 권고안 제공", is_active: true },
      { text: "검사 이력 무제한", is_active: true },
    ],
    up: {
      title: "Pro로 올리면 검사가 무제한이 됩니다.",
      desc: "콘텐츠 생성 월 5회와 이력 통합 대시보드가 함께 열립니다.",
    },
  },
  Pro: {
    name: "Pro",
    price: "14.9만원",
    used: 47,
    limit: null,
    feats: [
      { text: "검사 무제한", is_active: true },
      { text: "수정 권고안 제공", is_active: true },
      { text: "콘텐츠 생성 월 5회", is_active: true },
      { text: "이력 통합 대시보드", is_active: true },
    ],
    up: {
      title: "현재 최상위 요금제(Pro)를 이용 중입니다.",
      desc: "리포트를 PDF로 내보내려면 Export 애드온을 추가할 수 있어요.",
    },
  },
};

export default function MyPage() {
  const [tier, set_tier] = useState<"Free" | "Basic" | "Pro">("Basic");
  const [is_compare_modal_open, set_is_compare_modal_open] = useState(false);

  const compare_btn_ref = useRef<HTMLButtonElement>(null);
  const modal_close_btn_ref = useRef<HTMLButtonElement>(null);
  const was_open = useRef(false);

  useEffect(() => {
    if (is_compare_modal_open) {
      modal_close_btn_ref.current?.focus();
      was_open.current = true;
    } else if (was_open.current) {
      compare_btn_ref.current?.focus();
      was_open.current = false;
    }
  }, [is_compare_modal_open]);

  // Esc 키 입력 시 모달 닫기
  useEffect(() => {
    const handle_keydown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        set_is_compare_modal_open(false);
      }
    };
    if (is_compare_modal_open) {
      window.addEventListener("keydown", handle_keydown);
    }
    return () => {
      window.removeEventListener("keydown", handle_keydown);
    };
  }, [is_compare_modal_open]);

  const active_tier = TIERS[tier];

  return (
    <>
      {/* 메타스트립: 브레드크럼 + 목업 전용 등급 스위처 */}
      <div className="metastrip">
        <span className="crumb">
          <Link href="/" className="home">
            홈
          </Link>{" "}
          <span className="sep">›</span> 마이페이지
        </span>
        <div className="tierswitch">
          <span className="tsl devnote">목업 전용 · 실제 화면엔 없음:</span>
          <div className="tsbtns" id="tierSwitch" role="group" aria-label="요금제 전환">
            {(["Free", "Basic", "Pro"] as const).map((t) => (
              <button
                key={t}
                className={`mono ${tier === t ? "on" : ""}`}
                onClick={() => set_tier(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 요금제 + 사용량 */}
      <div className="sec">
        <div className="seclabel">
          <span className="n">01</span>
          <h2>요금제 · 사용량</h2>
          <span className="rule"></span>
          <span className="hint">glowskin 계정</span>
        </div>
        <div className="planrow">
          <div className="card">
            <p className="ctitle">현재 요금제</p>
            <div className="planname">
              <span className="pn">{active_tier.name}</span>
              <span className="pp">
                {active_tier.price} <span className="per">/ 월</span>
              </span>
            </div>
            <ul className="planfeat">
              {active_tier.feats.map((feat, index) => (
                <li key={index} className={feat.is_active ? "" : "off"}>
                  {feat.is_active ? (
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M4 12l5 5L20 6" />
                    </svg>
                  ) : (
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M5 12h14" />
                    </svg>
                  )}
                  <span>{feat.text}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card">
            <p className="ctitle">이번 달 사용량</p>
            {active_tier.limit === null ? (
              <div>
                <div className="usagehead">
                  <span className="ul">이번 달 검사</span>
                  <span className="uv">
                    <b>{active_tier.used}</b>건
                  </span>
                </div>
                <span className="unlimited">
                  <svg
                    viewBox="0 0 24 24"
                    width="14"
                    height="14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    aria-hidden="true"
                  >
                    <path d="M7 12c0-2 1.5-3.5 3.5-3.5S14 12 14 12s1.5 3.5 3.5 3.5S21 14 21 12s-1.5-3.5-3.5-3.5S14 12 14 12s-1.5 3.5-3.5 3.5S3 14 3 12s1.5-3.5 4-3.5" />
                  </svg>
                  무제한 검사
                </span>
                <div className="usagemeta">한도 없음 · 이번 달 {active_tier.used}건 사용</div>
              </div>
            ) : (
              <div>
                <div className="usagehead">
                  <span className="ul">검사 사용량</span>
                  <span className="uv">
                    <b>{active_tier.used}</b> / {active_tier.limit}건
                  </span>
                </div>
                <div 
                  className="usagebar" 
                  aria-label={`검사 사용량 ${Math.round((active_tier.used / active_tier.limit) * 100)}% 사용함`}
                >
                  <div 
                    className="fill" 
                    style={{ width: `${Math.round((active_tier.used / active_tier.limit) * 100)}%` }}
                  ></div>
                </div>
                <div className="usagemeta">{active_tier.limit - active_tier.used}건 남음 · 매월 1일 초기화</div>
              </div>
            )}
          </div>
        </div>
        <div className="upbanner" id="upBanner">
          <div className="ubtx">
            <b>{active_tier.up.title}</b>
            <p>{active_tier.up.desc}</p>
          </div>
          <button 
            id="openCompare"
            ref={compare_btn_ref}
            className="btn primary" 
            onClick={() => set_is_compare_modal_open(true)}
          >
            요금제 비교 <span className="mono">→</span>
          </button>
        </div>
      </div>

      {/* Pro 전용: 이력 통합 대시보드 */}
      {tier === "Pro" && (
        <div className="sec dash">
          <div className="seclabel">
            <span className="n">02</span>
            <h2>이력 통합 대시보드</h2>
            <span className="rule"></span>
            <span className="hint">Pro · 이번 분기</span>
          </div>
          <div className="stattiles">
            <div className="stattile">
              <p className="stlabel">이번 분기 위반</p>
              <div className="stval crit">42</div>
              <div className="stdelta">지난 분기 대비 8건 감소</div>
              <svg className="spark" viewBox="0 0 240 34" preserveAspectRatio="none" aria-hidden="true">
                {[5, 7, 4, 6, 8, 5, 3, 4].map((val, i) => {
                  const max_val = 8;
                  const height_factor = 24 / max_val;
                  const h = val * height_factor;
                  const y = 34 - h;
                  const x = 1 + i * 30;
                  const fill = i === 7 ? "var(--crit)" : "var(--ink-3)";
                  return (
                    <rect
                      key={i}
                      x={x}
                      y={y}
                      width={28}
                      height={h + 4}
                      rx={4}
                      fill={fill}
                    >
                      <title>{8 - i}주 전 기준 {val}건</title>
                    </rect>
                  );
                })}
              </svg>
            </div>
            <div className="stattile">
              <p className="stlabel">이번 분기 검토필요</p>
              <div className="stval">21</div>
              <div className="stdelta">지난 분기 대비 3건 증가</div>
              <svg className="spark" viewBox="0 0 240 34" preserveAspectRatio="none" aria-hidden="true">
                {[2, 3, 2, 4, 3, 2, 3, 2].map((val, i) => {
                  const max_val = 4;
                  const height_factor = 24 / max_val;
                  const h = val * height_factor;
                  const y = 34 - h;
                  const x = 1 + i * 30;
                  const fill = i === 7 ? "var(--ink-2)" : "var(--ink-3)";
                  return (
                    <rect
                      key={i}
                      x={x}
                      y={y}
                      width={28}
                      height={h + 4}
                      rx={4}
                      fill={fill}
                    >
                      <title>{8 - i}주 전 기준 {val}건</title>
                    </rect>
                  );
                })}
              </svg>
            </div>
          </div>
          <p className="dashnote">최근 8주 주별 추이 · 막대에 올리면 값 표시 · 검사 128건 기준</p>
        </div>
      )}

      {/* 검사 이력 */}
      <div className="sec" style={{ borderBottom: 0 }}>
        <div className="seclabel">
          <span className="n" id="histNo">{tier === "Pro" ? "03" : "02"}</span>
          <h2>검사 이력</h2>
          <span className="rule"></span>
          <span className="hint" id="histHint">최근 5건</span>
        </div>
        <div className="histlist">
          <Link href="/report/demo-id-1" className="hrow">
            <span className="hname">글로우 세럼 · 미국 상세페이지</span>
            <span className="htag">해외 · 미국</span>
            <span className="hstat need">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
              >
                <path d="M12 3 2 20h20L12 3z" />
                <path d="M12 10v4M12 17v.5" />
              </svg>
              검토 필요
            </span>
            <span className="haction">리포트 다시 보기</span>
            <span className="hupd">방금</span>
          </Link>

          <Link href="/report/demo-id-2" className="hrow">
            <span className="hname">수분 크림 리뉴얼 상세페이지</span>
            <span className="htag">국내</span>
            <span className="hstat done">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
              >
                <path d="M4 12l5 5L20 6" />
              </svg>
              검사 완료
            </span>
            <span className="haction">리포트 다시 보기</span>
            <span className="hupd">2일 전</span>
          </Link>

          <Link href="/report/demo-id-3" className="hrow">
            <span className="hname">선크림 SPF50 신제품</span>
            <span className="htag">국내</span>
            <span className="hstat need">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
              >
                <path d="M12 3 2 20h20L12 3z" />
                <path d="M12 10v4M12 17v.5" />
              </svg>
              위반 3건
            </span>
            <span className="haction">리포트 다시 보기</span>
            <span className="hupd">3일 전</span>
          </Link>

          <Link href="/report/demo-id-4" className="hrow">
            <span className="hname">아이크림 재론칭 상세페이지</span>
            <span className="htag">국내</span>
            <span className="hstat done">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
              >
                <path d="M4 12l5 5L20 6" />
              </svg>
              검사 완료
            </span>
            <span className="haction">리포트 다시 보기</span>
            <span className="hupd">1주 전</span>
          </Link>

          <Link href="/report/demo-id-5" className="hrow">
            <span className="hname">클렌징폼 성분 개편</span>
            <span className="htag">해외 · 미국</span>
            <span className="hstat need">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="square"
                aria-hidden="true"
              >
                <path d="M12 3 2 20h20L12 3z" />
                <path d="M12 10v4M12 17v.5" />
              </svg>
              검토 필요
            </span>
            <span className="haction">리포트 다시 보기</span>
            <span className="hupd">2주 전</span>
          </Link>
        </div>
      </div>

      <PageFooter />

      {/* 요금제 비교 모달 */}
      {is_compare_modal_open && (
        <div 
          className="modal-backdrop" 
          onClick={() => set_is_compare_modal_open(false)}
        >
          <div 
            className="modal" 
            role="dialog" 
            aria-modal="true" 
            aria-labelledby="cmTitle"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <span id="cmTitle">[ 요금제 비교 ]</span>
              <button 
                id="cmClose"
                ref={modal_close_btn_ref}
                className="modal-x" 
                onClick={() => set_is_compare_modal_open(false)}
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className={`prow ${tier === "Free" ? "on" : ""}`}>
                <span className="pk">›</span>
                <span className="pnm">
                  Free
                  {tier === "Free" && <span className="cur"> (현재 이용 중)</span>}
                </span>
                <span className="ppr">0원 / 월</span>
                <span className="pdesc">월 3건 검사 · 위반 탐지와 근거까지 체험</span>
              </div>
              <div className={`prow ${tier === "Basic" ? "on" : ""}`}>
                <span className="pk">›</span>
                <span className="pnm">
                  Basic
                  {tier === "Basic" && <span className="cur"> (현재 이용 중)</span>}
                </span>
                <span className="ppr">4.9만원 / 월</span>
                <span className="pdesc">월 20건 · 수정 권고안 제공 · 검사 이력 무제한</span>
              </div>
              <div className={`prow ${tier === "Pro" ? "on" : ""}`}>
                <span className="pk">›</span>
                <span className="pnm">
                  Pro
                  {tier === "Pro" && <span className="cur"> (현재 이용 중)</span>}
                </span>
                <span className="ppr">14.9만원 / 월</span>
                <span className="pdesc">검사 무제한 · 콘텐츠 생성 월 5회 · 이력 통합 대시보드</span>
              </div>
              <div className="addon">
                <b>Export 애드온</b> <span className="ap">건당 4.9만원</span> · 리포트를 PDF로 내보내기 (모든 요금제에 추가 가능)
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
