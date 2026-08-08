import { Shield, ShieldCheck } from "@phosphor-icons/react/dist/ssr";

/**
 * 증거 확보 수준을 방패 모양으로 표시 (목업 .ev-badge 규격).
 * 색이 아니라 모양으로 구분한다(색각이상 대응, HANDOFF §3.1-4):
 *  - full: 체크 방패(shield-check)
 *  - half: 좌측 절반만 채운 방패(채운 방패를 50% 클립)
 *  - none: 빈 방패 (색은 한 단계 흐리게 ink-3, 상태 표현이 아니라 '비어있음' 표시)
 * 단색(currentColor)만 쓴다. 색으로 등급을 나누지 않는다.
 */
type Level = "full" | "half" | "none";

const LABEL: Record<Level, string> = {
  full: "근거 확보",
  half: "근거 일부",
  none: "근거 미확보",
};

export function EvidenceShield({
  level,
  size = 20,
}: {
  level: Level;
  size?: number;
}) {
  const tone = level === "none" ? "text-ink-3" : "text-ink-2";

  return (
    <span
      role="img"
      aria-label={LABEL[level]}
      title={LABEL[level]}
      className={`inline-grid place-items-center ${tone}`}
      style={{ width: size, height: size }}
    >
      {level === "full" && <ShieldCheck size={size} weight="regular" />}
      {level === "none" && <Shield size={size} weight="regular" />}
      {level === "half" && (
        <span
          className="relative inline-block"
          style={{ width: size, height: size }}
        >
          {/* 바탕: 빈 방패 윤곽 */}
          <Shield size={size} weight="regular" className="absolute inset-0" />
          {/* 좌측 절반만 채운 방패를 겹쳐 클립 → 진짜 '반쪽 채움' */}
          <span
            className="absolute inset-y-0 left-0 overflow-hidden"
            style={{ width: size / 2 }}
            aria-hidden="true"
          >
            <Shield
              size={size}
              weight="fill"
              className="absolute left-0 top-0"
            />
          </span>
        </span>
      )}
    </span>
  );
}
