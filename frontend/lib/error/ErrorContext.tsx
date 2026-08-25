"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Modal } from "@/components/Modal/Modal";

interface ErrorContextType {
  showError: (title: string, message: string) => void;
  hideError: () => void;
}

const ErrorContext = createContext<ErrorContextType | undefined>(undefined);

export function ErrorProvider({ children }: { children: React.ReactNode }) {
  const [errorState, setErrorState] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
  }>({
    isOpen: false,
    title: "",
    message: "",
  });

  const showError = useCallback((title: string, message: string) => {
    setErrorState({
      isOpen: true,
      title: title || "오류",
      message: message || "알 수 없는 오류가 발생했습니다.",
    });
  }, []);

  const hideError = useCallback(() => {
    setErrorState((prev) => ({ ...prev, isOpen: false }));
  }, []);

  useEffect(() => {
    const handleGlobalError = (event: ErrorEvent) => {
      // 렌더링 에러 혹은 스크립트 에러 감지
      event.preventDefault();
      const message = event.error?.message || event.message || "알 수 없는 런타임 오류가 발생했습니다.";
      showError("시스템 오류", message);
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      // 비동기 fetch 등 Promise 캐치되지 않은 에러 감지
      event.preventDefault();
      const message = event.reason instanceof Error
        ? event.reason.message
        : typeof event.reason === "string"
        ? event.reason
        : "네트워크 혹은 서버 연결에 실패했습니다.";
      showError("네트워크 오류", message);
    };

    window.addEventListener("error", handleGlobalError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleGlobalError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, [showError]);

  const footer = (
    <button
      type="button"
      onClick={hideError}
      className="px-4 py-1.5 bg-[var(--ink)] text-[var(--surface)] hover:bg-[var(--ink-2)] border-0 font-mono text-[12px] font-bold cursor-pointer transition-all duration-[120ms]"
    >
      확인
    </button>
  );

  return (
    <ErrorContext.Provider value={{ showError, hideError }}>
      {children}
      <Modal
        isOpen={errorState.isOpen}
        title={errorState.title}
        onClose={hideError}
        footer={footer}
        size="sm"
      >
        <div className="text-[13px] text-[var(--ink-2)] leading-[1.6] break-keep font-sans whitespace-pre-wrap">
          {errorState.message}
        </div>
      </Modal>
    </ErrorContext.Provider>
  );
}

export function useError() {
  const context = useContext(ErrorContext);
  if (context === undefined) {
    throw new Error("useError must be used within an ErrorProvider");
  }
  return context;
}
