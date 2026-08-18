"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

export type Tier = "Free" | "Basic" | "Pro";

const STORAGE_KEY = "barum-tier";
const IMPROVE_USED_KEY = "barum-improve-used";

interface TierContextValue {
  tier: Tier;
  setTier: (t: Tier) => void;
}

const TierContext = createContext<TierContextValue | null>(null);

function readTier(): Tier {
  if (typeof window === "undefined") return "Free";
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === "Free" || raw === "Basic" || raw === "Pro") return raw;
  return "Free";
}

export function TierProvider({ children }: { children: ReactNode }) {
  const [tier, setTierState] = useState<Tier>(readTier);

  const setTier = useCallback((t: Tier) => {
    setTierState(t);
    localStorage.setItem(STORAGE_KEY, t);
  }, []);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setTierState(readTier());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
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

function readImproveUsed(): number {
  if (typeof window === "undefined") return 0;
  const raw = localStorage.getItem(IMPROVE_USED_KEY);
  return raw ? parseInt(raw, 10) || 0 : 0;
}

export function useImproveQuota() {
  const FREE_LIMIT = 1;
  const [used, setUsedState] = useState(readImproveUsed);

  const remaining = Math.max(0, FREE_LIMIT - used);

  const consume = useCallback(() => {
    const next = used + 1;
    setUsedState(next);
    localStorage.setItem(IMPROVE_USED_KEY, String(next));
  }, [used]);

  const resetWithAd = useCallback(() => {
    setUsedState(0);
    localStorage.setItem(IMPROVE_USED_KEY, "0");
  }, []);

  return { used, remaining, consume, resetWithAd };
}
