/**
 * 상태 뱃지 (목업 .htag 규격). 사방 균일 테두리 + 옅은 배경 + 텍스트.
 * 색 규칙(HANDOFF §3.1-1): 경보(위해 고 등)만 crit 빨강, 나머지는 회색.
 * border-left 굵게 강조 금지 → border 유틸리티로 사방 1px 균일.
 *
 * props:
 *  - label: 표시 문구 (예: "위해 고", "진행 중")
 *  - tone:  'crit' = 지금 급한 경보만. 'muted'(기본) = 그 외 전부 회색.
 */
type Tone = "crit" | "muted";

export function StateBadge({
  label,
  tone = "muted",
}: {
  label: string;
  tone?: Tone;
}) {
  const toneCls =
    tone === "crit"
      ? "border-crit-bd bg-crit-bg text-crit"
      : "border-line-2 bg-surface-sub text-ink-2";

  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-[3px] border px-[7px] py-px text-[11px] font-bold ${toneCls}`}
    >
      {label}
    </span>
  );
}
