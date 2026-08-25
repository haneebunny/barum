"use client";

import { useCallback, useSyncExternalStore } from "react";

// 이용권(일회성 결제) 체계. 기존 Free/Basic/Pro 월 구독제를 대체한다.
//
// 실제 PG 결제는 이번 범위 밖이라 전부 localStorage 데모다. 다만 흐름은 실제와 같게
// 재현한다(구매 → 결제 완료 → 잔액 반영 → 소모). 백엔드에는 결제/구독 모델이 없다.

export type TicketKind = "domestic" | "content" | "combo" | "overseas";

/** 이용권 1장이 덮는 범위. 구매 UI와 게이팅이 같은 값을 보게 여기 모아둔다. */
export interface TicketProduct {
  kind: TicketKind;
  name: string;
  /** 1장이 무엇을 주는지 한 줄 설명 */
  desc: string;
  /** 묶음 옵션. 콘텐츠·해외는 단일만 판다. */
  packs: { size: number; price: number }[];
  /**
   * 국내 정식 상품 3종과 위계를 나눈다. 해외 프리플라이트는 아직 베타(선크림 단일
   * 품목)라 메인 가격표에 섞지 않고 아래쪽에 따로 안내한다.
   */
  beta?: boolean;
}

export const TICKET_PRODUCTS: TicketProduct[] = [
  {
    kind: "domestic",
    name: "리포트",
    desc: "국내 광고 검사 리포트 1건 전체 열람",
    packs: [
      { size: 1, price: 5900 },
      { size: 3, price: 15900 },
      { size: 5, price: 26500 },
    ],
  },
  {
    kind: "content",
    name: "콘텐츠 생성",
    desc: "화장품법을 지키는 상세페이지 초안 1건 생성",
    packs: [{ size: 1, price: 9900 }],
  },
  {
    kind: "combo",
    name: "결합형",
    desc: "국내 리포트 1건 전체 열람 + 상세페이지 초안 1건 생성",
    packs: [
      { size: 1, price: 12900 },
      { size: 3, price: 34800 },
      { size: 5, price: 58000 },
    ],
  },
  {
    kind: "overseas",
    name: "해외 프리플라이트",
    desc: "미국 수출 프리플라이트 리포트 1건 전체 열람",
    packs: [{ size: 1, price: 7900 }],
    beta: true,
  },
];

/** 메인 가격표에 나란히 세우는 국내 정식 3종 */
export const MAIN_PRODUCTS = TICKET_PRODUCTS.filter((p) => !p.beta);
/** 베타라 따로 안내하는 상품 */
export const BETA_PRODUCTS = TICKET_PRODUCTS.filter((p) => p.beta);

export function getProduct(kind: TicketKind): TicketProduct {
  const p = TICKET_PRODUCTS.find((x) => x.kind === kind);
  if (!p) throw new Error(`unknown ticket kind: ${kind}`);
  return p;
}

/** 상세페이지 생성 권한을 주는 이용권인지 */
export function grantsContent(kind: TicketKind): boolean {
  return kind === "content" || kind === "combo";
}

/** 리포트 열람 권한을 주는 이용권인지 */
export function grantsReport(kind: TicketKind): boolean {
  return kind === "domestic" || kind === "combo" || kind === "overseas";
}

/** 하루 무료 검사 한도. 국내 검사에만 적용되고 해외 프리플라이트는 무료체험이 없다. */
export const FREE_DAILY_LIMIT = 3;
/** 무료 요약 리포트 이력 보관 일수. 지나면 이력에서 만료 처리된다. */
export const FREE_SUMMARY_RETENTION_DAYS = 7;
/** 이용권 유효기간 */
export const TICKET_VALIDITY_DAYS = 365;
/** 만료 임박 안내를 띄우기 시작하는 잔여 일수 */
export const EXPIRY_WARNING_DAYS = 30;
/**
 * 콘텐츠 권한을 주는 이용권 1장이 만들어주는 상세페이지 건수.
 * 생성은 원샷이고(편집·재생성 UI가 없다) 무엇을 바꿀지 지시할 입력란도 없어서,
 * 여러 회를 파는 게 실효가 없다. 1장 = 상세페이지 1건으로 맞춘다.
 */
export const CONTENT_PER_TICKET = 1;

/**
 * 유효기간을 두는 이유. 구매·마이페이지·결제 모달에서 같은 문장을 써야 해서 상수로 둔다.
 * (요구사항: 1년 제한의 근거를 UI 카피에 명시할 것)
 */
export const TICKET_VALIDITY_NOTE =
  "이용권 유효기간은 구매일로부터 1년입니다. 판정 기준이 되는 레퍼런스 팩(식약처 고시·가이드라인)이 해마다 갱신되기 때문에, 오래된 기준으로 검사하지 않도록 기간을 둡니다.";

export const DEMO_CHECKOUT_NOTE = "데모 화면으로 실제 결제는 이뤄지지 않습니다.";

// ---------------------------------------------------------------------------
// localStorage 스토어 (SSR 안전)
// ---------------------------------------------------------------------------

// localStorage는 서버에 없어서 첫 렌더에 바로 읽으면 SSR(항상 기본값) vs 클라이언트가
// 달라져 hydration mismatch가 난다. useSyncExternalStore로 하이드레이션 렌더는 항상
// 서버 스냅샷을 쓰고, 마운트 후에만 실제 값으로 갈아끼운다.
//
// 객체를 돌려주는 스냅샷은 매번 새 참조를 만들면 무한 리렌더가 나므로, 원본 문자열이
// 그대로면 파싱 결과를 캐시해서 같은 참조를 돌려준다.
interface Store<T> {
  subscribe: (onStoreChange: () => void) => () => void;
  getSnapshot: () => T;
  getServerSnapshot: () => T;
  read: () => T;
  write: (next: T) => void;
}

function createStore<T>(key: string, empty: T, revive: (parsed: unknown) => T): Store<T> {
  const listeners = new Set<() => void>();
  let cachedRaw: string | null = null;
  let cachedValue: T = empty;
  let primed = false;

  function read(): T {
    let raw: string | null = null;
    try {
      raw = localStorage.getItem(key);
    } catch {
      return empty; // 접근 실패(프라이빗 모드 등)면 빈 값으로 동작
    }
    if (primed && raw === cachedRaw) return cachedValue;
    cachedRaw = raw;
    primed = true;
    if (raw === null) {
      cachedValue = empty;
      return cachedValue;
    }
    try {
      cachedValue = revive(JSON.parse(raw));
    } catch {
      cachedValue = empty; // 손상된 값은 빈 값 취급, 다음 write에서 덮인다
    }
    return cachedValue;
  }

  function write(next: T) {
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // 저장 실패해도 이번 화면에서는 반영되게 캐시는 갱신한다
      cachedRaw = null;
      primed = true;
      cachedValue = next;
    }
    listeners.forEach((notify) => notify());
  }

  return {
    subscribe(onStoreChange) {
      listeners.add(onStoreChange);
      const onStorage = (e: StorageEvent) => {
        if (e.key === key) onStoreChange();
      };
      window.addEventListener("storage", onStorage);
      return () => {
        listeners.delete(onStoreChange);
        window.removeEventListener("storage", onStorage);
      };
    },
    getSnapshot: read,
    getServerSnapshot: () => empty,
    read,
    write,
  };
}

// ---------------------------------------------------------------------------
// 이용권 잔액
// ---------------------------------------------------------------------------

/**
 * 구매 단위(lot). 만료일이 구매 시점마다 다르므로 종류별 합산이 아니라 구매 건별로 쌓는다.
 * 소모는 만료가 임박한 lot부터 빼서 사용자가 손해를 덜 본다.
 */
export interface TicketLot {
  id: string;
  kind: TicketKind;
  /** 구매 수량 */
  size: number;
  /** 남은 수량 */
  remaining: number;
  /** 결제 금액(구매 이력 표시용) */
  price: number;
  purchasedAt: string;
  expiresAt: string;
}

const TICKETS_KEY = "barum-tickets";

const ticketStore = createStore<TicketLot[]>(TICKETS_KEY, [], (parsed) =>
  Array.isArray(parsed) ? (parsed as TicketLot[]) : [],
);

function addDays(from: Date, days: number): Date {
  const d = new Date(from);
  d.setDate(d.getDate() + days);
  return d;
}

/** 만료일까지 남은 일수. 이미 지났으면 음수. */
export function daysUntil(iso: string): number {
  const MS_PER_DAY = 86400000;
  const end = new Date(iso).getTime();
  return Math.ceil((end - Date.now()) / MS_PER_DAY);
}

export function isExpired(lot: TicketLot): boolean {
  return new Date(lot.expiresAt).getTime() <= Date.now();
}

/** 샘플 데이터 체험 진입 시 이용권을 미리 채운다 — 이용권 없이 열람되게 한다.
 * 실제 결제가 아니며, 데모 lot이 이미 있으면 중복 시드하지 않는다. */
export function grantDemoAccess(): void {
  try {
    const lots = ticketStore.read();
    if (lots.some((l) => l.id === "demo-combo")) return;
    const now = new Date();
    ticketStore.write([
      ...lots,
      {
        id: "demo-combo",
        kind: "combo",
        size: 9,
        remaining: 9,
        price: 0,
        purchasedAt: now.toISOString(),
        expiresAt: addDays(now, TICKET_VALIDITY_DAYS).toISOString(),
      },
    ]);
  } catch {
    /* localStorage 접근 실패(프라이빗 모드 등)면 조용히 넘어간다 */
  }
}

/** 아직 쓸 수 있는 lot(만료 전 + 잔량 있음)을 만료 임박 순으로 */
function usableLots(lots: TicketLot[]): TicketLot[] {
  return lots
    .filter((l) => l.remaining > 0 && !isExpired(l))
    .sort((a, b) => new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime());
}

export function useTickets() {
  const lots = useSyncExternalStore(
    ticketStore.subscribe,
    ticketStore.getSnapshot,
    ticketStore.getServerSnapshot,
  );

  const balance = (kind: TicketKind): number =>
    usableLots(lots)
      .filter((l) => l.kind === kind)
      .reduce((sum, l) => sum + l.remaining, 0);

  const has = (kind: TicketKind): boolean => balance(kind) > 0;

  /** 만료 임박(기본 30일 이내) lot. 잔량이 남은 것만 알린다. */
  const expiringSoon = usableLots(lots).filter((l) => daysUntil(l.expiresAt) <= EXPIRY_WARNING_DAYS);

  /** 만료된 lot. 잔액에선 빠지지만 마이페이지엔 '만료'로 남긴다. */
  const expired = lots.filter((l) => isExpired(l) && l.remaining > 0);

  const purchase = useCallback((kind: TicketKind, size: number) => {
    const product = getProduct(kind);
    const pack = product.packs.find((p) => p.size === size);
    if (!pack) throw new Error(`unknown pack: ${kind} x${size}`);
    const now = new Date();
    const lot: TicketLot = {
      // Date+난수 조합이면 같은 밀리초에 두 번 눌려도 안 겹친다
      id: `${now.getTime().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
      kind,
      size: pack.size,
      remaining: pack.size,
      price: pack.price,
      purchasedAt: now.toISOString(),
      expiresAt: addDays(now, TICKET_VALIDITY_DAYS).toISOString(),
    };
    ticketStore.write([...ticketStore.read(), lot]);
    return lot;
  }, []);

  /** 이용권 1장 소모. 쓸 게 없으면 false. */
  const consume = useCallback((kind: TicketKind): boolean => {
    const current = ticketStore.read();
    const target = usableLots(current).find((l) => l.kind === kind);
    if (!target) return false;
    ticketStore.write(
      current.map((l) => (l.id === target.id ? { ...l, remaining: l.remaining - 1 } : l)),
    );
    return true;
  }, []);

  return { lots, balance, has, expiringSoon, expired, purchase, consume };
}

// ---------------------------------------------------------------------------
// 일일 무료 검사 카운터 (국내 검사 전용)
// ---------------------------------------------------------------------------

interface DailyChecks {
  /** YYYY-MM-DD 로컬 날짜. 바뀌면 카운트를 0으로 본다. */
  date: string;
  count: number;
}

const DAILY_KEY = "barum-daily-checks";
const EMPTY_DAILY: DailyChecks = { date: "", count: 0 };

const dailyStore = createStore<DailyChecks>(DAILY_KEY, EMPTY_DAILY, (parsed) => {
  const p = parsed as Partial<DailyChecks> | null;
  if (!p || typeof p.date !== "string" || typeof p.count !== "number") return EMPTY_DAILY;
  return { date: p.date, count: p.count };
});

/** 로컬 기준 오늘 날짜. UTC로 자르면 한국 자정과 어긋나서 로컬 값을 쓴다. */
function todayKey(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function useDailyChecks() {
  const stored = useSyncExternalStore(
    dailyStore.subscribe,
    dailyStore.getSnapshot,
    dailyStore.getServerSnapshot,
  );

  // 날짜가 바뀌었으면 저장값과 무관하게 0부터. 굳이 write로 밀지 않고 읽을 때 판단한다.
  const used = stored.date === todayKey() ? stored.count : 0;
  const remaining = Math.max(0, FREE_DAILY_LIMIT - used);

  const record = useCallback(() => {
    const today = todayKey();
    const current = dailyStore.read();
    const base = current.date === today ? current.count : 0;
    dailyStore.write({ date: today, count: base + 1 });
  }, []);

  return { used, remaining, limit: FREE_DAILY_LIMIT, canRunFreeCheck: remaining > 0, record };
}

// ---------------------------------------------------------------------------
// 리포트별 열람 상태
// ---------------------------------------------------------------------------

/**
 * 리포트 하나에 대한 접근 상태.
 * - 무료 요약이면 unlockedWith가 없고, previewViolationId 1건만 미리 볼 수 있다(한 번 고르면 고정).
 * - 이용권으로 열면 unlockedWith가 채워지고 무기한 보관된다.
 */
export interface ReportAccess {
  /** 무료 요약에서 사용자가 고른 미리보기 위반 1건. 한 번 고르면 못 바꾼다. */
  previewViolationId?: string;
  /** 어떤 이용권으로 열었는지. 없으면 아직 무료 요약. */
  unlockedWith?: TicketKind;
  unlockedAt?: string;
  /**
   * 이 리포트(또는 콘텐츠 작업공간)에 붙은 상세페이지 생성 권한 수.
   * 결합형으로 열었거나 콘텐츠 이용권을 붙일 때마다 1씩 늘어난다.
   */
  contentAllowance: number;
  /** 그중 실제로 생성에 쓴 수 */
  contentUsed: number;
}

const ACCESS_KEY = "barum-report-access";
const EMPTY_ACCESS: Record<string, ReportAccess> = {};

const accessStore = createStore<Record<string, ReportAccess>>(ACCESS_KEY, EMPTY_ACCESS, (parsed) =>
  parsed && typeof parsed === "object" ? (parsed as Record<string, ReportAccess>) : EMPTY_ACCESS,
);

const DEFAULT_ACCESS: ReportAccess = { contentAllowance: 0, contentUsed: 0 };

/** 저장된 값에 새 필드가 없을 수 있어(구버전 데모 데이터) 기본값으로 메운다. */
function withDefaults(a: ReportAccess | undefined): ReportAccess {
  if (!a) return DEFAULT_ACCESS;
  return {
    ...a,
    contentAllowance: a.contentAllowance ?? 0,
    contentUsed: a.contentUsed ?? 0,
  };
}

/** 리포트 접근 상태 전체(이력 페이지처럼 여러 건을 한 번에 볼 때) */
export function useAllReportAccess() {
  return useSyncExternalStore(
    accessStore.subscribe,
    accessStore.getSnapshot,
    accessStore.getServerSnapshot,
  );
}

export function useReportAccess(reportId: string) {
  const all = useAllReportAccess();
  const access = withDefaults(all[reportId]);

  const update = useCallback(
    (patch: Partial<ReportAccess>) => {
      const current = accessStore.read();
      const prev = withDefaults(current[reportId]);
      accessStore.write({ ...current, [reportId]: { ...prev, ...patch } });
    },
    [reportId],
  );

  /** 무료 요약에서 미리 볼 위반 1건 선택. 이미 골랐으면 무시한다(재선택 불가). */
  const pickPreview = useCallback(
    (violationId: string) => {
      const prev = withDefaults(accessStore.read()[reportId]);
      if (prev.previewViolationId) return;
      update({ previewViolationId: violationId });
    },
    [reportId, update],
  );

  /**
   * 이용권 1장을 이 리포트에 붙여 연다. 결합형은 상세페이지 생성 권한도 같이 준다.
   * (호출 전에 useTickets().consume으로 잔액을 먼저 차감해야 한다)
   */
  const unlock = useCallback(
    (kind: TicketKind) => {
      const prev = withDefaults(accessStore.read()[reportId]);
      update({
        unlockedWith: kind,
        unlockedAt: new Date().toISOString(),
        contentAllowance: prev.contentAllowance + (grantsContent(kind) ? CONTENT_PER_TICKET : 0),
      });
    },
    [reportId, update],
  );

  /**
   * 콘텐츠 생성 권한만 1건 붙인다. 콘텐츠 단독 이용권을 썼거나, 이미 붙은 권한을
   * 다 쓰고 한 장 더 쓸 때. 리포트 열람 상태(unlockedWith)는 건드리지 않는다.
   */
  const grantContent = useCallback(() => {
    const prev = withDefaults(accessStore.read()[reportId]);
    update({ contentAllowance: prev.contentAllowance + CONTENT_PER_TICKET });
  }, [reportId, update]);

  /** 상세페이지 1건 소모. 남은 권한이 없으면 false. */
  const consumeContent = useCallback((): boolean => {
    const prev = withDefaults(accessStore.read()[reportId]);
    if (prev.contentUsed >= prev.contentAllowance) return false;
    update({ contentUsed: prev.contentUsed + 1 });
    return true;
  }, [reportId, update]);

  const isUnlocked = Boolean(access.unlockedWith);
  /** 아직 안 쓴 상세페이지 생성 권한 수 */
  const contentRemaining = Math.max(0, access.contentAllowance - access.contentUsed);
  /** 지금 상세페이지를 만들 수 있는지 */
  const canGenerateContent = contentRemaining > 0;

  return {
    access,
    isUnlocked,
    contentRemaining,
    canGenerateContent,
    pickPreview,
    unlock,
    grantContent,
    consumeContent,
  };
}

// ---------------------------------------------------------------------------
// 무료 요약 보관 만료
// ---------------------------------------------------------------------------

/**
 * 무료 요약 리포트가 7일 보관을 넘겼는지. 이용권으로 연 리포트는 무기한이라 항상 false.
 * createdAt은 리포트 생성 시각(이력의 created_at).
 */
export function isFreeSummaryExpired(createdAt: string, access: ReportAccess | undefined): boolean {
  if (access?.unlockedWith) return false;
  return -daysUntil(createdAt) >= FREE_SUMMARY_RETENTION_DAYS;
}

/** 무료 요약이 사라지기까지 남은 일수 */
export function freeSummaryDaysLeft(createdAt: string): number {
  const elapsed = -daysUntil(createdAt);
  return Math.max(0, FREE_SUMMARY_RETENTION_DAYS - elapsed);
}

export function formatPrice(won: number): string {
  return `${won.toLocaleString("ko-KR")}원`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}.${m}.${day}`;
}
