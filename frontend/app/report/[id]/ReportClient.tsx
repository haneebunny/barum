"use client";

import Link from "next/link";
import { useState } from "react";
import type { ReportEnvelope } from "@/lib/api/schema";
import { getReport } from "@/lib/api/client";

const TYPE_LABEL = {
  "1호_의약품오인": "1호 · 의약품 오인",
  "2호_기능성오인": "2호 · 기능성 오인",
  "5호_거짓과장기만": "5호 · 거짓·과장·기만",
};

interface ReportClientProps {
  envelope: ReportEnvelope;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] || c));
}

function markSentence(sentence: string, hlItems: Array<{ span: string; cls: string; badge: number }>) {
  let out = escapeHtml(sentence);
  const items = [...hlItems].sort((a, b) => b.span.length - a.span.length);
  items.forEach((it) => {
    const needle = escapeHtml(it.span);
    if (out.indexOf(needle) === -1) return;
    out = out.replace(
      needle,
      `<span class="hlspan ${it.cls}"><span class="tag">${it.badge}</span>${needle}</span>`
    );
  });
  return out;
}

export function ReportClient({ envelope }: ReportClientProps) {
  const [activeEnvelope, setActiveEnvelope] = useState<ReportEnvelope>(envelope);
  const [activeFixture, setActiveFixture] = useState<"image" | "text" | "unjudged" | string>(() => {
    if (envelope.result_id === "demo-text-id" || envelope.result_id === "text") return "text";
    if (envelope.result_id === "demo-unjudged-id" || envelope.result_id === "unjudged" || envelope.result_id === "a3Fk9mdemo") return "unjudged";
    return "image";
  });
  const [loading, setLoading] = useState(false);
  const [actions, setActions] = useState<Record<number, "accept" | "exclude" | "hold" | null>>({});

  const handleFixtureChange = async (key: "image" | "text" | "unjudged") => {
    setLoading(true);
    try {
      const data = await getReport(key);
      setActiveEnvelope(data);
      setActiveFixture(key);
      setActions({});
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const d = activeEnvelope.report;

  // 10단계에서 제외(exclude) 처리 시 수치 실시간 계산을 위한 바인딩 연동
  let nViol = 0;
  let nReview = 0;

  d.findings.forEach((f, i) => {
    if (actions[i] === "exclude") return;
    if (f.flag === "위반") {
      nViol++;
    } else {
      nReview++;
    }
  });

  const typeCounts: Record<string, number> = {};
  d.findings.forEach((f, i) => {
    if (actions[i] === "exclude") return;
    typeCounts[f.violation_type] = (typeCounts[f.violation_type] || 0) + 1;
  });

  const isImageMode = d.findings.some((f) => f.location.tile) || d.unjudged.some((u) => u.location.tile);

  // findings의 order 기준으로 순서(num: 1, 2, 3...) 매기기
  const findByOrder = d.findings
    .map((f, i) => ({ f, idx: i, num: 0 }))
    .sort((a, b) => a.f.location.order - b.f.location.order);
  findByOrder.forEach((item, index) => {
    item.num = index + 1;
  });

  // unjudged의 order 기준으로 정렬
  const ujByOrder = [...d.unjudged].sort((a, b) => a.location.order - b.location.order);

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: styles }} />
      <div className="metastrip">
        <span className="crumb">
          <Link href="/" className="home">
            홈
          </Link>{" "}
          <span className="sep">›</span> 국내 광고 검증 <span className="sep">›</span> 리포트
        </span>
        <div className="modeswitch">
          <span className="msl devnote">목업 전용 · 실제 화면엔 없음:</span>
          <div className="msbtns" id="fixtureSwitch" role="group" aria-label="fixture 전환">
            <button
              onClick={() => handleFixtureChange("image")}
              className={activeFixture === "image" ? "on" : ""}
              disabled={loading}
            >
              이미지 예시
            </button>
            <button
              onClick={() => handleFixtureChange("text")}
              className={activeFixture === "text" ? "on" : ""}
              disabled={loading}
            >
              텍스트 예시
            </button>
            <button
              onClick={() => handleFixtureChange("unjudged")}
              className={activeFixture === "unjudged" ? "on" : ""}
              disabled={loading}
            >
              미판정 포함
            </button>
          </div>
        </div>
      </div>

      {/* 요약 상단바 */}
      <div className="statbar">
        <p className="headline">
          <span className="nviol">위반 {nViol}건</span>
          <span className="sep2">·</span>
          검토필요 {nReview}건
          <span className="sep2">·</span>
          미판정 {d.unjudged.length}건
        </p>
        <div className="typechips">
          {Object.entries(typeCounts).map(([type, count]) => {
            if (count === 0) return null;
            const label = TYPE_LABEL[type as keyof typeof TYPE_LABEL] || type;
            return (
              <span key={type} className="typechip">
                {label} <span className="cnt">{count}</span>
              </span>
            );
          })}
          {Object.keys(typeCounts).length === 0 && (
            <span className="typechip devnote">제외 처리 후 남은 지적 없음</span>
          )}
        </div>
      </div>

      {/* 2단 리포트 그리드 (뼈대 유지) */}
      <div className="reportgrid">
        <div className="repcol left">
          <div className="seclabel">
            <span className="n">01</span>
            <h2>원문 하이라이트</h2>
            <span className="rule" />
            <span className="hint">
              {isImageMode ? "이미지 모드 · 타일 오버레이" : "텍스트 모드 · 스팬 밑줄"}
            </span>
          </div>
          <div id="origPanel">
            {loading ? (
              <p className="devnote" style={{ padding: "12px" }}>
                로딩 중...
              </p>
            ) : isImageMode ? (
              (() => {
                const byTile: Record<
                  string,
                  Array<
                    | { type: "find"; num: number; item: typeof d.findings[number] }
                    | { type: "uj"; letter: string; item: typeof d.unjudged[number] }
                  >
                > = {};

                findByOrder.forEach((o) => {
                  const t = o.f.location.tile;
                  if (t) {
                    if (!byTile[t]) byTile[t] = [];
                    byTile[t].push({ type: "find", num: o.num, item: o.f });
                  }
                });

                ujByOrder.forEach((u, i) => {
                  const t = u.location.tile;
                  if (t) {
                    if (!byTile[t]) byTile[t] = [];
                    byTile[t].push({ type: "uj", letter: String.fromCharCode(65 + i), item: u });
                  }
                });

                const tiles = Object.keys(byTile).sort();

                return (
                  <>
                    {tiles.map((t) => {
                      const rows = byTile[t].sort(
                        (a, b) => a.item.location.order - b.item.location.order
                      );
                      return (
                        <div className="tileblock" key={t}>
                          <div className="tilehead">{t}</div>
                          <div className="tilebg">
                            {rows.map((r, ri) => {
                              if (r.type === "find") {
                                const cls = r.item.flag === "위반" ? "violation" : "review";
                                return (
                                  <div className={`hlband ${cls}`} key={ri}>
                                    <span className="hlbadge">{r.num}</span>
                                    <span className="hltxt">{r.item.span}</span>
                                  </div>
                                );
                              } else {
                                return (
                                  <div className="hlband unjudged" key={ri}>
                                    <span className="hlbadge">{r.letter}</span>
                                    <span className="hltxt">{r.item.sentence}</span>
                                  </div>
                                );
                              }
                            })}
                          </div>
                        </div>
                      );
                    })}
                    <p className="devnote" style={{ marginTop: "8px" }}>
                      실제 좌표(bbox)는 없어 타일 내 순서대로만 배치(문서 참조)
                    </p>
                  </>
                );
              })()
            ) : (
              (() => {
                // 텍스트 모드: findings 및 unjudged 문장들을 통합하여 order 순으로 렌더링
                // 1. findings 문장 분류
                const seenFindings: Record<string, Array<{ span: string; cls: string; badge: number }>> = {};
                const sentenceOrders: Record<string, number> = {};

                findByOrder.forEach((o) => {
                  const sentence = o.f.sentence;
                  if (!seenFindings[sentence]) {
                    seenFindings[sentence] = [];
                    sentenceOrders[sentence] = o.f.location.order;
                  }
                  seenFindings[sentence].push({
                    span: o.f.span,
                    cls: o.f.flag === "위반" ? "violation" : "review",
                    badge: o.num,
                  });
                });

                // 2. unjudged 문장 분류
                const unjudgedSentences: Array<{ sentence: string; letter: string; order: number }> = [];
                ujByOrder.forEach((u, i) => {
                  unjudgedSentences.push({
                    sentence: u.sentence,
                    letter: String.fromCharCode(65 + i),
                    order: u.location.order,
                  });
                });

                // 3. 모든 문장 목록 구성 및 order 순 정렬
                interface TextSentenceNode {
                  type: "find" | "uj";
                  sentence: string;
                  order: number;
                  // find type extra
                  hlItems?: Array<{ span: string; cls: string; badge: number }>;
                  // uj type extra
                  letter?: string;
                }

                const allSentences: TextSentenceNode[] = [];

                Object.keys(seenFindings).forEach((s) => {
                  allSentences.push({
                    type: "find",
                    sentence: s,
                    order: sentenceOrders[s],
                    hlItems: seenFindings[s],
                  });
                });

                unjudgedSentences.forEach((u) => {
                  allSentences.push({
                    type: "uj",
                    sentence: u.sentence,
                    order: u.order,
                    letter: u.letter,
                  });
                });

                allSentences.sort((a, b) => a.order - b.order);

                // 4. HTML 생성
                const htmlContent = allSentences
                  .map((node) => {
                    if (node.type === "find" && node.hlItems) {
                      return markSentence(node.sentence, node.hlItems);
                    } else if (node.type === "uj" && node.letter) {
                      return `<span class="hlspan unjudged"><span class="tag">${node.letter}</span>${escapeHtml(
                        node.sentence
                      )}</span>`;
                    }
                    return "";
                  })
                  .join(" ");

                return (
                  <div
                    className="textpanel"
                    dangerouslySetInnerHTML={{ __html: htmlContent }}
                  />
                );
              })()
            )}
          </div>
        </div>
        <div className="repcol right">
          <div className="seclabel">
            <span className="n">02</span>
            <h2>지적 카드</h2>
            <span className="rule" />
            <span className="hint">{d.findings.length}건</span>
          </div>
          <div className="findlist">
            <p
              className="devnote"
              style={{
                padding: "12px",
                border: "1px dashed var(--line-2)",
                background: "var(--surface-sub)",
              }}
            >
              지적 카드 목록 (Micro-step 10에서 구현 예정)
            </p>
          </div>
          {d.unjudged.length > 0 && (
            <div className="ujwrap">
              <div className="seclabel">
                <span className="n">?</span>
                <h2>재검사 필요</h2>
                <span className="rule" />
                <span className="hint">판정 실패 · 미판정</span>
              </div>
              <div className="ujlist">
                <p
                  className="devnote"
                  style={{
                    padding: "12px",
                    border: "1px dashed var(--line-2)",
                    background: "var(--surface-sub)",
                  }}
                >
                  재검사 필요 목록 (Micro-step 10에서 구현 예정)
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 하단 브릿지 */}
      <div className="bridge">
        <p>지적된 표현을 검토했다면, 위험을 낮춘 수정 권고안을 반영해 상세페이지 초안을 만들 수 있어요.</p>
        <Link href="/" className="btn primary">
          이 수정안대로 상세페이지 만들기 <span className="mono">→</span>
        </Link>
      </div>

      <div className="compliance">
        바름은 사전 스크리너이며 최종 법적 판단이 아닙니다. 위험 후보를 넓게 잡아(미탐 최소화) &apos;통과&apos;가
        100% 안전을 보장하진 않습니다. 최종 게시 판단과 책임은 사업자에게 있습니다.{" "}
        <b>적용 기준: 화장품법 · 고시 2025-79호</b>
      </div>
      <div className="statusbar">
        <span className="seg inv">바름</span>
        <span className="seg">glowskin</span>
        <span className="seg grow">국내 광고 검증 · 리포트</span>
        <span className="seg">^R 다시 검사</span>
      </div>
    </>
  );
}

const styles = `
  .metastrip {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 20px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-sub);
    font-family: var(--mono);
    font-size: 11px;
    color: var(--ink-3);
    flex-wrap: wrap;
  }
  .metastrip .crumb {
    color: var(--ink-2);
  }
  .metastrip .crumb .home {
    color: var(--ink-3);
    cursor: pointer;
    text-decoration: none;
  }
  .metastrip .crumb .home:hover {
    color: var(--ink);
  }
  .metastrip .sep {
    color: var(--ink-3);
  }

  .statbar {
    padding: 18px 20px;
    border-bottom: 1px solid var(--line);
  }
  .statbar .headline {
    margin: 0 0 12px;
    font-size: 16px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.2px;
  }
  .statbar .headline .nviol {
    color: var(--crit);
  }
  .statbar .headline .sep2 {
    color: var(--ink-3);
    font-weight: 400;
    margin: 0 3px;
  }
  .typechips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .typechip {
    font-family: var(--mono);
    font-size: 11px;
    border: 1px solid var(--line-2);
    background: var(--surface-sub);
    color: var(--ink-2);
    padding: 3px 9px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .typechip .cnt {
    color: var(--ink-3);
  }

  .reportgrid {
    display: grid;
    grid-template-columns: 0.86fr 1.14fr;
  }
  .repcol {
    padding: 18px 20px 22px;
  }
  .repcol.left {
    border-right: 1px solid var(--line);
  }
  .seclabel {
    display: flex;
    align-items: center;
    gap: 11px;
    margin: 0 0 13px;
  }
  .seclabel .n {
    color: var(--on-brand);
    background: var(--brand-deep);
    font-family: var(--mono);
    font-weight: 700;
    font-size: 11px;
    padding: 2px 7px;
  }
  .seclabel h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.2px;
  }
  .seclabel .rule {
    flex: 1;
    height: 0;
    border-top: 1px dashed var(--line-2);
  }
  .seclabel .hint {
    color: var(--ink-3);
    font-family: var(--mono);
    font-size: 10.5px;
  }

  .tileblock {
    border: 1px solid var(--line-2);
    margin-bottom: 14px;
  }
  .tileblock:last-child {
    margin-bottom: 0;
  }
  .tilehead {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--ink-3);
    padding: 6px 10px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-sub);
  }
  .tilebg {
    position: relative;
    aspect-ratio: 4 / 5;
    background: repeating-linear-gradient(135deg, var(--surface-sub) 0 10px, var(--surface) 10px 20px);
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .hlband {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 9px;
    background: var(--surface);
    border: 1px solid var(--line-2);
    font-size: 12px;
    color: var(--ink-2);
  }
  .hlband.violation {
    border-color: var(--crit-bd);
    background: var(--crit-bg);
  }
  .hlband.review {
    border-style: solid;
  }
  .hlband.unjudged {
    border-style: dashed;
  }
  .hlbadge {
    flex: 0 0 auto;
    width: 19px;
    height: 19px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: var(--mono);
    font-size: 10.5px;
    font-weight: 700;
    border-radius: 50%;
    border: 1.5px solid currentColor;
  }
  .hlband.violation .hlbadge {
    color: var(--crit);
    border-color: var(--crit);
  }
  .hlband.review .hlbadge {
    color: var(--ink-3);
    border-color: var(--ink-3);
  }
  .hlband.unjudged .hlbadge {
    color: var(--ink-3);
    border-color: var(--ink-3);
    border-style: dashed;
  }
  .hlband .hltxt {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .hlband.violation .hltxt {
    color: var(--crit);
  }

  .textpanel {
    border: 1px solid var(--line-2);
    background: var(--surface-sub);
    padding: 16px 15px;
    font-size: 14px;
    color: var(--ink);
    line-height: 2;
  }
  .hlspan {
    position: relative;
    padding: 0 1px;
    cursor: default;
  }
  .hlspan.violation {
    border-bottom: 2px solid var(--crit);
    color: var(--crit);
    font-weight: 600;
  }
  .hlspan.review {
    border-bottom: 2px solid var(--ink-3);
  }
  .hlspan.unjudged {
    border-bottom: 2px dashed var(--ink-3);
  }
  .hlspan .tag {
    position: absolute;
    top: -9px;
    left: -2px;
    font-family: var(--mono);
    font-size: 9px;
    font-weight: 700;
    color: inherit;
  }

  .findlist {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .fcard {
    border: 1px solid var(--line-2);
    background: var(--surface);
  }
  .fcard.violation {
    border-left: 3px solid var(--crit);
  }
  .fcard.review {
    border-left: 3px solid var(--ink-3);
  }
  .fhead {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 9px 12px;
    border-bottom: 1px solid var(--line);
    background: var(--surface-sub);
  }
  .fhead .fbadge {
    flex: 0 0 auto;
    width: 20px;
    height: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 700;
    border-radius: 50%;
    border: 1.5px solid currentColor;
  }
  .fcard.violation .fbadge {
    color: var(--crit);
    border-color: var(--crit);
  }
  .fcard.review .fbadge {
    color: var(--ink-3);
    border-color: var(--ink-3);
  }
  .fhead .ftype {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--ink-2);
    font-weight: 600;
  }
  .fhead .fflag {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11.5px;
    font-weight: 700;
  }
  .fhead .fflag svg {
    width: 14px;
    height: 14px;
  }
  .fcard.violation .fflag {
    color: var(--crit);
  }
  .fcard.review .fflag {
    color: var(--ink-3);
  }
  .fbody {
    padding: 13px 14px 14px;
  }
  .fsent {
    margin: 0 0 8px;
    font-size: 14px;
    color: var(--ink);
    line-height: 1.65;
  }
  .fsent .fspan {
    font-weight: 700;
  }
  .fcard.violation .fsent .fspan {
    color: var(--crit);
    border-bottom: 2px solid var(--crit);
  }
  .fcard.review .fsent .fspan {
    color: var(--ink);
    border-bottom: 2px solid var(--ink-3);
  }
  .fbasis {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--brand-ink);
    margin: 0 0 8px;
  }
  .fexpl {
    font-size: 12.5px;
    color: var(--ink-3);
    line-height: 1.6;
    margin: 0 0 12px;
  }
  .falt {
    border: 1px dashed var(--line-2);
    background: var(--surface-sub);
    padding: 10px 11px;
    margin: 0 0 12px;
  }
  .falt .faltlabel {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 6px;
  }
  .falt .faltlabel b {
    font-size: 11.5px;
    color: var(--ink-2);
    font-weight: 700;
  }
  .falt .faltlabel .faltflag {
    font-family: var(--mono);
    font-size: 9.5px;
    color: var(--ink-3);
    border: 1px solid var(--line-2);
    padding: 1px 6px;
  }
  .falt .falttext {
    font-size: 13px;
    color: var(--ink-2);
    line-height: 1.6;
  }
  .factions {
    display: flex;
    gap: 6px;
  }
  .fabtn {
    font-family: var(--sans);
    font-size: 11.5px;
    font-weight: 600;
    padding: 6px 11px;
    border: 1px solid var(--line-2);
    background: transparent;
    color: var(--ink-3);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  .fabtn svg {
    width: 13px;
    height: 13px;
  }
  .fabtn:hover {
    color: var(--ink);
    background: var(--nav-hover);
  }
  .fabtn.on {
    color: var(--ink);
    font-weight: 700;
  }
  .fabtn.accept.on {
    border-color: var(--ink-2);
    background: var(--nav-active-bg);
  }
  .fabtn.exclude.on {
    border-color: var(--ink-3);
    background: var(--surface-sub);
  }
  .fabtn.hold.on {
    border-color: var(--ink-3);
    background: var(--surface-sub);
  }
  .fcard.st-exclude {
    opacity: 0.5;
  }
  .fcard.st-exclude .fsent {
    text-decoration: line-through;
    text-decoration-color: var(--ink-3);
  }
  .fcard.st-hold {
    position: relative;
  }
  .fcard.st-hold::after {
    content: "보류 중";
    position: absolute;
    top: 9px;
    right: 12px;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--ink-3);
  }

  .ujwrap {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px dashed var(--line-2);
  }
  .ujwrap .seclabel .n {
    background: var(--surface-sub);
    color: var(--ink-3);
    border: 1px solid var(--line-2);
  }
  .ujlist {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .ujrow {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    border: 1px dashed var(--line-2);
    background: var(--surface-sub);
    padding: 8px 10px;
  }
  .ujrow .ujbadge {
    flex: 0 0 auto;
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 700;
    color: var(--ink-3);
    border: 1.5px dashed var(--ink-3);
    border-radius: 50%;
  }
  .ujrow .ujsent {
    flex: 1;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  .ujrow .ujloc {
    flex: 0 0 auto;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--ink-3);
  }

  .bridge {
    padding: 18px 20px;
    border-top: 1px solid var(--line);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
  }
  .bridge p {
    margin: 0;
    font-size: 12px;
    color: var(--ink-3);
    max-width: 56ch;
  }
  .btn {
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 700;
    padding: 11px 16px;
    border: 1px solid transparent;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    transition: background 0.12s, color 0.12s;
    text-decoration: none;
  }
  .btn.primary {
    background: var(--brand);
    color: #fff;
    border-color: var(--brand);
  }
  :root[data-theme="dark"] .btn.primary {
    color: var(--on-brand);
  }
  .btn.primary:hover {
    background: var(--brand-ink);
  }
  :root[data-theme="dark"] .btn.primary:hover {
    background: #63e89f;
  }

  .compliance {
    padding: 10px 20px;
    border-top: 1px solid var(--line);
    background: var(--surface-sub);
    font-size: 11px;
    color: var(--ink-3);
    line-height: 1.65;
  }
  .compliance b {
    color: var(--brand-ink);
    font-weight: 600;
  }
  .statusbar {
    display: flex;
    border-top: 1px solid var(--line-2);
    font-family: var(--mono);
    font-size: 11px;
    background: var(--surface-sub);
  }
  .statusbar .seg {
    padding: 7px 13px;
    border-right: 1px solid var(--line);
    color: var(--ink-3);
  }
  .statusbar .seg.inv {
    background: var(--brand-deep);
    color: var(--on-brand);
    font-weight: 700;
  }
  .statusbar .seg.grow {
    flex: 1;
    border-right: none;
    color: var(--ink-3);
  }

  @media (max-width: 900px) {
    .reportgrid {
      grid-template-columns: 1fr;
    }
    .repcol.left {
      border-right: 0;
      border-bottom: 1px solid var(--line);
    }
    .statusbar .seg.grow {
      display: none;
    }
  }
`;
