"use client";

import React, { useEffect, useImperativeHandle, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  isOpen: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md";
}

export const Modal = React.forwardRef<HTMLButtonElement, ModalProps>(
  ({ isOpen, title, onClose, children, footer, size = "sm" }, ref) => {
    const closeBtnRef = useRef<HTMLButtonElement>(null);
    const [mounted, setMounted] = useState(false);

    // SSR 대응을 위해 클라이언트 사이드 마운트 여부 체크
    useEffect(() => {
      setMounted(true);
    }, []);

    // Forward the ref to closeBtnRef
    useImperativeHandle(ref, () => closeBtnRef.current!);

    useEffect(() => {
      if (isOpen && mounted) {
        closeBtnRef.current?.focus();
      }
    }, [isOpen, mounted]);

    if (!isOpen || !mounted) return null;

    const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    };

    const modalHTML = (
      <div
        className="fixed inset-0 bg-[#070b08]/50 flex items-center justify-center p-5 z-50"
        onClick={handleBackdropClick}
      >
        <div
          className={`w-full bg-[var(--surface)] border border-[var(--line-2)] font-mono shadow-[0_14px_44px_rgba(7,11,8,0.28)] animate-[modalin_0.16s_ease] ${
            size === "md" ? "max-w-[560px]" : "max-w-[380px]"
          }`}
          role="dialog"
          aria-modal="true"
          aria-label={title}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-3 px-4 border-b border-[var(--line-2)] bg-[var(--surface-sub)] text-[15px] text-[var(--brand-ink)] font-bold tracking-[0.3px]">
            <span>[ {title} ]</span>
            <button
              className="border-0 bg-transparent text-[var(--ink-3)] cursor-pointer font-mono text-[14px] leading-none p-0.5 px-1 hover:text-[var(--ink)]"
              ref={closeBtnRef}
              aria-label="닫기"
              onClick={onClose}
            >
              ✕
            </button>
          </div>
          <div className="p-4 px-5">
            {children}
          </div>
          {footer && (
            <div className="flex justify-end gap-2 p-3 px-5 pb-4 border-t border-dashed border-[var(--line-2)]">
              {footer}
            </div>
          )}
        </div>
      </div>
    );

    return createPortal(modalHTML, document.body);
  }
);

Modal.displayName = "Modal";
