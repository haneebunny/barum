import { StateBadge } from "@/components/StateBadge/StateBadge";
import { EvidenceShield } from "@/components/EvidenceShield/EvidenceShield";

/**
 * 디자인 시스템 쇼케이스(개발/검증용). 토큰·컴포넌트를 한 화면에 렌더한다.
 * 상단 우측 테마 토글로 라이트/다크를 바꿔가며 색·대비를 눈이 아니라 이 화면으로 검증.
 * 색 스와치는 Tailwind bg-* 유틸리티(리터럴)로 칠해 @theme 브리지가 실제로 도는지도 확인.
 */

type Swatch = { cls: string; name: string; token: string; note?: string };

const SURFACES: Swatch[] = [
  { cls: "bg-canvas", name: "캔버스", token: "--canvas" },
  { cls: "bg-surface", name: "표면", token: "--surface" },
  { cls: "bg-surface-sub", name: "표면 보조", token: "--surface-sub" },
];

const BRAND: Swatch[] = [
  { cls: "bg-navy", name: "네이비(구조)", token: "--navy" },
  { cls: "bg-accent", name: "액센트(인터랙션)", token: "--accent" },
  { cls: "bg-accent-2", name: "액센트 강", token: "--accent-2" },
  { cls: "bg-accent-weak", name: "액센트 옅음", token: "--accent-weak" },
];

const SEMANTIC: Swatch[] = [
  { cls: "bg-crit", name: "위해 경보", token: "--crit", note: "유일 심각도 색" },
  { cls: "bg-ok", name: "정상 · 이행", token: "--ok" },
  { cls: "bg-low", name: "저(회색)", token: "--low" },
  { cls: "bg-info", name: "정보", token: "--info" },
  { cls: "bg-warn", name: "앰버", token: "--warn", note: "정의만, 심각도색 금지" },
];

function SwatchGrid({ items }: { items: Swatch[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {items.map((s) => (
        <div key={s.token}>
          <div
            className={`h-14 rounded-app border border-line ${s.cls}`}
            aria-hidden="true"
          />
          <div className="mt-1.5 text-[12px] font-semibold text-ink">
            {s.name}
          </div>
          <div className="text-[11px] text-ink-3">
            <code>{s.token}</code>
            {s.note && <span className="text-crit"> · {s.note}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function Section({
  title,
  desc,
  children,
}: {
  title: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-card border border-line bg-surface p-5 shadow-card">
      <h2 className="m-0 text-[15px] font-bold text-ink">{title}</h2>
      {desc && <p className="mt-1 mb-0 text-[12.5px] text-ink-3">{desc}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function StyleguidePage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="m-0 text-[22px] font-extrabold tracking-tight text-ink">
          스타일가이드
        </h1>
        <p className="mt-1 mb-0 text-[12.5px] text-ink-3">
          토큰과 공용 컴포넌트 쇼케이스. 우측 상단 토글로 라이트/다크를 전환해
          검증한다.
        </p>
      </header>

      <Section
        title="표면 · 텍스트 · 라인"
        desc="쿨 뉴트럴 표면과 3단계 텍스트, 2단계 라인."
      >
        <SwatchGrid items={SURFACES} />
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-app border border-line bg-surface p-3">
            <p className="m-0 text-[14px] text-ink">본문 텍스트 --ink</p>
            <p className="m-0 text-[13px] text-ink-2">보조 텍스트 --ink-2</p>
            <p className="m-0 text-[12px] text-ink-3">흐린 텍스트 --ink-3</p>
          </div>
          <div className="grid place-items-center gap-2 rounded-app border border-line bg-surface p-3">
            <div className="h-8 w-full rounded-app border border-line" />
            <div className="h-8 w-full rounded-app border border-line-2" />
            <span className="text-[11px] text-ink-3">
              --line / --line-2 (사방 균일, border-left 강조 금지)
            </span>
          </div>
        </div>
      </Section>

      <Section
        title="브랜드"
        desc="네이비는 구조(브랜드), 정부 블루는 인터랙션."
      >
        <SwatchGrid items={BRAND} />
      </Section>

      <Section
        title="시맨틱 색"
        desc="색은 '지금 급한 것'에만. 시스템은 빨강만 경보, 나머지는 회색. 앰버는 빨강과 색각이상 구분이 안 돼 심각도 색으로 쓰지 않는다."
      >
        <SwatchGrid items={SEMANTIC} />
      </Section>

      <Section
        title="StateBadge"
        desc="사방 균일 테두리 + 옅은 배경 + 텍스트. 경보(위해 고)만 crit, 나머지는 muted 회색."
      >
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge label="위해 고" tone="crit" />
          <StateBadge label="기한 초과" tone="crit" />
          <StateBadge label="위해 중" />
          <StateBadge label="위해 저" />
          <StateBadge label="진행 중" />
          <StateBadge label="추적" />
        </div>
      </Section>

      <Section
        title="EvidenceShield"
        desc="증거 확보 수준을 색이 아니라 모양으로 구분(색각이상 대응). 단색만."
      >
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2">
            <EvidenceShield level="full" size={22} />
            <span className="text-[12px] text-ink-2">근거 확보</span>
          </div>
          <div className="flex items-center gap-2">
            <EvidenceShield level="half" size={22} />
            <span className="text-[12px] text-ink-2">근거 일부</span>
          </div>
          <div className="flex items-center gap-2">
            <EvidenceShield level="none" size={22} />
            <span className="text-[12px] text-ink-2">근거 미확보</span>
          </div>
        </div>
      </Section>

      <Section
        title="숫자 정렬"
        desc="전역 tabular-nums. 자릿수가 세로로 맞아 표에서 흔들리지 않는다."
      >
        <div className="font-mono text-[13px] leading-6 text-ink">
          <div>1,204</div>
          <div>9,887</div>
          <div>10,003</div>
        </div>
      </Section>
    </div>
  );
}
