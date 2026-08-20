"use client";

import { createContext, useContext, useCallback, useSyncExternalStore, type ReactNode } from "react";

export type Tier = "Free" | "Basic" | "Pro";

const STORAGE_KEY = "barum-tier";
const IMPROVE_USED_KEY = "barum-improve-used";

interface TierContextValue {
  tier: Tier;
  setTier: (t: Tier) => void;
}

const TierContext = createContext<TierContextValue | null>(null);

// localStorage는 서버에 없어서 첫 렌더에 바로 읽으면 SSR(항상 기본값) vs 클라이언트(사용자가
// 이전에 고른 값)가 달라져 hydration mismatch가 난다. useSyncExternalStore로 하이드레이션
// 렌더는 항상 서버 스냅샷을 쓰고, 마운트 후에만 실제 값으로 갈아끼운다(AppShell 사이드바 접힘과 동일 패턴).
const tierListeners = new Set<() => void>();

function subscribeTier(onStoreChange: () => void) {
  tierListeners.add(onStoreChange);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) onStoreChange();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    tierListeners.delete(onStoreChange);
    window.removeEventListener("storage", onStorage);
  };
}

function getTierSnapshot(): Tier {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "Free" || raw === "Basic" || raw === "Pro") return raw;
  } catch {
    // 접근 실패 시 기본값
  }
  return "Free";
}

function getTierServerSnapshot(): Tier {
  return "Free";
}

export function TierProvider({ children }: { children: ReactNode }) {
  const tier = useSyncExternalStore(subscribeTier, getTierSnapshot, getTierServerSnapshot);

  const setTier = useCallback((t: Tier) => {
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch {
      // 저장 실패해도 이번 화면에서는 그대로 반영
    }
    tierListeners.forEach((notify) => notify());
  }, []);

  return (
    <TierContext.Provider value={{ tier, setTier }}>
      {children}
    </TierContext.Provider>
  );
}

export function useTier() {
  const ctx = useContext(TierContext);
  if (!ctx) throw new Error("useTier must be used inside TierProvider");
  return ctx;
}

const improveUsedListeners = new Set<() => void>();

function subscribeImproveUsed(onStoreChange: () => void) {
  improveUsedListeners.add(onStoreChange);
  return () => improveUsedListeners.delete(onStoreChange);
}

function getImproveUsedSnapshot(): number {
  try {
    const raw = localStorage.getItem(IMPROVE_USED_KEY);
    return raw ? parseInt(raw, 10) || 0 : 0;
  } catch {
    return 0;
  }
}

function getImproveUsedServerSnapshot(): number {
  return 0;
}

export function useImproveQuota() {
  const FREE_LIMIT = 1;
  const used = useSyncExternalStore(subscribeImproveUsed, getImproveUsedSnapshot, getImproveUsedServerSnapshot);

  const remaining = Math.max(0, FREE_LIMIT - used);

  const consume = useCallback(() => {
    try {
      localStorage.setItem(IMPROVE_USED_KEY, String(getImproveUsedSnapshot() + 1));
    } catch {
      // 저장 실패해도 이번 화면에서는 그대로 반영
    }
    improveUsedListeners.forEach((notify) => notify());
  }, []);

  const resetWithAd = useCallback(() => {
    try {
      localStorage.setItem(IMPROVE_USED_KEY, "0");
    } catch {
      // 저장 실패해도 이번 화면에서는 그대로 반영
    }
    improveUsedListeners.forEach((notify) => notify());
  }, []);

  return { used, remaining, consume, resetWithAd };
}
