"use client";

import Link from "next/link";

export default function MyPage() {
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
          <div className="tsbtns" role="group" aria-label="요금제 전환">
            <button className="mono">Free</button>
            <button className="mono on">Basic</button>
            <button className="mono">Pro</button>
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
              <span className="pn">Basic</span>
              <span className="pp">
                4.9만원 <span className="per">/ 월</span>
              </span>
            </div>
            <ul className="planfeat">
              <li>
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
                <span>월 20건 검사</span>
              </li>
              <li>
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
                <span>위반 탐지 · 근거 조항</span>
              </li>
              <li>
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
                <span>수정 권고안 제공</span>
              </li>
              <li>
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
                <span>검사 이력 무제한</span>
              </li>
            </ul>
          </div>
          <div className="card">
            <p className="ctitle">이번 달 사용량</p>
            <div>
              <div className="usagehead">
                <span className="ul">검사 사용량</span>
                <span className="uv">
                  <b>12</b> / 20건
                </span>
              </div>
              {/* 진행바: 비긴급 피드백이므로 디자인 가이드라인에 따라 무채색 회색 계열(var(--ink-3))로 렌더링 */}
              <div className="usagebar" aria-label="검사 사용량 60% 사용함">
                <div className="fill" style={{ width: "60%" }}></div>
              </div>
              <div className="usagemeta">8건 남음 · 매월 1일 초기화</div>
            </div>
          </div>
        </div>
        <div className="upbanner">
          <div className="ubtx">
            <b>Pro로 올리면 검사가 무제한이 됩니다.</b>
            <p>콘텐츠 생성 월 5회와 이력 통합 대시보드가 함께 열립니다.</p>
          </div>
          <button className="btn primary">
            요금제 비교 <span className="mono">→</span>
          </button>
        </div>
      </div>

      {/* 검사 이력 */}
      <div className="sec" style={{ borderBottom: 0 }}>
        <div className="seclabel">
          <span className="n">02</span>
          <h2>검사 이력</h2>
          <span className="rule"></span>
          <span className="hint">최근 5건</span>
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

      <div className="compliance">
        바름은 사전 스크리너이며 최종 법적 판단이 아닙니다. 최종 게시 판단과 책임은 사업자에게 있습니다.{" "}
        <b>적용 기준: 화장품법 · 고시 2025-79호</b>
      </div>

      <div className="statusbar">
        <span className="seg inv">바름</span>
        <span className="seg">glowskin</span>
        <span className="seg grow">
          마이페이지 · <span id="tierSeg">Basic</span>
        </span>
        <span className="seg">^N 새 검사</span>
      </div>
    </>
  );
}
