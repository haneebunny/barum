"use client";

import { useEffect, useState } from "react";

export type GenerationMode = "create" | "improve";

interface GenerationLoadingProps {
  mode: GenerationMode;
  // 이미지 생성 체크박스(create 모드 전용). 꺼져 있으면 "이미지 생성 중" 단계
  // 자체를 안 보여준다 - 실제로 안 도는 단계를 도는 것처럼 보이면 거짓말이 된다
  // (팀장 지시, 2026-08-23).
  imagesRequested?: boolean;
}

/**
 * 실제 파이프라인 순서(backend/src/barum/generate/content.py
 * _generate_create_content / _generate_improve_content 주석 그대로 옮김,
 * 2026-08-23 기준). 지어낸 단계명 아님 - 백엔드 코드가 바뀌면 이 목록도 같이 봐야 한다.
 */
const STEPS_IMPROVE = [
  "원본 문구 검사 중",
  "대체 표현 생성 중",
  "섹션 문구 생성 중",
  "생성물 재검증 중",
];

const STEPS_CREATE_BASE = ["레이아웃 플랜 생성 중", "섹션별 문구 생성 중"];
const STEP_CREATE_IMAGE = "이미지 생성 중";
const STEPS_CREATE_TAIL = ["카드 조립 중", "생성물 재검증 중"];

function buildSteps(mode: GenerationMode, imagesRequested: boolean): string[] {
  if (mode === "improve") return STEPS_IMPROVE;
  return imagesRequested
    ? [...STEPS_CREATE_BASE, STEP_CREATE_IMAGE, ...STEPS_CREATE_TAIL]
    : [...STEPS_CREATE_BASE, ...STEPS_CREATE_TAIL];
}

// 실제 진행률이 아니다 - 기다릴 수 있게 하는 눈속임 진행바다(팀장 지시).
// 92% 점근선 도달 시점이 실제 평균 완료 시점 근처에 오도록 실측 기반으로 잡았다
// (generate_cost_probe.py 실측, 2026-08-23: 이미지 끔 66~96초·켬 107~125초, 각 범위
// 중앙값을 기준으로 역산 - 57행 공식상 92% 도달 시점은 total의 약 1.515배).
// create 모드만 실측함. improve 모드는 이미지를 안 쓰므로 항상 이미지 끔 값을 쓰는데,
// 그 값 자체가 improve 모드로 실측된 적은 없다(재검증·대체표현 생성뿐이라 더 짧을 가능성 높음,
// 확인 전엔 추정 안 함).
function estimatedTotalMs(imagesRequested: boolean): number {
  return imagesRequested ? 76_550 : 53_450;
}

export function GenerationLoading({ mode, imagesRequested = false }: GenerationLoadingProps) {
  const steps = buildSteps(mode, imagesRequested);
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const id = setInterval(() => setElapsedMs(Date.now() - startedAt), 200);
    return () => clearInterval(id);
  }, []);

  const total = estimatedTotalMs(imagesRequested);
  // 92%에서 점근선을 그린다 - 100%는 실제 응답이 도착했을 때만 부모가 이
  // 컴포넌트를 내려서 보여준다. 그 전에 100%에서 멈춰 있으면 오히려 불신을 준다.
  const rawProgress = 1 - Math.exp(-elapsedMs / (total * 0.6));
  const progressPct = Math.min(92, Math.round(rawProgress * 100));
  const stepDuration = total / steps.length;
  const activeStepIdx = Math.min(steps.length - 1, Math.floor(elapsedMs / stepDuration));

  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[320px] font-mono text-[12.5px] text-[var(--ink-3)] gap-4 p-6">
      <div className="w-full max-w-[340px] flex flex-col gap-[7px]">
        {steps.map((step, i) => {
          const isDone = i < activeStepIdx;
          const isActive = i === activeStepIdx;
          return (
            <div key={step} className="flex items-center gap-2">
              <span className="w-[12px] text-center shrink-0" aria-hidden="true">
                {isDone ? "✓" : isActive ? (
                  <span className="inline-block animate-[blink_1.1s_steps(1)_infinite]">›</span>
                ) : "·"}
              </span>
              <span className={isActive ? "text-[var(--ink)] font-bold" : isDone ? "" : "opacity-40"}>
                {step}
              </span>
            </div>
          );
        })}
      </div>
      <div className="w-full max-w-[340px] h-[5px] border border-[var(--line-2)] bg-[var(--surface-sub)] overflow-hidden">
        <div
          className="h-full bg-[var(--brand)] transition-[width] duration-300 ease-out"
          style={{ width: `${progressPct}%` }}
        />
      </div>
      <span className="text-[11px] tracking-[1px]">[ {progressPct}% ]</span>
    </div>
  );
}

export default GenerationLoading;
