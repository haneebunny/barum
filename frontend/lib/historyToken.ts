const HISTORY_TOKEN_KEY = "barum-anonymous-history-token";

function createHistoryToken(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** 같은 브라우저에서 재접속해도 유지되는 익명 검사 이력 토큰. */
export function getOrCreateHistoryToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(HISTORY_TOKEN_KEY);
    if (stored && stored.length >= 32) return stored;
    const token = createHistoryToken();
    window.localStorage.setItem(HISTORY_TOKEN_KEY, token);
    return token;
  } catch (error) {
    console.warn("검사 이력 토큰을 저장하지 못했습니다.", error);
    return null;
  }
}

export function historyTokenHeaders(): Record<string, string> {
  const token = getOrCreateHistoryToken();
  return token ? { "X-History-Token": token } : {};
}
